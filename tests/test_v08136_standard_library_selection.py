from pathlib import Path
import unittest

from migration_report_tool.domain.mapping.signal_mapping import build_signal_mapping_report


class V08136StandardLibrarySelectionTests(unittest.TestCase):
    def test_signal_report_input_paths_capture_current_physical_inputs(self):
        root = Path(__file__).resolve().parents[1]
        sample = root / "examples" / "sample-data"
        standard = root / "resources" / "templates" / "IOA STANDARD.xlsx"
        report = build_signal_mapping_report(
            sample / "ZENON-ADMS-IOA.csv",
            sample / "ADMS-SLD.csv",
            standard,
        )
        self.assertEqual(
            [p.name for p in report.input_paths],
            ["ZENON-ADMS-IOA.csv", "ADMS-SLD.csv", "IOA STANDARD.xlsx"],
        )

    def test_settings_ui_supports_multiple_uploads_manual_activation_and_overwrite_prompt(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("Upload STANDARD(s)...", text)
        self.assertIn("Use Selected", text)
        self.assertIn("getOpenFileNames", text)
        self.assertIn("STANDARD Already Exists", text)
        self.assertIn("Active STANDARD was not changed", text)
        self.assertIn("activate_selected_standard_reference", text)

    def test_release_version(self):
        root = Path(__file__).resolve().parents[1]
        version = (root / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.8.215"', version)


if __name__ == "__main__":
    unittest.main()
