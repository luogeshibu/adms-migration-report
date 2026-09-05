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

    def test_review_selection_persists_until_explicit_clear(self):
        self.assertIn("app.installEventFilter(self)", self.ui)
        self.assertIn("QEvent.Type.MouseButtonPress", self.ui)
        self.assertIn("if clicked_table is not None:", self.ui)
        self.assertIn("Normal multi-cell review selections keep their existing persistent", self.ui)
        self.assertIn("Empty-space clicks must not destroy a deliberate review", self.ui)
        self.assertIn("self.setCurrentIndex(QModelIndex())", self.ui)

    def test_review_grids_use_standard_ctrl_shift_selection_and_explicit_clear(self):
        self.assertNotIn('QPushButton("Row Select")', self.ui)
        self.assertNotIn("def set_row_selection_mode(self, enabled: bool)", self.ui)
        self.assertIn('QPushButton("Clear Selection")', self.ui)
        self.assertIn("self.comparison_locator.setSelectionMode(QAbstractItemView.ExtendedSelection)", self.ui)
        self.assertIn("self.db_smart_locator.setSelectionMode(QAbstractItemView.ExtendedSelection)", self.ui)
        self.assertIn("self.comparison_locator.itemSelectionChanged.connect(self._sync_comparison_selection_from_locator)", self.ui)
        self.assertIn("self.db_smart_locator.itemSelectionChanged.connect(self._sync_db_smart_selection_from_locator)", self.ui)
        self.assertIn("self.comparison_clear_selection_btn.clicked.connect(self._clear_comparison_selection)", self.ui)
        self.assertIn("self.db_smart_clear_selection_btn.clicked.connect(self._clear_db_smart_selection)", self.ui)

    def test_selected_cells_keep_business_fill_and_use_outer_outline(self):
        self.assertIn("selected = bool(option.state & QStyle.State_Selected)", self.ui)
        self.assertIn("base_option = QStyleOptionViewItem(option)", self.ui)
        self.assertIn("base_option.state &= ~QStyle.State_Selected", self.ui)
        self.assertIn('SELECTION_COLOR = QColor("#2F80ED")', self.ui)
        self.assertIn("top_edge = not self._selected(row - 1, column)", self.ui)
        self.assertIn("bottom_edge = not self._selected(row + 1, column)", self.ui)
        self.assertIn("left_edge = not self._selected(row, column - 1)", self.ui)
        self.assertIn("right_edge = not self._selected(row, column + 1)", self.ui)
        self.assertNotIn("QTableWidget::item:selected", self.ui)

    def test_rmu_review_has_frozen_row_locator(self):
        self.assertIn("self.comparison_locator = SpreadsheetTableWidget(0, 5)", self.ui)
        self.assertIn('("locator_no", "No.", 55)', self.ui)
        self.assertIn('("locator_rmu", "RMU", 90)', self.ui)
        self.assertIn('("locator_checked", "Checked", 74)', self.ui)
        self.assertIn('("locator_analysis", "Analysis", 115)', self.ui)
        self.assertIn('("locator_review", "Review", 115)', self.ui)
        self.assertIn("verticalScrollBar().valueChanged.connect(self.comparison_locator.verticalScrollBar().setValue)", self.ui)

    def test_dashboard_separates_rmu_and_signal_kpis(self):
        for text in (
            'MetricCard("Total RMUs"', 'MetricCard("Pass"', 'MetricCard("With Issues"',
            'MetricCard("ADMS Points"', 'MetricCard("Matched"', 'MetricCard("Mismatched"',
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

    def test_signal_kpis_are_standard_driven_without_unchecked(self):
        self.assertIn('MetricCard("ADMS Points"', self.ui)
        self.assertIn('MetricCard("ZENON Extra"', self.ui)
        self.assertNotIn('MetricCard("Unchecked"', self.ui)
        self.assertIn('ADMS Points {signal_total}', self.ui)

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

    def test_signal_mapping_has_compact_review_locator_in_rmu_detail(self):
        self.assertIn("self.db_smart_locator = SpreadsheetTableWidget(0, 2)", self.ui)
        self.assertIn('("locator_checked", "Checked", 74)', self.ui)
        self.assertIn('("locator_review", "Review", 115)', self.ui)
        self.assertIn('self.db_smart_locator.setHorizontalHeaderLabels(["Checked", "Review"])', self.ui)
        self.assertIn("self.store.update_db_smart_check_passed(", self.ui)
        self.assertIn('self.db_smart_detail_title.setText(f"RMU {metrics[\'rmu\']}")', self.ui)

    def test_signal_mapping_is_rmu_first_with_point_number_categories(self):
        self.assertIn('self.db_smart_rmu_table = QTableWidget(0, 9)', self.ui)
        self.assertIn('"RMU", "Type", "Total", "Analog", "Status/Cmd",', self.ui)
        self.assertIn('self.db_smart_rmu_table.cellClicked.connect(self._open_db_smart_rmu_from_row)', self.ui)
        status_tab = self.ui.index('self.db_smart_category_tabs.addTab("Status / Cmd")')
        analog_tab = self.ui.index('self.db_smart_category_tabs.addTab("Analog")')
        self.assertLess(status_tab, analog_tab)
        self.assertIn('self._db_smart_signal_category = "STATUS_CMD" if index == 0 else "ANALOG"', self.ui)
        self.assertIn('point_no is not None and point_no >= 13000', self.ui)



    def test_signal_mapping_uses_13000_business_boundary(self):
        self.assertIn('point_no is not None and point_no >= 13000', self.ui)
        self.assertNotIn('point_no is not None and point_no >= 1300 else', self.ui)

    def test_signal_mapping_locator_stays_in_pixel_lockstep(self):
        self.assertIn('self.db_smart_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)', self.ui)
        self.assertIn('self.db_smart_locator.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)', self.ui)
        self.assertIn('self.db_smart_locator.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)', self.ui)
        self.assertIn('main_rmu = clean(row.values[0])', self.ui)
        self.assertIn('shown.append((row, status, comments, analysis_result, zenon_only))', self.ui)

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
        self.assertIn("Review defaults to Closed. Double-click for an optional comment", self.ui)

    def test_rmu_pass_defaults_closed_but_three_state_review_is_editable(self):
        self.assertIn('options = ["Unreviewed", "Closed", "Needs Action"]', self.ui)
        self.assertIn('rmu_review_display_status(data, review_record)', self.ui)
        self.assertIn('def edit_rmu_manual_review_comment(', self.ui)
        self.assertIn('manual_review_comment = clean(review_record.get("manual_comment"))', self.ui)
        self.assertIn('Double-click to add a new optional human Review comment', self.ui)

    def test_rmu_legend_uses_minimal_color_semantics(self):
        self.assertIn('("#FFF8D8", "Has Issues"', self.ui)
        self.assertIn('("#F7D7D7", "FALSE = mismatch"', self.ui)
        self.assertNotIn('("#FFF0A8", "FEEDER"', self.ui)
        self.assertNotIn('("#D8E9FF", "SMART"', self.ui)
        self.assertNotIn('("#FFDDB8", "TYPE"', self.ui)

    def test_delivery_status_is_live_review_stage(self):
        self.assertIn('display_state = f"REVIEW PENDING · {review_pct}%"', self.ui)
        self.assertIn('display_state = f"ACTION REQUIRED · {needs_action}"', self.ui)
        self.assertNotIn('VALIDATION INCOMPLETE · {validation_unchecked} UNCHECKED', self.ui)
        self.assertNotIn('state = "VALIDATION COMPLETE"', self.ui)
        self.assertIn('Resolution {resolved_issue_decisions} / {total_issue_decisions} issue decision(s)', self.ui)
        self.assertIn('review_total = rmu_review_total + signal_review_total', self.ui)
        self.assertNotIn('validation_unchecked', self.ui)

    def test_human_review_counts_exceptions_only(self):
        self.assertIn('MetricCard("Closed / Issues"', self.ui)
        self.assertIn('one affected RMU + one mismatched signal', self.ui)
        self.assertIn('mismatch_keys = {', self.ui)
        self.assertIn('signal_review_total = len(mismatch_keys)', self.ui)
        self.assertIn('per-field decisions remain an implementation/detail view inside the RMU', self.ui)
        self.assertIn('STANDARD-driven signal rows are TRUE/FALSE', self.ui)

    def test_dashboard_review_progress_uses_business_objects(self):
        self.assertIn('MetricCard("Closed / Issues"', self.ui)
        self.assertIn('rmu_review_total = rmu_issues', self.ui)
        self.assertIn('visible_status = rmu_review_display_status(row, review_record)', self.ui)
        self.assertIn('f"RMU Review: {rmu_reviewed} / {rmu_review_total}', self.ui)
        self.assertIn('f"Human Review · RMU {rmu_reviewed}/{rmu_review_total} · "', self.ui)
        self.assertIn('f"Signal {signal_reviewed}/{signal_review_total}"', self.ui)
        self.assertIn('signal_processed_total = signal_reviewed + signal_required_needs', self.ui)
        self.assertIn('signal_closed = signal_review_counts["CLOSED"]', self.ui)

    def test_review_workflow_exposes_only_three_states_and_zenon_only_defaults_closed(self):
        self.assertIn('"UNREVIEWED": ("Unreviewed", "#F3F4F6"', self.ui)
        self.assertIn('"CLOSED": ("Closed", "#2E7D32"', self.ui)
        self.assertIn('"NEEDS ACTION": ("Needs Action", "#D92D20"', self.ui)
        self.assertNotIn('"NOT REQUIRED": ("Not Required"', self.ui)
        self.assertNotIn('"REVIEWED": ("Reviewed"', self.ui)
        self.assertIn('signal_row_is_zenon_only(row)', self.ui)
        self.assertIn('if analysis_result == "TRUE" or zenon_only:', self.ui)


    def test_signal_comments_are_always_neutral_white(self):
        self.assertIn('item.setBackground(QColor("#FFFFFF"))', self.ui)
        self.assertIn('Double-click to choose ADD / MODIFY / DELETE and enter the required remark', self.ui)

    def test_review_color_is_distinct_from_automatic_validation(self):
        self.assertIn('"UNREVIEWED": ("Unreviewed", "#F3F4F6", "#475467")', self.ui)
        self.assertIn('"CLOSED": ("Closed", "#2E7D32", "#FFFFFF")', self.ui)
        self.assertIn('"NEEDS ACTION": ("Needs Action", "#D92D20", "#FFFFFF")', self.ui)
        self.assertIn('color is isolated to the Review cell', self.ui)
        self.assertNotIn('"REVIEWED": ("Reviewed"', self.ui)


    def test_rmu_post_edit_reselection_preserves_horizontal_viewport(self):
        start = self.ui.index("    def _select_comparison_rmu(self, rmu: str):")
        end = self.ui.index("    def refresh_changes(self):", start)
        block = self.ui[start:end]
        self.assertIn("old_h = table.horizontalScrollBar().value()", block)
        self.assertIn("visible_col = table.columnAt(0)", block)
        self.assertIn("table.scrollToItem(active_item, QAbstractItemView.EnsureVisible)", block)
        self.assertIn("table.horizontalScrollBar().setValue(old_h)", block)
        self.assertIn("QTimer.singleShot(0", block)
        self.assertNotIn("QAbstractItemView.PositionAtCenter", block)


    def test_module_navigation_reuses_loaded_signal_mapping(self):
        self.assertIn('Navigation must be cheap: QStackedWidget keeps every page alive', self.ui)
        self.assertIn('self.refresh_db_smart_report(force=False, rescan=False)', self.ui)
        self.assertIn('and self._db_smart_report_site.casefold() == site_name.casefold()', self.ui)
        self.assertIn('if not self._db_smart_ui_ready:', self.ui)
        self.assertIn('self._present_db_smart_report(self.db_smart_report)', self.ui)
        self.assertNotIn('self.refresh_site_repository()\n        elif index == 3', self.ui)

    def test_review_search_can_target_exact_table_columns(self):
        self.assertIn('self.comparison_search_field = QComboBox()', self.ui)
        self.assertIn('self.db_smart_search_field = QComboBox()', self.ui)
        self.assertIn('self.comparison_search_field.addItem("All Columns", "*")', self.ui)
        self.assertIn('self.db_smart_search_field.addItem("All Columns", "*")', self.ui)
        self.assertIn('searchable = clean(data.get(search_field))', self.ui)
        self.assertIn('column_keys = [clean(item[0])', self.ui)
        self.assertIn('self._db_smart_search_text(row, status, comments, str(search_field))', self.ui)

    def test_search_refresh_restores_selection_by_business_keys(self):
        self.assertIn('def _capture_comparison_selection_keys', self.ui)
        self.assertIn('def _restore_comparison_selection_keys', self.ui)
        self.assertIn('def _capture_db_smart_selection_keys', self.ui)
        self.assertIn('def _restore_db_smart_selection_keys', self.ui)
        self.assertIn('row_key + column key', self.ui)

    def test_search_is_debounced_for_large_review_tables(self):
        self.assertIn('self._comparison_search_timer.setInterval(180)', self.ui)
        self.assertIn('self._db_smart_search_timer.setInterval(180)', self.ui)

    def test_signal_mapping_has_explicit_result_filter(self):
        self.assertIn('self.db_smart_result_combo.addItems(["ALL RESULTS", "MATCHED", "MISMATCHED", "ZENON EXTRA"])', self.ui)
        self.assertIn('result_filter == "MISMATCHED"', self.ui)
        self.assertIn('result_filter == "ZENON EXTRA"', self.ui)


    def test_review_pages_have_show_all_filter_reset(self):
        self.assertIn('self.comparison_show_all_btn = QPushButton("Show All")', self.ui)
        self.assertIn('self.db_smart_show_all_btn = QPushButton("Show All")', self.ui)
        self.assertIn('def _show_all_comparison(self)', self.ui)
        self.assertIn('def _show_all_db_smart(self)', self.ui)
        self.assertIn('self.rmu_review_filter_combo.setCurrentIndex(0)', self.ui)
        self.assertIn('self.db_smart_result_combo.setCurrentIndex(0)', self.ui)

    def test_source_import_is_incremental_and_multi_file(self):
        self.assertIn('choose_source_file_for_table', self.ui)
        self.assertIn('table.setCellWidget(row, 1, source_button)', self.ui)
        self.assertNotIn('add_files_btn = QPushButton("Import Source File...")', self.ui)
        self.assertIn('QFileDialog.getOpenFileNames(', self.ui)
        self.assertIn('def add_source_files(self):', self.ui)
        self.assertIn('self.store.mark_manual_source_override(source_type, selected)', self.ui)
        self.assertIn('self.store.config["validation_required_after_source_import"] = True', self.ui)
        self.assertNotIn('advanced_btn = QPushButton("Advanced Manual Import")', self.ui)


    def test_review_navigation_shows_progress_before_heavy_preparation(self):
        self.assertIn('self._show_busy_operation("nav-review-load", title, detail)', self.ui)
        self.assertIn('QTimer.singleShot(0, lambda idx=index: self._continue_review_navigation(idx))', self.ui)
        self.assertIn('QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)', self.ui)

    def test_signal_type_warning_colors_only_rmu_locator_cell(self):
        block = self.ui[self.ui.index("def _render_db_smart_rmu_list"):self.ui.index("def _show_db_smart_rmu_overview")]
        self.assertIn('if col == 0:', block)
        self.assertIn('if has_type_issue:', block)
        self.assertIn('cell.setBackground(QColor("#F3E8FF"))', block)
        self.assertIn('cell.setToolTip(type_issue_tooltip)', block)
        self.assertNotIn('fill = QColor("#F3E8FF")', block)

    def test_source_version_picker_auto_latest_and_manual_pin_priority(self):
        self.assertIn('AUTO · Latest published version', self.ui)
        self.assertIn('if no published V exists, use the configured Source Detection Rules/base filename', self.ui)
        self.assertIn('PIN: use the exact V version you select', self.ui)
        self.assertIn('MANUAL: browse any physical file; explicit user selection has the highest priority', self.ui)

if __name__ == "__main__":
    unittest.main()

def test_v0838_source_discovery_and_responsive_overview_contract():
    ui = Path('src/migration_report_tool/ui/main_window.py').read_text(encoding='utf-8')
    assert '"App Table", "Source File", "File Path",' in ui
    assert '"Fields Used in This Module (App ← Source)", "Status"' in ui
    assert 'mapping_btn = QPushButton("Map Fields...")' in ui
    assert 'self.unmapped_files_label = QLabel("Unmapped Files")' in ui
    assert 'self.assign_unmapped_btn = QPushButton("Assign Source...")' in ui
    assert 'detection_title = QLabel("Source Detection Rules")' in ui
    assert 'content.setMinimumHeight(760)' in ui
    assert 'self.dashboard_scroll = scroll' in ui


def test_v0838_signal_locator_reserves_main_horizontal_scrollbar_height():
    ui = Path('src/migration_report_tool/ui/main_window.py').read_text(encoding='utf-8')
    assert 'self.db_smart_locator_scroll_spacer' in ui
    assert 'def _sync_db_smart_locator_geometry' in ui
    assert 'reserve = hbar.sizeHint().height() if hbar.maximum() > hbar.minimum() else 0' in ui
    assert 'self.db_smart_table.setRowHeight(visual_row, 32)' in ui
    assert 'self.db_smart_locator.setRowHeight(visual_row, 32)' in ui


def test_v0847_any_review_cell_can_set_three_state_status():
    ui = Path('src/migration_report_tool/ui/main_window.py').read_text(encoding='utf-8')
    assert 'self.comparison_table.setContextMenuPolicy(Qt.CustomContextMenu)' in ui
    assert 'self.db_smart_table.setContextMenuPolicy(Qt.CustomContextMenu)' in ui
    assert 'menu.addAction("Mark Unreviewed"' in ui
    assert 'menu.addAction("Mark Closed"' in ui
    assert 'menu.addAction("Needs Action"' in ui
    assert 'set_comparison_review_status("CLOSED")' in ui
    assert 'set_db_smart_review_status("CLOSED")' in ui
    assert 'review_btn = QPushButton("Set Status")' in ui
    assert 'self.db_smart_status_btn = QPushButton("Set Status")' in ui
    assert '"CLOSED": ("Closed", "#2E7D32"' in ui
    assert '"REVIEWED": ("Reviewed"' not in ui
