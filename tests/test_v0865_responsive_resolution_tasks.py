from __future__ import annotations

from pathlib import Path
import tempfile

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore


def _feeder_row():
    return {
        "no": 1,
        "rmu": "27547",
        "analysis_name": "TRUE",
        "analysis_feeder": "FALSE",
        "analysis_smart": "TRUE",
        "analysis_type": "TRUE",
        "analysis_ip": "TRUE",
        "analysis_feeder_detail": "ZENON SLD: JUAS-23 / ADMS DB: ABH-21",
        "resolution_candidates": {
            "FEEDER": [
                {"source": "ZENON SLD XML", "value": "JED-NTH-JUAS-23", "normalized": "JUAS-23"},
                {"source": "ADMS DB", "value": "JED-NTH-ABH-AH21", "normalized": "ABH-21"},
            ]
        },
        "status": "FAILED",
        "remarks": "Analysis mismatch: FEEDER",
        "comments": "",
    }


def test_resolution_batch_saves_without_deriving_review_status():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _feeder_row()
            store.save_comparison([row])
            selected = row["resolution_candidates"]["FEEDER"][1]
            status, summary = store.save_rmu_resolution_decisions(
                "27547",
                row,
                {
                    "FEEDER": {
                        "decision_type": "USE_SOURCE",
                        "selected_source": selected["source"],
                        "selected_value": selected["value"],
                        "normalized_value": selected["normalized"],
                    }
                },
                "tester",
            )
            assert status == "UNREVIEWED"
            assert "approved feeder assignment" in summary
            assert store.rmu_review_map()["27547"]["review_status"] == "UNREVIEWED"
        finally:
            store.close()


def test_sqlite_store_uses_wal_for_background_read_write_concurrency():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            mode = store.db.execute("PRAGMA journal_mode").fetchone()[0]
            assert str(mode).lower() == "wal"
            timeout_ms = store.db.execute("PRAGMA busy_timeout").fetchone()[0]
            assert int(timeout_ms) >= 15000
        finally:
            store.close()


def test_ui_performance_contract_uses_worker_pool_and_targeted_resolution_refresh():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "QThreadPool" in ui
    assert "_background_validation_job" in ui
    assert "_background_refresh_sources_job" in ui
    assert "_background_resolution_save_job" in ui
    assert "_refresh_comparison_resolution_row" in ui
    block = ui[ui.index("def open_rmu_resolution_dialog"):ui.index("def edit_rmu_manual_review_comment")]
    assert "self.refresh_all()" not in block
    assert "_start_background_task" in block
