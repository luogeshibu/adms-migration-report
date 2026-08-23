from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from migration_report_tool.config.column_schema import COMPARISON_GROUPS
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import (
    RMU_REVIEW_DISPLAY_BINDINGS,
    apply_display_names_to_groups,
    default_display_name,
    get_source_display_names,
    set_source_display_names,
)


class GlobalDisplayNameTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_user_data = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(Path(self._tmp.name) / "global-user-data")

    def tearDown(self):
        if self._old_user_data is None:
            os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = self._old_user_data
        self._tmp.cleanup()

    def test_zenon_db_rmu_type_default_matches_actual_app_header(self):
        self.assertEqual(default_display_name("zenon_db", "rmu_type", "RMU Type"), "Device")

    def test_global_display_name_is_shared_by_independent_sites(self):
        root = Path(self._tmp.name)
        store_a = ProjectStore(root / "ADF")
        store_b = ProjectStore(root / "ABN2")
        try:
            set_source_display_names(store_a, "zenon_db", {"rmu_type": "RMU Type"}, "tester")
            self.assertEqual(get_source_display_names(store_a, "zenon_db")["rmu_type"], "RMU Type")
            self.assertEqual(get_source_display_names(store_b, "zenon_db")["rmu_type"], "RMU Type")

            groups = apply_display_names_to_groups(COMPARISON_GROUPS, store_b, RMU_REVIEW_DISPLAY_BINDINGS)
            labels = {key: label for _group, _color, columns in groups for key, label, _width in columns}
            self.assertEqual(labels["zdb_device"], "RMU Type")
        finally:
            store_a.db.close()
            store_b.db.close()

    def test_reset_to_device_removes_global_override(self):
        store = ProjectStore(Path(self._tmp.name) / "ADF")
        try:
            set_source_display_names(store, "zenon_db", {"rmu_type": "RMU Type"}, "tester")
            self.assertIn("rmu_type", get_source_display_names(store, "zenon_db"))
            set_source_display_names(store, "zenon_db", {"rmu_type": "Device"}, "tester")
            self.assertNotIn("rmu_type", get_source_display_names(store, "zenon_db"))
        finally:
            store.db.close()

    def test_actual_column_mapping_remains_site_local(self):
        root = Path(self._tmp.name)
        store_a = ProjectStore(root / "ADF")
        store_b = ProjectStore(root / "ABN2")
        try:
            store_a.config.setdefault("source_column_overrides", {})["zenon_db"] = {"rmu_type": "DEVICE"}
            store_a.save_config()
            self.assertEqual(store_a.source_column_overrides("zenon_db").get("rmu_type"), "DEVICE")
            self.assertEqual(store_b.source_column_overrides("zenon_db"), {})
        finally:
            store_a.db.close()
            store_b.db.close()


if __name__ == "__main__":
    unittest.main()
