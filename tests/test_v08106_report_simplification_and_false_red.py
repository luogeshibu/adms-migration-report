from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_signal_false_is_strong_red_not_warning_yellow():
    start = UI.index("def _render_db_smart_detail") if "def _render_db_smart_detail" in UI else UI.index("analysis_result == \"TRUE\" or zenon_only")
    block = UI[start:start + 18000]
    assert 'item.setBackground(QColor("#D92D20"))' in block
    assert 'item.setForeground(QColor("#FFFFFF"))' in block
    assert 'row_fill = QColor("#FDECEC")' in block


def test_pdf_restores_prepared_by_without_company():
    body = PDF[PDF.index("<h1>STATION MODIFICATION"):PDF.index("<h2>RMU Data Summary</h2>")]
    cover = PDF[PDF.index("info = ["):PDF.index("label_font =", PDF.index("info = ["))]
    assert "Prepared By" in body and "Prepared By" in cover
    assert ">Company<" not in body and "Company" not in cover


def test_rmu_register_restores_formal_headers_and_combined_remarks():
    for label in ("Original Value", "Target Value", "Source", "Remarks"):
        assert f"<th>{label}</th>" in PDF
    assert "adms_db_value" in PDF and "user_value" in PDF and "comments" in PDF
    block = PDF[PDF.index("def _rmu_open_action_snapshot"):PDF.index("def build_site_signoff_snapshot")]
    assert '"ADMS DB"' in block
    assert 'manual_comment' in block
    # v0.8.110+ deliberately restores the compact App-generated Resolution text
    # and appends the user's manual comment in the same Remarks cell.
    assert 'compact_resolution_text(record)' in block
    assert 'comment_lines.append(f"User comment: {manual_comment}")' in block


def test_signal_remarks_include_generated_action_text_and_user_comments():
    block = PDF[PDF.index("def _signal_need_action_snapshot"):PDF.index("def _signal_validation_summary")]
    assert '"user_comment": clean(review.get("comments"))' in block
    assert 'item["auto_remark"] = _signal_auto_resolution_text(item)' in block
    assert 'item["required_action"] = _signal_combined_remarks(item)' in block
    assert 'Needs Action remains open at export time' not in block


def test_printed_verification_boxes_and_order_are_restored():
    assert PDF.count("<th>NARI Confirm</th><th>SE/DNV Verify</th>") == 3
    assert "&#9633;" in PDF


def test_release_version():
    assert '__version__ = "0.8.120"' in VERSION
