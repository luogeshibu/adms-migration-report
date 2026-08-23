from pathlib import Path


def _source_text():
    root = Path(__file__).resolve().parents[1]
    return (root / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")


def test_repository_uses_module_tabs_and_standard_mapping():
    text = _source_text()
    assert "self.module_source_tabs = QTabWidget()" in text
    assert "Edit Selected Table Mapping" in text
    assert 'source_type == "standard_reference"' in text
    assert "MODULE_SOURCE_GROUPS" in text


def test_redundant_repository_page_actions_are_removed():
    text = _source_text()
    # The page header itself should not duplicate Refresh Sources / Run Comparison.
    build_page = text[text.index("def _build_import_page"):text.index("def _source_description")]
    assert 'QPushButton("Refresh Sources")' not in build_page
    assert 'QPushButton("Run Comparison")' not in build_page
    assert 'QPushButton("Open Workspace")' in build_page
    assert 'QPushButton("Select Workspace")' in build_page
