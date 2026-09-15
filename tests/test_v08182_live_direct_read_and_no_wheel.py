import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.services.configurable_comparison_service import (
    encode_source_path,
    save_config,
    source_path,
)


ROOT = Path(__file__).resolve().parents[1]


class DirectReadSourceTests(unittest.TestCase):
    def _workbook(self, path: Path):
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        ws.append(["Device", "FEEDER", "TYPE"])
        ws.append(["A", "F1", "RMU"])
        wb.save(path)

    def test_configurable_source_keeps_live_site_path_and_creates_no_source_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = root / "site"
            project = root / "project"
            site.mkdir(); project.mkdir()
            live = site / "SE.xlsx"
            self._workbook(live)
            store = ProjectStore(project)
            try:
                store.config["repository_path"] = str(site)
                store.save_config()
                encoded, mode = encode_source_path(store, live)
                config = {
                    "sources": [{
                        "id": "src_test", "title": "SE", "path": encoded,
                        "path_mode": mode, "sheet_name": "Data", "header_row": 1,
                        "key_column": "", "hidden_columns": [], "enabled": True,
                        "selection_mode": "pinned", "family_key": "se", "family_suffix": ".xlsx",
                    }],
                    "comparisons": [],
                }
                saved = save_config(store, config, modified_by="TEST")
                resolved = source_path(store, saved["sources"][0])
                self.assertEqual(resolved.resolve(), live.resolve())
                self.assertEqual(saved["sources"][0]["path_mode"], "site_relative")
                self.assertEqual(list(store.sources_dir.glob("*")), [])
            finally:
                store.close()


    def test_renamed_bootstrapped_source_escapes_timestamped_workspace_copy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            site = root / "site"
            project = root / "project"
            site.mkdir(); project.mkdir()
            live = site / "SE.xlsx"
            self._workbook(live)
            store = ProjectStore(project)
            try:
                store.config["repository_path"] = str(site)
                store.save_config()
                archived = store.set_source("se_list", live)
                store.mark_manual_source_override("se_list", live)
                source = {
                    "id": "src_old", "title": "CUSTOM EQUIPMENT SOURCE",
                    "path": str(archived.resolve()), "path_mode": "absolute",
                    "sheet_name": "Data", "header_row": 1, "key_column": "",
                    "hidden_columns": [], "enabled": True, "selection_mode": "pinned",
                    "family_key": "", "family_suffix": ".xlsx",
                }
                resolved = source_path(store, source)
                self.assertEqual(resolved.resolve(), live.resolve())
            finally:
                store.close()

    def test_direct_read_and_global_no_wheel_contract_is_wired(self):
        service = (ROOT / "src/migration_report_tool/services/configurable_comparison_service.py").read_text(encoding="utf-8")
        guard = (ROOT / "src/migration_report_tool/ui/input_guards.py").read_text(encoding="utf-8")
        app = (ROOT / "src/migration_report_tool/app/application.py").read_text(encoding="utf-8")
        self.assertIn("direct-read only", service)
        self.assertIn("QComboBox", guard)
        self.assertIn("QAbstractSpinBox", guard)
        self.assertIn("QEvent.Type.Wheel", guard)
        self.assertIn("event.accept()", guard)
        self.assertIn("install_selection_wheel_guard(app)", app)


if __name__ == "__main__":
    unittest.main()
