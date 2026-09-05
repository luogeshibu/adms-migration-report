from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem import site_repository as repo


class V08140AutoDetectionFallbackPriorityTests(unittest.TestCase):
    @staticmethod
    def _write(path: Path, feeder: str = "X") -> Path:
        path.write_text(f"RMU,Feeder,CabinetType\n1001,{feeder},2L1T\n", encoding="utf-8")
        return path

    def test_release_version(self):
        root = Path(__file__).resolve().parents[1]
        version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.8.143"', version)

    def test_latest_valid_v_wins_over_unversioned_rule_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            self._write(site / "ADMS-SLD.csv", "BASE")
            self._write(site / "ADMS-SLD-V1.csv", "V1")
            self._write(site / "ADMS-SLD-V2.1.csv", "V21")
            sources, detections, _ = repo.discover_site_sources(site, deep=False)
            self.assertEqual(sources["adms_sld"].name, "ADMS-SLD-V2.1.csv")
            self.assertEqual(detections["adms_sld"].method, "Auto Latest Version")

    def test_unversioned_base_uses_detection_rule_when_no_v_exists(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            self._write(site / "ADMS-SLD.csv", "BASE")
            sources, detections, _ = repo.discover_site_sources(site, deep=False)
            self.assertEqual(sources["adms_sld"].name, "ADMS-SLD.csv")
            self.assertEqual(detections["adms_sld"].method, "Auto Detection Rule")

    def test_custom_detection_rule_can_resolve_unversioned_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = root / "ADF"
            site.mkdir()
            self._write(site / "MY-SLD-DATA.csv", "BASE")
            cfg = root / "site_repository.json"
            with patch.object(repo, "_config_path", return_value=cfg):
                keywords = repo.load_source_detection_keywords()
                keywords["adms_sld"] = ["MY-SLD-DATA"]
                repo.save_source_detection_keywords(keywords)
                sources, detections, _ = repo.discover_site_sources(site, deep=False)
            self.assertEqual(sources["adms_sld"].name, "MY-SLD-DATA.csv")
            self.assertEqual(detections["adms_sld"].method, "Auto Detection Rule")

    def test_malformed_v_suffix_is_not_auto_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            self._write(site / "ADMS-SLD-VX.csv", "BAD")
            sources, _detections, unmapped = repo.discover_site_sources(site, deep=False)
            self.assertNotIn("adms_sld", sources)
            self.assertIn("ADMS-SLD-VX.csv", {p.name for p in unmapped})

    def test_user_pin_still_beats_auto_latest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site_dir = root / "ADF"
            site_dir.mkdir()
            v2 = self._write(site_dir / "ADMS-SLD-V2.csv", "V2")
            v3 = self._write(site_dir / "ADMS-SLD-V3.csv", "V3")
            sources, detections, unmapped = repo.discover_site_sources(site_dir, deep=False)
            site = repo.SiteInfo("ADF", site_dir, sources, detections, unmapped)
            self.assertEqual(site.sources["adms_sld"], v3)
            store = ProjectStore(root / "project")
            try:
                store.set_source_file_selection("adms_sld", v2.name, "reviewer")
                self.assertEqual(repo.effective_repository_sources(site, store)["adms_sld"], v2)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
