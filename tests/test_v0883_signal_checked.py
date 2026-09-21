from __future__ import annotations

from pathlib import Path
import tempfile

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.database.migrations import TARGET_SCHEMA_VERSION


def test_signal_manual_checked_persists_across_row_fingerprint_refresh():
    with tempfile.TemporaryDirectory() as td:
        site = Path(td) / "site"
        store = ProjectStore(site)
        try:
            columns = {row[1] for row in store.db.execute("PRAGMA table_info(db_smart_reviews)")}
            assert {"check_passed", "check_passed_by", "check_passed_at"}.issubset(columns)

            store.update_db_smart_check_passed(
                "sig-100", "10689", True, "reviewer-a",
                source_hash="source-a", row_hash="row-a", site_name="1-ABH",
            )
            record = store.db_smart_review_map()["sig-100"]
            assert int(record["check_passed"]) == 1
            assert record["check_passed_by"] == "reviewer-a"
            assert record["check_passed_at"]
            assert record["review_status"] == "UNREVIEWED"

            # Unchanged validation keeps the manual check.
            store.sync_db_smart_review_fingerprints(
                {"sig-100": {"source_hash": "source-a", "row_hash": "row-a"}}
            )
            assert int(store.db_smart_review_map()["sig-100"]["check_passed"]) == 1

            # Changed row fingerprint updates validation metadata but retains the
            # independent human Checked record.
            store.sync_db_smart_review_fingerprints(
                {"sig-100": {"source_hash": "source-a", "row_hash": "row-b"}}
            )
            record = store.db_smart_review_map()["sig-100"]
            assert int(record["check_passed"]) == 1
            assert record["check_passed_by"] == "reviewer-a"
            assert record["check_passed_at"]
            audit = [item for item in store.changes() if item["field_name"] == "db_smart_check_passed"]
            assert any(item["new_value"] == "PASS" for item in audit)
            assert not any(item["old_value"] == "PASS" and item["new_value"] == "" for item in audit)
        finally:
            store.close()

        reopened = ProjectStore(site)
        try:
            assert reopened.project_schema_version() == TARGET_SCHEMA_VERSION
            assert int(reopened.db_smart_review_map()["sig-100"]["check_passed"]) == 1
        finally:
            reopened.close()
