from pathlib import Path

from migration_report_tool.version import __version__

ROOT = Path(__file__).resolve().parents[1]
I18N = (ROOT / "src/migration_report_tool/ui/i18n.py").read_text(encoding="utf-8")
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")


def test_release_version():
    assert __version__ == "0.8.158"


def test_table_translation_boundary_is_global():
    assert "def _is_table_presentation_widget" in I18N
    assert "if _is_table_presentation_widget(widget):" in I18N
    assert "QTableWidget headers, body" in I18N
    assert "_i18n_source_header_" not in I18N


def test_source_role_labels_stay_english_in_chinese_dictionary():
    assert '"SE Equipment": "SE Equipment"' in I18N
    assert '"SE Equipment List": "SE Equipment List"' in I18N


def test_grouped_and_review_table_labels_are_not_translated_at_paint_time():
    assert "Qt.AlignCenter | Qt.TextWordWrap, label)" in UI
    assert "Qt.AlignCenter | Qt.TextWordWrap, group)" in UI
    assert "return label, QColor(fill), QColor(text)" in UI


def test_map_fields_table_cells_stay_english():
    assert "QTableWidgetItem(role_key)" in UI
    assert "QTableWidgetItem(status_text)" in UI
    assert 'QTableWidgetItem("USER")' in UI
    assert 'QTableWidgetItem("Mapped" if mapped else "Unmapped · blank")' in UI


def test_site_source_table_stays_english_contract():
    assert "display_mapping_parts = [str(mapping_part) for mapping_part in mapping_parts]" in UI
    assert "display_sheet = sheet_display" in UI
    assert "display_status = simple_status" in UI
    assert "display_ref_label = ref.label" in UI
