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
            assert store._active_rmu_issue_fields(row) == ["FEEDER", "TYPE", "LINK"]

            feeder = row["resolution_candidates"]["FEEDER"][0]
            store.set_rmu_resolution(
                "1001", "FEEDER", "USE_SOURCE", "tester",
                selected_source=feeder["source"], selected_value=feeder["value"],
                normalized_value=feeder["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "FEEDER"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "UNREVIEWED"

            rtype = row["resolution_candidates"]["TYPE"][1]
            store.set_rmu_resolution(
                "1001", "TYPE", "USE_SOURCE", "tester",
                selected_source=rtype["source"], selected_value=rtype["value"],
                normalized_value=rtype["normalized"],
                analysis_fingerprint=store._rmu_field_fingerprint(row, "TYPE"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "UNREVIEWED"

            store.set_rmu_resolution(
                "1001", "LINK", "ACCEPT_EXCEPTION", "tester",
                analysis_fingerprint=store._rmu_field_fingerprint(row, "LINK"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "REVIEWED"
            assert len(store.rmu_resolution_map("1001")) == 3
        finally:
            store.db.close()


def test_needs_action_drives_review_status():
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
            store.set_rmu_resolution(
                "1001", "LINK", "NEEDS_ACTION", "tester",
                analysis_fingerprint=store._rmu_field_fingerprint(row, "LINK"),
            )
            assert store.sync_rmu_review_from_resolutions("1001", row, "tester") == "NEEDS ACTION"
            assert "LINK → Needs Action" in store.rmu_resolution_summary("1001")
        finally:
            store.db.close()


def test_changed_validation_invalidates_only_affected_resolution():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "site")
        try:
            row = _row()
            store.save_comparison([row])
            for field in ("FEEDER", "TYPE", "LINK"):
                if field == "LINK":
                    store.set_rmu_resolution(
                        "1001", field, "ACCEPT_EXCEPTION", "tester",
                        analysis_fingerprint=store._rmu_field_fingerprint(row, field),
                    )
                else:
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
            assert "LINK" in resolutions
            assert store.rmu_review_map()["1001"]["review_status"] == "UNREVIEWED"
        finally:
            store.db.close()
