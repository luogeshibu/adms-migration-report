from pathlib import Path
from types import SimpleNamespace

from migration_report_tool.services import import_service
from migration_report_tool.version import __version__


class _Db:
    def __init__(self):
        self.calls = []
    def execute(self, *args):
        self.calls.append(args)
    def commit(self):
        pass


class _Store:
    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.db = _Db()
        self._overrides = {}
        self.stored = None
    def source_column_overrides(self, _source_type):
        return dict(self._overrides)
    def set_source(self, source_type, selected):
        target = self.tmp_path / f"{source_type}{Path(selected).suffix}"
        target.write_bytes(Path(selected).read_bytes())
        self.stored = target
        return target


def test_release_version():
    assert __version__ == "0.8.149"


def test_unresolved_source_is_staged_for_remapping(monkeypatch, tmp_path):
    source = tmp_path / "replacement.csv"
    source.write_text("NewRMU,NewFeeder,NewType\n1,F-1,T-1\n", encoding="utf-8")
    validation = SimpleNamespace(
        headers=("NewRMU", "NewFeeder", "NewType"),
        errors=("RMU missing", "FEEDER missing"),
        error_message=lambda name: f"{name}: required mapping missing",
    )
    monkeypatch.setattr(import_service, "validate_source_file", lambda *_a, **_k: validation)
    monkeypatch.setattr(import_service, "read_mapped_rows", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("strict reader must not run while mapping is pending")))
    store = _Store(tmp_path)

    result = import_service.import_source(store, "zenon_db", source, allow_unresolved_mapping=True)

    assert result.mapping_required is True
    assert result.detected_headers == validation.headers
    assert result.stored_path.exists()
    assert result.row_count == 0


def test_normal_import_still_rejects_unresolved_mapping(monkeypatch, tmp_path):
    source = tmp_path / "replacement.csv"
    source.write_text("Other\n1\n", encoding="utf-8")
    validation = SimpleNamespace(headers=("Other",), errors=("missing",), error_message=lambda name: name)
    monkeypatch.setattr(import_service, "validate_source_file", lambda *_a, **_k: validation)

    # Patch the exception class imported lazily by import_source.
    import migration_report_tool.domain.schema as schema_mod
    class _SchemaValidationError(Exception):
        pass
    monkeypatch.setattr(schema_mod, "SchemaValidationError", _SchemaValidationError)

    store = _Store(tmp_path)
    try:
        import_service.import_source(store, "zenon_db", source)
    except _SchemaValidationError:
        pass
    else:
        raise AssertionError("strict import must still reject unresolved required mappings")


def test_ui_contract_opens_map_fields_instead_of_schema_failure():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert "Source Loaded · Mapping Required" in ui
    assert "This is not a source-file error. Remap the required App Columns" in ui
    assert "open_mapping_on_required=True" in ui
    assert "self._open_source_mapping_for_type" in ui
    assert "allow_unresolved_mapping=True" in ui
    assert "Source staged · field mapping required before RMU Analysis" in ui
    assert 'schema_text = "MAPPING REQUIRED"' in ui
    assert 'store.config["pending_source_mappings"] = pending_source_mappings' in ui


def test_v08148_protected_system_mapping_contract_remains():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert "Unlock System Mappings..." in ui
    assert "SYSTEM · UNLOCKED" in ui
    assert "SYSTEM · LOCKED" in ui
    assert "Protected system mapping changes were not saved" in ui
