import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_report_tool.config.column_schema import DATA_GROUPS, COMPARISON_COLUMN_SCHEMA_VERSION, migrate_comparison_visible_columns
from migration_report_tool.services.rmu_review_service import build_comparison
from migration_report_tool.services.schema_service import RMU_REVIEW_DISPLAY_BINDINGS, set_source_overrides
from migration_report_tool.domain.schema import BLANK_OVERRIDE_TOKEN
from migration_report_tool.storage import ProjectStore


def _write_csv(path: Path, fieldnames, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


class V08130ZenonSldSmartReviewColumnTests(unittest.TestCase):
    def test_zenon_sld_smart_is_a_real_review_column_and_display_binding(self):
        zsld_group = next(cols for group, _color, cols in DATA_GROUPS if group == "ZENON SLD")
        keys = [key for key, _label, _width in zsld_group]
        self.assertIn("zsld_smart", keys)
        self.assertEqual(RMU_REVIEW_DISPLAY_BINDINGS["zsld_smart"], ("zenon_sld", "smart"))
        self.assertGreaterEqual(COMPARISON_COLUMN_SCHEMA_VERSION, 7)
        self.assertIn("zsld_smart", migrate_comparison_visible_columns(["no", "rmu"], 6))

    def test_blank_system_mapping_keeps_zenon_sld_smart_column_present_but_value_blank(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zsld = root / "ZENON-SLD.csv"
            _write_csv(zsld, ["RMU", "Feeder", "CabinetType", "SMART"], [
                {"RMU": "10689", "Feeder": "JED-NTH-ABH-03", "CabinetType": "3L1T", "SMART": "SMART"},
            ])
            with patch("migration_report_tool.infrastructure.database.global_settings_store.user_data_root", return_value=root / "appdata"):
                store = ProjectStore(root / "project")
                try:
                    store.config["site_name"] = "1-ABH"
                    store.config["repository_site"] = "1-ABH"
                    store.save_config()
                    store.set_source("zenon_sld", zsld)
                    set_source_overrides(store, "zenon_sld", {"smart": BLANK_OVERRIDE_TOKEN}, "tester")
                    rows, _summary = build_comparison(store)
                    row = next(r for r in rows if r["rmu"] == "10689")
                    self.assertIn("zsld_smart", row)
                    self.assertEqual(row["zsld_smart"], "")
                finally:
                    store.db.close()

    def test_auto_mapping_populates_zenon_sld_smart_review_value(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zsld = root / "ZENON-SLD.csv"
            _write_csv(zsld, ["RMU", "Feeder", "CabinetType", "SMART"], [
                {"RMU": "10689", "Feeder": "JED-NTH-ABH-03", "CabinetType": "3L1T", "SMART": "SMART"},
            ])
            with patch("migration_report_tool.infrastructure.database.global_settings_store.user_data_root", return_value=root / "appdata"):
                store = ProjectStore(root / "project")
                try:
                    store.config["site_name"] = "1-ABH"
                    store.config["repository_site"] = "1-ABH"
                    store.save_config()
                    store.set_source("zenon_sld", zsld)
                    set_source_overrides(store, "zenon_sld", {"smart": "SMART"}, "tester")
                    rows, _summary = build_comparison(store)
                    row = next(r for r in rows if r["rmu"] == "10689")
                    self.assertEqual(row["zsld_smart"], "SMART")
                finally:
                    store.db.close()


if __name__ == "__main__":
    unittest.main()
