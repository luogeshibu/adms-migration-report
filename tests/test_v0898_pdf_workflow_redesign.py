from pathlib import Path


def _source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')


def test_summary_matches_requested_rmu_and_signal_metrics():
    text = _source()
    for label in (
        'RMU Data Summary', 'Total RMUs', 'Validation Pass', 'RMUs With Issues',
        'Review Passed / Closed', 'Need Action / Open', 'Pending Review',
        'Signal Data Summary', 'STANDARD Point Numbers', 'ADMS Point Numbers', 'Matched to STANDARD',
        'Need Action / Open', 'Closed', 'Pending Review',
    ):
        assert label in text
    assert '_signal_validation_summary' in text
    assert 'analysis_review_state(row)' in text


def test_exactly_three_rectification_registers_have_requested_columns():
    text = _source()
    assert 'RMU Need Action Register' in text
    assert 'Status / Cmd Need Action Register' in text
    assert 'Analog Need Action Register' in text
    assert text.index('RMU Need Action Register') < text.index('Status / Cmd Need Action Register') < text.index('Analog Need Action Register')
    for label in ('Issue Type', 'Original Value', 'Target Value', 'Source', 'Remarks'):
        assert f'<th>{label}</th>' in text
    assert text.count('<th>NARI Confirm</th>') == 3
    assert text.count('<th>SE/DNV Verify</th>') == 3
    assert 'Point No.' in text and '<th>Action</th>' in text
    assert "&#9633;" in text


def test_signal_action_is_add_delete_modify_and_category_order_is_status_first():
    text = _source()
    assert 'return "DELETE"' in text
    assert 'return "ADD"' in text
    assert 'return "MODIFY"' in text
    assert text.index('Status / Cmd Need Action Register') < text.index('Analog Need Action Register')


def test_signature_tables_keep_requested_customer_workflow_layout():
    text = _source()
    assert '<h2 class="signoff-heading">Issue Confirmation / Acceptance</h2>' in text
    assert '<tr><th class="stub" width="9%"></th><th>SE</th><th>ALF/CET/NARI</th></tr>' in text
    assert '<h2 class="signoff-heading">Final Rectification Sign-off</h2>' in text
    assert '<tr><th class="stub" width="9%"></th><th>ALF/CET/NARI</th><th>PDC/DNV</th><th>SE</th></tr>' in text
    assert '<colgroup><col width="9%"><col width="45.5%"><col width="45.5%"></colgroup>' in text
    assert '<colgroup><col width="9%"><col width="30.33%"><col width="30.33%"><col width="30.34%"></colgroup>' in text
    assert 'NARI Resubmission' not in text
    assert 'PDC/DNV Review' not in text
    assert 'SE Review' not in text
    assert 'page-break-inside:avoid' in text


def test_closed_records_stay_out_of_action_registers():
    text = _source()
    assert 'clean(tracker.get("tracking_status")).upper() != "OPEN"' in text
    assert 'get("review_status")).upper() == "NEEDS ACTION"' in text
    assert 'RMU Manual Verification' not in text
    assert 'Registered Issue / Action Items' not in text
    assert 'Change Audit Snapshot' not in text


def test_version_v0898():
    root = Path(__file__).resolve().parents[1]
    version = (root / 'src/migration_report_tool/version.py').read_text(encoding='utf-8')
    assert '__version__ = "0.8.120"' in version
