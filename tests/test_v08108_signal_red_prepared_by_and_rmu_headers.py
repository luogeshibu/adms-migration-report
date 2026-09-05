from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
PDF = (ROOT / "src/migration_report_tool/infrastructure/export/signoff_pdf.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_signal_overview_need_action_is_red_but_closed_mismatch_can_return_green():
    start = UI.index("def _render_db_smart_rmu_list")
    end = UI.index("def _show_db_smart_rmu_overview", start)
    block = UI[start:end]
    assert 'has_need_action = bool(metric["needs_action"])' in block
    assert 'has_unreviewed = bool(metric.get("unreviewed", 0))' in block
    assert 'has_unreviewed_mismatch = bool(metric.get("unreviewed_mismatch", 0))' in block
    assert '(col == 6 and has_unreviewed_mismatch) or (col == 8 and has_need_action)' in block
    assert 'cell.setBackground(QColor("#D92D20"))' in block
    assert 'fill = QColor("#EAF7F0")' in block


def test_need_action_review_badge_is_strong_red():
    assert '"NEEDS ACTION": ("Needs Action", "#D92D20", "#FFFFFF")' in UI


def test_pdf_export_requires_typed_prepared_by():
    start = UI.index("    def export_signoff_pdf(self):")
    end = UI.index("    def ", start + 10)
    block = UI[start:end]
    assert 'QInputDialog.getText' in block
    assert '"Prepared By"' in block
    assert 'Prepared By Required' in block
    assert 'prepared_by=prepared_by' in block
    assert 'prepared_by=self.user_name' not in block


def test_rmu_register_formal_headers_are_restored_while_contents_remain_simple():
    expected = '<th>No.</th><th>RMU</th><th>Modification Item</th><th>Original Value</th><th>Target Value</th><th>Source</th><th>Remarks</th><th>NARI Confirm</th><th>SE/DNV Verify</th>'
    assert expected in PDF
    block = PDF[PDF.index("def _rmu_open_action_snapshot"):PDF.index("def build_site_signoff_snapshot")]
    assert '"adms_db_value"' in block
    assert '"user_value"' in block
    assert '"comments"' in block


def test_release_version():
    assert '__version__ = "0.8.120"' in VERSION
