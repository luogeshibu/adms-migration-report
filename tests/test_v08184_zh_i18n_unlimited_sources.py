from __future__ import annotations

import unittest
from pathlib import Path

from migration_report_tool.version import __version__


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
I18N = (ROOT / "src" / "migration_report_tool" / "ui" / "i18n.py").read_text(encoding="utf-8")
MODULES = (ROOT / "src" / "migration_report_tool" / "config" / "source_modules.py").read_text(encoding="utf-8")


class TestV08184ZhI18nUnlimitedSources(unittest.TestCase):
    def test_release_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_new_configurable_source_and_profile_ui_has_chinese_contracts(self):
        cases = {
            '"Available Site Files": "现场可用文件"',
            '"Equipment Sources": "设备审核数据源"',
            '"Configuration Reuse / Inheritance": "配置复用 / 继承"',
            '"Local · this site only": "本地配置 · 仅当前站点"',
            '"Inherit global profile · explicit sync": "继承全局模板 · 手动同步"',
            '"Apply / Sync": "应用 / 同步"',
            '"Latest file in family (AUTO)": "同系列最新文件（自动）"',
            '"Pin this exact file": "固定使用当前文件"',
        }
        for contract in cases:
            self.assertIn(contract, I18N)

    def test_site_list_no_longer_renders_fixed_six_source_counter(self):
        start = UI.index("    def _render_site_list")
        end = UI.index("    def _site_item_changed", start)
        block = UI[start:end]
        self.assertNotIn("len(SOURCE_DEFINITIONS)", block)
        self.assertNotIn("source_count_text", block)
        self.assertNotIn("/6", block)
        self.assertIn('status = "CONFIGURED" if current_site_configured else ("CONFIGURABLE"', block)
        self.assertIn("数据源数量按站点自由配置", UI)

    def test_equipment_module_description_is_arbitrary_source_contract(self):
        self.assertIn("supports any number of configured CSV/XLSX/XLSM source tables", MODULES)
        self.assertNotIn("Review every equipment type across SE, ZENON DB, ZENON SLD, ADMS DB and ADMS SLD", MODULES)

    def test_configurable_source_table_renders_localized_placeholder_body(self):
        self.assertIn('QTableWidgetItem(ui_tr("Configurable Equipment Comparison", self.ui_language))', UI)
        self.assertIn('QTableWidgetItem(ui_tr("Any CSV / Excel", self.ui_language))', UI)
        self.assertIn('QPushButton(ui_tr("Configure Sources...", self.ui_language))', UI)

    def test_configured_ready_text_has_no_fixed_source_denominator(self):
        start = UI.index("    def _update_validation_text", UI.index("class ConfigurableEquipmentComparisonDialog"))
        end = UI.index("    def _accept_config", start)
        block = UI[start:end]
        self.assertIn("数据源数量不设固定上限", block)
        self.assertNotIn("active_count}/{", block)


if __name__ == "__main__":
    unittest.main()
