from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_rmu_pdf_remarks_include_app_generated_resolution_and_user_comment():
    start = PDF.index("def _rmu_open_action_snapshot")
    end = PDF.index("def build_site_signoff_snapshot", start)
    block = PDF[start:end]
    assert "compact_resolution_text(record)" in block
    assert "comment_lines.append(generated_remark)" in block
    assert 'comment_lines.append(f"User comment: {manual_comment}")' in block
    # OTHER's user text is already embedded in compact_resolution_text and must
    # not be appended raw a second time.
    other_start = block.index('elif decision == "OTHER":')
    other_end = block.index('elif decision == "NEEDS_ACTION":', other_start)
    assert "comment_lines.append(selected_value)" not in block[other_start:other_end]


def test_pdf_explains_combined_remarks_contract():
    assert "Remarks contains the App-generated Resolution text plus any reviewer-entered comment." in PDF


def test_explicit_gap_exists_before_final_rectification_signoff():
    assert '.signoff-gap {{ height:32px; line-height:32px; font-size:1px; }}' in PDF
    marker = '<div class="signoff-gap">&nbsp;</div>'
    final_heading = '<h2 class="signoff-heading">Final Rectification Sign-off</h2>'
    assert marker in PDF
    assert PDF.index(marker) < PDF.index(final_heading)


def test_release_version():
    assert '__version__ = "0.8.120"' in VERSION
