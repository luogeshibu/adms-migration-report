# v0.8.73 contract tests
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_signal_detail_has_need_action_summary_and_click_navigation():
    ui = (_root() / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'QLabel("Need Action Summary")' in ui
    assert "db_smart_need_action_summary" in ui
    assert "db_smart_need_action_list" in ui
    assert "_refresh_db_smart_need_action_summary" in ui
    assert "_locate_db_smart_need_action_from_summary" in ui
    assert "_locate_db_smart_review_row" in ui
    assert "_db_smart_need_action_highlight_keys" in ui
    assert 'QColor("#DCEEFF")' in ui


def test_existing_comment_to_adms_implementation_navigation_is_preserved():
    ui = (_root() / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'QLabel("ADMS Implementation Summary")' in ui
    assert "_db_smart_detail_cell_clicked" in ui
    assert "_locate_db_smart_implementation" in ui
    assert "zenon_only_adms_match_rows" in ui


def test_pdf_contains_split_signal_need_action_summary_and_modification_list():
    pdf = (_root() / "src" / "migration_report_tool" / "infrastructure" / "export" / "signoff_pdf.py").read_text(encoding="utf-8")
    assert "Signal Data Summary" in pdf
    assert "Analog Need Action" in pdf
    assert "Status / Cmd Need Action" in pdf
    assert "signal_need_action_analog" in pdf
    assert "signal_need_action_status_cmd" in pdf
    assert "Analog Need Action Register" in pdf
    assert "Status / Cmd Need Action Register" in pdf
    assert "Remarks" in pdf
    assert '== "NEEDS ACTION"' in pdf
    assert 'point_no >= 13000' in pdf
    assert "Change Audit Snapshot" not in pdf
