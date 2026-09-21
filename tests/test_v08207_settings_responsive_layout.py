from pathlib import Path
import unittest


class SettingsResponsiveLayoutTests(unittest.TestCase):
    def test_settings_page_uses_responsive_vertical_scroll(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('self.settings_scroll = scroll', source)
        self.assertIn('scroll.setWidgetResizable(True)', source)
        self.assertIn('scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)', source)

    def test_release_version_is_08207(self):
        root = Path(__file__).resolve().parents[1]
        version = (root / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.8.215"', version)
