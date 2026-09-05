import unittest
from pathlib import Path


class V08131MapFieldsSaveProgressContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
        cls.version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")

    def test_release_version(self):
        self.assertIn('__version__ = "0.8.143"', self.version)

    def test_dialog_save_uses_cached_header_instead_of_full_file_reread(self):
        start = self.ui.index("    def _save(self):", self.ui.index("class SourceMappingDialog"))
        end = self.ui.index("class DerivedTableBuilderDialog", start)
        save_body = self.ui[start:end]
        self.assertIn("resolve_schema(self.schema, self.validation.headers, overrides)", save_body)
        self.assertNotIn("validate_source_file(self.source_type, self.source_path, overrides)", save_body)
        self.assertIn('self._set_save_state(True, "Saving field mapping settings... Please wait.")', save_body)

    def test_post_save_refresh_is_spawned_and_animated(self):
        self.assertIn('"mapping-refresh": _background_mapping_refresh_job', self.ui)
        self.assertIn('self._apply_saved_source_mapping_async(source_type, ref.label)', self.ui)
        self.assertIn('"mapping-save", task_label, "mapping-refresh"', self.ui)
        self.assertIn('progress_value=None', self.ui)

    def test_mapping_save_blocks_competing_source_pipeline_actions(self):
        busy_start = self.ui.index("    def _source_pipeline_busy(self)")
        busy_end = self.ui.index("    def _set_work_progress", busy_start)
        self.assertIn('"mapping-save"', self.ui[busy_start:busy_end])


if __name__ == "__main__":
    unittest.main()
