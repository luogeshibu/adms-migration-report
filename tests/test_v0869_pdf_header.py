from pathlib import Path

import struct


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_report_header_asset_is_packaged_and_wide():
    path = _root() / "resources" / "assets" / "report_header.png"
    assert path.exists()
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width > height * 8
    assert width >= 1500


def test_signoff_pdf_repeats_header_on_each_page():
    source = (_root() / "src" / "migration_report_tool" / "infrastructure" / "export" / "signoff_pdf.py").read_text(encoding="utf-8")
    assert "report_header.png" in source
    assert "_print_document_with_repeating_header" in source
    assert "for page_index in range(page_count)" in source
    assert "writer.newPage()" in source
    assert "painter.drawImage" in source
    assert "_print_document_with_repeating_header(" in source
    assert "cover={" in source
