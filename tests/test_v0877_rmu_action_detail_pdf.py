from pathlib import Path

def _pdf_source():
    return (Path(__file__).resolve().parents[1] / 'src/migration_report_tool/infrastructure/export/signoff_pdf.py').read_text(encoding='utf-8')

def test_open_rmu_pdf_has_rectification_fields():
    pdf = _pdf_source()
    for label in ('Modification Item', 'Original Value', 'Target Value', 'Source', 'Remarks'):
        assert f'<th>{label}</th>' in pdf
    assert 'adms_db_value' in pdf
    assert 'user_value' in pdf
    assert 'manual_comment' in pdf
