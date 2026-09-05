from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import (
    get_source_display_names,
    set_source_display_names,
    rmu_review_groups,
)
from migration_report_tool.services.rmu_review_service import rmu_type_issue_map


class GlobalColumnsAndSignalTypeWarningV08123Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_user_data = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(Path(self._tmp.name) / "user-data")

    def tearDown(self):
        if self._old_user_data is None:
            os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = self._old_user_data
        self._tmp.cleanup()

    def test_built_in_app_column_rename_is_global_across_sites(self):
        a = ProjectStore(Path(self._tmp.name) / "site-a")
        b = ProjectStore(Path(self._tmp.name) / "site-b")
        try:
            set_source_display_names(a, "adms_db", {"channel_ip": "IP-BAK"}, "tester")
            self.assertEqual(get_source_display_names(b, "adms_db").get("channel_ip"), "IP-BAK")
            groups = {group: list(columns) for group, _color, columns in rmu_review_groups(b)}
            labels = {key: label for key, label, _width in groups["ADMS DB"]}
            self.assertEqual(labels.get("adms_channel_ip"), "IP-BAK")
        finally:
            a.close(); b.close()

    def test_user_added_app_column_definition_and_mapping_are_global(self):
        a = ProjectStore(Path(self._tmp.name) / "site-a")
        b = ProjectStore(Path(self._tmp.name) / "site-b")
        try:
            a.replace_custom_source_fields(
                "adms_db",
                [{"field_key": "backup_ip", "display_name": "IP-BAK", "actual_column": "NET_DESCRIPTION1"}],
                "tester",
            )
            b_fields = b.custom_source_fields("adms_db")
            self.assertEqual([(x["field_key"], x["display_name"]) for x in b_fields], [("backup_ip", "IP-BAK")])
            self.assertEqual(b_fields[0]["actual_column"], "NET_DESCRIPTION1")
            groups = {group: list(columns) for group, _color, columns in rmu_review_groups(b)}
            self.assertTrue(any(label == "IP-BAK" for _key, label, _width in groups["ADMS DB"]))
        finally:
            a.close(); b.close()

    def test_signal_type_warning_reuses_rmu_data_review_type_tooltip(self):
        class FakeStore:
            def rows(self):
                return [
                    {
                        "rmu": "36352",
                        "analysis_type": "FALSE",
                        "analysis_type_detail": "TYPE consistency check\n\nZENON SLD: 2L1T\nADMS DB: 2L2T\nADMS SLD: 2L2T\n\nResult: FALSE",
                    },
                    {"rmu": "36361", "analysis_type": "TRUE", "analysis_type_detail": "TYPE consistency check\n\nResult: TRUE"},
                ]

        warnings = rmu_type_issue_map(FakeStore())
        self.assertEqual(set(warnings), {"36352"})
        self.assertIn("ZENON SLD: 2L1T", warnings["36352"])
        self.assertIn("Result: FALSE", warnings["36352"])

    def test_signal_rmu_overview_marks_only_rmu_cell_with_distinct_color_and_same_tooltip(self):
        source = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("type_issue_map = rmu_type_issue_map(self.store)", source)
        block = source[source.index("def _render_db_smart_rmu_list"):source.index("def _show_db_smart_rmu_overview")]
        self.assertIn('if col == 0:', block)
        self.assertIn('cell.setBackground(QColor("#F3E8FF"))', block)
        self.assertIn('cell.setForeground(QColor("#6D28D9"))', block)
        self.assertIn("cell.setToolTip(type_issue_tooltip)", block)
        self.assertNotIn('fill = QColor("#F3E8FF")', block)


if __name__ == "__main__":
    unittest.main()
