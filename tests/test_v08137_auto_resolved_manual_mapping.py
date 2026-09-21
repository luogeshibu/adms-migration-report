from pathlib import Path
import unittest

from migration_report_tool.config.sources import schema_for
from migration_report_tool.domain.schema import (
    BLANK_OVERRIDE_TOKEN,
    MappingKind,
    decode_manual_override,
    encode_manual_override,
    is_manual_override,
    resolve_schema,
)


class V08137AutoResolvedManualMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.ui = (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
        cls.version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")

    def test_version(self):
        self.assertIn('__version__ = "0.8.215"', self.version)

    def test_auto_label_shows_current_resolved_header_when_available(self):
        self.assertIn('auto_label = f"Auto → {auto_resolved}" if auto_resolved else "Auto · No match"', self.ui)
        self.assertIn('auto_resolved = source_header', self.ui)

    def test_auto_label_stays_plain_when_unresolved(self):
        self.assertIn('auto_label = f"Auto → {auto_resolved}" if auto_resolved else "Auto · No match"', self.ui)

    def test_deliberate_manual_mapping_beats_auto_alias(self):
        headers = ["RMU_NAME", "IP", "IP-BAK"]
        result = resolve_schema(
            schema_for("adms_db"), headers,
            {"channel_ip": encode_manual_override("IP-BAK")},
        )
        mapping = result.mapping_by_key["channel_ip"]
        self.assertEqual(mapping.kind, MappingKind.OVERRIDE)
        self.assertEqual(mapping.actual_column, "IP-BAK")

    def test_legacy_raw_override_remains_fallback_only(self):
        headers = ["RMU_NAME", "IP", "IP-BAK"]
        result = resolve_schema(
            schema_for("adms_db"), headers,
            {"channel_ip": "IP-BAK"},
        )
        mapping = result.mapping_by_key["channel_ip"]
        self.assertEqual(mapping.actual_column, "IP")
        self.assertIn("ignored", mapping.message.lower())

    def test_manual_token_round_trip(self):
        encoded = encode_manual_override("控制")
        self.assertTrue(is_manual_override(encoded))
        self.assertEqual(decode_manual_override(encoded), "控制")

    def test_blank_still_wins_over_auto_and_manual(self):
        result = resolve_schema(schema_for("se_list"), ["SS", "FEEDR", "EQUIPMENT"], {"station": BLANK_OVERRIDE_TOKEN})
        mapping = result.mapping_by_key["station"]
        self.assertEqual(mapping.kind, MappingKind.BLANK)
        self.assertIsNone(mapping.actual_column)

    def test_ui_saves_physical_header_as_explicit_manual_mode(self):
        self.assertIn('self.current_overrides[key] = encode_manual_override(value)', self.ui)
        self.assertIn('self.current_overrides.pop(key, None)', self.ui)
        self.assertIn('"Blank · no source field"', self.ui)

    def test_internal_manual_token_is_not_user_facing_in_mapping_summary_or_audit(self):
        root = Path(__file__).resolve().parents[1]
        schema_service = (root / "src/migration_report_tool/services/schema_service.py").read_text(encoding="utf-8")
        audit = (root / "src/migration_report_tool/services/audit_presentation.py").read_text(encoding="utf-8")
        self.assertIn("decode_manual_override(explicit)", schema_service)
        self.assertIn('return f"Manual → {actual}"', audit)



if __name__ == "__main__":
    unittest.main()
