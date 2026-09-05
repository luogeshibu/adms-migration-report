from pathlib import Path

def _source():
    return (Path(__file__).resolve().parents[1] / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')

def test_signoff_blocks_use_natural_flow_without_forced_pagebreak():
    text = _source()
    rmu = text.index('RMU Need Action Register')
    first_signoff = text.index('<h2 class="signoff-heading">Issue Confirmation / Acceptance</h2>', rmu)
    between = text[rmu:first_signoff]
    assert 'page-break-before:always' not in between
    assert '.signoff {{ width:100%; min-width:100%; border-collapse:collapse; margin-top:18px; table-layout:fixed; page-break-inside:avoid; }}' in text

def test_version_bumped():
    version = (Path(__file__).resolve().parents[1] / 'src/migration_report_tool/version.py').read_text(encoding='utf-8')
    assert '__version__ = "0.8.120"' in version
