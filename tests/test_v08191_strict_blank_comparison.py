from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from migration_report_tool.domain.analysis.consistency import compare_strict_consistency
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.configurable_comparison_service import (
    analysis_column_key,
    build_configurable_review,
    inspect_table,
    save_config,
)
from migration_report_tool.version import __version__


class TestV08191StrictBlankComparison(unittest.TestCase):
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

    def test_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_strict_helper_treats_blank_as_real_value(self):
        normalizer = lambda value: "" if value is None else str(value).strip()
        self.assertTrue(compare_strict_consistency({"A": "F1", "B": "F1"}, normalizer).value)
        self.assertFalse(compare_strict_consistency({"A": "F1", "B": ""}, normalizer).value)
        self.assertTrue(compare_strict_consistency({"A": "", "B": ""}, normalizer).value)
        self.assertFalse(compare_strict_consistency({"A": "F1", "B": "F2", "C": "F1"}, normalizer).value)
        self.assertFalse(compare_strict_consistency({"A": "", "B": "", "C": "F1"}, normalizer).value)

    def test_configurable_review_blank_nonblank_is_false_and_all_blank_is_true(self):
        a = self._csv("a.csv", [["NAME", "FEEDER", "TYPE"], ["D1", "F1", ""], ["D2", "", ""], ["D3", "F3", "T3"]])
        b = self._csv("b.csv", [["DEVICE", "FDR", "KIND"], ["D1", "", ""], ["D2", "", ""], ["D3", "F3", "T3"]])
        aid, bid = self._ids(a), self._ids(b)
        save_config(self.store, {
            "sources": [
                {"id": "a", "title": "A", "path": str(a), "path_mode": "absolute", "header_row": 1, "key_column": aid["NAME"], "hidden_columns": []},
                {"id": "b", "title": "B", "path": str(b), "path_mode": "absolute", "header_row": 1, "key_column": bid["DEVICE"], "hidden_columns": []},
            ],
            "comparisons": [
                {"id": "feed", "title": "FEEDER", "bindings": {"a": aid["FEEDER"], "b": bid["FDR"]}},
                {"id": "type", "title": "TYPE", "bindings": {"a": aid["TYPE"], "b": bid["KIND"]}},
            ],
        }, "tester")
        rows, _ = build_configurable_review(self.store)
        by_key = {row["rmu"]: row for row in rows}
        self.assertEqual(by_key["D1"][analysis_column_key("feed")], "FALSE")   # F1 vs blank
        self.assertEqual(by_key["D1"][analysis_column_key("type")], "TRUE")   # blank vs blank
        self.assertEqual(by_key["D2"][analysis_column_key("feed")], "TRUE")   # blank vs blank
        self.assertEqual(by_key["D3"][analysis_column_key("feed")], "TRUE")   # F3 vs F3
        self.assertEqual(by_key["D3"][analysis_column_key("type")], "TRUE")   # T3 vs T3
        self.assertIn("<blank>", by_key["D1"][analysis_column_key("feed") + "__detail"])

    def test_missing_bound_source_row_counts_as_blank(self):
        a = self._csv("left.csv", [["NAME", "FEEDER"], ["D1", "F1"], ["D2", ""]])
        b = self._csv("right.csv", [["NAME", "FEEDER"], ["D2", ""]])
        aid, bid = self._ids(a), self._ids(b)
        save_config(self.store, {
            "sources": [
                {"id": "a", "title": "A", "path": str(a), "path_mode": "absolute", "header_row": 1, "key_column": aid["NAME"], "hidden_columns": []},
                {"id": "b", "title": "B", "path": str(b), "path_mode": "absolute", "header_row": 1, "key_column": bid["NAME"], "hidden_columns": []},
            ],
            "comparisons": [{"id": "feed", "title": "FEEDER", "bindings": {"a": aid["FEEDER"], "b": bid["FEEDER"]}}],
        }, "tester")
        rows, _ = build_configurable_review(self.store)
        by_key = {row["rmu"]: row for row in rows}
        self.assertEqual(by_key["D1"][analysis_column_key("feed")], "FALSE")  # F1 vs missing row => blank
        self.assertEqual(by_key["D2"][analysis_column_key("feed")], "TRUE")   # blank vs blank

    def test_unbound_source_does_not_participate(self):
        a = self._csv("a.csv", [["NAME", "FEEDER"], ["D1", "F1"]])
        b = self._csv("b.csv", [["NAME", "OTHER"], ["D1", "anything"]])
        aid, bid = self._ids(a), self._ids(b)
        save_config(self.store, {
            "sources": [
                {"id": "a", "title": "A", "path": str(a), "path_mode": "absolute", "header_row": 1, "key_column": aid["NAME"], "hidden_columns": []},
                {"id": "b", "title": "B", "path": str(b), "path_mode": "absolute", "header_row": 1, "key_column": bid["NAME"], "hidden_columns": []},
            ],
            "comparisons": [{"id": "feed", "title": "FEEDER", "bindings": {"a": aid["FEEDER"]}}],
        }, "tester")
        rows, _ = build_configurable_review(self.store)
        self.assertEqual(rows[0][analysis_column_key("feed")], "TRUE")


if __name__ == "__main__":
    unittest.main()
