from pathlib import Path


def test_rmu_review_navigation_defers_heavy_refresh_until_page_can_paint():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    block = ui[ui.index("def set_page"):ui.index("def _mark_site_pages_dirty")]
    assert "index == 2 and index in self._dirty_pages" in block
    assert "self._set_comparison_loading(True)" in block
    assert "QTimer.singleShot(0" in block


def test_rmu_review_grid_is_rendered_in_event_loop_batches():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "self._comparison_render_batch_size = 20" in ui
    assert "def _render_comparison_batch" in ui
    assert "def _finish_comparison_render" in ui
    block = ui[ui.index("def _render_comparison_batch"):ui.index("def _finish_comparison_render")]
    assert "QTimer.singleShot(0" in block
    assert "_populate_comparison_locator_row" in block


def test_rmu_review_uses_shared_loading_progress_surface():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    page_block = ui[ui.index("def _build_comparison_page"):ui.index("def _mirror_comparison_locator_row_height")]
    assert "comparison_loading_card" not in page_block
    assert "comparison_loading_progress" not in page_block
    loading = ui[ui.index("def _set_comparison_loading"):ui.index("def _cancel_comparison_render")]
    assert 'self._show_busy_operation("rmu-render"' in loading
    assert 'self._hide_busy_operation("rmu-render")' in loading
