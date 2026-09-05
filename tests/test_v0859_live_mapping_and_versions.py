from __future__ import annotations

import tempfile
from pathlib import Path

from migration_report_tool.infrastructure.database.sqlite_store import ProjectStore
from migration_report_tool.repository import scan_repository, sync_site_to_project
from migration_report_tool.services.schema_service import (
    get_hidden_source_fields,
    rmu_review_groups,
    set_hidden_source_fields,
    system_logic_field_keys,
)


def _group_keys(groups, group_name: str) -> set[str]:
    cols = next(cols for group, _color, cols in groups if group == group_name)
    return {key for key, _label, _width in cols}


def test_system_logic_fields_are_protected_but_optional_presentation_fields_can_hide():
    with tempfile.TemporaryDirectory() as td:
        store = ProjectStore(Path(td) / "project")
        try:
            assert "rmu" in system_logic_field_keys("zenon_db")
            assert "brand" not in system_logic_field_keys("zenon_db")

            # A request to hide a locked business field is ignored, while an
            # optional presentation field is persisted as hidden.
            set_hidden_source_fields(store, "zenon_db", {"rmu", "brand"}, "tester")
            assert get_hidden_source_fields(store, "zenon_db") == {"brand"}

            keys = _group_keys(rmu_review_groups(store), "ZENON DB")
            assert "zdb_rmu" in keys
            assert "zdb_brand" not in keys
        finally:
            store.close()


def test_refresh_semantics_pick_new_highest_version_and_same_version_content_change():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "repo"
        site_dir = root / "1-ABH"
        site_dir.mkdir(parents=True)
        v1 = site_dir / "ZENON-SLD-V1.csv"
        v2 = site_dir / "ZENON-SLD-V2.csv"
        v1.write_text("RMU,Feeder\n1001,V1\n", encoding="utf-8")
        v2.write_text("RMU,Feeder\n1001,V2-A\n", encoding="utf-8")

        store = ProjectStore(Path(td) / "project")
        try:
            site = scan_repository(root)[0]
            assert site.sources["zenon_sld"].name == "ZENON-SLD-V2.csv"
            first = sync_site_to_project(store, site)
            assert "zenon_sld" in first.changed_keys
            assert "V2-A" in store.source_path("zenon_sld").read_text(encoding="utf-8-sig")

            # Same physical version, changed content: explicit refresh/sync must
            # read the file again rather than trusting the previous snapshot.
            v2.write_text("RMU,Feeder\n1001,V2-B\n", encoding="utf-8")
            second = sync_site_to_project(store, site)
            assert "zenon_sld" in second.changed_keys
            assert "V2-B" in store.source_path("zenon_sld").read_text(encoding="utf-8-sig")

            # A new higher V version becomes the AUTO source on the next scan.
            v3 = site_dir / "ZENON-SLD-V3.1.csv"
            v3.write_text("RMU,Feeder\n1001,V31\n", encoding="utf-8")
            site = scan_repository(root)[0]
            assert site.sources["zenon_sld"].name == "ZENON-SLD-V3.1.csv"
            third = sync_site_to_project(store, site)
            assert "zenon_sld" in third.changed_keys
            assert "V31" in store.source_path("zenon_sld").read_text(encoding="utf-8-sig")
        finally:
            store.close()
