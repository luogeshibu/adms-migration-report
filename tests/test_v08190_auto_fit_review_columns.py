import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py"
I18N = ROOT / "src" / "migration_report_tool" / "ui" / "i18n.py"
VERSION = ROOT / "src" / "migration_report_tool" / "version.py"


class AutoFitReviewColumnTests(unittest.TestCase):
    def test_version_bumped_to_08190(self):
        self.assertIn('__version__ = "0.8.215"', VERSION.read_text(encoding="utf-8"))

    def test_finish_render_runs_content_aware_auto_fit(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn("def _auto_fit_comparison_columns(", source)
        self.assertIn('rows=list(ctx.get("rows") or [])', source)
        self.assertIn('shown=list(ctx.get("shown") or [])', source)
        self.assertIn("self._comparison_auto_width_for_column(", source)

    def test_manual_widths_still_win_and_auto_fit_is_bounded(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn("if key in self.comparison_column_widths:", source)
        self.assertIn("maximum = 520", source)
        self.assertIn("self._comparison_width_sample(source_records, 180)", source)
        self.assertIn("longest_record = max(", source)

    def test_double_click_resets_one_column_to_auto_fit(self):
        source = UI.read_text(encoding="utf-8")
        self.assertIn("sectionDoubleClicked.connect(self._auto_fit_comparison_section)", source)
        self.assertIn("self.comparison_column_widths.pop(key, None)", source)
        self.assertIn("self._auto_fit_comparison_columns(only_keys={key})", source)

    def test_chinese_resize_guidance_exists(self):
        source = I18N.read_text(encoding="utf-8")
        self.assertIn('"Column width fitted to current content": "列宽已按当前内容自动适配"', source)
        self.assertIn("双击表头可按内容自动适配", source)


if __name__ == "__main__":
    unittest.main()
