from pathlib import Path
import unittest

from migration_report_tool.config.sources import schema_for
from migration_report_tool.domain.schema import MappingKind, encode_manual_override, resolve_schema
from migration_report_tool.version import __version__


class V08174UnlockNonstandardSystemMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")

    def test_release_version(self):
        self.assertEqual(__version__, "0.8.196")

    def test_nonstandard_se_equipment_name_can_be_explicitly_bound(self):
        headers = [
            "GSS", "FEEDER", "DE_NAME", "DE_TYPE", "OR_SAMRT", "IF_NOP",
            "WORKLOCATION", "EQ_TYPE", "MANUFACTURER", "IP", "TYPE", "OFFICE", "AREA",
        ]
        baseline = resolve_schema(schema_for("se_list"), headers, {})
        self.assertTrue(baseline.errors)
        self.assertEqual(baseline.mapping_by_key["rmu"].kind, MappingKind.MISSING)

        fixed = resolve_schema(
            schema_for("se_list"),
            headers,
            {
                "rmu": encode_manual_override("DE_NAME"),
                "device_type": encode_manual_override("DE_TYPE"),
                "smart": encode_manual_override("OR_SAMRT"),
                "rmu_type": encode_manual_override("EQ_TYPE"),
            },
        )
        self.assertFalse(fixed.errors)
        self.assertEqual(fixed.mapping_by_key["rmu"].actual_column, "DE_NAME")
        self.assertEqual(fixed.mapping_by_key["device_type"].actual_column, "DE_TYPE")
        self.assertEqual(fixed.mapping_by_key["smart"].actual_column, "OR_SAMRT")
        self.assertEqual(fixed.mapping_by_key["rmu_type"].actual_column, "EQ_TYPE")

    def test_unlock_opens_real_system_assignment_editor_and_stays_reusable(self):
        self.assertIn("class SystemMappingEditorDialog", self.ui)
        self.assertIn("def _edit_system_mappings(self):", self.ui)
        self.assertIn('self.unlock_system_btn.setText("Edit System Mappings...")', self.ui)
        self.assertIn("self.unlock_system_btn.setEnabled(True)", self.ui)
        self.assertIn("self._edit_system_mappings()", self.ui)
        self.assertNotIn('self.unlock_system_btn.setEnabled(False)', self.ui)

    def test_missing_required_system_mapping_is_not_a_phantom_main_row(self):
        self.assertIn("one physical source column equals one App row", self.ui)
        self.assertIn("This does not add phantom source columns", self.ui)
        self.assertIn("A newly-bound required", self.ui)
        self.assertIn("one-source-column/one-App-row invariant remains", self.ui)

    def test_save_tracks_missing_to_manual_as_protected_change(self):
        self.assertIn("self._initial_locked_mapping_state", self.ui)
        self.assertIn("def _locked_mapping_state", self.ui)
        self.assertIn("current_state.get(key) != self._initial_locked_mapping_state.get(key)", self.ui)
        self.assertIn("self._capture_unsaved_state()\n        # v0.8.148", self.ui)


if __name__ == "__main__":
    unittest.main()
