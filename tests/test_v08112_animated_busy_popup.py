from pathlib import Path

UI = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
VERSION = Path("src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_version_is_08112():
    assert '__version__ = "0.8.120"' in VERSION


def test_shared_animated_busy_popup_exists():
    assert "class BusyOperationPopup(QFrame):" in UI
    assert 'self.progress.setRange(0, 0)' in UI
    assert 'self.setAttribute(Qt.WA_TransparentForMouseEvents, True)' in UI
    assert 'self.busy_operation_popup = BusyOperationPopup(self.stack)' in UI
    assert 'def _show_busy_operation(' in UI
    assert 'progress_value: int | None = None' in UI
    assert 'def _hide_busy_operation(self, key: str)' in UI


def test_rmu_show_all_yields_before_full_render_and_closes_when_done():
    assert '"rmu-show-all"' in UI
    assert '"Loading all RMU rows..."' in UI
    assert 'QTimer.singleShot(0, self._complete_show_all_comparison)' in UI
    assert 'self._hide_busy_operation("rmu-show-all")' in UI


def test_signal_show_all_has_animated_feedback():
    assert '"signal-show-all"' in UI
    assert '"Loading all signal rows..."' in UI
    assert 'QTimer.singleShot(0, self._complete_show_all_db_smart)' in UI
    assert 'self.db_smart_show_all_btn.setEnabled(False)' in UI
    assert 'self.db_smart_show_all_btn.setEnabled(True)' in UI


def test_background_progress_jobs_feed_popup_without_blocking_auto_refresh():
    assert 'popup_key = f"task:{key}"' in UI
    assert 'show_popup = bool(with_progress and key != "source-auto-refresh")' in UI
    assert 'self._update_busy_operation(' in UI
    assert 'detail=f"{stage_text} · {int(value)}%"' in UI


def test_refresh_mapping_uses_worker_feedback_path():
    assert 'self.db_smart_refresh_btn.clicked.connect(self._refresh_db_smart_mapping_with_feedback)' in UI
    assert 'def _refresh_db_smart_mapping_with_feedback(self) -> None:' in UI
    assert 'self._start_signal_mapping_module_load()' in UI
