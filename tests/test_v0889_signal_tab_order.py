from pathlib import Path


def _source() -> str:
    return (Path(__file__).resolve().parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")


def test_status_cmd_tab_is_left_of_analog_and_index_mapping_is_consistent():
    source = _source()
    assert source.index('self.db_smart_category_tabs.addTab("Status / Cmd")') < source.index('self.db_smart_category_tabs.addTab("Analog")')
    assert 'self._db_smart_signal_category = "STATUS_CMD" if index == 0 else "ANALOG"' in source
    assert 'tab_index = 1 if self._db_smart_signal_category == "ANALOG" else 0' in source
    assert 'self.db_smart_category_tabs.setTabText(0, f"Status / Cmd ({metrics[\'status_cmd\']})")' in source
    assert 'self.db_smart_category_tabs.setTabText(1, f"Analog ({metrics[\'analog\']})")' in source
    assert source.count('setCurrentIndex(1 if target_category == "ANALOG" else 0)') == 2


def test_signal_business_boundary_remains_unchanged():
    source = _source()
    assert 'point_no is not None and point_no >= 13000' in source
