from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.version import __version__


ROOT = Path(__file__).parents[1]
UI = (ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
DB = (ROOT / "src" / "migration_report_tool" / "infrastructure" / "database" / "sqlite_store.py").read_text(encoding="utf-8")


class TestV08193ReviewCheckPerformance(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_equipment_check_does_not_sync_refresh_heavy_pages(self):
        start = UI.index("def _on_comparison_locator_check_passed_toggled")
        end = UI.index("def _clear_comparison_selection", start)
        block = UI[start:end]
        self.assertNotIn("self.refresh_changes()", block)
        self.assertNotIn("self.refresh_site_history()", block)
        self.assertNotIn("self.refresh_export_page()", block)
        self.assertNotIn("self._refresh_comparison_summary_only()", block)
        self.assertIn("self._dirty_pages.update({0, 4, 6, 7})", block)

    def test_signal_check_uses_same_lazy_refresh_policy(self):
        start = UI.index("def _on_db_smart_locator_check_passed_toggled")
        end = UI.index("def _clear_db_smart_selection", start)
        block = UI[start:end]
        self.assertNotIn("self.refresh_changes()", block)
        self.assertNotIn("self.refresh_site_history()", block)
        self.assertNotIn("self.refresh_export_page()", block)
        self.assertIn("self._dirty_pages.update({0, 4, 6, 7})", block)

    def test_plain_check_does_not_build_lifecycle_snapshot_without_case(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "project")
            try:
                # A normal verification row with no Needs Action history must
                # not pay the cost of building a rich lifecycle snapshot.
                def should_not_run(*_args, **_kwargs):
                    raise AssertionError("snapshot should be lazy when no lifecycle exists")

                store._rmu_issue_snapshot = should_not_run  # type: ignore[method-assign]
                store.update_rmu_check_passed("EQ::LBS::LBS-001", True, "tester")
                record = store.rmu_review_record("EQ::LBS::LBS-001")
                self.assertEqual(int(record["check_passed"]), 1)
            finally:
                store.close()

    def test_check_audit_is_still_persisted(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "project")
            try:
                store.update_rmu_check_passed("EQ::REC::REC-001", True, "tester")
                audit = [row for row in store.changes() if row["field_name"] == "rmu_check_passed"]
                self.assertEqual(len(audit), 1)
                self.assertEqual(audit[0]["new_value"], "PASS")
            finally:
                store.close()

    def test_database_uses_lazy_historical_case_gate(self):
        self.assertIn('historical_case = self._issue_case_row("RMU", rmu, open_only=False)', DB)
        self.assertIn("if historical_case is not None:", DB)


if __name__ == "__main__":
    unittest.main()
