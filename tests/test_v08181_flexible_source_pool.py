from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.configurable_comparison_service import (
    build_configurable_review,
    file_family_key,
    get_signal_source_assignments,
    inspect_table,
    resolve_signal_source_assignment,
    review_groups,
    save_config,
    save_signal_source_assignment,
    scan_site_tabular_files,
    source_path,
)
from migration_report_tool.version import __version__


class TestV08181FlexibleSourcePool(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.site = self.root / "SITE"
        self.site.mkdir()
        self.store = ProjectStore(self.root / "project")
        self.store.config["repository_path"] = str(self.site)
        self.store.save_config()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _csv(self, relative: str, rows: list[list[str]]) -> Path:
        path = self.site / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            csv.writer(handle).writerows(rows)
        return path

    def test_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_refresh_inventory_discovers_flat_and_optional_subfolders_without_auto_membership(self):
        flat = self._csv("NEW-SYSTEM.csv", [["ID", "TYPE"], ["A", "T"]])
        equipment = self._csv("Equipment/SE-V2.csv", [["ID", "TYPE"], ["A", "T"]])
        signal = self._csv("SignalMapping/IOA.csv", [["ID", "VALUE"], ["A", "1"]])
        (self.site / "notes.txt").write_text("ignore", encoding="utf-8")
        found = scan_site_tabular_files(self.store)
        self.assertEqual(set(found), {flat, equipment, signal})
        # Discovery is inventory only and never silently creates review sources.
        self.assertEqual(self.store.config.get("equipment_comparison_config_v1"), None)

    def test_auto_family_resolves_explicit_highest_version_then_newest(self):
        v1 = self._csv("Equipment/NEWSYSTEM-SLD-V1.csv", [["ID"], ["A"]])
        v3 = self._csv("Equipment/NEWSYSTEM-SLD-V3.csv", [["ID"], ["A"]])
        base = self._csv("Equipment/NEWSYSTEM-SLD.csv", [["ID"], ["A"]])
        source = {
            "path": str(base.relative_to(self.site)), "path_mode": "site_relative",
            "selection_mode": "latest_family", "family_key": file_family_key(base),
            "family_suffix": ".csv",
        }
        self.assertEqual(source_path(self.store, source), v3)
        v3.unlink()
        self.assertEqual(source_path(self.store, source), v1)

    def test_disabled_equipment_source_is_preserved_but_excluded_from_review(self):
        a = self._csv("A.csv", [["ID", "TYPE"], ["1", "X"]])
        b = self._csv("B.csv", [["ID", "TYPE"], ["1", "Y"]])
        ca = {c.header: c.id for c in inspect_table(a).columns}
        cb = {c.header: c.id for c in inspect_table(b).columns}
        save_config(self.store, {
            "sources": [
                {"id": "a", "title": "A", "path": str(a), "path_mode": "absolute", "sheet_name": "", "header_row": 1, "key_column": ca["ID"], "hidden_columns": [], "enabled": True},
                {"id": "b", "title": "B", "path": str(b), "path_mode": "absolute", "sheet_name": "", "header_row": 1, "key_column": cb["ID"], "hidden_columns": [], "enabled": False},
            ],
            "comparisons": [{"id": "type", "title": "TYPE", "bindings": {"a": ca["TYPE"], "b": cb["TYPE"]}}],
        }, "tester")
        rows, summary = build_configurable_review(self.store)
        self.assertEqual(summary["source_count"], 1)
        self.assertEqual(rows[0]["equipment_source_count"], "1/1")
        groups = {name for name, _color, _cols in review_groups(self.store)}
        self.assertIn("A", groups)
        self.assertNotIn("B", groups)
        cfg = self.store.config["equipment_comparison_config_v1"]
        self.assertEqual(len(cfg["sources"]), 2)
        self.assertFalse(cfg["sources"][1]["enabled"])

    def test_signal_mapping_assignment_can_be_auto_or_pinned(self):
        base = self._csv("SignalMapping/ADMS-SLD.csv", [["ID"], ["A"]])
        newer = self._csv("SignalMapping/ADMS-SLD-V2.csv", [["ID"], ["A"]])
        save_signal_source_assignment(self.store, "adms_sld", base, selection_mode="latest_family")
        self.assertEqual(resolve_signal_source_assignment(self.store, "adms_sld"), newer)
        self.assertEqual(get_signal_source_assignments(self.store)["adms_sld"]["selection_mode"], "latest_family")
        save_signal_source_assignment(self.store, "adms_sld", base, selection_mode="pinned")
        self.assertEqual(resolve_signal_source_assignment(self.store, "adms_sld"), base)

    def test_ui_contract_exposes_pool_membership_and_version_controls(self):
        text = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        for token in (
            "Available Site Files", "Add → Equipment", "Use for Signal...", "Enable / Disable",
            "Participate in Equipment Data Review", "Latest file in family (AUTO)", "Pin this exact file",
        ):
            self.assertIn(token, text)
        self.assertIn('resolve_configurable_signal_assignment(store, source_type)', text)


if __name__ == "__main__":
    unittest.main()
