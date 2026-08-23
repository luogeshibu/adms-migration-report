from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from migration_report_tool.repository import resolve_site_sources, scan_repository


class SiteRepositoryTests(unittest.TestCase):
    def test_canonical_names_are_detected(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            for name in [
                "SE.xlsx", "ZENON.XML", "ZENON-DB.csv", "ZENON-SLD.csv",
                "ADMS-DB.csv", "ADMS-SLD.csv", "ZENON-ADMS-IOA.csv",
            ]:
                (site / name).write_bytes(b"x")
            sources = resolve_site_sources(site)
            self.assertEqual(set(sources), {
                "se_list", "zenon_xml", "zenon_db", "zenon_sld",
                "adms_db", "adms_sld", "ioa",
            })
            info = scan_repository(Path(td))[0]
            self.assertTrue(info.ready)

    def test_current_legacy_adf_names_are_detected(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            for name in ["ADF-SE.xlsx", "ADF.XML", "ZENON-DB.csv", "ADMS-DB.csv", "ADMS-SLD.csv", "ZENON-ADMS-IOA.csv"]:
                (site / name).write_bytes(b"x")
            sources = resolve_site_sources(site)
            self.assertEqual(sources["se_list"].name, "ADF-SE.xlsx")
            self.assertEqual(sources["zenon_xml"].name, "ADF.XML")
            self.assertTrue(scan_repository(Path(td))[0].ready)

    def test_xml_or_sld_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            for name in ["SE.xlsx", "ZENON-DB.csv", "ADMS-DB.csv", "ADMS-SLD.csv"]:
                (site / name).write_bytes(b"x")
            info = scan_repository(Path(td))[0]
            self.assertFalse(info.ready)
            self.assertIn("zenon_xml_or_sld", info.missing_required)

    def test_combined_xml_filename_is_detected_when_unambiguous(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ABN2"
            site.mkdir()
            for name in ["SE.xlsx", "ABN-ABN2.XML", "ZENON-DB.csv", "ADMS-DB.csv", "ADMS-SLD.csv", "ZENON-ADMS-IOA.csv"]:
                (site / name).write_bytes(b"x")
            sources = resolve_site_sources(site)
            self.assertEqual(sources["zenon_xml"].name, "ABN-ABN2.XML")
            self.assertTrue(scan_repository(Path(td))[0].ready)

    def test_combined_xml_can_be_selected_by_site_token_among_multiple_xmls(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ABN2"
            site.mkdir()
            for name in ["SE.xlsx", "ABN-ABN2.XML", "OTHER.XML", "ZENON-DB.csv", "ADMS-DB.csv", "ADMS-SLD.csv"]:
                (site / name).write_bytes(b"x")
            sources = resolve_site_sources(site)
            self.assertEqual(sources["zenon_xml"].name, "ABN-ABN2.XML")

    def test_ioa_is_required_for_formal_delivery_readiness(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            for name in ["SE.xlsx", "ZENON.XML", "ZENON-DB.csv", "ADMS-DB.csv", "ADMS-SLD.csv"]:
                (site / name).write_bytes(b"x")
            info = scan_repository(Path(td))[0]
            self.assertFalse(info.ready)
            self.assertIn("ioa", info.missing_required)

    def test_site_report_workbook_is_not_a_repository_source(self):
        with tempfile.TemporaryDirectory() as td:
            site = Path(td) / "ADF"
            site.mkdir()
            for name in ["SE.xlsx", "ZENON.XML", "ZENON-DB.csv", "ADMS-DB.csv", "ADMS-SLD.csv", "ADF-REPORT.xlsx"]:
                (site / name).write_bytes(b"x")
            sources = resolve_site_sources(site)
            self.assertNotIn("report_template", sources)
            self.assertNotIn("standard_reference", sources)


if __name__ == "__main__":
    unittest.main()


def test_comparison_column_layout_migration_adds_ip_and_link_once():
    from migration_report_tool.schema import (
        COMPARISON_COLUMN_SCHEMA_VERSION,
        migrate_comparison_visible_columns,
    )

    old_saved = [
        "no", "rmu", "analysis_name", "analysis_feeder",
        "analysis_smart", "analysis_type", "remarks", "comments",
    ]
    migrated = migrate_comparison_visible_columns(old_saved, 1)
    assert "analysis_ip" in migrated
    assert "analysis_link" in migrated

    # Once the schema version is current, an explicit user hide is preserved.
    current_saved = [key for key in migrated if key not in {"analysis_ip", "analysis_link"}]
    preserved = migrate_comparison_visible_columns(
        current_saved, COMPARISON_COLUMN_SCHEMA_VERSION
    )
    assert "analysis_ip" not in preserved
    assert "analysis_link" not in preserved
