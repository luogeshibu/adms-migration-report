from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
MAIN = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def _signal_summary_block() -> str:
    start = PDF.index("<h2>Signal Data Summary</h2>")
    end = PDF.index("<h2>RMU Need Action Register", start)
    return PDF[start:end]


def test_signal_summary_has_source_totals_and_workflow_counts():
    block = _signal_summary_block()
    assert "STANDARD Point Numbers" in block
    assert "signal_standard_points" in block
    assert "ADMS Point Numbers" in block
    assert "Matched to STANDARD" in block
    assert "Need Action Total" in block
    assert ">Closed<" in block
    assert "Pending / Open" in block
    assert "Mismatch / Difference (Info)" not in block


def test_standard_total_counts_standard_dot_rows():
    start = PDF.index("def _signal_validation_summary")
    end = PDF.index("def _signal_review_state_summary", start)
    block = PDF[start:end]
    assert '_signal_row_value(report, row, "standard_dot_no")' in block
    assert '"standard_points": standard_points' in block


def test_validation_cache_persists_standard_and_adms_totals():
    assert '"standard_points": int(standard_points)' in MAIN
    assert '"standard_points": int(signal_standard_points)' in MAIN
    assert '"adms_points": int(signal_adms_points)' in MAIN


def test_release_version_is_08117():
    assert '__version__ = "0.8.120"' in VERSION
