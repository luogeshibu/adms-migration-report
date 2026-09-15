from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.configurable_comparison_service import (
    COMPARISON_MODE_DEFAULT,
    COMPARISON_MODE_IGNORE_BLANK,
    COMPARISON_MODE_STRICT,
    analysis_column_key,
    build_configurable_review,
    inspect_table,
    normalize_config,
    save_config,
)
from migration_report_tool.version import __version__


class TestV08192SelectableComparisonModes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = ProjectStore(self.root / "project")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _csv(self, name: str, rows: list[list[object]]) -> Path:
        path = self.root / name
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            csv.writer(handle).writerows(rows)
        return path

    @staticmethod
    def _ids(path: Path) -> dict[str, str]:
        return {column.header: column.id for column in inspect_table(path).columns}

    def _config(self, default_mode: str) -> dict:
        a = self._csv("a.csv", [["NAME", "FEEDER"], ["D1", "F1"], ["D2", ""], ["D3", "F1"]])
        b = self._csv("b.csv", [["NAME", "FDR"], ["D1", ""], ["D2", ""], ["D3", "F2"]])
        aid, bid = self._ids(a), self._ids(b)
        return {
            "default_comparison_mode": default_mode,
            "sources": [
                {"id": "a", "title": "A", "path": str(a), "path_mode": "absolute", "header_row": 1, "key_column": aid["NAME"], "hidden_columns": []},
                {"id": "b", "title": "B", "path": str(b), "path_mode": "absolute", "header_row": 1, "key_column": bid["NAME"], "hidden_columns": []},
            ],
            "comparisons": [
                {"id": "inherit", "title": "INHERIT", "comparison_mode": COMPARISON_MODE_DEFAULT, "bindings": {"a": aid["FEEDER"], "b": bid["FDR"]}},
                {"id": "strict", "title": "STRICT", "comparison_mode": COMPARISON_MODE_STRICT, "bindings": {"a": aid["FEEDER"], "b": bid["FDR"]}},
                {"id": "loose", "title": "LOOSE", "comparison_mode": COMPARISON_MODE_IGNORE_BLANK, "bindings": {"a": aid["FEEDER"], "b": bid["FDR"]}},
            ],
        }

    def test_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_old_configs_migrate_to_strict_site_default(self):
        config = normalize_config({"sources": [], "comparisons": [{"id": "x", "title": "X", "bindings": {}}]})
        self.assertEqual(config["default_comparison_mode"], COMPARISON_MODE_STRICT)
        self.assertEqual(config["comparisons"][0]["comparison_mode"], COMPARISON_MODE_DEFAULT)

    def test_rule_can_inherit_or_override_strict_site_default(self):
        save_config(self.store, self._config(COMPARISON_MODE_STRICT), "tester")
        rows, _ = build_configurable_review(self.store)
        by_key = {row["rmu"]: row for row in rows}
        self.assertEqual(by_key["D1"][analysis_column_key("inherit")], "FALSE")
        self.assertEqual(by_key["D1"][analysis_column_key("strict")], "FALSE")
        self.assertEqual(by_key["D1"][analysis_column_key("loose")], "TRUE")
        self.assertEqual(by_key["D2"][analysis_column_key("inherit")], "TRUE")
        self.assertEqual(by_key["D2"][analysis_column_key("loose")], "")
        self.assertEqual(by_key["D3"][analysis_column_key("inherit")], "FALSE")
        self.assertIn("Mode: Strict equality", by_key["D1"][analysis_column_key("inherit") + "__detail"])
        self.assertIn("Mode: Ignore blank values", by_key["D1"][analysis_column_key("loose") + "__detail"])
        self.assertIn("B: <blank>", by_key["D1"][analysis_column_key("loose") + "__detail"])

    def test_rule_can_override_ignore_blank_site_default(self):
        save_config(self.store, self._config(COMPARISON_MODE_IGNORE_BLANK), "tester")
        rows, _ = build_configurable_review(self.store)
        by_key = {row["rmu"]: row for row in rows}
        self.assertEqual(by_key["D1"][analysis_column_key("inherit")], "TRUE")
        self.assertEqual(by_key["D1"][analysis_column_key("strict")], "FALSE")
        self.assertEqual(by_key["D1"][analysis_column_key("loose")], "TRUE")
        self.assertEqual(by_key["D2"][analysis_column_key("inherit")], "")
        self.assertEqual(by_key["D3"][analysis_column_key("inherit")], "FALSE")

    def test_ui_exposes_site_default_and_per_rule_mode(self):
        text = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        for token in (
            "Default Comparison Mode",
            "Use site default",
            "Strict equality · blank participates",
            "Ignore blank values",
            '"comparison_mode"',
        ):
            self.assertIn(token, text)


if __name__ == "__main__":
    unittest.main()
