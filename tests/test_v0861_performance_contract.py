from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_report_tool.infrastructure.filesystem import site_repository as repo


class FastRepositoryNavigationTests(unittest.TestCase):
    def test_shallow_scan_never_uses_schema_or_xml_content_detection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = root / "1-ABH"
            site.mkdir()
            # Deliberately invalid workbook bytes: shallow discovery must use the
            # canonical filename without trying to open it as an XLSX archive.
            (site / "SE.xlsx").write_bytes(b"not-an-xlsx")
            (site / "ZENON-SLD-V2.csv").write_text("RMU,TYPE\n1001,2L1T\n", encoding="utf-8")
            (site / "ADMS-DB.csv").write_text("RMU_NAME,TYPE\n1001,2L1T\n", encoding="utf-8")
            (site / "ADMS-SLD.csv").write_text("RMU,TYPE\n1001,2L1T\n", encoding="utf-8")

            with patch.object(repo, "_schema_content_score", side_effect=AssertionError("deep schema read")):
                sites = repo.scan_repository(root, deep=False)

            self.assertEqual(len(sites), 1)
            # Shallow discovery chooses the highest explicit V version first,
            # then falls back to canonical/configured filename rules without
            # opening source content.
            self.assertEqual(sites[0].sources["zenon_sld"].name, "ZENON-SLD-V2.csv")
            self.assertEqual(sites[0].sources["se_list"].name, "SE.xlsx")
            self.assertEqual(sites[0].sources["adms_db"].name, "ADMS-DB.csv")

    def test_quick_source_status_does_not_sha256_source_files(self):
        with tempfile.TemporaryDirectory() as td:
            site_dir = Path(td) / "1-ABH"
            site_dir.mkdir()
            source = site_dir / "ZENON-SLD.csv"
            source.write_text("RMU,TYPE\n1001,2L1T\n", encoding="utf-8")
            site = repo.SiteInfo("1-ABH", site_dir, {"zenon_sld": source})

            with patch.object(repo, "file_sha256", side_effect=AssertionError("SHA256 should be explicit only")):
                status = repo.source_status(site, None, hash_contents=False)

            self.assertEqual(status["zenon_sld"]["path"], source)
            self.assertEqual(status["zenon_sld"]["fingerprint"]["sha256"], "")

    def test_ui_startup_and_site_switch_are_lazy_by_contract(self):
        ui_path = Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py"
        text = ui_path.read_text(encoding="utf-8")
        self.assertIn("QTimer.singleShot(0, self._load_initial_workspace)", text)
        self.assertIn("self.refresh_site_repository(force=False, deep=False)", text)
        self.assertIn("ordinary site switching must never open IOA/ADMS-SLD/STANDARD", text)
        self.assertNotIn("self.refresh_all(refresh_sources=True)", text)


if __name__ == "__main__":
    unittest.main()
