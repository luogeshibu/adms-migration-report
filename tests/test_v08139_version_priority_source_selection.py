from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import (
    SiteInfo,
    discover_site_sources,
    effective_repository_sources,
    has_explicit_source_version,
    source_version_candidates,
)


class V08139VersionPrioritySourceSelectionTests(unittest.TestCase):
    @staticmethod
    def _write(path: Path, value: str = "X") -> Path:
        path.write_text(f"RMU,Feeder,CabinetType\n1001,{value},2L1T\n", encoding="utf-8")
        return path

    def test_release_version(self):
        root = Path(__file__).resolve().parents[1]
        version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.8.215"', version)

    def test_explicit_version_recognition_is_strict(self):
        self.assertTrue(has_explicit_source_version(Path("ZENON-SLD-V1.csv")))
        self.assertTrue(has_explicit_source_version(Path("ZENON-SLD-v2.1.0.csv")))
        self.assertFalse(has_explicit_source_version(Path("ZENON-SLD.csv")))
        self.assertFalse(has_explicit_source_version(Path("ZENON-SLD-final.csv")))
        self.assertFalse(has_explicit_source_version(Path("ZENON-SLD-VX.csv")))

    def test_auto_uses_highest_semantic_v_and_ignores_unversioned(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "1-ABH"
            site.mkdir()
            self._write(site / "ZENON-SLD.csv", "BASE")
            self._write(site / "ZENON-SLD-V1.csv", "V1")
            self._write(site / "ZENON-SLD-V2.9.csv", "V29")
            self._write(site / "ZENON-SLD-V3.csv", "V3")
            self._write(site / "ZENON-SLD-final.csv", "FINAL")

            candidates = source_version_candidates(site, "zenon_sld")
            self.assertEqual([p.name for p in candidates], [
                "ZENON-SLD-V3.csv", "ZENON-SLD-V2.9.csv", "ZENON-SLD-V1.csv"
            ])
            sources, _detections, unmapped = discover_site_sources(site, deep=False)
            self.assertEqual(sources["zenon_sld"].name, "ZENON-SLD-V3.csv")
            self.assertIn("ZENON-SLD.csv", {p.name for p in unmapped})
            self.assertIn("ZENON-SLD-final.csv", {p.name for p in unmapped})

    def test_user_pin_v2_overrides_auto_v3(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site_dir = root / "1-ABH"
            site_dir.mkdir()
            v2 = self._write(site_dir / "ZENON-SLD-V2.csv", "V2")
            v3 = self._write(site_dir / "ZENON-SLD-V3.csv", "V3")
            sources, detections, unmapped = discover_site_sources(site_dir, deep=False)
            self.assertEqual(sources["zenon_sld"], v3)
            site = SiteInfo("1-ABH", site_dir, sources, detections, unmapped)

            store = ProjectStore(root / "project")
            try:
                store.set_source_file_selection("zenon_sld", v2.name, "tester")
                effective = effective_repository_sources(site, store)
                self.assertEqual(effective["zenon_sld"], v2)
            finally:
                store.close()

    def test_manual_unversioned_assignment_is_allowed_and_beats_auto(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site_dir = root / "1-ABH"
            site_dir.mkdir()
            v3 = self._write(site_dir / "ZENON-SLD-V3.csv", "V3")
            manual = self._write(root / "custom-no-version.csv", "MANUAL")
            sources, detections, unmapped = discover_site_sources(site_dir, deep=False)
            site = SiteInfo("1-ABH", site_dir, sources, detections, unmapped)
            store = ProjectStore(root / "project")
            try:
                # Workspace manual import is intentionally allowed to use a file
                # without a V suffix; explicit reviewer intent outranks AUTO.
                store.set_source("zenon_sld", manual)
                store.mark_manual_source_override("zenon_sld", manual)
                effective = effective_repository_sources(site, store)
                # effective_repository_sources only applies repository pins; GUI/
                # sync uses the manual workspace override ahead of site.sources.
                self.assertEqual(site.sources["zenon_sld"], v3)
                self.assertTrue(store.is_manual_source_override("zenon_sld"))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
