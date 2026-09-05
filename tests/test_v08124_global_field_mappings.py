from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import get_source_overrides, set_source_overrides


class GlobalFieldMappingsV08124Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(Path(self.tmp.name) / "user-data")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = self.old
        self.tmp.cleanup()

    def test_user_column_mapping_changes_are_global_in_both_directions(self):
        a = ProjectStore(Path(self.tmp.name) / "site-a")
        b = ProjectStore(Path(self.tmp.name) / "site-b")
        try:
            a.replace_custom_source_fields(
                "adms_db",
                [
                    {"field_key": "voltage", "display_name": "Voltage", "actual_column": "port"},
                    {"field_key": "ip", "display_name": "IP", "actual_column": "NET_DESCRIPTION1"},
                ],
                "a",
            )
            self.assertEqual(
                [(x["field_key"], x["actual_column"]) for x in b.custom_source_fields("adms_db")],
                [("voltage", "port"), ("ip", "NET_DESCRIPTION1")],
            )

            b.replace_custom_source_fields(
                "adms_db",
                [
                    {"field_key": "voltage", "display_name": "Voltage", "actual_column": "Voltage"},
                    {"field_key": "ip", "display_name": "IP", "actual_column": "IP"},
                ],
                "b",
            )
            self.assertEqual(
                [(x["field_key"], x["actual_column"]) for x in a.custom_source_fields("adms_db")],
                [("voltage", "Voltage"), ("ip", "IP")],
            )
        finally:
            a.close(); b.close()

    def test_builtin_explicit_source_field_selection_is_global(self):
        a = ProjectStore(Path(self.tmp.name) / "site-a")
        b = ProjectStore(Path(self.tmp.name) / "site-b")
        try:
            set_source_overrides(a, "adms_db", {"channel_ip": "CUSTOM_IP", "channel_port": "CUSTOM_PORT"}, "a")
            self.assertEqual(
                get_source_overrides(b, "adms_db"),
                {"channel_ip": "CUSTOM_IP", "channel_port": "CUSTOM_PORT"},
            )
            self.assertEqual(b.source_column_overrides("adms_db")["channel_ip"], "CUSTOM_IP")

            set_source_overrides(b, "adms_db", {"channel_ip": "IP2"}, "b")
            self.assertEqual(get_source_overrides(a, "adms_db"), {"channel_ip": "IP2"})
        finally:
            a.close(); b.close()

    def test_legacy_site_mapping_is_promoted_without_deleting_project_copy(self):
        site = Path(self.tmp.name) / "legacy-site"
        site.mkdir(parents=True)
        (site / "project.json").write_text(
            '{"project_name":"legacy-site","sources":{},"source_column_overrides":{"adms_db":{"channel_ip":"LEGACY_IP"}}}',
            encoding="utf-8",
        )
        a = ProjectStore(site)
        b = ProjectStore(Path(self.tmp.name) / "other-site")
        try:
            self.assertEqual(a.config["source_column_overrides"]["adms_db"]["channel_ip"], "LEGACY_IP")
            self.assertEqual(get_source_overrides(b, "adms_db")["channel_ip"], "LEGACY_IP")
        finally:
            a.close(); b.close()

    def test_map_fields_copy_explains_global_mapping_semantics(self):
        source = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("explicit Source Field selections and saved column order are shared by every station", source)
        self.assertIn("Name, deletion and Source Field mapping all apply to every station", source)


if __name__ == "__main__":
    unittest.main()
