from pathlib import Path

def _pdf_source():
    return (Path(__file__).resolve().parents[1] / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')

def test_pdf_is_need_action_focused_and_split_by_category():
    pdf = _pdf_source()
    assert 'RMU Need Action Register' in pdf
    assert 'Status / Cmd Need Action Register' in pdf
    assert 'Analog Need Action Register' in pdf
    assert 'RMU Manual Verification' not in pdf
