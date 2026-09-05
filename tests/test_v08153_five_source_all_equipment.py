from __future__ import annotations
from pathlib import Path

from migration_report_tool.adapters import SourceAdapter
from migration_report_tool.services.rmu_review_service import build_equipment_source_view
from migration_report_tool.storage import ProjectStore
from migration_report_tool.version import __version__


class MultiAdapter(SourceAdapter):
    def __init__(self, tables):
        self.tables = {k: list(v) for k, v in tables.items()}

    def load_rows(self, source_type: str):
        return [dict(row) for row in self.tables.get(source_type, [])]


def test_release_version():
    assert __version__ == "0.8.153"


def test_lbs_is_rendered_across_all_five_sources(tmp_path: Path):
    tables = {
        "zenon_sld": [{
            "device_type": "LBS", "rmu": "1196", "feeder": "JED-STH-ADEL-20",
            "cabinet_type": "OLBS", "screen_name": "ADEL-110 (JEDDAH)",
            "name_status": "OK", "confidence": "HIGH",
        }],
        "se_list": [{"rmu": "1196", "feeder": "ADEL-20", "rmu_type": "OLBS", "smart": "NORMAL"}],
        "zenon_db": [{"rmu": "1196", "feeder": "ADEL-20", "rmu_type": "OLBS", "ip": "10.0.0.11"}],
        "adms_db": [{"rmu": "1196", "gss_fid": "ADEL-20", "rmu_type": "OLBS", "channel_ip": "10.0.0.11"}],
        "adms_sld": [{"rmu": "1196", "feeder": "ADEL-20", "rmu_type": "OLBS"}],
    }
    store = ProjectStore(tmp_path / "site")
    try:
        rows, summary = build_equipment_source_view(store, "LBS", MultiAdapter(tables))
        assert len(rows) == 1
        row = rows[0]
        assert row["equipment_device_type"] == "LBS"
        assert row["equipment_source_count"] == "5/5"
        assert row["equipment_missing_sources"] == ""
        assert row["eq_se_rmu"] == "1196"
        assert row["eq_zdb_rmu"] == "1196"
        assert row["eq_zsld_rmu"] == "1196"
        assert row["eq_adb_rmu"] == "1196"
        assert row["eq_asld_rmu"] == "1196"
        assert summary["coverage"] == {"5/5": 1}
    finally:
        store.close()


def test_missing_sources_stay_blank_and_are_reported(tmp_path: Path):
    tables = {
        "zenon_sld": [{"device_type": "FUSE", "rmu": "F101", "feeder": "ADEL-03", "name_status": "OK", "confidence": "HIGH"}],
        "se_list": [{"rmu": "F101", "feeder": "ADEL-03"}],
        "zenon_db": [],
        "adms_db": [],
        "adms_sld": [],
    }
    store = ProjectStore(tmp_path / "site")
    try:
        rows, summary = build_equipment_source_view(store, "FUSE", MultiAdapter(tables))
        row = rows[0]
        assert row["equipment_source_count"] == "2/5"
        assert "ZENON DB" in row["equipment_missing_sources"]
        assert "ADMS DB" in row["equipment_missing_sources"]
        assert row["eq_zdb_rmu"] == ""
        assert row["eq_adb_rmu"] == ""
        assert summary["coverage"] == {"2/5": 1}
    finally:
        store.close()


def test_non_rmu_ui_uses_five_source_groups():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    schema = Path("src/migration_report_tool/config/column_schema.py").read_text(encoding="utf-8")
    assert "equipment_source_review_groups(self.store)" in ui
    assert '"mode": "equipment_sources"' in ui
    for group in ("SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"):
        assert f'(\"{group}\",' in schema
