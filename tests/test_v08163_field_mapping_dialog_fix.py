from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py"


def test_release_version():
    version_text = (ROOT / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")
    assert '__version__ = "0.8.163"' in version_text


def test_no_wheel_combo_class_is_defined_before_mapping_dialog():
    text = MAIN.read_text(encoding="utf-8")
    tree = ast.parse(text)
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    assert "NoWheelComboBox" in classes
    assert "SourceMappingDialog" in classes
    assert classes["NoWheelComboBox"].lineno < classes["SourceMappingDialog"].lineno


def test_source_combo_constructs_the_defined_no_wheel_combo():
    text = MAIN.read_text(encoding="utf-8")
    assert "def _source_combo(" in text
    assert "combo = NoWheelComboBox()" in text
    assert "class NoWheelComboBox(QComboBox):" in text
