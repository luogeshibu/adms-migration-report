"""Application-wide persistent settings.

Unlike ``ProjectStore`` (one database per site), this store holds presentation
metadata that must be identical for every site, such as review-table Display
Names.  When the shared site repository is available it lives inside that
repository, so every workstation reads the same configuration.  A local
application-data fallback is retained for offline/legacy use.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
from pathlib import Path
import os
import sqlite3
import json

from ...utils.paths import user_data_root


def global_settings_db_path() -> Path:
    """Return the shared configuration database used by all workstations.

    The repository is resolved lazily to avoid importing the site repository
    during module initialization (the site repository itself imports the
    project database layer).  The first workstation that sees a shared
    repository safely copies the legacy local database into ``_shared``; later
    workstations use that shared database directly.
    """
    local_path = user_data_root() / "settings" / "global_settings.db"
    local_path.parent.mkdir(parents=True, exist_ok=True)

    # Test suites deliberately point MIGRATION_REPORT_TOOL_USER_DATA_ROOT at a
    # temporary directory.  Keep those runs isolated from the live shared
    # repository; production workstations that do not set this variable still
    # use the shared _shared/global_settings.db as intended.
    if os.environ.get("MIGRATION_REPORT_TOOL_USER_DATA_ROOT", "").strip():
        return local_path

    shared_path: Path | None = None
    try:
        from ..filesystem.site_repository import load_repository_root

        repository = load_repository_root()
        if repository and Path(repository).is_dir():
            shared_path = Path(repository) / "_shared" / "global_settings.db"
            shared_path.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, ImportError, RuntimeError):
        shared_path = None

    if shared_path is None:
        return local_path
    if shared_path.resolve() == local_path.resolve():
        return shared_path

    # Preserve existing per-workstation settings on the first migration.  A
    # SQLite backup is used instead of copying a possibly inconsistent file.
    if not shared_path.exists() and local_path.is_file():
        try:
            source = sqlite3.connect(str(local_path), timeout=15)
            target = sqlite3.connect(str(shared_path), timeout=15)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
        except (OSError, sqlite3.Error):
            # The shared repository remains usable even if a legacy local DB
            # is locked or damaged; schema creation below will initialize it.
            pass
    return shared_path


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(global_settings_db_path(), timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=15000")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS source_display_names (
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            modified_by TEXT,
            modified_at TEXT,
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS source_display_name_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            modified_by TEXT,
            modified_at TEXT
        );
        CREATE TABLE IF NOT EXISTS source_custom_columns (
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS source_custom_column_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            modified_by TEXT,
            modified_at TEXT
        );
        CREATE TABLE IF NOT EXISTS source_custom_column_tombstones (
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            deleted_by TEXT NOT NULL DEFAULT '',
            deleted_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS review_column_preferences (
            view_key TEXT PRIMARY KEY,
            hidden_keys_json TEXT NOT NULL DEFAULT '[]',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_column_order_preferences (
            source_type TEXT PRIMARY KEY,
            order_json TEXT NOT NULL DEFAULT '[]',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_visibility_preferences (
            source_type TEXT PRIMARY KEY,
            hidden_keys_json TEXT NOT NULL DEFAULT '[]',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_visibility_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            old_hidden_keys_json TEXT NOT NULL DEFAULT '[]',
            new_hidden_keys_json TEXT NOT NULL DEFAULT '[]',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_field_override_mappings (
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            actual_column TEXT NOT NULL DEFAULT '',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS source_field_override_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            old_value TEXT NOT NULL DEFAULT '',
            new_value TEXT NOT NULL DEFAULT '',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_custom_column_bindings (
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            actual_column TEXT NOT NULL DEFAULT '',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY(source_type, field_key)
        );
        CREATE TABLE IF NOT EXISTS source_custom_column_binding_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            field_key TEXT NOT NULL,
            old_value TEXT NOT NULL DEFAULT '',
            new_value TEXT NOT NULL DEFAULT '',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS equipment_comparison_profiles (
            profile_name TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL DEFAULT '{}',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS equipment_comparison_profile_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_name TEXT NOT NULL,
            old_payload_json TEXT NOT NULL DEFAULT '{}',
            new_payload_json TEXT NOT NULL DEFAULT '{}',
            modified_by TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS global_configuration_admin (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            user_name TEXT NOT NULL DEFAULT '',
            machine_name TEXT NOT NULL DEFAULT '',
            ip_address TEXT NOT NULL DEFAULT '',
            client_id TEXT NOT NULL DEFAULT '',
            claimed_at TEXT NOT NULL DEFAULT '',
            modified_at TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS workstation_presence (
            client_id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL DEFAULT '',
            machine_name TEXT NOT NULL DEFAULT '',
            ip_address TEXT NOT NULL DEFAULT '',
            app_version TEXT NOT NULL DEFAULT '',
            is_admin INTEGER NOT NULL DEFAULT 0,
            last_seen_at TEXT NOT NULL DEFAULT ''
        );
        """
    )
    # Existing shared databases were created before the workstation IP was
    # recorded.  Upgrade that one table in place without touching templates or
    # any site's project.db.
    admin_columns = {
        str(row[1]) for row in db.execute("PRAGMA table_info(global_configuration_admin)").fetchall()
    }
    if "ip_address" not in admin_columns:
        db.execute("ALTER TABLE global_configuration_admin ADD COLUMN ip_address TEXT NOT NULL DEFAULT ''")
        db.commit()
    return db


def global_configuration_admin() -> dict | None:
    """Return the single shared configuration administrator, if claimed.

    This state deliberately lives beside the global templates and mappings.  A
    workstation can therefore be copied or replaced without changing who owns
    the shared configuration.  Review records remain in each site's project.db.
    """
    with closing(_connect()) as db:
        row = db.execute(
            "SELECT user_name,machine_name,ip_address,client_id,claimed_at,modified_at "
            "FROM global_configuration_admin WHERE singleton=1"
        ).fetchone()
    if row is None:
        return None
    return {key: str(row[key] or "").strip() for key in row.keys()}


def claim_global_configuration_admin(
    user_name: str, machine_name: str = "", client_id: str = "", ip_address: str = ""
) -> dict | None:
    """Claim the shared configuration role using first-claim-wins semantics.

    Repeated claims from the same client are harmless.  A different client is
    rejected until the current administrator explicitly releases the role.
    SQLite's immediate transaction prevents two workstations claiming it at
    the same time over the Windows share.
    """
    user = str(user_name or "").strip() or "User"
    machine = str(machine_name or "").strip()
    client = str(client_id or "").strip()
    ip = str(ip_address or "").strip()
    if not client:
        return None
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT user_name,machine_name,ip_address,client_id,claimed_at,modified_at "
                "FROM global_configuration_admin WHERE singleton=1"
            ).fetchone()
            if row is not None and str(row["client_id"] or "").strip() != client:
                db.rollback()
                return None
            if row is None:
                db.execute(
                    "INSERT INTO global_configuration_admin(singleton,user_name,machine_name,ip_address,client_id,claimed_at,modified_at) "
                    "VALUES(1,?,?,?,?,?,?)",
                    (user, machine, ip, client, now, now),
                )
                claimed_at = now
            else:
                claimed_at = str(row["claimed_at"] or now)
                db.execute(
                    "UPDATE global_configuration_admin SET user_name=?,machine_name=?,ip_address=?,modified_at=? WHERE singleton=1",
                    (user, machine, ip, now),
                )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {
        "user_name": user,
        "machine_name": machine,
        "ip_address": ip,
        "client_id": client,
        "claimed_at": claimed_at,
        "modified_at": now,
    }


def force_claim_global_configuration_admin(
    user_name: str, machine_name: str = "", client_id: str = "", ip_address: str = ""
) -> dict | None:
    """Explicitly replace the current shared Admin after user confirmation.

    Normal claims remain first-claim-wins.  This separate operation is used only
    by the visible Force Takeover action for the recovery case where the old
    workstation is unavailable and cannot release the persistent lock.
    """
    user = str(user_name or "").strip() or "User"
    machine = str(machine_name or "").strip()
    client = str(client_id or "").strip()
    ip = str(ip_address or "").strip()
    if not client:
        return None
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT claimed_at FROM global_configuration_admin WHERE singleton=1"
            ).fetchone()
            claimed_at = str(row["claimed_at"] or now) if row is not None else now
            db.execute(
                "INSERT INTO global_configuration_admin(singleton,user_name,machine_name,ip_address,client_id,claimed_at,modified_at) "
                "VALUES(1,?,?,?,?,?,?) "
                "ON CONFLICT(singleton) DO UPDATE SET user_name=excluded.user_name, "
                "machine_name=excluded.machine_name, ip_address=excluded.ip_address, "
                "client_id=excluded.client_id, modified_at=excluded.modified_at",
                (user, machine, ip, client, claimed_at, now),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
    return {
        "user_name": user,
        "machine_name": machine,
        "ip_address": ip,
        "client_id": client,
        "claimed_at": claimed_at,
        "modified_at": now,
    }


def release_global_configuration_admin(user_name: str, client_id: str) -> bool:
    """Release the shared role only when called by its current workstation."""
    client = str(client_id or "").strip()
    if not client:
        return False
    with closing(_connect()) as db:
        with db:
            result = db.execute(
                "DELETE FROM global_configuration_admin WHERE singleton=1 AND client_id=?",
                (client,),
            )
    return result.rowcount > 0


def is_global_configuration_admin(user_name: str, client_id: str) -> bool:
    """Return whether this stable workstation identity owns the Admin role.

    Usernames are deliberately ignored here.  They are display/audit labels;
    the persistent client ID is the identity boundary that separates two
    workstations using the same Windows account.
    """
    state = global_configuration_admin()
    return bool(
        state
        and str(state.get("client_id") or "").strip() == str(client_id or "").strip()
    )


def touch_workstation_presence(
    user_name: str,
    machine_name: str,
    ip_address: str,
    client_id: str,
    app_version: str = "",
    is_admin: bool = False,
) -> bool:
    """Publish one workstation's lightweight shared-folder heartbeat.

    This is intentionally based on the shared SQLite file rather than LAN
    broadcast or IP scanning.  SMB access to the repository is already the
    application's common dependency, so this works across subnets/firewalls
    as long as the shared folder is available.  ``client_id`` is the stable
    per-workstation identity and prevents identical Windows usernames from
    overwriting one another.
    """
    client = str(client_id or "").strip()
    if not client:
        return False
    now = datetime.now().isoformat(timespec="seconds")
    values = (
        client,
        str(user_name or "").strip() or "User",
        str(machine_name or "").strip(),
        str(ip_address or "").strip(),
        str(app_version or "").strip(),
        1 if is_admin else 0,
        now,
    )
    with closing(_connect()) as db:
        with db:
            db.execute(
                """
                INSERT INTO workstation_presence(
                    client_id,user_name,machine_name,ip_address,app_version,is_admin,last_seen_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(client_id) DO UPDATE SET
                    user_name=excluded.user_name,
                    machine_name=excluded.machine_name,
                    ip_address=excluded.ip_address,
                    app_version=excluded.app_version,
                    is_admin=excluded.is_admin,
                    last_seen_at=excluded.last_seen_at
                """,
                values,
            )
    return True


def list_workstation_presence(max_age_seconds: int = 90) -> list[dict]:
    """Return known workstations, newest first, with an online flag.

    A stale row is retained as history and marked offline instead of being
    deleted, so an administrator can still identify a workstation that used
    to own the shared configuration.
    """
    now = datetime.now()
    try:
        age_limit = max(1, int(max_age_seconds))
    except (TypeError, ValueError):
        age_limit = 90
    with closing(_connect()) as db:
        rows = db.execute(
            """
            SELECT client_id,user_name,machine_name,ip_address,app_version,is_admin,last_seen_at
            FROM workstation_presence
            ORDER BY last_seen_at DESC, machine_name COLLATE NOCASE, client_id
            """
        ).fetchall()
    result: list[dict] = []
    for row in rows:
        payload = {key: str(row[key] or "").strip() for key in row.keys() if key != "is_admin"}
        payload["is_admin"] = bool(row["is_admin"])
        try:
            seen = datetime.fromisoformat(payload["last_seen_at"])
            payload["online"] = (now - seen).total_seconds() <= age_limit
        except (TypeError, ValueError):
            payload["online"] = False
        result.append(payload)
    return result


def source_display_names(source_type: str) -> dict[str, str]:
    source_type = str(source_type or "").strip()
    if not source_type:
        return {}
    # sqlite3.Connection's context manager commits/rolls back but does NOT
    # close the handle.  That is harmless on POSIX but leaves
    # global_settings.db locked on Windows and prevents TemporaryDirectory
    # cleanup during formal regression builds.  Always close explicitly.
    with closing(_connect()) as db:
        return {
            row["field_key"]: row["display_name"]
            for row in db.execute(
                "SELECT field_key, display_name FROM source_display_names WHERE source_type=? ORDER BY field_key",
                (source_type,),
            )
        }


def replace_source_display_names(
    source_type: str, names: dict[str, str], modified_by: str = ""
) -> None:
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    cleaned = {
        str(key).strip(): str(value).strip()
        for key, value in (names or {}).items()
        if str(key).strip() and str(value).strip()
    }
    before = source_display_names(source_type)
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as db:
        # Explicit transaction + explicit close: on Windows the database file
        # must be released before a test/application-data folder can be removed.
        with db:
            db.execute("DELETE FROM source_display_names WHERE source_type=?", (source_type,))
            for key, value in sorted(cleaned.items()):
                db.execute(
                    "INSERT INTO source_display_names(source_type,field_key,display_name,modified_by,modified_at) VALUES(?,?,?,?,?)",
                    (source_type, key, value, modified_by or "system", now),
                )
            for key in sorted(set(before) | set(cleaned)):
                old_value = str(before.get(key, "") or "").strip()
                new_value = str(cleaned.get(key, "") or "").strip()
                if old_value == new_value:
                    continue
                db.execute(
                    "INSERT INTO source_display_name_audit(source_type,field_key,old_value,new_value,modified_by,modified_at) VALUES(?,?,?,?,?,?)",
                    (source_type, key, old_value, new_value, modified_by or "system", now),
                )



def source_field_overrides(source_type: str) -> dict[str, str]:
    """Return application-wide explicit built-in Source Field selections.

    These are user choices from Map Fields.  They are global by source type so
    selecting a mapping at one station immediately becomes the mapping used by
    every other station.  Automatic declared-header matching still has higher
    priority in the resolver, which protects business logic when a current file
    already contains the canonical/declared header.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return {}
    with closing(_connect()) as db:
        return {
            str(row["field_key"]): str(row["actual_column"] or "").strip()
            for row in db.execute(
                "SELECT field_key,actual_column FROM source_field_override_mappings WHERE source_type=? ORDER BY field_key",
                (source_type,),
            )
            if str(row["field_key"] or "").strip() and str(row["actual_column"] or "").strip()
        }


def replace_source_field_overrides(
    source_type: str, mappings: dict[str, str], modified_by: str = ""
) -> None:
    """Replace the application-wide explicit built-in Source Field selections."""
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    cleaned = {
        str(key).strip(): str(value).strip()
        for key, value in dict(mappings or {}).items()
        if str(key).strip() and str(value).strip()
    }
    before = source_field_overrides(source_type)
    now = datetime.now().isoformat(timespec="seconds")
    by = modified_by or "system"
    with closing(_connect()) as db:
        with db:
            db.execute("DELETE FROM source_field_override_mappings WHERE source_type=?", (source_type,))
            for key, value in sorted(cleaned.items()):
                db.execute(
                    "INSERT INTO source_field_override_mappings(source_type,field_key,actual_column,modified_by,modified_at) VALUES(?,?,?,?,?)",
                    (source_type, key, value, by, now),
                )
            for key in sorted(set(before) | set(cleaned)):
                old_value = str(before.get(key) or "").strip()
                new_value = str(cleaned.get(key) or "").strip()
                if old_value == new_value:
                    continue
                db.execute(
                    "INSERT INTO source_field_override_audit(source_type,field_key,old_value,new_value,modified_by,modified_at) VALUES(?,?,?,?,?,?)",
                    (source_type, key, old_value, new_value, by, now),
                )


def ensure_source_field_overrides(
    source_type: str, mappings: dict[str, str], modified_by: str = "migration"
) -> None:
    """Promote legacy site-local overrides without overwriting global choices.

    This is intentionally merge-only.  Existing project.json values are never
    deleted, and once a global choice exists, opening another site cannot replace
    it.  The user can explicitly replace the global mapping from Map Fields.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    current = source_field_overrides(source_type)
    merged = dict(current)
    changed = False
    for key, value in dict(mappings or {}).items():
        key = str(key or "").strip()
        value = str(value or "").strip()
        if key and value and key not in merged:
            merged[key] = value
            changed = True
    if changed:
        replace_source_field_overrides(source_type, merged, modified_by)


def source_custom_column_bindings(source_type: str) -> dict[str, str]:
    """Return application-wide USER App-column -> Source Field selections."""
    source_type = str(source_type or "").strip()
    if not source_type:
        return {}
    with closing(_connect()) as db:
        return {
            str(row["field_key"]): str(row["actual_column"] or "").strip()
            for row in db.execute(
                "SELECT field_key,actual_column FROM source_custom_column_bindings WHERE source_type=? ORDER BY field_key",
                (source_type,),
            )
            if str(row["field_key"] or "").strip() and str(row["actual_column"] or "").strip()
        }


def replace_source_custom_column_bindings(
    source_type: str, mappings: dict[str, str], modified_by: str = ""
) -> None:
    """Replace global USER App-column physical Source Field selections."""
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    cleaned = {
        str(key).strip(): str(value).strip()
        for key, value in dict(mappings or {}).items()
        if str(key).strip() and str(value).strip()
    }
    before = source_custom_column_bindings(source_type)
    now = datetime.now().isoformat(timespec="seconds")
    by = modified_by or "system"
    with closing(_connect()) as db:
        with db:
            db.execute("DELETE FROM source_custom_column_bindings WHERE source_type=?", (source_type,))
            for key, value in sorted(cleaned.items()):
                db.execute(
                    "INSERT INTO source_custom_column_bindings(source_type,field_key,actual_column,modified_by,modified_at) VALUES(?,?,?,?,?)",
                    (source_type, key, value, by, now),
                )
            for key in sorted(set(before) | set(cleaned)):
                old_value = str(before.get(key) or "").strip()
                new_value = str(cleaned.get(key) or "").strip()
                if old_value == new_value:
                    continue
                db.execute(
                    "INSERT INTO source_custom_column_binding_audit(source_type,field_key,old_value,new_value,modified_by,modified_at) VALUES(?,?,?,?,?,?)",
                    (source_type, key, old_value, new_value, by, now),
                )


def ensure_source_custom_column_bindings(
    source_type: str, mappings: dict[str, str], modified_by: str = "migration"
) -> None:
    """Promote legacy site-local USER mappings without replacing global choices."""
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    current = source_custom_column_bindings(source_type)
    merged = dict(current)
    changed = False
    for key, value in dict(mappings or {}).items():
        key = str(key or "").strip()
        value = str(value or "").strip()
        if key and value and key not in merged:
            merged[key] = value
            changed = True
    if changed:
        replace_source_custom_column_bindings(source_type, merged, modified_by)

def source_custom_columns(source_type: str) -> list[dict]:
    """Return application-wide user-added App columns for one source table.

    The column definition (stable key + display name) is global across all
    sites. Physical Source Field selections are stored separately in the same
    global settings database so a mapping chosen at one station is reused by
    every station. Missing physical headers still render as blank values.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return []
    with closing(_connect()) as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT source_type,field_key,display_name,created_by,created_at,updated_at "
                "FROM source_custom_columns WHERE source_type=? ORDER BY rowid",
                (source_type,),
            )
        ]


def replace_source_custom_columns(
    source_type: str, fields: list[dict], modified_by: str = ""
) -> None:
    """Replace the application-wide App-column definition list for a source.

    Deleting a USER column here removes it from the live RMU Data Review schema
    for every site.  Historical site snapshots/audit remain untouched.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    before = {row["field_key"]: row for row in source_custom_columns(source_type)}
    cleaned: list[dict] = []
    seen: set[str] = set()
    for item in fields or []:
        key = str((item or {}).get("field_key") or "").strip()
        display = str((item or {}).get("display_name") or "").strip()
        if not key or not display or key in seen:
            continue
        seen.add(key)
        cleaned.append({"field_key": key, "display_name": display})
    after = {item["field_key"]: item for item in cleaned}
    now = datetime.now().isoformat(timespec="seconds")
    by = modified_by or "system"
    with closing(_connect()) as db:
        with db:
            db.execute("DELETE FROM source_custom_columns WHERE source_type=?", (source_type,))
            for item in cleaned:
                # Re-adding a USER column intentionally clears an old deletion tombstone.
                db.execute(
                    "DELETE FROM source_custom_column_tombstones WHERE source_type=? AND field_key=?",
                    (source_type, item["field_key"]),
                )
                prior = before.get(item["field_key"]) or {}
                db.execute(
                    "INSERT INTO source_custom_columns(source_type,field_key,display_name,created_by,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (
                        source_type,
                        item["field_key"],
                        item["display_name"],
                        str(prior.get("created_by") or by),
                        str(prior.get("created_at") or now),
                        now,
                    ),
                )
            for key in sorted(set(before) - set(after)):
                db.execute(
                    """INSERT INTO source_custom_column_tombstones(source_type,field_key,deleted_by,deleted_at)
                    VALUES(?,?,?,?)
                    ON CONFLICT(source_type,field_key) DO UPDATE SET deleted_by=excluded.deleted_by,deleted_at=excluded.deleted_at""",
                    (source_type, key, by, now),
                )
            for key in sorted(set(before) | set(after)):
                old_value = str((before.get(key) or {}).get("display_name") or "")
                new_value = str((after.get(key) or {}).get("display_name") or "")
                if old_value == new_value:
                    continue
                db.execute(
                    "INSERT INTO source_custom_column_audit(source_type,field_key,old_value,new_value,modified_by,modified_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (source_type, key, old_value, new_value, by, now),
                )


def ensure_source_custom_columns(
    source_type: str, fields: list[dict], modified_by: str = "migration"
) -> None:
    """Promote legacy site-local custom fields into the global App schema.

    Existing global definitions win on key collisions.  This makes an upgrade
    from v0.8.63 safe: a USER column already created at one site becomes visible
    application-wide as soon as that site's ProjectStore is opened.
    """
    current = source_custom_columns(source_type)
    by_key = {str(item.get("field_key") or "").strip(): dict(item) for item in current}
    with closing(_connect()) as db:
        deleted = {
            str(row[0] or "").strip()
            for row in db.execute(
                "SELECT field_key FROM source_custom_column_tombstones WHERE source_type=?",
                (str(source_type or "").strip(),),
            )
        }
    changed = False
    for item in fields or []:
        key = str((item or {}).get("field_key") or "").strip()
        display = str((item or {}).get("display_name") or key).strip()
        if key and key not in by_key and key not in deleted:
            by_key[key] = {"field_key": key, "display_name": display}
            changed = True
    if changed:
        replace_source_custom_columns(source_type, list(by_key.values()), modified_by)



def review_hidden_columns(view_key: str = "rmu_data_review") -> set[str] | None:
    """Return explicitly hidden columns for a review view.

    ``None`` means no preference has ever been saved.  Persisting *hidden* keys
    instead of a snapshot of visible keys is deliberate: any column introduced
    by a later App version or by a new USER App-column definition is visible by
    default until the reviewer explicitly hides it.
    """
    view_key = str(view_key or "").strip()
    if not view_key:
        return None
    with closing(_connect()) as db:
        row = db.execute(
            "SELECT hidden_keys_json FROM review_column_preferences WHERE view_key=?",
            (view_key,),
        ).fetchone()
    if row is None:
        return None
    try:
        raw = json.loads(str(row["hidden_keys_json"] or "[]"))
    except Exception:
        raw = []
    if not isinstance(raw, list):
        raw = []
    return {str(value).strip() for value in raw if str(value).strip()}


def replace_review_hidden_columns(
    hidden_keys, view_key: str = "rmu_data_review"
) -> None:
    """Persist the reviewer's explicit hidden-column choices application-wide."""
    view_key = str(view_key or "").strip()
    if not view_key:
        return
    cleaned = sorted({str(value).strip() for value in (hidden_keys or []) if str(value).strip()})
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as db:
        with db:
            db.execute(
                """INSERT INTO review_column_preferences(view_key,hidden_keys_json,modified_at)
                VALUES(?,?,?)
                ON CONFLICT(view_key) DO UPDATE SET
                    hidden_keys_json=excluded.hidden_keys_json,
                    modified_at=excluded.modified_at""",
                (view_key, json.dumps(cleaned, ensure_ascii=False), now),
            )

def source_hidden_fields(source_type: str) -> set[str] | None:
    """Return application-wide hidden App/source fields for one source table.

    ``None`` means no visibility choice has ever been saved globally.  The
    preference is keyed only by source type, not by station/project, so a Show
    checkbox change made for ADMS SLD at one station is immediately reused by
    every other station.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return None
    with closing(_connect()) as db:
        row = db.execute(
            "SELECT hidden_keys_json FROM source_visibility_preferences WHERE source_type=?",
            (source_type,),
        ).fetchone()
    if row is None:
        return None
    try:
        raw = json.loads(str(row["hidden_keys_json"] or "[]"))
    except Exception:
        raw = []
    if not isinstance(raw, list):
        raw = []
    return {str(value).strip() for value in raw if str(value).strip()}


def replace_source_hidden_fields(
    source_type: str, hidden_keys, modified_by: str = ""
) -> None:
    """Persist source-field visibility application-wide for every station."""
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    cleaned = sorted({str(value).strip() for value in (hidden_keys or []) if str(value).strip()})
    before = source_hidden_fields(source_type)
    before_sorted = sorted(before or set()) if before is not None else None
    now = datetime.now().isoformat(timespec="seconds")
    by = modified_by or "system"
    with closing(_connect()) as db:
        with db:
            db.execute(
                """INSERT INTO source_visibility_preferences(source_type,hidden_keys_json,modified_by,modified_at)
                VALUES(?,?,?,?)
                ON CONFLICT(source_type) DO UPDATE SET
                    hidden_keys_json=excluded.hidden_keys_json,
                    modified_by=excluded.modified_by,
                    modified_at=excluded.modified_at""",
                (source_type, json.dumps(cleaned, ensure_ascii=False), by, now),
            )
            if before_sorted is None or before_sorted != cleaned:
                db.execute(
                    "INSERT INTO source_visibility_audit(source_type,old_hidden_keys_json,new_hidden_keys_json,modified_by,modified_at) VALUES(?,?,?,?,?)",
                    (
                        source_type,
                        json.dumps(before_sorted or [], ensure_ascii=False),
                        json.dumps(cleaned, ensure_ascii=False),
                        by,
                        now,
                    ),
                )


def source_column_order(source_type: str) -> list[str] | None:
    """Return the application-wide App-column order for one physical source.

    ``None`` means the user has never customized the order.  The stored keys are
    canonical App field keys (built-in or USER), never physical CSV/XLSX indexes.
    This makes the layout independent of source-file column insertion/reordering.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return None
    with closing(_connect()) as db:
        row = db.execute(
            "SELECT order_json FROM source_column_order_preferences WHERE source_type=?",
            (source_type,),
        ).fetchone()
    if row is None:
        return None
    try:
        raw = json.loads(str(row["order_json"] or "[]"))
    except Exception:
        raw = []
    if not isinstance(raw, list):
        raw = []
    output: list[str] = []
    seen: set[str] = set()
    for value in raw:
        key = str(value or "").strip()
        if key and key not in seen:
            seen.add(key)
            output.append(key)
    return output


def replace_source_column_order(
    source_type: str, field_keys, modified_by: str = ""
) -> None:
    """Persist presentation order without touching any site/project data.

    The preference lives in ``global_settings.db`` because App-column definitions
    and display names are application-wide.  It is deliberately separate from
    ``project.db``; changing display order must never migrate or rewrite review
    records, comments, resolutions, audit history or sign-off snapshots.
    """
    source_type = str(source_type or "").strip()
    if not source_type:
        return
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in field_keys or []:
        key = str(value or "").strip()
        if key and key not in seen:
            seen.add(key)
            cleaned.append(key)
    now = datetime.now().isoformat(timespec="seconds")
    with closing(_connect()) as db:
        with db:
            db.execute(
                """INSERT INTO source_column_order_preferences(source_type,order_json,modified_by,modified_at)
                VALUES(?,?,?,?)
                ON CONFLICT(source_type) DO UPDATE SET
                    order_json=excluded.order_json,
                    modified_by=excluded.modified_by,
                    modified_at=excluded.modified_at""",
                (source_type, json.dumps(cleaned, ensure_ascii=False), modified_by or "system", now),
            )



def equipment_comparison_profiles() -> list[dict]:
    """Return reusable Equipment Data Review comparison profiles.

    Profiles live in ``global_settings.db`` and therefore are available to every
    site/project opened by the same application user.  They intentionally store
    logical configuration only; physical site file paths are removed by the
    configurable comparison service before a profile is persisted.
    """
    with closing(_connect()) as db:
        rows = db.execute(
            "SELECT profile_name,payload_json,modified_by,modified_at "
            "FROM equipment_comparison_profiles ORDER BY profile_name COLLATE NOCASE"
        ).fetchall()
    output: list[dict] = []
    for row in rows:
        try:
            payload = json.loads(str(row["payload_json"] or "{}"))
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        output.append({
            "name": str(row["profile_name"] or "").strip(),
            "payload": payload,
            "modified_by": str(row["modified_by"] or "").strip(),
            "modified_at": str(row["modified_at"] or "").strip(),
        })
    return output


def equipment_comparison_profile(profile_name: str) -> dict | None:
    name = str(profile_name or "").strip()
    if not name:
        return None
    with closing(_connect()) as db:
        row = db.execute(
            "SELECT profile_name,payload_json,modified_by,modified_at "
            "FROM equipment_comparison_profiles WHERE profile_name=?",
            (name,),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row["payload_json"] or "{}"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return {
        "name": str(row["profile_name"] or "").strip(),
        "payload": payload,
        "modified_by": str(row["modified_by"] or "").strip(),
        "modified_at": str(row["modified_at"] or "").strip(),
    }


def replace_equipment_comparison_profile(
    profile_name: str, payload: dict, modified_by: str = ""
) -> dict:
    """Create or replace one application-wide reusable comparison profile."""
    name = str(profile_name or "").strip()
    if not name:
        raise ValueError("Profile name is required")
    if not isinstance(payload, dict):
        raise ValueError("Profile payload must be an object")
    before = equipment_comparison_profile(name)
    before_json = json.dumps((before or {}).get("payload") or {}, ensure_ascii=False, sort_keys=True)
    cleaned_payload = json.loads(json.dumps(payload, ensure_ascii=False))
    new_json = json.dumps(cleaned_payload, ensure_ascii=False, sort_keys=True)
    now = datetime.now().isoformat(timespec="seconds")
    by = str(modified_by or "system").strip() or "system"
    with closing(_connect()) as db:
        with db:
            db.execute(
                """INSERT INTO equipment_comparison_profiles(profile_name,payload_json,modified_by,modified_at)
                VALUES(?,?,?,?)
                ON CONFLICT(profile_name) DO UPDATE SET
                    payload_json=excluded.payload_json,
                    modified_by=excluded.modified_by,
                    modified_at=excluded.modified_at""",
                (name, new_json, by, now),
            )
            if before_json != new_json:
                db.execute(
                    "INSERT INTO equipment_comparison_profile_audit(profile_name,old_payload_json,new_payload_json,modified_by,modified_at) VALUES(?,?,?,?,?)",
                    (name, before_json, new_json, by, now),
                )
    return {"name": name, "payload": cleaned_payload, "modified_by": by, "modified_at": now}


def delete_equipment_comparison_profile(profile_name: str, modified_by: str = "") -> bool:
    """Delete a reusable profile without changing any site's saved configuration."""
    name = str(profile_name or "").strip()
    if not name:
        return False
    before = equipment_comparison_profile(name)
    if before is None:
        return False
    before_json = json.dumps(before.get("payload") or {}, ensure_ascii=False, sort_keys=True)
    now = datetime.now().isoformat(timespec="seconds")
    by = str(modified_by or "system").strip() or "system"
    with closing(_connect()) as db:
        with db:
            db.execute("DELETE FROM equipment_comparison_profiles WHERE profile_name=?", (name,))
            db.execute(
                "INSERT INTO equipment_comparison_profile_audit(profile_name,old_payload_json,new_payload_json,modified_by,modified_at) VALUES(?,?,?,?,?)",
                (name, before_json, "{}", by, now),
            )
    return True
