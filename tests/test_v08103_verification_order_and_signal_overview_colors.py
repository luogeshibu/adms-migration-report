from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pdf_verification_columns_restore_nari_then_se_dnv_and_print_boxes():
    text = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
    assert text.count("<th>NARI Confirm</th><th>SE/DNV Verify</th>") == 3
    assert "<th>SE/DNV Verify</th><th>NARI Confirm</th>" not in text
    assert "&#9633;" in text
    assert "Verification marking: mark &#10003; in the box to confirm/accept, or &#10007; to reject/not confirm." in text


def test_signal_rmu_overview_clean_rows_are_green_and_problems_keep_issue_colors():
    text = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    start = text.index("def _render_db_smart_rmu_list")
    end = text.index("def _show_db_smart_rmu_overview", start)
    block = text[start:end]
    assert 'has_need_action = bool(metric["needs_action"])' in block
    assert 'has_unreviewed = bool(metric.get("unreviewed", 0))' in block
    assert 'has_unreviewed_mismatch = bool(metric.get("unreviewed_mismatch", 0))' in block
    assert 'fill = QColor("#FDECEC")' in block
    assert 'fill = QColor("#FFF8E6")' in block
    assert 'cell.setBackground(QColor("#D92D20"))' in block
    assert '(col == 6 and has_unreviewed_mismatch) or (col == 8 and has_need_action)' in block
    assert 'fill = QColor("#EAF7F0")' in block


def test_release_version_is_v08103():
    version = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")
    assert '__version__ = "0.8.120"' in version
