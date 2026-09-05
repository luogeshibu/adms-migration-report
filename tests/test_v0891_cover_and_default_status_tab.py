from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF_SOURCE = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
UI_SOURCE = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")


def test_cover_title_is_single_line():
    assert 'title_text = "DISTRIBUTION NETWORK DATA MIGRATION REPORT"' in PDF_SOURCE
    assert 'title_lines =' not in PDF_SOURCE


def test_signal_review_defaults_to_status_cmd_when_opening_rmu():
    assert 'self._db_smart_signal_category: str = "STATUS_CMD"' in UI_SOURCE
    start = UI_SOURCE.index('def _show_db_smart_rmu_detail')
    end = UI_SOURCE.index('def _db_smart_category_changed', start)
    block = UI_SOURCE[start:end]
    assert 'if reset_category:' in block
    assert 'self._db_smart_signal_category = "STATUS_CMD"' in block
    assert '"ANALOG" if metrics["analog"] else "STATUS_CMD"' not in block
    assert 'self.db_smart_category_tabs.setCurrentIndex(tab_index)' in block
