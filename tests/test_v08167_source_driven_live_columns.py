from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
VERSION = (ROOT / "src/migration_report_tool/version.py").read_text(encoding="utf-8")

def test_version():
    assert '__version__ = "0.8.172"' in VERSION

def test_source_driven_rows_contract():
    assert "one physical source column = one App row" in MAIN
    assert "for header in headers:" in MAIN
    assert "rows.append(('custom'" in MAIN
    assert "rows.append(('built_in'" in MAIN

def test_live_header_watch_contract():
    assert "self._live_header_timer.setInterval(1500)" in MAIN
    assert "self._refresh_if_source_changed" in MAIN
    assert "validate_source_file(" in MAIN

def test_default_app_name_uses_source_header():
    assert "display_name = source_header" in MAIN
    assert "'display_name': header" in MAIN

def test_system_visibility_stays_locked():
    assert "locked = spec.key in self.locked_system_fields" in MAIN
    assert "self._visibility_widget(spec.key, locked=locked)" in MAIN
