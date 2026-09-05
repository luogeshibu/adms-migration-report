from pathlib import Path
import csv
import tempfile
import unittest

from migration_report_tool.db_smart import (
    build_signal_mapping_report,
    read_db_smart_report,
    SIGNAL_MAPPING_COLUMNS,
)
from migration_report_tool.storage import ProjectStore
from migration_report_tool.paths import resource_root


class SignalMappingReviewTests(unittest.TestCase):
    def _write_ioa(self, path: Path, *, adms_signal="26859 Y1 CMD", adms_dot="1"):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "RMU_NO", "ZENON_GSS-FID", "ZENON_signal_name", "ZENON_DOT_NO",
                "ADMS_GSS-FID", "ADMS_signal_name", "ADMS_DOT_NO",
            ])
            w.writeheader()
            w.writerow({
                "RMU_NO": "26859", "ZENON_GSS-FID": "JED-CTL-RDS-09",
                "ZENON_signal_name": "26859_Y1-RMURDS09_CMD", "ZENON_DOT_NO": "1",
                "ADMS_GSS-FID": "JED CTL ADF 16", "ADMS_signal_name": adms_signal,
                "ADMS_DOT_NO": adms_dot,
            })

    def _write_adms_sld(self, path: Path, cabinet_type="3L1T"):
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["环网柜名称", "环网柜类型", "LINK"])
            w.writeheader()
            w.writerow({"环网柜名称": "26859", "环网柜类型": cabinet_type, "LINK": "TRUE"})

    def test_signal_mapping_is_calculated_from_ioa_adms_sld_and_standard_only(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ioa = root / "ZENON-ADMS-IOA.csv"
            adms_sld = root / "ADMS-SLD.csv"
            self._write_ioa(ioa)
            self._write_adms_sld(adms_sld)
            standard = resource_root() / "templates" / "IOA STANDARD.xlsx"
            report = build_signal_mapping_report(ioa, adms_sld, standard)
            self.assertEqual(report.sheet_name, "Calculated · STANDARD → ADMS validation + ZENON implementation hint")
            self.assertGreater(len(report.rows), 1)
            index = {key: i for i, (key, _label, _width) in enumerate(SIGNAL_MAPPING_COLUMNS)}
            row = next(item for item in report.rows if item.values[index["standard_dot_no"]] == "1")
            self.assertEqual(row.rmu, "26859")
            self.assertEqual(row.values[1], "3L1T")
            self.assertEqual(row.values[index["standard_signal_name"]], "Y1 CMD")
            self.assertEqual(row.values[index["standard_dot_no"]], "1")
            self.assertEqual(row.values[report.analysis_column], "TRUE")
            self.assertIn("Type (from ADMS SLD): 3L1T", row.analysis_detail)
            groups = [g[0] for g in report.group_definitions]
            self.assertLess(groups.index("STANDARD DATABASE I/O list"), groups.index("ADMS"))
            self.assertLess(groups.index("ADMS"), groups.index("ZENON"))

    def test_wrong_rmu_type_does_not_cross_match_another_standard_type(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ioa = root / "ZENON-ADMS-IOA.csv"
            adms_sld = root / "ADMS-SLD.csv"
            self._write_ioa(ioa)
            self._write_adms_sld(adms_sld, cabinet_type="99L99T")
            standard = resource_root() / "templates" / "IOA STANDARD.xlsx"
            report = build_signal_mapping_report(ioa, adms_sld, standard)
            self.assertEqual(report.rows[0].values[report.analysis_column], "FALSE")
            self.assertIn("not present in the STANDARD point list", report.rows[0].analysis_detail)

    def test_same_dot_but_different_signal_name_is_false(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ioa = root / "ZENON-ADMS-IOA.csv"
            adms_sld = root / "ADMS-SLD.csv"
            self._write_ioa(ioa, adms_signal="26859 DEFINITELY WRONG SIGNAL")
            self._write_adms_sld(adms_sld, cabinet_type="3L1T")
            standard = resource_root() / "templates" / "IOA STANDARD.xlsx"
            report = build_signal_mapping_report(ioa, adms_sld, standard)
            row = next(item for item in report.rows if item.values[report.analysis_column] == "FALSE" and "DEFINITELY WRONG SIGNAL" in item.analysis_detail)
            self.assertIn("signal name mismatch", row.analysis_detail)

    def test_legacy_db_smart_sheet_is_not_a_source_anymore(self):
        with self.assertRaises(RuntimeError):
            read_db_smart_report(resource_root() / "templates" / "IOA STANDARD.xlsx")

    def test_store_builder_uses_bundled_standard_not_site_report(self):
        from migration_report_tool.db_smart import build_signal_mapping_report_from_store
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ioa = root / "ZENON-ADMS-IOA.csv"
            adms_sld = root / "ADMS-SLD.csv"
            self._write_ioa(ioa)
            self._write_adms_sld(adms_sld)
            store = ProjectStore(root / "project")
            try:
                store.set_source("ioa", ioa)
                store.set_source("adms_sld", adms_sld)
                report = build_signal_mapping_report_from_store(store)
                index = {key: i for i, (key, _label, _width) in enumerate(SIGNAL_MAPPING_COLUMNS)}
                self.assertEqual(report.rows[0].values[index["standard_signal_name"]], "Y1 CMD")
                self.assertTrue(any(p.name == "IOA STANDARD.xlsx" for p in report.input_paths))
            finally:
                store.db.close()

    def test_signal_mapping_review_is_persistent_and_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp) / "ADF")
            store.update_db_smart_review(
                row_key="row-key-1", rmu="26859", field="review_status", value="CLOSED",
                modified_by="tester", source_hash="abc", site_name="ADF",
            )
            store.update_db_smart_review(
                row_key="row-key-1", rmu="26859", field="comments", value="Checked by SE",
                modified_by="tester", source_hash="abc", site_name="ADF",
            )
            review = store.db_smart_review_map()["row-key-1"]
            self.assertEqual(review["review_status"], "CLOSED")
            self.assertEqual(review["comments"], "Checked by SE")
            changes = store.changes()
            self.assertEqual(len(changes), 2)
            self.assertTrue(changes[0]["rmu"].startswith("DBSMART:"))
            store.db.close()


if __name__ == "__main__":
    unittest.main()
