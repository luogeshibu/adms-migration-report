from pathlib import Path


def _pdf_source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")


def _ui_source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")


def test_pdf_metadata_restores_prepared_by_but_company_stays_removed():
    text = _pdf_source()
    body = text[text.index("<h1>STATION MODIFICATION"):text.index("<h2>RMU Data Summary</h2>")]
    assert "Prepared By" in body
    assert ">Company<" not in body
    cover_info = text[text.index("info = ["):text.index("label_font =", text.index("info = ["))]
    assert "Prepared By" in cover_info
    assert "Company" not in cover_info


def test_pdf_export_requires_prepared_by_name_and_does_not_prompt_for_company():
    text = _ui_source()
    start = text.index("    def export_signoff_pdf(self):")
    end = text.index("    def ", start + 10)
    block = text[start:end]
    assert 'QInputDialog.getText' in block
    assert '"Prepared By"' in block
    assert 'if prepared_by:' in block
    assert 'Prepared By Required' in block
    assert 'prepared_by=prepared_by' in block
    assert 'company="NARI"' in block


def test_v08102_version():
    root = Path(__file__).resolve().parents[1]
    version = (root / "src/migration_report_tool/version.py").read_text(encoding="utf-8")
    assert '__version__ = "0.8.120"' in version
