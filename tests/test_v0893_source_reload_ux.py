from pathlib import Path

ROOT = Path(__file__).parents[1]
MAIN = (ROOT / 'src' / 'migration_report_tool' / 'ui' / 'main_window.py').read_text(encoding='utf-8')
REPO = (ROOT / 'src' / 'migration_report_tool' / 'infrastructure' / 'filesystem' / 'site_repository.py').read_text(encoding='utf-8')
VERSION = (ROOT / 'src' / 'migration_report_tool' / 'version.py').read_text(encoding='utf-8')


def _method(source: str, name: str, next_name: str) -> str:
    start = source.index(f'    def {name}(')
    end = source.index(f'    def {next_name}(', start)
    return source[start:end]


def test_run_validation_force_rereads_all_active_sources_with_progress():
    job = MAIN[MAIN.index('def _background_validation_job'):MAIN.index('def _background_reload_live_sources_job')]
    run = _method(MAIN, 'run_comparison', '_selected_comparison_rmus')
    assert 'sync_site_to_project(store, site, force_all=True)' in job
    assert 'Re-reading all active source files' in job
    assert 'Running RMU validation' in job
    assert 'Running Signal Mapping validation' in job
    assert 'with_progress=True' in run
    assert 'lambda progress: _background_validation_job' in run


def test_source_selection_rereads_only_selected_table():
    choose = _method(MAIN, 'choose_source_file_for_table', 'select_active_source_file')
    pin = _method(MAIN, 'select_active_source_file', 'assign_unmapped_source')
    assert 'refresh_sources_and_reload()' not in choose
    assert 'refresh_sources_and_reload()' not in pin
    assert '_reload_live_sources(' in choose
    assert '[source_type]' in choose
    assert '_reload_live_sources(' in pin
    assert '[source_type]' in pin
    assert 'import_source(self.store, source_type, selected_path)' not in choose


def test_live_source_watcher_is_stat_only_and_non_intrusive():
    detect = _method(MAIN, '_detect_live_source_changes', '_check_live_source_changes')
    watch = _method(MAIN, '_check_live_source_changes', '_reload_live_sources')
    assert 'deep=False' in detect
    assert '.stat()' in detect
    assert 'validate_source_file' not in detect
    assert 'read_csv_rows' not in detect
    assert 'activeModalWidget()' in watch
    assert '_comparison_render_in_progress' in watch
    assert 'source-auto-refresh' in watch
    assert 'setInterval(5000)' in MAIN


def test_source_io_uses_single_shared_progress_popup():
    assert 'self.work_progress_frame' not in MAIN
    assert 'self.work_progress_bar' not in MAIN
    assert 'progressed = Signal(int, str)' in MAIN
    assert 'popup_key = f"task:{key}"' in MAIN
    assert 'progress_value=value' in MAIN


def test_validation_deep_scans_only_active_site_not_every_workspace_site():
    helper = MAIN[MAIN.index('def _load_repository_site'):MAIN.index('def _background_resolution_save_job')]
    assert 'discover_site_sources(site_dir, deep=deep)' in helper
    assert 'scan_repository(root, deep=True)' not in helper


def test_sync_supports_force_all_and_persists_live_metadata():
    block = REPO[REPO.index('def sync_site_to_project'):]
    assert 'force_all: bool = False' in block
    assert 'force_all or key in forced_keys' in block
    assert 'live_source_metadata' in block


def test_version_bumped_to_0893():
    assert '__version__ = "0.8.120"' in VERSION
