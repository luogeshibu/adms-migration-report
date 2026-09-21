import unittest

from migration_report_tool.config.sources import schema_for
from migration_report_tool.services.schema_service import canonical_system_field_label
from migration_report_tool.version import __version__


class V08176EquipmentIdentitySemanticTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_equipment_sources_use_equipment_name_for_legacy_rmu_key(self):
        for source_type in ("se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"):
            schema = schema_for(source_type)
            spec = next(field for field in schema.fields if field.key == "rmu")
            self.assertEqual(spec.label, "Equipment Name", source_type)
            self.assertEqual(
                canonical_system_field_label(source_type, "rmu", "RMU"),
                "Equipment Name",
                source_type,
            )

    def test_legacy_rmu_source_header_remains_supported(self):
        for source_type in ("se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"):
            schema = schema_for(source_type)
            spec = next(field for field in schema.fields if field.key == "rmu")
            self.assertIn("RMU", spec.aliases, source_type)


if __name__ == "__main__":
    unittest.main()
