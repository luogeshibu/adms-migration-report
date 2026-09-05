from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from migration_report_tool.config.sources import schema_for
from migration_report_tool.domain.schema import BLANK_OVERRIDE_TOKEN, MappingKind, resolve_schema
from migration_report_tool.infrastructure.parsers import read_mapped_rows
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.schema_service import module_field_mapping_lines, set_source_overrides


class V08129ExplicitBlankSystemMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]

    def test_version(self):
        version = (self.root / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")
        self.assertIn('__version__ = "0.8.143"', version)

    def test_explicit_blank_wins_over_existing_auto_header(self):
        result = resolve_schema(
            schema_for("zenon_sld"),
            ["RMU", "Feeder", "CabinetType", "SMART"],
            {"smart": BLANK_OVERRIDE_TOKEN},
        )
        mapping = result.mapping_by_key["smart"]
        self.assertEqual(mapping.kind, MappingKind.BLANK)
        self.assertIsNone(mapping.actual_column)
        self.assertFalse(result.errors)

    def test_explicit_blank_canonical_value_is_none(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ZENON-SLD.csv"
            path.write_text("RMU,Feeder,CabinetType,SMART\n10689,ABH-08,3L1T,SMART\n", encoding="utf-8")
            mapped = read_mapped_rows("zenon_sld", path, {"smart": BLANK_OVERRIDE_TOKEN}, strict=True)
            self.assertEqual(mapped.rows[0]["rmu"], "10689")
            self.assertIsNone(mapped.rows[0]["smart"])

    def test_required_field_can_be_explicitly_blank_without_forced_substitute(self):
        result = resolve_schema(
            schema_for("zenon_sld"),
            ["RMU", "Feeder"],
            {"rmu": BLANK_OVERRIDE_TOKEN},
        )
        self.assertEqual(result.mapping_by_key["rmu"].kind, MappingKind.BLANK)
        self.assertFalse(result.errors)

    def test_site_data_sources_hides_internal_blank_token(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "site")
            try:
                set_source_overrides(store, "zenon_sld", {"smart": BLANK_OVERRIDE_TOKEN}, "tester")
                lines = module_field_mapping_lines("rmu_review", "zenon_sld", store, validation=None)
                smart_lines = [line for line in lines if line.startswith("SMART ←")]
                self.assertEqual(smart_lines, ["SMART ← —"])
                self.assertNotIn(BLANK_OVERRIDE_TOKEN, "\n".join(lines))
            finally:
                store.close()

    def test_ui_contains_blank_option(self):
        source = (self.root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn('combo.addItem("Blank · no source field", BLANK_OVERRIDE_TOKEN)', source)

    def test_project_schema_unchanged(self):
        migrations = (self.root / "src" / "migration_report_tool" / "infrastructure" / "database" / "migrations.py").read_text(encoding="utf-8")
        self.assertIn("TARGET_SCHEMA_VERSION = 11", migrations)


if __name__ == "__main__":
    unittest.main()
