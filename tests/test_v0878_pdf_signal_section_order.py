from pathlib import Path

def test_status_cmd_precedes_analog_in_pdf():
    pdf = (Path(__file__).resolve().parents[1] / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')
    assert pdf.index('Status / Cmd Need Action Register') < pdf.index('Analog Need Action Register')
