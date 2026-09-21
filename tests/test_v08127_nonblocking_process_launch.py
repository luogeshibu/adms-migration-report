from pathlib import Path
import unittest


class V08127NonBlockingProcessLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.ui = (cls.root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        cls.version = (cls.root / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")

    def test_version(self):
        self.assertIn('__version__ = "0.8.215"', self.version)

    def test_process_spawn_is_launched_by_threadpool(self):
        block = self.ui[self.ui.index("def _start_process_background_task"):self.ui.index("def _reopen_active_store_after_worker")]
        self.assertIn("launcher = BackgroundTask(lambda: _launch_review_process", block)
        self.assertIn("self.thread_pool.start(launcher)", block)
        self.assertNotIn("\n        process.start()", block)

    def test_spawn_helper_starts_child_outside_gui_method(self):
        block = self.ui[self.ui.index("def _launch_review_process"):self.ui.index("def _background_process_job_entry")]
        self.assertIn('ctx = mp.get_context("spawn")', block)
        self.assertIn("process.start()", block)

    def test_queue_poll_is_bounded_to_preserve_repaints(self):
        block = self.ui[self.ui.index("def _start_process_background_task"):self.ui.index("def _reopen_active_store_after_worker")]
        self.assertIn("for _ in range(8):", block)
        self.assertIn("progress_value=None", block)

    def test_busy_animation_is_fast_timer_driven(self):
        marquee = self.ui[self.ui.index("class BusyMarqueeProgressBar"):self.ui.index("class BusyOperationPopup")]
        self.assertIn("self._marquee_timer.setInterval(16)", marquee)
        self.assertIn("self._marquee_position += 2.8 * self._marquee_direction", marquee)

    def test_project_schema_unchanged(self):
        migrations = (self.root / "src" / "migration_report_tool" / "infrastructure" / "database" / "migrations.py").read_text(encoding="utf-8")
        self.assertIn("TARGET_SCHEMA_VERSION = 12", migrations)


if __name__ == "__main__":
    unittest.main()
