from pathlib import Path


def _source() -> str:
    root = Path(__file__).resolve().parents[1]
    return (root / "src" / "migration_report_tool" / "infrastructure" / "export" / "signoff_pdf.py").read_text(encoding="utf-8")


def test_cover_title_uses_balanced_single_line_layout():
    source = _source()
    assert 'title_text = "DISTRIBUTION NETWORK DATA MIGRATION REPORT"' in source
    assert 'QFont("Segoe UI", 15)' in source
    assert 'title_width = page_width * 0.88' in source
    assert 'title_height = page_height * 0.040' in source
    assert 'subtitle_top = title_top + page_height * 0.055' in source


def test_revision_fallback_is_version_not_current():
    source = _source()
    assert 'return f"v{__version__}"' in source
    assert 'raw.upper() not in {"CURRENT", "LATEST"}' in source
    assert 'revision_name = _display_revision_name(revision)' in source
    assert 'or "Current"' not in source


def test_body_summary_tables_are_explicit_full_width():
    source = _source()
    assert '<table class="meta" width="100%" cellspacing="0" cellpadding="0">' in source
    assert '<table class="summary" width="100%" cellspacing="0" cellpadding="0">' in source
    assert '.meta, .summary, .grid {{ width:100%; min-width:100%;' in source
    assert '<colgroup><col width="18%"><col width="22%"><col width="18%"><col width="42%"></colgroup>' in source
    assert '<colgroup><col width="23%"><col width="10%"><col width="23%"><col width="10%"><col width="24%"><col width="10%"></colgroup>' in source


def test_cover_remains_english_only():
    source = _source()
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in source)
