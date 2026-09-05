from pathlib import Path
import unittest


class V08133LivePulseAndRmuOnlyTypeWarningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.ui = (cls.root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        cls.version = (cls.root / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")

    def test_version(self):
        self.assertIn('__version__ = "0.8.143"', self.version)

    def test_busy_popup_never_switches_to_static_percentage_mode(self):
        block = self.ui[self.ui.index("def set_message(self, title:"):self.ui.index("def signal_review_row_hash")]
        self.assertIn("self.progress.start()", block)
        self.assertNotIn("self.progress.setValue(", block)
        self.assertNotIn("self.progress.setFormat", block)

    def test_rmu_gui_render_yields_frequently_to_animation_timer(self):
        self.assertIn("self._comparison_render_batch_size = 1", self.ui)
        render_block = self.ui[self.ui.index("def _render_comparison_batch"):self.ui.index("def _finish_comparison_render")]
        self.assertIn("QTimer.singleShot(0", render_block)

    def test_signal_type_warning_only_colors_rmu_locator_cell_purple(self):
        block = self.ui[self.ui.index("def _render_db_smart_rmu_list"):self.ui.index("def _show_db_smart_rmu_overview")]
        self.assertIn('if col == 0:', block)
        self.assertIn('if has_type_issue:', block)
        self.assertIn('cell.setBackground(QColor("#F3E8FF"))', block)
        self.assertIn('cell.setForeground(QColor("#6D28D9"))', block)
        self.assertNotIn('render the complete RMU summary row', block)
        # Row background is selected from workflow state before the RMU-only override.
        self.assertIn('if has_need_action:', block)
        self.assertIn('elif has_unreviewed:', block)

    def test_project_schema_is_still_v10(self):
        migrations = (self.root / "src" / "migration_report_tool" / "infrastructure" / "database" / "migrations.py").read_text(encoding="utf-8")
        self.assertIn("TARGET_SCHEMA_VERSION = 11", migrations)


if __name__ == "__main__":
    unittest.main()
