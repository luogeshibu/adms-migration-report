from pathlib import Path


def _text():
    root = Path(__file__).resolve().parents[1]
    return (root / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')


def test_signoff_pdf_excludes_secondary_tracking_sections_and_manual_verification():
    text = _text()
    assert 'RMU Need Action Decisions' not in text
    assert 'Registered Issue / Action Items' not in text
    assert 'RMU Manual Verification' not in text
    assert 'Change Audit Snapshot' not in text
    assert '"structured_rmu_resolutions"' in text
    assert '"issue_actions"' in text
    assert '"manual_rmu_checks"' in text


def test_signoff_pdf_uses_requested_two_stage_signature_workflow():
    text = _text()
    assert text.count('class="signoff" width="100%"') == 2
    issue_heading = '<h2 class="signoff-heading">Issue Confirmation / Acceptance</h2>'
    issue_header = '<tr><th class="stub" width="9%"></th><th>SE</th><th>ALF/CET/NARI</th></tr>'
    final_heading = '<h2 class="signoff-heading">Final Rectification Sign-off</h2>'
    final_header = '<tr><th class="stub" width="9%"></th><th>ALF/CET/NARI</th><th>PDC/DNV</th><th>SE</th></tr>'
    assert issue_heading in text and issue_header in text and final_heading in text and final_header in text
    assert text.index(issue_heading) < text.index(issue_header) < text.index(final_heading) < text.index(final_header)
    assert '<colgroup><col width="9%"><col width="45.5%"><col width="45.5%"></colgroup>' in text
    assert '<colgroup><col width="9%"><col width="30.33%"><col width="30.33%"><col width="30.34%"></colgroup>' in text
    assert 'SE confirms the identified issues on the left.' in text
    assert 'ALF/CET/NARI acknowledges the listed issues' in text
    assert '_print_document_with_repeating_header(' in text
    assert 'cover={' in text
