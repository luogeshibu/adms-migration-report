from __future__ import annotations

import unittest
from pathlib import Path

from migration_report_tool.version import __version__

ROOT = Path(__file__).parents[1]
UI = (ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")


class TestV08196ReviewInteractionPerformance(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_filters_are_local_not_full_refresh(self):
        build_start = UI.index("def _build_comparison_page")
        build_end = UI.index("def _build_changes_page", build_start)
        block = UI[build_start:build_end]
        self.assertIn("self._comparison_search_timer.timeout.connect(self._apply_comparison_filters_local)", block)
        self.assertIn("self.rmu_review_filter_combo.currentIndexChanged.connect(self._apply_comparison_filters_local)", block)
        self.assertIn("self.analysis_combo.currentIndexChanged.connect(self._apply_comparison_filters_local)", block)
        self.assertNotIn("self.rmu_review_filter_combo.currentIndexChanged.connect(self.refresh_comparison)", block)

    def test_refresh_builds_unfiltered_canonical_dataset(self):
        start = UI.index("def refresh_comparison(self)")
        end = UI.index("def _render_comparison_batch", start)
        block = UI[start:end]
        self.assertIn('term = ""', block)
        self.assertIn('review_filter = "ALL REVIEWS"', block)
        self.assertIn('analysis_filter = "ALL ANALYSIS"', block)
        self.assertIn("self._comparison_row_cache", block)
        self.assertIn("self._comparison_entry_cache", block)

    def test_row_lookup_hits_memory_before_source_rebuild(self):
        start = UI.index("def _comparison_row_by_rmu")
        end = UI.index("@staticmethod\n    def _equipment_display_name", start)
        block = UI[start:end]
        self.assertLess(block.index("_comparison_row_cache"), block.index("build_equipment_source_view"))

    def test_show_all_does_not_rebuild_dataset(self):
        start = UI.index("def _show_all_comparison")
        end = UI.index("def _sync_comparison_selection_from_locator", start)
        block = UI[start:end]
        self.assertIn("self._apply_comparison_filters_local()", block)
        self.assertNotIn("self.refresh_comparison()", block)

    def test_status_write_is_optimistic_and_background(self):
        start = UI.index("def set_comparison_review_status")
        end = UI.index("def edit_comparison_cell", start)
        block = UI[start:end]
        self.assertIn("self._patch_cached_review_status", block)
        self.assertIn("_background_review_status_batch_job", block)
        self.assertNotIn("self.store.update_rmu_review_status(", block)

    def test_summary_uses_cached_review_map(self):
        start = UI.index("def _refresh_comparison_summary_only")
        end = UI.index("def open_rmu_resolution_dialog", start)
        block = UI[start:end]
        self.assertIn("_comparison_review_map_cache", block)
        self.assertNotIn("self.store.rmu_review_map()", block)

    def test_lifecycle_skips_untracked_rows(self):
        start = UI.index("def refresh_selected_rmu_lifecycle")
        end = UI.index("def _open_selected_rmu_lifecycle", start)
        block = UI[start:end]
        self.assertIn("_comparison_action_tracking_keys", block)
        self.assertLess(block.index("if rmu not in tracked_keys"), block.index("equipment_full_lifecycle"))


if __name__ == "__main__":
    unittest.main()
