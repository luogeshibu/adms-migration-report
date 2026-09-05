from pathlib import Path

def _pdf_source():
    return (Path(__file__).resolve().parents[1] / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')

def test_pdf_action_lists_are_open_only():
    pdf = _pdf_source()
    assert 'clean(tracker.get("tracking_status")).upper() != "OPEN"' in pdf
    assert 'get("review_status")).upper() == "NEEDS ACTION"' in pdf
    assert 'RMU Need Action Decisions' not in pdf
    assert 'Registered Issue / Action Items' not in pdf
