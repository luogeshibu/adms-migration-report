from pathlib import Path
import unittest


class BuildPipelineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_windows_setup_and_formal_build_are_the_only_script_entrypoints(self):
        self.assertTrue((self.root / "setup.bat").is_file())
        self.assertTrue((self.root / "build.ps1").is_file())
        for legacy in (
            "setup.ps1",
            "build.bat", "build_exe.bat", "build_release.bat", "release.bat",
            "install_windows.bat", "start_windows.bat", "start_debug.bat", "clean.bat",
            "requirements.txt", "requirements-build.txt", "requirements-build.lock.txt", "requirements-runtime.lock.txt",
            "scripts/build.ps1", "scripts/release.ps1",
        ):
            self.assertFalse((self.root / legacy).exists(), legacy)
        self.assertTrue((self.root / "requirements.lock.txt").is_file())
        templates = [p.name for p in (self.root / "resources" / "templates").iterdir() if p.is_file()]
        self.assertEqual(templates, ["IOA STANDARD.xlsx"])

    def test_setup_bat_owns_windows_environment_initialization(self):
        text = (self.root / "setup.bat").read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn("requirements.lock.txt", text)
        self.assertIn("-m venv", lowered)
        self.assertIn("-m pip install", lowered)
        self.assertIn("-e \"%root%\" --no-deps", lowered)
        self.assertIn("--recreate", lowered)
        self.assertIn("--verify", lowered)
        self.assertNotIn("setup.ps1", lowered)

    def test_build_validates_environment_but_never_installs_it(self):
        text = (self.root / "build.ps1").read_text(encoding="utf-8")
        self.assertIn("Run setup.bat first", text)
        self.assertIn("verify_locked_environment.py", text)
        self.assertIn("pip','check", text)
        self.assertNotIn("setup.ps1", text)
        self.assertNotIn("ForceRecreateVenv", text)
        self.assertNotIn("'-m','pip','install'", text)
        self.assertNotIn("-m', 'venv", text)

    def test_build_script_targets_release_not_dist(self):
        text = (self.root / "build.ps1").read_text(encoding="utf-8")
        self.assertIn("$ReleaseRoot = Join-Path $Root 'release'", text)
        self.assertIn("packaging\\tools\\package_release.py", text)
        self.assertNotIn("$DistDir", text)

    def test_build_script_runs_tests_and_packaged_self_test(self):
        text = (self.root / "build.ps1").read_text(encoding="utf-8")
        self.assertIn("'unittest','discover'", text)
        self.assertIn("--self-test", text)

    def test_build_python_wrapper_never_uses_reserved_args(self):
        text = (self.root / "build.ps1").read_text(encoding="utf-8")
        self.assertNotIn("[string[]]$Args", text)
        self.assertIn("[string[]]$PythonArgs", text)
        self.assertIn("refused to start Python without arguments", text)

    def test_sample_data_uses_current_abH_source_set(self):
        sample = self.root / "examples" / "sample-data"
        self.assertEqual(
            sorted(p.name for p in sample.iterdir() if p.is_file()),
            sorted(["SE.xlsx", "ZENON-DB.csv", "ZENON-SLD.csv", "ADMS-DB.csv", "ADMS-SLD.csv", "ZENON-ADMS-IOA.csv"]),
        )

    def test_source_mapping_combo_disables_mouse_wheel_changes(self):
        text = (self.root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("class NoWheelComboBox(QComboBox)", text)
        self.assertIn("def wheelEvent(self, event):", text)
        self.assertIn("event.ignore()", text)
        self.assertIn("combo = NoWheelComboBox()", text)

    def test_standard_reference_is_user_replaceable_but_not_a_site_source(self):
        ui = (self.root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        paths = (self.root / "src" / "migration_report_tool" / "utils" / "paths.py").read_text(encoding="utf-8")
        self.assertIn('QPushButton("Update STANDARD...")', ui)
        self.assertIn('Upload / Replace STANDARD...', ui)
        self.assertIn('def standard_override_path()', paths)
        self.assertIn('def standard_reference_path()', paths)

    def test_rmu_review_status_is_explicit_not_inferred_from_any_audit_change(self):
        text = (self.root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        store = (self.root / "src" / "migration_report_tool" / "infrastructure" / "database" / "sqlite_store.py").read_text(encoding="utf-8")
        self.assertIn('review_btn = QPushButton("Set Status")', text)
        self.assertIn('self.store.rmu_review_map()', text)
        self.assertIn('self.store.set_rmu_resolution(', text)
        self.assertIn('def sync_rmu_review_from_resolutions(', store)
        self.assertNotIn('self.update_rmu_review_status(', store[store.index('def sync_rmu_review_from_resolutions('):store.index('def _rmu_analysis_hash')])
        self.assertNotIn('change_rmus = {x["rmu"] for x in self.store.changes()', text)
        self.assertIn('self.rmu_review_filter_combo.addItems(["ALL REVIEWS", "UNREVIEWED", "CLOSED", "NEEDS ACTION"])', text)
        self.assertNotIn('self.status_combo.addItems(["ALL", "MATCHED", "WARNING", "FAILED"', text)

    def test_release_packages_svg_icons_and_qtsvg(self):
        spec = (self.root / "packaging" / "windows" / "MigrationReportTool.spec").read_text(encoding="utf-8")
        self.assertIn('(str(RES / "icons"), "icons")', spec)
        self.assertIn('"PySide6.QtSvg"', spec)
        icons = self.root / "resources" / "icons"
        for name in ("overview", "database", "rmu", "signal", "audit", "versions", "report", "settings"):
            self.assertTrue((icons / f"{name}.svg").is_file(), name)

    def test_setup_bat_preserves_python_launcher_and_selector(self):
        text = (self.root / "setup.bat").read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn('set "bootstrap_exe=', lowered)
        self.assertIn('set "bootstrap_selector=', lowered)
        self.assertIn('call :run_bootstrap -m venv', lowered)
        self.assertIn(':run_bootstrap', lowered)
        self.assertNotIn('call %bootstrap_py% -m venv', lowered)
        self.assertIn('bootstrap python executable is empty', lowered)


if __name__ == "__main__":
    unittest.main()
