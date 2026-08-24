"""Calculated Signal Mapping Review engine.

Signal Mapping Review is application-owned data.  It is **not** read from the
legacy DB-smart worksheet anymore.

Inputs:
* ZENON-ADMS-IOA.csv: RMU + Zenon/ADMS signal mapping rows;
* ADMS-SLD.csv: cabinet type for each RMU;
* active application IOA STANDARD.xlsx: STANDARD reference worksheet (user override or bundled default).

STANDARD is intentionally treated as a reference dictionary. Only the
``Type``, ``IOA`` and ``name`` columns are used. ADMS/STANDARD validation is
primarily value-based: a normalized ADMS signal name plus ADMS point number
matching a STANDARD name plus IOA is sufficient for TRUE. RMU Type remains
supporting lookup/context so the UI can show the expected STANDARD row when an
exact name+IOA match is not available.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1, sha256
from pathlib import Path
import re
from typing import Iterable

from openpyxl import load_workbook

from ..analysis.consistency import normalize_type
from ...parsers import clean, normalize_key
from ...infrastructure.parsers import read_mapped_rows
from ...utils.paths import standard_reference_path


@dataclass(frozen=True)
class DBSmartRow:
    excel_row: int
    row_key: str
    rmu: str
    values: tuple[str, ...]
    analysis_detail: str = ""


@dataclass(frozen=True)
class DBSmartReport:
    source_path: Path
    sheet_name: str
    source_hash: str
    group_definitions: tuple[tuple[str, str, tuple[tuple[str, str, int], ...]], ...]
    columns: tuple[tuple[str, str, int], ...]
    rows: tuple[DBSmartRow, ...]
    analysis_column: int | None
    input_paths: tuple[Path, ...] = ()


SIGNAL_MAPPING_GROUPS = (
    ("RMU", "#E5E7EB", (
        ("rmu_no", "RMU", 105),
        ("rmu_type", "Type", 90),
    )),
    ("ZENON", "#E5E7EB", (
        ("zenon_gss_fid", "ZENON GSS-FID", 200),
        ("zenon_signal_name", "ZENON signal name", 260),
        ("zenon_dot_no", "ZENON DOT NO", 120),
    )),
    ("ADMS", "#E5E7EB", (
        ("adms_gss_fid", "ADMS GSS-FID", 200),
        ("adms_signal_name", "ADMS signal name", 270),
        ("adms_dot_no", "ADMS DOT NO", 120),
    )),
    ("STANDARD DATABASE I/O list", "#E5E7EB", (
        ("standard_signal_name", "STANDARD signal name", 250),
        ("standard_dot_no", "STANDARD DOT NO", 135),
    )),
    ("Analysis", "#E5E7EB", (
        ("analysis_adms_standard", "ADMS/STANDARD", 125),
    )),
    ("Comparison Summary", "#E5E7EB", (
        ("summary_item", "Item", 140),
        ("summary_adms_standard", "ADMS/STANDARD", 130),
        ("summary_zenon_standard", "ZENON/STANDARD", 130),
    )),
)
SIGNAL_MAPPING_COLUMNS = tuple(
    column for _group, _color, columns in SIGNAL_MAPPING_GROUPS for column in columns
)
ANALYSIS_COLUMN = next(
    i for i, (key, _label, _width) in enumerate(SIGNAL_MAPPING_COLUMNS)
    if key == "analysis_adms_standard"
)


def _file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _combined_hash(paths: Iterable[Path]) -> str:
    digest = sha256()
    for path in paths:
        path = Path(path)
        digest.update(path.name.encode("utf-8", errors="replace"))
        digest.update(_file_sha256(path).encode("ascii"))
    return digest.hexdigest()


def _norm_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(value).casefold())


def _norm_type_key(value: object) -> str:
    # STANDARD Type is a business key, not free text. Keep extended types such
    # as "3L1T-MRMU (...)" distinct from the base "3L1T" so Type+IOA remains
    # a deterministic unique lookup as required by the report contract.
    return re.sub(r"\s+", " ", clean(value).strip().upper())


def _norm_ioa(value: object) -> str:
    text = clean(value)
    if not text:
        return ""
    # Excel/CSV frequently represents integer IOAs as 1000.0.
    try:
        number = float(text.replace(",", ""))
        if number.is_integer():
            return str(int(number))
    except Exception:
        pass
    return text.upper()


def _display_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _strip_rmu_prefix(signal: object, rmu: object) -> str:
    text = clean(signal).strip()
    rmu_text = normalize_key(rmu).strip()
    if not text:
        return ""
    if rmu_text:
        # ADMS examples: "26859 Y1 CMD".  Remove only a true leading RMU token.
        text = re.sub(rf"^\s*{re.escape(rmu_text)}(?:\s+|[_-]+)", "", text, flags=re.I)
    return text.strip()


def normalize_signal_name(value: object, *, strip_rmu: object = "") -> str:
    """Normalize signal text using the legacy report's proven comparison rules."""
    text = _strip_rmu_prefix(value, strip_rmu) if strip_rmu else clean(value)
    text = text.casefold().replace(" ", "").replace("_", "")
    replacements = (
        ("iavalue(a)", "icurrent(a)"),
        ("ibvalue(a)", "icurrent(b)"),
        ("icvalue(a)", "icurrent(c)"),
        ("invalue(a)", "icurrent(n)"),
        ("uabvalue(kv)", "vvoltage(a-b)"),
        ("ubcvalue(kv)", "vvoltage(b-c)"),
        ("ucavalue(kv)", "vvoltage(c-a)"),
        ("unvalue(kv)", "vvoltage(n)"),
        ("value", ""),
        ("state", ""),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _find_standard_sheet(wb):
    for name in wb.sheetnames:
        if name.strip().casefold() == "standard":
            return wb[name]
    raise ValueError("STANDARD sheet not found in the active IOA STANDARD workbook.")


def _standard_header_columns(ws) -> tuple[int, int, int, int]:
    """Return (header_row, type_col, ioa_col, name_col)."""
    for row_idx in range(1, min(ws.max_row, 25) + 1):
        found: dict[str, int] = {}
        for col_idx in range(1, ws.max_column + 1):
            key = _norm_header(ws.cell(row_idx, col_idx).value)
            if key == "type" and "type" not in found:
                found["type"] = col_idx
            elif key == "ioa" and "ioa" not in found:
                found["ioa"] = col_idx
            elif key == "name" and "name" not in found:
                found["name"] = col_idx
        if {"type", "ioa", "name"} <= set(found):
            return row_idx, found["type"], found["ioa"], found["name"]
    raise ValueError("STANDARD must contain columns named Type, IOA and name.")


def _read_standard_index(path: Path, overrides: dict[str, str] | None = None):
    """Return STANDARD indexes for exact value matching and type-assisted lookup.

    ``by_ioa`` intentionally contains rows across all RMU types. This lets the
    validation rule accept an ADMS signal when *name + DOT/IOA* exactly matches
    the STANDARD reference even if the ADMS-SLD Type is missing or different.
    ``by_type_ioa`` is retained as supporting context/fallback for explaining
    mismatches and selecting the expected STANDARD row.
    """
    mapped = read_mapped_rows("standard_reference", path, overrides or {}, strict=True)
    by_type_ioa: dict[tuple[str, str], list[dict[str, str]]] = {}
    by_ioa: dict[str, list[dict[str, str]]] = {}
    for row_number, row in enumerate(mapped.rows, 1):
        type_value = _norm_type_key(row.get("type"))
        ioa_value = _norm_ioa(row.get("ioa"))
        name_value = _display_value(row.get("name"))
        if not ioa_value:
            continue
        item = {
            "type": type_value, "ioa": ioa_value, "name": name_value, "row": str(row_number),
        }
        by_ioa.setdefault(ioa_value, []).append(item)
        if type_value:
            by_type_ioa.setdefault((type_value, ioa_value), []).append(item)
    return by_type_ioa, by_ioa


def _first_value(row: dict, *keys: str) -> str:
    # First exact lookup, then case/character-insensitive lookup for site variants.
    for key in keys:
        if clean(row.get(key)):
            return clean(row.get(key))
    normalized = {_norm_header(k): clean(v) for k, v in row.items() if clean(v)}
    for key in keys:
        hit = normalized.get(_norm_header(key))
        if hit:
            return hit
    return ""


def _read_adms_sld_types(path: Path, overrides: dict[str, str] | None = None):
    rows = read_mapped_rows("adms_sld", path, overrides or {}, strict=True).rows
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        rmu = normalize_key(row.get("rmu"))
        if rmu:
            grouped.setdefault(rmu, []).append(row)

    result: dict[str, tuple[str, str]] = {}
    for rmu, candidates in grouped.items():
        types = {normalize_type(row.get("rmu_type")) for row in candidates}
        types.discard("")
        if len(types) == 1:
            result[rmu] = (next(iter(types)), "")
        elif len(types) > 1:
            result[rmu] = ("", f"ADMS SLD has conflicting RMU types: {', '.join(sorted(types))}")
        else:
            result[rmu] = ("", "ADMS SLD RMU type is blank")
    return result


def _row_key(source: dict, row_number: int) -> str:
    identity = [
        normalize_key(source.get("rmu")),
        clean(source.get("zenon_gss_fid")),
        clean(source.get("zenon_signal_name")),
        _norm_ioa(source.get("zenon_dot_no")),
        clean(source.get("adms_gss_fid")),
        clean(source.get("adms_signal_name")),
        _norm_ioa(source.get("adms_dot_no")),
    ]
    payload = "\x1f".join(x.casefold() for x in identity)
    if not payload.strip("\x1f"):
        payload = f"row:{row_number}"
    return sha1(payload.encode("utf-8", errors="replace")).hexdigest()


def _analysis_for_row(
    *, rmu: str, rmu_type: str, type_reason: str, adms_signal: str,
    adms_dot: str, type_candidates: list[dict[str, str]],
    ioa_candidates: list[dict[str, str]],
) -> tuple[str, str, str, str]:
    """Return analysis, STANDARD name/DOT and human-readable reason.

    Business rule:
      ADMS signal name + ADMS DOT number == STANDARD name + IOA  -> TRUE

    RMU Type is supporting context only. It is used to choose the most useful
    STANDARD row for mismatch explanation, but a Type mismatch must not turn an
    otherwise exact name+DOT match into FALSE.
    """
    if not adms_dot and not clean(adms_signal):
        return "", "", "", "ADMS signal and ADMS point number are blank; no STANDARD check was performed."
    if not adms_dot:
        return "FALSE", "", "", f"ADMS_DOT_NO is blank for RMU {rmu or '—'}; signal name + DOT are required for STANDARD validation."

    adms_norm = normalize_signal_name(adms_signal, strip_rmu=rmu)
    ioa_norm = _norm_ioa(adms_dot)

    # Primary rule: name + DOT/IOA equality is sufficient, across RMU types.
    exact_value_matches = [
        item for item in ioa_candidates
        if adms_norm
        and normalize_signal_name(item.get("name"))
        and normalize_signal_name(item.get("name")) == adms_norm
        and _norm_ioa(item.get("ioa")) == ioa_norm
    ]
    if exact_value_matches:
        # Prefer the same Type for presentation when one exists, but do not
        # require Type equality for the TRUE result.
        same_type = [item for item in exact_value_matches if rmu_type and item.get("type") == _norm_type_key(rmu_type)]
        standard = (same_type or exact_value_matches)[0]
        standard_name = clean(standard.get("name"))
        standard_dot = _norm_ioa(standard.get("ioa"))
        detail = [
            "ADMS/STANDARD consistency check",
            "",
            "Rule: normalized ADMS signal name + ADMS DOT number must match STANDARD name + IOA.",
            "RMU Type is supporting context and is not required when name + DOT already match.",
            "",
            f"RMU: {rmu or '—'}",
            f"Type (from ADMS SLD): {rmu_type or '<missing>'}",
            f"STANDARD Type: {standard.get('type') or '<blank>'}",
            f"ADMS_DOT_NO: {adms_dot}",
            f"STANDARD IOA: {standard_dot}",
            f"ADMS signal: {adms_signal or '<blank>'}",
            f"STANDARD name: {standard_name}",
            "",
            f"Normalized ADMS signal: {adms_norm or '<blank>'}",
            f"Normalized STANDARD name: {normalize_signal_name(standard_name) or '<blank>'}",
            "",
            "Result: TRUE",
            "Reason: ADMS signal name and DOT number match the STANDARD reference.",
        ]
        return "TRUE", standard_name, standard_dot, "\n".join(detail)

    # No exact name+DOT match. Use Type+IOA (when available) to show the
    # expected STANDARD row and explain the mismatch. If Type is unavailable or
    # wrong, a unique IOA row can still provide useful context.
    candidates = list(type_candidates)
    lookup_reason = "Type + IOA"
    if not candidates:
        candidates = list(ioa_candidates)
        lookup_reason = "IOA"

    if not candidates:
        type_text = rmu_type or "<missing>"
        return "FALSE", "", "", (
            f"STANDARD mapping not found for ADMS signal={adms_signal or '<blank>'}, "
            f"IOA={adms_dot}, Type={type_text}. No STANDARD row has the same DOT number."
        )

    # If several candidates share the IOA, choose a same-Type candidate first
    # for display. Multiple rows are not an automatic failure anymore because
    # the business truth condition is name+DOT; at this point none matched the
    # ADMS signal name, so the result is FALSE regardless.
    same_type = [item for item in candidates if rmu_type and item.get("type") == _norm_type_key(rmu_type)]
    standard = (same_type or candidates)[0]
    standard_name = clean(standard.get("name"))
    standard_dot = _norm_ioa(standard.get("ioa"))
    standard_norm = normalize_signal_name(standard_name)
    dot_match = ioa_norm == standard_dot
    name_match = bool(adms_norm and standard_norm and adms_norm == standard_norm)

    detail = [
        "ADMS/STANDARD consistency check",
        "",
        "Rule: normalized ADMS signal name + ADMS DOT number must match STANDARD name + IOA.",
        "RMU Type is supporting context only.",
        "",
        f"RMU: {rmu or '—'}",
        f"Type (from ADMS SLD): {rmu_type or '<missing>'}",
        f"STANDARD Type: {standard.get('type') or '<blank>'}",
        f"Fallback lookup: {lookup_reason}",
        f"ADMS_DOT_NO: {adms_dot}",
        f"STANDARD IOA: {standard_dot}",
        f"ADMS signal: {adms_signal or '<blank>'}",
        f"STANDARD name: {standard_name or '<blank>'}",
        "",
        f"Normalized ADMS signal: {adms_norm or '<blank>'}",
        f"Normalized STANDARD name: {standard_norm or '<blank>'}",
        "",
        "Result: FALSE",
    ]
    problems = []
    if not name_match:
        problems.append("signal name mismatch")
    if not dot_match:
        problems.append("point number mismatch")
    if not problems:
        # Defensive only: exact name+DOT would already have returned TRUE.
        problems.append("STANDARD value mismatch")
    detail.append("Reason: " + " / ".join(problems))
    if type_reason:
        detail.append("Type context: " + type_reason)
    return "FALSE", standard_name, standard_dot, "\n".join(detail)


def _zenon_standard_match(rmu: str, zenon_signal: str, zenon_dot: str, standard_name: str, standard_dot: str) -> bool | None:
    """Best-effort secondary summary without changing the detail-sheet contract."""
    if not (clean(zenon_signal) or clean(zenon_dot)):
        return None
    if not (standard_name and standard_dot):
        return False
    # Point number is authoritative; signal comparison is best effort because
    # Zenon symbolic names contain driver/RMU technical tokens.
    return _norm_ioa(zenon_dot) == _norm_ioa(standard_dot)


def build_signal_mapping_report(ioa_path: Path, adms_sld_path: Path, standard_workbook_path: Path, *, ioa_overrides: dict[str, str] | None = None, adms_sld_overrides: dict[str, str] | None = None, standard_overrides: dict[str, str] | None = None) -> DBSmartReport:
    ioa_path = Path(ioa_path)
    adms_sld_path = Path(adms_sld_path)
    standard_workbook_path = Path(standard_workbook_path)
    for path, label in (
        (ioa_path, "ZENON-ADMS-IOA.csv"),
        (adms_sld_path, "ADMS-SLD.csv"),
        (standard_workbook_path, "active IOA STANDARD.xlsx"),
    ):
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    ioa_rows = read_mapped_rows("ioa", ioa_path, ioa_overrides or {}, strict=True).rows
    adms_types = _read_adms_sld_types(adms_sld_path, adms_sld_overrides)
    standard_type_index, standard_ioa_index = _read_standard_index(standard_workbook_path, standard_overrides)

    detail_rows: list[dict] = []
    adms_results: list[bool] = []
    zenon_results: list[bool] = []
    seen: dict[str, int] = {}

    for source_row_number, source in enumerate(ioa_rows, 2):
        rmu = normalize_key(source.get("rmu"))
        rmu_type, type_reason = adms_types.get(rmu, ("", f"RMU {rmu or '—'} was not found in ADMS SLD."))
        zenon_gss = clean(source.get("zenon_gss_fid"))
        zenon_signal = clean(source.get("zenon_signal_name"))
        zenon_dot = _norm_ioa(source.get("zenon_dot_no"))
        adms_gss = clean(source.get("adms_gss_fid"))
        adms_signal = clean(source.get("adms_signal_name"))
        adms_dot = _norm_ioa(source.get("adms_dot_no"))
        type_candidates = standard_type_index.get((_norm_type_key(rmu_type), adms_dot), []) if rmu_type and adms_dot else []
        ioa_candidates = standard_ioa_index.get(adms_dot, []) if adms_dot else []
        analysis, standard_name, standard_dot, analysis_detail = _analysis_for_row(
            rmu=rmu, rmu_type=rmu_type, type_reason=type_reason,
            adms_signal=adms_signal, adms_dot=adms_dot,
            type_candidates=type_candidates,
            ioa_candidates=ioa_candidates,
        )
        if analysis in {"TRUE", "FALSE"}:
            adms_results.append(analysis == "TRUE")
        zmatch = _zenon_standard_match(rmu, zenon_signal, zenon_dot, standard_name, standard_dot)
        if zmatch is not None:
            zenon_results.append(bool(zmatch))

        base_key = _row_key(source, source_row_number)
        occurrence = seen.get(base_key, 0)
        seen[base_key] = occurrence + 1
        row_key = base_key if occurrence == 0 else f"{base_key}:{occurrence + 1}"
        detail_rows.append({
            "source_row_number": source_row_number,
            "row_key": row_key,
            "rmu": rmu,
            "analysis_detail": analysis_detail,
            "values": [
                rmu, rmu_type,
                zenon_gss, zenon_signal, zenon_dot,
                adms_gss, adms_signal, adms_dot,
                standard_name, standard_dot,
                analysis,
            ],
        })

    def summary(results: list[bool]):
        matched = sum(1 for x in results if x)
        mismatched = sum(1 for x in results if not x)
        total = len(results)
        return [matched, mismatched, total, (matched / total if total else None), (mismatched / total if total else None)]

    adms_summary = summary(adms_results)
    zenon_summary = summary(zenon_results)
    items = ["Matched", "Mismatched", "Total Checked", "Match Rate", "Mismatch Rate"]

    rows: list[DBSmartRow] = []
    for index, item in enumerate(detail_rows):
        values = list(item["values"])
        if index < len(items):
            def fmt(v):
                if v is None:
                    return ""
                if isinstance(v, float):
                    return f"{v:.2%}"
                return str(v)
            values.extend([items[index], fmt(adms_summary[index]), fmt(zenon_summary[index])])
        else:
            values.extend(["", "", ""])
        rows.append(DBSmartRow(
            excel_row=item["source_row_number"],
            row_key=item["row_key"],
            rmu=item["rmu"],
            values=tuple(values),
            analysis_detail=item["analysis_detail"],
        ))

    inputs = (ioa_path.resolve(), adms_sld_path.resolve(), standard_workbook_path.resolve())
    return DBSmartReport(
        source_path=ioa_path.resolve(),
        sheet_name="Calculated · IOA + ADMS SLD + STANDARD",
        source_hash=_combined_hash(inputs),
        group_definitions=SIGNAL_MAPPING_GROUPS,
        columns=SIGNAL_MAPPING_COLUMNS,
        rows=tuple(rows),
        analysis_column=ANALYSIS_COLUMN,
        input_paths=inputs,
    )


def build_signal_mapping_report_from_store(store) -> DBSmartReport:
    ioa = store.source_path("ioa")
    adms_sld = store.source_path("adms_sld")
    standard = standard_reference_path()
    missing = []
    if not ioa:
        missing.append("ZENON-ADMS-IOA.csv")
    if not adms_sld:
        missing.append("ADMS-SLD.csv")
    if not standard.exists():
        missing.append("active IOA STANDARD.xlsx")
    if missing:
        raise FileNotFoundError("Signal Mapping Review requires: " + ", ".join(missing))
    return build_signal_mapping_report(
        ioa, adms_sld, standard,
        ioa_overrides=store.source_column_overrides("ioa"),
        adms_sld_overrides=store.source_column_overrides("adms_sld"),
        standard_overrides=store.source_column_overrides("standard_reference"),
    )


# Compatibility aliases for older plugins/tests.  Legacy DB-smart worksheet
# discovery is no longer used by the application.
def find_db_smart_sheet(sheet_names: Iterable[str]) -> str | None:
    return None


def read_db_smart_report(path: Path) -> DBSmartReport:  # pragma: no cover - explicit migration guard
    raise RuntimeError(
        "Signal Mapping Review is calculated from ZENON-ADMS-IOA.csv + ADMS-SLD.csv + the active application IOA STANDARD.xlsx; "
        "the legacy DB-smart worksheet is no longer a source."
    )
