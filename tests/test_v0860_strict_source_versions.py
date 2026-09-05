from __future__ import annotations

import tempfile
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.infrastructure.filesystem.site_repository import (
    SiteInfo,
    selected_repository_source_path,
    source_user_visible_name,
    source_version_candidates,
)


def test_zenon_sld_version_picker_never_lists_zenon_db():
    with tempfile.TemporaryDirectory() as td:
        site = Path(td) / "1-ABH"
        site.mkdir()
        for name in (
            "ZENON-SLD.csv",
            "ZENON-SLD-V1.csv",
            "ZENON-SLD-V2.1.0.csv",
            "ZENON-DB.csv",
            "ZENON-DB-V9.csv",
            "ADMS-SLD-V7.csv",
        ):
            (site / name).write_text("RMU,Feeder\n1001,X\n", encoding="utf-8")

        names = [p.name for p in source_version_candidates(site, "zenon_sld")]
        assert names == ["ZENON-SLD-V2.1.0.csv", "ZENON-SLD-V1.csv"]
        assert "ZENON-SLD.csv" not in names  # base fallback is AUTO-detectable but is not a published V pin
        assert "ZENON-DB.csv" not in names
        assert "ZENON-DB-V9.csv" not in names
        assert "ADMS-SLD-V7.csv" not in names


def test_stale_cross_table_pinned_selection_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        site_dir = Path(td) / "1-ABH"
        site_dir.mkdir()
        sld = site_dir / "ZENON-SLD-V2.csv"
        zdb = site_dir / "ZENON-DB.csv"
        sld.write_text("RMU,Feeder\n1001,A\n", encoding="utf-8")
        zdb.write_text("RMU,Feeder\n1001,B\n", encoding="utf-8")
        site = SiteInfo("1-ABH", site_dir, sources={"zenon_sld": sld, "zenon_db": zdb})

        store = ProjectStore(Path(td) / "project")
        try:
            # Simulate a bad selection saved by the v0.8.59 picker bug.
            store.set_source_file_selection("zenon_sld", "ZENON-DB.csv", "tester")
            assert selected_repository_source_path(site, store, "zenon_sld") is None

            store.set_source_file_selection("zenon_sld", "ZENON-SLD-V2.csv", "tester")
            assert selected_repository_source_path(site, store, "zenon_sld") == sld
        finally:
            store.close()


def test_manual_workspace_snapshot_displays_original_filename():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        site_dir = root / "1-ABH"
        site_dir.mkdir()
        site = SiteInfo("1-ABH", site_dir)
        supplied = root / "ZENON-SLD-V4.csv"
        supplied.write_text("RMU,Feeder\n1001,A\n", encoding="utf-8")

        store = ProjectStore(root / "project")
        try:
            internal = store.set_source("zenon_sld", supplied)
            assert internal.name.startswith("zenon_sld_")
            store.mark_manual_source_override("zenon_sld", supplied)
            assert source_user_visible_name(site, store, "zenon_sld", internal) == "ZENON-SLD-V4.csv"
        finally:
            store.close()


def test_pinned_repository_filename_wins_over_older_manual_snapshot_name():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        site_dir = root / "1-ABH"
        site_dir.mkdir()
        pinned = site_dir / "ZENON-SLD-V5.csv"
        pinned.write_text("RMU,Feeder\n1001,A\n", encoding="utf-8")
        site = SiteInfo("1-ABH", site_dir, sources={"zenon_sld": pinned})
        manual = root / "old-custom.csv"
        manual.write_text("RMU,Feeder\n1001,B\n", encoding="utf-8")

        store = ProjectStore(root / "project")
        try:
            store.set_source("zenon_sld", manual)
            store.mark_manual_source_override("zenon_sld", manual)
            store.set_source_file_selection("zenon_sld", pinned.name, "tester")
            assert source_user_visible_name(site, store, "zenon_sld", pinned) == pinned.name
        finally:
            store.close()
