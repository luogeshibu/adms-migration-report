from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_report_tool.infrastructure.database.migrations import TARGET_SCHEMA_VERSION, database_schema_version
from migration_report_tool.storage import ProjectStore
from migration_report_tool.utils.paths import project_data_root, set_project_data_root, workspace_root


class PersistentSiteRecordsTests(unittest.TestCase):
    def test_project_data_is_outside_release_and_remembered(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            user_data = base / "user-data"
            chosen = base / "project-data"
            with patch.dict(os.environ, {"MIGRATION_REPORT_TOOL_USER_DATA_ROOT": str(user_data)}, clear=False):
                os.environ.pop("MIGRATION_REPORT_TOOL_PROJECT_DATA_ROOT", None)
                set_project_data_root(chosen)
                self.assertEqual(project_data_root(), chosen.resolve())
                self.assertEqual(workspace_root(), chosen.resolve() / "workspace")
                self.assertTrue((user_data / "settings" / "project_data.json").exists())

    def test_every_site_keeps_its_own_records_after_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = ProjectStore(root / "workspace" / "1-ABH")
            b = ProjectStore(root / "workspace" / "1-ABN")
            try:
                a.update_rmu_review_status("17228", "CLOSED", "reviewer-a")
                a.update_rmu_manual_review_comment("17228", "ABH checked", "reviewer-a")
                a.config["source_column_overrides"] = {"adms_db": {"rmu": "RMU_NAME"}}
                a.save_config()

                b.update_rmu_review_status("17228", "CLOSED", "reviewer-b")
                b.update_rmu_manual_review_comment("17228", "ABN closed", "reviewer-b")
            finally:
                a.close(); b.close()

            a2 = ProjectStore(root / "workspace" / "1-ABH")
            b2 = ProjectStore(root / "workspace" / "1-ABN")
            try:
                self.assertEqual(a2.rmu_review_map()["17228"]["review_status"], "CLOSED")
                self.assertEqual(a2.rmu_manual_review_comment("17228"), "ABH checked")
                self.assertEqual(a2.config["source_column_overrides"]["adms_db"]["rmu"], "RMU_NAME")
                self.assertEqual(b2.rmu_review_map()["17228"]["review_status"], "CLOSED")
                self.assertEqual(b2.rmu_manual_review_comment("17228"), "ABN closed")
            finally:
                a2.close(); b2.close()

    def test_unversioned_db_is_backed_up_before_schema_adoption(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "1-ABH"
            site.mkdir()
            db_path = site / "project.db"
            db = sqlite3.connect(db_path)
            db.execute("CREATE TABLE old_data(value TEXT)")
            db.execute("INSERT INTO old_data(value) VALUES('preserve-me')")
            db.commit(); db.close()

            store = ProjectStore(site)
            try:
                self.assertEqual(store.project_schema_version(), TARGET_SCHEMA_VERSION)
                self.assertEqual(database_schema_version(db_path), TARGET_SCHEMA_VERSION)
                backups = list((site / "backups").glob(f"project_before_schema_{TARGET_SCHEMA_VERSION:03d}_*.db"))
                self.assertEqual(len(backups), 1)
                backup_db = sqlite3.connect(backups[0])
                try:
                    self.assertEqual(backup_db.execute("SELECT value FROM old_data").fetchone()[0], "preserve-me")
                finally:
                    backup_db.close()
            finally:
                store.close()

    def test_ui_calls_persistent_project_data_not_release_workspace(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('workspace_caption = QLabel("PROJECT DATA")', text)
        self.assertIn('form.addRow("Legacy Project Data (compatibility)", project_data_widget)', text)
        self.assertIn('choose_project_data_root', text)
        self.assertNotIn('workspace_caption = QLabel("PROJECT APP WORKSPACE")', text)

    def test_site_history_issue_and_signed_report_survive_reopen(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "workspace" / "1-ABH"
            store = ProjectStore(site)
            try:
                version_id = store.save_version("R001", "Initial closure", "reviewer-a")
                revision_id = store.create_site_revision(
                    "R001", "Initial closure", "reviewer-a", version_id=version_id
                )
                issue_id = store.add_issue_action(
                    revision_id=revision_id,
                    category="RMU",
                    equipment="RMU-01",
                    issue="Name position incorrect",
                    action_taken="Moved to agreed position",
                    result="CLOSED",
                    comments="Field checked",
                    created_by="reviewer-a",
                )
                generated = store.reports_dir / "ABH_R001.pdf"
                generated.write_bytes(b"%PDF-1.4\n% test\n")
                report_id = store.record_signoff_report(
                    revision_id=revision_id,
                    path=generated,
                    snapshot={"site": "ABH", "revision": "R001"},
                    created_by="reviewer-a",
                )
                signed = Path(td) / "signed.pdf"
                signed.write_bytes(b"%PDF-1.4\n% signed\n")
                signed_target = store.attach_signed_report(report_id, signed)
                self.assertTrue(signed_target.exists())
                self.assertGreater(issue_id, 0)
            finally:
                store.close()

            reopened = ProjectStore(site)
            try:
                self.assertEqual(reopened.latest_site_revision()["revision_name"], "R001")
                self.assertEqual(reopened.issue_actions()[0]["equipment"], "RMU-01")
                report = reopened.signoff_reports()[0]
                self.assertEqual(report["report_status"], "SIGNED")
                self.assertTrue(Path(report["signed_file_path"]).exists())
                self.assertEqual(reopened.config["db_schema_version"], TARGET_SCHEMA_VERSION)
            finally:
                reopened.close()

    def test_v0843_schema_is_backed_up_and_versions_are_backfilled_to_site_history(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "workspace" / "1-ABH"
            site.mkdir(parents=True)
            db_path = site / "project.db"
            db = sqlite3.connect(db_path)
            db.executescript(
                """
                CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO app_meta(key,value) VALUES('schema_version','1');
                CREATE TABLE versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, version_name TEXT,
                    description TEXT, snapshot_json TEXT, created_by TEXT, created_at TEXT
                );
                INSERT INTO versions(version_name,description,snapshot_json,created_by,created_at)
                VALUES('R000','Before app upgrade','{}','old-reviewer','2026-08-24T10:00:00');
                """
            )
            db.commit(); db.close()

            store = ProjectStore(site)
            try:
                self.assertEqual(store.project_schema_version(), TARGET_SCHEMA_VERSION)
                self.assertEqual(store.latest_site_revision()["revision_name"], "R000")
                self.assertEqual(store.latest_site_revision()["version_id"], 1)
                backups = list((site / "backups").glob(f"project_before_schema_{TARGET_SCHEMA_VERSION:03d}_*.db"))
                self.assertEqual(len(backups), 1)
            finally:
                store.close()


    def test_schema_v3_resolution_records_survive_v4_migration(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "workspace" / "1-ABH"
            site.mkdir(parents=True)
            db_path = site / "project.db"
            db = sqlite3.connect(db_path)
            db.executescript(
                """
                CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO app_meta(key,value) VALUES('schema_version','3');
                CREATE TABLE rmu_resolutions (
                    rmu TEXT NOT NULL, analysis_field TEXT NOT NULL, decision_type TEXT NOT NULL,
                    selected_source TEXT NOT NULL DEFAULT '', selected_value TEXT NOT NULL DEFAULT '',
                    normalized_value TEXT NOT NULL DEFAULT '', analysis_fingerprint TEXT NOT NULL DEFAULT '',
                    modified_by TEXT, modified_at TEXT, PRIMARY KEY(rmu, analysis_field)
                );
                INSERT INTO rmu_resolutions(
                    rmu,analysis_field,decision_type,selected_source,selected_value,normalized_value,analysis_fingerprint,modified_by,modified_at
                ) VALUES('17233','FEEDER','USE_SOURCE','ZENON SLD XML','JED-NTH-ABH-15','ABH-15','fp','reviewer','2026-08-25T20:00:00');
                """
            )
            db.commit(); db.close()

            store = ProjectStore(site)
            try:
                record = store.rmu_resolution_map("17233")["FEEDER"]
                self.assertEqual(record["selected_source"], "ZENON SLD XML")
                self.assertEqual(record["selected_value"], "JED-NTH-ABH-15")
                self.assertIn("decision_description", record)
                self.assertIn("issue_snapshot_json", record)
                backups = list((site / "backups").glob(f"project_before_schema_{TARGET_SCHEMA_VERSION:03d}_*.db"))
                self.assertEqual(len(backups), 1)
            finally:
                store.close()

    def test_schema_v4_adds_signoff_resolution_snapshot_columns(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "workspace" / "1-ABH"
            store = ProjectStore(site)
            try:
                columns = {row[1] for row in store.db.execute("PRAGMA table_info(rmu_resolutions)")}
                self.assertIn("decision_description", columns)
                self.assertIn("issue_snapshot_json", columns)
                self.assertEqual(store.project_schema_version(), TARGET_SCHEMA_VERSION)
            finally:
                store.close()

    def test_schema_v3_migrates_legacy_reviewed_to_closed_without_rewriting_audit(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "workspace" / "1-ABH"
            old = ProjectStore(site)
            try:
                now = "2026-08-25T10:00:00"
                old.db.execute(
                    "INSERT OR REPLACE INTO rmu_reviews(rmu,review_status,manual_comment,reviewed_by,reviewed_at,updated_at,analysis_hash) VALUES(?,?,?,?,?,?,?)",
                    ("10689", "REVIEWED", "legacy RMU review", "old-user", now, now, "hash-a"),
                )
                old.db.execute(
                    "INSERT OR REPLACE INTO db_smart_reviews(row_key,site_name,rmu,source_hash,row_hash,review_status,comments,reviewed_by,reviewed_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("sig-1", "1-ABH", "10689", "source", "row", "REVIEWED", "legacy signal review", "old-user", now, now),
                )
                old.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    ("10689", "rmu_review_status", "UNREVIEWED", "REVIEWED", "legacy audit", "old-user", now),
                )
                old.db.execute("UPDATE app_meta SET value='2' WHERE key='schema_version'")
                old.db.commit()
            finally:
                old.close()

            upgraded = ProjectStore(site)
            try:
                self.assertEqual(upgraded.project_schema_version(), TARGET_SCHEMA_VERSION)
                self.assertEqual(upgraded.rmu_review_map()["10689"]["review_status"], "CLOSED")
                self.assertEqual(upgraded.db_smart_review_map()["sig-1"]["review_status"], "CLOSED")
                legacy_audit = next(item for item in upgraded.changes() if item["reason"] == "legacy audit")
                self.assertEqual(legacy_audit["new_value"], "REVIEWED")
                backups = list((site / "backups").glob(f"project_before_schema_{TARGET_SCHEMA_VERSION:03d}_*.db"))
                self.assertEqual(len(backups), 1)
            finally:
                upgraded.close()


if __name__ == "__main__":
    unittest.main()
