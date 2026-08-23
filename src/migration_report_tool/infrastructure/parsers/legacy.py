"""File and zenOn XML parsers. No UI dependencies.

The zenOn XML parser is site-aware. A combined XML may contain graphics from
multiple sites (for example ABN and ABN2); callers can pass ``site_name`` and
optional SE feeder values so only the selected site's feeder records are kept.
"""
from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook


def normalize_key(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def direct_child_text(elem: ET.Element, child_name: str) -> str:
    for child in elem:
        if local_name(child.tag) == child_name:
            return (child.text or "").strip()
    return ""


CABINET_TYPE_RE = re.compile(r"(?<![A-Za-z0-9])(\d+L(?:\d+T)?)(?![A-Za-z0-9])", re.I)
FEEDER_TOKEN_RE = re.compile(r"[A-Z0-9]+", re.I)


def parse_destination(value: str) -> tuple[str, str, str]:
    """Parse SubstituteDestination using the proven RMU extraction rule.

    Any zenOn project/driver prefix before the final ``#`` is ignored. The last
    hyphen-delimited token is the RMU and everything before it is the feeder.
    """
    value = clean(value)
    if not value:
        return "", "", ""
    normalized = value.rsplit("#", 1)[-1].strip()
    if "-" not in normalized:
        return normalized, "", ""
    feeder, rmu = normalized.rsplit("-", 1)
    return normalized, feeder.strip(), rmu.strip()


def _feeder_tokens(value: str) -> list[str]:
    return [x.upper() for x in FEEDER_TOKEN_RE.findall(clean(value))]


def normalize_feeder(value: str) -> str:
    """Normalize feeder text without losing token boundaries."""
    return "-".join(_feeder_tokens(value))


def feeder_matches_site(feeder: str, site_name: str | None, allowed_feeders: Iterable[str] | None = None) -> bool:
    """Return whether a feeder belongs to the selected site.

    Matching is deliberately token-aware: site ``ABN`` does **not** match token
    ``ABN2``. This is important for combined files such as ABN-ABN2.XML.

    SE feeder values are an additional positive signal. A short SE feeder like
    ``ABN2-16`` matches ``JED-NTH-ABN2-16`` by suffix, which also supports sites
    whose repository folder name is not identical to the feeder token.
    """
    if not site_name:
        return True
    feeder_norm = normalize_feeder(feeder)
    if not feeder_norm:
        return False

    feeder_tokens = feeder_norm.split("-")
    site_tokens = _feeder_tokens(site_name)
    if site_tokens:
        # Exact contiguous token sequence. ABN can never match ABN2.
        n = len(site_tokens)
        for i in range(0, len(feeder_tokens) - n + 1):
            if feeder_tokens[i:i+n] == site_tokens:
                return True

    for candidate in allowed_feeders or ():
        candidate_norm = normalize_feeder(candidate)
        if not candidate_norm:
            continue
        if feeder_norm == candidate_norm or feeder_norm.endswith("-" + candidate_norm):
            return True
    return False


def parse_zenon_xml(
    xml_path: Path,
    site_name: str | None = None,
    allowed_feeders: Iterable[str] | None = None,
) -> list[dict]:
    """Extract one record per logical RMU from zenOn XML.

    ``Picture/@ShortName`` maps to DATA ``Screen name``. If ``site_name`` is
    supplied, records are filtered by the parsed feeder before deduplication.
    This prevents a shared ABN-ABN2.XML from leaking ABN RMUs into an ABN2 run.
    """
    allowed_feeders = tuple(clean(x) for x in (allowed_feeders or ()) if clean(x))
    raw: list[dict] = []
    current_picture = ""
    inside_element = 0
    context = ET.iterparse(str(xml_path), events=("start", "end"))
    for event, elem in context:
        tag = local_name(elem.tag)
        if event == "start":
            if tag == "Picture":
                current_picture = clean(elem.attrib.get("ShortName"))
            if tag.startswith("Elements_"):
                inside_element += 1
            continue

        if tag.startswith("Elements_"):
            link_name = direct_child_text(elem, "LinkName")
            destination = direct_child_text(elem, "SubstituteDestination")
            if link_name and "RMU" in link_name.upper() and destination:
                normalized, feeder, rmu = parse_destination(destination)
                # Site filtering is based on feeder, not Picture name. Combined
                # zenOn exports can contain cross-site graphics under one Picture.
                if site_name and not feeder_matches_site(feeder, site_name, allowed_feeders):
                    elem.clear()
                    inside_element = max(0, inside_element - 1)
                    continue
                match = CABINET_TYPE_RE.search(link_name)
                cabinet_type = match.group(1).upper() if match else ""
                warnings = []
                if not cabinet_type:
                    warnings.append("Cabinet type not parsed")
                if not feeder or not rmu:
                    warnings.append("SubstituteDestination not parsed")
                raw.append({
                    "xml_file": xml_path.name,
                    "screen_name": current_picture,
                    "picture": current_picture,  # legacy alias for older project data
                    "cabinet_type": cabinet_type,
                    "feeder": feeder,
                    "rmu": rmu,
                    "link_name": link_name,
                    "destination": destination,
                    "normalized_destination": normalized,
                    "warning": "; ".join(warnings),
                })
            elem.clear()
            inside_element = max(0, inside_element - 1)
        elif tag == "Picture":
            elem.clear()
            current_picture = ""
        elif inside_element == 0:
            elem.clear()

    grouped: dict[tuple[str, str, str], dict] = {}
    counts: Counter = Counter()
    for row in raw:
        key = (row["cabinet_type"], row["feeder"], row["rmu"])
        counts[key] += 1
        if key not in grouped:
            grouped[key] = row
        elif row["screen_name"] and row["screen_name"] not in grouped[key]["screen_name"].split("; "):
            grouped[key]["screen_name"] = "; ".join(x for x in [grouped[key]["screen_name"], row["screen_name"]] if x)
            grouped[key]["picture"] = grouped[key]["screen_name"]

    result = []
    for key, row in grouped.items():
        row = dict(row)
        row["duplicate_count"] = counts[key]
        if counts[key] > 1:
            row["warning"] = "; ".join(x for x in [row["warning"], f"Duplicate graphic x{counts[key]}"] if x)
        result.append(row)
    result.sort(key=lambda r: (normalize_feeder(r["feeder"]), normalize_key(r["rmu"]), r["cabinet_type"]))
    return result


def read_csv_rows(path: Path) -> list[dict]:
    raw = path.read_bytes()
    text = None
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "latin1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if text is None:
        raise ValueError(f"Unable to decode {path.name}")
    return list(csv.DictReader(text.splitlines()))


def read_excel_rows(path: Path) -> list[dict]:
    """Read the active worksheet and release the workbook deterministically.

    ``read_only=True`` keeps the XLSX zip archive open while rows are streamed.
    On Windows that handle prevents ``TemporaryDirectory`` / project cleanup
    from deleting an imported workbook until ``Workbook.close()`` is called.
    Always close in ``finally`` so normal returns, empty workbooks and parser
    exceptions all release the file immediately.
    """
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        try:
            headers = [clean(x) for x in next(rows)]
        except StopIteration:
            return []
        result = []
        for values in rows:
            if not any(v is not None and clean(v) for v in values):
                continue
            result.append({headers[i]: values[i] if i < len(values) else None for i in range(len(headers))})
        return result
    finally:
        wb.close()
