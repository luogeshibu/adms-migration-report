from pathlib import Path
import unittest

from migration_report_tool.config.sources import schema_for
from migration_report_tool.domain.schema import MappingKind, resolve_schema


class V08138AutoNoMatchStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
        cls.version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")

    def test_version(self):
        self.assertIn('__version__ = "0.8.215"', self.version)

    def test_unresolved_auto_is_explicit_in_ui(self):
        self.assertIn('else "Auto · No match"', self.ui)
        self.assertIn('The App value will remain blank', self.ui)

    def test_missing_mapping_explains_expected_aliases(self):
        # ADMS SLD FEEDER is intentionally absent from this sample header set.
        result = resolve_schema(schema_for("adms_sld"), ["环网柜名称", "环网柜类型", "是否智能"])
        mapping = result.mapping_by_key["feeder"]
        self.assertEqual(mapping.kind, MappingKind.MISSING)
        self.assertIsNone(mapping.actual_column)
        self.assertIn("Automatic mapping found no matching Source Field", mapping.message)
        self.assertIn("remain blank", mapping.message)

    def test_auto_no_match_keeps_auto_mode_data_empty(self):
        # The combo label may say No match, but its stored item data must remain
        # the empty string so Save continues to mean Auto, not Manual/Blank.
        self.assertIn('combo.addItem(auto_label, "")', self.ui)


if __name__ == "__main__":
    unittest.main()
