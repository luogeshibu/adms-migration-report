from pathlib import Path

from migration_report_tool.version import __version__
ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
I18N = (ROOT / "src/migration_report_tool/ui/i18n.py").read_text(encoding="utf-8")


def test_release_version():
    assert __version__ == "0.8.159"


def test_five_source_names_are_language_neutral():
    assert '"SE Equipment": "SE Equipment"' in I18N
    assert '"SE Equipment List": "SE Equipment List"' in I18N
    for name in ("SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"):
        assert f'"{name}": "' not in I18N or f'"{name}": "{name}"' in I18N


def test_workflow_meta_headers_remain_localized_in_chinese():
    for english, chinese in (("Row Locator", "行定位"), ("Index", "索引"), ("Source Coverage", "来源覆盖"), ("Analysis", "分析"), ("Remarks", "备注"), ("Resolution", "处理决议")):
        assert f'"{english}": "{chinese}"' in I18N
    assert 'display_group = group if group in source_groups else ui_tr(group, current_language())' in UI
    assert 'display_label = label if group in source_groups or group == "Analysis" else ui_tr(label, current_language())' in UI


def test_settings_help_paragraphs_have_chinese_translations():
    samples = [
        "Setup complete. Source Workspace and Project Data Storage are configured and will be reused automatically on future launches.",
        "Recommended filenames are not mandatory. Configure comma-separated filename keywords here; the detector also checks CSV/XLSX column structure. Ambiguous files remain unmapped until assigned manually.",
        "Signal Mapping Review and every formal export use the explicitly selected application-wide STANDARD workbook. You may keep multiple validated STANDARD versions in the library. Uploading never changes the active version automatically; choose the workbook below and click Use Selected. Site Repository files are never modified.",
    ]
    for text in samples:
        assert text in I18N
    assert "设置已完成" in I18N
    assert "推荐文件名不是强制要求" in I18N
    assert "信号映射审核和所有正式导出" in I18N


def test_large_equipment_grid_uses_batched_items_not_row_widgets():
    assert "self._comparison_render_batch_size = 24" in UI
    locator_start = UI.index("def _populate_comparison_locator_row")
    locator_end = UI.index("def _refresh_comparison_locator", locator_start)
    locator = UI[locator_start:locator_end]
    assert "QTableWidgetItem()" in locator
    assert "ItemIsUserCheckable" in locator
    assert "setCellWidget(r, 2" not in locator


def test_hover_tracking_does_not_force_full_viewport_repaint():
    start = UI.index("def set_tracked_hover_row")
    end = UI.index("def _on_current_cell_changed", start)
    block = UI[start:end]
    assert "viewport().update()" not in block


def test_equipment_source_custom_mapping_metadata_is_loaded_once_per_source():
    service = (ROOT / "src/migration_report_tool/services/rmu_review_service.py").read_text(encoding="utf-8")
    assert "custom_fields_by_source" in service
    assert "custom_fields_by_source[source_type] = list(store.custom_source_fields(source_type) or [])" in service
    row_loop = service.index("for zrow in zsld_rows:")
    tail = service[row_loop:service.index("return output, summary", row_loop)]
    assert "store.custom_source_fields(source_type)" not in tail
