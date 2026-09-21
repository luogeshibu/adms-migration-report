"""Site Repository discovery, validation and reproducible source synchronization.

The repository is a user-managed input tree. Comparison/sync operations are
read-only: each site supplies tabular source files such as SE.xlsx,
ZENON-SLD.csv, ZENON-DB.csv, ADMS-DB.csv and ADMS-SLD.csv.

ZENON-SLD.csv is supplied directly by the user/external extractor. The
Migration Report application does not parse ZENON XML and never generates or
overwrites ZENON-SLD.csv.
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
import csv
from typing import Iterable
from functools import lru_cache

from openpyxl import load_workbook

from ...config.sources import schema_for
from ...domain.schema import MappingKind, resolve_schema

from ...storage import ProjectStore
from ...importing import ImportResult, import_source
from ...services.portable_site_service import is_unified_site_folder


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    label: str
    canonical_name: str
    required: bool = True


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition("se_list", "SE Equipment", "SE.xlsx", True),
    SourceDefinition("zenon_db", "ZENON DB", "ZENON-DB.csv", True),
    SourceDefinition("zenon_sld", "ZENON SLD", "ZENON-SLD.csv", True),
    SourceDefinition("adms_db", "ADMS DB", "ADMS-DB.csv", True),
    SourceDefinition("adms_sld", "ADMS SLD", "ADMS-SLD.csv", True),
    SourceDefinition("ioa", "ZENON-ADMS IOA", "ZENON-ADMS-IOA.csv", True),
)
SOURCE_BY_KEY = {item.key: item for item in SOURCE_DEFINITIONS}


# Filename keywords are only a discovery hint.  Exact/manual mappings win and
# tabular keyword hits are verified against the source schema before use.
DEFAULT_SOURCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "se_list": ("SE", "LIST", "EQUIPMENT"),
    "zenon_db": ("ZENON-DB", "ZENON_DB", "ZENONDB"),
    "zenon_sld": ("ZENON-SLD", "ZENON_SLD", "ZENONSLD", "DEVICE_INVENTORY", "DEVICE-INVENTORY"),
    "adms_db": ("ADMS-DB", "ADMS_DB", "ADMSDB"),
    "adms_sld": ("ADMS-SLD", "ADMS_SLD", "ADMSSLD"),
    "ioa": ("ZENON-ADMS-IOA", "IOA"),
}


@dataclass(frozen=True)
class SourceDetection:
    path: Path
    method: str
    confidence: int = 100
    detail: str = ""


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


DEFAULT_SHARED_REPOSITORY_ROOT = Path(r"\\172.16.21.101\Share Folder\Downstream Report")


def load_repository_root() -> Path | None:
    config = _load_repository_config()
    value = str(config.get("root", "")).strip()
    # Do not probe the default UNC path while constructing the main window.
    # Windows can block for a long time when a remembered server is offline.
    # The setup guide can still offer/select this path after the UI is visible.
    # A saved explicit path remains authoritative for upgrade compatibility.
    return Path(value) if value else None


def load_last_site() -> str:
    return str(_load_repository_config().get("last_site", "")).strip()


def save_repository_root(root: Path) -> None:
    root = Path(root).resolve()
    payload = _load_repository_config()
    payload["root"] = str(root)
    payload["repository_root_user_selected_v1"] = True
    _save_repository_config(payload)


def save_last_site(site_name: str) -> None:
    payload = _load_repository_config()
    payload["last_site"] = str(site_name).strip()
    _save_repository_config(payload)


def _detection_category_key(label: str, existing: set[str] | None = None) -> str:
    """Create a stable custom detection-hint key from a reviewer label.

    Built-in source keys remain unchanged for backward compatibility. Custom
    categories are presentation/discovery hints only and never become mandatory
    business source roles.
    """
    label = str(label or "").strip()
    token = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_") or "category"
    base = f"custom::{token}"
    used = set(existing or ())
    if base not in used:
        return base
    index = 2
    while f"{base}_{index}" in used:
        index += 1
    return f"{base}_{index}"


def load_source_detection_categories() -> list[dict]:
    """Return every optional filename-recognition category.

    The historical six source roles are seeded as built-ins so legacy AUTO
    discovery keeps working. Reviewers may add any number of extra categories;
    those custom categories are hints for file-pool classification only and do
    not constrain filenames or force a file into Equipment/Signal review.
    """
    config = _load_repository_config()
    payload = config.get("source_detection_keywords", {}) or {}
    labels = config.get("source_detection_labels", {}) or {}
    builtin_by_key = {definition.key: definition for definition in SOURCE_DEFINITIONS}
    ordered_keys = [definition.key for definition in SOURCE_DEFINITIONS]
    for key in payload:
        key = str(key or "").strip()
        if key and key not in ordered_keys:
            ordered_keys.append(key)
    result: list[dict] = []
    for key in ordered_keys:
        definition = builtin_by_key.get(key)
        configured = payload.get(key)
        defaults = list(DEFAULT_SOURCE_KEYWORDS.get(key, ())) if definition else []
        values = configured if isinstance(configured, list) else defaults
        clean_values = [str(value).strip() for value in values if str(value).strip()]
        label = str(labels.get(key) or (definition.label if definition else key.removeprefix("custom::").replace("_", " ").strip().title()) or key).strip()
        result.append({
            "key": key,
            "label": label,
            "keywords": clean_values,
            "built_in": bool(definition),
        })
    return result


def save_source_detection_categories(categories: list[dict]) -> None:
    """Persist built-in and reviewer-defined optional recognition categories."""
    config = _load_repository_config()
    existing_keys: set[str] = set()
    cleaned_keywords: dict[str, list[str]] = {}
    cleaned_labels: dict[str, str] = {}
    builtin_keys = {definition.key for definition in SOURCE_DEFINITIONS}

    # Always keep built-in keys available for legacy AUTO source resolution.
    incoming_by_key = {str(item.get("key") or "").strip(): dict(item) for item in (categories or []) if str(item.get("key") or "").strip()}
    for definition in SOURCE_DEFINITIONS:
        item = incoming_by_key.get(definition.key, {})
        values = item.get("keywords", DEFAULT_SOURCE_KEYWORDS.get(definition.key, ()))
        cleaned_keywords[definition.key] = [str(value).strip() for value in (values or []) if str(value).strip()]
        cleaned_labels[definition.key] = str(item.get("label") or definition.label).strip()
        existing_keys.add(definition.key)

    for raw in categories or []:
        key = str(raw.get("key") or "").strip()
        label = str(raw.get("label") or "").strip()
        if key in builtin_keys:
            continue
        if not label and not key:
            continue
        if not key or key in existing_keys:
            key = _detection_category_key(label or key, existing_keys)
        values = raw.get("keywords", []) or []
        cleaned_keywords[key] = [str(value).strip() for value in values if str(value).strip()]
        cleaned_labels[key] = label or key.removeprefix("custom::").replace("_", " ").strip().title()
        existing_keys.add(key)

    config["source_detection_keywords"] = cleaned_keywords
    config["source_detection_labels"] = cleaned_labels
    _save_repository_config(config)


def load_source_detection_keywords() -> dict[str, list[str]]:
    return {
        str(item.get("key")): list(item.get("keywords") or [])
        for item in load_source_detection_categories()
        if str(item.get("key") or "").strip()
    }


def save_source_detection_keywords(keywords: dict[str, list[str]]) -> None:
    """Backward-compatible save used by older UI/tests.

    Unknown keys are retained as custom hint categories instead of being
    discarded, removing the historical fixed-six-category UI limitation.
    """
    current = {item["key"]: item for item in load_source_detection_categories()}
    categories: list[dict] = []
    for key, values in (keywords or {}).items():
        key = str(key or "").strip()
        if not key:
            continue
        item = dict(current.get(key) or {"key": key, "label": key, "built_in": key in SOURCE_BY_KEY})
        item["keywords"] = list(values or [])
        categories.append(item)
    # Preserve categories omitted by the caller, because recognition is now a
    # freely extensible preference rather than a fixed form contract.
    seen = {item.get("key") for item in categories}
    categories.extend(item for key, item in current.items() if key not in seen)
    save_source_detection_categories(categories)


def classify_source_detection_hint(path: Path) -> list[dict]:
    """Return optional filename-category hints for one arbitrary tabular file.

    This helper never rejects or auto-enrols a file. It merely ranks configured
    filename hints so the configurable source pool can show useful suggestions.
    Manual source selection and field/key mapping remain authoritative.
    """
    path = Path(path)
    ranked: list[dict] = []
    for category in load_source_detection_categories():
        hits = [kw for kw in (category.get("keywords") or []) if _keyword_matches(path, kw)]
        if not hits:
            continue
        ranked.append({
            "key": category.get("key"),
            "label": category.get("label") or category.get("key"),
            "keywords": hits,
            "score": max(1, len(hits)),
            "built_in": bool(category.get("built_in")),
        })
    ranked.sort(key=lambda item: (-int(item.get("score") or 0), 0 if item.get("built_in") else 1, str(item.get("label") or "").casefold()))
    return ranked


def _manual_assignment_bucket(site_dir: Path) -> tuple[dict, str]:
    payload = _load_repository_config()
    root = str(Path(site_dir).resolve())
    assignments = payload.setdefault("manual_source_assignments", {})
    return payload, root


def save_manual_source_assignment(site_dir: Path, source_type: str, file_path: Path | None) -> None:
    payload, root = _manual_assignment_bucket(site_dir)
    assignments = payload.setdefault("manual_source_assignments", {})
    site_map = dict(assignments.get(root, {}) or {})
    if file_path is None:
        site_map.pop(source_type, None)
    else:
        site_map[source_type] = Path(file_path).name
    assignments[root] = site_map
    _save_repository_config(payload)


def load_manual_source_assignments(site_dir: Path) -> dict[str, str]:
    _payload = _load_repository_config()
    root = str(Path(site_dir).resolve())
    return dict((_payload.get("manual_source_assignments", {}) or {}).get(root, {}) or {})


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


def metadata_fingerprint(path: Path) -> dict:
    """Cheap file identity for UI/navigation.

    Full SHA256 is intentionally excluded; explicit Refresh Sources and
    Validation still use :func:`fingerprint` so change detection remains exact
    at the processing boundary.
    """
    stat = Path(path).stat()
    return {
        "name": Path(path).name,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": "",
    }


def _files_casefold(site_dir: Path) -> dict[str, Path]:
    result = {p.name.casefold(): p for p in site_dir.iterdir() if p.is_file()}
    # Unified sites keep source tables in source_files. Keep the legacy root
    # lookup first so duplicate names remain deterministic during migration.
    for path in site_tabular_files(site_dir):
        result.setdefault(path.name.casefold(), path)
    return result


def _first_existing(files: dict[str, Path], names: Iterable[str]) -> Path | None:
    for name in names:
        result = files.get(name.casefold())
        if result:
            return result
    return None


TABULAR_SOURCE_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}


def site_tabular_files(site_dir: Path) -> tuple[Path, ...]:
    """Return all supported tabular files below one site folder recursively.

    Site folders are reviewer-managed and may organize sources in arbitrary
    nested subfolders (for example ``Equipment/`` and ``SignalMapping/``).
    Discovery therefore must never be root-only.  Temporary Office lock files
    and clearly archival/hidden folders are ignored so they cannot make an
    otherwise empty site look configurable.
    """
    root = Path(site_dir)
    if not root.exists() or not root.is_dir():
        return ()
    found: list[Path] = []
    for candidate in root.rglob("*"):
        try:
            if not candidate.is_file() or candidate.suffix.lower() not in TABULAR_SOURCE_EXTENSIONS:
                continue
            if candidate.name.startswith("~$"):
                continue
            rel = candidate.relative_to(root)
            parent_parts = rel.parts[:-1]
            if any(
                part.startswith(".")
                or part.casefold() in {"archive", "backup", "backups", "generated", "reports", "snapshots", "__pycache__"}
                for part in parent_parts
            ):
                continue
            found.append(candidate)
        except (OSError, ValueError):
            continue
    return tuple(sorted(
        found,
        key=lambda path: (
            len(path.relative_to(root).parts),
            str(path.relative_to(root)).casefold(),
        ),
    ))


def site_has_tabular_files(site_dir: Path) -> bool:
    """Cheap semantic helper used by station-list availability status."""
    return bool(site_tabular_files(site_dir))


def _source_extensions(source_type: str) -> set[str]:
    # v0.8.155: every site source role accepts either CSV or modern Excel.
    # The physical filename is not a business contract; App-field mapping is.
    return set(TABULAR_SOURCE_EXTENSIONS)


_SOURCE_VERSION_RE = re.compile(r"(?:^|[-_.\s])V(\d+(?:\.\d+)*)$", flags=re.IGNORECASE)
_SOURCE_VERSIONISH_RE = re.compile(r"(?:^|[-_.\s])V[^-_.\s]+$", flags=re.IGNORECASE)


def has_explicit_source_version(path: Path) -> bool:
    """Return True only when the physical filename ends in an explicit V version.

    Automatic repository selection is intentionally strict: an input is a
    published/auto-selectable source only when its filename carries a parsable
    suffix such as ``-V1`` or ``-V2.1.0``.  Unversioned files remain available
    for explicit/manual assignment, but they never participate in AUTO latest
    selection.
    """
    return bool(_SOURCE_VERSION_RE.search(Path(path).stem.strip()))


def source_file_version(path: Path) -> tuple[int, ...]:
    """Return a semantic V-version tuple parsed from the filename.

    Examples:
    ``ZENON-SLD.csv`` -> ``(0,)`` (unversioned / AUTO-ineligible)
    ``ZENON-SLD-V1.csv`` -> ``(1,)``
    ``ZENON-SLD-V2.1.0.csv`` -> ``(2, 1, 0)``

    AUTO source selection uses only filenames for which
    :func:`has_explicit_source_version` is true.  Modification time is only a
    tie-breaker between files carrying the same semantic V version.
    """
    stem = Path(path).stem.strip()
    match = _SOURCE_VERSION_RE.search(stem)
    if not match:
        return (0,)
    try:
        return tuple(int(part) for part in match.group(1).split("."))
    except Exception:
        return (0,)


def source_file_version_label(path: Path) -> str:
    if not has_explicit_source_version(path):
        return "Unversioned"
    version = source_file_version(path)
    return "V" + ".".join(str(part) for part in version)


def _stem_without_version(path: Path) -> str:
    return re.sub(r"(?:[-_.\s])V\d+(?:\.\d+)*$", "", Path(path).stem, flags=re.IGNORECASE).strip()


def _normalized_source_stem(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _family_name_matches_source(path: Path, source_type: str, site_name: str = "") -> bool:
    """Recognize canonical/site-prefixed source filenames with optional V suffix."""
    definition = SOURCE_BY_KEY.get(source_type)
    if definition is None:
        return False
    stem = _normalized_source_stem(_stem_without_version(path))
    canonical_stem = _normalized_source_stem(Path(definition.canonical_name).stem)
    site_stem = _normalized_source_stem(site_name)
    accepted = {canonical_stem}
    if site_stem:
        accepted.add(site_stem + canonical_stem)
    if source_type == "se_list":
        accepted.update({_normalized_source_stem("SE"), _normalized_source_stem(f"{site_name}-SE")})
    return stem in accepted


def _has_unparsable_version_suffix(path: Path) -> bool:
    """Return True when a filename looks versioned but its V suffix is invalid.

    ``ZENON-SLD-VX.csv`` and ``ADMS-DB-Vfinal.csv`` must never become AUTO
    fallbacks merely because filename detection rules match the rest of their
    names.  A plain base file such as ``ZENON-SLD.csv`` is *not* malformed and
    remains eligible for rule-based AUTO fallback when no published V file
    exists.
    """
    stem = Path(path).stem.strip()
    return bool(_SOURCE_VERSIONISH_RE.search(stem)) and not has_explicit_source_version(path)


def source_version_candidates(site_dir: Path, source_type: str) -> list[Path]:
    """Return published filename-family V versions for one source, newest first.

    Published versions remain strict: a file must carry a parsable ``V`` suffix
    (``V1``, ``V2``, ``V2.1.0`` ...).  AUTO uses the highest such version first.
    If no published V candidate exists, repository discovery may then fall back
    to the configured Source Detection Rules for an unversioned base file.
    Explicit MANUAL selection still has the highest priority.
    """
    site_dir = Path(site_dir)
    if source_type not in SOURCE_BY_KEY or not site_dir.exists():
        return []
    result: list[Path] = []
    for candidate in site_tabular_files(site_dir):
        if candidate.suffix.lower() not in _source_extensions(source_type):
            continue
        if _family_name_matches_source(candidate, source_type, site_dir.name) and has_explicit_source_version(candidate):
            result.append(candidate)

    def sort_key(path: Path):
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            mtime = 0
        # normalize variable-length versions: V2.1 > V2.0.9 > V1
        version = source_file_version(path)
        padded = tuple(version) + (0,) * max(0, 8 - len(version))
        return padded, mtime, path.name.casefold()

    result.sort(key=sort_key, reverse=True)
    return result


def _rule_fallback_candidates(site_dir: Path, source_type: str, used: set[Path] | None = None) -> list[Path]:
    """Return filename-rule candidates for AUTO fallback.

    This is intentionally cheap and never opens source contents.  It uses the
    user-configurable Source Detection Rules plus the canonical filename family.
    Parsable V files sort above base files; malformed V-looking filenames are
    excluded from AUTO.  Callers use this only after the strict canonical
    published-version pass, so the normal path is: latest V -> rule fallback.
    """
    site_dir = Path(site_dir)
    used = used or set()
    if source_type not in SOURCE_BY_KEY or not site_dir.exists():
        return []
    keywords = load_source_detection_keywords().get(source_type, [])
    candidates: list[Path] = []
    for candidate in site_tabular_files(site_dir):
        if candidate.suffix.lower() not in _source_extensions(source_type):
            continue
        try:
            if candidate.resolve() in used:
                continue
        except OSError:
            continue
        if _has_unparsable_version_suffix(candidate):
            continue
        family = _family_name_matches_source(candidate, source_type, site_dir.name)
        keyword = any(_keyword_matches(candidate, kw) for kw in keywords)
        if family or keyword:
            candidates.append(candidate)

    # If any rule candidate is a valid published version, unversioned siblings
    # do not compete with it.  This lets custom filename rules still obey the
    # latest-version policy.
    versioned = [p for p in candidates if has_explicit_source_version(p)]
    if versioned:
        candidates = versioned

    def sort_key(path: Path):
        family = 1 if _family_name_matches_source(path, source_type, site_dir.name) else 0
        version = source_file_version(path) if has_explicit_source_version(path) else (0,)
        padded = tuple(version) + (0,) * max(0, 8 - len(version))
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            mtime = 0
        return (1 if has_explicit_source_version(path) else 0, padded, family, mtime, path.name.casefold())

    candidates.sort(key=sort_key, reverse=True)
    return candidates


def _decode_preview(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "latin1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1", errors="ignore")


def _quick_tabular_header_rows(path: Path, scan_rows: int = 10) -> list[list[str]]:
    """Read only candidate header rows; discovery never loads whole source tables."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        text = _decode_preview(path.read_bytes()[:256 * 1024])
        sample = text.splitlines()
        if not sample:
            return []
        try:
            dialect = csv.Sniffer().sniff("\n".join(sample[:8]), delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = []
        for row in csv.reader(sample[:scan_rows], dialect):
            cleaned = [str(value or "").replace("\ufeff", "").strip() for value in row]
            if any(cleaned):
                rows.append(cleaned)
        return rows
    if suffix in {".xlsx", ".xlsm"}:
        # Repository discovery must never crash the whole desktop App because a
        # user folder contains a damaged workbook, a legacy XLS file renamed to
        # .xlsx, or a partially copied Excel file. Treat it as unreadable here;
        # the Site Data Sources page will show the mapped source as ERROR instead.
        try:
            wb = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        except Exception:
            return []
        try:
            # Filenames are not source contracts. For content/schema discovery,
            # inspect candidate header rows from every worksheet so a Cover or
            # README first sheet cannot hide the real data sheet. Workbook order
            # is preserved and downstream reading still uses the selected/AUTO sheet.
            rows = []
            for name in wb.sheetnames:
                ws = wb[name]
                for values in ws.iter_rows(min_row=1, max_row=min(scan_rows, ws.max_row), values_only=True):
                    cleaned = [str(value or "").replace("\ufeff", "").strip() for value in values]
                    if any(cleaned):
                        rows.append(cleaned)
            return rows
        except Exception:
            return []
        finally:
            try:
                wb.close()
            except Exception:
                pass
    return []


@lru_cache(maxsize=2048)
def _schema_content_score_cached(source_type: str, path_text: str, size: int, mtime_ns: int) -> tuple[int, str]:
    # size/mtime are part of the cache key so unchanged source files are never
    # reopened merely because the user revisits Site Data Sources.
    path = Path(path_text)
    schema = schema_for(source_type)
    if schema is None:
        return 0, ""
    best_score = 0
    best_detail = ""
    for headers in _quick_tabular_header_rows(path):
        validation = resolve_schema(schema, headers)
        if validation.errors:
            continue
        matched = [m for m in validation.mappings if m.kind not in {MappingKind.MISSING, MappingKind.AMBIGUOUS}]
        required = [m for m in validation.mappings if m.required]
        if required and any(m.kind == MappingKind.MISSING for m in required):
            continue
        coverage = len(matched) / max(1, len(validation.mappings))
        required_ratio = sum(m.required for m in matched) / max(1, sum(m.required for m in validation.mappings))
        # Required fields dominate; optional distinctive fields push a source
        # above ambiguous RMU-only CSVs.
        score = int(round(55 + 20 * required_ratio + 25 * coverage))
        if len(matched) <= 1:
            score = min(score, 68)
        if score > best_score:
            best_score = score
            best_detail = ", ".join(m.actual_column for m in matched if m.actual_column)
    return best_score, best_detail


def _schema_content_score(source_type: str, path: Path) -> tuple[int, str]:
    try:
        stat = Path(path).stat()
        return _schema_content_score_cached(source_type, str(Path(path).resolve()), int(stat.st_size), int(stat.st_mtime_ns))
    except Exception:
        return 0, ""



def _keyword_matches(path: Path, keyword: str) -> bool:
    kw = str(keyword or "").strip().casefold()
    if not kw:
        return False
    stem = path.stem.casefold()
    if len(kw) <= 3 and kw.isalnum():
        tokens = re.findall(r"[a-z0-9]+", stem)
        return kw in tokens
    compact_stem = re.sub(r"[^a-z0-9]+", "", stem)
    compact_kw = re.sub(r"[^a-z0-9]+", "", kw)
    return kw in stem or (compact_kw and compact_kw in compact_stem)


def rank_source_candidates(path: Path) -> list[tuple[str, int, str]]:
    """Rank source types for one user-selected file without importing it.

    This uses the same conservative filename/content signals as repository
    discovery.  The UI may auto-assign only a clearly better high-confidence
    result; otherwise the reviewer chooses the source type explicitly.
    """
    path = Path(path)
    if not path.exists() or not path.is_file():
        return []
    suffix = path.suffix.lower()
    keywords = load_source_detection_keywords()
    ranked: list[tuple[str, int, str]] = []
    for definition in SOURCE_DEFINITIONS:
        key = definition.key
        if suffix not in _source_extensions(key):
            continue
        exact = path.name.casefold() == definition.canonical_name.casefold()
        keyword_hit = any(_keyword_matches(path, kw) for kw in keywords.get(key, []))
        content_score, columns = _schema_content_score(key, path)
        detail = ("Matched columns: " + columns) if columns else ""
        score = content_score
        method_parts = []
        if exact:
            score = max(score, 100)
            method_parts.append("Recommended filename")
        if keyword_hit:
            # A keyword alone is only a hint.  For tabular sources it becomes
            # strong only when the schema also fits.
            if content_score >= 75:
                score = max(score, 82)
            method_parts.append("filename keyword")
        if content_score:
            method_parts.append("content/schema")
        if score > 0:
            explanation = " + ".join(method_parts) or detail or "Content signature"
            if detail and detail not in explanation:
                explanation = f"{explanation} · {detail}"
            ranked.append((key, int(score), explanation))
    ranked.sort(key=lambda item: (-item[1], SOURCE_BY_KEY[item[0]].label.casefold()))
    return ranked


def _is_explicit_version_family_candidate(path: Path, site_name: str) -> bool:
    """Return True for canonical source-family files carrying an explicit V suffix."""
    if not has_explicit_source_version(path):
        return False
    return any(_family_name_matches_source(path, key, site_name) for key in SOURCE_BY_KEY)


def discover_site_sources(site_dir: Path, *, deep: bool = True) -> tuple[dict[str, Path], dict[str, SourceDetection], tuple[Path, ...]]:
    """Discover source files for one site.

    ``deep=False`` is the fast navigation/startup path: it uses persisted manual
    assignments, the highest published V file, then the configured filename
    detection rules as an unversioned fallback.  It never opens CSV/XLSX
    contents. ``deep=True`` additionally discovers arbitrary filenames by their
    mapped/schema fields, so filenames are recommendations rather than contracts.
    """
    site_dir = Path(site_dir)
    site = site_dir.name
    files = _files_casefold(site_dir)
    # Read both legacy root-level sources and organized source_files. Output
    # folders are excluded by site_tabular_files.
    supported = list(site_tabular_files(site_dir))
    result: dict[str, Path] = {}
    detections: dict[str, SourceDetection] = {}
    used: set[Path] = set()

    def assign(key: str, path: Path, method: str, confidence: int = 100, detail: str = "") -> None:
        resolved = path.resolve()
        if key in result or resolved in used:
            return
        result[key] = path
        detections[key] = SourceDetection(path, method, int(confidence), detail)
        used.add(resolved)

    # 1) Explicit user mapping is authoritative.
    for key, filename in load_manual_source_assignments(site_dir).items():
        candidate = files.get(str(filename).casefold())
        if key in SOURCE_BY_KEY and candidate and candidate.suffix.lower() in _source_extensions(key):
            assign(key, candidate, "Manual", 100, "User-assigned source file")

    # 2) AUTO first chooses the highest semantic published V version.
    for definition in SOURCE_DEFINITIONS:
        key = definition.key
        if key in result:
            continue
        versions = source_version_candidates(site_dir, key)
        if versions:
            chosen = versions[0]
            assign(
                key, chosen, "Auto Latest Version", 100,
                f"Highest published explicit version: {source_file_version_label(chosen)}",
            )

    # 3) If no published V exists for a logical source, fall back to the user's
    # Source Detection Rules / canonical base filename.  This is the behavior
    # used by legacy site folders containing ADMS-DB.csv, ADMS-SLD.csv, etc.
    # A malformed V-looking filename (for example -VX) is never auto-selected.
    for definition in SOURCE_DEFINITIONS:
        key = definition.key
        if key in result:
            continue
        fallback = _rule_fallback_candidates(site_dir, key, used)
        if not fallback:
            continue
        # In the fast path accept only a unique rule match, or a canonical
        # filename-family match.  Deep refresh can resolve other ambiguity using
        # schema/content below.
        canonical = [p for p in fallback if _family_name_matches_source(p, key, site)]
        if has_explicit_source_version(fallback[0]):
            # Non-canonical files identified by a configured filename rule still
            # obey semantic version priority: V3 > V2.9 > V1.
            chosen = fallback[0]
        elif canonical:
            # CSV/XLSX/XLSM are equivalent physical containers. When a site
            # replaces ZENON-SLD.csv with ZENON-SLD.xlsx (or keeps both during
            # transition), AUTO follows the newest canonical-family file instead
            # of declaring the role ambiguous. A deliberate explicit pin still
            # wins later in selected_repository_source_path().
            chosen = max(
                canonical,
                key=lambda p: (p.stat().st_mtime_ns if p.exists() else 0, p.name.casefold()),
            )
        elif len(fallback) == 1:
            chosen = fallback[0]
        else:
            continue
        method = "Auto Detection Rule"
        if has_explicit_source_version(chosen):
            detail = f"Highest rule-matched published version: {source_file_version_label(chosen)}"
        elif _family_name_matches_source(chosen, key, site):
            detail = "Canonical/base filename matched Source Detection Rule"
        else:
            detail = "Configured Source Detection Rule fallback"
        assign(key, chosen, method, 92, detail)

    # Fast startup/site-navigation intentionally stops here.  It has already
    # resolved strict latest V files and unversioned rule fallbacks without
    # opening source contents.  Explicit Refresh Sources performs the deeper
    # schema/content pass for unresolved non-standard filenames.
    if not deep:
        version_family_paths: set[Path] = set()
        for key in result:
            for candidate in source_version_candidates(site_dir, key):
                try:
                    version_family_paths.add(candidate.resolve())
                except OSError:
                    pass
        unmapped = tuple(sorted(
            (p for p in supported if p.resolve() not in used and p.resolve() not in version_family_paths),
            key=lambda p: p.name.casefold(),
        ))
        return result, detections, unmapped

    # 4) Configurable filename keywords. Verify tabular candidates by schema.
    keywords = load_source_detection_keywords()
    for key in (d.key for d in SOURCE_DEFINITIONS):
        if key in result:
            continue
        possible = []
        for candidate in supported:
            if candidate.resolve() in used or candidate.suffix.lower() not in _source_extensions(key):
                continue
            # Published V files remain preferred, but when none was resolved
            # above the configured filename rules may identify an unversioned
            # base file.  Malformed V-looking suffixes stay AUTO-ineligible.
            if _has_unparsable_version_suffix(candidate):
                continue
            if _is_explicit_version_family_candidate(candidate, site):
                continue
            if not any(_keyword_matches(candidate, kw) for kw in keywords.get(key, [])):
                continue
            content_score, columns = _schema_content_score(key, candidate)
            if content_score < 75:
                continue
            score = max(82, content_score)
            detail = "Filename keyword + schema: " + columns
            possible.append((score, candidate, detail))
        possible.sort(key=lambda item: (-item[0], item[1].name.casefold()))
        if len(possible) == 1 or (possible and (len(possible) == 1 or possible[0][0] - possible[1][0] >= 8)):
            score, candidate, detail = possible[0]
            assign(key, candidate, "Filename Rule", score, detail)

    # 5) Content/schema discovery. Build proposals and accept only high-confidence,
    # uniquely better matches so an unrelated report workbook stays unmapped.
    proposals = []
    unresolved_keys = [d.key for d in SOURCE_DEFINITIONS if d.key not in result]
    for candidate in supported:
        if candidate.resolve() in used:
            continue
        if _has_unparsable_version_suffix(candidate):
            continue
        if _is_explicit_version_family_candidate(candidate, site):
            continue
        candidate_scores = []
        for key in unresolved_keys:
            if candidate.suffix.lower() not in _source_extensions(key):
                continue
            score, detail = _schema_content_score(key, candidate)
            if score:
                candidate_scores.append((score, key, detail))
        candidate_scores.sort(reverse=True)
        if not candidate_scores:
            continue
        best_score, best_key, detail = candidate_scores[0]
        second_score = candidate_scores[1][0] if len(candidate_scores) > 1 else 0
        if best_score >= 75 and best_score - second_score >= 8:
            proposals.append((best_score, best_key, candidate, detail))
    proposals.sort(key=lambda item: (-item[0], item[2].name.casefold()))
    for score, key, candidate, detail in proposals:
        if key not in result and candidate.resolve() not in used:
            assign(key, candidate, "Content", score, "Matched columns: " + detail if detail else "Content signature")

    # Older/newer siblings of a recognized logical source are legitimate version
    # candidates, not "unmapped" files.  They remain available in the Active File
    # selector while only one version is fed into validation at a time.
    version_family_paths: set[Path] = set()
    for key in result:
        for candidate in source_version_candidates(site_dir, key):
            try:
                version_family_paths.add(candidate.resolve())
            except OSError:
                pass
    unmapped = tuple(sorted(
        (p for p in supported if p.resolve() not in used and p.resolve() not in version_family_paths),
        key=lambda p: p.name.casefold(),
    ))
    return result, detections, unmapped


def resolve_site_sources(site_dir: Path) -> dict[str, Path]:
    """Compatibility API returning only resolved source paths."""
    return discover_site_sources(site_dir)[0]


@dataclass
class SiteInfo:
    name: str
    path: Path
    sources: dict[str, Path] = field(default_factory=dict)
    detections: dict[str, SourceDetection] = field(default_factory=dict)
    unmapped_files: tuple[Path, ...] = ()

    @property
    def missing_required(self) -> list[str]:
        return [d.key for d in SOURCE_DEFINITIONS if d.required and d.key not in self.sources]

    @property
    def ready(self) -> bool:
        return not self.missing_required


def scan_repository(root: Path, *, deep: bool = True) -> list[SiteInfo]:
    """Scan site folders.

    Use ``deep=False`` for startup/navigation so repository discovery is based
    on filenames only.  ``deep=True`` may inspect file contents and is therefore
    appropriate only for explicit refresh/validation actions.
    """
    root = Path(root)
    if not root.exists() or not root.is_dir():
        return []
    if is_unified_site_folder(root):
        sources, detections, unmapped = discover_site_sources(root, deep=deep)
        return [SiteInfo(root.name, root, sources, detections, unmapped)]
    sites = []
    for folder in sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))), key=lambda p: p.name.casefold()):
        sources, detections, unmapped = discover_site_sources(folder, deep=deep)
        sites.append(SiteInfo(folder.name, folder, sources, detections, unmapped))
    return sites


def selected_repository_source_path(site: SiteInfo, store: ProjectStore | None, source_type: str) -> Path | None:
    """Resolve a persistent version pin, rejecting stale cross-table selections.

    v0.8.59 briefly allowed schema-similar files from another source family to
    appear in the version picker.  A previously persisted bad pin such as
    ``zenon_sld -> ZENON-DB.csv`` must therefore be ignored as well as prevented
    in the new picker.
    """
    if store is None or not hasattr(store, "source_file_selection"):
        return None
    selection = store.source_file_selection(source_type)
    filename = str((selection or {}).get("file_name") or "").strip()
    if not filename:
        return None
    candidates = [
        path for path in site_tabular_files(site.path)
        if path.name.casefold() == Path(filename).name.casefold()
    ]
    if not candidates:
        return None
    # Prefer a root-level legacy file when both layouts temporarily coexist;
    # otherwise use the organized source_files copy.
    candidate = min(
        candidates,
        key=lambda path: (len(path.relative_to(site.path).parts), str(path).casefold()),
    )
    if candidate.suffix.lower() not in _source_extensions(source_type):
        return None
    # Explicit user selection is authoritative. The physical filename is not a
    # source contract; field mapping/schema determines the business meaning.
    # This deliberately permits names such as customer_final.xlsx.
    return candidate


def source_user_visible_name(site: SiteInfo, store: ProjectStore | None, source_type: str, path: Path | None = None) -> str:
    """Return the filename the reviewer actually supplied/selected.

    Workspace snapshots use timestamped internal filenames.  Those are an
    implementation detail and should never replace the reviewer's source name in
    the Site Data Sources UI.  Manual imports therefore expose their persisted
    ``original_name``; repository AUTO/PINNED files expose their real basename.
    """
    selected = selected_repository_source_path(site, store, source_type)
    if selected is not None:
        # Explicit version pin wins over any older manual workspace override.
        if path is None:
            return selected.name
        try:
            if Path(path).resolve() == selected.resolve():
                return selected.name
        except OSError:
            pass
    if store is not None and store.is_manual_source_override(source_type):
        record = store.manual_source_overrides().get(str(source_type), {}) or {}
        original = str(record.get("original_name") or "").strip()
        if original:
            return Path(original).name
    if path is not None:
        return Path(path).name
    if selected is not None:
        return selected.name
    auto = site.sources.get(source_type)
    return Path(auto).name if auto else "Not found"


def source_user_visible_path(site: SiteInfo, store: ProjectStore | None, source_type: str, path: Path | None = None) -> str:
    """Return the reviewer-facing full path for the active source file.

    Repository AUTO/PINNED sources expose their real site path. Manual imports
    expose the original external path when known, never the timestamped internal
    snapshot path. Older manual records that predate original-path persistence
    fall back to the currently readable path.
    """
    selected = selected_repository_source_path(site, store, source_type)
    if selected is not None:
        return str(selected.resolve())
    if store is not None and store.is_manual_source_override(source_type):
        record = store.manual_source_overrides().get(str(source_type), {}) or {}
        original_path = str(record.get("original_path") or "").strip()
        if original_path:
            return original_path
    if path is not None:
        return str(Path(path).resolve())
    auto = site.sources.get(source_type)
    return str(Path(auto).resolve()) if auto else ""


def effective_repository_sources(site: SiteInfo, store: ProjectStore | None = None) -> dict[str, Path]:
    """Return repository sources after applying per-project active-version selections."""
    result = dict(site.sources)
    if store is None:
        return result
    for definition in SOURCE_DEFINITIONS:
        selected = selected_repository_source_path(site, store, definition.key)
        if selected is not None:
            result[definition.key] = selected
    return result


def source_status(site: SiteInfo, store: ProjectStore | None = None, *, hash_contents: bool = True) -> dict[str, dict]:
    previous = {}
    manual_overrides: dict[str, dict] = {}
    if store and store.config.get("repository_site", "").casefold() == site.name.casefold():
        previous = store.config.get("repository_fingerprints", {}) or {}
        manual_overrides = store.manual_source_overrides()
    statuses: dict[str, dict] = {}
    for definition in SOURCE_DEFINITIONS:
        key = definition.key
        selected_path = selected_repository_source_path(site, store, key)
        if selected_path:
            statuses[key] = {
                "status": "SELECTED",
                "path": selected_path,
                "fingerprint": fingerprint(selected_path) if hash_contents else metadata_fingerprint(selected_path),
                "manual": True,
                "selected_version": True,
            }
            continue
        manual_path = store.source_path(key) if store and key in manual_overrides else None
        if manual_path:
            statuses[key] = {
                "status": "MANUAL",
                "path": manual_path,
                "fingerprint": fingerprint(manual_path) if hash_contents else metadata_fingerprint(manual_path),
                "manual": True,
            }
            continue
        path = site.sources.get(key)
        if not path:
            statuses[key] = {
                "status": "MISSING" if definition.required else "OPTIONAL",
                "path": None,
                "fingerprint": None,
                "manual": False,
            }
            continue
        fp = fingerprint(path) if hash_contents else metadata_fingerprint(path)
        old = previous.get(key)
        if not old:
            state = "NEW"
        elif hash_contents:
            state = "UPDATED" if old.get("sha256") != fp.get("sha256") else "CURRENT"
        else:
            # Navigation/startup uses only cheap metadata.  Exact content
            # comparison is performed by explicit Refresh Sources/Validation.
            state = "UPDATED" if (
                int(old.get("size") or -1) != int(fp.get("size") or -1)
                or int(old.get("mtime_ns") or -1) != int(fp.get("mtime_ns") or -1)
            ) else "CURRENT"
        statuses[key] = {"status": state, "path": path, "fingerprint": fp, "manual": False}
    return statuses


@dataclass(frozen=True)
class SiteSyncResult:
    snapshot_dir: Path
    imported: tuple[ImportResult, ...]
    changed_keys: tuple[str, ...]


def sync_site_to_project(
    store: ProjectStore, site: SiteInfo, *, force_all: bool = False, force_keys: Iterable[str] | None = None
) -> SiteSyncResult:
    """Snapshot repository sources while preserving explicit workspace overrides.

    Repository files remain read-only.  A source imported explicitly from
    ``Add Source Files`` stays authoritative until the reviewer replaces or
    clears that manual override; ordinary repository refreshes must not silently
    overwrite it.
    """
    store.config["project_name"] = site.name
    store.config["site_name"] = site.name
    store.config["repository_site"] = site.name
    store.config["repository_path"] = str(site.path.resolve())
    store.save_config()

    forced_keys = {str(key) for key in (force_keys or ()) if str(key)}
    manual_records = store.manual_source_overrides()
    manual_keys = {
        key for key in manual_records
        if store.source_path(key) is not None
    }

    # Explicitly imported files may live outside the site repository. Refresh
    # Sources / Run Validation must re-read that original external file when it
    # changes instead of treating the internal snapshot as the source of truth.
    manual_imported: list[ImportResult] = []
    manual_changed: list[str] = []
    for key in sorted(manual_keys):
        if selected_repository_source_path(site, store, key) is not None:
            continue
        record = manual_records.get(key, {}) or {}
        original_text = str(record.get("original_path") or "").strip()
        if not original_text:
            continue
        original = Path(original_text)
        if not original.exists() or not original.is_file():
            continue
        current = store.source_path(key)
        try:
            changed_external = (
                force_all or key in forced_keys or current is None or not current.exists()
                or fingerprint(original).get("sha256") != fingerprint(current).get("sha256")
            )
        except OSError:
            changed_external = True
        if changed_external:
            manual_imported.append(import_source(store, key, original))
            store.mark_manual_source_override(key, original)
            manual_changed.append(key)

    statuses = source_status(site, store)
    previous = store.config.get("repository_fingerprints", {}) or {}
    previous_keys = set(previous.keys())
    repository_sources = effective_repository_sources(site, store)
    repository_keys = set(repository_sources.keys())
    removed = sorted((previous_keys - repository_keys) - manual_keys)
    changed = list(removed) + list(manual_changed)
    for key, path in repository_sources.items():
        selected = selected_repository_source_path(site, store, key) is not None
        if key in manual_keys and not selected:
            continue
        fp = fingerprint(path)
        old = previous.get(key)
        if force_all or key in forced_keys or not old or old.get("sha256") != fp.get("sha256"):
            changed.append(key)

    # Repair an incomplete non-manual workspace even if the repository file
    # fingerprint itself is unchanged.
    for key, path in repository_sources.items():
        if key in manual_keys and selected_repository_source_path(site, store, key) is None:
            continue
        if not store.source_path(key) and key not in changed:
            changed.append(key)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    snapshot_dir = store.snapshots_dir / stamp
    imported: list[ImportResult] = list(manual_imported)
    if changed or not store.config.get("repository_last_sync"):
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        manifest = {
            "site": site.name,
            "repository_path": str(site.path.resolve()),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "sources": {},
            "manual_overrides": sorted(manual_keys),
        }
        for key, source in repository_sources.items():
            if key in manual_keys and selected_repository_source_path(site, store, key) is None:
                continue
            definition = SOURCE_BY_KEY[key]
            # Preserve the real physical container extension.  A workbook must
            # never be copied into a .csv snapshot name because downstream
            # readers select their parser from the suffix.  The logical source
            # role is carried by `key`; filenames are not the business contract.
            canonical_stem = Path(definition.canonical_name).stem
            source_suffix = source.suffix.lower() or Path(definition.canonical_name).suffix.lower()
            target = snapshot_dir / f"{canonical_stem}{source_suffix}"
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
        previous_snapshot = store.config.get("repository_last_snapshot", "")
        snapshot_dir = Path(previous_snapshot) if previous_snapshot else store.snapshots_dir

    current_fps = {
        key: fingerprint(path)
        for key, path in repository_sources.items()
        if key not in manual_keys or selected_repository_source_path(site, store, key) is not None
    }
    # Keep a cheap live-origin signature for startup/in-session change detection.
    # Repository and manual external files are both tracked; no workbook parsing
    # is required to decide whether a source needs to be re-read later.
    live_source_metadata: dict[str, dict] = {}
    for key, path in repository_sources.items():
        if key in manual_keys and selected_repository_source_path(site, store, key) is None:
            continue
        try:
            stat = Path(path).stat()
            live_source_metadata[key] = {
                "path": str(Path(path).resolve()),
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        except OSError:
            pass
    for key in manual_keys:
        if selected_repository_source_path(site, store, key) is not None:
            continue
        record = manual_records.get(key, {}) or {}
        original_text = str(record.get("original_path") or "").strip()
        if not original_text:
            continue
        original = Path(original_text)
        try:
            stat = original.stat()
            live_source_metadata[key] = {
                "path": str(original.resolve()),
                "size": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
            }
        except OSError:
            pass
    store.config["project_name"] = site.name
    store.config["site_name"] = site.name
    store.config["repository_site"] = site.name
    store.config["repository_path"] = str(site.path.resolve())
    store.config["repository_fingerprints"] = current_fps
    store.config["live_source_metadata"] = live_source_metadata
    store.config["repository_last_sync"] = datetime.now().isoformat(timespec="seconds")
    store.config["repository_last_snapshot"] = str(snapshot_dir)
    store.save_config()
    return SiteSyncResult(snapshot_dir=snapshot_dir, imported=tuple(imported), changed_keys=tuple(sorted(set(changed))))
