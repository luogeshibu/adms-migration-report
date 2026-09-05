from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def _signal_summary_block() -> str:
    start = PDF.index("<h2>Signal Data Summary</h2>")
    end = PDF.index("<h2>RMU Need Action Register", start)
    return PDF[start:end]


def test_signal_pdf_summary_mirrors_rmu_review_state_shape():
    block = _signal_summary_block()
    assert "STANDARD Point Numbers" in block
    assert "ADMS Point Numbers" in block
    assert "Matched to STANDARD" in block
    assert "Mismatch / Difference (Info)" not in block
    assert "Need Action Total" in block
    assert ">Closed<" in block
    assert "Pending / Open" in block
    assert "Signals With Issues" not in block
    assert "Match Rate" not in block
    assert "Status / Cmd Need Action" not in block
    assert "Analog Need Action" not in block


def test_signal_difference_is_analysis_only_and_need_action_is_formal_issue_total():
    start = PDF.index("def _signal_validation_summary")
    end = PDF.index("def _signal_review_state_summary", start)
    block = PDF[start:end]
    assert 'if result == "FALSE":\n            differences += 1' in block
    assert '"differences": differences' in block
    assert '"signal_with_issues": int(signal_need_action_counts.get("TOTAL", 0))' in PDF
    assert "signal_mismatch_info" in PDF


def test_signal_review_summary_uses_need_action_lifecycle_partition():
    start = PDF.index("def _signal_review_state_summary")
    end = PDF.index("def _load_issue_snapshot", start)
    block = PDF[start:end]
    assert 'ever_needs_action' in block
    assert 'raw_status == "CLOSED"' in block
    assert 'raw_status == "NEEDS ACTION"' in block
    assert '"need_action_total": total' in block
    assert '"closed": closed' in block
    assert '"pending": pending' in block


def test_signal_register_category_split_is_still_retained():
    assert "Status / Cmd Need Action Register" in PDF
    assert "Analog Need Action Register" in PDF
    assert "signal_need_action_status_cmd" in PDF
    assert "signal_need_action_analog" in PDF


def test_release_version_is_08113():
    assert '__version__ = "0.8.120"' in VERSION
