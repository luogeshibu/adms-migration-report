from __future__ import annotations

import tempfile
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import (
    SiteInfo,
    source_user_visible_path,
    sync_site_to_project,
)
from migration_report_tool.infrastructure.parsers import validate_source_file
from migration_report_tool.services.rmu_review_service import build_comparison
from migration_report_tool.services.schema_service import module_field_mapping_lines


def test_rmu_source_groups_show_only_values_from_their_own_table():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        zdb = root / "ZENON-DB.csv"
        zdb.write_text(
            "RMU,FEEDER,SMART,PRIMARY_IP,PRIMARY_PORT\n1001,Z-FDR,SMART HT,10.0.0.1,2404\n",
            encoding="utf-8",
        )
        adb = root / "ADMS-DB.csv"
        # Deliberately no NET_DESCRIPTION1/IP column. ADMS DB display must stay blank
        # even though ZENON DB has a driver IP for the same RMU.
        adb.write_text("RMU_NAME,ADMS_GSS-FID,TYPE\n1001,A-FDR,2L1T\n", encoding="utf-8")
        asld = root / "ADMS-SLD.csv"
        asld.write_text("RMU,TYPE,SMART\n1001,2L1T,SMART HT\n", encoding="utf-8")

        store = ProjectStore(root / "project")
        try:
            store.set_source("zenon_db", zdb)
            store.set_source("adms_db", adb)
            store.set_source("adms_sld", asld)
            rows, _ = build_comparison(store)
            row = next(r for r in rows if r["rmu"] == "1001")
            assert row["driver_ip"] == "10.0.0.1"
            assert row["adms_channel_ip"] == ""
            # Display keeps the exact ADMS-SLD source text; normalization is only
            # for Analysis and must not rewrite the source-table cell.
            assert row["asld_smart"] == "SMART HT"
        finally:
            store.close()


def test_module_mapping_explains_only_fields_consumed_by_that_module():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        source = root / "ADMS-SLD.csv"
        source.write_text(
            "RMU,TYPE,SMART,FEEDER,NEW LINK\n1001,2L1T,SMART,FDR-1,L-1\n",
            encoding="utf-8",
        )
        store = ProjectStore(root / "project")
        try:
            store.replace_custom_source_fields(
                "adms_sld",
                [{"field_key": "new_link", "display_name": "NEW LINK", "actual_column": "NEW LINK"}],
                "tester",
            )
            validation = validate_source_file("adms_sld", source, {})

            signal_lines = module_field_mapping_lines("signal_mapping", "adms_sld", store, validation)
            assert any(line.startswith("RMU ← ") for line in signal_lines)
            assert any(line.startswith("Type ← ") for line in signal_lines)
            assert not any(line.startswith("SMART ← ") for line in signal_lines)
            assert not any(line.startswith("Feeder ← ") for line in signal_lines)
            assert not any(line.startswith("NEW LINK ← ") for line in signal_lines)

            rmu_lines = module_field_mapping_lines("rmu_review", "adms_sld", store, validation)
            assert any(line.startswith("SMART ← ") for line in rmu_lines)
            assert any(line.startswith("Feeder ← ") for line in rmu_lines)
            assert "NEW LINK ← NEW LINK" in rmu_lines
        finally:
            store.close()


def test_manual_external_source_path_is_visible_and_refresh_re_reads_change():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        site_dir = root / "site" / "1-ABH"
        site_dir.mkdir(parents=True)
        external_dir = root / "external"
        external_dir.mkdir()
        external = external_dir / "ZENON-SLD-V3.csv"
        external.write_text("RMU,Feeder\n1001,FDR-A\n", encoding="utf-8")

        store = ProjectStore(root / "project")
        try:
            store.set_source("zenon_sld", external)
            store.mark_manual_source_override("zenon_sld", external)
            site = SiteInfo("1-ABH", site_dir, sources={})
            assert source_user_visible_path(site, store, "zenon_sld", store.source_path("zenon_sld")) == str(external.resolve())

            external.write_text("RMU,Feeder\n1001,FDR-B\n", encoding="utf-8")
            result = sync_site_to_project(store, site)
            assert "zenon_sld" in result.changed_keys
            active = store.source_path("zenon_sld")
            assert active is not None
            assert "FDR-B" in active.read_text(encoding="utf-8-sig")
        finally:
            store.close()


def test_site_data_sources_ui_has_clear_actions_path_and_module_mapping_columns():
    ui = (Path(__file__).parents[1] / "src" / "migration_report_tool" / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert '"App Table", "Source File", "File Path",' in ui
    assert '"Fields Used in This Module (App ← Source)", "Status"' in ui
    assert 'choose_source_file_for_table' in ui
    assert 'table.setCellWidget(row, 1, source_button)' in ui
    assert 'active_file_btn = QPushButton("Choose Active File...")' not in ui
    assert 'add_files_btn = QPushButton("Import Source File...")' not in ui
    assert 'source_user_visible_path(site, active_store, source_type, Path(path))' in ui
