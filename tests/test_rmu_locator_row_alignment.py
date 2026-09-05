from pathlib import Path


def test_rmu_locator_mirrors_main_grid_row_height():
    source = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "self.comparison_locator.setRowHeight(r, max(1, self.comparison_table.rowHeight(r)))" in source
    assert "sectionResized.connect(self._mirror_comparison_locator_row_height)" in source
    assert "def _mirror_comparison_locator_row_height" in source
