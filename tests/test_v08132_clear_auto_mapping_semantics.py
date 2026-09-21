from pathlib import Path
import unittest


class ClearAutoMappingSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
        cls.version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")

    def test_version(self):
        self.assertIn('__version__ = "0.8.215"', self.version)

    def test_auto_option_is_stable_mode_with_visible_resolution(self):
        self.assertIn('auto_label = f"Auto → {auto_resolved}" if auto_resolved else "Auto · No match"', self.ui)
        self.assertIn('combo.addItem(auto_label, "")', self.ui)
        self.assertIn('Automatic mapping. Current resolved Source Field:', self.ui)

    def test_auto_resolution_is_explained_in_tooltip(self):
        self.assertIn('Automatic mapping. Current resolved Source Field:', self.ui)
        self.assertIn('# Auto is represented by no override at all.', self.ui)
        self.assertNotIn('auto_column=', self.ui)


if __name__ == "__main__":
    unittest.main()
