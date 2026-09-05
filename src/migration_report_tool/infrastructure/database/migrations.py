"""Forward-only SQLite schema migrations for persistent site project databases."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sqlite3
import json

TARGET_SCHEMA_VERSION = 12


def _table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def database_schema_version(db_path: Path) -> int:
    path = Path(db_path)
    if not path.exists() or path.stat().st_size == 0:
        return 0
    db = sqlite3.connect(path)
    try:
        if not _table_exists(db, "app_meta"):
            return 0
        row = db.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()
        try:
            return int(row[0]) if row else 0
        except (TypeError, ValueError):
            return 0
    finally:
        db.close()


def _quick_check(db_path: Path) -> None:
    """Raise if SQLite cannot verify the database as internally consistent."""
    db = sqlite3.connect(Path(db_path))
    try:
        row = db.execute("PRAGMA quick_check").fetchone()
        result = str(row[0] if row else "").strip().lower()
        if result != "ok":
            raise RuntimeError(f"SQLite quick_check failed for {db_path}: {result or 'unknown error'}")
    finally:
        db.close()


def _snapshot_table_row_counts(db_path: Path) -> dict[str, int]:
    """Capture row counts for every existing user table before an upgrade.

    Schema migrations in this application are additive/normalizing. Existing
    persistent rows must therefore never disappear during an upgrade.
    """
    path = Path(db_path)
    if not path.exists() or path.stat().st_size == 0:
        return {}
    db = sqlite3.connect(path)
    try:
        tables = [
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts: dict[str, int] = {}
        for table in tables:
            escaped = table.replace('"', '""')
            counts[table] = int(db.execute(f'SELECT COUNT(*) FROM "{escaped}"').fetchone()[0])
        return counts
    finally:
        db.close()


def _assert_rows_preserved(db_path: Path, before: dict[str, int]) -> None:
    """Fail an upgrade if an existing table/row disappears unexpectedly."""
    if not before:
        return
    db = sqlite3.connect(Path(db_path))
    try:
        existing = {
            str(row[0]) for row in db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        for table, old_count in before.items():
            if table not in existing:
                raise RuntimeError(f"Migration safety check failed: table {table!r} disappeared")
            escaped = table.replace('"', '""')
            new_count = int(db.execute(f'SELECT COUNT(*) FROM "{escaped}"').fetchone()[0])
            if new_count < int(old_count):
                raise RuntimeError(
                    f"Migration safety check failed: table {table!r} lost rows "
                    f"({old_count} -> {new_count})"
                )
    finally:
        db.close()


def _restore_database_backup(backup: Path, db_path: Path) -> None:
    """Atomically restore a verified pre-migration SQLite backup."""
    backup = Path(backup)
    path = Path(db_path)
    restore_tmp = path.with_name(path.name + ".restore.tmp")
    restore_tmp.unlink(missing_ok=True)
    shutil.copy2(backup, restore_tmp)
    _quick_check(restore_tmp)
    # A failed migration may have used WAL mode. Remove sidecars before the
    # verified rollback file replaces the live database, otherwise stale WAL
    # pages could be replayed against the restored main file.
    for suffix in ("-wal", "-shm"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)
    restore_tmp.replace(path)



def backup_database(db_path: Path, backups_dir: Path, *, target_version: int) -> Path | None:
    """Create and verify a consistent backup before a schema upgrade."""
    path = Path(db_path)
    if not path.exists() or path.stat().st_size == 0:
        return None
    backups = Path(backups_dir)
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backups / f"project_before_schema_{target_version:03d}_{stamp}.db"
    source = sqlite3.connect(path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    # Never begin modifying the live project database unless the backup itself
    # can be opened and passes SQLite's consistency check.
    _quick_check(target)
    return target


def _migration_001_persistent_baseline(db: sqlite3.Connection) -> None:
    """Adopt the v0.8.42 database contract without changing business data."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comparison (
            rmu TEXT PRIMARY KEY, no INTEGER, station TEXT, se_feeder TEXT,
            se_device TEXT, oh_ug TEXT, zenon_feeder TEXT, zenon_type TEXT,
            picture TEXT, adms_db_feeder TEXT, adms_db_type TEXT,
            adms_sld_type TEXT, smart TEXT, status TEXT, remarks TEXT, comments TEXT,
            auto_json TEXT, updated_at TEXT, data_json TEXT
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
            reviewed_by TEXT, reviewed_at TEXT, updated_at TEXT,
            analysis_hash TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS rmu_resolutions (
            rmu TEXT NOT NULL, analysis_field TEXT NOT NULL, decision_type TEXT NOT NULL,
            selected_source TEXT NOT NULL DEFAULT '', selected_value TEXT NOT NULL DEFAULT '',
            normalized_value TEXT NOT NULL DEFAULT '', analysis_fingerprint TEXT NOT NULL DEFAULT '',
            modified_by TEXT, modified_at TEXT,
            PRIMARY KEY(rmu, analysis_field)
        );
        CREATE TABLE IF NOT EXISTS db_smart_reviews (
            row_key TEXT PRIMARY KEY, site_name TEXT, rmu TEXT, source_hash TEXT,
            row_hash TEXT NOT NULL DEFAULT '', review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
            comments TEXT NOT NULL DEFAULT '', reviewed_by TEXT, reviewed_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS source_display_names (
            source_type TEXT NOT NULL, field_key TEXT NOT NULL, display_name TEXT NOT NULL,
            modified_by TEXT, modified_at TEXT,
            PRIMARY KEY(source_type, field_key)
        );
        """
    )

    # Safely adopt any unversioned v0.8.42 project.db placed in Project Data.
    if _table_exists(db, "comparison"):
        columns = {row[1] for row in db.execute("PRAGMA table_info(comparison)")}
        if "data_json" not in columns:
            db.execute("ALTER TABLE comparison ADD COLUMN data_json TEXT")
        if "comments" not in columns:
            db.execute("ALTER TABLE comparison ADD COLUMN comments TEXT")
    if _table_exists(db, "rmu_reviews"):
        columns = {row[1] for row in db.execute("PRAGMA table_info(rmu_reviews)")}
        if "analysis_hash" not in columns:
            db.execute("ALTER TABLE rmu_reviews ADD COLUMN analysis_hash TEXT NOT NULL DEFAULT ''")
        if "manual_comment" not in columns:
            db.execute("ALTER TABLE rmu_reviews ADD COLUMN manual_comment TEXT NOT NULL DEFAULT ''")
    if _table_exists(db, "db_smart_reviews"):
        columns = {row[1] for row in db.execute("PRAGMA table_info(db_smart_reviews)")}
        if "row_hash" not in columns:
            db.execute("ALTER TABLE db_smart_reviews ADD COLUMN row_hash TEXT NOT NULL DEFAULT ''")


def _migration_002_site_history_and_signoff(db: sqlite3.Connection) -> None:
    """Add durable site revision / issue-action / signed report history."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS site_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            version_id INTEGER,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS issue_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER,
            category TEXT NOT NULL DEFAULT 'Other',
            equipment TEXT NOT NULL DEFAULT '',
            issue TEXT NOT NULL,
            action_taken TEXT NOT NULL DEFAULT '',
            result TEXT NOT NULL DEFAULT 'OPEN',
            comments TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS signoff_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id INTEGER,
            report_type TEXT NOT NULL DEFAULT 'SITE_SIGNOFF',
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            report_status TEXT NOT NULL DEFAULT 'GENERATED',
            snapshot_json TEXT NOT NULL DEFAULT '{}',
            sha256 TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            signed_file_name TEXT NOT NULL DEFAULT '',
            signed_file_path TEXT NOT NULL DEFAULT '',
            signed_sha256 TEXT NOT NULL DEFAULT '',
            signed_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_issue_actions_revision ON issue_actions(revision_id, id);
        CREATE INDEX IF NOT EXISTS idx_signoff_reports_revision ON signoff_reports(revision_id, id);
        """
    )
    # Existing named Review Versions are already durable station snapshots.
    # Backfill them once so an upgrade immediately shows prior history instead
    # of presenting an empty Site History page.
    if _table_exists(db, "versions"):
        count = db.execute("SELECT COUNT(*) FROM site_revisions").fetchone()[0]
        if not count:
            db.execute(
                """INSERT INTO site_revisions(revision_name,description,version_id,created_by,created_at)
                SELECT version_name,description,id,created_by,created_at FROM versions ORDER BY id"""
            )


def _migration_003_three_state_review_workflow(db: sqlite3.Connection) -> None:
    """Normalize legacy Review values to UNREVIEWED / CLOSED / NEEDS ACTION.

    Historical REVIEWED means the reviewer completed the item, so it migrates
    to CLOSED.  Audit/history rows are intentionally left untouched.
    """
    for table in ("rmu_reviews", "db_smart_reviews"):
        if not _table_exists(db, table):
            continue
        db.execute(
            f"UPDATE {table} SET review_status='CLOSED' WHERE UPPER(TRIM(COALESCE(review_status,'')))='REVIEWED'"
        )
        db.execute(
            f"UPDATE {table} SET review_status='UNREVIEWED' "
            "WHERE UPPER(TRIM(COALESCE(review_status,''))) NOT IN ('UNREVIEWED','CLOSED','NEEDS ACTION')"
        )


def _migration_004_resolution_signoff_text(db: sqlite3.Connection) -> None:
    """Persist complete customer-facing RMU resolution text for sign-off.

    Existing resolution rows are preserved.  The new columns are optional for
    legacy rows and are filled automatically the next time a decision is saved.
    """
    if not _table_exists(db, "rmu_resolutions"):
        return
    columns = {row[1] for row in db.execute("PRAGMA table_info(rmu_resolutions)")}
    if "decision_description" not in columns:
        db.execute("ALTER TABLE rmu_resolutions ADD COLUMN decision_description TEXT NOT NULL DEFAULT ''")
    if "issue_snapshot_json" not in columns:
        db.execute("ALTER TABLE rmu_resolutions ADD COLUMN issue_snapshot_json TEXT NOT NULL DEFAULT '{}'")


def _migration_005_custom_fields_and_derived_tables(db: sqlite3.Connection) -> None:
    """Add persistent custom source fields and derived-table configurations."""
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS custom_source_fields (
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            actual_column TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS derived_table_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            base_source_type TEXT NOT NULL DEFAULT '',
            config_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_custom_source_fields_source
            ON custom_source_fields(source_type, field_key);
        """
    )


def _migration_006_manual_rmu_checks_and_source_versions(db: sqlite3.Connection) -> None:
    """Persist manual RMU verification and active source-file version choices."""
    if _table_exists(db, "rmu_reviews"):
        columns = {row[1] for row in db.execute("PRAGMA table_info(rmu_reviews)")}
        if "check_passed" not in columns:
            db.execute("ALTER TABLE rmu_reviews ADD COLUMN check_passed INTEGER NOT NULL DEFAULT 0")
        if "check_passed_by" not in columns:
            db.execute("ALTER TABLE rmu_reviews ADD COLUMN check_passed_by TEXT NOT NULL DEFAULT ''")
        if "check_passed_at" not in columns:
            db.execute("ALTER TABLE rmu_reviews ADD COLUMN check_passed_at TEXT NOT NULL DEFAULT ''")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_file_selections (
            source_type TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            selected_by TEXT NOT NULL DEFAULT '',
            selected_at TEXT NOT NULL
        );
        """
    )



def _migration_007_rmu_need_action_tracking(db: sqlite3.Connection) -> None:
    """Persist RMUs that enter NEEDS ACTION until they are explicitly closed.

    The tracker is deliberately independent from the current validation row.
    Once an RMU enters NEEDS ACTION it remains an OPEN follow-up item through
    refreshes/UNREVIEWED resets until Review is set to CLOSED. Reopening the
    same RMU increments ``open_count`` while preserving the first occurrence.
    """
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS rmu_action_tracking (
            rmu TEXT PRIMARY KEY,
            tracking_status TEXT NOT NULL DEFAULT 'OPEN',
            first_need_action_at TEXT NOT NULL DEFAULT '',
            last_need_action_at TEXT NOT NULL DEFAULT '',
            closed_at TEXT NOT NULL DEFAULT '',
            opened_by TEXT NOT NULL DEFAULT '',
            closed_by TEXT NOT NULL DEFAULT '',
            open_count INTEGER NOT NULL DEFAULT 1,
            last_reason TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_rmu_action_tracking_status
            ON rmu_action_tracking(tracking_status, rmu);
        """
    )
    if _table_exists(db, "rmu_reviews"):
        now = datetime.now().isoformat(timespec="seconds")
        rows = db.execute(
            "SELECT rmu,reviewed_by,reviewed_at,updated_at FROM rmu_reviews "
            "WHERE UPPER(TRIM(COALESCE(review_status,'')))='NEEDS ACTION'"
        ).fetchall()
        for rmu, reviewed_by, reviewed_at, updated_at in rows:
            stamp = str(reviewed_at or updated_at or now)
            db.execute(
                """INSERT OR IGNORE INTO rmu_action_tracking(
                    rmu,tracking_status,first_need_action_at,last_need_action_at,closed_at,
                    opened_by,closed_by,open_count,last_reason,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (str(rmu or ''), 'OPEN', stamp, stamp, '', str(reviewed_by or 'migration'), '', 1,
                 'Backfilled from existing RMU Needs Action review', stamp),
            )


def _migration_008_manual_signal_checks(db: sqlite3.Connection) -> None:
    """Persist manual Signal Mapping verification, matching the RMU Checked workflow."""
    if not _table_exists(db, "db_smart_reviews"):
        return
    columns = {row[1] for row in db.execute("PRAGMA table_info(db_smart_reviews)")}
    if "check_passed" not in columns:
        db.execute("ALTER TABLE db_smart_reviews ADD COLUMN check_passed INTEGER NOT NULL DEFAULT 0")
    if "check_passed_by" not in columns:
        db.execute("ALTER TABLE db_smart_reviews ADD COLUMN check_passed_by TEXT NOT NULL DEFAULT ''")
    if "check_passed_at" not in columns:
        db.execute("ALTER TABLE db_smart_reviews ADD COLUMN check_passed_at TEXT NOT NULL DEFAULT ''")



def _migration_009_signal_review_snapshot_metadata(db: sqlite3.Connection) -> None:
    """Keep unresolved Signal Needs Action records classifiable across mapping refreshes.

    v0.8.99 changed Signal Mapping from source-row-driven to STANDARD-driven
    identities.  Store the point/category/source snapshot alongside the human
    review so a site report can include every currently-open NEEDS ACTION even
    when the calculated row identity changes later.
    """
    if not _table_exists(db, "db_smart_reviews"):
        return
    columns = {row[1] for row in db.execute("PRAGMA table_info(db_smart_reviews)")}
    additions = (
        ("signal_category", "TEXT NOT NULL DEFAULT ''"),
        ("point_no", "TEXT NOT NULL DEFAULT ''"),
        ("signal_name", "TEXT NOT NULL DEFAULT ''"),
        ("signal_snapshot_json", "TEXT NOT NULL DEFAULT '{}'"),
    )
    for name, ddl in additions:
        if name not in columns:
            db.execute(f"ALTER TABLE db_smart_reviews ADD COLUMN {name} {ddl}")


def _migration_010_signal_need_action_lifecycle(db: sqlite3.Connection) -> None:
    """Persist whether a Signal row has ever entered the formal Needs Action scope.

    The PDF lifecycle summary must satisfy: Need Action Total = Closed + Pending/Open.
    Current review_status alone cannot preserve that relationship after an item is
    closed, so retain a one-way history flag on the review record.
    """
    if not _table_exists(db, "db_smart_reviews"):
        return
    columns = {row[1] for row in db.execute("PRAGMA table_info(db_smart_reviews)")}
    if "ever_needs_action" not in columns:
        db.execute("ALTER TABLE db_smart_reviews ADD COLUMN ever_needs_action INTEGER NOT NULL DEFAULT 0")

    # Current open actions are unambiguous.
    db.execute(
        "UPDATE db_smart_reviews SET ever_needs_action=1 "
        "WHERE UPPER(TRIM(COALESCE(review_status,'')))='NEEDS ACTION'"
    )

    # v0.8.116 introduced structured Action | Remark comments.  A closed row that
    # still carries one of these comments was previously an explicit action item.
    db.execute(
        """UPDATE db_smart_reviews SET ever_needs_action=1
           WHERE UPPER(TRIM(COALESCE(comments,''))) LIKE 'ADD |%'
              OR UPPER(TRIM(COALESCE(comments,''))) LIKE 'MODIFY |%'
              OR UPPER(TRIM(COALESCE(comments,''))) LIKE 'DELETE |%'"""
    )

    # Recover older closed action rows from frozen sign-off snapshots whenever
    # their row_key is available.  Ignore malformed legacy snapshots safely.
    if _table_exists(db, "signoff_reports"):
        keys: set[str] = set()
        for row in db.execute("SELECT snapshot_json FROM signoff_reports WHERE COALESCE(snapshot_json,'')<>''"):
            try:
                snapshot = json.loads(row[0] or "{}")
            except Exception:
                continue
            for item in snapshot.get("signal_need_action_items", []) or []:
                key = str((item or {}).get("row_key") or "").strip()
                if key:
                    keys.add(key)
        if keys:
            db.executemany(
                "UPDATE db_smart_reviews SET ever_needs_action=1 WHERE row_key=?",
                [(key,) for key in keys],
            )


def _migration_011_issue_lifecycle(db: sqlite3.Connection) -> None:
    """Add append-only Need Action lifecycle cases/events for RMUs and Signals.

    Existing review/audit rows are never rewritten.  A conservative legacy
    baseline is created only for records that can be proven to have entered
    Needs Action.  Earlier per-edit history remains available in ``changes``;
    v11 records every subsequent lifecycle event without overwriting history.
    """
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS issue_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_key TEXT NOT NULL,
            case_no INTEGER NOT NULL DEFAULT 1,
            site_name TEXT NOT NULL DEFAULT '',
            rmu TEXT NOT NULL DEFAULT '',
            point_no TEXT NOT NULL DEFAULT '',
            signal_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'OPEN',
            opened_at TEXT NOT NULL DEFAULT '',
            opened_by TEXT NOT NULL DEFAULT '',
            closed_at TEXT NOT NULL DEFAULT '',
            closed_by TEXT NOT NULL DEFAULT '',
            open_reason TEXT NOT NULL DEFAULT '',
            close_reason TEXT NOT NULL DEFAULT '',
            open_snapshot_json TEXT NOT NULL DEFAULT '{}',
            close_snapshot_json TEXT NOT NULL DEFAULT '{}',
            app_version TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            UNIQUE(entity_type, entity_key, case_no)
        );
        CREATE TABLE IF NOT EXISTS issue_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            field_name TEXT NOT NULL DEFAULT '',
            old_value TEXT NOT NULL DEFAULT '',
            new_value TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL,
            snapshot_json TEXT NOT NULL DEFAULT '{}',
            app_version TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(case_id) REFERENCES issue_cases(id)
        );
        CREATE INDEX IF NOT EXISTS idx_issue_cases_entity
            ON issue_cases(entity_type, entity_key, case_no DESC);
        CREATE INDEX IF NOT EXISTS idx_issue_cases_status
            ON issue_cases(status, entity_type, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_issue_events_case
            ON issue_events(case_id, id);
        CREATE INDEX IF NOT EXISTS idx_issue_events_time
            ON issue_events(modified_at, id);
        """
    )

    now = datetime.now().isoformat(timespec="seconds")

    # RMU baseline: migration 7 already records only RMUs that really entered
    # Needs Action.  Do not invent separate historical cases for open_count > 1
    # because old versions did not retain enough timestamps to reconstruct them.
    if _table_exists(db, "rmu_action_tracking"):
        for row in db.execute("SELECT * FROM rmu_action_tracking ORDER BY rmu"):
            rmu = str(row["rmu"] or "").strip()
            if not rmu:
                continue
            exists = db.execute(
                "SELECT 1 FROM issue_cases WHERE entity_type='RMU' AND entity_key=? LIMIT 1", (rmu,)
            ).fetchone()
            if exists:
                continue
            tracking_status = str(row["tracking_status"] or "OPEN").strip().upper()
            status = "CLOSED" if tracking_status == "CLOSED" else "OPEN"
            opened_at = str(row["first_need_action_at"] or row["last_need_action_at"] or now)
            closed_at = str(row["closed_at"] or "") if status == "CLOSED" else ""
            snapshot = json.dumps({
                "legacy_baseline": True,
                "legacy_open_count": int(row["open_count"] or 1),
                "first_need_action_at": str(row["first_need_action_at"] or ""),
                "last_need_action_at": str(row["last_need_action_at"] or ""),
                "last_reason": str(row["last_reason"] or ""),
                "note": "Pre-v11 lifecycle summarized from RMU tracking; detailed earlier edits remain in Change Audit.",
            }, ensure_ascii=False)
            cur = db.execute(
                """INSERT INTO issue_cases(
                    entity_type,entity_key,case_no,site_name,rmu,status,opened_at,opened_by,
                    closed_at,closed_by,open_reason,close_reason,open_snapshot_json,close_snapshot_json,
                    app_version,created_at,updated_at
                ) VALUES('RMU',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    rmu, 1, "", rmu, status, opened_at, str(row["opened_by"] or "migration"),
                    closed_at, str(row["closed_by"] or "") if status == "CLOSED" else "",
                    str(row["last_reason"] or "Legacy Needs Action"),
                    str(row["last_reason"] or "") if status == "CLOSED" else "",
                    snapshot, snapshot if status == "CLOSED" else "{}", "legacy", opened_at,
                    str(row["updated_at"] or closed_at or opened_at),
                ),
            )
            case_id = int(cur.lastrowid)
            db.execute(
                """INSERT INTO issue_events(
                    case_id,event_type,field_name,old_value,new_value,reason,modified_by,modified_at,snapshot_json,app_version
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    case_id, "LEGACY_BASELINE", "review_status", "", status,
                    "Imported existing RMU Needs Action tracking without fabricating unavailable historical edits",
                    "MIGRATION", opened_at, snapshot, "legacy",
                ),
            )

    # Signal baseline: ever_needs_action is a one-way proof that this signal was
    # formally in rectification scope.  Preserve the stored business metadata.
    if _table_exists(db, "db_smart_reviews"):
        columns = {r[1] for r in db.execute("PRAGMA table_info(db_smart_reviews)")}
        if "ever_needs_action" in columns:
            for row in db.execute("SELECT * FROM db_smart_reviews WHERE ever_needs_action=1 ORDER BY row_key"):
                key = str(row["row_key"] or "").strip()
                if not key:
                    continue
                exists = db.execute(
                    "SELECT 1 FROM issue_cases WHERE entity_type='SIGNAL' AND entity_key=? LIMIT 1", (key,)
                ).fetchone()
                if exists:
                    continue
                review_status = str(row["review_status"] or "UNREVIEWED").strip().upper()
                status = "CLOSED" if review_status == "CLOSED" else "OPEN"
                opened_at = str(row["reviewed_at"] or row["updated_at"] or now)
                closed_at = str(row["reviewed_at"] or row["updated_at"] or now) if status == "CLOSED" else ""
                try:
                    signal_snapshot = json.loads(str(row["signal_snapshot_json"] or "{}"))
                except Exception:
                    signal_snapshot = {}
                snapshot = json.dumps({
                    "legacy_baseline": True,
                    "review_status": review_status,
                    "comments": str(row["comments"] or ""),
                    "source_hash": str(row["source_hash"] or ""),
                    "row_hash": str(row["row_hash"] or ""),
                    "signal": signal_snapshot,
                    "note": "Pre-v11 lifecycle summarized from Signal review; detailed earlier edits remain in Change Audit.",
                }, ensure_ascii=False)
                cur = db.execute(
                    """INSERT INTO issue_cases(
                        entity_type,entity_key,case_no,site_name,rmu,point_no,signal_name,status,
                        opened_at,opened_by,closed_at,closed_by,open_reason,close_reason,
                        open_snapshot_json,close_snapshot_json,app_version,created_at,updated_at
                    ) VALUES('SIGNAL',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        key, 1, str(row["site_name"] or ""), str(row["rmu"] or ""),
                        str(row["point_no"] or ""), str(row["signal_name"] or ""), status,
                        opened_at, str(row["reviewed_by"] or "migration"), closed_at,
                        str(row["reviewed_by"] or "") if status == "CLOSED" else "",
                        "Legacy Signal Needs Action", "Legacy Signal Closed" if status == "CLOSED" else "",
                        snapshot, snapshot if status == "CLOSED" else "{}", "legacy", opened_at,
                        str(row["updated_at"] or closed_at or opened_at),
                    ),
                )
                case_id = int(cur.lastrowid)
                db.execute(
                    """INSERT INTO issue_events(
                        case_id,event_type,field_name,old_value,new_value,reason,modified_by,modified_at,snapshot_json,app_version
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        case_id, "LEGACY_BASELINE", "review_status", "", status,
                        "Imported existing Signal Needs Action state without fabricating unavailable historical edits",
                        "MIGRATION", opened_at, snapshot, "legacy",
                    ),
                )


def _migration_012_append_only_rmu_review_history(db: sqlite3.Connection) -> None:
    """Preserve every RMU review/comment submission without overwriting history.

    ``rmu_reviews.manual_comment`` and ``rmu_resolutions.customer_comment`` remain
    the convenient latest-value projections used by the grid/dialog.  This
    append-only table is the durable reviewer timeline, including comments made
    before an RMU first enters Needs Action.  Once a Needs Action case exists the
    RMU Action Tracking view can therefore show the complete review story.
    """
    db.row_factory = sqlite3.Row
    if _table_exists(db, "rmu_resolutions"):
        columns = {row[1] for row in db.execute("PRAGMA table_info(rmu_resolutions)")}
        if "customer_comment" not in columns:
            db.execute("ALTER TABLE rmu_resolutions ADD COLUMN customer_comment TEXT NOT NULL DEFAULT ''")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS rmu_review_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rmu TEXT NOT NULL,
            case_id INTEGER,
            analysis_field TEXT NOT NULL DEFAULT '',
            event_type TEXT NOT NULL DEFAULT 'COMMENT_RECORDED',
            review_status TEXT NOT NULL DEFAULT '',
            comment TEXT NOT NULL DEFAULT '',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL,
            snapshot_json TEXT NOT NULL DEFAULT '{}',
            app_version TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(case_id) REFERENCES issue_cases(id)
        );
        CREATE INDEX IF NOT EXISTS idx_rmu_review_events_rmu_time
            ON rmu_review_events(rmu, modified_at, id);
        CREATE INDEX IF NOT EXISTS idx_rmu_review_events_case
            ON rmu_review_events(case_id, id);
        """
    )

    # Recover the historical manual-review comment edits that older versions
    # already preserved in Change Audit.  This is an exact backfill of stored
    # audit rows, not synthesized history.
    if _table_exists(db, "changes"):
        existing = db.execute("SELECT COUNT(*) FROM rmu_review_events").fetchone()[0]
        if not existing:
            for row in db.execute(
                """SELECT rmu,old_value,new_value,reason,modified_by,modified_at
                     FROM changes
                    WHERE field_name='rmu_review_comment'
                    ORDER BY modified_at,id"""
            ):
                rmu = str(row["rmu"] or "").strip()
                if not rmu:
                    continue
                new_value = str(row["new_value"] or "")
                old_value = str(row["old_value"] or "")
                event_type = "COMMENT_CLEARED" if not new_value.strip() else "COMMENT_RECORDED"
                snapshot = json.dumps({
                    "legacy_backfill": True,
                    "old_comment": old_value,
                    "new_comment": new_value,
                    "reason": str(row["reason"] or ""),
                }, ensure_ascii=False)
                db.execute(
                    """INSERT INTO rmu_review_events(
                        rmu,case_id,analysis_field,event_type,review_status,comment,
                        modified_by,modified_at,snapshot_json,app_version
                    ) VALUES(?,NULL,'',?,?,?,?,?,?,?)""",
                    (
                        rmu, event_type, "", new_value, str(row["modified_by"] or "migration"),
                        str(row["modified_at"] or datetime.now().isoformat(timespec="seconds")),
                        snapshot, "legacy",
                    ),
                )


MIGRATIONS = {
    1: _migration_001_persistent_baseline,
    2: _migration_002_site_history_and_signoff,
    3: _migration_003_three_state_review_workflow,
    4: _migration_004_resolution_signoff_text,
    5: _migration_005_custom_fields_and_derived_tables,
    6: _migration_006_manual_rmu_checks_and_source_versions,
    7: _migration_007_rmu_need_action_tracking,
    8: _migration_008_manual_signal_checks,
    9: _migration_009_signal_review_snapshot_metadata,
    10: _migration_010_signal_need_action_lifecycle,
    11: _migration_011_issue_lifecycle,
    12: _migration_012_append_only_rmu_review_history,
}


def migrate_project_database(db_path: Path, backups_dir: Path) -> tuple[int, Path | None]:
    """Upgrade a site DB in place, backing it up before the first needed migration."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = database_schema_version(path)
    if current > TARGET_SCHEMA_VERSION:
        raise RuntimeError(
            f"Project database schema {current} is newer than this application supports "
            f"({TARGET_SCHEMA_VERSION}). Install a newer application version."
        )
    if current == TARGET_SCHEMA_VERSION:
        return current, None

    existed = path.exists() and path.stat().st_size > 0
    # Capture the pre-upgrade persistent row inventory before touching the DB.
    # Together with the verified SQLite backup this makes schema upgrades
    # fail-safe: an accidental row/table loss aborts and restores the original.
    before_rows = _snapshot_table_row_counts(path) if existed else {}
    backup = backup_database(path, backups_dir, target_version=TARGET_SCHEMA_VERSION) if existed else None
    db = sqlite3.connect(path)
    try:
        for version in range(current + 1, TARGET_SCHEMA_VERSION + 1):
            migration = MIGRATIONS.get(version)
            if migration is None:
                raise RuntimeError(f"Missing project database migration {version}")
            with db:
                migration(db)
                db.execute(
                    "INSERT INTO app_meta(key,value) VALUES('schema_version',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(version),),
                )
                db.execute(
                    "INSERT INTO app_meta(key,value) VALUES('schema_updated_at',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (datetime.now().isoformat(timespec="seconds"),),
                )
        db.close()
        # Validate both SQLite integrity and preservation of every table/row
        # that existed before the migration. If either check fails, the except
        # block below restores the verified pre-upgrade backup.
        _quick_check(path)
        _assert_rows_preserved(path, before_rows)
        return TARGET_SCHEMA_VERSION, backup
    except Exception:
        db.close()
        if backup and backup.exists():
            _restore_database_backup(backup, path)
        elif not existed and path.exists():
            path.unlink(missing_ok=True)
        raise
    finally:
        try:
            db.close()
        except Exception:
            pass
