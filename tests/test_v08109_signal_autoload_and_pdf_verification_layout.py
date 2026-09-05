from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")

def test_signal_fingerprint_sync_uses_function_report_argument():
    block = MAIN[MAIN.index("def _sync_signal_review_fingerprints"):MAIN.index("@staticmethod", MAIN.index("def _sync_signal_review_fingerprints"))]
    assert "signal_review_alias_map(report)" in block
    assert "signal_review_metadata(report, item)" in block
    assert "signal_review_alias_map(signal_report)" not in block

def test_verification_columns_and_large_box():
    assert PDF.count("<th>NARI Confirm</th><th>SE/DNV Verify</th>") == 3
    assert "&#9633;" in PDF
    assert "font-size:17pt" in PDF
    assert "&#10003;" in PDF and "&#10007;" in PDF

def test_final_signoff_has_explicit_gap_from_issue_confirmation():
    assert ".signoff-block + .signoff-block {{ margin-top:46px; padding-top:8px; }}" in PDF

def test_version():
    assert '__version__ = "0.8.120"' in VERSION
