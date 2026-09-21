import tempfile
import unittest
from pathlib import Path

from migration_report_tool.storage import ProjectStore


ROOT = Path(__file__).parents[1]
MAIN = (ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
STORE = (ROOT / "src" / "migration_report_tool" / "infrastructure" / "database" / "sqlite_store.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")


def function_block(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}(")
    end = source.index(f"    def {next_name}(", start)
    return source[start:end]


class ReviewSaveResponsivenessTests(unittest.TestCase):
    def test_version(self):
        self.assertIn('__version__ = "0.8.215"', VERSION)

    def test_item_picker_uses_save_cancel_labels(self):
        block = MAIN[MAIN.index("class QInputDialog"):MAIN.index("class I18nStatusBar")]
        self.assertIn('dialog.setOkButtonText(ui_tr("Save", current_language()))', block)
        self.assertIn('dialog.setCancelButtonText(ui_tr("Cancel", current_language()))', block)
        self.assertNotIn('return _QtInputDialog.getItem(', block)

    def test_equipment_hot_paths_do_not_rebuild_site_history(self):
        resolution = function_block(MAIN, "open_rmu_resolution_dialog", "edit_rmu_manual_review_comment")
        comment = function_block(MAIN, "edit_rmu_manual_review_comment", "set_comparison_review_status")
        status = function_block(MAIN, "set_comparison_review_status", "edit_comparison_cell")
        self.assertNotIn("self.refresh_site_history()", resolution)
        self.assertNotIn("self.refresh_site_history()", comment)
        self.assertNotIn("self.refresh_site_history()", status)
        self.assertIn("self._dirty_pages.update({0, 4, 5, 6, 7})", resolution)
        self.assertIn("self._dirty_pages.update({0, 4, 5, 6, 7})", comment)
        self.assertIn("self._dirty_pages.update({0, 4, 5, 6, 7})", status)

    def test_manual_comment_does_not_recalculate_unrelated_counters(self):
        comment = function_block(MAIN, "edit_rmu_manual_review_comment", "set_comparison_review_status")
        self.assertIn("self.store.append_rmu_manual_review_comment(", comment)
        self.assertIn("_refresh_comparison_resolution_row(rmu, refresh_progress=False)", comment)
        self.assertNotIn("_refresh_comparison_summary_only()", comment)
        self.assertNotIn("_refresh_comparison_resolution_progress_only()", comment)

    def test_single_equipment_lookup_exists_and_snapshot_uses_it(self):
        self.assertIn("def rmu_review_record(self, rmu: str) -> dict:", STORE)
        self.assertIn("review = self.rmu_review_record(rmu)", STORE)
        repaint = function_block(MAIN, "_refresh_comparison_resolution_row", "_refresh_comparison_summary_only")
        self.assertIn("self.store.rmu_review_record(rmu)", repaint)

    def test_append_comment_still_persists_latest_and_history(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                store.append_rmu_manual_review_comment("H22-0274", "first comment", "alice")
                store.append_rmu_manual_review_comment("H22-0274", "second comment", "bob")
                self.assertEqual(store.rmu_manual_review_comment("H22-0274"), "second comment")
                events = [e for e in store.rmu_review_events("H22-0274") if e["event_type"] == "COMMENT_RECORDED"]
                self.assertEqual([e["comment"] for e in events], ["first comment", "second comment"])
                self.assertEqual(store.rmu_review_record("H22-0274")["manual_comment"], "second comment")
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
