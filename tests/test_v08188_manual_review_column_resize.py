import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py"
VERSION = ROOT / "src" / "migration_report_tool" / "version.py"


class ManualReviewColumnResizeTests(unittest.TestCase):
    def test_version_bumped_to_08188(self):
        self.assertIn('__version__ = "0.8.196"', VERSION.read_text(encoding="utf-8"))

    def test_equipment_review_main_grid_columns_are_user_resizable(self):
        source = UI.read_text(encoding="utf-8")
        marker = "self.comparison_table.horizontalHeader().setDefaultAlignment"
        start = source.index(marker)
        window = source[start:start + 1800]
        self.assertIn("setSectionResizeMode(QHeaderView.Interactive)", window)
        self.assertIn("sectionResized.connect(self._on_comparison_column_resized)", window)
        self.assertNotIn("setSectionResizeMode(QHeaderView.Fixed)", window)

    def test_manual_widths_are_persisted_by_stable_column_key_and_reapplied(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn('comparison/column_widths_json', source)
        self.assertIn("self._comparison_column_keys = [key for key, _label, _width in columns]", source)
        self.assertIn("target_width = self.comparison_column_widths.get(key, initial_width)", source)
        self.assertIn("self.comparison_column_widths[key] = max(55, min(2400, int(new_size)))", source)
        self.assertIn("self._comparison_width_save_timer.start()", source)

    def test_visibility_changes_do_not_replace_saved_width_with_zero(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn("if int(new_size) < 55:", source)


if __name__ == "__main__":
    unittest.main()
