from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.domain.analysis.severity import analysis_review_state
from migration_report_tool.services.configurable_comparison_service import (
    CONFIG_KEY,
    analysis_column_key,
    bootstrap_legacy_sources,
    build_configurable_review,
    get_config,
    inspect_table,
    review_column_key,
    review_groups,
    save_config,
)
from migration_report_tool.version import __version__


class TestV08178ConfigurableEquipmentComparison(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.store = ProjectStore(self.project)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _csv(self, name: str, headers: list[str], rows: list[list[object]]) -> Path:
        path = self.root / name
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
        return path

    def _xlsx(self, name: str, sheet_name: str, headers: list[str], rows: list[list[object]]) -> Path:
        path = self.root / name
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(path)
        wb.close()
        return path

    @staticmethod
    def _col(path: Path, header: str, sheet_name: str = "") -> str:
        structure = inspect_table(path, sheet_name=sheet_name, header_row=1)
        return next(column.id for column in structure.columns if column.header == header)

    def test_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_any_number_of_files_and_per_file_keys_build_dynamic_review(self):
        a = self._csv(
            "anything-A.csv",
            ["EquipmentName", "Feeder", "Type", "Only-A"],
            [["D1", "F1", "T1", "A1"], ["D2", "F2", "T2", "A2"]],
        )
        b = self._csv(
            "customer_export_2026.csv",
            ["Asset_ID", "FeedCode", "ModelType", "Only-B"],
            [["D1", "F1", "T1", "B1"], ["D2", "F9", "T2", "B2"]],
        )
        c = self._xlsx(
            "third totally arbitrary.xlsx",
            "Devices Here",
            ["NAME", "FeederX", "Kind", "Only-C"],
            [["D1", "F1", "T1", "C1"], ["D2", "F2", "T2", "C2"], ["D3", "F3", "T3", "C3"]],
        )

        config = {
            "sources": [
                {
                    "id": "src_a", "title": "Primary Equipment", "path": str(a), "path_mode": "absolute",
                    "sheet_name": "", "header_row": 1, "key_column": self._col(a, "EquipmentName"), "hidden_columns": [],
                },
                {
                    "id": "src_b", "title": "Customer DB", "path": str(b), "path_mode": "absolute",
                    "sheet_name": "", "header_row": 1, "key_column": self._col(b, "Asset_ID"), "hidden_columns": [],
                },
                {
                    "id": "src_c", "title": "SLD Export", "path": str(c), "path_mode": "absolute",
                    "sheet_name": "Devices Here", "header_row": 1, "key_column": self._col(c, "NAME", "Devices Here"), "hidden_columns": [],
                },
            ],
            "comparisons": [
                {
                    "id": "cmp_feeder", "title": "Feeder",
                    "bindings": {
                        "src_a": self._col(a, "Feeder"),
                        "src_b": self._col(b, "FeedCode"),
                        "src_c": self._col(c, "FeederX", "Devices Here"),
                    },
                },
                {
                    "id": "cmp_type", "title": "Equipment Type",
                    "bindings": {
                        "src_a": self._col(a, "Type"),
                        "src_b": self._col(b, "ModelType"),
                        "src_c": self._col(c, "Kind", "Devices Here"),
                    },
                },
            ],
        }
        save_config(self.store, config, "tester")
        rows, summary = build_configurable_review(self.store)
        self.assertEqual(summary["source_count"], 3)
        self.assertEqual([row["rmu"] for row in rows], ["D1", "D2", "D3"])
        by_key = {row["rmu"]: row for row in rows}

        self.assertEqual(by_key["D1"][analysis_column_key("cmp_feeder")], "TRUE")
        self.assertEqual(by_key["D1"][analysis_column_key("cmp_type")], "TRUE")
        self.assertEqual(by_key["D2"][analysis_column_key("cmp_feeder")], "FALSE")
        self.assertEqual(by_key["D2"][analysis_column_key("cmp_type")], "TRUE")
        # Strict rule: src_a/src_b are bound but the D3 row is absent there, so their
        # blank values participate and disagree with src_c=F3.
        self.assertEqual(by_key["D3"][analysis_column_key("cmp_feeder")], "FALSE")
        self.assertEqual(by_key["D2"]["equipment_source_count"], "3/3")
        self.assertEqual(by_key["D3"]["equipment_source_count"], "1/3")
        self.assertEqual(analysis_review_state(by_key["D2"]).issue_count, 1)
        self.assertIn("cmp_feeder", analysis_review_state(by_key["D2"]).false_fields)

        # Every physical field is rendered by default, and group titles are user-editable source titles.
        groups = review_groups(self.store)
        group_map = {name: columns for name, _color, columns in groups}
        self.assertIn("Primary Equipment", group_map)
        self.assertIn("Customer DB", group_map)
        self.assertIn("SLD Export", group_map)
        self.assertEqual(len(group_map["Primary Equipment"]), 4)
        self.assertEqual(len(group_map["Customer DB"]), 4)
        self.assertEqual(len(group_map["SLD Export"]), 4)

        # Source fields are preserved in row data under stable source/physical ids.
        only_a = self._col(a, "Only-A")
        self.assertEqual(by_key["D1"][review_column_key("src_a", only_a)], "A1")

    def test_site_local_hide_is_presentation_only(self):
        source = self._csv("source.csv", ["ID", "Compare", "Keep", "HideMe"], [["1", "X", "K", "H"]])
        cols = inspect_table(source).columns
        ids = {column.header: column.id for column in cols}
        config = {
            "sources": [{
                "id": "src_1", "title": "My File", "path": str(source), "path_mode": "absolute",
                "sheet_name": "", "header_row": 1, "key_column": ids["ID"], "hidden_columns": [ids["HideMe"]],
            }],
            "comparisons": [],
        }
        save_config(self.store, config, "tester")
        groups = review_groups(self.store)
        source_group = next(columns for name, _color, columns in groups if name == "My File")
        labels = [label for _key, label, _width in source_group]
        self.assertIn("ID", labels)
        self.assertIn("Compare", labels)
        self.assertIn("Keep", labels)
        self.assertNotIn("HideMe", labels)

        rows, _ = build_configurable_review(self.store)
        self.assertEqual(rows[0][review_column_key("src_1", ids["HideMe"])], "H")

    def test_legacy_bootstrap_is_editable_proposal_and_cancel_safe(self):
        source = self._csv("legacy-se.csv", ["Equipment Name", "FEEDER"], [["D1", "F1"]])
        self.store.set_source("se_list", source)
        self.assertNotIn(CONFIG_KEY, self.store.config)
        proposal = bootstrap_legacy_sources(self.store)
        self.assertEqual(len(proposal["sources"]), 1)
        self.assertNotIn(CONFIG_KEY, self.store.config)
        self.assertEqual(get_config(self.store, bootstrap=False)["sources"], [])

    def test_generic_source_values_participate_in_existing_source_change_projection(self):
        row = {
            review_column_key("src_any", "c_any"): "VALUE",
            "_source_audit_names": {"src_any": "User File"},
            "_source_field_labels": {"src_any": {"c_any": "Custom Header"}},
        }
        projection = self.store._comparison_source_projection(row)
        self.assertEqual(projection[("src_any", "c_any")], "VALUE")


if __name__ == "__main__":
    unittest.main()
