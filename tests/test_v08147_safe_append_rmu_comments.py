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


def _resolution(comment: str, *, submitted: bool) -> dict:
    return {
        "FEEDER": {
            "decision_type": "USE_SOURCE",
            "selected_source": "ZENON DB",
            "selected_value": "RHB-23",
            "normalized_value": "RHB-23",
            "decision_description": "Use ZENON DB feeder RHB-23",
            "customer_comment": comment,
            "customer_comment_submitted": submitted,
        }
    }


def test_release_version_08147():
    assert __version__ == "0.8.147"


def test_manual_review_add_is_append_only_even_when_same_wording_repeated():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            store.append_rmu_manual_review_comment("5977", "现场确认仍需复核", "alice")
            store.append_rmu_manual_review_comment("5977", "现场确认仍需复核", "bob")

            assert store.rmu_manual_review_comment("5977") == "现场确认仍需复核"
            events = [
                event for event in store.rmu_review_events("5977")
                if not event["analysis_field"] and event["event_type"] == "COMMENT_RECORDED"
            ]
            assert [event["comment"] for event in events] == ["现场确认仍需复核", "现场确认仍需复核"]
            assert [event["modified_by"] for event in events] == ["alice", "bob"]
            # Repeating the exact latest wording is a new review event, not a fake value change.
            changes = store.db.execute(
                "SELECT * FROM changes WHERE rmu='5977' AND field_name='rmu_review_comment' ORDER BY id"
            ).fetchall()
            assert len(changes) == 1
        finally:
            store.close()


def test_resolution_save_without_new_comment_preserves_latest_and_does_not_append_note():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        row = _issue_row()
        try:
            store.save_rmu_resolution_decisions(
                "6537", row, _resolution("Customer confirmed Rev.01", submitted=True), "alice"
            )
            first_events = [
                event for event in store.rmu_review_events("6537")
                if event["analysis_field"] == "FEEDER"
            ]
            assert len(first_events) == 1

            # This models reopening the Resolution dialog and saving a Resolution only:
            # the blank New Customer Comment editor keeps the existing latest value.
            store.save_rmu_resolution_decisions(
                "6537", row, _resolution("Customer confirmed Rev.01", submitted=False), "bob"
            )
            saved = store.rmu_resolution_map("6537")["FEEDER"]
            assert saved["customer_comment"] == "Customer confirmed Rev.01"
            second_events = [
                event for event in store.rmu_review_events("6537")
                if event["analysis_field"] == "FEEDER"
            ]
            assert len(second_events) == 1
        finally:
            store.close()


def test_explicit_same_resolution_comment_is_a_new_review_round():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        row = _issue_row()
        try:
            store.save_rmu_resolution_decisions(
                "6537", row, _resolution("Still confirmed by customer", submitted=True), "alice"
            )
            store.save_rmu_resolution_decisions(
                "6537", row, _resolution("Still confirmed by customer", submitted=True), "bob"
            )
            events = [
                event for event in store.rmu_review_events("6537")
                if event["analysis_field"] == "FEEDER"
            ]
            assert len(events) == 2
            assert [event["modified_by"] for event in events] == ["alice", "bob"]
        finally:
            store.close()


def test_ui_uses_read_only_history_and_blank_new_comment_editor():
    ui = Path("src/migration_report_tool/ui/main_window.py").read_text(encoding="utf-8")
    assert "class RMUReviewCommentDialog" in ui
    assert 'QLabel("Latest Saved Comment (read-only)")' in ui
    assert 'QLabel("New Review Comment")' in ui
    assert 'QPushButton("Continue from Latest")' in ui
    assert 'save.setText("Add Comment")' in ui
    assert "self.store.append_rmu_manual_review_comment(" in ui
    assert 'QLabel("Latest Customer Comment (read-only)")' in ui
    assert 'QLabel("New Customer Comment (Optional)")' in ui
    assert 'payload["customer_comment_submitted"] = bool(new_comment)' in ui
    # The old manual dialog populated the editable field with the latest text,
    # which made accidental overwrite/clear too easy.
    start = ui.index("def edit_rmu_manual_review_comment")
    end = ui.index("def set_comparison_review_status", start)
    assert "QInputDialog.getMultiLineText" not in ui[start:end]
