from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _pdf_source() -> str:
    return (_root() / "src" / "migration_report_tool" / "infrastructure" / "export" / "signoff_pdf.py").read_text(encoding="utf-8")


def test_rmu_register_flows_into_signature_workflow_without_forced_pagebreak():
    pdf = _pdf_source()
    assert "RMU Need Action Register" in pdf
    assert "This report is generated from the site's persistent Project Data" not in pdf
    rmu_pos = pdf.index("RMU Need Action Register")
    signoff_pos = pdf.index('<h2 class="signoff-heading">Issue Confirmation / Acceptance</h2>', rmu_pos)
    between = pdf[rmu_pos:signoff_pos]
    assert 'page-break-before:always' not in between
    assert '<div class="pagebreak"></div>' not in between
    assert '.signoff-block {{ page-break-inside:avoid; margin-top:22px; }}' in pdf

def test_body_pages_are_numbered_but_cover_is_not():
    pdf = _pdf_source()
    assert "def _paint_body_page_number(" in pdf
    assert 'f"Page {page_number} of {page_count}"' in pdf
    assert "page_number=page_index + 1" in pdf
    cover_block = pdf[pdf.index("def _paint_cover_page("):pdf.index("def _print_document_with_repeating_header(")]
    assert "_paint_body_page_number(" not in cover_block
    assert "page_number_height = _body_page_number_height(writer)" in pdf


def test_version_bumped_to_v0895():
    version = (_root() / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")
    assert '__version__ = "0.8.120"' in version
