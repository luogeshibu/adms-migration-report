from pathlib import Path

ROOT = Path(__file__).parents[1]
MAIN = (ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src" / "migration_report_tool" / "version.py").read_text(encoding="utf-8")


def _method(name: str, next_name: str) -> str:
    start = MAIN.index(f"    def {name}(")
    end = MAIN.index(f"    def {next_name}(", start)
    return MAIN[start:end]


def test_signal_mapping_auto_loads_on_first_module_open():
    navigation = _method("set_page", "_mark_site_pages_dirty")
    assert "if index == 3 and self.db_smart_report is None:" in navigation
    assert "self._dirty_pages.add(3)" in navigation
    page = _method("_refresh_page_if_dirty", "_start_signal_mapping_module_load")
    assert "self._start_signal_mapping_module_load()" in page
    assert "self.refresh_db_smart_report(force=False, rescan=False)" in page
    lazy = _method("_start_signal_mapping_module_load", "_start_rmu_review_module_load")
    assert "module-signal-load" in lazy
    assert "_background_signal_mapping_module_job" in lazy
    assert "with_progress=True" in lazy
    assert "Loading Signal Mapping Review automatically" in lazy


def test_lazy_signal_job_reads_only_signal_inputs_and_restores_reviews():
    start = MAIN.index("def _background_signal_mapping_module_job")
    end = MAIN.index("def _background_rmu_review_module_job", start)
    job = MAIN[start:end]
    assert '_worker_effective_source_path(site, store, "ioa")' in job
    assert '_worker_effective_source_path(site, store, "adms_sld")' in job
    assert "build_signal_mapping_report(" in job
    assert "sync_db_smart_review_fingerprints" in job
    assert "build_comparison(store)" not in job
    assert "STANDARD → ADMS → ZENON" in job


def test_lazy_signal_resolution_honors_pins_manual_and_cached_sources():
    start = MAIN.index("def _worker_effective_source_path")
    end = MAIN.index("def _background_signal_mapping_module_job", start)
    helper = MAIN[start:end]
    assert "selected_repository_source_path" in helper
    assert "manual_source_overrides" in helper
    assert "site.sources.get" in helper
    assert "store.source_path" in helper


def test_rmu_review_auto_builds_only_when_cache_is_empty():
    page = _method("_refresh_page_if_dirty", "_start_signal_mapping_module_load")
    assert "if self.store and not self.store.rows():" in page
    assert "self._start_rmu_review_module_load()" in page
    lazy = _method("_start_rmu_review_module_load", "_setup_state")
    assert "module-rmu-load" in lazy
    assert "_background_rmu_review_module_job" in lazy
    assert "with_progress=True" in lazy


def test_sync_refresh_mapping_uses_effective_pinned_sources_too():
    live = _method("_live_signal_mapping_sources", "_present_db_smart_report")
    assert 'for key in ("ioa", "adms_sld")' in live
    assert "self._effective_site_source_path(key)" in live


def test_lazy_module_tasks_share_source_pipeline_busy_gate():
    busy = _method("_source_pipeline_busy", "_set_work_progress")
    assert '"module-signal-load"' in busy
    assert '"module-rmu-load"' in busy


def test_version_bumped_to_08107():
    assert '__version__ = "0.8.120"' in VERSION
