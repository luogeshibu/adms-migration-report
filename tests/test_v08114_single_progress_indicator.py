from pathlib import Path

UI = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
VERSION = Path("src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_version_is_08114():
    assert '__version__ = "0.8.120"' in VERSION


def test_only_one_operational_progress_widget_is_constructed():
    assert 'self.busy_operation_popup = BusyOperationPopup(self.stack)' in UI
    assert 'self.work_progress_frame = QFrame()' not in UI
    assert 'self.work_progress_bar = QProgressBar()' not in UI
    assert 'self.comparison_loading_progress = QProgressBar()' not in UI


def test_background_progress_updates_single_popup():
    block = UI[UI.index('def _start_background_task'):UI.index('def _reopen_active_store_after_worker')]
    assert 'progress_value=0' in block
    assert 'progress_value=value' in block
    assert '_set_work_progress(True' not in block


def test_rmu_incremental_render_reuses_single_popup():
    loading = UI[UI.index('def _set_comparison_loading'):UI.index('def _cancel_comparison_render')]
    batch = UI[UI.index('def _render_comparison_batch'):UI.index('def _finish_comparison_render')]
    assert '"rmu-render"' in loading
    assert '_show_busy_operation' in loading
    assert '_hide_busy_operation' in loading
    assert 'progress_value=(int(round(end * 100 / total)) if total else None)' in batch


def test_busy_popup_supports_determinate_and_indeterminate_modes():
    block = UI[UI.index('class BusyOperationPopup'):UI.index('def signal_review_row_hash')]
    assert 'progress_value: int | None = None' in block
    assert 'self.progress.setRange(0, 0)' in block
    assert 'self.progress.setRange(0, 100)' in block
    assert 'self.progress.setFormat(f"{value}%")' in block
