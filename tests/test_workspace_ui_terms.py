from pathlib import Path


def test_workspace_ui_terminology():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'QPushButton("Open Workspace")' in text
    assert 'QPushButton("Select Workspace")' in text
    assert 'QLabel("Workspace")' in text
    assert 'QPushButton("Open Root")' not in text
    assert 'QPushButton("Change Root")' not in text
