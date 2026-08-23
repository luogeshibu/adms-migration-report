from pathlib import Path
import unittest


class UISelectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ui = (Path(__file__).resolve().parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")

    def test_spreadsheet_table_uses_extended_cell_selection(self):
        self.assertIn("class SpreadsheetTableWidget(QTableWidget)", self.ui)
        self.assertIn("setSelectionBehavior(QAbstractItemView.SelectItems)", self.ui)
        self.assertIn("setSelectionMode(QAbstractItemView.ExtendedSelection)", self.ui)

    def test_review_tables_do_not_force_row_selection(self):
        self.assertIn("self.comparison_table = SpreadsheetTableWidget", self.ui)
        self.assertIn("self.db_smart_table = SpreadsheetTableWidget", self.ui)
        self.assertNotIn("cellClicked.connect(lambda row, _col: self.comparison_table.selectRow(row))", self.ui)
        self.assertNotIn("cellClicked.connect(lambda row, _col: self.db_smart_table.selectRow(row))", self.ui)

    def test_outside_click_clears_current_selection(self):
        self.assertIn("app.installEventFilter(self)", self.ui)
        self.assertIn("QEvent.Type.MouseButtonPress", self.ui)
        self.assertIn("table.clear_spreadsheet_selection()", self.ui)
        self.assertIn("self.setCurrentIndex(QModelIndex())", self.ui)

    def test_rmu_review_has_frozen_row_locator(self):
        self.assertIn("self.comparison_locator = SpreadsheetTableWidget(0, 4)", self.ui)
        self.assertIn('("locator_no", "No.", 55)', self.ui)
        self.assertIn('("locator_rmu", "RMU", 90)', self.ui)
        self.assertIn('("locator_analysis", "Analysis", 115)', self.ui)
        self.assertIn('("locator_review", "Review", 115)', self.ui)
        self.assertIn("verticalScrollBar().valueChanged.connect(self.comparison_locator.verticalScrollBar().setValue)", self.ui)

    def test_dashboard_separates_rmu_and_signal_kpis(self):
        for text in (
            'MetricCard("Total RMUs"', 'MetricCard("Pass"', 'MetricCard("With Issues"',
            'MetricCard("Total Signals"', 'MetricCard("Matched"', 'MetricCard("Mismatched"',
        ):
            self.assertIn(text, self.ui)
        self.assertIn('QPushButton("Review Signal Mismatches")', self.ui)

    def test_formal_delivery_workflow_is_explicit(self):
        self.assertIn('QPushButton("Run Validation")', self.ui)
        self.assertNotIn('QLabel("MIGRATION REVIEW")', self.ui)
        for text in ('1  Data Sources', '2  Validation', '3  Human Review', '4  Migration Report'):
            self.assertIn(text, self.ui)
        for state in ('SOURCES INCOMPLETE', 'VALIDATION REQUIRED', 'REVIEW PENDING', 'ACTION REQUIRED', 'READY FOR EXPORT'):
            self.assertIn(state, self.ui)

    def test_signal_kpis_reconcile_checked_and_unchecked(self):
        self.assertIn('MetricCard("Checked"', self.ui)
        self.assertIn('MetricCard("Unchecked"', self.ui)
        self.assertIn('Matched / Checked =', self.ui)
        self.assertIn('signal_unchecked = max(0, signal_total - signal_checked)', self.ui)

    def test_project_icons_are_used_for_navigation_and_modules(self):
        self.assertIn('def app_icon(name: str) -> QIcon:', self.ui)
        self.assertIn('btn.setIcon(app_icon(icon_name))', self.ui)
        self.assertIn('icon_label("rmu"', self.ui)
        self.assertIn('icon_label("signal"', self.ui)

    def test_row_tracking_uses_border_only_delegate(self):
        self.assertIn("class RowTrackingDelegate(QStyledItemDelegate)", self.ui)
        self.assertIn("hoverRowChanged = Signal(int)", self.ui)
        self.assertIn("activeRowChanged = Signal(int)", self.ui)
        self.assertIn("painter.drawLine(rect.topLeft(), rect.topRight())", self.ui)
        self.assertIn("painter.drawLine(rect.bottomLeft(), rect.bottomRight())", self.ui)

    def test_signal_mapping_has_locator_too(self):
        self.assertIn("self.db_smart_locator = SpreadsheetTableWidget(0, 3)", self.ui)
        self.assertIn('self.db_smart_locator.setHorizontalHeaderLabels(["RMU", "Type", "Review"])', self.ui)

    def test_dashboard_exception_actions_apply_real_filters(self):
        self.assertIn("self.dashboard_rmu_issues_button.clicked.connect(self.open_dashboard_rmu_issues)", self.ui)
        self.assertIn('self.analysis_combo.setCurrentText("ANY MISMATCH")', self.ui)
        self.assertIn("self.dashboard_signal_mismatch_button.clicked.connect(self.open_dashboard_signal_mismatches)", self.ui)
        self.assertIn('self.db_smart_result_combo.setCurrentText("MISMATCHED")', self.ui)
        self.assertNotIn('b2.clicked.connect(lambda: self.set_page(2))', self.ui)
        self.assertNotIn('b3.clicked.connect(lambda: self.set_page(3))', self.ui)

    def test_review_cells_are_directly_editable_by_double_click(self):
        self.assertIn("self.comparison_locator.cellDoubleClicked.connect(self._edit_comparison_locator_review)", self.ui)
        self.assertIn("self.db_smart_locator.cellDoubleClicked.connect(self._edit_db_smart_locator_review)", self.ui)
        self.assertIn("pass rows set Review directly; issue rows open structured Resolution", self.ui)

    def test_rmu_legend_uses_minimal_color_semantics(self):
        self.assertIn('("#FFF8D8", "Has Issues"', self.ui)
        self.assertIn('("#F7D7D7", "FALSE = mismatch"', self.ui)
        self.assertNotIn('("#FFF0A8", "FEEDER"', self.ui)
        self.assertNotIn('("#D8E9FF", "SMART"', self.ui)
        self.assertNotIn('("#FFDDB8", "TYPE"', self.ui)

    def test_delivery_status_is_live_review_stage(self):
        self.assertIn('display_state = f"REVIEW PENDING · {review_pct}%"', self.ui)
        self.assertIn('display_state = f"ACTION REQUIRED · {needs_action}"', self.ui)
        self.assertNotIn('state = "VALIDATION COMPLETE"', self.ui)
        self.assertIn('Review {reviewed_or_action} / {len(active_rmus)}', self.ui)
        self.assertIn('Resolution {resolved_issue_decisions} / {total_issue_decisions} issues', self.ui)

    def test_signal_mapping_has_explicit_result_filter(self):
        self.assertIn('self.db_smart_result_combo.addItems(["ALL RESULTS", "MATCHED", "MISMATCHED", "UNCHECKED"])', self.ui)
        self.assertIn('result_filter == "MISMATCHED"', self.ui)
        self.assertIn('result_filter == "UNCHECKED"', self.ui)


if __name__ == "__main__":
    unittest.main()
