"""Explicit Site Repository regeneration of derived ZENON-SLD.csv."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from uuid import uuid4

from ..infrastructure.parsers import read_mapped_rows
from ..parsers import parse_zenon_xml
from .rmu_review_service import write_zenon_sld_csv_path


@dataclass(frozen=True)
class ZenonSldRegenerationResult:
    xml_path: Path
    target_path: Path
    row_count: int


def regenerate_site_zenon_sld(site, store) -> ZenonSldRegenerationResult:
    """Regenerate ``<site>/ZENON-SLD.csv`` from the site's live zenOn XML.

    XML is the source of truth. The old CSV is left untouched until a complete
    non-empty replacement has been written successfully beside it; ``os.replace``
    then performs the final replacement. A zero-row parse is treated as an error
    specifically to prevent a valid existing CSV from being destroyed by a
    wrong site/XML selection.
    """
    if site is None:
        raise ValueError("Select a site first.")
    xml_value = site.sources.get("zenon_xml")
    if not xml_value:
        raise FileNotFoundError("ZENON XML was not found for the selected site.")
    xml_path = Path(xml_value)
    if not xml_path.exists():
        raise FileNotFoundError("ZENON XML was not found for the selected site.")

    se_feeders: list[str] = []
    se_path = site.sources.get("se_list")
    if se_path and Path(se_path).exists():
        try:
            overrides = store.source_column_overrides("se_list") if store else {}
            se_rows = read_mapped_rows("se_list", Path(se_path), overrides, strict=True).rows
            se_feeders = [str(row.get("feeder") or "").strip() for row in se_rows]
            se_feeders = [value for value in se_feeders if value]
        except Exception:
            # Site-token filtering remains deterministic even when the optional
            # extra feeder hints cannot be read.
            se_feeders = []

    rows = parse_zenon_xml(xml_path, site_name=str(site.name).strip() or None, allowed_feeders=se_feeders)
    if not rows:
        raise ValueError(
            "No RMU records were generated from the selected XML. Existing ZENON-SLD.csv was not changed."
        )

    target = Path(site.path) / "ZENON-SLD.csv"
    temp = target.with_name(f".{target.stem}.{uuid4().hex}.tmp.csv")
    try:
        write_zenon_sld_csv_path(temp, xml_path, rows)
        # Basic post-write guard before replacing the user's derived file.
        if not temp.exists() or temp.stat().st_size <= 0:
            raise IOError("Temporary ZENON-SLD.csv was not written correctly.")
        os.replace(temp, target)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass
    return ZenonSldRegenerationResult(xml_path=xml_path, target_path=target, row_count=len(rows))
