import unittest
from pathlib import Path

from migration_report_tool.version import __version__


class V08177BuildTestIsolationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.build = (cls.root / "build.ps1").read_text(encoding="utf-8-sig")

    def test_release_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_regression_tests_use_isolated_global_and_project_data(self):
        self.assertIn("function Invoke-IsolatedRegressionTests", self.build)
        self.assertIn("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", self.build)
        self.assertIn("MIGRATION_REPORT_TOOL_PROJECT_DATA_ROOT", self.build)
        self.assertIn("$TestUserData", self.build)
        self.assertIn("$TestProjectData", self.build)
        self.assertIn("Invoke-IsolatedRegressionTests", self.build)

    def test_build_restores_operator_environment_after_tests(self):
        self.assertIn("$PreviousUserDataRoot", self.build)
        self.assertIn("$PreviousProjectDataRoot", self.build)
        self.assertIn("Remove-Item Env:MIGRATION_REPORT_TOOL_USER_DATA_ROOT", self.build)
        self.assertIn("Remove-Item Env:MIGRATION_REPORT_TOOL_PROJECT_DATA_ROOT", self.build)
        self.assertIn("finally", self.build)

    def test_regression_command_is_not_run_directly_against_operator_profile(self):
        direct = "Invoke-Python -Label '[3/10] Regression tests...'"
        self.assertNotIn(direct, self.build)
        self.assertIn("Regression tests (isolated)", self.build)


if __name__ == "__main__":
    unittest.main()
