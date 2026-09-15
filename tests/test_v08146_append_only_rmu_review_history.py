import tempfile
from pathlib import Path

from migration_report_tool.storage import ProjectStore
from migration_report_tool.version import __version__


def _issue_row(rmu: str = "6537") -> dict:
    return {
        "rmu": rmu,
        "analysis_name": "TRUE",
        "analysis_feeder": "FALSE",
        "analysis_smart": "TRUE",
        "analysis_type": "TRUE",
        "analysis_ip": "TRUE",
        "analysis_feeder_detail": "SE BWD2-23 vs ZENON DB RHB-23",
        "resolution_candidates": {
            "FEEDER": [
                {"source": "SE", "value": "BWD2-23", "normalized": "BWD2-23"},
                {"source": "ZENON DB", "value": "RHB-23", "normalized": "RHB-23"},
                {"source": "ADMS DB", "value": "JED-CTL-BWD2-AH323", "normalized": "BWD2-23"},
            ]
        },
    }


def _decision(comment: str) -> dict:
    return {
        "FEEDER": {
            "decision_type": "USE_SOURCE",
            "selected_source": "ZENON DB",
            "selected_value": "RHB-23",
            "normalized_value": "RHB-23",
            "decision_description": "Use ZENON DB feeder RHB-23",
            "customer_comment": comment,
        }
    }


def test_release_and_schema_12_contract():
    assert tuple(map(int, __version__.split("."))) >= (0, 8, 146)
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            assert store.project_schema_version() == 12
            resolution_cols = {row[1] for row in store.db.execute("PRAGMA table_info(rmu_resolutions)")}
            assert "customer_comment" in resolution_cols
            assert store.db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rmu_review_events'"
            ).fetchone()
        finally:
            store.close()


def test_pass_rmu_comments_are_append_only_before_need_action_and_revealed_later():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            store.update_rmu_manual_review_comment("5977", "First field review note", "alice")
            store.update_rmu_manual_review_comment("5977", "Second review after RMU modification", "bob")

            # Comments alone never fabricate a formal Needs Action case.
            assert store.issue_cases(entity_type="RMU", entity_key="5977") == []
            notes = store.rmu_review_events("5977")
            assert [row["comment"] for row in notes] == [
                "First field review note",
                "Second review after RMU modification",
            ]
            assert all(row["case_id"] is None for row in notes)
            assert store.rmu_manual_review_comment("5977") == "Second review after RMU modification"

            # Once a real Needs Action case exists, earlier notes remain intact.
            store.update_rmu_review_status("5977", "NEEDS ACTION", "bob", "Manual site issue discovered")
            lifecycle = store.rmu_full_lifecycle("5977")
            assert lifecycle["rmu_case_count"] == 1
            assert lifecycle["review_event_count"] == 2
            assert [row["comment"] for row in lifecycle["review_events"]] == [
                "First field review note",
                "Second review after RMU modification",
            ]
        finally:
            store.close()


def test_resolution_choice_and_customer_comment_are_independent_and_comment_history_appends():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        row = _issue_row()
        try:
            store.save_comparison([row])
            store.update_rmu_review_status(
                "6537", "NEEDS ACTION", "alice", "Reviewer explicitly opened Needs Action"
            )
            status1, _ = store.save_rmu_resolution_decisions(
                "6537", row, _decision("Confirmed by customer drawing Rev.01"), "alice"
            )
            first = store.rmu_resolution_map("6537")["FEEDER"]
            assert first["decision_type"] == "USE_SOURCE"
            assert first["selected_source"] == "ZENON DB"
            assert first["selected_value"] == "RHB-23"
            assert first["customer_comment"] == "Confirmed by customer drawing Rev.01"
            assert status1 == "NEEDS ACTION"  # explicit Review Status is preserved

            status2, _ = store.save_rmu_resolution_decisions(
                "6537", row, _decision("Rechecked after modification; customer still confirms RHB-23"), "bob"
            )
            second = store.rmu_resolution_map("6537")["FEEDER"]
            assert second["decision_type"] == "USE_SOURCE"
            assert second["selected_source"] == "ZENON DB"
            assert second["selected_value"] == "RHB-23"
            assert second["customer_comment"] == "Rechecked after modification; customer still confirms RHB-23"
            assert status2 == "NEEDS ACTION"

            notes = [
                row for row in store.rmu_review_events("6537")
                if row["analysis_field"] == "FEEDER"
            ]
            assert [row["comment"] for row in notes] == [
                "Confirmed by customer drawing Rev.01",
                "Rechecked after modification; customer still confirms RHB-23",
            ]
            assert all(row["case_no"] == 1 for row in notes)
            assert all(row["review_status"] == "NEEDS ACTION" for row in notes)
        finally:
            store.close()


def test_ui_contract_has_independent_customer_comment_and_conditional_tracker():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert 'QLabel("New Customer Comment (Optional)")' in ui
    assert 'payload["customer_comment"]' in ui
    assert 'self.customer_comments: dict[str, QTextEdit]' in ui
    assert 'review_events = list(payload.get("review_events") or [])' in ui
    assert 'if not rmu_cases:' in ui
    assert 'card.setVisible(False)' in ui
    assert 'Comment cleared (previous history retained)' in ui
