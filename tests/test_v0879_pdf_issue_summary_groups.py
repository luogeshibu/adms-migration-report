from pathlib import Path

def test_pdf_has_separate_rmu_and_signal_summary_tables():
    pdf = Path('src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')
    assert '<h2>RMU Data Summary</h2>' in pdf
    assert '<h2>Signal Data Summary</h2>' in pdf
    assert pdf.index('RMU Data Summary') < pdf.index('Signal Data Summary')
