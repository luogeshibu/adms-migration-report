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

class ProjectStore:
    def __init__(self, folder: Path):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.sources_dir = self.folder / "source_files"
        self.generated_dir = self.folder / "generated"
        self.reports_dir = self.folder / "reports"
        self.snapshots_dir = self.folder / "snapshots"
        for directory in (self.sources_dir, self.generated_dir, self.reports_dir, self.snapshots_dir):
            directory.mkdir(exist_ok=True)
        self.config_path = self.folder / "project.json"
        self.db_path = self.folder / "project.db"
        self.config = self._load_config()
        self.db = sqlite3.connect(self.db_path)
        self.db.row_factory = sqlite3.Row
        self._init_db()

    def _load_config(self):
        if self.config_path.exists():
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        return {"project_name": self.folder.name, "created_at": datetime.now().isoformat(timespec="seconds"), "sources": {}}

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

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
            reviewed_by TEXT, reviewed_at TEXT, updated_at TEXT, analysis_hash TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS db_smart_reviews (
            row_key TEXT PRIMARY KEY, site_name TEXT, rmu TEXT, source_hash TEXT, row_hash TEXT NOT NULL DEFAULT '',
            review_status TEXT NOT NULL DEFAULT 'UNREVIEWED', comments TEXT NOT NULL DEFAULT '',
            reviewed_by TEXT, reviewed_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS source_display_names (
            source_type TEXT NOT NULL, field_key TEXT NOT NULL, display_name TEXT NOT NULL,
            modified_by TEXT, modified_at TEXT,
            PRIMARY KEY(source_type, field_key)
        );
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(comparison)")}
        if "data_json" not in columns:
            self.db.execute("ALTER TABLE comparison ADD COLUMN data_json TEXT")
        if "comments" not in columns:
            self.db.execute("ALTER TABLE comparison ADD COLUMN comments TEXT")
        rmu_review_columns = {row[1] for row in self.db.execute("PRAGMA table_info(rmu_reviews)")}
        if "analysis_hash" not in rmu_review_columns:
            self.db.execute("ALTER TABLE rmu_reviews ADD COLUMN analysis_hash TEXT NOT NULL DEFAULT ''")
        signal_review_columns = {row[1] for row in self.db.execute("PRAGMA table_info(db_smart_reviews)")}
        if "row_hash" not in signal_review_columns:
            self.db.execute("ALTER TABLE db_smart_reviews ADD COLUMN row_hash TEXT NOT NULL DEFAULT ''")
        self.db.commit()


    def source_column_overrides(self, source_type: str) -> dict[str, str]:
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

    @staticmethod
    def _rmu_analysis_hash(row: dict) -> str:
        """Fingerprint only the automatic RMU analysis result.

        Manual Review stays valid when unrelated source/display data changes, but
        is invalidated when an Analysis field or its explanation changes.
        """
        payload = {
            key: clean(value)
            for key, value in sorted((row or {}).items())
            if str(key).startswith("analysis_")
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _sync_rmu_review_analysis_hash(self, rmu: str, analysis_hash: str) -> None:
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
        if old_hash and old_hash != analysis_hash and status != "UNREVIEWED":
            self.db.execute(
                "UPDATE rmu_reviews SET review_status='UNREVIEWED',reviewed_by='',reviewed_at='',updated_at=?,analysis_hash=? WHERE rmu=?",
                (now, analysis_hash, rmu),
            )
            self.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                (rmu, "rmu_review_status", status, "UNREVIEWED",
                 "Automatic reset: RMU validation result changed after source refresh", "SYSTEM", now),
            )
        elif old_hash != analysis_hash:
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
                self._sync_rmu_review_analysis_hash(rmu, self._rmu_analysis_hash(auto))
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

    def rows(self) -> list[dict]:
        result = []
        for record in self.db.execute("SELECT * FROM comparison ORDER BY no, rmu"):
            row = dict(record)
            result.append(json.loads(row.get("data_json") or "{}") or row)
        return result

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
        self.db.commit()

    def save_version(self, name: str, description: str, created_by: str):
        snapshot = {
            "project": self.config,
            "rows": self.rows(),
            "changes": self.changes(),
            "rmu_reviews": list(self.rmu_review_map().values()),
            "db_smart_reviews": list(self.db_smart_review_map().values()),
            "source_display_names": {
                source_type: self.source_display_names(source_type)
                for source_type in sorted({row["source_type"] for row in self.db.execute("SELECT DISTINCT source_type FROM source_display_names")})
            },
        }
        self.db.execute(
            "INSERT INTO versions(version_name,description,snapshot_json,created_by,created_at) VALUES(?,?,?,?,?)",
            (name, description, json.dumps(snapshot, ensure_ascii=False), created_by, datetime.now().isoformat(timespec="seconds")),
        )
        self.db.commit()

    def versions(self):
        return [dict(r) for r in self.db.execute("SELECT id,version_name,description,created_by,created_at FROM versions ORDER BY id DESC")]

    def changes(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM changes ORDER BY id DESC")]


    def rmu_review_map(self) -> dict[str, dict]:
        return {
            row["rmu"]: dict(row)
            for row in self.db.execute("SELECT * FROM rmu_reviews")
        }

    def update_rmu_review_status(
        self, rmu: str, review_status: str, modified_by: str,
        reason: str = "RMU Data Review status changed",
    ) -> None:
        rmu = clean(rmu)
        if not rmu:
            raise ValueError("RMU is required for review status")
        value = clean(review_status).upper() or "UNREVIEWED"
        if value not in {"UNREVIEWED", "REVIEWED", "NEEDS ACTION"}:
            raise ValueError(f"Invalid RMU review status: {value}")
        current = self.db.execute("SELECT * FROM rmu_reviews WHERE rmu=?", (rmu,)).fetchone()
        old_value = clean(current["review_status"]).upper() if current else "UNREVIEWED"
        if old_value == value:
            return
        now = datetime.now().isoformat(timespec="seconds")
        reviewed_by = modified_by if value in {"REVIEWED", "NEEDS ACTION"} else ""
        reviewed_at = now if value in {"REVIEWED", "NEEDS ACTION"} else ""
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
        self.db.commit()


    def db_smart_review_map(self) -> dict[str, dict]:
        return {
            row["row_key"]: dict(row)
            for row in self.db.execute("SELECT * FROM db_smart_reviews")
        }

    def sync_db_smart_review_fingerprints(
        self, fingerprints: dict[str, dict[str, str]], modified_by: str = "SYSTEM"
    ) -> int:
        """Invalidate only Signal Mapping rows whose validation fingerprint changed.

        Comments and audit history are preserved.  Legacy reviewed rows that only
        have the old report-level source_hash are reset if the source hash changed.
        Returns the number of human Review states reset to UNREVIEWED.
        """
        reset_count = 0
        now = datetime.now().isoformat(timespec="seconds")
        with self.db:
            for row_key, info in (fingerprints or {}).items():
                current = self.db.execute("SELECT * FROM db_smart_reviews WHERE row_key=?", (row_key,)).fetchone()
                if current is None:
                    continue
                new_row_hash = clean(info.get("row_hash"))
                new_source_hash = clean(info.get("source_hash"))
                old_row_hash = clean(current["row_hash"])
                old_source_hash = clean(current["source_hash"])
                status = clean(current["review_status"]).upper() or "UNREVIEWED"
                changed = bool(old_row_hash and new_row_hash and old_row_hash != new_row_hash)
                if not old_row_hash and old_source_hash and new_source_hash and old_source_hash != new_source_hash:
                    changed = True
                if changed and status != "UNREVIEWED":
                    self.db.execute(
                        "UPDATE db_smart_reviews SET review_status='UNREVIEWED',reviewed_by='',reviewed_at='',source_hash=?,row_hash=?,updated_at=? WHERE row_key=?",
                        (new_source_hash, new_row_hash, now, row_key),
                    )
                    self.db.execute(
                        "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                        (f"DBSMART:{clean(current['rmu']) or row_key[:12]}", "db_smart_review_status", status, "UNREVIEWED",
                         "Automatic reset: Signal Mapping validation result changed after source refresh", modified_by or "SYSTEM", now),
                    )
                    reset_count += 1
                elif old_source_hash != new_source_hash or old_row_hash != new_row_hash:
                    self.db.execute(
                        "UPDATE db_smart_reviews SET source_hash=?,row_hash=?,updated_at=? WHERE row_key=?",
                        (new_source_hash, new_row_hash, now, row_key),
                    )
        return reset_count

    def update_db_smart_review(
        self, row_key: str, rmu: str, field: str, value: str, modified_by: str,
        source_hash: str = "", row_hash: str = "", site_name: str = "", reason: str = "Signal Mapping Review",
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
            if value not in {"UNREVIEWED", "REVIEWED", "NEEDS ACTION"}:
                raise ValueError(f"Invalid DB Smart review status: {value}")
        if old_value == value:
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
        }
        payload[field] = value
        if field == "review_status" and value in {"REVIEWED", "NEEDS ACTION"}:
            payload["reviewed_by"] = modified_by
            payload["reviewed_at"] = now
        self.db.execute(
            """INSERT INTO db_smart_reviews
            (row_key,site_name,rmu,source_hash,row_hash,review_status,comments,reviewed_by,reviewed_at,updated_at)
            VALUES(:row_key,:site_name,:rmu,:source_hash,:row_hash,:review_status,:comments,:reviewed_by,:reviewed_at,:updated_at)
            ON CONFLICT(row_key) DO UPDATE SET
              site_name=excluded.site_name,rmu=excluded.rmu,source_hash=excluded.source_hash,row_hash=excluded.row_hash,
              review_status=excluded.review_status,comments=excluded.comments,
              reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at,updated_at=excluded.updated_at
            """,
            payload,
        )
        audit_record = f"DBSMART:{rmu or row_key[:12]}"
        self.db.execute(
            "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
            (audit_record, f"db_smart_{field}", old_value, value, reason, modified_by, now),
        )
        self.db.commit()


