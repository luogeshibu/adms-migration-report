"""Workspace project persistence and SQLite audit repository."""
from __future__ import annotations
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from ...schema import EDITABLE_COLUMNS
from ...parsers import clean
from ...domain.analysis.resolution_text import build_resolution_description, resolution_display_text
from ...version import __version__
from .migrations import TARGET_SCHEMA_VERSION, migrate_project_database
from .global_settings_store import (
    source_custom_columns as global_source_custom_columns,
    replace_source_custom_columns as replace_global_source_custom_columns,
    ensure_source_custom_columns as ensure_global_source_custom_columns,
    source_custom_column_bindings as global_source_custom_column_bindings,
    replace_source_custom_column_bindings as replace_global_source_custom_column_bindings,
    ensure_source_custom_column_bindings as ensure_global_source_custom_column_bindings,
    source_field_overrides as global_source_field_overrides,
    ensure_source_field_overrides as ensure_global_source_field_overrides,
)

class ProjectStore:
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.sources_dir = self.folder / "source_files"
        self.generated_dir = self.folder / "generated"
        self.reports_dir = self.folder / "reports"
        self.signed_reports_dir = self.reports_dir / "signed"
        self.snapshots_dir = self.folder / "snapshots"
        self.backups_dir = self.folder / "backups"
        for directory in (
            self.sources_dir,
            self.generated_dir,
            self.reports_dir,
            self.signed_reports_dir,
            self.snapshots_dir,
            self.backups_dir,
        ):
            directory.mkdir(exist_ok=True)
        self.config_path = self.folder / "project.json"
        self.db_path = self.folder / "project.db"
        self.config = self._load_config()
        self.schema_version, self.last_migration_backup = migrate_project_database(self.db_path, self.backups_dir)
        self.db = sqlite3.connect(self.db_path, timeout=15.0)
        self.db.row_factory = sqlite3.Row
        # WAL allows the GUI connection to keep reading while background
        # workers commit source refresh/validation results through a separate
        # ProjectStore connection.  NORMAL synchronous mode is durable enough
        # for the local workspace while avoiding unnecessary fsync stalls.
        try:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
            self.db.execute("PRAGMA busy_timeout=15000")
        except sqlite3.DatabaseError:
            pass
        self._init_db()
        self._promote_legacy_custom_fields_to_global()
        self._promote_legacy_source_overrides_to_global()
        # Keep project.json metadata aligned with the migrated SQLite schema so
        # support/debug exports never report a stale pre-upgrade version.
        if int(self.config.get("db_schema_version") or 0) != int(self.schema_version):
            self.save_config()

    def _load_config(self):
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        return {"project_name": self.folder.name, "created_at": datetime.now().isoformat(timespec="seconds"), "sources": {}}

    def save_config(self):
        self.config.setdefault("project_data_format", 1)
        self.config["db_schema_version"] = self.project_schema_version() if hasattr(self, "db") else TARGET_SCHEMA_VERSION
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass

    def project_schema_version(self) -> int:
        try:
            row = self.db.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()
            return int(row[0]) if row else TARGET_SCHEMA_VERSION
        except Exception:
            return TARGET_SCHEMA_VERSION

    def _init_db(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS comparison (
            rmu TEXT PRIMARY KEY, no INTEGER, station TEXT, se_feeder TEXT,
            se_device TEXT, oh_ug TEXT, zenon_feeder TEXT, zenon_type TEXT,
            picture TEXT, adms_db_feeder TEXT, adms_db_type TEXT,
            adms_sld_type TEXT, smart TEXT, status TEXT, remarks TEXT, comments TEXT,
            auto_json TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, rmu TEXT, field_name TEXT,
            old_value TEXT, new_value TEXT, reason TEXT, modified_by TEXT,
            modified_at TEXT
        );
        CREATE TABLE IF NOT EXISTS imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, source_type TEXT, original_name TEXT,
            stored_path TEXT, imported_at TEXT, row_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, version_name TEXT,
            description TEXT, snapshot_json TEXT, created_by TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS rmu_reviews (
            rmu TEXT PRIMARY KEY, review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
            manual_comment TEXT NOT NULL DEFAULT '',
            check_passed INTEGER NOT NULL DEFAULT 0,
            check_passed_by TEXT NOT NULL DEFAULT '', check_passed_at TEXT NOT NULL DEFAULT '',
            reviewed_by TEXT, reviewed_at TEXT, updated_at TEXT, analysis_hash TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS rmu_resolutions (
            rmu TEXT NOT NULL, analysis_field TEXT NOT NULL, decision_type TEXT NOT NULL,
            selected_source TEXT NOT NULL DEFAULT '', selected_value TEXT NOT NULL DEFAULT '',
            normalized_value TEXT NOT NULL DEFAULT '', analysis_fingerprint TEXT NOT NULL DEFAULT '',
            decision_description TEXT NOT NULL DEFAULT '', customer_comment TEXT NOT NULL DEFAULT '',
            issue_snapshot_json TEXT NOT NULL DEFAULT '{}', modified_by TEXT, modified_at TEXT,
            PRIMARY KEY(rmu, analysis_field)
        );
        CREATE TABLE IF NOT EXISTS db_smart_reviews (
            row_key TEXT PRIMARY KEY, site_name TEXT, rmu TEXT, source_hash TEXT, row_hash TEXT NOT NULL DEFAULT '',
            review_status TEXT NOT NULL DEFAULT 'UNREVIEWED', comments TEXT NOT NULL DEFAULT '',
            check_passed INTEGER NOT NULL DEFAULT 0,
            check_passed_by TEXT NOT NULL DEFAULT '', check_passed_at TEXT NOT NULL DEFAULT '',
            reviewed_by TEXT, reviewed_at TEXT, updated_at TEXT,
            signal_category TEXT NOT NULL DEFAULT '', point_no TEXT NOT NULL DEFAULT '',
            signal_name TEXT NOT NULL DEFAULT '', signal_snapshot_json TEXT NOT NULL DEFAULT '{}',
            ever_needs_action INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS source_display_names (
            source_type TEXT NOT NULL, field_key TEXT NOT NULL, display_name TEXT NOT NULL,
            modified_by TEXT, modified_at TEXT,
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS site_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, revision_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '', version_id INTEGER,
            created_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS issue_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER,
            category TEXT NOT NULL DEFAULT 'Other', equipment TEXT NOT NULL DEFAULT '',
            issue TEXT NOT NULL, action_taken TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT 'OPEN', comments TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS signoff_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id INTEGER,
            report_type TEXT NOT NULL DEFAULT 'SITE_SIGNOFF', file_name TEXT NOT NULL,
            file_path TEXT NOT NULL, report_status TEXT NOT NULL DEFAULT 'GENERATED',
            snapshot_json TEXT NOT NULL DEFAULT '{}', sha256 TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            signed_file_name TEXT NOT NULL DEFAULT '', signed_file_path TEXT NOT NULL DEFAULT '',
            signed_sha256 TEXT NOT NULL DEFAULT '', signed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS custom_source_fields (
            source_type TEXT NOT NULL, field_key TEXT NOT NULL, display_name TEXT NOT NULL,
            actual_column TEXT NOT NULL DEFAULT '', created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS derived_table_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, table_name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '', base_source_type TEXT NOT NULL DEFAULT '',
            config_json TEXT NOT NULL DEFAULT '{}', created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_file_selections (
            source_type TEXT PRIMARY KEY, file_name TEXT NOT NULL,
            selected_by TEXT NOT NULL DEFAULT '', selected_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rmu_action_tracking (
            rmu TEXT PRIMARY KEY, tracking_status TEXT NOT NULL DEFAULT 'OPEN',
            first_need_action_at TEXT NOT NULL DEFAULT '', last_need_action_at TEXT NOT NULL DEFAULT '',
            closed_at TEXT NOT NULL DEFAULT '', opened_by TEXT NOT NULL DEFAULT '', closed_by TEXT NOT NULL DEFAULT '',
            open_count INTEGER NOT NULL DEFAULT 1, last_reason TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_rmu_action_tracking_status ON rmu_action_tracking(tracking_status, rmu);
        CREATE TABLE IF NOT EXISTS rmu_review_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, rmu TEXT NOT NULL, case_id INTEGER,
            analysis_field TEXT NOT NULL DEFAULT '', event_type TEXT NOT NULL DEFAULT 'COMMENT_RECORDED',
            review_status TEXT NOT NULL DEFAULT '', comment TEXT NOT NULL DEFAULT '',
            modified_by TEXT NOT NULL DEFAULT '', modified_at TEXT NOT NULL,
            snapshot_json TEXT NOT NULL DEFAULT '{}', app_version TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(case_id) REFERENCES issue_cases(id)
        );
        CREATE INDEX IF NOT EXISTS idx_rmu_review_events_rmu_time ON rmu_review_events(rmu, modified_at, id);
        CREATE INDEX IF NOT EXISTS idx_rmu_review_events_case ON rmu_review_events(case_id, id);
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(comparison)")}
        if "data_json" not in columns:
            self.db.execute("ALTER TABLE comparison ADD COLUMN data_json TEXT")
        if "comments" not in columns:
            self.db.execute("ALTER TABLE comparison ADD COLUMN comments TEXT")
        rmu_review_columns = {row[1] for row in self.db.execute("PRAGMA table_info(rmu_reviews)")}
        if "analysis_hash" not in rmu_review_columns:
            self.db.execute("ALTER TABLE rmu_reviews ADD COLUMN analysis_hash TEXT NOT NULL DEFAULT ''")
        if "manual_comment" not in rmu_review_columns:
            self.db.execute("ALTER TABLE rmu_reviews ADD COLUMN manual_comment TEXT NOT NULL DEFAULT ''")
        if "check_passed" not in rmu_review_columns:
            self.db.execute("ALTER TABLE rmu_reviews ADD COLUMN check_passed INTEGER NOT NULL DEFAULT 0")
        if "check_passed_by" not in rmu_review_columns:
            self.db.execute("ALTER TABLE rmu_reviews ADD COLUMN check_passed_by TEXT NOT NULL DEFAULT ''")
        if "check_passed_at" not in rmu_review_columns:
            self.db.execute("ALTER TABLE rmu_reviews ADD COLUMN check_passed_at TEXT NOT NULL DEFAULT ''")
        resolution_columns = {row[1] for row in self.db.execute("PRAGMA table_info(rmu_resolutions)")}
        if "decision_description" not in resolution_columns:
            self.db.execute("ALTER TABLE rmu_resolutions ADD COLUMN decision_description TEXT NOT NULL DEFAULT ''")
        if "issue_snapshot_json" not in resolution_columns:
            self.db.execute("ALTER TABLE rmu_resolutions ADD COLUMN issue_snapshot_json TEXT NOT NULL DEFAULT '{}'")
        if "customer_comment" not in resolution_columns:
            self.db.execute("ALTER TABLE rmu_resolutions ADD COLUMN customer_comment TEXT NOT NULL DEFAULT ''")
        signal_review_columns = {row[1] for row in self.db.execute("PRAGMA table_info(db_smart_reviews)")}
        if "row_hash" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN row_hash TEXT NOT NULL DEFAULT ''")
        if "check_passed" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN check_passed INTEGER NOT NULL DEFAULT 0")
        if "check_passed_by" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN check_passed_by TEXT NOT NULL DEFAULT ''")
        if "check_passed_at" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN check_passed_at TEXT NOT NULL DEFAULT ''")
        if "signal_category" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN signal_category TEXT NOT NULL DEFAULT ''")
        if "point_no" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN point_no TEXT NOT NULL DEFAULT ''")
        if "signal_name" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN signal_name TEXT NOT NULL DEFAULT ''")
        if "signal_snapshot_json" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN signal_snapshot_json TEXT NOT NULL DEFAULT '{}'")
        if "ever_needs_action" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN ever_needs_action INTEGER NOT NULL DEFAULT 0")
        self.db.commit()


    def _local_custom_source_fields(self, source_type: str) -> list[dict]:
        """Read legacy site-local USER bindings kept only as a safety copy."""
        return [
            dict(row) for row in self.db.execute(
                "SELECT source_type,field_key,display_name,actual_column,created_by,created_at,updated_at "
                "FROM custom_source_fields WHERE source_type=? ORDER BY rowid",
                (clean(source_type),),
            )
        ]

    def _promote_legacy_custom_fields_to_global(self) -> None:
        """Upgrade legacy site-local USER columns and bindings to App-global settings.

        Promotion is merge-only: existing global choices win, and legacy project
        rows stay untouched as a safety/backward-compatibility copy.
        """
        try:
            source_types = [
                clean(row[0]) for row in self.db.execute(
                    "SELECT DISTINCT source_type FROM custom_source_fields ORDER BY source_type"
                ) if clean(row[0])
            ]
            for source_type in source_types:
                legacy = self._local_custom_source_fields(source_type)
                if not legacy:
                    continue
                ensure_global_source_custom_columns(source_type, legacy, "migration")
                ensure_global_source_custom_column_bindings(
                    source_type,
                    {
                        clean(item.get("field_key")): clean(item.get("actual_column"))
                        for item in legacy
                        if clean(item.get("field_key")) and clean(item.get("actual_column"))
                    },
                    "migration",
                )
        except Exception:
            # Global settings must never prevent an existing project from opening.
            # The site-local rows remain intact and can be promoted on a later run.
            pass

    def _promote_legacy_source_overrides_to_global(self) -> None:
        """Promote old project.json Map Fields choices without deleting them."""
        try:
            root = self.config.get("source_column_overrides", {}) or {}
            for source_type, mappings in dict(root).items():
                ensure_global_source_field_overrides(
                    clean(source_type),
                    {clean(k): clean(v) for k, v in dict(mappings or {}).items() if clean(k) and clean(v)},
                    "migration",
                )
        except Exception:
            pass

    def custom_source_fields(self, source_type: str) -> list[dict]:
        """Return application-global USER App columns and Source Field mappings.

        Both the column definition and selected physical Source Field are shared
        across all sites.  Legacy site-local bindings are retained only as a
        fallback/safety copy and are promoted merge-only into global settings.
        """
        source_type = clean(source_type)
        local = {row["field_key"]: row for row in self._local_custom_source_fields(source_type)}
        definitions = list(global_source_custom_columns(source_type) or [])
        bindings = dict(global_source_custom_column_bindings(source_type) or {})
        output = []
        for definition in definitions:
            key = clean(definition.get("field_key"))
            if not key:
                continue
            legacy = local.get(key) or {}
            actual = clean(bindings.get(key)) or clean(legacy.get("actual_column"))
            output.append({
                "source_type": source_type,
                "field_key": key,
                "display_name": clean(definition.get("display_name")) or key,
                "actual_column": actual,
                "created_by": clean(definition.get("created_by") or legacy.get("created_by")),
                "created_at": clean(definition.get("created_at") or legacy.get("created_at")),
                "updated_at": clean(definition.get("updated_at") or legacy.get("updated_at")),
            })
        return output

    def replace_custom_source_fields(self, source_type: str, fields: list[dict], modified_by: str = "") -> None:
        """Save global USER App-column definitions and physical mappings.

        The current project's legacy table is also updated as a non-authoritative
        safety copy.  Other project databases are never rewritten; they read the
        shared mapping from ``global_settings.db`` on demand.
        """
        source_type = clean(source_type)
        before = {row["field_key"]: row for row in self.custom_source_fields(source_type)}
        cleaned_fields = []
        seen = set()
        for item in fields or []:
            key = clean((item or {}).get("field_key"))
            display = clean((item or {}).get("display_name"))
            actual = clean((item or {}).get("actual_column"))
            if not key or not display or key in seen:
                continue
            seen.add(key)
            cleaned_fields.append({"field_key": key, "display_name": display, "actual_column": actual})

        replace_global_source_custom_columns(source_type, cleaned_fields, modified_by)
        replace_global_source_custom_column_bindings(
            source_type,
            {item["field_key"]: item["actual_column"] for item in cleaned_fields if item["actual_column"]},
            modified_by,
        )

        now = datetime.now().isoformat(timespec="seconds")
        with self.db:
            self.db.execute("DELETE FROM custom_source_fields WHERE source_type=?", (source_type,))
            for item in cleaned_fields:
                old = before.get(item["field_key"]) or {}
                created_at = clean(old.get("created_at")) or now
                created_by = clean(old.get("created_by")) or modified_by or "system"
                self.db.execute(
                    "INSERT INTO custom_source_fields(source_type,field_key,display_name,actual_column,created_by,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (source_type, item["field_key"], item["display_name"], item["actual_column"], created_by, created_at, now),
                )
            after = {item["field_key"]: item for item in cleaned_fields}
            for key in sorted(set(before) | set(after)):
                old_text = json.dumps({
                    "display_name": clean((before.get(key) or {}).get("display_name")),
                    "actual_column": clean((before.get(key) or {}).get("actual_column")),
                }, ensure_ascii=False, sort_keys=True) if key in before else ""
                new_text = json.dumps(after.get(key) or {}, ensure_ascii=False, sort_keys=True) if key in after else ""
                if old_text == new_text:
                    continue
                self.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    (f"SCHEMA_CUSTOM:{source_type}", f"custom_field.{key}", old_text, new_text,
                     "Global App column / global Source Field mapping", modified_by or "system", now),
                )

    def derived_table_configs(self) -> list[dict]:
        output = []
        for row in self.db.execute(
            "SELECT id,table_name,description,base_source_type,config_json,created_by,created_at,updated_at "
            "FROM derived_table_configs ORDER BY table_name COLLATE NOCASE"
        ):
            item = dict(row)
            try:
                item["config"] = json.loads(item.get("config_json") or "{}")
            except Exception:
                item["config"] = {}
            output.append(item)
        return output

    def derived_table_config(self, table_name: str) -> dict | None:
        row = self.db.execute(
            "SELECT id,table_name,description,base_source_type,config_json,created_by,created_at,updated_at "
            "FROM derived_table_configs WHERE table_name=?",
            (clean(table_name),),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["config"] = json.loads(item.get("config_json") or "{}")
        except Exception:
            item["config"] = {}
        return item

    def save_derived_table_config(self, config: dict, modified_by: str = "") -> None:
        table_name = clean((config or {}).get("table_name"))
        if not table_name:
            raise ValueError("Derived table name cannot be blank.")
        description = clean((config or {}).get("description"))
        base_source_type = clean((config or {}).get("base_source_type"))
        payload = json.dumps(dict(config or {}), ensure_ascii=False, sort_keys=True, indent=2)
        current = self.derived_table_config(table_name)
        now = datetime.now().isoformat(timespec="seconds")
        with self.db:
            if current:
                self.db.execute(
                    "UPDATE derived_table_configs SET description=?,base_source_type=?,config_json=?,updated_at=? WHERE table_name=?",
                    (description, base_source_type, payload, now, table_name),
                )
            else:
                self.db.execute(
                    "INSERT INTO derived_table_configs(table_name,description,base_source_type,config_json,created_by,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (table_name, description, base_source_type, payload, modified_by or "system", now, now),
                )
            old_payload = clean((current or {}).get("config_json"))
            if old_payload != payload:
                self.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    (f"DERIVED:{table_name}", "derived_table.config", old_payload, payload,
                     "Derived table configuration", modified_by or "system", now),
                )

    def delete_derived_table_config(self, table_name: str, modified_by: str = "") -> None:
        current = self.derived_table_config(table_name)
        if not current:
            return
        now = datetime.now().isoformat(timespec="seconds")
        with self.db:
            self.db.execute("DELETE FROM derived_table_configs WHERE table_name=?", (clean(table_name),))
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (f"DERIVED:{clean(table_name)}", "derived_table.config", clean(current.get("config_json")), "",
                 "Derived table deleted", modified_by or "system", now),
            )


    def source_column_overrides(self, source_type: str) -> dict[str, str]:
        """Return application-global explicit Map Fields selections.

        Legacy project.json mappings remain untouched and are used only as a
        fallback if global settings cannot be read.
        """
        source_type = clean(source_type)
        try:
            global_values = dict(global_source_field_overrides(source_type) or {})
            if global_values:
                return global_values
        except Exception:
            pass
        return dict((self.config.get("source_column_overrides", {}) or {}).get(source_type, {}) or {})

    def source_display_names(self, source_type: str) -> dict[str, str]:
        """Read legacy v0.8.14-v0.8.15 site-local Display Names.

        v0.8.16+ uses the application-global settings database instead. This
        method/table remains only for backward-compatible access to old site DBs.
        """
        return {
            row["field_key"]: row["display_name"]
            for row in self.db.execute(
                "SELECT field_key, display_name FROM source_display_names WHERE source_type=? ORDER BY field_key",
                (str(source_type),),
            )
        }

    def replace_source_display_names(
        self, source_type: str, names: dict[str, str], modified_by: str = ""
    ) -> None:
        """Legacy site-local Display Name writer retained for old project DB compatibility."""
        source_type = clean(source_type)
        before = self.source_display_names(source_type)
        cleaned = {clean(k): clean(v) for k, v in (names or {}).items() if clean(k) and clean(v)}
        now = datetime.now().isoformat(timespec="seconds")
        with self.db:
            self.db.execute("DELETE FROM source_display_names WHERE source_type=?", (source_type,))
            for key, value in sorted(cleaned.items()):
                self.db.execute(
                    "INSERT INTO source_display_names(source_type,field_key,display_name,modified_by,modified_at) VALUES(?,?,?,?,?)",
                    (source_type, key, value, modified_by or "system", now),
                )
            for key in sorted(set(before) | set(cleaned)):
                old_value = clean(before.get(key))
                new_value = clean(cleaned.get(key))
                if old_value == new_value:
                    continue
                self.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    (f"DISPLAY:{source_type}", f"display_name.{key}", old_value, new_value,
                     "Source display name", modified_by or "system", now),
                )

    def record_schema_mapping_change(self, source_type: str, old_mapping: dict, new_mapping: dict, modified_by: str = "") -> None:
        """Persist schema override changes in the immutable audit log."""
        now = datetime.now().isoformat(timespec="seconds")
        keys = sorted(set(old_mapping) | set(new_mapping))
        for key in keys:
            old_value = clean(old_mapping.get(key))
            new_value = clean(new_mapping.get(key))
            if old_value == new_value:
                continue
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (f"SCHEMA:{source_type}", f"source_mapping.{key}", old_value, new_value,
                 "Source schema override", modified_by or "system", now),
            )
        self.db.commit()

    def set_source(self, source_type: str, selected: Path) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target = self.sources_dir / f"{source_type}_{stamp}{selected.suffix.lower()}"
        shutil.copy2(selected, target)
        self.config["sources"][source_type] = str(target.relative_to(self.folder))
        self.save_config()
        return target

    def source_path(self, source_type: str) -> Path | None:
        value = self.config.get("sources", {}).get(source_type)
        if not value:
            return None
        path = self.folder / value
        return path if path.exists() else None

    def clear_source(self, source_type: str) -> None:
        """Deactivate a source without deleting archived historical copies."""
        if source_type in self.config.get("sources", {}):
            self.config["sources"].pop(source_type, None)
            self.save_config()

    def source_file_selection(self, source_type: str) -> dict | None:
        row = self.db.execute(
            "SELECT source_type,file_name,selected_by,selected_at FROM source_file_selections WHERE source_type=?",
            (clean(source_type),),
        ).fetchone()
        return dict(row) if row else None

    def source_file_selections(self) -> dict[str, dict]:
        return {
            row["source_type"]: dict(row)
            for row in self.db.execute(
                "SELECT source_type,file_name,selected_by,selected_at FROM source_file_selections"
            )
        }

    def set_source_file_selection(self, source_type: str, file_name: str, modified_by: str = "") -> None:
        """Persist the repository file version explicitly selected for one source role."""
        source_type = clean(source_type)
        file_name = Path(str(file_name or "")).name
        if not source_type or not file_name:
            raise ValueError("Source type and file name are required")
        current = self.source_file_selection(source_type)
        old_name = clean((current or {}).get("file_name"))
        if old_name == file_name:
            return
        now = datetime.now().isoformat(timespec="seconds")
        with self.db:
            self.db.execute(
                """INSERT INTO source_file_selections(source_type,file_name,selected_by,selected_at)
                VALUES(?,?,?,?)
                ON CONFLICT(source_type) DO UPDATE SET
                  file_name=excluded.file_name,selected_by=excluded.selected_by,selected_at=excluded.selected_at""",
                (source_type, file_name, modified_by or "system", now),
            )
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (f"SOURCE:{source_type}", "active_source_file", old_name, file_name,
                 "Active repository source version selected", modified_by or "system", now),
            )

    def clear_source_file_selection(self, source_type: str, modified_by: str = "") -> None:
        """Return one source role to automatic latest-version selection."""
        source_type = clean(source_type)
        current = self.source_file_selection(source_type)
        if not current:
            return
        old_name = clean(current.get("file_name"))
        now = datetime.now().isoformat(timespec="seconds")
        with self.db:
            self.db.execute("DELETE FROM source_file_selections WHERE source_type=?", (source_type,))
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (f"SOURCE:{source_type}", "active_source_file", old_name, "AUTO (latest version)",
                 "Active repository source returned to automatic latest-version selection", modified_by or "system", now),
            )

    def manual_source_overrides(self) -> dict[str, dict]:
        """Return workspace-level manual source overrides.

        Repository discovery stays read-only.  When a reviewer imports a file
        explicitly, the copied workspace source can remain authoritative even if
        the repository has no matching filename/content signature.
        """
        raw = self.config.get("manual_source_overrides", {}) or {}
        return {str(key): dict(value or {}) for key, value in raw.items()}

    def is_manual_source_override(self, source_type: str) -> bool:
        return str(source_type) in self.manual_source_overrides() and self.source_path(source_type) is not None

    def mark_manual_source_override(self, source_type: str, original_path: Path | str) -> None:
        overrides = self.manual_source_overrides()
        source_type = str(source_type)
        stored = self.source_path(source_type)
        original = Path(original_path)
        try:
            resolved_original = str(original.resolve())
        except OSError:
            resolved_original = str(original)
        overrides[source_type] = {
            "original_name": original.name,
            "original_path": resolved_original,
            "stored_path": str(stored) if stored else "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.config["manual_source_overrides"] = overrides
        self.save_config()

    def clear_manual_source_override(self, source_type: str) -> None:
        overrides = self.manual_source_overrides()
        if str(source_type) in overrides:
            overrides.pop(str(source_type), None)
            self.config["manual_source_overrides"] = overrides
            self.save_config()

    def source_sheet_selection(self, source_type: str) -> dict:
        """Return site/project-level Excel sheet selection for one source role.

        Field mappings are global by source type, while sheet selection belongs
        to this site's physical file and therefore lives in the ProjectStore.
        Missing/blank means AUTO (first usable sheet in workbook order).
        """
        raw = self.config.get("source_sheet_selections", {}) or {}
        return dict(raw.get(str(source_type), {}) or {})

    def source_sheet_name(self, source_type: str) -> str:
        return clean(self.source_sheet_selection(source_type).get("sheet_name"))

    def set_source_sheet_selection(self, source_type: str, sheet_name: str, modified_by: str = "") -> None:
        source_type = clean(source_type)
        sheet_name = clean(sheet_name)
        if not source_type or not sheet_name:
            raise ValueError("Source type and sheet name are required")
        root = dict(self.config.get("source_sheet_selections", {}) or {})
        current = clean((root.get(source_type) or {}).get("sheet_name"))
        if current == sheet_name:
            return
        now = datetime.now().isoformat(timespec="seconds")
        root[source_type] = {"mode": "MANUAL", "sheet_name": sheet_name, "updated_at": now}
        self.config["source_sheet_selections"] = root
        self.save_config()
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (f"SOURCE:{source_type}", "active_source_sheet", current or "AUTO", sheet_name,
             "Active Excel source sheet selected", modified_by or "system", now),
        )
        self.db.commit()

    def clear_source_sheet_selection(self, source_type: str, modified_by: str = "") -> None:
        source_type = clean(source_type)
        root = dict(self.config.get("source_sheet_selections", {}) or {})
        current = clean((root.get(source_type) or {}).get("sheet_name"))
        if source_type not in root:
            return
        root.pop(source_type, None)
        self.config["source_sheet_selections"] = root
        self.save_config()
        now = datetime.now().isoformat(timespec="seconds")
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (f"SOURCE:{source_type}", "active_source_sheet", current, "AUTO",
             "Active Excel source sheet returned to AUTO", modified_by or "system", now),
        )
        self.db.commit()

    _RMU_ANALYSIS_FIELDS = ("NAME", "FEEDER", "SMART", "TYPE", "IP")

    @classmethod
    def _active_rmu_issue_fields(cls, row: dict) -> list[str]:
        return [
            field for field in cls._RMU_ANALYSIS_FIELDS
            if clean((row or {}).get(f"analysis_{field.lower()}" )).upper() == "FALSE"
        ]

    @staticmethod
    def _rmu_field_fingerprint(row: dict, field: str) -> str:
        field = clean(field).upper()
        key = f"analysis_{field.lower()}"
        candidates = ((row or {}).get("resolution_candidates") or {}).get(field, [])
        payload = {
            "result": clean((row or {}).get(key)),
            "detail": clean((row or {}).get(f"{key}_detail")),
            "candidates": candidates,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _sync_rmu_resolutions(self, rmu: str, row: dict) -> int:
        """Invalidate structured decisions when the corresponding issue changed.

        Current decisions are authoritative only for the exact validation inputs
        that the reviewer saw.  Audit history remains immutable after a decision
        is cleared.
        """
        active = set(self._active_rmu_issue_fields(row))
        existing = list(self.db.execute("SELECT * FROM rmu_resolutions WHERE rmu=?", (rmu,)))
        if not existing:
            return 0
        now = datetime.now().isoformat(timespec="seconds")
        cleared = 0
        for record in existing:
            field = clean(record["analysis_field"]).upper()
            current_fp = self._rmu_field_fingerprint(row, field) if field in active else ""
            old_fp = clean(record["analysis_fingerprint"])
            if field not in active or (old_fp and current_fp and old_fp != current_fp):
                old_summary = self._resolution_record_summary(record)
                self.db.execute("DELETE FROM rmu_resolutions WHERE rmu=? AND analysis_field=?", (rmu, field))
                reason = (
                    "Automatic reset: issue no longer exists after validation"
                    if field not in active else
                    "Automatic reset: issue source values changed after validation"
                )
                self.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    (rmu, f"resolution.{field}", old_summary, "UNRESOLVED", reason, "SYSTEM", now),
                )
                self._record_issue_field_change(
                    "RMU", rmu, field_name=f"resolution.{field}", old_value=old_summary, new_value="UNRESOLVED",
                    modified_by="SYSTEM", reason=reason, snapshot=self._rmu_issue_snapshot(rmu, row=row),
                    event_type="RESOLUTION_RESET", rmu=rmu,
                )
                cleared += 1
            elif old_fp != current_fp:
                self.db.execute(
                    "UPDATE rmu_resolutions SET analysis_fingerprint=?,modified_at=? WHERE rmu=? AND analysis_field=?",
                    (current_fp, now, rmu, field),
                )
        return cleared

    @staticmethod
    def _resolution_record_summary(record) -> str:
        if not record:
            return "Unresolved"
        data = dict(record) if not isinstance(record, dict) else record
        return resolution_display_text(data)

    @staticmethod
    def _resolution_issue_snapshot(row: dict, field: str) -> dict:
        field = clean(field).upper()
        candidates = list((((row or {}).get("resolution_candidates") or {}).get(field, []) or []))
        return {
            "analysis_field": field,
            "analysis_result": clean((row or {}).get(f"analysis_{field.lower()}")),
            "analysis_detail": clean((row or {}).get(f"analysis_{field.lower()}_detail")),
            "source_values": [dict(item or {}) for item in candidates],
        }

    def rmu_resolution_map(self, rmu: str | None = None) -> dict:
        if rmu:
            rows = self.db.execute(
                "SELECT * FROM rmu_resolutions WHERE rmu=? ORDER BY analysis_field", (clean(rmu),)
            )
            return {clean(row["analysis_field"]).upper(): dict(row) for row in rows}
        result: dict[str, dict[str, dict]] = {}
        for row in self.db.execute("SELECT * FROM rmu_resolutions ORDER BY rmu,analysis_field"):
            result.setdefault(clean(row["rmu"]), {})[clean(row["analysis_field"]).upper()] = dict(row)
        return result

    def rmu_resolution_summary(self, rmu: str) -> str:
        resolutions = self.rmu_resolution_map(rmu)
        parts = []
        for field in self._RMU_ANALYSIS_FIELDS:
            record = resolutions.get(field)
            if not record:
                continue
            parts.append(self._resolution_record_summary(record))
        return "\n".join(parts)

    def rmu_resolution_review_text(self, rmu: str) -> str:
        """Latest customer-facing Resolution plus independent per-issue comments."""
        resolutions = self.rmu_resolution_map(rmu)
        parts: list[str] = []
        for field in self._RMU_ANALYSIS_FIELDS:
            record = resolutions.get(field)
            if not record:
                continue
            parts.append(self._resolution_record_summary(record))
            comment = clean(record.get("customer_comment"))
            if comment:
                parts.append(f"{field} comment: {comment}")
        return "\n".join(parts)

    def rmu_resolution_tooltip(self, rmu: str) -> str:
        resolutions = self.rmu_resolution_map(rmu)
        if not resolutions:
            return "No Resolution decisions recorded."
        lines = []
        for field in self._RMU_ANALYSIS_FIELDS:
            record = resolutions.get(field)
            if not record:
                continue
            try:
                snapshot = json.loads(clean(record.get("issue_snapshot_json")) or "{}")
            except Exception:
                snapshot = {}
            detail = clean(snapshot.get("analysis_detail"))
            if detail:
                lines.append(f"{field} issue:\n{detail}")
            lines.append(f"Agreed resolution:\n{self._resolution_record_summary(record)}")
            customer_comment = clean(record.get("customer_comment"))
            if customer_comment:
                lines.append(f"Customer comment:\n{customer_comment}")
            lines.append("")
        return "\n".join(lines).strip() or "No Resolution decisions recorded."

    def set_rmu_resolution(
        self, rmu: str, analysis_field: str, decision_type: str, modified_by: str,
        *, selected_source: str = "", selected_value: str = "", normalized_value: str = "",
        analysis_fingerprint: str = "", decision_description: str = "", customer_comment: str = "",
        issue_snapshot: dict | None = None, reason: str = "RMU issue Resolution decision", _commit: bool = True,
    ) -> None:
        rmu = clean(rmu)
        field = clean(analysis_field).upper()
        decision = clean(decision_type).upper()
        if not rmu or field not in self._RMU_ANALYSIS_FIELDS:
            raise ValueError("RMU and a valid Analysis field are required")
        if decision not in {"USE_SOURCE", "NEEDS_ACTION", "ACCEPT_EXCEPTION", "OTHER"}:
            raise ValueError(f"Unsupported Resolution decision: {decision}")
        if decision == "OTHER" and not clean(selected_value):
            raise ValueError("A manual comment is required for OTHER")
        if decision == "USE_SOURCE" and not clean(selected_source):
            raise ValueError("A source is required for USE_SOURCE")
        description = clean(decision_description) or build_resolution_description(
            rmu=rmu, field=field, decision_type=decision,
            selected_source=selected_source, selected_value=selected_value, normalized_value=normalized_value,
        )
        snapshot_json = json.dumps(issue_snapshot or {}, ensure_ascii=False, sort_keys=True)
        current = self.db.execute(
            "SELECT * FROM rmu_resolutions WHERE rmu=? AND analysis_field=?", (rmu, field)
        ).fetchone()
        old_summary = self._resolution_record_summary(current) if current else "UNRESOLVED"
        now = datetime.now().isoformat(timespec="seconds")
        payload = (
            rmu, field, decision, clean(selected_source), clean(selected_value), clean(normalized_value),
            clean(analysis_fingerprint), description, clean(customer_comment), snapshot_json, modified_by or "system", now,
        )
        self.db.execute(
            """INSERT INTO rmu_resolutions
            (rmu,analysis_field,decision_type,selected_source,selected_value,normalized_value,analysis_fingerprint,decision_description,customer_comment,issue_snapshot_json,modified_by,modified_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(rmu,analysis_field) DO UPDATE SET
              decision_type=excluded.decision_type,selected_source=excluded.selected_source,
              selected_value=excluded.selected_value,normalized_value=excluded.normalized_value,
              analysis_fingerprint=excluded.analysis_fingerprint,decision_description=excluded.decision_description,
              customer_comment=excluded.customer_comment,issue_snapshot_json=excluded.issue_snapshot_json,
              modified_by=excluded.modified_by,modified_at=excluded.modified_at
            """, payload,
        )
        new_record = self.db.execute(
            "SELECT * FROM rmu_resolutions WHERE rmu=? AND analysis_field=?", (rmu, field)
        ).fetchone()
        new_summary = self._resolution_record_summary(new_record)
        if old_summary != new_summary:
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (rmu, f"resolution.{field}", old_summary, new_summary, reason, modified_by or "system", now),
            )
            self._record_issue_field_change(
                "RMU", rmu, field_name=f"resolution.{field}", old_value=old_summary, new_value=new_summary,
                modified_by=modified_by or "system", reason=reason, snapshot=self._rmu_issue_snapshot(rmu),
                event_type="RESOLUTION_CHANGED", rmu=rmu,
            )
        if _commit:
            self.db.commit()

    def clear_rmu_resolution(self, rmu: str, analysis_field: str, modified_by: str, reason: str = "Resolution cleared", *, _commit: bool = True) -> None:
        rmu = clean(rmu); field = clean(analysis_field).upper()
        current = self.db.execute(
            "SELECT * FROM rmu_resolutions WHERE rmu=? AND analysis_field=?", (rmu, field)
        ).fetchone()
        if not current:
            return
        old_summary = self._resolution_record_summary(current)
        now = datetime.now().isoformat(timespec="seconds")
        self.db.execute("DELETE FROM rmu_resolutions WHERE rmu=? AND analysis_field=?", (rmu, field))
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (rmu, f"resolution.{field}", old_summary, "UNRESOLVED", reason, modified_by or "system", now),
        )
        self._record_issue_field_change(
            "RMU", rmu, field_name=f"resolution.{field}", old_value=old_summary, new_value="UNRESOLVED",
            modified_by=modified_by or "system", reason=reason, snapshot=self._rmu_issue_snapshot(rmu),
            event_type="RESOLUTION_CHANGED", rmu=rmu,
        )
        if _commit:
            self.db.commit()

    def save_rmu_resolution_decisions(
        self, rmu: str, row: dict, decisions: dict[str, dict | None], modified_by: str
    ) -> tuple[str, str]:
        """Persist every active RMU decision in one SQLite transaction.

        The previous UI path committed once per FALSE field, then committed the
        Review state again.  On networked/slow disks that made a single dialog
        save visibly stall.  One transaction keeps audit/history semantics but
        reduces the write path to one durable commit.
        """
        rmu = clean(rmu)
        active = self._active_rmu_issue_fields(row)
        previous = self.rmu_resolution_map(rmu)
        previous_comments = {
            field: clean((previous.get(field) or {}).get("customer_comment"))
            for field in active
        }
        try:
            self.db.execute("BEGIN IMMEDIATE")
            for field in active:
                payload = (decisions or {}).get(field)
                if not payload:
                    self.clear_rmu_resolution(
                        rmu, field, modified_by, reason="RMU Resolution set to Unresolved", _commit=False
                    )
                    continue
                self.set_rmu_resolution(
                    rmu=rmu, analysis_field=field, decision_type=payload.get("decision_type", ""),
                    selected_source=payload.get("selected_source", ""),
                    selected_value=payload.get("selected_value", ""),
                    normalized_value=payload.get("normalized_value", ""),
                    analysis_fingerprint=self._rmu_field_fingerprint(row, field),
                    decision_description=payload.get("decision_description", ""),
                    customer_comment=payload.get("customer_comment", ""),
                    issue_snapshot=payload.get("issue_snapshot") or self._resolution_issue_snapshot(row, field),
                    modified_by=modified_by, reason="Structured RMU Resolution decision", _commit=False,
                )
            review_status = self.sync_rmu_review_from_resolutions(
                rmu, row, modified_by, _commit=False
            )
            saved_after = self.rmu_resolution_map(rmu)
            for field in active:
                before_comment = previous_comments.get(field, "")
                after_comment = clean((saved_after.get(field) or {}).get("customer_comment"))
                payload = (decisions or {}).get(field) or {}
                explicit_comment_submission = bool(payload.get("customer_comment_submitted"))
                # v0.8.147: the Resolution dialog has a separate blank "New Customer
                # Comment" editor. Saving only a Resolution must preserve the latest
                # comment without creating another note. An explicit non-blank
                # submission is always an append-only review event, even when the
                # reviewer deliberately repeats the same wording in a later round.
                if explicit_comment_submission or before_comment != after_comment:
                    self._append_rmu_review_event(
                        rmu,
                        analysis_field=field,
                        event_type="RESOLUTION_COMMENT_CLEARED" if not after_comment else "RESOLUTION_COMMENT_RECORDED",
                        review_status=review_status,
                        comment=after_comment,
                        modified_by=modified_by,
                        snapshot={
                            "previous_comment": before_comment,
                            "customer_comment": after_comment,
                            "explicit_comment_submission": explicit_comment_submission,
                            "resolution": dict(saved_after.get(field) or {}),
                            "issue": self._resolution_issue_snapshot(row, field),
                        },
                    )
            summary = self.rmu_resolution_summary(rmu) or "Unresolved"
            self.db.commit()
            return review_status, summary
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _normalized_resolution_value(record: dict | None) -> str:
        """Return the normalized value frozen with a structured decision.

        Resolution candidates already carry the same field-specific normalized
        value used by automatic Analysis.  Falling back to the raw value keeps
        older persisted decisions compatible.
        """
        record = record or {}
        return clean(record.get("normalized_value") or record.get("selected_value")).upper()

    @staticmethod
    def _adms_db_candidate_for_field(row: dict, field: str) -> dict | None:
        """Return the ADMS DB candidate for an Analysis field when available.

        ADMS DB is the customer's reference for NAME / FEEDER / SMART / TYPE.
        Some checks, notably IP, intentionally have no ADMS DB candidate; those
        keep the pre-v0.8.54 Resolution behavior.
        """
        candidates = list((((row or {}).get("resolution_candidates") or {}).get(clean(field).upper(), []) or []))
        for candidate in candidates:
            if clean((candidate or {}).get("source")).upper() == "ADMS DB":
                return dict(candidate or {})
        return None

    @classmethod
    def _resolution_differs_from_adms_db(cls, row: dict, field: str, record: dict | None) -> bool:
        """True when a USE_SOURCE choice disagrees with an available ADMS DB value.

        Only fields that actually expose an ADMS DB validation candidate use
        this rule. If ADMS DB is absent/blank for the field, existing Resolution
        semantics are preserved.
        """
        record = record or {}
        if clean(record.get("decision_type")).upper() != "USE_SOURCE":
            return False
        adms = cls._adms_db_candidate_for_field(row, field)
        if not adms:
            return False
        adms_value = clean(adms.get("normalized") or adms.get("value")).upper()
        if not adms_value:
            return False

        selected_source = clean(record.get("selected_source")).upper()
        if selected_source == "ADMS DB":
            # A persisted ADMS DB choice is authoritative even for an older
            # record that predates normalized_value persistence. The decision
            # fingerprint still protects against stale validation inputs.
            return False

        selected_value = cls._normalized_resolution_value(record)
        if not clean(record.get("normalized_value")) and selected_source:
            candidates = list((((row or {}).get("resolution_candidates") or {}).get(clean(field).upper(), []) or []))
            source_candidate = next((
                candidate for candidate in candidates
                if clean((candidate or {}).get("source")).upper() == selected_source
            ), None)
            if source_candidate:
                selected_value = clean(source_candidate.get("normalized") or source_candidate.get("value")).upper()
        return selected_value != adms_value

    def sync_rmu_review_from_resolutions(self, rmu: str, row: dict, modified_by: str, *, _commit: bool = True) -> str:
        """Derive Review from the customer's structured Resolution decisions.

        For an active FALSE field that has an ADMS DB candidate, selecting a
        value equal to ADMS DB automatically closes that decision. Selecting a
        different source/value automatically puts the RMU in NEEDS ACTION.
        Explicit Needs Action still wins, unresolved issues still remain
        Unreviewed, and fields without an ADMS DB candidate keep the previous
        resolved/closed behavior.
        """
        active = self._active_rmu_issue_fields(row)
        if not active:
            return clean(self.rmu_review_map().get(rmu, {}).get("review_status")).upper() or "UNREVIEWED"
        resolutions = self.rmu_resolution_map(rmu)
        current_status = clean(self.rmu_review_map().get(rmu, {}).get("review_status")).upper() or "UNREVIEWED"

        if any(clean((resolutions.get(field) or {}).get("decision_type")).upper() == "NEEDS_ACTION" for field in active):
            target = "NEEDS ACTION"
        elif any(
            self._resolution_differs_from_adms_db(row, field, resolutions.get(field))
            for field in active if field in resolutions
        ):
            target = "NEEDS ACTION"
        elif current_status == "CLOSED":
            # Preserve an explicit human Closed state unless a newly saved
            # Resolution explicitly disagrees with the ADMS DB reference.
            target = "CLOSED"
        elif any(field not in resolutions for field in active):
            target = "UNREVIEWED"
        else:
            target = "CLOSED"
        self.update_rmu_review_status(
            rmu, target, modified_by, reason="Automatic Review state from structured Resolution decisions", _commit=_commit
        )
        return target

    @classmethod
    def _rmu_analysis_hash(cls, row: dict) -> str:
        """Fingerprint only the currently active automatic RMU Analysis fields.

        Manual Review stays valid when unrelated source/display data changes.
        Retired compatibility fields (for example legacy LINK) must not reopen a
        reviewed RMU merely because their raw source value changes.
        """
        payload = {}
        for field in cls._RMU_ANALYSIS_FIELDS:
            key = f"analysis_{field.lower()}"
            payload[key] = clean((row or {}).get(key))
            payload[f"{key}_detail"] = clean((row or {}).get(f"{key}_detail"))
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _sync_rmu_review_analysis_hash(self, rmu: str, analysis_hash: str, row: dict | None = None) -> None:
        current = self.db.execute("SELECT * FROM rmu_reviews WHERE rmu=?", (rmu,)).fetchone()
        now = datetime.now().isoformat(timespec="seconds")
        if current is None:
            self.db.execute(
                "INSERT INTO rmu_reviews(rmu,review_status,reviewed_by,reviewed_at,updated_at,analysis_hash) VALUES(?,?,?,?,?,?)",
                (rmu, "UNREVIEWED", "", "", now, analysis_hash),
            )
            return
        old_hash = clean(current["analysis_hash"])
        status = clean(current["review_status"]).upper() or "UNREVIEWED"
        explicit_unreviewed = status == "UNREVIEWED" and bool(clean(current["reviewed_by"]) or clean(current["reviewed_at"]))
        check_passed = bool(int(current["check_passed"] or 0)) if "check_passed" in current.keys() else False
        if old_hash and old_hash != analysis_hash and (status != "UNREVIEWED" or explicit_unreviewed):
            self._record_issue_field_change(
                "RMU", rmu, field_name="analysis_hash", old_value=old_hash, new_value=analysis_hash,
                modified_by="SYSTEM", reason="RMU validation result changed after source refresh",
                snapshot=self._rmu_issue_snapshot(rmu, row=row), event_type="VALIDATION_CHANGED", rmu=rmu,
            )
            self.db.execute(
                """UPDATE rmu_reviews
                SET review_status='UNREVIEWED',reviewed_by='',reviewed_at='',
                    check_passed=0,check_passed_by='',check_passed_at='',updated_at=?,analysis_hash=?
                WHERE rmu=?""",
                (now, analysis_hash, rmu),
            )
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (rmu, "rmu_review_status", status, "UNREVIEWED",
                 "Automatic reset: RMU validation result changed after source refresh", "SYSTEM", now),
            )
            if check_passed:
                self.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    (rmu, "rmu_check_passed", "PASS", "",
                     "Automatic reset: RMU validation result changed after source refresh", "SYSTEM", now),
                )
        elif old_hash != analysis_hash:
            if old_hash:
                self._record_issue_field_change(
                    "RMU", rmu, field_name="analysis_hash", old_value=old_hash, new_value=analysis_hash,
                    modified_by="SYSTEM", reason="RMU validation result changed after source refresh",
                    snapshot=self._rmu_issue_snapshot(rmu, row=row), event_type="VALIDATION_CHANGED", rmu=rmu,
                )
            if check_passed and old_hash:
                self.db.execute(
                    "UPDATE rmu_reviews SET check_passed=0,check_passed_by='',check_passed_at='',analysis_hash=?,updated_at=? WHERE rmu=?",
                    (analysis_hash, now, rmu),
                )
                self.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    (rmu, "rmu_check_passed", "PASS", "",
                     "Automatic reset: RMU validation result changed after source refresh", "SYSTEM", now),
                )
            else:
                self.db.execute("UPDATE rmu_reviews SET analysis_hash=?,updated_at=? WHERE rmu=?", (analysis_hash, now, rmu))

    def save_comparison(self, rows: list[dict]):
        overrides = {}
        legacy_fields = {"zsld_picture": "zsld_screen_name"}
        for item in self.db.execute("SELECT * FROM changes ORDER BY id"):
            field_name = legacy_fields.get(item["field_name"], item["field_name"])
            overrides[(item["rmu"], field_name)] = item["new_value"]
        self.db.execute("DELETE FROM comparison")
        sql = """INSERT INTO comparison
        (rmu,no,station,se_feeder,se_device,oh_ug,zenon_feeder,zenon_type,picture,
         adms_db_feeder,adms_db_type,adms_sld_type,smart,status,remarks,comments,auto_json,updated_at,data_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
        for row in rows:
            auto = dict(row)
            rmu = clean(auto.get("rmu"))
            if rmu:
                self._sync_rmu_review_analysis_hash(rmu, self._rmu_analysis_hash(auto), row=auto)
                self._sync_rmu_resolutions(rmu, auto)
            for field in EDITABLE_COLUMNS:
                if (row["rmu"], field) in overrides:
                    row[field] = overrides[(row["rmu"], field)]
            values = [row.get(k, "") for k in (
                "rmu", "no", "se_station", "se_feeder", "se_smart", "se_oh_ug",
                "zsld_feeder", "zsld_type", "zsld_screen_name", "adb_gss_fid",
                "adb_type", "asld_type", "asld_smart", "status", "remarks", "comments")]
            values += [json.dumps(auto, ensure_ascii=False), datetime.now().isoformat(timespec="seconds"), json.dumps(row, ensure_ascii=False)]
            self.db.execute(sql, values)
        self.db.commit()

    def comparison_row_count(self) -> int:
        """Return cached RMU row count without decoding any comparison JSON."""
        record = self.db.execute("SELECT COUNT(*) FROM comparison").fetchone()
        return int(record[0] or 0) if record is not None else 0

    def rows(self) -> list[dict]:
        result = []
        for record in self.db.execute("SELECT * FROM comparison ORDER BY no, rmu"):
            row = dict(record)
            result.append(json.loads(row.get("data_json") or "{}") or row)
        return result

    def row_by_rmu(self, rmu: str) -> dict | None:
        """Fetch one comparison row without deserializing the whole site."""
        record = self.db.execute("SELECT * FROM comparison WHERE rmu=?", (clean(rmu),)).fetchone()
        if record is None:
            return None
        row = dict(record)
        return json.loads(row.get("data_json") or "{}") or row

    def update_value(self, rmu, field, new_value, modified_by, reason):
        row = self.db.execute("SELECT data_json FROM comparison WHERE rmu=?", (rmu,)).fetchone()
        if not row:
            return
        data = json.loads(row[0] or "{}")
        old_value = clean(data.get(field))
        new_value = clean(new_value)
        if old_value == new_value:
            return
        now = datetime.now().isoformat(timespec="seconds")
        data[field] = new_value
        if field == "comments":
            self.db.execute(
                "UPDATE comparison SET data_json=?, comments=?, updated_at=? WHERE rmu=?",
                (json.dumps(data, ensure_ascii=False), new_value, now, rmu),
            )
        else:
            self.db.execute("UPDATE comparison SET data_json=?, updated_at=? WHERE rmu=?", (json.dumps(data, ensure_ascii=False), now, rmu))
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (rmu, field, old_value, new_value, reason, modified_by, now),
        )
        self._record_issue_field_change(
            "RMU", clean(rmu), field_name=field, old_value=old_value, new_value=new_value,
            modified_by=modified_by or "system", reason=reason, snapshot=self._rmu_issue_snapshot(clean(rmu)),
            event_type="COMMENT_CHANGED" if field in {"comments", "remarks"} else "FIELD_CHANGED", rmu=clean(rmu),
        )
        self.db.commit()

    def save_version(self, name: str, description: str, created_by: str) -> int:
        snapshot = {
            "project": self.config,
            "rows": self.rows(),
            "changes": self.changes(),
            "rmu_reviews": list(self.rmu_review_map().values()),
            "rmu_resolutions": self.rmu_resolution_map(),
            "rmu_action_tracking": self.rmu_action_tracking(),
            "issue_cases": self.issue_cases(),
            "issue_events": [event for case in self.issue_cases() for event in self.issue_case_events(int(case["id"]))],
            "rmu_review_events": self.rmu_review_events(),
            "db_smart_reviews": list(self.db_smart_review_map().values()),
            "source_file_selections": list(self.source_file_selections().values()),
            "source_display_names": {
                source_type: self.source_display_names(source_type)
                for source_type in sorted({row["source_type"] for row in self.db.execute("SELECT DISTINCT source_type FROM source_display_names")})
            },
        }
        cursor = self.db.execute(
            "INSERT INTO versions(version_name,description,snapshot_json,created_by,created_at) VALUES(?,?,?,?,?)",
            (name, description, json.dumps(snapshot, ensure_ascii=False), created_by, datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def versions(self):
        return [dict(r) for r in self.db.execute("SELECT id,version_name,description,created_by,created_at FROM versions ORDER BY id DESC")]

    def changes(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM changes ORDER BY id DESC")]

    # ------------------------- durable site history -------------------------
    def create_site_revision(
        self, revision_name: str, description: str, created_by: str, *, version_id: int | None = None
    ) -> int:
        name = clean(revision_name)
        if not name:
            raise ValueError("Revision name is required")
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.db.execute(
            "INSERT INTO site_revisions(revision_name,description,version_id,created_by,created_at) VALUES(?,?,?,?,?)",
            (name, str(description or "").strip(), version_id, created_by or "system", now),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def site_revisions(self) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT id,revision_name,description,version_id,created_by,created_at "
                "FROM site_revisions ORDER BY id DESC"
            )
        ]

    def latest_site_revision(self) -> dict | None:
        row = self.db.execute(
            "SELECT id,revision_name,description,version_id,created_by,created_at "
            "FROM site_revisions ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def add_issue_action(
        self,
        *,
        revision_id: int | None,
        category: str,
        equipment: str,
        issue: str,
        action_taken: str,
        result: str,
        comments: str,
        created_by: str,
    ) -> int:
        issue_text = str(issue or "").strip()
        if not issue_text:
            raise ValueError("Issue description is required")
        normalized_result = clean(result).upper() or "OPEN"
        if normalized_result not in {"OPEN", "PASS", "CLOSED", "NEEDS ACTION", "N/A"}:
            raise ValueError(f"Unsupported issue result: {normalized_result}")
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.db.execute(
            """INSERT INTO issue_actions
            (revision_id,category,equipment,issue,action_taken,result,comments,created_by,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                revision_id,
                clean(category) or "Other",
                clean(equipment),
                issue_text,
                str(action_taken or "").strip(),
                normalized_result,
                str(comments or "").strip(),
                created_by or "system",
                now,
                now,
            ),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def issue_actions(self, revision_id: int | None = None) -> list[dict]:
        sql = (
            "SELECT ia.*, sr.revision_name FROM issue_actions ia "
            "LEFT JOIN site_revisions sr ON sr.id=ia.revision_id"
        )
        params: tuple = ()
        if revision_id is not None:
            sql += " WHERE ia.revision_id=?"
            params = (int(revision_id),)
        sql += " ORDER BY ia.id DESC"
        return [dict(row) for row in self.db.execute(sql, params)]

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def record_signoff_report(
        self,
        *,
        revision_id: int | None,
        path: Path,
        snapshot: dict,
        created_by: str,
        report_type: str = "SITE_SIGNOFF",
    ) -> int:
        target = Path(path).resolve()
        now = datetime.now().isoformat(timespec="seconds")
        cursor = self.db.execute(
            """INSERT INTO signoff_reports
            (revision_id,report_type,file_name,file_path,report_status,snapshot_json,sha256,created_by,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                revision_id,
                report_type,
                target.name,
                str(target),
                "GENERATED",
                json.dumps(snapshot or {}, ensure_ascii=False),
                self._sha256_file(target),
                created_by or "system",
                now,
            ),
        )
        self.db.commit()
        return int(cursor.lastrowid)

    def signoff_reports(self) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT srp.*, rev.revision_name
                FROM signoff_reports srp
                LEFT JOIN site_revisions rev ON rev.id=srp.revision_id
                ORDER BY srp.id DESC"""
            )
        ]

    def attach_signed_report(self, report_id: int, selected_pdf: Path) -> Path:
        source = Path(selected_pdf)
        if not source.exists() or source.suffix.lower() != ".pdf":
            raise ValueError("Select a valid signed PDF file")
        row = self.db.execute("SELECT * FROM signoff_reports WHERE id=?", (int(report_id),)).fetchone()
        if row is None:
            raise ValueError("Sign-off report record was not found")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(row["file_name"]).stem
        target = self.signed_reports_dir / f"{base}_SIGNED_{stamp}.pdf"
        shutil.copy2(source, target)
        now = datetime.now().isoformat(timespec="seconds")
        self.db.execute(
            """UPDATE signoff_reports
            SET report_status='SIGNED',signed_file_name=?,signed_file_path=?,signed_sha256=?,signed_at=?
            WHERE id=?""",
            (target.name, str(target.resolve()), self._sha256_file(target), now, int(report_id)),
        )
        self.db.commit()
        return target


    # ------------------------- Need Action lifecycle -------------------------
    @staticmethod
    def _json_text(value: object) -> str:
        if isinstance(value, str):
            try:
                json.loads(value or "{}")
                return value or "{}"
            except Exception:
                return json.dumps({"value": value}, ensure_ascii=False, sort_keys=True)
        return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, default=str)

    def _rmu_issue_snapshot(self, rmu: str, row: dict | None = None) -> dict:
        data = dict(row or self.row_by_rmu(rmu) or {})
        review = self.rmu_review_map().get(clean(rmu), {})
        resolutions = self.rmu_resolution_map(clean(rmu))
        return {
            "entity_type": "RMU",
            "rmu": clean(rmu),
            "review_status": clean(review.get("review_status")),
            "manual_comment": clean(review.get("manual_comment")),
            "analysis": {
                field: clean(data.get(f"analysis_{field.lower()}"))
                for field in self._RMU_ANALYSIS_FIELDS
            },
            "analysis_detail": {
                field: clean(data.get(f"analysis_{field.lower()}_detail"))
                for field in self._RMU_ANALYSIS_FIELDS
                if clean(data.get(f"analysis_{field.lower()}_detail"))
            },
            "resolutions": {
                field: self._resolution_record_summary(record)
                for field, record in resolutions.items()
            },
        }

    @staticmethod
    def _signal_issue_snapshot(
        *, row_key: str, rmu: str, review_status: str = "", comments: str = "",
        source_hash: str = "", row_hash: str = "", metadata: dict | None = None,
    ) -> dict:
        meta = dict(metadata or {})
        raw_snapshot = meta.get("signal_snapshot_json") or "{}"
        try:
            signal = json.loads(raw_snapshot) if isinstance(raw_snapshot, str) else dict(raw_snapshot or {})
        except Exception:
            signal = {}
        return {
            "entity_type": "SIGNAL",
            "row_key": clean(row_key),
            "rmu": clean(rmu),
            "point_no": clean(meta.get("point_no")),
            "signal_name": clean(meta.get("signal_name")),
            "signal_category": clean(meta.get("signal_category")),
            "review_status": clean(review_status).upper(),
            "comments": clean(comments),
            "source_hash": clean(source_hash),
            "row_hash": clean(row_hash),
            "signal": signal,
        }

    def _append_rmu_review_event(
        self, rmu: str, *, analysis_field: str = "", event_type: str = "COMMENT_RECORDED",
        review_status: str = "", comment: str = "", modified_by: str = "",
        snapshot: dict | None = None, modified_at: str | None = None, case_id: int | None = None,
    ) -> int:
        """Append one immutable human-review note/event for an RMU.

        A review note may exist before the RMU ever becomes Needs Action.  In
        that case ``case_id`` deliberately remains NULL.  If a formal Needs
        Action case is currently open, the note is linked to that case.
        """
        rmu = clean(rmu)
        if not rmu:
            raise ValueError("RMU is required for review history")
        if case_id is None:
            open_case = self._issue_case_row("RMU", rmu, open_only=True)
            case_id = int(open_case["id"]) if open_case is not None else None
        status = clean(review_status).upper()
        if not status:
            review = self.rmu_review_map().get(rmu, {})
            status = clean(review.get("review_status")).upper() or "UNREVIEWED"
        stamp = modified_at or datetime.now().isoformat(timespec="seconds")
        cursor = self.db.execute(
            """INSERT INTO rmu_review_events(
                rmu,case_id,analysis_field,event_type,review_status,comment,
                modified_by,modified_at,snapshot_json,app_version
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                rmu, case_id, clean(analysis_field).upper(), clean(event_type).upper() or "COMMENT_RECORDED",
                status, str(comment or ""), modified_by or "system", stamp,
                self._json_text(snapshot), __version__,
            ),
        )
        return int(cursor.lastrowid)

    def rmu_review_events(self, rmu: str | None = None) -> list[dict]:
        """Return append-only RMU review/comment submissions in chronological order."""
        args: tuple[object, ...] = ()
        where = ""
        if rmu:
            where = " WHERE e.rmu=?"
            args = (clean(rmu),)
        rows = self.db.execute(
            """SELECT e.*,COALESCE(c.case_no,0) AS case_no,COALESCE(c.status,'') AS case_status
                 FROM rmu_review_events e
                 LEFT JOIN issue_cases c ON c.id=e.case_id""" + where +
            " ORDER BY e.modified_at,e.id",
            args,
        )
        return [dict(row) for row in rows]

    def _issue_case_row(self, entity_type: str, entity_key: str, *, open_only: bool = False):
        entity_type = clean(entity_type).upper()
        entity_key = clean(entity_key)
        if not entity_type or not entity_key:
            return None
        sql = "SELECT * FROM issue_cases WHERE entity_type=? AND entity_key=?"
        args: list[object] = [entity_type, entity_key]
        if open_only:
            sql += " AND status='OPEN'"
        sql += " ORDER BY case_no DESC,id DESC LIMIT 1"
        return self.db.execute(sql, tuple(args)).fetchone()

    def _append_issue_event(
        self, case_id: int, event_type: str, *, field_name: str = "",
        old_value: str = "", new_value: str = "", reason: str = "",
        modified_by: str = "", snapshot: dict | None = None, modified_at: str | None = None,
    ) -> int:
        stamp = modified_at or datetime.now().isoformat(timespec="seconds")
        cursor = self.db.execute(
            """INSERT INTO issue_events(
                case_id,event_type,field_name,old_value,new_value,reason,modified_by,modified_at,snapshot_json,app_version
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                int(case_id), clean(event_type).upper() or "UPDATED", clean(field_name),
                str(old_value or ""), str(new_value or ""), str(reason or ""),
                modified_by or "system", stamp, self._json_text(snapshot), __version__,
            ),
        )
        self.db.execute("UPDATE issue_cases SET updated_at=? WHERE id=?", (stamp, int(case_id)))
        return int(cursor.lastrowid)

    def _open_issue_case(
        self, entity_type: str, entity_key: str, *, site_name: str = "", rmu: str = "",
        point_no: str = "", signal_name: str = "", modified_by: str = "", reason: str = "",
        snapshot: dict | None = None, old_status: str = "UNREVIEWED",
    ) -> int:
        entity_type = clean(entity_type).upper()
        entity_key = clean(entity_key)
        current = self._issue_case_row(entity_type, entity_key, open_only=True)
        if current:
            return int(current["id"])
        row = self.db.execute(
            "SELECT COALESCE(MAX(case_no),0) FROM issue_cases WHERE entity_type=? AND entity_key=?",
            (entity_type, entity_key),
        ).fetchone()
        case_no = int(row[0] or 0) + 1
        now = datetime.now().isoformat(timespec="seconds")
        snap = self._json_text(snapshot)
        cursor = self.db.execute(
            """INSERT INTO issue_cases(
                entity_type,entity_key,case_no,site_name,rmu,point_no,signal_name,status,
                opened_at,opened_by,open_reason,open_snapshot_json,app_version,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,'OPEN',?,?,?,?,?,?,?)""",
            (
                entity_type, entity_key, case_no, clean(site_name), clean(rmu), clean(point_no), clean(signal_name),
                now, modified_by or "system", reason or f"{entity_type} Needs Action", snap, __version__, now, now,
            ),
        )
        case_id = int(cursor.lastrowid)
        self._append_issue_event(
            case_id, "CASE_OPENED", field_name="review_status", old_value=clean(old_status).upper(),
            new_value="NEEDS ACTION", reason=reason or f"{entity_type} Needs Action opened",
            modified_by=modified_by, snapshot=snapshot, modified_at=now,
        )
        return case_id

    def _sync_issue_case_status(
        self, entity_type: str, entity_key: str, *, old_status: str, new_status: str,
        modified_by: str, reason: str, site_name: str = "", rmu: str = "",
        point_no: str = "", signal_name: str = "", snapshot: dict | None = None,
    ) -> None:
        old_status = clean(old_status).upper() or "UNREVIEWED"
        new_status = clean(new_status).upper() or "UNREVIEWED"
        open_case = self._issue_case_row(entity_type, entity_key, open_only=True)
        if new_status == "NEEDS ACTION":
            if open_case is None:
                self._open_issue_case(
                    entity_type, entity_key, site_name=site_name, rmu=rmu, point_no=point_no,
                    signal_name=signal_name, modified_by=modified_by, reason=reason,
                    snapshot=snapshot, old_status=old_status,
                )
            elif old_status != new_status:
                self._append_issue_event(
                    int(open_case["id"]), "STATUS_CHANGED", field_name="review_status",
                    old_value=old_status, new_value=new_status, reason=reason,
                    modified_by=modified_by, snapshot=snapshot,
                )
            return
        if open_case is None:
            return
        case_id = int(open_case["id"])
        if new_status == "CLOSED":
            now = datetime.now().isoformat(timespec="seconds")
            self._append_issue_event(
                case_id, "CASE_CLOSED", field_name="review_status", old_value=old_status,
                new_value="CLOSED", reason=reason or "Needs Action closed",
                modified_by=modified_by, snapshot=snapshot, modified_at=now,
            )
            self.db.execute(
                """UPDATE issue_cases SET status='CLOSED',closed_at=?,closed_by=?,close_reason=?,
                    close_snapshot_json=?,updated_at=? WHERE id=?""",
                (now, modified_by or "system", reason or "Needs Action closed", self._json_text(snapshot), now, case_id),
            )
        elif old_status != new_status:
            # UNREVIEWED does not remove the formal follow-up.  The case remains
            # OPEN until an explicit CLOSED decision, but the state transition is
            # preserved in the timeline.
            self._append_issue_event(
                case_id, "STATUS_CHANGED", field_name="review_status", old_value=old_status,
                new_value=new_status, reason=reason, modified_by=modified_by, snapshot=snapshot,
            )

    def _record_issue_field_change(
        self, entity_type: str, entity_key: str, *, field_name: str, old_value: str,
        new_value: str, modified_by: str, reason: str, snapshot: dict | None = None,
        event_type: str = "FIELD_CHANGED", open_if_needed: bool = False,
        site_name: str = "", rmu: str = "", point_no: str = "", signal_name: str = "",
        old_status: str = "UNREVIEWED",
    ) -> None:
        if str(old_value or "") == str(new_value or ""):
            return
        case = self._issue_case_row(entity_type, entity_key, open_only=True)
        if case is None and open_if_needed:
            case_id = self._open_issue_case(
                entity_type, entity_key, site_name=site_name, rmu=rmu, point_no=point_no,
                signal_name=signal_name, modified_by=modified_by, reason=reason,
                snapshot=snapshot, old_status=old_status,
            )
            case = self.db.execute("SELECT * FROM issue_cases WHERE id=?", (case_id,)).fetchone()
        if case is None:
            case = self._issue_case_row(entity_type, entity_key, open_only=False)
        if case is None:
            return
        self._append_issue_event(
            int(case["id"]), event_type, field_name=field_name, old_value=old_value,
            new_value=new_value, reason=reason, modified_by=modified_by, snapshot=snapshot,
        )

    def issue_cases(
        self, *, entity_type: str | None = None, status: str | None = None,
        entity_key: str | None = None,
    ) -> list[dict]:
        clauses = []
        args: list[object] = []
        if entity_type:
            clauses.append("c.entity_type=?"); args.append(clean(entity_type).upper())
        if status:
            clauses.append("c.status=?"); args.append(clean(status).upper())
        if entity_key:
            clauses.append("c.entity_key=?"); args.append(clean(entity_key))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.db.execute(
            """SELECT c.*,
                (SELECT COUNT(*) FROM issue_events e WHERE e.case_id=c.id) AS event_count,
                (SELECT COUNT(DISTINCT CASE WHEN UPPER(TRIM(COALESCE(e.modified_by,''))) NOT IN ('SYSTEM','MIGRATION','')
                    THEN e.modified_by END) FROM issue_events e WHERE e.case_id=c.id) AS participant_count,
                (SELECT MAX(e.modified_at) FROM issue_events e WHERE e.case_id=c.id) AS last_event_at
               FROM issue_cases c""" + where + " ORDER BY c.updated_at DESC,c.id DESC",
            tuple(args),
        )
        return [dict(row) for row in rows]

    def issue_case_events(self, case_id: int) -> list[dict]:
        return [
            dict(row) for row in self.db.execute(
                "SELECT * FROM issue_events WHERE case_id=? ORDER BY id", (int(case_id),)
            )
        ]

    def issue_lifecycle(self, entity_type: str, entity_key: str) -> list[dict]:
        cases = self.issue_cases(entity_type=entity_type, entity_key=entity_key)
        for case in cases:
            case["events"] = self.issue_case_events(int(case["id"]))
        return cases

    def rmu_full_lifecycle(self, rmu: str) -> dict:
        """Return the complete formal lifecycle for one RMU and its child signals.

        The v11 lifecycle tables intentionally store RMU and Signal cases as
        separate append-only entities.  RMU Data Review, however, is an RMU-
        centric workspace: when a reviewer selects RMU 15953 they need to see
        not only the RMU-level Needs Action case, but also every Signal Mapping
        case that belongs to that same RMU.  This helper performs that join once
        in the persistence layer and exposes a stable, read-only view to the UI.

        No history is synthesized here.  Only rows already present in
        ``issue_cases`` / ``issue_events`` are returned, so the audit guarantee
        remains append-only and backward compatible with schema v11.
        """
        rmu = clean(rmu)
        empty = {
            "rmu": rmu,
            "cases": [],
            "events": [],
            "case_count": 0,
            "open_count": 0,
            "closed_count": 0,
            "rmu_case_count": 0,
            "signal_case_count": 0,
            "event_count": 0,
            "participant_count": 0,
            "first_activity_at": "",
            "last_activity_at": "",
            "review_events": [],
            "review_event_count": 0,
        }
        if not rmu:
            return empty

        rows = self.db.execute(
            """SELECT c.*,
                (SELECT COUNT(*) FROM issue_events e WHERE e.case_id=c.id) AS event_count,
                (SELECT COUNT(DISTINCT CASE WHEN UPPER(TRIM(COALESCE(e.modified_by,''))) NOT IN ('SYSTEM','MIGRATION','')
                    THEN e.modified_by END) FROM issue_events e WHERE e.case_id=c.id) AS participant_count,
                (SELECT MAX(e.modified_at) FROM issue_events e WHERE e.case_id=c.id) AS last_event_at
               FROM issue_cases c
              WHERE (c.entity_type='RMU' AND c.entity_key=?)
                 OR (c.entity_type='SIGNAL' AND c.rmu=?)
              ORDER BY COALESCE(c.opened_at,c.created_at),c.id""",
            (rmu, rmu),
        )
        cases = [dict(row) for row in rows]

        participants: set[str] = set()
        events: list[dict] = []
        review_states = {"UNREVIEWED", "NEEDS ACTION", "CLOSED"}
        for case in cases:
            case_events = self.issue_case_events(int(case["id"]))
            case["events"] = case_events

            # ``issue_cases.status`` is the FINAL formal case state (OPEN/CLOSED).
            # It must not be copied onto every historical event: doing that made
            # a completed case look CLOSED even at the moment it was opened as
            # NEEDS ACTION.  Reconstruct the business review state as-of each
            # event from the append-only review_status transitions instead.
            event_state = ""
            for event in case_events:
                event_type = clean(event.get("event_type")).upper()
                field_name = clean(event.get("field_name")).lower()
                new_value = clean(event.get("new_value")).upper()
                if event_type == "CASE_OPENED":
                    event_state = "NEEDS ACTION"
                elif event_type == "CASE_CLOSED":
                    event_state = "CLOSED"
                elif field_name == "review_status":
                    if new_value in review_states:
                        event_state = new_value
                    elif new_value == "OPEN":
                        # Legacy baseline uses formal OPEN rather than the newer
                        # three-state review vocabulary. OPEN means the Needs
                        # Action follow-up was still active.
                        event_state = "NEEDS ACTION"
                    elif new_value == "CLOSED":
                        event_state = "CLOSED"

                if not event_state:
                    # Defensive fallback for imported histories that predate
                    # explicit CASE_OPENED events. This is only display metadata;
                    # no stored audit row is changed or fabricated.
                    event_state = "CLOSED" if clean(case.get("status")).upper() == "CLOSED" else "NEEDS ACTION"

                user = clean(event.get("modified_by"))
                if user.upper() not in {"", "SYSTEM", "MIGRATION"}:
                    participants.add(user)
                enriched = dict(event)
                enriched.update({
                    "case_no": int(case.get("case_no") or 0),
                    "case_status": clean(case.get("status")).upper(),
                    "event_state": event_state,
                    "entity_type": clean(case.get("entity_type")).upper(),
                    "entity_key": clean(case.get("entity_key")),
                    "rmu": clean(case.get("rmu")) or rmu,
                    "point_no": clean(case.get("point_no")),
                    "signal_name": clean(case.get("signal_name")),
                    "case_opened_at": clean(case.get("opened_at")),
                    "case_closed_at": clean(case.get("closed_at")),
                })
                events.append(enriched)

        # Event ids are local monotonically increasing keys.  Sorting primarily
        # by timestamp keeps imported/backfilled history readable while id keeps
        # simultaneous events deterministic.
        events.sort(key=lambda item: (clean(item.get("modified_at")), int(item.get("id") or 0)))
        activity_times = [clean(item.get("modified_at")) for item in events if clean(item.get("modified_at"))]
        if not activity_times:
            activity_times = [
                clean(case.get("opened_at") or case.get("created_at"))
                for case in cases
                if clean(case.get("opened_at") or case.get("created_at"))
            ]

        review_events = self.rmu_review_events(rmu)
        for item in review_events:
            user = clean(item.get("modified_by"))
            if user.upper() not in {"", "SYSTEM", "MIGRATION"}:
                participants.add(user)
        review_activity = [clean(item.get("modified_at")) for item in review_events if clean(item.get("modified_at"))]
        combined_activity = activity_times + review_activity

        return {
            "rmu": rmu,
            "cases": cases,
            "events": events,
            "review_events": review_events,
            "review_event_count": len(review_events),
            "case_count": len(cases),
            "open_count": sum(clean(case.get("status")).upper() == "OPEN" for case in cases),
            "closed_count": sum(clean(case.get("status")).upper() == "CLOSED" for case in cases),
            "rmu_case_count": sum(clean(case.get("entity_type")).upper() == "RMU" for case in cases),
            "signal_case_count": sum(clean(case.get("entity_type")).upper() == "SIGNAL" for case in cases),
            "event_count": len(events),
            "participant_count": len(participants),
            "first_activity_at": min(combined_activity) if combined_activity else "",
            "last_activity_at": max(combined_activity) if combined_activity else "",
        }

    def issue_lifecycle_counts(self) -> dict[str, int]:
        counts = {"OPEN": 0, "CLOSED": 0, "TOTAL": 0, "RMU": 0, "SIGNAL": 0}
        for row in self.db.execute(
            "SELECT status,entity_type,COUNT(*) AS n FROM issue_cases GROUP BY status,entity_type"
        ):
            n = int(row["n"] or 0)
            counts[clean(row["status"]).upper()] = counts.get(clean(row["status"]).upper(), 0) + n
            counts[clean(row["entity_type"]).upper()] = counts.get(clean(row["entity_type"]).upper(), 0) + n
            counts["TOTAL"] += n
        return counts


    def rmu_review_map(self) -> dict[str, dict]:
        return {
            row["rmu"]: dict(row)
            for row in self.db.execute("SELECT * FROM rmu_reviews")
        }

    def update_rmu_check_passed(
        self, rmu: str, passed: bool, modified_by: str,
        reason: str = "RMU manual verification changed",
    ) -> None:
        """Persist the Row Locator checkbox as a real manual pass/verification record.

        This flag is intentionally independent from the three-state Review field.
        It records that a human explicitly checked this RMU and accepted it for
        delivery/reporting; it is not transient table selection state.
        """
        rmu = clean(rmu)
        if not rmu:
            raise ValueError("RMU is required for manual verification")
        current = self.db.execute("SELECT * FROM rmu_reviews WHERE rmu=?", (rmu,)).fetchone()
        old_value = bool(int(current["check_passed"] or 0)) if current and "check_passed" in current.keys() else False
        new_value = bool(passed)
        if old_value == new_value:
            return
        now = datetime.now().isoformat(timespec="seconds")
        by = modified_by or "system"
        passed_by = by if new_value else ""
        passed_at = now if new_value else ""
        if current is None:
            self.db.execute(
                """INSERT INTO rmu_reviews(
                    rmu,review_status,manual_comment,check_passed,check_passed_by,check_passed_at,
                    reviewed_by,reviewed_at,updated_at,analysis_hash
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (rmu, "UNREVIEWED", "", int(new_value), passed_by, passed_at, "", "", now, ""),
            )
        else:
            self.db.execute(
                "UPDATE rmu_reviews SET check_passed=?,check_passed_by=?,check_passed_at=?,updated_at=? WHERE rmu=?",
                (int(new_value), passed_by, passed_at, now, rmu),
            )
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (rmu, "rmu_check_passed", "PASS" if old_value else "", "PASS" if new_value else "", reason, by, now),
        )
        self._record_issue_field_change(
            "RMU", rmu, field_name="check_passed", old_value="PASS" if old_value else "",
            new_value="PASS" if new_value else "", modified_by=by, reason=reason,
            snapshot=self._rmu_issue_snapshot(rmu), event_type="CHECK_CHANGED", rmu=rmu,
        )
        self.db.commit()

    def rmu_manual_review_comment(self, rmu: str) -> str:
        row = self.db.execute("SELECT manual_comment FROM rmu_reviews WHERE rmu=?", (clean(rmu),)).fetchone()
        return clean(row["manual_comment"]) if row else ""

    def append_rmu_manual_review_comment(
        self, rmu: str, comment: str, modified_by: str,
        reason: str = "RMU manual Review comment added",
    ) -> None:
        """Append one deliberate RMU review note and update the latest-value projection.

        Unlike the legacy latest-value editor, this API never treats an empty
        editor as a request to clear prior text.  Every non-blank submission is
        an immutable ``rmu_review_events`` record, even when a reviewer repeats
        the exact same wording during a later review round.  The grid still
        projects only the latest submitted comment through
        ``rmu_reviews.manual_comment``.
        """
        rmu = clean(rmu)
        if not rmu:
            raise ValueError("RMU is required for manual review comment")
        new_value = str(comment or "").strip()
        if not new_value:
            raise ValueError("A new RMU review comment is required")
        current = self.db.execute("SELECT * FROM rmu_reviews WHERE rmu=?", (rmu,)).fetchone()
        old_value = clean(current["manual_comment"]) if current and "manual_comment" in current.keys() else ""
        now = datetime.now().isoformat(timespec="seconds")
        if current is None:
            self.db.execute(
                "INSERT INTO rmu_reviews(rmu,review_status,manual_comment,reviewed_by,reviewed_at,updated_at,analysis_hash) VALUES(?,?,?,?,?,?,?)",
                (rmu, "UNREVIEWED", new_value, "", "", now, ""),
            )
        else:
            self.db.execute(
                "UPDATE rmu_reviews SET manual_comment=?,updated_at=? WHERE rmu=?",
                (new_value, now, rmu),
            )

        by = modified_by or "system"
        snapshot = self._rmu_issue_snapshot(rmu)
        self._append_rmu_review_event(
            rmu,
            event_type="COMMENT_RECORDED",
            review_status=clean(snapshot.get("review_status")),
            comment=new_value,
            modified_by=by,
            snapshot={
                **snapshot,
                "previous_comment": old_value,
                "submitted_comment": new_value,
                "append_only_submission": True,
            },
            modified_at=now,
        )

        # Change Audit remains change-oriented: identical repeated wording is a
        # new review event but not a value change.  When the projected latest
        # text changes, preserve the existing audit/lifecycle compatibility.
        if old_value != new_value:
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (rmu, "rmu_review_comment", old_value, new_value, reason, by, now),
            )
            self._record_issue_field_change(
                "RMU", rmu, field_name="comment", old_value=old_value, new_value=new_value,
                modified_by=by, reason=reason, snapshot=snapshot,
                event_type="COMMENT_CHANGED", rmu=rmu,
            )
        self.db.commit()

    def update_rmu_manual_review_comment(
        self, rmu: str, comment: str, modified_by: str,
        reason: str = "Optional RMU manual Review comment updated",
    ) -> None:
        """Update the latest RMU note while preserving every accepted note forever.

        ``rmu_reviews.manual_comment`` is only the latest-value projection used
        by the grid.  Every changed/cleared comment is also appended to
        ``rmu_review_events``.  Therefore a Pass RMU can be annotated before it
        ever enters Needs Action; if Needs Action is raised later, the tracker
        can reveal those earlier review notes as part of the complete process.
        """
        rmu = clean(rmu)
        if not rmu:
            raise ValueError("RMU is required for manual review comment")
        new_value = str(comment or "").strip()
        current = self.db.execute("SELECT * FROM rmu_reviews WHERE rmu=?", (rmu,)).fetchone()
        old_value = clean(current["manual_comment"]) if current and "manual_comment" in current.keys() else ""
        now = datetime.now().isoformat(timespec="seconds")
        if current is None:
            self.db.execute(
                "INSERT INTO rmu_reviews(rmu,review_status,manual_comment,reviewed_by,reviewed_at,updated_at,analysis_hash) VALUES(?,?,?,?,?,?,?)",
                (rmu, "UNREVIEWED", new_value, "", "", now, ""),
            )
        elif old_value != new_value:
            self.db.execute(
                "UPDATE rmu_reviews SET manual_comment=?,updated_at=? WHERE rmu=?",
                (new_value, now, rmu),
            )

        # Re-saving exactly the same non-blank note is not duplicated. A later
        # review with changed text is always a new immutable event.
        if old_value != new_value:
            by = modified_by or "system"
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (rmu, "rmu_review_comment", old_value, new_value, reason, by, now),
            )
            snapshot = self._rmu_issue_snapshot(rmu)
            self._append_rmu_review_event(
                rmu,
                event_type="COMMENT_CLEARED" if not new_value else "COMMENT_RECORDED",
                review_status=clean(snapshot.get("review_status")),
                comment=new_value,
                modified_by=by,
                snapshot={
                    **snapshot,
                    "previous_comment": old_value,
                    "submitted_comment": new_value,
                },
                modified_at=now,
            )
            # Keep the formal case audit compatible for existing Site History /
            # lifecycle readers. The compact RMU tracker suppresses this duplicate
            # and renders the richer rmu_review_events row instead.
            self._record_issue_field_change(
                "RMU", rmu, field_name="comment", old_value=old_value, new_value=new_value,
                modified_by=by, reason=reason, snapshot=snapshot,
                event_type="COMMENT_CHANGED", rmu=rmu,
            )
        self.db.commit()

    def update_rmu_review_status(
        self, rmu: str, review_status: str, modified_by: str,
        reason: str = "RMU Data Review status changed", *, _commit: bool = True,
    ) -> None:
        rmu = clean(rmu)
        if not rmu:
            raise ValueError("RMU is required for review status")
        value = clean(review_status).upper() or "UNREVIEWED"
        if value not in {"UNREVIEWED", "CLOSED", "NEEDS ACTION"}:
            raise ValueError(f"Invalid RMU review status: {value}")
        current = self.db.execute("SELECT * FROM rmu_reviews WHERE rmu=?", (rmu,)).fetchone()
        old_value = clean(current["review_status"]).upper() if current else "UNREVIEWED"
        if old_value == value and current is not None and (clean(current["reviewed_by"]) or clean(current["reviewed_at"])):
            return
        now = datetime.now().isoformat(timespec="seconds")
        # All three values are explicit workflow states when set through this
        # method. Automatic fingerprint resets bypass this method and clear the
        # reviewer metadata, letting the UI distinguish an explicit UNREVIEWED
        # decision from the automatic default.
        reviewed_by = modified_by or "system"
        reviewed_at = now
        self.db.execute(
            """INSERT INTO rmu_reviews(rmu,review_status,reviewed_by,reviewed_at,updated_at)
            VALUES(?,?,?,?,?)
            ON CONFLICT(rmu) DO UPDATE SET
              review_status=excluded.review_status,reviewed_by=excluded.reviewed_by,
              reviewed_at=excluded.reviewed_at,updated_at=excluded.updated_at
            """,
            (rmu, value, reviewed_by, reviewed_at, now),
        )
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (rmu, "rmu_review_status", old_value, value, reason, modified_by, now),
        )
        self._sync_issue_case_status(
            "RMU", rmu, old_status=old_value, new_status=value, modified_by=modified_by or "system",
            reason=reason, rmu=rmu, snapshot=self._rmu_issue_snapshot(rmu),
        )
        self._sync_rmu_action_tracking(rmu, value, modified_by, reason)
        if _commit:
            self.db.commit()


    def rmu_action_tracking(self, *, status: str | None = None) -> list[dict]:
        """Return durable RMU follow-up records (OPEN/CLOSED)."""
        if status:
            rows = self.db.execute(
                "SELECT * FROM rmu_action_tracking WHERE tracking_status=? ORDER BY updated_at DESC,rmu",
                (clean(status).upper(),),
            )
        else:
            rows = self.db.execute("SELECT * FROM rmu_action_tracking ORDER BY updated_at DESC,rmu")
        return [dict(row) for row in rows]

    def rmu_action_tracking_counts(self) -> dict[str, int]:
        counts = {"OPEN": 0, "CLOSED": 0, "TOTAL": 0}
        for row in self.db.execute(
            "SELECT tracking_status,COUNT(*) AS n FROM rmu_action_tracking GROUP BY tracking_status"
        ):
            key = clean(row["tracking_status"]).upper()
            counts[key] = int(row["n"] or 0)
            counts["TOTAL"] += int(row["n"] or 0)
        return counts

    def _sync_rmu_action_tracking(
        self, rmu: str, review_status: str, modified_by: str, reason: str
    ) -> None:
        """Open/reopen on NEEDS ACTION and close only on explicit CLOSED.

        UNREVIEWED never drops an existing OPEN follow-up item. This is the
        closure guarantee: once a reviewer flags an RMU, the App keeps tracking
        it across source refreshes until that RMU is actually closed.
        """
        rmu = clean(rmu)
        status = clean(review_status).upper()
        if not rmu or status not in {"NEEDS ACTION", "CLOSED"}:
            return
        current = self.db.execute("SELECT * FROM rmu_action_tracking WHERE rmu=?", (rmu,)).fetchone()
        now = datetime.now().isoformat(timespec="seconds")
        by = modified_by or "system"
        if status == "NEEDS ACTION":
            if current is None:
                self.db.execute(
                    """INSERT INTO rmu_action_tracking(
                        rmu,tracking_status,first_need_action_at,last_need_action_at,closed_at,
                        opened_by,closed_by,open_count,last_reason,updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (rmu, "OPEN", now, now, "", by, "", 1, reason or "RMU Needs Action", now),
                )
                old_tracking = ""
                new_tracking = "OPEN"
            elif clean(current["tracking_status"]).upper() == "CLOSED":
                self.db.execute(
                    """UPDATE rmu_action_tracking SET tracking_status='OPEN',last_need_action_at=?,closed_at='',
                    opened_by=?,closed_by='',open_count=?,last_reason=?,updated_at=? WHERE rmu=?""",
                    (now, by, int(current["open_count"] or 0) + 1, reason or "RMU Needs Action", now, rmu),
                )
                old_tracking = "CLOSED"
                new_tracking = "OPEN"
            else:
                self.db.execute(
                    "UPDATE rmu_action_tracking SET last_need_action_at=?,last_reason=?,updated_at=? WHERE rmu=?",
                    (now, reason or "RMU Needs Action", now, rmu),
                )
                return
        else:  # CLOSED
            if current is None or clean(current["tracking_status"]).upper() != "OPEN":
                return
            self.db.execute(
                """UPDATE rmu_action_tracking SET tracking_status='CLOSED',closed_at=?,closed_by=?,
                last_reason=?,updated_at=? WHERE rmu=?""",
                (now, by, reason or "RMU closed", now, rmu),
            )
            old_tracking = "OPEN"
            new_tracking = "CLOSED"
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (rmu, "rmu_action_tracking", old_tracking, new_tracking,
             reason or "RMU Needs Action closure tracking", by, now),
        )


    def _rekey_signal_issue_cases(self, legacy_key: str, target_key: str) -> None:
        """Carry Signal lifecycle history across a canonical row-key migration."""
        legacy_key = clean(legacy_key); target_key = clean(target_key)
        if not legacy_key or not target_key or legacy_key == target_key:
            return
        legacy_cases = list(self.db.execute(
            "SELECT id,case_no FROM issue_cases WHERE entity_type='SIGNAL' AND entity_key=? ORDER BY case_no,id",
            (legacy_key,),
        ))
        if not legacy_cases:
            return
        max_target = int(self.db.execute(
            "SELECT COALESCE(MAX(case_no),0) FROM issue_cases WHERE entity_type='SIGNAL' AND entity_key=?",
            (target_key,),
        ).fetchone()[0] or 0)
        # Renumber first to avoid UNIQUE(entity_type,entity_key,case_no) collisions.
        for offset, case in enumerate(legacy_cases, start=1):
            self.db.execute(
                "UPDATE issue_cases SET case_no=?,entity_key=?,updated_at=? WHERE id=?",
                (max_target + offset, target_key, datetime.now().isoformat(timespec="seconds"), int(case["id"])),
            )


    def db_smart_review_map(self) -> dict[str, dict]:
        return {
            row["row_key"]: dict(row)
            for row in self.db.execute("SELECT * FROM db_smart_reviews")
        }

    def _apply_db_smart_metadata(self, row_key: str, metadata: dict | None) -> None:
        metadata = dict(metadata or {})
        if not metadata:
            return
        self.db.execute(
            """UPDATE db_smart_reviews SET
               signal_category=?,point_no=?,signal_name=?,signal_snapshot_json=?
               WHERE row_key=?""",
            (
                clean(metadata.get("signal_category")),
                clean(metadata.get("point_no")),
                clean(metadata.get("signal_name")),
                str(metadata.get("signal_snapshot_json") or "{}"),
                clean(row_key),
            ),
        )

    def sync_db_smart_review_fingerprints(
        self, fingerprints: dict[str, dict[str, str]], modified_by: str = "SYSTEM",
        *, aliases: dict[str, str] | None = None, metadata: dict[str, dict] | None = None,
    ) -> int:
        """Synchronize current Signal rows without losing unresolved Needs Action.

        ``aliases`` migrates pre-STANDARD-driven source-row keys onto the new
        canonical STANDARD row identity. ``metadata`` freezes point/category
        details so every site NEEDS ACTION remains reportable even if a later
        source refresh changes or removes the calculated row.

        CLOSED/manual-check decisions are invalidated when the validation row
        itself changes. NEEDS ACTION is deliberately preserved until a reviewer
        explicitly changes it, because it represents an unresolved site action.
        """
        reset_count = 0
        now = datetime.now().isoformat(timespec="seconds")
        aliases = {clean(k): clean(v) for k, v in (aliases or {}).items() if clean(k) and clean(v) and clean(k) != clean(v)}
        metadata = {clean(k): dict(v or {}) for k, v in (metadata or {}).items() if clean(k)}

        def explicit(record) -> bool:
            if record is None:
                return False
            status = clean(record["review_status"]).upper()
            return status in {"CLOSED", "NEEDS ACTION", "REVIEWED"} or bool(clean(record["reviewed_by"]) or clean(record["reviewed_at"]))

        with self.db:
            existing = {clean(row["row_key"]): row for row in self.db.execute("SELECT * FROM db_smart_reviews")}

            # One-time/ongoing semantic re-key: carry old review decisions to the
            # STANDARD-driven canonical row instead of leaving false historical
            # orphans after v0.8.99.
            for legacy_key, target_key in aliases.items():
                legacy = existing.get(legacy_key)
                if legacy is None:
                    continue
                target = existing.get(target_key)
                self._rekey_signal_issue_cases(legacy_key, target_key)
                if target is None:
                    self.db.execute("UPDATE db_smart_reviews SET row_key=?,updated_at=? WHERE row_key=?", (target_key, now, legacy_key))
                    self.db.execute(
                        "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                        (f"DBSMART:{clean(legacy['rmu']) or legacy_key[:12]}", "db_smart_row_key", legacy_key, target_key,
                         "Signal Mapping row identity migrated to STANDARD-driven key", modified_by or "SYSTEM", now),
                    )
                else:
                    # Prefer the newest explicit human decision.  A purely
                    # automatic/unreviewed target must never overwrite an older
                    # unresolved NEEDS ACTION.
                    legacy_stamp = clean(legacy["updated_at"])
                    target_stamp = clean(target["updated_at"])
                    use_legacy = explicit(legacy) and (not explicit(target) or legacy_stamp >= target_stamp)
                    chosen = legacy if use_legacy else target
                    comments = clean(chosen["comments"]) or clean(legacy["comments"]) or clean(target["comments"])
                    self.db.execute(
                        """UPDATE db_smart_reviews SET
                           site_name=?,rmu=?,review_status=?,comments=?,check_passed=?,check_passed_by=?,check_passed_at=?,
                           reviewed_by=?,reviewed_at=?,updated_at=? WHERE row_key=?""",
                        (
                            clean(chosen["site_name"]) or clean(target["site_name"]) or clean(legacy["site_name"]),
                            clean(chosen["rmu"]) or clean(target["rmu"]) or clean(legacy["rmu"]),
                            clean(chosen["review_status"]) or "UNREVIEWED", comments,
                            int(chosen["check_passed"] or 0) if "check_passed" in chosen.keys() else 0,
                            clean(chosen["check_passed_by"]) if "check_passed_by" in chosen.keys() else "",
                            clean(chosen["check_passed_at"]) if "check_passed_at" in chosen.keys() else "",
                            clean(chosen["reviewed_by"]), clean(chosen["reviewed_at"]), now, target_key,
                        ),
                    )
                    self.db.execute("DELETE FROM db_smart_reviews WHERE row_key=?", (legacy_key,))
                existing = {clean(row["row_key"]): row for row in self.db.execute("SELECT * FROM db_smart_reviews")}

            for row_key, info in (fingerprints or {}).items():
                row_key = clean(row_key)
                current = existing.get(row_key)
                if current is None:
                    continue
                new_row_hash = clean(info.get("row_hash"))
                new_source_hash = clean(info.get("source_hash"))
                old_row_hash = clean(current["row_hash"])
                old_source_hash = clean(current["source_hash"])
                status = clean(current["review_status"]).upper() or "UNREVIEWED"
                check_passed = bool(int(current["check_passed"] or 0)) if "check_passed" in current.keys() else False
                changed = bool(old_row_hash and new_row_hash and old_row_hash != new_row_hash)
                if not old_row_hash and old_source_hash and new_source_hash and old_source_hash != new_source_hash:
                    changed = True
                explicit_unreviewed = status == "UNREVIEWED" and bool(clean(current["reviewed_by"]) or clean(current["reviewed_at"]))

                if changed:
                    meta = dict(metadata.get(row_key) or {})
                    if not meta:
                        meta = {
                            "signal_category": clean(current["signal_category"]) if "signal_category" in current.keys() else "",
                            "point_no": clean(current["point_no"]) if "point_no" in current.keys() else "",
                            "signal_name": clean(current["signal_name"]) if "signal_name" in current.keys() else "",
                            "signal_snapshot_json": clean(current["signal_snapshot_json"]) if "signal_snapshot_json" in current.keys() else "{}",
                        }
                    snap = self._signal_issue_snapshot(
                        row_key=row_key, rmu=clean(current["rmu"]), review_status=status,
                        comments=clean(current["comments"]), source_hash=new_source_hash, row_hash=new_row_hash, metadata=meta,
                    )
                    self._record_issue_field_change(
                        "SIGNAL", row_key, field_name="validation_fingerprint",
                        old_value=f"{old_source_hash}:{old_row_hash}", new_value=f"{new_source_hash}:{new_row_hash}",
                        modified_by=modified_by or "SYSTEM", reason="Signal Mapping validation result changed after source refresh",
                        snapshot=snap, event_type="VALIDATION_CHANGED", rmu=clean(current["rmu"]),
                        point_no=clean(meta.get("point_no")), signal_name=clean(meta.get("signal_name")),
                        site_name=clean(current["site_name"]),
                    )

                if changed and status == "NEEDS ACTION":
                    # An unresolved action belongs to the site until a human
                    # closes/reclassifies it. Refreshing source data must not
                    # silently erase it; only a manual Checked flag is stale.
                    self.db.execute(
                        """UPDATE db_smart_reviews SET
                           check_passed=0,check_passed_by='',check_passed_at='',
                           source_hash=?,row_hash=?,updated_at=? WHERE row_key=?""",
                        (new_source_hash, new_row_hash, now, row_key),
                    )
                    if check_passed:
                        self.db.execute(
                            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                            (f"DBSMART:{clean(current['rmu']) or row_key[:12]}", "db_smart_check_passed", "PASS", "",
                             "Automatic reset: Signal Mapping source changed while Needs Action remains open", modified_by or "SYSTEM", now),
                        )
                elif changed and (status != "UNREVIEWED" or explicit_unreviewed):
                    self.db.execute(
                        """UPDATE db_smart_reviews
                        SET review_status='UNREVIEWED',reviewed_by='',reviewed_at='',
                            check_passed=0,check_passed_by='',check_passed_at='',
                            source_hash=?,row_hash=?,updated_at=? WHERE row_key=?""",
                        (new_source_hash, new_row_hash, now, row_key),
                    )
                    self.db.execute(
                        "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                        (f"DBSMART:{clean(current['rmu']) or row_key[:12]}", "db_smart_review_status", status, "UNREVIEWED",
                         "Automatic reset: Signal Mapping validation result changed after source refresh", modified_by or "SYSTEM", now),
                    )
                    if check_passed:
                        self.db.execute(
                            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                            (f"DBSMART:{clean(current['rmu']) or row_key[:12]}", "db_smart_check_passed", "PASS", "",
                             "Automatic reset: Signal Mapping validation result changed after source refresh", modified_by or "SYSTEM", now),
                        )
                    reset_count += 1
                elif changed and check_passed:
                    self.db.execute(
                        """UPDATE db_smart_reviews
                        SET check_passed=0,check_passed_by='',check_passed_at='',
                            source_hash=?,row_hash=?,updated_at=? WHERE row_key=?""",
                        (new_source_hash, new_row_hash, now, row_key),
                    )
                    self.db.execute(
                        "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                        (f"DBSMART:{clean(current['rmu']) or row_key[:12]}", "db_smart_check_passed", "PASS", "",
                         "Automatic reset: Signal Mapping validation result changed after source refresh", modified_by or "SYSTEM", now),
                    )
                elif old_source_hash != new_source_hash or old_row_hash != new_row_hash:
                    self.db.execute(
                        "UPDATE db_smart_reviews SET source_hash=?,row_hash=?,updated_at=? WHERE row_key=?",
                        (new_source_hash, new_row_hash, now, row_key),
                    )

                self._apply_db_smart_metadata(row_key, metadata.get(row_key))
        return reset_count

    def update_db_smart_check_passed(
        self, row_key: str, rmu: str, passed: bool, modified_by: str,
        source_hash: str = "", row_hash: str = "", site_name: str = "",
        reason: str = "Signal manually checked / passed in Row Locator", metadata: dict | None = None,
    ) -> None:
        """Persist a Signal Mapping manual verification check independently of Review."""
        row_key = clean(row_key)
        if not row_key:
            raise ValueError("Signal row key is required for manual verification")
        current = self.db.execute(
            "SELECT * FROM db_smart_reviews WHERE row_key=?", (row_key,)
        ).fetchone()
        old_value = bool(int(current["check_passed"] or 0)) if current and "check_passed" in current.keys() else False
        new_value = bool(passed)
        if old_value == new_value:
            return
        now = datetime.now().isoformat(timespec="seconds")
        by = modified_by or "system"
        payload = {
            "row_key": row_key,
            "site_name": site_name or (clean(current["site_name"]) if current else ""),
            "rmu": clean(rmu) or (clean(current["rmu"]) if current else ""),
            "source_hash": source_hash or (clean(current["source_hash"]) if current else ""),
            "row_hash": row_hash or (clean(current["row_hash"]) if current else ""),
            "review_status": clean(current["review_status"]) if current else "UNREVIEWED",
            "comments": clean(current["comments"]) if current else "",
            "check_passed": int(new_value),
            "check_passed_by": by if new_value else "",
            "check_passed_at": now if new_value else "",
            "reviewed_by": clean(current["reviewed_by"]) if current else "",
            "reviewed_at": clean(current["reviewed_at"]) if current else "",
            "updated_at": now,
        }
        self.db.execute(
            """INSERT INTO db_smart_reviews
            (row_key,site_name,rmu,source_hash,row_hash,review_status,comments,
             check_passed,check_passed_by,check_passed_at,reviewed_by,reviewed_at,updated_at)
            VALUES(:row_key,:site_name,:rmu,:source_hash,:row_hash,:review_status,:comments,
                   :check_passed,:check_passed_by,:check_passed_at,:reviewed_by,:reviewed_at,:updated_at)
            ON CONFLICT(row_key) DO UPDATE SET
              site_name=excluded.site_name,rmu=excluded.rmu,source_hash=excluded.source_hash,row_hash=excluded.row_hash,
              check_passed=excluded.check_passed,check_passed_by=excluded.check_passed_by,
              check_passed_at=excluded.check_passed_at,updated_at=excluded.updated_at
            """,
            payload,
        )
        self._apply_db_smart_metadata(row_key, metadata)
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (f"DBSMART:{payload['rmu'] or row_key[:12]}", "db_smart_check_passed",
             "PASS" if old_value else "", "PASS" if new_value else "", reason, by, now),
        )
        meta = dict(metadata or {})
        snap = self._signal_issue_snapshot(
            row_key=row_key, rmu=payload["rmu"], review_status=payload["review_status"], comments=payload["comments"],
            source_hash=payload["source_hash"], row_hash=payload["row_hash"], metadata=meta,
        )
        self._record_issue_field_change(
            "SIGNAL", row_key, field_name="check_passed", old_value="PASS" if old_value else "",
            new_value="PASS" if new_value else "", modified_by=by, reason=reason, snapshot=snap,
            event_type="CHECK_CHANGED", site_name=payload["site_name"], rmu=payload["rmu"],
            point_no=clean(meta.get("point_no")), signal_name=clean(meta.get("signal_name")),
        )
        self.db.commit()


    def update_db_smart_review(
        self, row_key: str, rmu: str, field: str, value: str, modified_by: str,
        source_hash: str = "", row_hash: str = "", site_name: str = "", reason: str = "Signal Mapping Review",
        metadata: dict | None = None,
    ) -> None:
        if field not in {"review_status", "comments"}:
            raise ValueError(f"Unsupported DB Smart review field: {field}")
        current = self.db.execute(
            "SELECT * FROM db_smart_reviews WHERE row_key=?", (row_key,)
        ).fetchone()
        old_value = clean(current[field]) if current else ("UNREVIEWED" if field == "review_status" else "")
        value = clean(value)
        if field == "review_status":
            value = value.upper() or "UNREVIEWED"
            if value not in {"UNREVIEWED", "CLOSED", "NEEDS ACTION"}:
                raise ValueError(f"Invalid DB Smart review status: {value}")
        if old_value == value and current is not None:
            if field != "review_status" or clean(current["reviewed_by"]) or clean(current["reviewed_at"]):
                return
        now = datetime.now().isoformat(timespec="seconds")
        payload = {
            "row_key": row_key,
            "site_name": site_name,
            "rmu": rmu,
            "source_hash": source_hash,
            "row_hash": row_hash or (clean(current["row_hash"]) if current else ""),
            "review_status": clean(current["review_status"]) if current else "UNREVIEWED",
            "comments": clean(current["comments"]) if current else "",
            "reviewed_by": clean(current["reviewed_by"]) if current else "",
            "reviewed_at": clean(current["reviewed_at"]) if current else "",
            "updated_at": now,
            "ever_needs_action": int(current["ever_needs_action"] or 0) if current and "ever_needs_action" in current.keys() else 0,
        }
        payload[field] = value
        if field == "review_status" and value == "NEEDS ACTION":
            payload["ever_needs_action"] = 1
        if field == "review_status":
            # Selecting any of the three states is an explicit review decision,
            # including UNREVIEWED (used to reopen an automatically closed row).
            payload["reviewed_by"] = modified_by or "system"
            payload["reviewed_at"] = now
        self.db.execute(
            """INSERT INTO db_smart_reviews
            (row_key,site_name,rmu,source_hash,row_hash,review_status,comments,reviewed_by,reviewed_at,updated_at,ever_needs_action)
            VALUES(:row_key,:site_name,:rmu,:source_hash,:row_hash,:review_status,:comments,:reviewed_by,:reviewed_at,:updated_at,:ever_needs_action)
            ON CONFLICT(row_key) DO UPDATE SET
              site_name=excluded.site_name,rmu=excluded.rmu,source_hash=excluded.source_hash,row_hash=excluded.row_hash,
              review_status=excluded.review_status,comments=excluded.comments,
              reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at,updated_at=excluded.updated_at,
              ever_needs_action=CASE WHEN db_smart_reviews.ever_needs_action=1 OR excluded.ever_needs_action=1 THEN 1 ELSE 0 END
            """,
            payload,
        )
        self._apply_db_smart_metadata(row_key, metadata)
        audit_record = f"DBSMART:{rmu or row_key[:12]}"
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (audit_record, f"db_smart_{field}", old_value, value, reason, modified_by, now),
        )
        meta = dict(metadata or {})
        current_status = payload["review_status"]
        snap = self._signal_issue_snapshot(
            row_key=row_key, rmu=payload["rmu"], review_status=current_status, comments=payload["comments"],
            source_hash=payload["source_hash"], row_hash=payload["row_hash"], metadata=meta,
        )
        if field == "review_status":
            self._sync_issue_case_status(
                "SIGNAL", row_key, old_status=old_value, new_status=value, modified_by=modified_by or "system",
                reason=reason, site_name=payload["site_name"], rmu=payload["rmu"],
                point_no=clean(meta.get("point_no")), signal_name=clean(meta.get("signal_name")), snapshot=snap,
            )
        else:
            self._record_issue_field_change(
                "SIGNAL", row_key, field_name="action_remark", old_value=old_value, new_value=value,
                modified_by=modified_by or "system", reason=reason, snapshot=snap, event_type="ACTION_REMARK_CHANGED",
                open_if_needed=bool(clean(value)), site_name=payload["site_name"], rmu=payload["rmu"],
                point_no=clean(meta.get("point_no")), signal_name=clean(meta.get("signal_name")),
                old_status=clean(current["review_status"]).upper() if current else "UNREVIEWED",
            )
        self.db.commit()


