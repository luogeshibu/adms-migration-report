from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem import site_repository
from migration_report_tool.version import __version__


ROOT = Path(__file__).resolve().parents[1]
UI_SOURCE = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
PDF_SOURCE = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")


class TestV08185ConfigurableUxExportEquipmentTracking(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_source_recognition_categories_are_extensible_optional_hints(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "site_repository.json"
            with patch.object(site_repository, "_config_path", return_value=cfg):
                categories = site_repository.load_source_detection_categories()
                categories.append({
                    "key": "",
                    "label": "HITACHI Export",
                    "keywords": ["HITACHI", "HIT-SLD"],
                    "built_in": False,
                })
                site_repository.save_source_detection_categories(categories)
                saved = site_repository.load_source_detection_categories()
                custom = next(item for item in saved if item["label"] == "HITACHI Export")
                self.assertFalse(custom["built_in"])
                self.assertEqual(custom["keywords"], ["HITACHI", "HIT-SLD"])
                # Recognition is a hint for an otherwise arbitrary filename; it is
                # not a fixed source-role requirement.
                hits = site_repository.classify_source_detection_hint(Path("customer-HITACHI-anything.xlsx"))
                self.assertEqual(hits[0]["label"], "HITACHI Export")

    def test_all_equipment_uses_durable_need_action_tracking(self):
        with tempfile.TemporaryDirectory() as td:
            store = ProjectStore(Path(td) / "project")
            try:
                key = "EQ::LBS::LBS-001"
                store.update_rmu_review_status(key, "NEEDS ACTION", "tester", "equipment needs action")
                rows = store.equipment_action_tracking()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["equipment_key"], key)
                self.assertEqual(rows[0]["tracking_status"], "OPEN")
                # UNREVIEWED must not silently drop a previously opened follow-up.
                store.update_rmu_review_status(key, "UNREVIEWED", "tester", "recheck")
                self.assertEqual(store.equipment_action_tracking()[0]["tracking_status"], "OPEN")
                store.update_rmu_review_status(key, "CLOSED", "tester", "resolved")
                self.assertEqual(store.equipment_action_tracking()[0]["tracking_status"], "CLOSED")
                self.assertGreaterEqual(store.equipment_full_lifecycle(key)["case_count"], 1)
            finally:
                store.close()

    def test_formal_exports_require_explicit_save_as_path(self):
        self.assertIn('target_path = self._choose_export_target(', UI_SOURCE)
        self.assertIn('"Choose Sign-off PDF Save Location"', UI_SOURCE)
        self.assertIn('"Choose Migration Report Save Location"', UI_SOURCE)
        self.assertIn('export_site_signoff_pdf(', UI_SOURCE)
        self.assertIn('target_path=target_path', UI_SOURCE)
        self.assertIn('_background_excel_export_job(project_folder, str(target_path))', UI_SOURCE)

    def test_signoff_pdf_tracks_generic_equipment(self):
        self.assertIn("<h2>Equipment Data Summary</h2>", PDF_SOURCE)
        self.assertIn("Equipment Need Action Register", PDF_SOURCE)
        self.assertIn("<th>Type</th><th>Equipment</th>", PDF_SOURCE)
        self.assertIn('store.equipment_action_tracking()', PDF_SOURCE)
        self.assertIn('"equipment_name": equipment_name', PDF_SOURCE)


if __name__ == "__main__":
    unittest.main()
