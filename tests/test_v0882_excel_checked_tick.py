from pathlib import Path


def test_checked_export_uses_tick_not_pass_text():
    source = (Path(__file__).resolve().parents[1] / "src" / "migration_report_tool" / "infrastructure" / "export" / "workbook_exporter.py").read_text(encoding="utf-8")
    assert '("✓" if bool(int(review_record.get("check_passed") or 0)) else "")' in source
    assert '("PASS" if bool(int(review_record.get("check_passed") or 0)) else "")' not in source
    assert '_FONT_CHECKMARK = Font(name="Segoe UI Symbol"' in source
