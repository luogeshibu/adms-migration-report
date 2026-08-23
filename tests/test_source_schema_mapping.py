from pathlib import Path
import tempfile
import unittest

from migration_report_tool.config.sources import schema_for
from migration_report_tool.domain.schema import MappingKind, SchemaValidationError, resolve_schema
from migration_report_tool.infrastructure.parsers import read_mapped_rows


class SourceSchemaMappingTests(unittest.TestCase):
    def test_zenon_db_current_headers_map_to_canonical_fields(self):
        headers = [
            "RMU","FEEDER","BRAND","DEVICE","NOP","SMART","VIP","Function Location",
            "PRIMARY_IP","PRIMARY_PORT","LINK_ADDRESS","LINK_ADDRESS_SIZE","COT_SIZE",
            "COA_SIZE","IOA_SIZE","T1","T2","T3","K_VALUE","W_VALUE","NET_ADDRESS",
        ]
        result = resolve_schema(schema_for("zenon_db"), headers)
        self.assertFalse(result.errors)
        self.assertEqual(result.mapped_column("rmu_type"), "DEVICE")
        self.assertEqual(result.mapped_column("ip"), "PRIMARY_IP")
        self.assertEqual(result.mapped_column("port"), "PRIMARY_PORT")

    def test_missing_required_column_is_error_not_silent_blank(self):
        result = resolve_schema(schema_for("zenon_db"), ["FEEDER", "DEVICE", "PRIMARY_IP"])
        self.assertTrue(result.errors)
        self.assertIn("RMU", result.error_message("ZENON-DB.csv"))

    def test_adms_db_does_not_define_smart_field(self):
        schema = schema_for("adms_db")
        keys = [field.key for field in schema.fields]
        self.assertNotIn("smart", keys)
        result = resolve_schema(schema, [
            "RMU_NAME", "ADMS_GSS-FID", "TYPE", "NET_DESCRIPTION1", "port",
            "Y1", "Y2", "Y3", "Y4", "Q1", "Q2",
        ])
        self.assertFalse(result.errors)
        self.assertFalse(result.warnings)

    def test_adms_db_smart_column_is_not_consumed_even_if_present(self):
        schema = schema_for("adms_db")
        result = resolve_schema(schema, ["RMU_NAME", "SMART"])
        self.assertNotIn("smart", result.mapping_by_key)
        self.assertIn("SMART", result.ignored_columns)

    def test_alias_priority_is_explicit_and_deterministic(self):
        result = resolve_schema(schema_for("adms_sld"), ["环网柜名称", "环网柜类型", "智能标识", "是否智能", "RMU可关联", "环网柜ID"])
        self.assertFalse(result.errors)
        self.assertEqual(result.mapped_column("smart"), "智能标识")
        self.assertEqual(result.mapped_column("link"), "RMU可关联")

    def test_site_override_can_map_confirmed_alternate_header(self):
        result = resolve_schema(schema_for("zenon_db"), ["RMU", "CABINET_MODEL"], {"rmu_type": "CABINET_MODEL"})
        self.assertFalse(result.errors)
        mapping = result.mapping_by_key["rmu_type"]
        self.assertEqual(mapping.actual_column, "CABINET_MODEL")
        self.assertEqual(mapping.kind, MappingKind.OVERRIDE)

    def test_csv_rows_are_returned_with_canonical_keys(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ZENON-DB.csv"
            path.write_text("RMU,DEVICE,PRIMARY_IP,PRIMARY_PORT\n26859,2L1T,172.20.46.228,2404\n", encoding="utf-8")
            mapped = read_mapped_rows("zenon_db", path)
            row = mapped.rows[0]
            self.assertEqual(row["rmu"], "26859")
            self.assertEqual(row["rmu_type"], "2L1T")
            self.assertEqual(row["ip"], "172.20.46.228")
            self.assertEqual(row["port"], "2404")

    def test_se_schema_matches_business_fields_without_duplicate_device_mapping(self):
        schema = schema_for("se_list")
        keys = [field.key for field in schema.fields]
        self.assertEqual(keys, ["station", "feeder", "rmu", "smart", "oh_ug", "rmu_type"])
        self.assertNotIn("device", keys)
        result = resolve_schema(schema, ["SS", "FEEDR", "EQUIPMENT", "EQUIP. TYPE", "OH / UG"])
        self.assertFalse(result.errors)
        self.assertEqual(result.mapped_column("smart"), "EQUIP. TYPE")
        self.assertIsNone(result.mapped_column("rmu_type"))

    def test_bundled_standard_reference_has_required_named_columns(self):
        from migration_report_tool.paths import resource_root
        path = resource_root() / "templates" / "IOA STANDARD.xlsx"
        mapped = read_mapped_rows("standard_reference", path)
        self.assertTrue(mapped.rows)
        self.assertEqual(mapped.validation.mapped_column("type"), "Type")
        self.assertEqual(mapped.validation.mapped_column("ioa"), "IOA")
        self.assertEqual(mapped.validation.mapped_column("name"), "name")


if __name__ == "__main__":
    unittest.main()
