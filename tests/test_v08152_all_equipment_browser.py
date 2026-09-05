from __future__ import annotations

from pathlib import Path

from migration_report_tool.adapters import SourceAdapter
from migration_report_tool.services.rmu_review_service import build_equipment_inventory, equipment_inventory_type_counts
from migration_report_tool.storage import ProjectStore
from migration_report_tool.version import __version__


class DictAdapter(SourceAdapter):
    def __init__(self, rows):
        self.rows = list(rows)

    def load_rows(self, source_type: str):
        return [dict(row) for row in self.rows] if source_type == "zenon_sld" else []


def test_release_version():
    assert __version__ == "0.8.152"


def test_all_equipment_inventory_keeps_every_device_type(tmp_path: Path):
    rows = [
        {"device_type": "RMU", "rmu": "1001", "feeder": "F-01", "cabinet_type": "2L1T", "name_status": "OK", "confidence": "HIGH"},
        {"device_type": "TRANSFORMER", "rmu": "T01", "feeder": "F-01", "cabinet_type": "OH_TR", "name_status": "RECOVERED", "confidence": "MEDIUM"},
        {"device_type": "FUSE", "rmu": "UNRESOLVED_FUSE@1", "cabinet_type": "FUSE", "name_status": "UNRESOLVED", "confidence": "LOW", "warning": "identifier unresolved"},
        {"device_type": "LBS", "rmu": "L01", "feeder": "F-02", "cabinet_type": "OLBS", "name_status": "OK", "confidence": "HIGH"},
        {"device_type": "REC", "rmu": "R01", "feeder": "F-03", "cabinet_type": "SREC", "name_status": "OK", "confidence": "HIGH"},
    ]
    store = ProjectStore(tmp_path / "site")
    try:
        adapter = DictAdapter(rows)
        counts = equipment_inventory_type_counts(store, adapter)
        assert counts == {"RMU": 1, "TRANSFORMER": 1, "FUSE": 1, "LBS": 1, "REC": 1}
        all_rows, summary = build_equipment_inventory(store, "__ALL__", adapter)
        assert len(all_rows) == 5
        assert {row["zsld_device_type"] for row in all_rows} == {"RMU", "TRANSFORMER", "FUSE", "LBS", "REC"}
        assert summary["OK"] == 3
        assert summary["REVIEW"] == 1
        assert summary["ATTENTION"] == 1
    finally:
        store.close()


def test_specific_non_rmu_profile_filters_without_losing_inventory_fields(tmp_path: Path):
    rows = [
        {"device_type": "TRANSFORMER", "rmu": "33445", "feeder": "JED-SHT-ADEL-45", "screen_name": "ADEL-110 (JEDDAH)", "cabinet_type": "OH_TR", "name_status": "MISMATCH_CORRECTED", "confidence": "MEDIUM", "warning": "name conflict"},
        {"device_type": "RMU", "rmu": "10169", "feeder": "JED-STH-ADEL-42", "cabinet_type": "2L1T", "smart": "NORMAL", "name_status": "OK", "confidence": "HIGH"},
    ]
    store = ProjectStore(tmp_path / "site")
    try:
        filtered, _ = build_equipment_inventory(store, "TRANSFORMER", DictAdapter(rows))
        assert len(filtered) == 1
        row = filtered[0]
        assert row["rmu"] == "33445"
        assert row["zsld_feeder"] == "JED-SHT-ADEL-45"
        assert row["zsld_type"] == "OH_TR"
        assert row["inventory_quality"] == "REVIEW"
        assert row["zsld_warning"] == "name conflict"
    finally:
        store.close()


def test_ui_profile_selector_is_enabled_and_source_driven():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert 'self.equipment_profile_combo.setEnabled(False)' not in ui
    assert 'equipment_inventory_type_counts(self.store)' in ui
    assert '"__ALL__"' in ui
    assert '"ZENON SLD Inventory"' in Path("src/migration_report_tool/config/column_schema.py").read_text(encoding="utf-8")
