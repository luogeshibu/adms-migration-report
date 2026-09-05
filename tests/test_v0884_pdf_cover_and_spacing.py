from pathlib import Path
import struct


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_data_migration_cover_asset_is_packaged():
    path = _root() / "resources" / "assets" / "data_migration_cover.png"
    assert path.exists()
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    assert width >= 600
    assert height >= 550


def test_pdf_has_dedicated_cover_before_unchanged_body():
    source = (_root() / "src" / "migration_report_tool" / "infrastructure" / "export" / "signoff_pdf.py").read_text(encoding="utf-8")
    assert "def _paint_cover_page(" in source
    assert 'title_text = "DISTRIBUTION NETWORK DATA MIGRATION REPORT"' in source
    assert 'data_migration_cover.png' in source
    assert '"SAUDI ADMS PROJECT - DATA MIGRATION"' in source
    assert not any('\u4e00' <= ch <= '\u9fff' for ch in source)
    assert 'writer.newPage()' in source
    assert '<h1>STATION MODIFICATION &amp; ISSUE CLOSURE REPORT</h1>' in source
    assert 'cover={' in source


def test_signoff_tables_use_requested_current_workflow_layout():
    source = (_root() / "src" / "migration_report_tool" / "infrastructure" / "export" / "signoff_pdf.py").read_text(encoding="utf-8")
    assert '.signoff-block {{ page-break-inside:avoid; margin-top:22px; }}' in source
    assert '<h2 class="signoff-heading">Issue Confirmation / Acceptance</h2>' in source
    assert '<tr><th class="stub" width="9%"></th><th>SE</th><th>ALF/CET/NARI</th></tr>' in source
    assert '<h2 class="signoff-heading">Final Rectification Sign-off</h2>' in source
    assert '<tr><th class="stub" width="9%"></th><th>ALF/CET/NARI</th><th>PDC/DNV</th><th>SE</th></tr>' in source
    assert '<colgroup><col width="9%"><col width="45.5%"><col width="45.5%"></colgroup>' in source
