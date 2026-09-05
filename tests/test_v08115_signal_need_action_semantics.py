from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_signal_summary_separates_analysis_difference_from_action_issue_count():
    start = PDF.index("<h2>Signal Data Summary</h2>")
    end = PDF.index("<h2>RMU Need Action Register", start)
    block = PDF[start:end]
    assert "STANDARD Point Numbers" in block
    assert "Mismatch / Difference (Info)" not in block
    assert "signal_need_action_total" in block
    assert "Signals With Issues" not in block


def test_formal_signal_actions_never_fall_back_to_review():
    start = PDF.index("def _signal_action_label")
    end = PDF.index("def _signal_label", start)
    block = PDF[start:end]
    assert 'return "ADD"' in block
    assert 'return "DELETE"' in block
    assert 'return "MODIFY"' in block
    assert 'return "REVIEW"' not in block


def test_signal_need_action_register_is_still_persistent_status_driven():
    start = PDF.index("def _signal_need_action_snapshot")
    end = PDF.index("def _signal_validation_summary", start)
    block = PDF[start:end]
    assert '== "NEEDS ACTION"' in block
    assert 'item["action"] = _signal_action_label(item)' in block


def test_release_version_is_08115():
    assert '__version__ = "0.8.120"' in VERSION
