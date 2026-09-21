from pathlib import Path
import sqlite3

from migration_report_tool.services.configurable_comparison_service import source_path
from migration_report_tool.services.portable_site_service import (
    PORTABLE_SITE_MARKER,
    is_portable_site_folder,
    migrate_legacy_project_data,
    organize_unified_site,
    prepare_portable_site,
    repair_unified_site_paths,
)


class _Store:
    def __init__(self, folder: Path, source: Path):
        self.folder = folder
        self.config = {
            "site_name": "1-AJWD",
            "repository_path": str(source.parent),
            "equipment_comparison_config_v1": {
                "sources": [{
                    "id": "adms",
                    "title": "ADMS DB",
                    "path": str(source),
                    "path_mode": "absolute",
                    "selection_mode": "pinned",
                }],
                "comparisons": [],
            },
        }

    def save_config(self):
        return None


def test_prepare_portable_site_keeps_project_data_and_rebinds_sources(tmp_path):
    repository = tmp_path / "DownStreamBatches" / "1-AJWD"
    repository.mkdir(parents=True)
    source = repository / "ADMS-DB.xlsx"
    source.write_bytes(b"customer source")

    package = tmp_path / "ProjectData" / "workspace" / "1-AJWD"
    package.mkdir(parents=True)
    (package / "project.db").write_bytes(b"existing review database")
    store = _Store(package, source)

    result = prepare_portable_site(store, repository)

    assert result["source_count"] == 1
    assert (package / "source_files" / "ADMS-DB.xlsx").read_bytes() == b"customer source"
    assert (package / "project.db").read_bytes() == b"existing review database"
    assert (package / PORTABLE_SITE_MARKER).is_file()
    assert is_portable_site_folder(package)
    saved_source = store.config["equipment_comparison_config_v1"]["sources"][0]
    assert saved_source["path"] == "source_files/ADMS-DB.xlsx"
    assert saved_source["path_mode"] == "project_relative"
    assert source_path(store, saved_source) == package / "source_files" / "ADMS-DB.xlsx"


def test_portable_marker_is_required_for_in_place_package_detection(tmp_path):
    folder = tmp_path / "1-AJWD"
    folder.mkdir()
    (folder / "project.db").write_bytes(b"db")

    assert not is_portable_site_folder(folder)
    (folder / PORTABLE_SITE_MARKER).write_text("{}", encoding="utf-8")
    assert is_portable_site_folder(folder)


def test_future_unified_site_is_detected_without_migration_marker(tmp_path):
    from migration_report_tool.services.portable_site_service import is_unified_site_folder

    folder = tmp_path / "1-NEW"
    folder.mkdir()
    (folder / "project.db").write_bytes(b"db")
    (folder / "SE.xlsx").write_bytes(b"source")

    assert is_unified_site_folder(folder)


def test_legacy_root_sources_are_organized_without_moving_project_data(tmp_path):
    package = tmp_path / "1-AJWD"
    package.mkdir(parents=True)
    (package / "project.db").write_bytes(b"db")
    workbook = package / "ADMS-DB.xlsx"
    workbook.write_bytes(b"source")
    store = _Store(package, workbook)
    (package / PORTABLE_SITE_MARKER).write_text("{}", encoding="utf-8")

    moved = organize_unified_site(store, package)

    assert moved == 1
    assert not workbook.exists()
    assert (package / "source_files" / "ADMS-DB.xlsx").read_bytes() == b"source"
    assert (package / "project.db").read_bytes() == b"db"
    source = store.config["equipment_comparison_config_v1"]["sources"][0]
    assert source["path"] == "source_files/ADMS-DB.xlsx"
    assert source["path_mode"] == "project_relative"


def test_repair_unified_site_paths_rebinds_old_absolute_workbook_path(tmp_path):
    package = tmp_path / "repair" / "1-AJWD"
    package.mkdir(parents=True)
    (package / "project.db").write_bytes(b"db")
    workbook = package / "ADMS-DB.xlsx"
    workbook.write_bytes(b"source")
    old_path = tmp_path / "old-machine" / "ADMS-DB.xlsx"
    store = _Store(package, old_path)
    store.config[PORTABLE_SITE_MARKER] = True
    (package / PORTABLE_SITE_MARKER).write_text("{}", encoding="utf-8")

    changed = repair_unified_site_paths(store, package)

    assert changed == 1
    source = store.config["equipment_comparison_config_v1"]["sources"][0]
    assert source["path"] == "ADMS-DB.xlsx"
    assert source["path_mode"] == "project_relative"


def test_legacy_project_database_is_adopted_without_deleting_original(tmp_path):
    legacy = tmp_path / "legacy" / "1-ABH"
    site = tmp_path / "shared" / "1-ABH"
    legacy.mkdir(parents=True)
    with sqlite3.connect(legacy / "project.db") as db:
        db.execute("CREATE TABLE comments (value TEXT)")
        db.execute("INSERT INTO comments(value) VALUES ('customer comment')")
    (legacy / "project.json").write_text('{"site_name":"1-ABH"}', encoding="utf-8")

    assert migrate_legacy_project_data(legacy, site)
    with sqlite3.connect(site / "project.db") as db:
        assert db.execute("SELECT value FROM comments").fetchone()[0] == "customer comment"
    assert (legacy / "project.db").is_file()
    assert (site / "project.json").read_text(encoding="utf-8") == '{"site_name":"1-ABH"}'
