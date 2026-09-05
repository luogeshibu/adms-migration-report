from pathlib import Path


def _ui() -> str:
    return (Path(__file__).resolve().parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")


def _method_block(source: str, name: str, next_name: str) -> str:
    start = source.index(f"    def {name}")
    end = source.index(f"    def {next_name}", start)
    return source[start:end]


def test_signal_navigation_highlight_has_explicit_transient_clear_path():
    ui = _ui()
    assert "def _db_smart_navigation_highlight_active" in ui
    assert "def _clear_db_smart_navigation_highlight" in ui
    assert 'self._db_smart_implementation_highlight_keys = set()' in ui
    assert 'self._db_smart_need_action_highlight_keys = set()' in ui
    assert 'item.setBackground(base_fill)' in ui
    assert 'self._clear_db_smart_navigation_highlight(clear_selection=True)' in ui


def test_transient_clear_does_not_force_full_signal_table_rerender():
    ui = _ui()
    block = _method_block(ui, "_clear_db_smart_navigation_highlight", "_sync_db_smart_locator_geometry")
    assert "_render_db_smart_rows" not in block
    assert "table.viewport().update()" in block


def test_set_status_and_comment_can_still_consume_located_signal_selection():
    ui = _ui()
    assert 'self.db_smart_status_btn = QPushButton("Set Status")' in ui
    assert 'getattr(self, "db_smart_status_btn", None)' in ui
    assert 'getattr(self, "db_smart_comment_btn", None)' in ui
    assert "keep_for_action = True" in ui


def test_clear_selection_also_removes_transient_locator_blue():
    ui = _ui()
    block = _method_block(ui, "_clear_db_smart_selection", "_show_db_smart_status_context_menu")
    assert "_clear_db_smart_navigation_highlight(clear_selection=False)" in block
