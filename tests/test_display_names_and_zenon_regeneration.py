from pathlib import Path
import csv
import tempfile
import unittest
import os

from openpyxl import load_workbook

from migration_report_tool.config.column_schema import COMPARISON_GROUPS
from migration_report_tool.core import build_comparison, export_report
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import SiteInfo
from migration_report_tool.services.schema_service import (
    RMU_REVIEW_DISPLAY_BINDINGS,
    SIGNAL_REVIEW_DISPLAY_BINDINGS,
    apply_display_names_to_groups,
    get_source_display_names,
    set_source_display_names,
)
from migration_report_tool.domain.mapping.signal_mapping import SIGNAL_MAPPING_GROUPS
from migration_report_tool.services.zenon_sld_service import regenerate_site_zenon_sld


class DisplayNameAndZenonRegenerationTests(unittest.TestCase):
    def setUp(self):
        self._global_tmp = tempfile.TemporaryDirectory()
        self._old_user_data = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(Path(self._global_tmp.name) / "user-data")

    def tearDown(self):
        if self._old_user_data is None:
            os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = self._old_user_data
        self._global_tmp.cleanup()

    def test_global_display_names_are_applied(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "ABS")
            try:
                set_source_display_names(
                    store,
                    "ioa",
                    {
                        "rmu": "RMU Number",
                        "zenon_gss_fid": "ZENON Feeder ID",
                        "adms_signal_name": "ADMS Signal",
                    },
                    "tester",
                )
                self.assertEqual(get_source_display_names(store, "ioa")["rmu"], "RMU Number")
                groups = apply_display_names_to_groups(
                    SIGNAL_MAPPING_GROUPS, store, SIGNAL_REVIEW_DISPLAY_BINDINGS
                )
                columns = {key: label for _g, _c, cols in groups for key, label, _w in cols}
                self.assertEqual(columns["rmu_no"], "RMU Number")
                self.assertEqual(columns["zenon_gss_fid"], "ZENON Feeder ID")
                self.assertEqual(columns["adms_signal_name"], "ADMS Signal")
                # Internal report keys never change.
                self.assertIn("zenon_gss_fid", columns)
            finally:
                store.db.close()

    def test_default_display_name_is_not_persisted_as_override(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "ABS")
            try:
                set_source_display_names(store, "ioa", {"rmu": "RMU"}, "tester")
                self.assertEqual(get_source_display_names(store, "ioa"), {})
            finally:
                store.db.close()

    def test_rmu_review_display_name_binding_changes_only_label(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "ABS")
            try:
                set_source_display_names(store, "adms_db", {"gss_fid": "ADMS Feeder ID"}, "tester")
                groups = apply_display_names_to_groups(
                    COMPARISON_GROUPS, store, RMU_REVIEW_DISPLAY_BINDINGS
                )
                columns = {key: label for _g, _c, cols in groups for key, label, _w in cols}
                self.assertEqual(columns["adb_gss_fid"], "ADMS Feeder ID")
                self.assertIn("adb_gss_fid", columns)
            finally:
                store.db.close()

    def test_display_names_are_used_by_formal_excel_review_headers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sample = Path(__file__).resolve().parents[1] / "examples" / "sample-data"
            store = ProjectStore(root / "ABS")
            try:
                mapping = {
                    "se_list": "SE.xlsx", "zenon_db": "ZENON-DB.csv", "zenon_sld": "ZENON-SLD.csv",
                    "adms_db": "ADMS-DB.csv", "adms_sld": "ADMS-SLD.csv", "ioa": "ZENON-ADMS-IOA.csv",
                }
                for source_type, filename in mapping.items():
                    store.set_source(source_type, sample / filename)
                rows, _summary = build_comparison(store)
                store.save_comparison(rows)
                set_source_display_names(store, "se_list", {"feeder": "SE Circuit"}, "tester")
                set_source_display_names(store, "ioa", {"rmu": "Equipment ID"}, "tester")
                target = export_report(store)
                wb = load_workbook(target, read_only=True, data_only=False)
                try:
                    self.assertEqual(wb["RMU Data Review"]["M2"].value, "SE Circuit")
                    self.assertEqual(wb["Signal Mapping Review"]["C2"].value, "Equipment ID")
                finally:
                    wb.close()
            finally:
                store.db.close()

    def test_regenerate_zenon_sld_atomically_replaces_existing_csv(self):
        xml = """<?xml version='1.0' encoding='utf-8'?>
<Root>
  <Picture ShortName='ABS-110'>
    <Elements_0><LinkName>01_VERT_SRMU_2L1T_01</LinkName><SubstituteDestination>JED-NTH-ABS-04-6299</SubstituteDestination></Elements_0>
  </Picture>
</Root>"""
        with tempfile.TemporaryDirectory() as td:
            site_dir = Path(td) / "ABS"
            site_dir.mkdir()
            xml_path = site_dir / "ABS.XML"
            xml_path.write_text(xml, encoding="utf-8")
            target = site_dir / "ZENON-SLD.csv"
            target.write_text("OLD CONTENT\n", encoding="utf-8")
            store = ProjectStore(Path(td) / "app-workspace")
            try:
                site = SiteInfo("ABS", site_dir, {"zenon_xml": xml_path})
                result = regenerate_site_zenon_sld(site, store)
                self.assertEqual(result.row_count, 1)
                self.assertEqual(result.target_path, target)
                with target.open("r", encoding="utf-8-sig", newline="") as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(rows[0]["RMU"], "6299")
                self.assertEqual(rows[0]["Feeder"], "JED-NTH-ABS-04")
                self.assertEqual(rows[0]["Screen name"], "ABS-110")
            finally:
                store.db.close()

    def test_zero_row_regeneration_keeps_existing_csv(self):
        xml = """<?xml version='1.0' encoding='utf-8'?><Root><Picture ShortName='OTHER'/></Root>"""
        with tempfile.TemporaryDirectory() as td:
            site_dir = Path(td) / "ABS"
            site_dir.mkdir()
            xml_path = site_dir / "ABS.XML"
            xml_path.write_text(xml, encoding="utf-8")
            target = site_dir / "ZENON-SLD.csv"
            target.write_text("OLD CONTENT\n", encoding="utf-8")
            store = ProjectStore(Path(td) / "app-workspace")
            try:
                site = SiteInfo("ABS", site_dir, {"zenon_xml": xml_path})
                with self.assertRaises(ValueError):
                    regenerate_site_zenon_sld(site, store)
                self.assertEqual(target.read_text(encoding="utf-8"), "OLD CONTENT\n")
            finally:
                store.db.close()


if __name__ == "__main__":
    unittest.main()
