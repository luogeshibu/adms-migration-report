import sqlite3
import tempfile
import unittest
from pathlib import Path

from migration_report_tool.storage import ProjectStore
from migration_report_tool.infrastructure.database.migrations import migrate_project_database
from migration_report_tool.version import __version__


class IssueLifecycleTests(unittest.TestCase):
    def test_version_and_schema(self):
        self.assertEqual(__version__, "0.8.196")
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                self.assertEqual(store.project_schema_version(), 12)
                names = {row[0] for row in store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn("issue_cases", names)
                self.assertIn("issue_events", names)
            finally:
                store.close()

    def test_rmu_need_action_comment_close_and_reopen_are_append_only(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                store.update_rmu_review_status("15953", "NEEDS ACTION", "alice", "Feeder mismatch")
                store.update_rmu_manual_review_comment("15953", "Confirm with field team", "bob")
                store.update_rmu_review_status("15953", "CLOSED", "carol", "Corrected and verified")

                first = store.issue_lifecycle("RMU", "15953")
                self.assertEqual(len(first), 1)
                self.assertEqual(first[0]["status"], "CLOSED")
                self.assertEqual(first[0]["participant_count"], 3)
                events = first[0]["events"]
                self.assertEqual([e["event_type"] for e in events], ["CASE_OPENED", "COMMENT_CHANGED", "CASE_CLOSED"])
                self.assertEqual(events[1]["new_value"], "Confirm with field team")
                self.assertEqual(first[0]["closed_by"], "carol")

                store.update_rmu_review_status("15953", "NEEDS ACTION", "dave", "Mismatch returned")
                cases = store.issue_cases(entity_type="RMU", entity_key="15953")
                self.assertEqual(len(cases), 2)
                self.assertEqual(cases[0]["case_no"], 2)
                self.assertEqual(cases[0]["status"], "OPEN")
                self.assertEqual(cases[1]["status"], "CLOSED")
            finally:
                store.close()

    def test_signal_action_remark_opens_case_and_close_preserves_timeline(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            meta = {
                "signal_category": "STATUS_CMD",
                "point_no": "1003",
                "signal_name": "KY2 state",
                "signal_snapshot_json": "{}",
            }
            try:
                # UI saves Action/Remark first, then marks Needs Action.
                store.update_db_smart_review(
                    "sig-1", "10689", "comments", "MODIFY | Verify mapping", "alice",
                    site_name="1-ABH", metadata=meta,
                )
                store.update_db_smart_review(
                    "sig-1", "10689", "review_status", "NEEDS ACTION", "alice",
                    site_name="1-ABH", metadata=meta,
                )
                store.update_db_smart_review(
                    "sig-1", "10689", "comments", "DELETE | Duplicate point", "bob",
                    site_name="1-ABH", metadata=meta,
                )
                store.update_db_smart_review(
                    "sig-1", "10689", "review_status", "CLOSED", "carol",
                    site_name="1-ABH", metadata=meta,
                )
                cases = store.issue_lifecycle("SIGNAL", "sig-1")
                self.assertEqual(len(cases), 1)
                case = cases[0]
                self.assertEqual(case["point_no"], "1003")
                self.assertEqual(case["signal_name"], "KY2 state")
                self.assertEqual(case["status"], "CLOSED")
                types = [event["event_type"] for event in case["events"]]
                self.assertIn("ACTION_REMARK_CHANGED", types)
                self.assertEqual(types[-1], "CASE_CLOSED")
                self.assertEqual(case["participant_count"], 3)
            finally:
                store.close()

    def test_schema_10_migration_backfills_without_removing_existing_rows(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db_path = root / "project.db"
            backups = root / "backups"
            db = sqlite3.connect(db_path)
            db.executescript(
                """
                CREATE TABLE app_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                INSERT INTO app_meta(key,value) VALUES('schema_version','10');
                CREATE TABLE rmu_action_tracking(
                    rmu TEXT PRIMARY KEY,tracking_status TEXT,first_need_action_at TEXT,last_need_action_at TEXT,
                    closed_at TEXT,opened_by TEXT,closed_by TEXT,open_count INTEGER,last_reason TEXT,updated_at TEXT
                );
                INSERT INTO rmu_action_tracking VALUES(
                    '15953','CLOSED','2026-08-01T10:00:00','2026-08-01T10:00:00','2026-08-02T10:00:00',
                    'alice','bob',1,'fixed','2026-08-02T10:00:00'
                );
                CREATE TABLE db_smart_reviews(
                    row_key TEXT PRIMARY KEY,site_name TEXT,rmu TEXT,source_hash TEXT,row_hash TEXT,
                    review_status TEXT,comments TEXT,reviewed_by TEXT,reviewed_at TEXT,updated_at TEXT,
                    signal_category TEXT,point_no TEXT,signal_name TEXT,signal_snapshot_json TEXT,ever_needs_action INTEGER
                );
                INSERT INTO db_smart_reviews VALUES(
                    'sig-old','1-ABH','10689','','','NEEDS ACTION','MODIFY | legacy','alice',
                    '2026-08-03T10:00:00','2026-08-03T10:00:00','STATUS_CMD','1003','KY2 state','{}',1
                );
                """
            )
            db.commit(); db.close()

            version, backup = migrate_project_database(db_path, backups)
            self.assertEqual(version, 12)
            self.assertIsNotNone(backup)
            db = sqlite3.connect(db_path)
            try:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM rmu_action_tracking").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM db_smart_reviews").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM issue_cases").fetchone()[0], 2)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM issue_events").fetchone()[0], 2)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
