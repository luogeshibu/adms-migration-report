from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from migration_report_tool.domain.schema import SchemaValidationError
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import SiteInfo, sync_site_to_project
from migration_report_tool.services.configurable_comparison_service import (
    analysis_column_key,
    build_configurable_review,
    inspect_table,
    save_config,
)
from migration_report_tool.version import __version__


class TestV08180ConfigurableValidationPath(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_configured_equipment_file_is_valid_even_when_legacy_schema_rejects_it(self):
        """The user's configured Key/Index + rules are authoritative for Equipment Review."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site_dir = root / "SITE"
            site_dir.mkdir()
            source = site_dir / "SE.xlsx"

            wb = Workbook()
            ws = wb.active
            ws.title = "Sheet1"
            # This mirrors the field family in the reported popup.  It is valid
            # for the generic configured engine because DE_NAME is explicitly
            # selected as the key, but the historical fixed SE schema does not
            # accept DE_NAME as its required Equipment Name field.
            ws.append(["GSS", "FEEDER", "DE_NAME", "DE_TYPE", "OR_SAMRT", "IF_NOP"])
            ws.append(["S1", "F1", "D1", "T1", "SMART", ""])
            ws.append(["S1", "F2", "D2", "T2", "NORMAL", ""])
            wb.save(source)
            wb.close()

            structure = inspect_table(source, sheet_name="Sheet1", header_row=1)
            ids = {column.header: column.id for column in structure.columns}
            store = ProjectStore(root / "project")
            try:
                save_config(
                    store,
                    {
                        "sources": [{
                            "id": "src_se",
                            "title": "SE",
                            "path": str(source),
                            "path_mode": "absolute",
                            "sheet_name": "Sheet1",
                            "header_row": 1,
                            "key_column": ids["DE_NAME"],
                            "hidden_columns": [],
                        }],
                        "comparisons": [
                            {"id": "cmp_feeder", "title": "FEEDER", "bindings": {"src_se": ids["FEEDER"]}},
                            {"id": "cmp_type", "title": "TYPE", "bindings": {"src_se": ids["DE_TYPE"]}},
                        ],
                    },
                    "tester",
                )

                rows, summary = build_configurable_review(store)
                self.assertEqual(summary["source_count"], 1)
                self.assertEqual([row["rmu"] for row in rows], ["D1", "D2"])
                self.assertTrue(all(row[analysis_column_key("cmp_feeder")] == "TRUE" for row in rows))
                self.assertTrue(all(row[analysis_column_key("cmp_type")] == "TRUE" for row in rows))

                # This is the obsolete gate that Run Validation used before
                # v0.8.182. Prove that the same table is rejected there, which
                # is why configured mode must bypass this legacy import path.
                site = SiteInfo("SITE", site_dir, {"se_list": source}, {}, ())
                with self.assertRaises(SchemaValidationError):
                    sync_site_to_project(store, site, force_all=True)
            finally:
                store.close()

    def test_run_validation_branches_before_legacy_force_all_sync(self):
        main_window = Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py"
        text = main_window.read_text(encoding="utf-8")
        start = text.index("def _background_validation_job(")
        end = text.index("def _background_reload_live_sources_job(", start)
        block = text[start:end]

        self.assertIn('configurable_mode = bool(configurable.get("sources"))', block)
        self.assertIn('if configurable_mode:', block)
        self.assertIn('sync = None', block)
        self.assertIn('sync = sync_site_to_project(store, site, force_all=True)', block)
        self.assertLess(block.index('if configurable_mode:'), block.index('sync = sync_site_to_project(store, site, force_all=True)'))
        self.assertIn('_worker_effective_source_path(site, store, "ioa")', block)
        self.assertIn('_worker_effective_source_path(site, store, "adms_sld")', block)

    def test_validation_summary_uses_configured_rule_labels(self):
        main_window = Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py"
        text = main_window.read_text(encoding="utf-8")
        self.assertIn('"issue_field_labels": issue_field_labels', text)
        self.assertIn('"issue_field_order": issue_field_order', text)
        self.assertIn('issue_labels.get(field_id) or field_id', text)


if __name__ == "__main__":
    unittest.main()
