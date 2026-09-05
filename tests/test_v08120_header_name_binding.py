from pathlib import Path
import csv
import tempfile
import unittest

from migration_report_tool.config.sources import SOURCE_SCHEMAS, schema_for
from migration_report_tool.domain.schema import MappingKind, resolve_schema
from migration_report_tool.infrastructure.parsers import read_mapped_rows


class HeaderNameBindingV08120Tests(unittest.TestCase):
    def test_adms_ip_prefers_explicit_ip_header_over_legacy_fallback(self):
        headers = [
            "RMU_NAME", "ADMS_GSS-FID", "NET_DESCRIPTION1", "Y1", "Y2", "Y3",
            "Y4", "Q1", "Q2", "TYPE", "IP-BAK", "PORT", "Voltage", "IP",
        ]
        result = resolve_schema(schema_for("adms_db"), headers)
        self.assertFalse(result.errors)
        self.assertEqual(result.mapped_column("channel_ip"), "IP")
        self.assertEqual(result.mapped_column("channel_port"), "PORT")
        self.assertIn("IP-BAK", result.ignored_columns)

    def test_adms_ip_falls_back_to_legacy_header_when_ip_is_absent(self):
        headers = ["RMU_NAME", "ADMS_GSS-FID", "NET_DESCRIPTION1", "PORT"]
        result = resolve_schema(schema_for("adms_db"), headers)
        self.assertFalse(result.errors)
        self.assertEqual(result.mapped_column("channel_ip"), "NET_DESCRIPTION1")

    def test_reordering_or_inserting_adms_columns_never_changes_values(self):
        first = [
            "RMU_NAME", "ADMS_GSS-FID", "Y1", "Y2", "Y3", "Y4", "Q1", "Q2",
            "TYPE", "SMART", "IP", "PORT", "Voltage",
        ]
        second = [
            "Voltage", "IP-BAK", "Q2", "RMU_NAME", "TYPE", "PORT", "Y4",
            "ADMS_GSS-FID", "SMART", "Q1", "Y3", "EXTRA NEW COLUMN", "IP", "Y1", "Y2",
        ]
        values = {
            "RMU_NAME": "10689", "ADMS_GSS-FID": "JED-NTH-ABH-AH308",
            "Y1": "1", "Y2": "1", "Y3": "1", "Y4": "0", "Q1": "1", "Q2": "0",
            "TYPE": "3L1T", "SMART": "SMART", "IP": "172.20.53.132", "PORT": "2404",
            "Voltage": "2404", "IP-BAK": "10689", "EXTRA NEW COLUMN": "anything",
        }
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for idx, headers in enumerate((first, second), 1):
                path = Path(td) / f"ADMS-DB-{idx}.csv"
                with path.open("w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=headers)
                    writer.writeheader()
                    writer.writerow({h: values.get(h, "") for h in headers})
                paths.append(path)
            rows = [read_mapped_rows("adms_db", p, strict=True).rows[0] for p in paths]

        keys = ["rmu", "gss_fid", "y1", "y2", "y3", "y4", "q1", "q2", "rmu_type", "smart", "channel_ip", "channel_port"]
        self.assertEqual({k: rows[0].get(k) for k in keys}, {k: rows[1].get(k) for k in keys})
        self.assertEqual(rows[1]["channel_ip"], "172.20.53.132")
        self.assertNotEqual(rows[1]["channel_ip"], "10689")

    def test_every_tabular_contract_is_order_independent(self):
        """All built-in source contracts bind by header name, not ordinal index."""
        for source_type, schema in SOURCE_SCHEMAS.items():
            # STANDARD has its own header-row scan, but uses the same resolver.
            headers = [spec.preferred_header for spec in schema.fields]
            baseline = resolve_schema(schema, headers)
            reordered = resolve_schema(schema, ["UNRELATED-NEW-COLUMN", *reversed(headers), "ANOTHER-EXTRA"])
            with self.subTest(source_type=source_type):
                self.assertFalse(baseline.errors)
                self.assertFalse(reordered.errors)
                for spec in schema.fields:
                    self.assertEqual(
                        baseline.mapped_column(spec.key),
                        reordered.mapped_column(spec.key),
                        f"{source_type}.{spec.key} changed when physical column order changed",
                    )

    def test_duplicate_business_header_is_ambiguous_not_positional(self):
        result = resolve_schema(schema_for("adms_db"), ["RMU_NAME", "IP", "IP"])
        mapping = result.mapping_by_key["channel_ip"]
        self.assertEqual(mapping.kind, MappingKind.AMBIGUOUS)
        self.assertIsNone(mapping.actual_column)
        self.assertIn(mapping, result.errors)

    def test_declared_header_beats_stale_site_override(self):
        headers = [
            "RMU_NAME", "ADMS_GSS-FID", "NET_DESCRIPTION1", "IP-BAK",
            "PORT", "Voltage", "IP",
        ]
        result = resolve_schema(
            schema_for("adms_db"), headers,
            {"channel_ip": "IP-BAK"},
        )
        mapping = result.mapping_by_key["channel_ip"]
        self.assertEqual(mapping.actual_column, "IP")
        self.assertIn("ignored", mapping.message.lower())

    def test_read_mapped_rows_ignores_stale_override_when_real_header_exists(self):
        headers = [
            "RMU_NAME", "ADMS_GSS-FID", "IP-BAK", "PORT", "Voltage", "IP",
        ]
        values = {
            "RMU_NAME": "10689", "ADMS_GSS-FID": "JED-NTH-ABH-AH308",
            "IP-BAK": "10689", "PORT": "2404", "Voltage": "2404",
            "IP": "172.20.53.132",
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "ADMS-DB.csv"
            with path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=headers)
                writer.writeheader(); writer.writerow(values)
            row = read_mapped_rows(
                "adms_db", path, {"channel_ip": "IP-BAK"}, strict=True
            ).rows[0]
        self.assertEqual(row["channel_ip"], "172.20.53.132")
        self.assertNotEqual(row["channel_ip"], "10689")

    def test_manual_override_remains_available_when_no_declared_header_exists(self):
        result = resolve_schema(
            schema_for("adms_db"),
            ["RMU_NAME", "COMMUNICATION_ADDRESS"],
            {"channel_ip": "COMMUNICATION_ADDRESS"},
        )
        mapping = result.mapping_by_key["channel_ip"]
        self.assertEqual(mapping.kind, MappingKind.OVERRIDE)
        self.assertEqual(mapping.actual_column, "COMMUNICATION_ADDRESS")


if __name__ == "__main__":
    unittest.main()
