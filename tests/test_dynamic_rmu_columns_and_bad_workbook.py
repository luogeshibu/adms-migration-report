import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import (
    _quick_tabular_header_rows,
    scan_repository,
)
from migration_report_tool.services.rmu_review_service import build_comparison
from migration_report_tool.services.schema_service import (
    custom_review_column_key,
    rmu_review_groups,
)


class DynamicRMUColumnTests(unittest.TestCase):
    def test_added_adms_sld_field_is_exposed_in_rmu_review(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "ADMS-SLD.csv"
            source.write_text(
                "RMU,TYPE,SMART,NEW LINK\n"
                "17233,2L1T,SMART,LINK-ABC\n",
                encoding="utf-8",
            )
            store = ProjectStore(root / "project")
            try:
                store.set_source("adms_sld", source)
                store.replace_custom_source_fields(
                    "adms_sld",
                    [{"field_key": "new_link", "display_name": "NEW LINK", "actual_column": "NEW LINK"}],
                    "tester",
                )
                rows, _summary = build_comparison(store)
                self.assertEqual(len(rows), 1)
                key = custom_review_column_key("adms_sld", "new_link")
                self.assertEqual(rows[0][key], "LINK-ABC")

                groups = rmu_review_groups(store)
                adms_sld_group = next(cols for group, _color, cols in groups if group == "ADMS SLD")
                self.assertIn((key, "NEW LINK", 130), adms_sld_group)
            finally:
                store.close()


class RepositoryBadWorkbookTests(unittest.TestCase):
    def test_invalid_xlsx_never_crashes_repository_scan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = root / "1-ABN"
            site.mkdir()
            # This reproduces the openpyxl/zipfile.BadZipFile startup failure:
            # a file has an .xlsx suffix but is not an OOXML ZIP workbook.
            bad = site / "SE.xlsx"
            bad.write_bytes(b"this is not a real xlsx workbook")
            self.assertEqual(_quick_tabular_header_rows(bad), [])
            sites = scan_repository(root)
            self.assertEqual(len(sites), 1)
            self.assertEqual(sites[0].name, "1-ABN")


if __name__ == "__main__":
    unittest.main()
