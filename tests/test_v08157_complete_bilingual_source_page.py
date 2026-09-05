from pathlib import Path

from migration_report_tool.version import __version__


ROOT = Path(__file__).resolve().parents[1]
I18N = (ROOT / "src/migration_report_tool/ui/i18n.py").read_text(encoding="utf-8")
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
MODULES = (ROOT / "src/migration_report_tool/config/source_modules.py").read_text(encoding="utf-8")


def test_release_version():
    assert __version__ == "0.8.157"


def test_current_site_source_prose_has_exact_chinese_translation():
    assert "AUTO still uses published V versions / detection rules" in UI
    assert "AUTO 仍会优先参考已发布的 V 版本和数据源识别规则" in I18N
    assert '"Fields Used in This Module (App ← Source)"' in I18N
    assert "本模块使用字段（App ← 源字段）" in I18N


def test_module_description_uses_generic_all_equipment_translated_contract():
    sentence = (
        "Review every equipment type across SE, ZENON DB, ZENON SLD, ADMS DB and ADMS SLD. "
        "Every detected equipment type uses the same Analysis, Review Status, Resolution, Comments "
        "and Needs Action lifecycle workflow."
    )
    assert sentence in MODULES
    assert sentence in I18N
    assert "五个来源中的所有设备类型进行审核" in I18N


def test_dynamic_site_repository_text_is_language_aware():
    assert 'f"{len(self.repository_sites)} 个站点 · {ready} 个就绪"' in UI
    assert 'display_status = ui_tr(status, self.ui_language)' in UI
    assert 'source_count_text = f"{present}/{len(SOURCE_DEFINITIONS)} 个数据源"' in UI
    assert 'ui_tr(\'Site scope: \', self.ui_language)' in UI
    assert 'ui_tr("Last scan: " + datetime.now().strftime' in UI


def test_mapping_summary_translates_only_app_side():
    assert 'left, sep, right = str(mapping_part).partition(" ← ")' in UI
    assert 'f"{ui_tr(left, self.ui_language)} ← {right}"' in UI
    assert 'ui_tr(label, self.ui_language)' in UI
