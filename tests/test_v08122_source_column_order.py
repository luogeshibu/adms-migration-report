from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import (
    get_source_column_order,
    set_source_column_order,
    rmu_review_groups,
    set_hidden_source_fields,
)


class SourceColumnOrderV08122Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_user_data = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(Path(self._tmp.name) / "user-data")
        self.store = ProjectStore(Path(self._tmp.name) / "site")

    def tearDown(self):
        self.store.db.close()
        if self._old_user_data is None:
            os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = self._old_user_data
        self._tmp.cleanup()

    def test_order_is_application_wide_and_key_based(self):
        order = ["channel_ip", "rmu", "gss_fid", "channel_port", "rmu_type"]
        set_source_column_order(self.store, "adms_db", order, "tester")
        self.assertEqual(get_source_column_order(self.store, "adms_db"), order)

        other_store = ProjectStore(Path(self._tmp.name) / "other-site")
        try:
            self.assertEqual(get_source_column_order(other_store, "adms_db"), order)
        finally:
            other_store.db.close()

    def test_rmu_review_adms_group_follows_saved_app_field_order(self):
        # Ordering test needs optional fields visible explicitly under the
        # v0.8.172 default-hide presentation policy.
        set_hidden_source_fields(self.store, "adms_db", set(), "tester")
        set_source_column_order(
            self.store,
            "adms_db",
            ["channel_ip", "rmu", "gss_fid", "channel_port", "rmu_type", "smart"],
            "tester",
        )
        groups = {group: list(columns) for group, _color, columns in rmu_review_groups(self.store)}
        adms_keys = [key for key, _label, _width in groups["ADMS DB"]]
        self.assertEqual(
            adms_keys[:6],
            ["adms_channel_ip", "adb_rmu", "adb_gss_fid", "adms_channel_port", "adb_type", "adb_smart"],
        )
        # Existing/new fields omitted from an older preference remain visible and append safely.
        self.assertIn("adb_y1", adms_keys)
        self.assertIn("adb_q2", adms_keys)

    def test_preference_does_not_modify_project_schema_or_review_tables(self):
        version_before = self.store.project_schema_version()
        before_tables = {
            row[0] for row in self.store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        set_source_column_order(self.store, "adms_db", ["rmu", "channel_ip"], "tester")
        version_after = self.store.project_schema_version()
        after_tables = {
            row[0] for row in self.store.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertEqual(version_before, version_after)
        self.assertEqual(before_tables, after_tables)

    def test_ui_contains_move_column_workflow(self):
        source = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('QPushButton("Move Column...")', source)
        self.assertIn("SourceColumnOrderDialog", source)
        self.assertIn("QAbstractItemView.InternalMove", source)
        self.assertIn("set_source_column_order", source)


if __name__ == "__main__":
    unittest.main()
