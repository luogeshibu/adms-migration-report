from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
PATHS = (ROOT / "src/migration_report_tool/utils/paths.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")


def test_first_run_setup_dialog_covers_source_and_project_locations():
    assert 'class InitialSetupDialog(QDialog):' in UI
    assert 'Source Workspace (read-only)' in UI
    assert 'Project Data Storage (writable)' in UI
    assert 'Save & Continue' in UI
    assert 'Configure Later' in UI
    assert 'These locations are remembered for future launches and can be changed later in Settings.' in UI


def test_startup_only_prompts_when_configuration_is_missing():
    block = UI[UI.index('    def _maybe_show_initial_setup'):UI.index('    def _load_initial_workspace')]
    assert 'self._setup_state()' in block
    assert 'onboarding/initial_setup_seen_v1' in block
    assert 'if not state["missing"]:' in block
    assert 'self.open_setup_dialog()' in block


def test_nonblocking_guidance_remains_on_dashboard_and_settings():
    assert 'self.setup_guidance_card' in UI
    assert 'Configure Now' in UI
    assert 'Open Settings' in UI
    assert 'Workspace & Project Data Setup' in UI
    assert 'Open Setup Guide' in UI
    assert 'self.setup_guidance_card.setVisible(bool(missing))' in UI


def test_setup_persists_both_paths_and_previous_configuration_is_reused():
    block = UI[UI.index('    def open_setup_dialog'):UI.index('    def _maybe_show_initial_setup')]
    assert 'set_project_data_root(new_project)' in block
    assert 'save_repository_root(self.repository_root)' in block
    assert 'self.settings.setValue("onboarding/initial_setup_seen_v1", True)' in block
    assert 'load_repository_root()' in UI
    assert 'project_data_root_is_configured' in UI


def test_project_data_setup_distinguishes_empty_default_from_established_history():
    assert 'def project_data_root_is_configured() -> bool:' in PATHS
    assert 'any(workspace.glob("*/project.db"))' in PATHS
    assert 'MIGRATION_REPORT_TOOL_PROJECT_DATA_ROOT' in PATHS


def test_setup_requires_separate_source_and_project_folders():
    dialog = UI[UI.index('class InitialSetupDialog'):UI.index('class MainWindow')]
    assert 'project_resolved.relative_to(source_resolved)' in dialog
    assert 'source_resolved.relative_to(project_resolved)' in dialog
    assert 'Use separate folders' in dialog


def test_version_bumped_to_0897():
    assert '__version__ = "0.8.120"' in VERSION
