from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")


def test_signal_mapping_has_neutral_loading_surface():
    assert 'self.db_smart_loading = QFrame()' in UI
    assert 'self.db_smart_stack.addWidget(self.db_smart_loading)' in UI


def test_signal_mapping_normal_load_does_not_show_unavailable_state():
    start = UI.index('def _start_signal_mapping_module_load')
    end = UI.index('def _start_rmu_review_module_load', start)
    block = UI[start:end]
    loading_pos = block.index('self.db_smart_stack.setCurrentWidget(self.db_smart_loading)')
    worker_pos = block.index('return self._start_process_background_task')
    assert loading_pos < worker_pos


def test_signal_mapping_failure_paths_still_show_unavailable_state():
    start = UI.index('def _start_signal_mapping_module_load')
    end = UI.index('def _start_rmu_review_module_load', start)
    block = UI[start:end]
    # One for confirmed missing inputs and one for worker failure.
    assert block.count('self.db_smart_stack.setCurrentWidget(self.db_smart_empty)') >= 2
