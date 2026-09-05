from pathlib import Path


def _source():
    root = Path(__file__).resolve().parents[1]
    return (root / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')


def test_issue_acceptance_headers_are_se_then_alf_cet_nari():
    text = _source()
    assert '<th>SE</th><th>ALF/CET/NARI</th>' in text
    assert 'Issue Raised / Reported By' not in text
    assert 'NARI Confirmation / Acceptance</th>' not in text


def test_final_rectification_headers_exactly_match_customer_labels():
    text = _source()
    assert '<th>ALF/CET/NARI</th><th>PDC/DNV</th><th>SE</th>' in text
    assert 'NARI Resubmission</th>' not in text
    assert 'PDC/DNV Review</th>' not in text
    assert 'SE Review</th>' not in text
