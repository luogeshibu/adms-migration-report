from pathlib import Path

from migration_report_tool.infrastructure.database.migrations import TARGET_SCHEMA_VERSION
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_pdf_signal_summary_is_full_width_and_partitioned_labels():
    start = PDF.index("<h2>Signal Data Summary</h2>")
    end = PDF.index("<h2>RMU Need Action Register", start)
    block = PDF[start:end]
    assert '<table class="summary" width="100%" cellspacing="0" cellpadding="0">' in block
    assert '<colgroup><col width="23%"><col width="10%"><col width="23%"><col width="10%"><col width="24%"><col width="10%"></colgroup>' in block
    assert "Need Action Total" in block
    assert "Pending / Open" in block


def test_schema_tracks_ever_needs_action(tmp_path):
    project = tmp_path / "site"
    store = ProjectStore(project)
    try:
        cols = {row[1] for row in store.db.execute("PRAGMA table_info(db_smart_reviews)")}
        assert "ever_needs_action" in cols
        assert store.schema_version == TARGET_SCHEMA_VERSION == 10
        store.update_db_smart_review("K1", "100", "review_status", "NEEDS ACTION", "tester", site_name="SITE")
        row = store.db.execute("SELECT review_status,ever_needs_action FROM db_smart_reviews WHERE row_key='K1'").fetchone()
        assert row[0] == "NEEDS ACTION" and row[1] == 1
        store.update_db_smart_review("K1", "100", "review_status", "CLOSED", "tester", site_name="SITE")
        row = store.db.execute("SELECT review_status,ever_needs_action FROM db_smart_reviews WHERE row_key='K1'").fetchone()
        assert row[0] == "CLOSED" and row[1] == 1
    finally:
        store.close()


def test_summary_code_partitions_only_tracked_need_action_rows():
    start = PDF.index("def _signal_review_state_summary")
    end = PDF.index("def _load_issue_snapshot", start)
    block = PDF[start:end]
    assert 'tracked = bool(int(record.get("ever_needs_action") or 0)) or raw_status == "NEEDS ACTION"' in block
    assert 'if raw_status == "CLOSED":' in block
    assert 'pending += 1' in block
    assert '"need_action_total": total' in block
    assert '"closed": closed' in block
    assert '"pending": pending' in block
    assert 'result == "FALSE"' not in block


def test_snapshot_uses_lifecycle_total_not_current_open_register_count():
    assert '"signal_need_action_total": int(signal_review_state.get("need_action_total", 0))' in PDF
    assert '__version__ = "0.8.120"' in VERSION
