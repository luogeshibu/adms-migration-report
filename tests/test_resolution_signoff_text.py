from migration_report_tool.domain.analysis.resolution_text import (
    build_resolution_description,
    compact_resolution_text,
    resolution_display_text,
)


def test_feeder_resolution_is_customer_facing_and_actionable():
    text = build_resolution_description(
        rmu="17233",
        field="FEEDER",
        decision_type="USE_SOURCE",
        selected_source="ZENON SLD XML",
        selected_value="JED-NTH-ABH-15",
        normalized_value="ABH-15",
    )
    assert "RMU 17233" in text
    assert "ZENON SLD XML" in text
    assert "JED-NTH-ABH-15" in text
    assert "approved feeder assignment" in text
    assert "Align the feeder value" in text
    assert "re-run Validation" in text


def test_needs_action_and_exception_are_explicit_for_signoff():
    needs_action = build_resolution_description(
        rmu="17233", field="TYPE", decision_type="NEEDS_ACTION"
    )
    exception = build_resolution_description(
        rmu="17233", field="TYPE", decision_type="ACCEPT_EXCEPTION"
    )
    assert "Further corrective action is required" in needs_action
    assert "Needs Action" in needs_action
    assert "approved exception" in exception
    assert "formal sign-off report" in exception


def test_persisted_description_wins_and_compact_text_keeps_value():
    record = {
        "rmu": "17233",
        "analysis_field": "FEEDER",
        "decision_type": "USE_SOURCE",
        "selected_source": "ZENON SLD XML",
        "selected_value": "JED-NTH-ABH-15",
        "normalized_value": "ABH-15",
        "decision_description": "Frozen customer wording",
    }
    assert resolution_display_text(record) == "Frozen customer wording"
    compact = compact_resolution_text(record)
    assert "FEEDER:" in compact
    assert "ZENON SLD XML" in compact
    assert "JED-NTH-ABH-15" in compact


def test_other_resolution_preserves_manual_comment_for_signoff():
    text = build_resolution_description(
        rmu="30242", field="FEEDER", decision_type="OTHER",
        selected_source="Others", selected_value="Customer requested manual feeder review before final cutover.",
    )
    assert "Other agreed resolution / comment" in text
    assert "Customer requested manual feeder review before final cutover." in text
    record = {
        "rmu": "30242", "analysis_field": "FEEDER", "decision_type": "OTHER",
        "selected_source": "Others", "selected_value": "Manual customer comment",
    }
    assert "Manual customer comment" in resolution_display_text(record)
    assert "Other - Manual customer comment" in compact_resolution_text(record)
