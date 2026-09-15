from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.database.global_settings_store import source_hidden_fields
from migration_report_tool.services.schema_service import (
    get_hidden_source_fields,
    set_hidden_source_fields,
    get_source_overrides,
    set_source_overrides,
    get_source_display_names,
    set_source_display_names,
    get_source_column_order,
    set_source_column_order,
)
from migration_report_tool.version import __version__


class GlobalMapVisibilitySyncV08175Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(Path(self.tmp.name) / "user-data")
        self.a = ProjectStore(Path(self.tmp.name) / "site-a")
        self.b = ProjectStore(Path(self.tmp.name) / "site-b")

    def tearDown(self):
        self.a.close(); self.b.close()
        if self.old is None:
            os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = self.old
        self.tmp.cleanup()

    def test_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_adms_sld_map_display_visibility_and_order_are_global(self):
        set_source_overrides(self.a, "adms_sld", {"rmu": "DeviceName", "rmu_type": "RMUType"}, "alice")
        set_source_display_names(self.a, "adms_sld", {"quality_status": "Quality"}, "alice")
        set_hidden_source_fields(self.a, "adms_sld", {"quality_status", "display_label"}, "alice")
        set_source_column_order(self.a, "adms_sld", ["rmu", "rmu_type", "quality_status"], "alice")

        self.assertEqual(get_source_overrides(self.b, "adms_sld"), {"rmu": "DeviceName", "rmu_type": "RMUType"})
        self.assertEqual(get_source_display_names(self.b, "adms_sld").get("quality_status"), "Quality")
        self.assertEqual(get_hidden_source_fields(self.b, "adms_sld"), {"quality_status", "display_label"})
        self.assertEqual(get_source_column_order(self.b, "adms_sld")[:3], ["rmu", "rmu_type", "quality_status"])

    def test_show_all_on_one_site_overrides_stale_local_hidden_list_on_another(self):
        # Simulate a pre-v0.8.176 site-local preference that must no longer be authoritative.
        self.b.config.setdefault("hidden_source_fields", {})["adms_sld"] = ["quality_status"]
        self.b.save_config()

        set_hidden_source_fields(self.a, "adms_sld", set(), "alice")
        self.assertEqual(source_hidden_fields("adms_sld"), set())
        self.assertEqual(get_hidden_source_fields(self.b, "adms_sld"), set())

    def test_legacy_site_visibility_promotes_once_then_global_wins(self):
        self.a.config.setdefault("hidden_source_fields", {})["adms_sld"] = ["quality_status"]
        self.a.save_config()
        self.b.config.setdefault("hidden_source_fields", {})["adms_sld"] = ["display_label"]
        self.b.save_config()

        self.assertEqual(get_hidden_source_fields(self.a, "adms_sld"), {"quality_status"})
        self.assertEqual(get_hidden_source_fields(self.b, "adms_sld"), {"quality_status"})

    def test_system_fields_cannot_be_hidden_globally(self):
        set_hidden_source_fields(self.a, "adms_sld", {"rmu", "device_type", "quality_status"}, "alice")
        self.assertEqual(get_hidden_source_fields(self.b, "adms_sld"), {"quality_status"})

    def test_ui_copy_states_global_scope_and_station_specific_file_sheet(self):
        ui = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Map Fields settings are global by App/source type", ui)
        self.assertIn("The physical source file and Excel sheet remain station-specific", ui)


if __name__ == "__main__":
    unittest.main()
