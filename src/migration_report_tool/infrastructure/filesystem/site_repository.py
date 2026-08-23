"""Site Repository discovery, validation and reproducible source synchronization.

The repository is a user-managed input tree. Normal comparison/sync operations are read-only::

    <root>/ADF/SE.xlsx, ZENON.XML, ...
    <root>/ABH/SE.xlsx, ZENON.XML, ...

A comparison run never edits these files: it fingerprints the live site folder,
snapshots it into the application workspace, then archives changed sources
through the existing import service before parsing/comparison. The separately
invoked Regenerate ZENON SLD command is the only repository write and replaces
the derived ZENON-SLD.csv after a successful XML parse.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import hashlib
import json
import shutil
import os
import re
from typing import Iterable

from ...storage import ProjectStore
from ...importing import ImportResult, import_source


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    label: str
    canonical_name: str
    required: bool = True


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition("se_list", "SE Equipment", "SE.xlsx", True),
    SourceDefinition("zenon_xml", "ZENON XML", "ZENON.XML", False),
    SourceDefinition("zenon_db", "ZENON DB", "ZENON-DB.csv", True),
    SourceDefinition("zenon_sld", "ZENON SLD", "ZENON-SLD.csv", False),
    SourceDefinition("adms_db", "ADMS DB", "ADMS-DB.csv", True),
    SourceDefinition("adms_sld", "ADMS SLD", "ADMS-SLD.csv", True),
    SourceDefinition("ioa", "ZENON-ADMS IOA", "ZENON-ADMS-IOA.csv", True),
)
SOURCE_BY_KEY = {item.key: item for item in SOURCE_DEFINITIONS}


def _config_path() -> Path:
    # User preference, not application content: keep it outside the install/release
    # directory so a read-only deployment or application upgrade does not lose it.
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"]) / "NARI" / "MigrationReportTool"
    else:
        base = Path.home() / ".migration-report-tool"
    path = base / "site_repository.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_repository_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_repository_config(payload: dict) -> None:
    payload = dict(payload)
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
    _config_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_repository_root() -> Path | None:
    value = str(_load_repository_config().get("root", "")).strip()
    return Path(value) if value else None


def load_last_site() -> str:
    return str(_load_repository_config().get("last_site", "")).strip()


def save_repository_root(root: Path) -> None:
    root = Path(root).resolve()
    payload = _load_repository_config()
    payload["root"] = str(root)
    _save_repository_config(payload)


def save_last_site(site_name: str) -> None:
    payload = _load_repository_config()
    payload["last_site"] = str(site_name).strip()
    _save_repository_config(payload)


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": file_sha256(path),
    }


def _files_casefold(site_dir: Path) -> dict[str, Path]:
    return {p.name.casefold(): p for p in site_dir.iterdir() if p.is_file()}


def _first_existing(files: dict[str, Path], names: Iterable[str]) -> Path | None:
    for name in names:
        result = files.get(name.casefold())
        if result:
            return result
    return None


def resolve_site_sources(site_dir: Path) -> dict[str, Path]:
    """Resolve canonical names plus safe legacy names used by existing sites."""
    site_dir = Path(site_dir)
    site = site_dir.name
    files = _files_casefold(site_dir)
    result: dict[str, Path] = {}

    candidates = {
        "se_list": ["SE.xlsx", f"{site}-SE.xlsx", f"{site}-LIST.xlsx", f"{site}-LIST(1).xlsx"],
        "zenon_xml": ["ZENON.XML", f"{site}.XML", f"{site}-ZENON.XML"],
        "zenon_db": ["ZENON-DB.csv", f"{site}-ZENON-DB.csv"],
        "zenon_sld": ["ZENON-SLD.csv", f"{site}-ZENON-SLD.csv"],
        "adms_db": ["ADMS-DB.csv", f"{site}-ADMS-DB.csv"],
        "adms_sld": ["ADMS-SLD.csv", f"{site}-ADMS-SLD.csv"],
        "ioa": ["ZENON-ADMS-IOA.csv", f"{site}-ZENON-ADMS-IOA.csv"],
    }
    for key, names in candidates.items():
        hit = _first_existing(files, names)
        if hit:
            result[key] = hit

    # Conservative fallbacks for legacy folders.  Only pick an unambiguous file.
    if "zenon_xml" not in result:
        xmls = list(site_dir.glob("*.xml")) + list(site_dir.glob("*.XML"))
        unique = list({p.resolve(): p for p in xmls}.values())
        site_token = site.upper()
        site_matches = []
        for candidate in unique:
            tokens = [x.upper() for x in re.findall(r"[A-Za-z0-9]+", candidate.stem)]
            if site_token in tokens:
                site_matches.append(candidate)
        if len(site_matches) == 1:
            result["zenon_xml"] = site_matches[0]
        elif len(unique) == 1:
            result["zenon_xml"] = unique[0]
    if "se_list" not in result:
        excels = [p for p in site_dir.glob("*.xlsx")]
        if len(excels) == 1:
            result["se_list"] = excels[0]
    return result


@dataclass
class SiteInfo:
    name: str
    path: Path
    sources: dict[str, Path] = field(default_factory=dict)

    @property
    def missing_required(self) -> list[str]:
        missing = [d.key for d in SOURCE_DEFINITIONS if d.required and d.key not in self.sources]
        # ZENON graphical source requires XML OR fallback SLD CSV.
        if "zenon_xml" not in self.sources and "zenon_sld" not in self.sources:
            missing.append("zenon_xml_or_sld")
        return missing

    @property
    def ready(self) -> bool:
        return not self.missing_required


def scan_repository(root: Path) -> list[SiteInfo]:
    root = Path(root)
    if not root.exists() or not root.is_dir():
        return []
    sites = []
    for folder in sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))), key=lambda p: p.name.casefold()):
        sites.append(SiteInfo(folder.name, folder, resolve_site_sources(folder)))
    return sites


def source_status(site: SiteInfo, store: ProjectStore | None = None) -> dict[str, dict]:
    previous = {}
    if store and store.config.get("repository_site", "").casefold() == site.name.casefold():
        previous = store.config.get("repository_fingerprints", {}) or {}
    statuses: dict[str, dict] = {}
    for definition in SOURCE_DEFINITIONS:
        path = site.sources.get(definition.key)
        if not path:
            graphical_missing = definition.key in {"zenon_xml", "zenon_sld"} and not ({"zenon_xml", "zenon_sld"} & set(site.sources))
            statuses[definition.key] = {
                "status": "MISSING" if definition.required or graphical_missing else "OPTIONAL",
                "path": None,
                "fingerprint": None,
            }
            continue
        fp = fingerprint(path)
        old = previous.get(definition.key)
        if not old:
            state = "NEW"
        elif old.get("sha256") != fp.get("sha256"):
            state = "UPDATED"
        else:
            state = "CURRENT"
        statuses[definition.key] = {"status": state, "path": path, "fingerprint": fp}
    return statuses


@dataclass(frozen=True)
class SiteSyncResult:
    snapshot_dir: Path
    imported: tuple[ImportResult, ...]
    changed_keys: tuple[str, ...]


def sync_site_to_project(store: ProjectStore, site: SiteInfo) -> SiteSyncResult:
    """Snapshot live site sources and archive changed files into the project.

    Source repository files remain untouched.  A new timestamped snapshot is made
    only when at least one source is new/changed or the project has no prior sync.
    """
    if not site.ready:
        raise ValueError("Missing required site source(s): " + ", ".join(site.missing_required))

    # The site folder is the identity. Persist it before importing so parsers
    # (especially combined zenOn XML) can apply the correct site feeder filter.
    store.config["project_name"] = site.name  # legacy compatibility key
    store.config["site_name"] = site.name
    store.config["repository_site"] = site.name
    store.config["repository_path"] = str(site.path.resolve())
    store.save_config()

    statuses = source_status(site, store)
    previous_keys = set((store.config.get("repository_fingerprints", {}) or {}).keys())
    removed = sorted(previous_keys - set(site.sources.keys()))
    changed = [key for key, value in statuses.items() if value["status"] in {"NEW", "UPDATED"}] + removed
    # Repair an incomplete workspace even if the live file fingerprint is unchanged.
    for key, path in site.sources.items():
        if not store.source_path(key) and key not in changed:
            changed.append(key)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    snapshot_dir = store.snapshots_dir / stamp
    imported: list[ImportResult] = []
    if changed or not store.config.get("repository_last_sync"):
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        manifest = {
            "site": site.name,
            "repository_path": str(site.path.resolve()),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "sources": {},
        }
        for key, source in site.sources.items():
            definition = SOURCE_BY_KEY[key]
            target = snapshot_dir / definition.canonical_name
            shutil.copy2(source, target)
            fp = fingerprint(source)
            manifest["sources"][key] = {"original_name": source.name, "snapshot_name": target.name, **fp}
            if key in changed:
                imported.append(import_source(store, key, source))
        for key in removed:
            store.clear_source(key)
            manifest.setdefault("removed_sources", []).append(key)
        (snapshot_dir / "snapshot.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        # No file content changed; reference the previous snapshot for diagnostics.
        previous = store.config.get("repository_last_snapshot", "")
        snapshot_dir = Path(previous) if previous else store.snapshots_dir

    current_fps = {key: fingerprint(path) for key, path in site.sources.items()}
    store.config["project_name"] = site.name  # legacy compatibility key
    store.config["site_name"] = site.name
    store.config["repository_site"] = site.name
    store.config["repository_path"] = str(site.path.resolve())
    store.config["repository_fingerprints"] = current_fps
    store.config["repository_last_sync"] = datetime.now().isoformat(timespec="seconds")
    store.config["repository_last_snapshot"] = str(snapshot_dir)
    store.save_config()
    return SiteSyncResult(snapshot_dir=snapshot_dir, imported=tuple(imported), changed_keys=tuple(sorted(set(changed))))
