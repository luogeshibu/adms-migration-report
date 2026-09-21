from pathlib import Path
import unittest


class V08126AnimatedProcessReviewLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.ui = (cls.root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        cls.app = (cls.root / "src" / "migration_report_tool" / "app" / "application.py").read_text(encoding="utf-8")
        cls.version = (cls.root / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")

    def test_version(self):
        self.assertIn('__version__ = "0.8.215"', self.version)

    def test_busy_popup_has_explicit_ping_pong_timer(self):
        marquee = self.ui[self.ui.index("class BusyMarqueeProgressBar"):self.ui.index("class BusyOperationPopup")]
        popup = self.ui[self.ui.index("class BusyOperationPopup"):self.ui.index("def signal_review_row_hash")]
        self.assertIn("self._marquee_timer = QTimer(self)", marquee)
        self.assertIn("self._marquee_timer.setInterval(16)", marquee)
        self.assertIn("self._marquee_position += 2.8 * self._marquee_direction", marquee)
        self.assertIn("self.progress = BusyMarqueeProgressBar()", popup)
        self.assertIn("self.progress.start()", popup)

    def test_first_open_review_jobs_use_spawned_processes(self):
        self.assertIn('ctx = mp.get_context("spawn")', self.ui)
        self.assertIn("target=_background_process_job_entry", self.ui)
        self.assertIn("launcher = BackgroundTask(lambda: _launch_review_process", self.ui)
        self.assertIn('"module-rmu-load": _background_rmu_review_module_job', self.ui)
        self.assertIn('"module-signal-load": _background_signal_mapping_module_job', self.ui)
        signal_block = self.ui[self.ui.index("def _start_signal_mapping_module_load"):self.ui.index("def _start_rmu_review_module_load")]
        rmu_block = self.ui[self.ui.index("def _start_rmu_review_module_load"):self.ui.index("def _setup_state")]
        self.assertIn("self._start_process_background_task", signal_block)
        self.assertIn("self._start_process_background_task", rmu_block)

    def test_process_progress_keeps_bar_animated(self):
        block = self.ui[self.ui.index("def _start_process_background_task"):self.ui.index("def _reopen_active_store_after_worker")]
        self.assertIn("progress_value=None", block)
        self.assertIn('detail=f"{stage} · {value}% · working in background"', block)
        self.assertNotIn("process.join()", block)

    def test_frozen_launch_enables_multiprocessing_support(self):
        self.assertIn("multiprocessing.freeze_support()", self.app)
        main = (self.root / "main.py").read_text(encoding="utf-8")
        module_main = (self.root / "src" / "migration_report_tool" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("multiprocessing.freeze_support()", main)
        self.assertIn("multiprocessing.freeze_support()", module_main)

    def test_project_schema_is_not_changed_by_this_release(self):
        migrations = (self.root / "src" / "migration_report_tool" / "infrastructure" / "database" / "migrations.py").read_text(encoding="utf-8")
        self.assertIn("TARGET_SCHEMA_VERSION = 12", migrations)


if __name__ == "__main__":
    unittest.main()
