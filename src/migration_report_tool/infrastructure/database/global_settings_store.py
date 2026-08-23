"""Application-wide persistent settings.

Unlike ``ProjectStore`` (one database per site), this store holds presentation
metadata that must be identical for every site, such as review-table Display
Names.  It lives under the writable application user-data root so settings
survive release-folder replacement.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3

from ...utils.paths import user_data_root


def global_settings_db_path() -> Path:
    path = user_data_root() / "settings" / "global_settings.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect() -> sqlite3.Connection:
    db = sqlite3.connect(global_settings_db_path())
    db.row_factory = sqlite3.Row
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
        """
    )
    return db


def source_display_names(source_type: str) -> dict[str, str]:
    source_type = str(source_type or "").strip()
    if not source_type:
        return {}
    with _connect() as db:
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
    with _connect() as db:
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
