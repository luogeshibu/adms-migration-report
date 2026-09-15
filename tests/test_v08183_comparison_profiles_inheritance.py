from __future__ import annotations

import csv
import os
import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.configurable_comparison_service import (
    apply_comparison_profile,
    build_configurable_review,
    file_family_key,
    get_comparison_profile,
    get_profile_link,
    inspect_table,
    list_comparison_profiles,
    save_comparison_profile,
    save_config,
    save_profile_link,
    source_path,
)
from migration_report_tool.version import __version__


class TestV08183ComparisonProfilesInheritance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_user_root = os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT")
        os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = str(self.root / "userdata")

    def tearDown(self):
        if self.old_user_root is None:
            os.environ.pop("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", None)
        else:
            os.environ["MIGRATION_REPORT_TOOL_USER_DATA_ROOT"] = self.old_user_root
        self.tmp.cleanup()

    @staticmethod
    def _csv(path: Path, rows: list[list[str]]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            csv.writer(handle).writerows(rows)
        return path

    @staticmethod
    def _ids(path: Path) -> dict[str, str]:
        return {column.header: column.id for column in inspect_table(path).columns}

    def test_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_profile_never_stores_origin_site_physical_paths(self):
        site = self.root / "SOURCE_SITE"
        a = self._csv(site / "Equipment" / "SE.csv", [["ID", "FEEDER"], ["D1", "F1"]])
        ids = self._ids(a)
        config = {
            "default_comparison_mode": "ignore_blank",
            "sources": [{
                "id": "src_se", "title": "SE", "path": str(a), "path_mode": "absolute",
                "sheet_name": "", "header_row": 1, "key_column": ids["ID"],
                "hidden_columns": [], "enabled": True, "selection_mode": "latest_family",
                "family_key": file_family_key(a), "family_suffix": ".csv",
            }],
            "comparisons": [{"id": "cmp_feeder", "title": "FEEDER", "comparison_mode": "strict", "bindings": {"src_se": ids["FEEDER"]}}],
        }
        saved = save_comparison_profile("Distribution Standard", config, "tester")
        self.assertEqual(saved["name"], "Distribution Standard")
        profile = get_comparison_profile("Distribution Standard")
        self.assertIsNotNone(profile)
        self.assertEqual(profile["config"]["sources"][0]["path"], "")
        self.assertEqual(profile["config"]["sources"][0]["family_key"], file_family_key(a))
        self.assertEqual(profile["config"]["default_comparison_mode"], "ignore_blank")
        self.assertEqual(profile["config"]["comparisons"][0]["comparison_mode"], "strict")
        self.assertEqual([p["name"] for p in list_comparison_profiles()], ["Distribution Standard"])

    def test_apply_profile_reuses_logical_mapping_but_binds_target_site_file(self):
        origin_site = self.root / "ORIGIN"
        a1 = self._csv(origin_site / "Equipment" / "SE.csv", [["ID", "FEEDER", "TYPE"], ["D1", "F1", "T1"]])
        b1 = self._csv(origin_site / "Equipment" / "DB.csv", [["ID", "FEEDER", "TYPE"], ["D1", "F1", "T1"]])
        aid = self._ids(a1); bid = self._ids(b1)
        source_config = {
            "sources": [
                {"id": "src_se", "title": "SE", "path": str(a1), "path_mode": "absolute", "sheet_name": "", "header_row": 1, "key_column": aid["ID"], "hidden_columns": [], "enabled": True, "selection_mode": "latest_family", "family_key": file_family_key(a1), "family_suffix": ".csv"},
                {"id": "src_db", "title": "DB", "path": str(b1), "path_mode": "absolute", "sheet_name": "", "header_row": 1, "key_column": bid["ID"], "hidden_columns": [], "enabled": True, "selection_mode": "latest_family", "family_key": file_family_key(b1), "family_suffix": ".csv"},
            ],
            "comparisons": [
                {"id": "cmp_feeder", "title": "FEEDER", "bindings": {"src_se": aid["FEEDER"], "src_db": bid["FEEDER"]}},
                {"id": "cmp_type", "title": "TYPE", "bindings": {"src_se": aid["TYPE"], "src_db": bid["TYPE"]}},
            ],
        }
        save_comparison_profile("Standard A", source_config, "tester")

        target_site = self.root / "TARGET"
        a2 = self._csv(target_site / "Equipment" / "SE-V2.csv", [["ID", "FEEDER", "TYPE"], ["D1", "F1", "T1"]])
        b2 = self._csv(target_site / "Equipment" / "DB-V3.csv", [["ID", "FEEDER", "TYPE"], ["D1", "F9", "T1"]])
        store = ProjectStore(self.root / "project_target")
        try:
            store.config["repository_path"] = str(target_site)
            store.save_config()
            merged, meta = apply_comparison_profile(store, "Standard A", current_config={"sources": [], "comparisons": []})
            self.assertEqual(meta["profile_name"], "Standard A")
            paths = {item["title"]: source_path(store, item) for item in merged["sources"]}
            self.assertEqual(paths["SE"], a2)
            self.assertEqual(paths["DB"], b2)
            save_config(store, merged, "tester")
            rows, summary = build_configurable_review(store)
            self.assertEqual(summary["source_count"], 2)
            self.assertEqual(rows[0]["analysis__cmp_feeder"], "FALSE")
            self.assertEqual(rows[0]["analysis__cmp_type"], "TRUE")
        finally:
            store.close()

    def test_sync_preserves_existing_site_path_id_and_disabled_state(self):
        site = self.root / "SITE"
        local = self._csv(site / "custom-location.csv", [["ID", "FEEDER"], ["D1", "F1"]])
        ids = self._ids(local)
        template = {
            "sources": [{
                "id": "template_id", "title": "SE", "path": str(self.root / "DO_NOT_USE.csv"), "path_mode": "absolute",
                "sheet_name": "", "header_row": 1, "key_column": ids["ID"], "hidden_columns": [],
                "enabled": True, "selection_mode": "latest_family", "family_key": "se", "family_suffix": ".csv",
            }],
            "comparisons": [],
        }
        save_comparison_profile("Sync Test", template, "tester")
        store = ProjectStore(self.root / "project")
        try:
            store.config["repository_path"] = str(site)
            store.save_config()
            current = {
                "sources": [{
                    "id": "local_stable_id", "title": "SE", "path": str(local), "path_mode": "absolute",
                    "sheet_name": "", "header_row": 1, "key_column": ids["ID"], "hidden_columns": [],
                    "enabled": False, "selection_mode": "pinned", "family_key": "se", "family_suffix": ".csv",
                }],
                "comparisons": [],
            }
            merged, _ = apply_comparison_profile(store, "Sync Test", current_config=current)
            self.assertEqual(merged["sources"][0]["id"], "local_stable_id")
            self.assertEqual(source_path(store, merged["sources"][0]), local)
            self.assertFalse(merged["sources"][0]["enabled"])
        finally:
            store.close()

    def test_profile_link_is_site_local_and_explicit(self):
        store = ProjectStore(self.root / "project_link")
        try:
            self.assertEqual(get_profile_link(store)["mode"], "local")
            saved = save_profile_link(store, mode="inherit", profile_name="Standard A", profile_modified_at="2026-09-14T10:00:00", synced_at="2026-09-14T10:01:00")
            self.assertEqual(saved["mode"], "inherit")
            self.assertEqual(get_profile_link(store)["profile_name"], "Standard A")
            save_profile_link(store, mode="local")
            self.assertEqual(get_profile_link(store)["mode"], "local")
        finally:
            store.close()

    def test_ui_exposes_explicit_profile_reuse_controls(self):
        text = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        for token in (
            "Configuration Reuse / Inheritance",
            "Local · this site only",
            "Inherit global profile · explicit sync",
            "Save Current as Profile...",
            "Apply / Sync",
            "Update Selected Profile",
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
