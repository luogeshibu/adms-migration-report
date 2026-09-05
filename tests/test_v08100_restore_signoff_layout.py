from pathlib import Path


def _source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")


def test_v08101_uses_requested_workflow_signature_layout_without_touching_registers():
    text = _source()
    assert 'RMU Data Summary' in text
    assert 'Signal Data Summary' in text
    assert 'RMU Need Action Register' in text
    assert 'Status / Cmd Need Action Register' in text
    assert 'Analog Need Action Register' in text
    issue_heading = '<h2 class="signoff-heading">Issue Confirmation / Acceptance</h2>'
    issue_header = '<tr><th class="stub" width="9%"></th><th>SE</th><th>ALF/CET/NARI</th></tr>'
    final_heading = '<h2 class="signoff-heading">Final Rectification Sign-off</h2>'
    final_header = '<tr><th class="stub" width="9%"></th><th>ALF/CET/NARI</th><th>PDC/DNV</th><th>SE</th></tr>'
    assert text.index(issue_heading) < text.index(issue_header) < text.index(final_heading) < text.index(final_header)
    assert '<colgroup><col width="9%"><col width="45.5%"><col width="45.5%"></colgroup>' in text
    assert '<colgroup><col width="9%"><col width="30.33%"><col width="30.33%"><col width="30.34%"></colgroup>' in text
    assert '<tr><th width="9%">Name</th><td></td><td>Jia Wei</td></tr>' in text
    assert '<tr><th width="9%">Name</th><td>Jia Wei</td><td></td><td></td></tr>' in text


def test_v08101_version():
    root = Path(__file__).resolve().parents[1]
    version = (root / 'src/migration_report_tool/version.py').read_text(encoding='utf-8')
    assert '__version__ = "0.8.120"' in version
