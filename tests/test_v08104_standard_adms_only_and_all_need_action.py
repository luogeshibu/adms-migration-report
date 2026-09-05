from pathlib import Path
from tempfile import TemporaryDirectory

from migration_report_tool.db_smart import (
    build_signal_mapping_report,
    signal_review_alias_map,
    signal_review_metadata,
    signal_row_is_zenon_only,
)
from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore


ROOT = Path(__file__).resolve().parents[1]


def _report():
    return build_signal_mapping_report(
        ROOT / "examples" / "sample-data" / "ZENON-ADMS-IOA.csv",
        ROOT / "examples" / "sample-data" / "ADMS-SLD.csv",
        ROOT / "resources" / "templates" / "IOA STANDARD.xlsx",
    )


def test_only_standard_adms_produces_true_false_and_zenon_is_hint_only():
    report = _report()
    idx = {key: i for i, (key, _label, _width) in enumerate(report.columns)}
    assert sum(row.values[report.analysis_column] == "TRUE" for row in report.rows) == 5520
    assert sum(row.values[report.analysis_column] == "FALSE" for row in report.rows) == 10
    zenon_extra = [row for row in report.rows if signal_row_is_zenon_only(row)]
    assert zenon_extra
    assert all(row.values[report.analysis_column] == "" for row in zenon_extra)
    assert all(not row.values[idx["standard_dot_no"]] and not row.values[idx["adms_dot_no"]] for row in zenon_extra)
    assert all("does not participate in TRUE/FALSE comparison" in row.analysis_detail for row in zenon_extra)


def test_legacy_signal_review_key_maps_to_standard_driven_row():
    report = _report()
    alias_map = signal_review_alias_map(report)
    row = next(row for row in report.rows if row.legacy_row_keys)
    legacy = row.legacy_row_keys[0]
    assert alias_map[legacy] == row.row_key
    meta = signal_review_metadata(report, row)
    assert meta["signal_category"] in {"STATUS_CMD", "ANALOG"}
    assert meta["point_no"]


def test_needs_action_survives_alias_migration_and_source_fingerprint_change():
    report = _report()
    row = next(row for row in report.rows if row.legacy_row_keys)
    legacy = row.legacy_row_keys[0]
    meta = signal_review_metadata(report, row)
    with TemporaryDirectory() as tmp:
        store = ProjectStore(Path(tmp) / "1-ABH")
        store.config["site_name"] = "1-ABH"
        store.save_config()
        store.update_db_smart_review(
            legacy, row.rmu, "review_status", "NEEDS ACTION", "reviewer",
            source_hash="legacy-source", row_hash="legacy-row", site_name="1-ABH",
        )
        store.sync_db_smart_review_fingerprints(
            {row.row_key: {"row_hash": "new-row", "source_hash": "new-source"}},
            aliases={legacy: row.row_key}, metadata={row.row_key: meta}, modified_by="SYSTEM",
        )
        reviews = store.db_smart_review_map()
        assert legacy not in reviews
        assert reviews[row.row_key]["review_status"] == "NEEDS ACTION"
        assert reviews[row.row_key]["signal_category"] == meta["signal_category"]
        assert reviews[row.row_key]["point_no"] == meta["point_no"]

        store.sync_db_smart_review_fingerprints(
            {row.row_key: {"row_hash": "changed-again", "source_hash": "changed-source"}},
            metadata={row.row_key: meta}, modified_by="SYSTEM",
        )
        assert store.db_smart_review_map()[row.row_key]["review_status"] == "NEEDS ACTION"
        store.close()


def test_pdf_snapshot_contract_counts_all_site_need_action_records():
    text = (ROOT / "src" / "migration_report_tool" / "infrastructure" / "export" / "signoff_pdf.py").read_text(encoding="utf-8")
    assert 'counts = {"TOTAL": len(need_action_reviews)' in text
    assert 'canonical_key = aliases.get(stored_key, stored_key)' in text
    assert 'review.get("signal_category")' in text
    assert 'historical_by_key' in text


def test_signal_ui_declares_standard_adms_zenon_order_and_has_no_unchecked():
    text = (ROOT / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "Source order: STANDARD → ADMS → ZENON" in text
    assert '"UNCHECKED"' not in text
