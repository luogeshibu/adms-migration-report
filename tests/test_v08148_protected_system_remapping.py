from pathlib import Path

from migration_report_tool.version import __version__


def _ui_source() -> str:
    return Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")


def test_release_version_08148():
    assert __version__ == "0.8.148"


def test_system_mapping_is_protected_by_default_and_requires_explicit_unlock():
    ui = _ui_source()
    assert "self.system_mapping_unlocked = False" in ui
    assert 'QPushButton("Unlock System Mappings...")' in ui
    assert '"Unlock System Mappings"' in ui
    assert "SYSTEM · LOCKED fields are used by system-level Analysis, matching, and validation calculations." in ui
    assert "combo.setEnabled(self.system_mapping_unlocked)" in ui
    assert '"SYSTEM · UNLOCKED" if locked and self.system_mapping_unlocked' in ui


def test_system_remap_requires_second_confirmation_at_save():
    ui = _ui_source()
    assert "def _changed_locked_mapping_keys" in ui
    assert "def _confirm_locked_mapping_save" in ui
    assert '"Confirm System Mapping Changes"' in ui
    assert "These mappings feed system-level Analysis and validation and are shared across ALL sites" in ui
    assert "changed_locked = self._changed_locked_mapping_keys()" in ui
    assert "if changed_locked and not self._confirm_locked_mapping_save(changed_locked):" in ui


def test_reset_auto_mapping_respects_protected_system_fields():
    ui = _ui_source()
    start = ui.index("def _reset_all_to_auto")
    end = ui.index("def _set_save_state", start)
    block = ui[start:end]
    assert "key in self.locked_system_fields and not self.system_mapping_unlocked" in block
    assert "Protected SYSTEM mappings were left unchanged" in block


def test_app_column_label_remains_presentation_only_while_source_relationship_is_protected():
    ui = _ui_source()
    assert "App Column display names remain editable because renaming is presentation-only" in ui
    assert "only the Source Field relationship that feeds system calculations is protected" in ui
