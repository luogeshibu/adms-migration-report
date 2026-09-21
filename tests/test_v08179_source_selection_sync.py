from __future__ import annotations

import unittest
from pathlib import Path

from migration_report_tool.version import __version__


class TestV08179SourceSelectionSync(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "0.8.215")

    def test_source_switch_does_not_refresh_list_while_qt_delivers_selection_signal(self):
        source = Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py"
        text = source.read_text(encoding="utf-8")
        start = text.index("    def _source_selection_changed")
        end = text.index("    def _load_source_editor", start)
        block = text[start:end]
        self.assertIn("_save_source_editor(previous_id, refresh_ui=False)", block)
        self.assertNotIn("_save_current_source_editor()", block)
        self.assertIn("self._current_source_id = source_id", block)
        self.assertIn("self._load_source_editor(self._source_by_id(source_id))", block)

    def test_programmatic_list_restore_happens_before_signals_unblock(self):
        source = Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py"
        text = source.read_text(encoding="utf-8")
        start = text.index("    def _refresh_source_list")
        end = text.index("    def _source_selection_changed", start)
        block = text[start:end]
        restore = block.index("self.source_list.setCurrentRow(restore)")
        unblock = block.index("self.source_list.blockSignals(False)")
        self.assertLess(restore, unblock)


if __name__ == "__main__":
    unittest.main()
