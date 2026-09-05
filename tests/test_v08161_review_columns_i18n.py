from pathlib import Path

from migration_report_tool.adapters import SourceAdapter
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.rmu_review_service import build_equipment_source_view
from migration_report_tool.services.schema_service import (
    equipment_review_column_key,
    equipment_review_protected_column_keys,
    equipment_source_review_groups,
)
from migration_report_tool.version import __version__


class MultiAdapter(SourceAdapter):
    def __init__(self, tables):
        self.tables = {key: list(value) for key, value in tables.items()}

    def load_rows(self, source_type: str):
        return [dict(row) for row in self.tables.get(source_type, [])]


def test_release_version():
    assert __version__ == "0.8.161"


def test_all_builtin_app_fields_are_available_to_equipment_review(tmp_path: Path):
    store = ProjectStore(tmp_path / "project")
    try:
        groups = equipment_source_review_groups(store)
        keys = {key for _group, _color, cols in groups for key, _label, _width in cols}
        assert equipment_review_column_key("zenon_sld", "script_version") in keys
        assert equipment_review_column_key("zenon_sld", "destination_name") in keys
        assert equipment_review_column_key("zenon_sld", "resolved_full_name") in keys
        assert equipment_review_column_key("adms_sld", "device_type") in keys
        assert equipment_review_column_key("adms_sld", "rmu_type") in keys
    finally:
        store.close()


def test_system_calculation_fields_are_protected_but_optional_fields_are_not():
    protected = equipment_review_protected_column_keys()
    assert equipment_review_column_key("zenon_sld", "device_type") in protected
    assert equipment_review_column_key("zenon_sld", "rmu") in protected
    assert equipment_review_column_key("zenon_sld", "feeder") in protected
    assert equipment_review_column_key("zenon_sld", "cabinet_type") in protected
    assert equipment_review_column_key("zenon_sld", "duplicate_count") in protected
    assert equipment_review_column_key("adms_sld", "device_type") in protected
    assert equipment_review_column_key("adms_sld", "rmu_type") in protected
    assert equipment_review_column_key("zenon_sld", "script_version") not in protected
    assert equipment_review_column_key("zenon_sld", "destination_name") not in protected


def test_dynamic_builtin_values_flow_into_universal_rows(tmp_path: Path):
    store = ProjectStore(tmp_path / "project")
    try:
        rows, _summary = build_equipment_source_view(
            store,
            "TRANSFORMER",
            MultiAdapter({
                "zenon_sld": [{
                    "device_type": "TRANSFORMER",
                    "rmu": "96104",
                    "feeder": "JED-SHT-ADEL-15",
                    "cabinet_type": "OH_TR",
                    "screen_name": "ADEL-110 (JEDDAH)",
                    "script_version": "2.18.126",
                    "destination_name": "TX_DEST_96104",
                    "resolved_full_name": "ADEL/96104",
                }],
                "adms_sld": [{
                    "rmu": "96104",
                    "device_type": "TRANSFORMER",
                    "rmu_type": "OH_TR",
                    "feeder": "JED-SHT-ADEL-15",
                }],
            }),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row[equipment_review_column_key("zenon_sld", "script_version")] == "2.18.126"
        assert row[equipment_review_column_key("zenon_sld", "destination_name")] == "TX_DEST_96104"
        assert row[equipment_review_column_key("zenon_sld", "resolved_full_name")] == "ADEL/96104"
        assert row[equipment_review_column_key("adms_sld", "device_type")] == "TRANSFORMER"
        assert row[equipment_review_column_key("adms_sld", "rmu_type")] == "OH_TR"
    finally:
        store.close()


def test_runtime_language_state_and_reverse_translation_are_wired():
    i18n = Path("src/migration_report_tool/ui/i18n.py").read_text(encoding="utf-8")
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert "_RUNTIME_LANGUAGE" in i18n
    assert "def set_current_language" in i18n
    assert "if _RUNTIME_LANGUAGE is not None" in i18n
    # v0.8.164 narrows embedded reverse replacement to safe prose fragments.
    # Replacing every short ZH_CN value inside a dynamic sentence can corrupt
    # strings such as “未关闭 / 已关闭” before structured reverse matching.
    assert "ZH_EMBEDDED" in i18n
    assert "sorted(ZH_EMBEDDED, key=lambda item: len(item[1]), reverse=True)" in i18n
    assert "sorted(ZH_CN.items(), key=lambda item: len(item[1]), reverse=True)" not in i18n
    assert "self.settings.sync()" in ui
    assert "QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)" in ui


def test_equipment_review_selector_is_universal_not_rmu_special():
    source = (Path(__file__).resolve().parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'addItem("All Equipment", "__ALL__")' in source
    assert 'addItem("RMU · Full Review", "RMU")' not in source
    assert 'combo.addItem(f"{all_equipment_label} ({total})"' in source
    assert 'combo.addItem(f"{token} ({int(count)})", token)' in source
