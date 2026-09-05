from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.migrations import TARGET_SCHEMA_VERSION
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore


class SafeSchemaMigrationV08119Tests(unittest.TestCase):
    def test_v9_to_v10_backup_and_signal_review_data_survive(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "1-ABH"
            site.mkdir(parents=True)
            db_path = site / "project.db"

            db = sqlite3.connect(db_path)
            db.executescript(
                """
                CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO app_meta(key,value) VALUES('schema_version','9');

                CREATE TABLE db_smart_reviews (
                    row_key TEXT PRIMARY KEY,
                    site_name TEXT,
                    rmu TEXT,
                    source_hash TEXT,
                    row_hash TEXT NOT NULL DEFAULT '',
                    review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
                    comments TEXT NOT NULL DEFAULT '',
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    updated_at TEXT,
                    check_passed INTEGER NOT NULL DEFAULT 0,
                    check_passed_by TEXT NOT NULL DEFAULT '',
                    check_passed_at TEXT NOT NULL DEFAULT '',
                    signal_category TEXT NOT NULL DEFAULT '',
                    point_no TEXT NOT NULL DEFAULT '',
                    signal_name TEXT NOT NULL DEFAULT '',
                    signal_snapshot_json TEXT NOT NULL DEFAULT '{}'
                );
                INSERT INTO db_smart_reviews(
                    row_key,site_name,rmu,source_hash,row_hash,review_status,comments,
                    reviewed_by,reviewed_at,updated_at,check_passed,check_passed_by,
                    check_passed_at,signal_category,point_no,signal_name,signal_snapshot_json
                ) VALUES(
                    'sig-10689-1003','1-ABH','10689','source-hash','row-hash','CLOSED',
                    'MODIFY | Keep this user remark','reviewer-a','2026-08-27T10:00:00',
                    '2026-08-27T10:00:00',1,'reviewer-a','2026-08-27T10:01:00',
                    'STATUS_CMD','1003','KY2 state','{"standard":"KY2 state"}'
                );

                CREATE TABLE rmu_resolutions (
                    rmu TEXT NOT NULL, analysis_field TEXT NOT NULL, decision_type TEXT NOT NULL,
                    selected_source TEXT NOT NULL DEFAULT '', selected_value TEXT NOT NULL DEFAULT '',
                    normalized_value TEXT NOT NULL DEFAULT '', analysis_fingerprint TEXT NOT NULL DEFAULT '',
                    decision_description TEXT NOT NULL DEFAULT '', issue_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    modified_by TEXT, modified_at TEXT,
                    PRIMARY KEY(rmu, analysis_field)
                );
                INSERT INTO rmu_resolutions(
                    rmu,analysis_field,decision_type,selected_source,selected_value,normalized_value,
                    analysis_fingerprint,decision_description,issue_snapshot_json,modified_by,modified_at
                ) VALUES(
                    '10689','FEEDER','USE_SOURCE','STANDARD','ABH-08','ABH-08','fp',
                    'Keep agreed feeder','{"before":"ABH-30"}','reviewer-a','2026-08-27T10:02:00'
                );
                """
            )
            db.commit()
            db.close()

            store = ProjectStore(site)
            try:
                self.assertEqual(TARGET_SCHEMA_VERSION, 11)
                self.assertEqual(store.project_schema_version(), TARGET_SCHEMA_VERSION)

                row = store.db.execute(
                    "SELECT review_status,comments,check_passed,check_passed_by,point_no,signal_name,"
                    "signal_snapshot_json,ever_needs_action FROM db_smart_reviews WHERE row_key=?",
                    ("sig-10689-1003",),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(
                    tuple(row[:7]),
                    (
                        "CLOSED",
                        "MODIFY | Keep this user remark",
                        1,
                        "reviewer-a",
                        "1003",
                        "KY2 state",
                        '{"standard":"KY2 state"}',
                    ),
                )
                self.assertEqual(row[7], 1)

                resolution = store.db.execute(
                    "SELECT selected_source,selected_value,decision_description,issue_snapshot_json "
                    "FROM rmu_resolutions WHERE rmu='10689' AND analysis_field='FEEDER'"
                ).fetchone()
                self.assertEqual(
                    tuple(resolution),
                    ("STANDARD", "ABH-08", "Keep agreed feeder", '{"before":"ABH-30"}'),
                )
            finally:
                store.close()

            backups = list((site / "backups").glob("project_before_schema_011_*.db"))
            self.assertEqual(len(backups), 1)
            backup = sqlite3.connect(backups[0])
            try:
                self.assertEqual(backup.execute("PRAGMA quick_check").fetchone()[0], "ok")
                self.assertEqual(
                    backup.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()[0],
                    "9",
                )
                original = backup.execute(
                    "SELECT review_status,comments,check_passed,point_no,signal_name "
                    "FROM db_smart_reviews WHERE row_key='sig-10689-1003'"
                ).fetchone()
                self.assertEqual(
                    original,
                    ("CLOSED", "MODIFY | Keep this user remark", 1, "1003", "KY2 state"),
                )
            finally:
                backup.close()


if __name__ == "__main__":
    unittest.main()
