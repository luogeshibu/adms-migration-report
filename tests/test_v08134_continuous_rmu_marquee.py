from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
STORE = (ROOT / "src/migration_report_tool/infrastructure/database/sqlite_store.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


class ContinuousRmuMarqueeTests(unittest.TestCase):
    def test_release_version(self):
        self.assertIn('__version__ = "0.8.143"', VERSION)

    def test_busy_bar_is_fixed_width_marquee(self):
        self.assertIn("class BusyMarqueeProgressBar(QProgressBar):", UI)
        self.assertIn("self._marquee_timer.setInterval(16)", UI)
        self.assertIn("chunk_width = max(38, int(track.width() * 0.24))", UI)
        self.assertIn("travel * (self._marquee_position / 100.0)", UI)
        self.assertIn("self.progress = BusyMarqueeProgressBar()", UI)

    def test_cached_rmu_preparation_runs_in_process(self):
        self.assertIn('"rmu-render-prepare": _background_rmu_render_prepare_job', UI)
        self.assertIn('def _background_rmu_render_prepare_job(', UI)
        refresh = UI[UI.index("    def refresh_comparison(self):"):UI.index("    def _render_comparison_batch", UI.index("    def refresh_comparison(self):"))]
        self.assertNotIn("self.store.rows()", refresh)
        self.assertIn('"rmu-render-prepare"', refresh)

    def test_navigation_does_not_decode_all_rows_to_check_emptiness(self):
        self.assertIn("self.store.comparison_row_count() == 0", UI)
        self.assertIn("def comparison_row_count(self) -> int:", STORE)
        self.assertIn('SELECT COUNT(*) FROM comparison', STORE)

    def test_rmu_paint_yields_every_row(self):
        self.assertIn("self._comparison_render_batch_size = 1", UI)
        self.assertIn("QTimer.singleShot(0, lambda g=generation: self._render_comparison_batch(g))", UI)


if __name__ == "__main__":
    unittest.main()
