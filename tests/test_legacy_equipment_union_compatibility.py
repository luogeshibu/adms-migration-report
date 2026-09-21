from __future__ import annotations

from pathlib import Path

from migration_report_tool.adapters import SourceAdapter
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.rmu_review_service import build_equipment_source_view


class _Tables(SourceAdapter):
    def __init__(self, tables: dict[str, list[dict]]):
        self.tables = tables

    def load_rows(self, source_type: str) -> list[dict]:
        return [dict(row) for row in self.tables.get(source_type, [])]


def test_legacy_project_keeps_union_rows_missing_from_zenon_sld(tmp_path: Path):
    """Old five-source projects must not lose rows absent from the SLD export."""
    tables = {
        "se_list": [
            {"rmu": "100", "feeder": "ABH-01", "device_type": "RMU"},
            {"rmu": "200", "feeder": "ABH-02", "device_type": "RMU"},
        ],
        "zenon_sld": [
            {"rmu": "100", "feeder": "ABH-01", "device_type": "RMU"},
        ],
    }
    store = ProjectStore(tmp_path / "site")
    try:
        rows, summary = build_equipment_source_view(store, "__ALL__", _Tables(tables))
    finally:
        store.close()

    by_name = {row["rmu"]: row for row in rows}
    assert set(by_name) == {"100", "200"}
    assert by_name["100"]["equipment_source_count"] == "2/5"
    assert by_name["200"]["equipment_source_count"] == "1/5"
    assert by_name["200"]["review_key"] == "200"
    assert summary["coverage"] == {"2/5": 1, "1/5": 1}
