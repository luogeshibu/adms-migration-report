from pathlib import Path
import tempfile

from migration_report_tool.storage import ProjectStore


def _row(rmu="1001"):
    return {
        "no": 1,
        "rmu": rmu,
        "analysis_name": "TRUE",
        "analysis_feeder": "FALSE",
        "analysis_smart": "TRUE",
        "analysis_type": "FALSE",
        "analysis_ip": "TRUE",
        "analysis_link": "FALSE",
        "analysis_name_detail": "NAME ok",
        "analysis_feeder_detail": "SE: ABH-22 / ADMS DB: ABH-23",
        "analysis_smart_detail": "SMART ok",
        "analysis_type_detail": "ZENON DB: 2L1T / ADMS SLD: 3L1T",
        "analysis_ip_detail": "IP ok",
        "analysis_link_detail": "ADMS SLD LINK: NO",
        "resolution_candidates": {
            "FEEDER": [
                {"source": "SE", "value": "ABH-22", "normalized": "ABH-22"},
                {"source": "ADMS DB", "value": "JED-NTH-ABH-23", "normalized": "ABH-23"},
            ],
            "TYPE": [
                {"source": "ZENON DB", "value": "2L1T", "normalized": "2L1T"},
                {"source": "ADMS SLD", "value": "3L1T", "normalized": "3L1T"},
            ],
            "LINK": [{"source": "ADMS SLD", "value": "NO", "normalized": "FALSE"}],
        },
        "status": "FAILED",
        "remarks": "Analysis mismatch: FEEDER / TYPE / LINK",
        "comments": "",
    }


def test_each_false_field_requires_its_own_resolution():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            store.save_comparison([row])
            assert store._active_rmu_issue_fields(row) == ["FEEDER", "TYPE"]

            feeder = row["resolution_candidates"]["FEEDER"][1]
            store.set_rmu_resolution(
                "1001", "FEEDER", "USE_SOURCE", "tester",
                selected_source=feeder["source"], selected_value=feeder["value"],
                normalized_value=feeder["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "UNREVIEWED"
            feeder_record = store.rmu_resolution_map("1001")["FEEDER"]
            assert "approved feeder assignment" in feeder_record["decision_description"]

            rtype = row["resolution_candidates"]["TYPE"][1]
            store.set_rmu_resolution(
                "1001", "TYPE", "USE_SOURCE", "tester",
                selected_source=rtype["source"], selected_value=rtype["value"],
                normalized_value=rtype["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "TYPE"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "UNREVIEWED"
            assert len(store.rmu_resolution_map("1001")) == 2
        finally:
            store.db.close()


def test_needs_action_drives_review_status():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            store.save_comparison([row])
            feeder = row["resolution_candidates"]["FEEDER"][0]
            store.set_rmu_resolution(
                "1001", "FEEDER", "USE_SOURCE", "tester",
                selected_source=feeder["source"], selected_value=feeder["value"],
                normalized_value=feeder["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
            )
            store.update_rmu_review_status("1001", "NEEDS ACTION", "tester", "Reviewer requires corrective action")
            store.set_rmu_resolution(
                "1001", "TYPE", "NEEDS_ACTION", "tester",
                analysis_fingerprint=store._rmu_field_fingerprint(row, "TYPE"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "NEEDS ACTION"
            assert "Further corrective action is required for the RMU type issue on RMU 1001" in store.rmu_resolution_summary("1001")
        finally:
            store.db.close()



def test_resolution_source_choice_never_changes_explicit_review_status():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            row["analysis_type"] = "TRUE"
            row["analysis_type_detail"] = "TYPE ok"
            store.save_comparison([row])

            # A reviewer-owned NEEDS ACTION state must survive even when the
            # selected Resolution value is exactly the ADMS DB value.
            store.update_rmu_review_status("1001", "NEEDS ACTION", "tester", "Manual Needs Action")
            adms = row["resolution_candidates"]["FEEDER"][1]
            store.set_rmu_resolution(
                "1001", "FEEDER", "USE_SOURCE", "tester",
                selected_source=adms["source"], selected_value=adms["value"],
                normalized_value=adms["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "NEEDS ACTION"

            # Choosing a different source also must not rewrite Review Status.
            se = row["resolution_candidates"]["FEEDER"][0]
            store.set_rmu_resolution(
                "1001", "FEEDER", "USE_SOURCE", "tester",
                selected_source=se["source"], selected_value=se["value"],
                normalized_value=se["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "NEEDS ACTION"

            # Closure is an explicit reviewer action and remains independent of
            # later Resolution edits too.
            store.update_rmu_review_status("1001", "CLOSED", "tester", "Reviewer explicitly closed item")
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "CLOSED"
        finally:
            store.db.close()


def test_same_normalized_value_as_adms_db_does_not_auto_close():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            row["analysis_type"] = "TRUE"
            row["resolution_candidates"]["FEEDER"] = [
                {"source": "SE", "value": "ABH-22", "normalized": "ABH-22"},
                {"source": "ZENON SLD XML", "value": "JED-NTH-ABH-23", "normalized": "ABH-23"},
                {"source": "ADMS DB", "value": "JED-NTH-ABH-AH23", "normalized": "ABH-23"},
            ]
            store.save_comparison([row])
            choice = row["resolution_candidates"]["FEEDER"][1]
            store.set_rmu_resolution(
                "1001", "FEEDER", "USE_SOURCE", "tester",
                selected_source=choice["source"], selected_value=choice["value"],
                normalized_value=choice["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "UNREVIEWED"
        finally:
            store.db.close()


def test_field_without_adms_db_candidate_also_keeps_review_status_independent():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            row["analysis_feeder"] = "TRUE"
            row["analysis_type"] = "TRUE"
            row["analysis_ip"] = "FALSE"
            row["analysis_ip_detail"] = "Driver info: 10.0.0.1 / ADMS Channel: 10.0.0.2"
            row["resolution_candidates"]["IP"] = [
                {"source": "Driver info", "value": "10.0.0.1", "normalized": "10.0.0.1"},
                {"source": "ADMS Channel", "value": "10.0.0.2", "normalized": "10.0.0.2"},
            ]
            store.save_comparison([row])
            choice = row["resolution_candidates"]["IP"][0]
            store.set_rmu_resolution(
                "1001", "IP", "USE_SOURCE", "tester",
                selected_source=choice["source"], selected_value=choice["value"],
                normalized_value=choice["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "IP"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "UNREVIEWED"
        finally:
            store.db.close()

def test_changed_validation_invalidates_only_affected_resolution():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            store.save_comparison([row])
            for field in ("FEEDER", "TYPE"):
                candidate = row["resolution_candidates"][field][0]
                store.set_rmu_resolution(
                    "1001", field, "USE_SOURCE", "tester",
                    selected_source=candidate["source"], selected_value=candidate["value"],
                    normalized_value=candidate["normalized"],
                    analysis_fingerprint=store._rmu_field_fingerprint(row, field),
                )
            store.sync_rmu_review_from_resolutions("1001", row, "tester")

            changed = _row()
            changed["analysis_feeder_detail"] = "SE: ABH-24 / ADMS DB: ABH-23"
            changed["resolution_candidates"]["FEEDER"][0] = {
                "source": "SE", "value": "ABH-24", "normalized": "ABH-24"
            }
            store.save_comparison([changed])
            resolutions = store.rmu_resolution_map("1001")
            assert "FEEDER" not in resolutions
            assert "TYPE" in resolutions
            assert "LINK" not in resolutions
            assert store.rmu_review_map()["1001"]["review_status"] == "UNREVIEWED"
        finally:
            store.db.close()


def test_other_manual_comment_is_a_resolved_customer_decision():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            row["analysis_type"] = "TRUE"
            row["analysis_type_detail"] = "TYPE ok"
            store.save_comparison([row])
            store.set_rmu_resolution(
                "1001", "FEEDER", "OTHER", "tester",
                selected_source="Others",
                selected_value="Keep the current feeder pending the agreed field note.",
                analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
            )
            record = store.rmu_resolution_map("1001")["FEEDER"]
            assert record["decision_type"] == "OTHER"
            assert record["selected_value"] == "Keep the current feeder pending the agreed field note."
            assert "Other agreed resolution / comment" in record["decision_description"]
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "UNREVIEWED"
        finally:
            store.db.close()


def test_other_resolution_requires_manual_comment():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            row["analysis_type"] = "TRUE"
            store.save_comparison([row])
            try:
                store.set_rmu_resolution(
                    "1001", "FEEDER", "OTHER", "tester",
                    selected_source="Others", selected_value="",
                    analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
                )
            except ValueError as exc:
                assert "manual comment" in str(exc)
            else:
                raise AssertionError("OTHER without a comment must be rejected")
        finally:
            store.db.close()
