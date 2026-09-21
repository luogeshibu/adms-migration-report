from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import (
    site_has_tabular_files,
    site_tabular_files,
)
from migration_report_tool.services.configurable_comparison_service import scan_site_tabular_files
from migration_report_tool.version import __version__


class TestV08186RecursiveSiteSourceDiscovery(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_station_availability_finds_nested_equipment_workbook(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "2-NAJ-HDRJNB"
            equipment = site / "Equipment"
            equipment.mkdir(parents=True)
            source = equipment / "SE.xlsx"
            source.write_bytes(b"placeholder")
            self.assertTrue(site_has_tabular_files(site))
            self.assertEqual(site_tabular_files(site), (source,))

    def test_configurable_pool_is_unbounded_recursive_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = root / "SITE"
            nested = site / "vendor" / "batch" / "revision" / "tables" / "final"
            nested.mkdir(parents=True)
            source = nested / "customer-any-name.csv"
            source.write_text("ID,TYPE\nA,X\n", encoding="utf-8")
            store = ProjectStore(root / "project")
            try:
                store.config["repository_path"] = str(site)
                store.save_config()
                self.assertIn(source, scan_site_tabular_files(store))
            finally:
                store.close()

    def test_temp_and_backup_files_do_not_make_site_available(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "SITE"
            (site / "backup").mkdir(parents=True)
            (site / "backup" / "old.xlsx").write_bytes(b"x")
            (site / "Equipment").mkdir(parents=True)
            (site / "Equipment" / "~$SE.xlsx").write_bytes(b"x")
            self.assertFalse(site_has_tabular_files(site))

    def test_station_list_uses_recursive_availability_helper(self):
        main_window = Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py"
        text = main_window.read_text(encoding="utf-8")
        # The recursive scan runs in the background repository indexer.  The
        # station list reuses its result instead of rescanning a UNC tree on
        # every GUI refresh.
        self.assertIn("has_tabular_files = bool(site.sources or site.unmapped_files)", text)


if __name__ == "__main__":
    unittest.main()
