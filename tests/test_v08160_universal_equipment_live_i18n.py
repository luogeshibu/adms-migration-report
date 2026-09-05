from pathlib import Path

from migration_report_tool.config.column_schema import EQUIPMENT_SOURCE_GROUPS
from migration_report_tool.config.sources.definitions import SOURCE_SCHEMAS
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.rmu_review_service import build_equipment_source_view
from migration_report_tool.services.schema_service import EQUIPMENT_SOURCE_DISPLAY_BINDINGS
from migration_report_tool.adapters import SourceAdapter
from migration_report_tool.version import __version__


class MultiAdapter(SourceAdapter):
    def __init__(self, tables):
        self.tables = {key: list(value) for key, value in tables.items()}

    def load_rows(self, source_type: str):
        return [dict(row) for row in self.tables.get(source_type, [])]


def test_release_version():
    assert __version__ == "0.8.160"


def test_runtime_translation_has_bidirectional_canonical_source_guard():
    i18n = Path("src/migration_report_tool/ui/i18n.py").read_text(encoding="utf-8")
    assert "def _reverse_exact_translation" in i18n
    assert "known_renderings = {source, tr(source, LANG_EN), tr(source, LANG_ZH_CN)}" in i18n
    assert "return _reverse_exact_translation(source)" in i18n


def test_adms_sld_has_separate_type_and_device_type_contracts():
    fields = {field.key: field for field in SOURCE_SCHEMAS["adms_sld"].fields}
    assert "rmu_type" in fields
    assert "device_type" in fields
    adms_group = next(cols for group, _color, cols in EQUIPMENT_SOURCE_GROUPS if group == "ADMS SLD")
    keys = [key for key, _label, _width in adms_group]
    assert "eq_asld_type" in keys
    assert "eq_asld_device_type" in keys
    assert EQUIPMENT_SOURCE_DISPLAY_BINDINGS["eq_asld_device_type"] == ("adms_sld", "device_type")


def test_rmu_and_other_equipment_use_same_universal_five_source_payload(tmp_path: Path):
    tables = {
        "zenon_sld": [
            {"device_type": "RMU", "rmu": "100", "feeder": "ADEL-01", "cabinet_type": "2L1T", "smart": "SMART"},
            {"device_type": "TRANSFORMER", "rmu": "200", "feeder": "ADEL-02", "cabinet_type": "OH_TR"},
        ],
        "adms_sld": [
            {"rmu": "100", "feeder": "ADEL-01", "rmu_type": "2L1T", "device_type": "RMU", "smart": "SMART"},
            {"rmu": "200", "feeder": "ADEL-02", "rmu_type": "OH_TR", "device_type": "TRANSFORMER"},
        ],
    }
    store = ProjectStore(tmp_path / "project")
    try:
        rmu_rows, _ = build_equipment_source_view(store, "RMU", MultiAdapter(tables))
        tx_rows, _ = build_equipment_source_view(store, "TRANSFORMER", MultiAdapter(tables))
        assert rmu_rows[0]["review_key"] == "100"  # historical RMU key preserved
        assert tx_rows[0]["review_key"] == "EQ::TRANSFORMER::200"
        for row in (rmu_rows[0], tx_rows[0]):
            assert "equipment_source_count" in row
            assert "analysis_name" in row
            assert "eq_asld_type" in row
            assert "eq_asld_device_type" in row
        assert rmu_rows[0]["eq_asld_device_type"] == "RMU"
        assert tx_rows[0]["eq_asld_device_type"] == "TRANSFORMER"
    finally:
        store.close()


def test_main_window_no_longer_selects_legacy_rmu_table_schema():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    block_start = ui.index("def _comparison_groups(self):")
    block_end = ui.index("def _comparison_columns(self):", block_start)
    block = ui[block_start:block_end]
    assert "rmu_review_groups" not in block
    assert "equipment_source_review_groups" in block
    assert "inventory_mode = True" in ui
