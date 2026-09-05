from pathlib import Path

from migration_report_tool.version import __version__


def test_release_version_08145():
    assert tuple(map(int, __version__.split("."))) >= (0, 8, 145)


def test_source_blocks_have_light_boundary_contract():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert "def set_source_group_boundaries" in ui
    assert '{"SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"}' in ui
    assert "painter.drawLine" in ui
    assert "self.comparison_table.set_source_group_boundaries" in ui


def test_inline_tracker_is_conditional_and_rmu_only():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert "self.comparison_lifecycle_card = lifecycle_card" in ui
    assert "lifecycle_card.setVisible(False)" in ui
    assert 'clean(case.get("entity_type")).upper() == "RMU"' in ui
    assert 'clean(event.get("entity_type")).upper() == "RMU"' in ui
    assert "if not rmu_cases:" in ui
    assert "card.setVisible(False)" in ui
    assert 'title.setText(f"RMU Action Tracking · {rmu}")' in ui


def test_inline_tracker_is_compact_issue_comments_view():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert '"Time", "Case", "Status", "Issue", "Comments", "User"' in ui
    assert 'return " / ".join(f"{name} mismatch"' in ui
    assert 'review_events = list(payload.get("review_events") or [])' in ui
    assert 'event_type == "RESOLUTION_CHANGED"' in ui


def test_light_source_group_visual_contract():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert 'QColor("#D5DEE7"), 1' in ui
    assert '"SE": ("#EEF3F7", "#F8FAFC", "#24364B")' in ui
    assert '"ZENON DB": ("#EEF5F5", "#F8FBFB", "#24364B")' in ui
    assert '"ZENON SLD": ("#EFF4F8", "#F9FBFC", "#24364B")' in ui
    assert '"ADMS DB": ("#F4F2EE", "#FBFAF8", "#24364B")' in ui
    assert '"ADMS SLD": ("#F0F5F1", "#F9FBF9", "#24364B")' in ui
    assert '#8B9BAB' not in ui
