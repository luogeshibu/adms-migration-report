"""RMU comparison service using mapped tabular source data."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from ..adapters import SourceAdapter, WorkspaceFileAdapter
from ..analysis import (
    compare_consistency, first_value, normalize_feeder_for_compare,
    normalize_ip, normalize_name, normalize_smart, normalize_type,
)
from ..parsers import clean, normalize_key, feeder_matches_site
from ..storage import ProjectStore
from .schema_service import (
    custom_review_column_key, equipment_review_column_key, RMU_CUSTOM_GROUP_BY_SOURCE,
)
from ..config.sources import schema_for
from .configurable_comparison_service import get_config as get_configurable_comparison_config, build_configurable_review


def _active_source_context(store: ProjectStore) -> dict[str, dict]:
    """Return reviewer-facing identity metadata for the five physical RMU sources.

    The comparison row stores this compact context so the *next* source refresh
    can explain exactly which file/version produced a value change.  The source
    data remain authoritative; this metadata is audit context only.
    """
    result: dict[str, dict] = {}
    fingerprints = dict((store.config or {}).get("repository_fingerprints", {}) or {})
    live_meta = dict((store.config or {}).get("live_source_metadata", {}) or {})
    manual = store.manual_source_overrides() if hasattr(store, "manual_source_overrides") else {}
    selections = store.source_file_selections() if hasattr(store, "source_file_selections") else {}

    for source_type in ("se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"):
        fp = dict(fingerprints.get(source_type) or {})
        live = dict(live_meta.get(source_type) or {})
        manual_record = dict(manual.get(source_type) or {})
        selection = dict(selections.get(source_type) or {})
        active = store.source_path(source_type) if hasattr(store, "source_path") else None

        # Reviewer-facing names have priority over timestamped workspace copies.
        name = str(selection.get("file_name") or "").strip()
        if not name:
            name = str(manual_record.get("original_name") or "").strip()
        if not name:
            name = str(fp.get("name") or "").strip()
        if not name and active is not None:
            name = Path(active).name

        result[source_type] = {
            "name": name,
            "sha256": str(fp.get("sha256") or ""),
            "size": int(fp.get("size") or live.get("size") or 0),
            "mtime_ns": int(fp.get("mtime_ns") or live.get("mtime_ns") or 0),
        }
    return result


def rmu_type_issue_map(store: ProjectStore | None) -> dict[str, str]:
    """Return RMUs whose RMU Data Review TYPE analysis is explicitly FALSE.

    The returned tooltip is the exact TYPE analysis detail already persisted in
    the RMU Data Review comparison row.  Signal Mapping Review consumes this
    small projection so it can surface a suspicious RMU type without
    reimplementing or diverging from the RMU validation rule.
    """
    if store is None:
        return {}
    output: dict[str, str] = {}
    try:
        rows = store.rows()
    except Exception:
        rows = []
    for row in rows or []:
        if clean((row or {}).get("analysis_type")).upper() != "FALSE":
            continue
        rmu = clean((row or {}).get("rmu"))
        if not rmu:
            continue
        detail = clean((row or {}).get("analysis_type_detail"))
        if not detail:
            detail = "TYPE consistency check\n\nResult: FALSE\nRMU Data Review found inconsistent cabinet type values."
        output.setdefault(rmu, detail)
    return output


def _consistency_tooltip(label: str, result) -> str:
    lines = [f"{label} consistency check"]
    lines.append("Rule: compare only non-blank source values; one available value is TRUE, multiple values must all agree.")
    if label.upper() == "IP":
        lines.append("IP uses every mapped RMU source IP field (SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD) when available.")
    if label.upper() == "FEEDER":
        lines.append("Rule: station/site token + feeder number must match; routing prefixes such as JED-NTH are ignored.")
        lines.append("Example: ABH-22 = JED-NTH-ABH-22, but ABH-22 != ABN-22.")
    if not result.normalized_by_source:
        lines += ["", "No non-blank source values", "Result: N/A"]
        return "\n".join(lines)
    lines.append("")
    for source, value in result.normalized_by_source.items():
        raw = clean(getattr(result, "raw_by_source", {}).get(source))
        if raw and raw != value:
            lines.append(f"{source}: {raw}  ->  {value}")
        else:
            lines.append(f"{source}: {value}")
    lines += ["", f"Result: {result.display or 'N/A'}"]
    if result.value is False:
        lines.append("Different normalized values were found across the available sources.")
    elif result.value is True and len(result.normalized_by_source) == 1:
        lines.append("Only one source has a value; blank sources are ignored by rule.")
    return "\n".join(lines)



# One source-aware registry drives every RMU Analysis field.  Blank values are
# ignored by compare_consistency, so a source participates only when it actually
# provides a value.  Keeping the mapping here prevents individual checks (most
# importantly IP) from drifting into pairwise/hard-coded special cases.
#
# For IP, every RMU source has an optional canonical ``ip`` slot; ADMS DB keeps
# its historical ``channel_ip`` key for UI/backward compatibility.  Therefore a
# future IP column added to SE / ZENON SLD / ADMS SLD automatically joins the
# same five-source comparison as soon as schema mapping resolves it.
_RMU_ANALYSIS_SOURCE_FIELDS: dict[str, dict[str, tuple[str, ...]]] = {
    "NAME": {
        "SE": ("rmu",), "ZENON DB": ("rmu",), "ZENON SLD": ("rmu",),
        "ADMS DB": ("rmu",), "ADMS SLD": ("rmu",),
    },
    "FEEDER": {
        "SE": ("feeder",), "ZENON DB": ("feeder",), "ZENON SLD": ("feeder",),
        "ADMS DB": ("gss_fid",), "ADMS SLD": ("feeder",),
    },
    "SMART": {
        "SE": ("smart",), "ZENON DB": ("smart",), "ZENON SLD": ("smart",),
        "ADMS DB": ("smart",), "ADMS SLD": ("smart",),
    },
    "TYPE": {
        "SE": ("rmu_type",), "ZENON DB": ("rmu_type",), "ZENON SLD": ("cabinet_type",),
        "ADMS DB": ("rmu_type",), "ADMS SLD": ("rmu_type",),
    },
    "IP": {
        "SE": ("ip",), "ZENON DB": ("ip",), "ZENON SLD": ("ip",),
        "ADMS DB": ("channel_ip", "ip"), "ADMS SLD": ("ip",),
    },
}


def _analysis_source_values(field: str, source_rows: dict[str, dict]) -> dict[str, object]:
    """Collect one business field from every applicable RMU source.

    The return value deliberately includes blank entries.  ``compare_consistency``
    owns the single business rule: blanks do not participate, one available value
    is TRUE, multiple available values are TRUE only when all normalized values
    agree, and no available value is N/A/blank.
    """
    mapping = _RMU_ANALYSIS_SOURCE_FIELDS.get(clean(field).upper(), {})
    return {
        source: first_value(source_rows.get(source) or {}, *keys)
        for source, keys in mapping.items()
    }


def _resolution_candidates(result) -> list[dict[str, str]]:
    """Return structured source choices for one automatic consistency issue.

    Raw and normalized values are kept together so Review can show exactly
    what each source supplied without re-parsing tooltip text.
    """
    candidates = []
    raw_by_source = getattr(result, "raw_by_source", {}) or {}
    normalized_by_source = getattr(result, "normalized_by_source", {}) or {}
    for source, normalized in normalized_by_source.items():
        candidates.append({
            "source": clean(source),
            "value": clean(raw_by_source.get(source) or normalized),
            "normalized": clean(normalized),
        })
    return candidates

def _link_analysis(raw_value: object) -> tuple[str, str]:
    """Interpret ADMS-SLD LINK as the RMU association state.

    LINK is not a cross-source consistency comparison.  It is the authoritative
    ADMS-SLD association flag. Blank/false-like values mean not linked; a true-
    like value or a non-empty association identifier means linked.
    """
    raw = clean(raw_value)
    token = raw.strip().upper()
    false_values = {"", "0", "FALSE", "NO", "N", "UNLINKED", "NONE", "NULL", "N/A", "NA", "-"}
    true_values = {"1", "TRUE", "YES", "Y", "LINKED", "OK"}
    if token in false_values:
        value = "FALSE"
        reason = "ADMS SLD LINK is blank/false; this RMU is not currently associated."
    elif token in true_values:
        value = "TRUE"
        reason = "ADMS SLD LINK indicates that this RMU is associated."
    else:
        # Some exports store a linked object/key instead of a Boolean.
        value = "TRUE"
        reason = "ADMS SLD LINK contains a non-empty association identifier."
    detail = "\n".join([
        "LINK association check",
        "",
        f"ADMS SLD LINK: {raw or '<blank>'}",
        f"Result: {value}",
        reason,
    ])
    return value, detail


def list_index(rows: list[dict], key_name: str) -> tuple[dict, dict]:
    grouped = {}
    for row in rows:
        key = normalize_name(row.get(key_name))
        if key:
            grouped.setdefault(key, []).append(row)
    return {k: v[0] for k, v in grouped.items()}, {k: len(v) for k, v in grouped.items()}


def list_index_alias(rows: list[dict], *keys: str) -> tuple[dict, dict]:
    grouped = {}
    for row in rows:
        key = normalize_name(first_value(row, *keys))
        if key:
            grouped.setdefault(key, []).append(row)
    return {k: v[0] for k, v in grouped.items()}, {k: len(v) for k, v in grouped.items()}


def _declared_duplicate_count(row: dict) -> int:
    """Return a source-declared duplicate count, defaulting to one.

    Generated ZENON-SLD.csv stores consolidated XML duplicates in the
    DuplicateCount column, so row-count-only duplicate detection is insufficient.
    """
    raw = clean(row.get("duplicate_count"))
    if not raw:
        return 1
    try:
        return max(1, int(float(raw)))
    except (TypeError, ValueError):
        return 1


def _anchor_rmus_and_feeders(
    se: list[dict], zdb: list[dict], adb: list[dict], asld: list[dict], site_name: str,
) -> tuple[set[str], dict[str, set[str]]]:
    """Return site RMU anchors and their known feeder identities.

    FEEDER is itself a field being validated, so it must never be used as the
    only gate deciding whether a ZENON SLD row is allowed into the comparison.
    RMUs already present in the other site sources are authoritative anchors;
    their graphical row must remain visible even when its feeder is wrong.
    """
    anchors: set[str] = set()
    feeders: dict[str, set[str]] = {}
    for rows, feeder_key in (
        (se, "feeder"), (zdb, "feeder"), (adb, "gss_fid"), (asld, "feeder"),
    ):
        for row in rows:
            rmu = normalize_name(row.get("rmu"))
            if not rmu:
                continue
            anchors.add(rmu)
            feeder = normalize_feeder_for_compare(row.get(feeder_key), site_name)
            if feeder:
                feeders.setdefault(rmu, set()).add(feeder)
    return anchors, feeders


def _scope_zenon_sld_rows(
    rows: list[dict], *, site_name: str, allowed_feeders: list[str],
    anchor_rmus: set[str], anchor_feeders: dict[str, set[str]],
) -> list[dict]:
    """Keep the selected site's graphical rows without hiding bad feeders.

    Historical code filtered ZENON SLD by feeder before comparison. That made
    the most important error case disappear: an RMU could be present in the
    site, but a wrong ZENON feeder caused the entire ZENON SLD row to be dropped
    and rendered as blank.  We now keep every row whose RMU is anchored by the
    other site sources.  Graphical-only rows are still site-filtered so a shared
    multi-site XML/CSV cannot leak unrelated RMUs into the selected site.

    If the same RMU appears more than once in a combined graphical source, the
    candidate matching a known feeder is ordered first (and therefore becomes
    the displayed row); equally relevant candidates remain so duplicate
    detection continues to work.
    """
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        rmu = normalize_name(row.get("rmu"))
        if rmu:
            grouped.setdefault(rmu, []).append(row)

    scoped: list[dict] = []
    for rmu, candidates in grouped.items():
        anchored = rmu in anchor_rmus
        if not anchored:
            candidates = [
                row for row in candidates
                if feeder_matches_site(clean(row.get("feeder")), site_name or None, allowed_feeders)
            ]
            if not candidates:
                continue

        known = anchor_feeders.get(rmu, set())

        def rank(row: dict) -> tuple[int, int, int, int]:
            feeder = clean(row.get("feeder"))
            feeder_norm = normalize_feeder_for_compare(feeder, site_name)
            exact_known = int(bool(feeder_norm and feeder_norm in known))
            site_match = int(feeder_matches_site(feeder, site_name or None, allowed_feeders))
            completeness = sum(bool(clean(row.get(key))) for key in ("feeder", "cabinet_type", "screen_name"))
            # Stable final component keeps the original source order for ties.
            return exact_known, site_match, completeness, -candidates.index(row)

        ranked = sorted(candidates, key=rank, reverse=True)
        if len(ranked) <= 1:
            scoped.extend(ranked)
            continue

        best = rank(ranked[0])[:2]
        # When one candidate is clearly the site/feeder match, cross-site rows
        # with the same numeric RMU are not treated as duplicates.  Otherwise
        # retain all equally relevant candidates so genuine duplicates surface.
        best_rows = [row for row in ranked if rank(row)[:2] == best]
        scoped.extend(best_rows)
    return scoped


def _filter_zenon_inventory_for_profile(rows: list[dict], profile: str = "RMU") -> list[dict]:
    """Return rows applicable to the active Equipment Data Review profile.

    v0.8.150 changes ZENON-SLD.csv from an RMU-only export into an
    all-equipment ``device_inventory.csv`` contract.  The source adapter must
    therefore canonicalize *every* DeviceType row, but the existing cross-system
    comparison is still the RMU profile.  When the new DeviceType field is
    present we select only that equipment class here; legacy RMU-only CSVs do
    not have DeviceType and intentionally keep the historical behavior.

    This boundary is what lets later CB/SFI/other profiles reuse the exact same
    mapped ZENON SLD inventory without contaminating today's RMU joins.
    """
    profile_token = clean(profile).upper() or "RMU"
    has_device_type = any(clean((row or {}).get("device_type")) for row in rows or [])
    if not has_device_type:
        return list(rows or [])
    return [
        row for row in rows or []
        if clean((row or {}).get("device_type")).upper() == profile_token
    ]


def _load_zenon_sld_for_review(
    adapter: SourceAdapter, *, site_name: str,
    se: list[dict], zdb: list[dict], adb: list[dict], asld: list[dict],
) -> list[dict]:
    """Load the authoritative mapped ZENON-SLD.csv used by Equipment Data Review.

    The application consumes only the supplied tabular inventory. XML parsing
    and in-app ZENON-SLD generation are intentionally outside this application.
    This guarantees that Site Data Sources shows exactly the graphical source
    used by Validation, customer Resolution and the sign-off report.
    """
    se_feeders = [clean(row.get("feeder")) for row in se]
    se_feeders = [value for value in se_feeders if value]
    anchor_rmus, anchor_feeders = _anchor_rmus_and_feeders(se, zdb, adb, asld, site_name)
    csv_rows = adapter.load_rows("zenon_sld")
    profile_rows = _filter_zenon_inventory_for_profile(csv_rows, "RMU")

    return _scope_zenon_sld_rows(
        profile_rows, site_name=site_name, allowed_feeders=se_feeders,
        anchor_rmus=anchor_rmus, anchor_feeders=anchor_feeders,
    )




def equipment_inventory_type_counts(store: ProjectStore, adapter: SourceAdapter | None = None) -> dict[str, int]:
    """Return legacy DeviceType filters only when the configurable engine is unused.

    v0.8.178 intentionally does not assume that any configured table contains a
    DeviceType column.  In configurable mode the Equipment Data Review scope is
    therefore the configured key union and the UI exposes only All Equipment.
    """
    configurable = get_configurable_comparison_config(store, bootstrap=False)
    if configurable.get("sources"):
        return {}
    adapter = adapter or WorkspaceFileAdapter(store)
    counts = Counter()
    for row in adapter.load_rows("zenon_sld") or []:
        token = clean((row or {}).get("device_type")).upper() or "UNCLASSIFIED"
        counts[token] += 1
    return dict(counts)


def _inventory_quality(row: dict) -> tuple[str, str]:
    status = clean((row or {}).get("name_status")).upper()
    warning = clean((row or {}).get("warning"))
    confidence = clean((row or {}).get("confidence")).upper()
    if status in {"UNRESOLVED", "FAILED", "ERROR"}:
        return "ATTENTION", "Identifier/name could not be resolved reliably."
    if warning or status in {"MISMATCH_CORRECTED", "RECOVERED", "AMBIGUOUS"} or confidence in {"LOW", "MEDIUM"}:
        return "REVIEW", warning or f"Name status={status or '—'}; confidence={confidence or '—'}"
    return "OK", "ZENON-SLD inventory record has no extractor quality warning."




_EQUIPMENT_SOURCE_LABELS = (
    ("se_list", "SE"),
    ("zenon_db", "ZENON DB"),
    ("zenon_sld", "ZENON SLD"),
    ("adms_db", "ADMS DB"),
    ("adms_sld", "ADMS SLD"),
)


def _equipment_rows_by_name(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows or []:
        key = normalize_name((row or {}).get("rmu"))
        if key:
            grouped.setdefault(key, []).append(row)
    return grouped


def _best_equipment_source_candidate(
    candidates: list[dict], *, target_feeder: str, source_feeder_key: str, site_name: str,
    target_device_type: str = "",
) -> dict:
    """Choose the most likely row when one equipment name occurs repeatedly.

    The equipment name remains the primary join key.  If a source contains more
    than one row for that name, the candidate whose normalized feeder agrees
    with the selected ZENON-SLD instance is preferred.  This keeps the browser
    deterministic without hiding duplicate physical source rows or pretending
    that feeder is the identity key.
    """
    candidates = list(candidates or [])
    if not candidates:
        return {}
    if len(candidates) == 1:
        return candidates[0]
    target_norm = normalize_feeder_for_compare(target_feeder, site_name)

    target_type = clean(target_device_type).upper()

    def rank(row: dict) -> tuple[int, int, int, int]:
        raw = clean((row or {}).get(source_feeder_key))
        norm = normalize_feeder_for_compare(raw, site_name)
        feeder_equal = int(bool(target_norm and norm and norm == target_norm))
        has_feeder = int(bool(norm))
        row_type = clean((row or {}).get("device_type")).upper()
        type_equal = int(bool(target_type and row_type and row_type == target_type))
        completeness = sum(bool(clean(value)) for value in (row or {}).values())
        # Device family is the strongest available disambiguator, followed by
        # feeder/scope. Blank device-type fields remain neutral.
        return type_equal, feeder_equal, has_feeder, completeness

    return max(candidates, key=rank)


def build_equipment_source_view(
    store: ProjectStore, profile: str = "__ALL__", adapter: SourceAdapter | None = None
) -> tuple[list[dict], dict]:
    """Build Equipment Data Review from the active site-local comparison config.

    v0.8.178 moves only the *source/comparison input layer* to a fully
    configurable engine. Existing projects are bootstrapped once from whatever
    legacy five-source files are active, after which the number/names of tables,
    key columns, comparison fields, source titles and visible fields are all
    site-local reviewer choices. The historical fixed implementation below is
    retained as a safety fallback only when no configurable source exists.
    """
    configurable = get_configurable_comparison_config(store, bootstrap=False)
    if configurable.get("sources"):
        return build_configurable_review(store)

    """Build the generic five-source Equipment Data Review view.

    ZENON-SLD remains the authoritative equipment/type inventory and therefore
    supplies the DeviceType selector.  For every selected equipment instance we
    join the corresponding equipment-name row from SE, ZENON DB, ADMS DB and
    ADMS SLD and render all five physical source blocks side-by-side.  Missing
    sources stay blank and are explicitly reported in Source Coverage.

    Every equipment class uses the same blank-ignoring five-source Analysis and
    the same Review/Resolution/Comments lifecycle. DeviceType only scopes rows;
    it does not select a different comparison engine. RMU keeps its historical
    raw review key solely for backward-compatible persistence.
    """
    adapter = adapter or WorkspaceFileAdapter(store)
    se = adapter.load_rows("se_list") or []
    zdb = adapter.load_rows("zenon_db") or []
    zsld_all = adapter.load_rows("zenon_sld") or []
    adb = adapter.load_rows("adms_db") or []
    asld = adapter.load_rows("adms_sld") or []

    wanted = clean(profile).upper() or "__ALL__"
    all_equipment_profiles = {"__ALL__", "ALL", "ALL EQUIPMENT"}

    # A project that has never explicitly saved the v0.8.178 configurable
    # source contract is still a legacy five-source project.  In that mode the
    # old comparison engine used the union of all source keys; making
    # ZENON-SLD the sole inventory here silently drops valid legacy rows when
    # the graphical inventory is incomplete or from a different export.
    # Keep the source-driven inventory contract for explicitly configurable
    # projects, but preserve the legacy union until the reviewer opts in.
    legacy_union_mode = not bool(configurable.get("sources"))
    site_name = clean(store.config.get("repository_site") or store.config.get("site_name")) if store else ""

    indices = {
        "se_list": _equipment_rows_by_name(se),
        "zenon_db": _equipment_rows_by_name(zdb),
        "adms_db": _equipment_rows_by_name(adb),
        "adms_sld": _equipment_rows_by_name(asld),
    }

    if legacy_union_mode:
        source_rows_by_type = {
            "se_list": se,
            "zenon_db": zdb,
            "zenon_sld": zsld_all,
            "adms_db": adb,
            "adms_sld": asld,
        }
        raw_name_by_key: dict[str, str] = {}
        for source_type in ("zenon_sld", "se_list", "zenon_db", "adms_db", "adms_sld"):
            for item in source_rows_by_type[source_type]:
                key = normalize_name((item or {}).get("rmu"))
                if key and key not in raw_name_by_key:
                    raw_name_by_key[key] = clean((item or {}).get("rmu"))

        if wanted in all_equipment_profiles:
            legacy_keys = set(raw_name_by_key)
        else:
            # Device-type filters still use the graphical inventory when one
            # exists; this keeps the historical RMU/non-RMU scope behavior
            # while allowing All Equipment to retain the complete key union.
            legacy_keys = {
                normalize_name(item.get("rmu"))
                for item in _filter_zenon_inventory_for_profile(zsld_all, wanted)
                if normalize_name(item.get("rmu"))
            }

        def legacy_sort_key(value: str) -> tuple[int, object]:
            token = clean(value)
            return (0, int(token)) if token.isdigit() else (1, token.casefold())

        zsld_by_key = _equipment_rows_by_name(zsld_all)
        zsld_rows = []
        for key in sorted(legacy_keys, key=legacy_sort_key):
            item = dict((zsld_by_key.get(key) or [{}])[0] or {})
            if not item:
                # Keep the identity available for the union row, but mark it
                # so the loop below does not falsely count ZENON-SLD as a
                # participating source.
                item = {"rmu": raw_name_by_key.get(key) or key, "_legacy_missing_zsld": True}
            zsld_rows.append(item)
    else:
        zsld_rows = (
            _filter_zenon_inventory_for_profile(zsld_all, wanted)
            if wanted not in all_equipment_profiles else list(zsld_all)
        )
    feeder_key = {
        "se_list": "feeder",
        "zenon_db": "feeder",
        "adms_db": "gss_fid",
        "adms_sld": "feeder",
    }

    output: list[dict] = []
    quality_counts = Counter()
    coverage_counts = Counter()

    # USER-added mapped columns are application-global metadata. Fetch them
    # once per source before the row loop. The previous implementation queried
    # SQLite for every source of every equipment row (5,000+ queries for a
    # 1,000-row inventory), which dominated refresh time on large stations.
    custom_fields_by_source: dict[str, list[dict]] = {}
    for source_type in RMU_CUSTOM_GROUP_BY_SOURCE:
        try:
            custom_fields_by_source[source_type] = list(store.custom_source_fields(source_type) or [])
        except Exception:
            custom_fields_by_source[source_type] = []

    for zrow in zsld_rows:
        zrow = dict(zrow or {})
        legacy_missing_zsld = bool(zrow.pop("_legacy_missing_zsld", False))
        equipment_name = clean(zrow.get("rmu"))
        name_key = normalize_name(equipment_name)
        target_feeder = clean(zrow.get("feeder"))
        target_device_type = clean(zrow.get("device_type")).upper()
        source_rows = {"zenon_sld": {} if legacy_missing_zsld else zrow}
        for source_type in ("se_list", "zenon_db", "adms_db", "adms_sld"):
            source_rows[source_type] = _best_equipment_source_candidate(
                indices[source_type].get(name_key, []),
                target_feeder=target_feeder,
                source_feeder_key=feeder_key[source_type],
                site_name=site_name,
                target_device_type=target_device_type,
            )

        s = source_rows["se_list"]
        z = source_rows["zenon_db"]
        a = source_rows["adms_db"]
        g = source_rows["adms_sld"]
        x = source_rows["zenon_sld"]
        present = [
            label for source_type, label in _EQUIPMENT_SOURCE_LABELS
            if bool(source_rows.get(source_type))
        ]
        missing = [label for _source_type, label in _EQUIPMENT_SOURCE_LABELS if label not in present]
        source_count = len(present)
        coverage_counts[f"{source_count}/5"] += 1
        if legacy_missing_zsld:
            quality, quality_detail = "REVIEW", "Legacy row retained; ZENON-SLD inventory row is missing."
        else:
            quality, quality_detail = _inventory_quality(x)
        quality_counts[quality] += 1

        # Rows retained only by the legacy union belong to the historical RMU
        # review scope.  Keep their plain RMU review key so old Review,
        # Checked and Resolution records can still be found by the new UI.
        device_type = (
            "RMU" if legacy_missing_zsld
            else (clean(x.get("device_type")).upper() or "UNCLASSIFIED")
        )
        source_rows_for_analysis = {
            "SE": s,
            "ZENON DB": z,
            "ZENON SLD": x,
            "ADMS DB": a,
            "ADMS SLD": g,
        }
        name_result = compare_consistency(
            _analysis_source_values("NAME", source_rows_for_analysis), normalize_name
        )
        feeder_result = compare_consistency(
            _analysis_source_values("FEEDER", source_rows_for_analysis),
            lambda value: normalize_feeder_for_compare(value, site_name),
        )
        smart_result = compare_consistency(
            _analysis_source_values("SMART", source_rows_for_analysis), normalize_smart
        )
        type_result = compare_consistency(
            _analysis_source_values("TYPE", source_rows_for_analysis), normalize_type
        )
        ip_result = compare_consistency(
            _analysis_source_values("IP", source_rows_for_analysis), normalize_ip
        )
        analysis_results = {
            "NAME": name_result, "FEEDER": feeder_result, "SMART": smart_result,
            "TYPE": type_result, "IP": ip_result,
        }
        mismatch_labels = [label for label, result in analysis_results.items() if result.value is False]
        remarks_parts = []
        if missing:
            remarks_parts.append("Not provided (ignored by Analysis): " + ", ".join(missing))
        if mismatch_labels:
            remarks_parts.append("Analysis mismatch: " + " / ".join(mismatch_labels))
        elif any(result.value is True for result in analysis_results.values()):
            remarks_parts.append("Analysis: all available checks passed")

        # Existing RMU review keys are deliberately preserved byte-for-byte so
        # upgrading an existing project never loses RMU Comments/Resolution/
        # lifecycle history. Other equipment types share the same mature review
        # engine through an isolated namespaced key.
        review_key = equipment_name if device_type == "RMU" else f"EQ::{device_type}::{equipment_name}"

        data = {
            "no": len(output) + 1,
            "rmu": equipment_name,
            "review_key": review_key,
            "equipment_device_type": device_type,
            "equipment_source_count": f"{source_count}/5",
            "equipment_missing_sources": ", ".join(missing),
            "equipment_source_presence_detail": "Present: " + (", ".join(present) or "—") + ("\nMissing: " + ", ".join(missing) if missing else ""),

            "eq_se_station": clean(s.get("station")),
            "eq_se_feeder": clean(s.get("feeder")),
            "eq_se_rmu": clean(s.get("rmu")),
            "eq_se_device_type": clean(s.get("device_type")).upper(),
            "eq_se_type": clean(s.get("rmu_type")),
            "eq_se_smart": clean(s.get("smart")),
            "eq_se_oh_ug": clean(s.get("oh_ug")),
            "eq_se_ip": clean(s.get("ip")),

            "eq_zdb_feeder": clean(z.get("feeder")),
            "eq_zdb_rmu": clean(z.get("rmu")),
            "eq_zdb_brand": clean(z.get("brand")),
            "eq_zdb_device_type": clean(z.get("device_type")).upper(),
            "eq_zdb_type": clean(z.get("rmu_type")),
            "eq_zdb_smart": clean(z.get("smart")),
            "eq_zdb_ip": clean(z.get("ip")),
            "eq_zdb_port": clean(z.get("port")),
            "eq_zdb_function_location": clean(z.get("function_location")),

            "eq_zsld_rmu": clean(x.get("rmu")),
            "eq_zsld_device_type": clean(x.get("device_type")).upper(),
            "eq_zsld_feeder": clean(x.get("feeder")),
            "eq_zsld_type": clean(x.get("cabinet_type")),
            "eq_zsld_screen": clean(x.get("screen_name")),
            "eq_zsld_smart": clean(x.get("smart")),
            "eq_zsld_ip": clean(x.get("ip")),

            "eq_adb_rmu": clean(a.get("rmu")),
            "eq_adb_feeder": clean(a.get("gss_fid")),
            "eq_adb_device_type": clean(a.get("device_type")).upper(),
            "eq_adb_type": clean(a.get("rmu_type")),
            "eq_adb_smart": clean(a.get("smart")),
            "eq_adb_ip": clean(a.get("channel_ip") or a.get("ip")),
            "eq_adb_port": clean(a.get("channel_port")),

            "eq_asld_rmu": clean(g.get("rmu")),
            "eq_asld_feeder": clean(g.get("feeder")),
            "eq_asld_type": clean(g.get("rmu_type")),
            "eq_asld_device_type": clean(g.get("device_type")).upper(),
            "eq_asld_smart": clean(g.get("smart")),
            "eq_asld_ip": clean(g.get("ip")),

            # Common five-source Analysis contract used by every equipment type.
            # Blank sources do not participate; one available value is TRUE;
            # multiple available values must normalize to the same value.
            "analysis_name": name_result.display,
            "analysis_feeder": feeder_result.display,
            "analysis_smart": smart_result.display,
            "analysis_type": type_result.display,
            "analysis_ip": ip_result.display,
            "analysis_name_detail": _consistency_tooltip("NAME", name_result),
            "analysis_feeder_detail": _consistency_tooltip("FEEDER", feeder_result),
            "analysis_smart_detail": _consistency_tooltip("SMART", smart_result),
            "analysis_type_detail": _consistency_tooltip("TYPE", type_result),
            "analysis_ip_detail": _consistency_tooltip("IP", ip_result),
            "resolution_candidates": {
                "NAME": _resolution_candidates(name_result),
                "FEEDER": _resolution_candidates(feeder_result),
                "SMART": _resolution_candidates(smart_result),
                "TYPE": _resolution_candidates(type_result),
                "IP": _resolution_candidates(ip_result),
            },
            "comments": "",

            "equipment_quality": quality,
            "equipment_quality_detail": quality_detail,
            "eq_zsld_name_status": clean(x.get("name_status")),
            "eq_zsld_confidence": clean(x.get("confidence")),
            "eq_zsld_resolved_full_name": clean(x.get("resolved_full_name")),
            "eq_zsld_element_name": clean(x.get("element_name")),
            "eq_zsld_classification_reason": clean(x.get("classification_reason")),
            "eq_zsld_warning": clean(x.get("warning")),
            "status": "WARNING" if mismatch_labels else "MATCHED",
            "remarks": "; ".join(remarks_parts),
        }

        # Every built-in App field in the five physical source schemas is made
        # available to Equipment Data Review.  Core fields keep their fixed
        # historical review keys; optional built-ins use deterministic
        # source-scoped keys.  This is presentation/reference data only: the
        # Analysis contract above remains the single calculation path.
        for source_type in RMU_CUSTOM_GROUP_BY_SOURCE:
            source_row = source_rows.get(source_type) or {}
            schema = schema_for(source_type)
            if schema is not None:
                for spec in schema.fields:
                    review_key = equipment_review_column_key(source_type, spec.key)
                    data.setdefault(review_key, clean(source_row.get(spec.key)))

            # USER App columns follow the same rule and stay source-faithful.
            for item in custom_fields_by_source.get(source_type, []):
                field_key = clean((item or {}).get("field_key"))
                if field_key:
                    data[custom_review_column_key(source_type, field_key)] = clean(source_row.get(field_key))

        output.append(data)

    summary = {
        "quality": dict(quality_counts),
        "coverage": dict(coverage_counts),
    }
    return output, summary

def build_equipment_inventory(
    store: ProjectStore, profile: str = "__ALL__", adapter: SourceAdapter | None = None
) -> tuple[list[dict], dict]:
    """Build a source-faithful ZENON-SLD equipment browser.

    This is intentionally separate from the existing RMU five-source Analysis.
    Every DeviceType is retained and immediately visible.  Selecting RMU in the
    UI continues to use ``build_comparison``; selecting ALL/non-RMU types uses
    this inventory view until a dedicated cross-system review profile is added.
    """
    adapter = adapter or WorkspaceFileAdapter(store)
    rows = adapter.load_rows("zenon_sld") or []
    wanted = clean(profile).upper() or "__ALL__"
    output = []
    quality_counts = Counter()
    for src in rows:
        device_type = clean((src or {}).get("device_type")).upper() or "UNCLASSIFIED"
        if wanted not in {"__ALL__", "ALL", "ALL EQUIPMENT"} and device_type != wanted:
            continue
        quality, quality_detail = _inventory_quality(src)
        quality_counts[quality] += 1
        output.append({
            "no": len(output) + 1,
            "rmu": clean(src.get("rmu")),
            "zsld_device_type": device_type,
            "zsld_type": clean(src.get("cabinet_type")),
            "zsld_smart": clean(src.get("smart")),
            "zsld_feeder": clean(src.get("feeder")),
            "zsld_screen_name": clean(src.get("screen_name")),
            "zsld_destination_name": clean(src.get("destination_name")),
            "zsld_display_name": clean(src.get("display_name")),
            "zsld_resolved_full_name": clean(src.get("resolved_full_name")),
            "zsld_name_source": clean(src.get("name_source")),
            "zsld_name_status": clean(src.get("name_status")),
            "zsld_confidence": clean(src.get("confidence")),
            "zsld_graphic_instances": clean(src.get("duplicate_count")),
            "zsld_element_name": clean(src.get("element_name")),
            "zsld_start_x": clean(src.get("start_x")),
            "zsld_start_y": clean(src.get("start_y")),
            "zsld_classification_reason": clean(src.get("classification_reason")),
            "zsld_warning": clean(src.get("warning")),
            "inventory_quality": quality,
            "inventory_quality_detail": quality_detail,
            "status": "INVENTORY",
            "remarks": clean(src.get("warning")),
        })
    return output, dict(quality_counts)

def build_comparison(store: ProjectStore, adapter: SourceAdapter | None = None) -> tuple[list[dict], dict]:
    adapter = adapter or WorkspaceFileAdapter(store)

    se = adapter.load_rows("se_list")
    zdb = adapter.load_rows("zenon_db")
    adb = adapter.load_rows("adms_db")
    asld = adapter.load_rows("adms_sld")
    site_name = clean(store.config.get("repository_site") or store.config.get("site_name"))
    zsld = _load_zenon_sld_for_review(
        adapter, site_name=site_name,
        se=se, zdb=zdb, adb=adb, asld=asld,
    )

    se_i, se_n = list_index(se, "rmu")
    zdb_i, zdb_n = list_index(zdb, "rmu")
    adb_i, adb_n = list_index(adb, "rmu")
    asld_i, asld_n = list_index(asld, "rmu")
    zsld_i, zsld_n = list_index(zsld, "rmu")

    keys = set(se_i) | set(zdb_i) | set(adb_i) | set(asld_i) | set(zsld_i)
    source_context = _active_source_context(store)
    rows = []
    for no, rmu in enumerate(sorted(keys, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x)), 1):
        s, z, x, a, g = se_i.get(rmu, {}), zdb_i.get(rmu, {}), zsld_i.get(rmu, {}), adb_i.get(rmu, {}), asld_i.get(rmu, {})
        z_device_type = clean(x.get("device_type"))
        z_feeder = clean(x.get("feeder"))
        z_type = clean(x.get("cabinet_type"))
        screen_name = clean(x.get("screen_name"))
        smart_raw = clean(g.get("smart"))
        smart = normalize_smart(smart_raw)
        adb_smart_raw = clean(a.get("smart"))
        se_feeder = clean(s.get("feeder"))
        adb_feeder = clean(a.get("gss_fid"))
        asld_feeder = clean(g.get("feeder"))
        driver_ip, driver_port = clean(z.get("ip")), clean(z.get("port"))
        channel_ip, channel_port = clean(a.get("channel_ip")), clean(a.get("channel_port"))
        asld_link_raw = clean(g.get("link"))

        source_rows_for_analysis = {
            "SE": s,
            "ZENON DB": z,
            "ZENON SLD": x,
            "ADMS DB": a,
            "ADMS SLD": g,
        }
        name_result = compare_consistency(
            _analysis_source_values("NAME", source_rows_for_analysis), normalize_name
        )
        feeder_result = compare_consistency(
            _analysis_source_values("FEEDER", source_rows_for_analysis),
            lambda value: normalize_feeder_for_compare(value, site_name),
        )
        smart_result = compare_consistency(
            _analysis_source_values("SMART", source_rows_for_analysis), normalize_smart
        )
        type_result = compare_consistency(
            _analysis_source_values("TYPE", source_rows_for_analysis), normalize_type
        )
        ip_result = compare_consistency(
            _analysis_source_values("IP", source_rows_for_analysis), normalize_ip
        )
        # ADMS SLD LINK is retained as raw source data for backward compatibility,
        # but v0.8.50 retires it from the active RMU Analysis/review contract.
        # It therefore cannot create an issue, affect row severity, or require a
        # customer Resolution decision.
        link_display = ""
        link_detail = ""

        analysis_values = {
            "NAME": name_result.value,
            "FEEDER": feeder_result.value,
            "SMART": smart_result.value,
            "TYPE": type_result.value,
            "IP": ip_result.value,
        }
        remarks = []
        missing = []
        for label, present in (("SE LIST", bool(s)), ("ZENON DB", bool(z)), ("ZENON SLD", bool(x)), ("ADMS DB", bool(a)), ("ADMS SLD", bool(g))):
            if not present:
                missing.append(label)
        if missing:
            remarks.append("Not provided (ignored by Analysis): " + ", ".join(missing))
        duplicates = [
            label for label, n in (
                ("SE LIST", se_n.get(rmu, 0)), ("ZENON DB", zdb_n.get(rmu, 0)),
                ("ZENON SLD", max(zsld_n.get(rmu, 0), _declared_duplicate_count(x) if x else 0)),
                ("ADMS DB", adb_n.get(rmu, 0)), ("ADMS SLD", asld_n.get(rmu, 0)),
            ) if n > 1
        ]
        if duplicates:
            remarks.append("Duplicate: " + ", ".join(duplicates))

        mismatch_labels = [label for label, flag in analysis_values.items() if flag is False]
        if mismatch_labels:
            remarks.append("Analysis mismatch: " + " / ".join(mismatch_labels))
        elif any(flag is True for flag in analysis_values.values()):
            remarks.append("Analysis: all available checks passed")

        if type_result.value is False:
            detail = " / ".join(f"{src}={value}" for src, value in type_result.normalized_by_source.items())
            remarks.append("Cabinet type mismatch: " + detail)
        if ip_result.value is False:
            detail = " / ".join(f"{src}={value}" for src, value in ip_result.normalized_by_source.items())
            remarks.append("IP mismatch: " + detail)
        warning = clean(x.get("warning"))
        if warning:
            remarks.append(warning)

        status = "MATCHED"
        type_mismatch = type_result.value is False
        failed_analysis = bool(mismatch_labels)
        # Missing source rows are informational only.  The formal Analysis rule
        # compares whatever values are available and never fails just because a
        # source is absent. Duplicates remain a separate data-quality warning.
        if duplicates or type_mismatch or failed_analysis:
            status = "FAILED" if type_mismatch or duplicates else "WARNING"

        row_data = {
            "no": no, "rmu": rmu,
            "se_station": clean(s.get("station")), "se_feeder": se_feeder,
            "se_rmu": clean(s.get("rmu")), "se_smart": clean(s.get("smart")), "se_oh_ug": clean(s.get("oh_ug")),
            "zdb_feeder": clean(z.get("feeder")), "zdb_rmu": clean(z.get("rmu")),
            "zdb_brand": clean(z.get("brand")), "zdb_device": clean(z.get("rmu_type")),
            "zdb_nop": clean(z.get("nop")), "zdb_smart": clean(z.get("smart")), "zdb_vip": clean(z.get("vip")),
            "zdb_function_location": clean(z.get("function_location")),
            "driver_ip": driver_ip, "driver_port": driver_port, "driver_link_address": clean(z.get("link_address")),
            "driver_link_address_size": clean(z.get("link_address_size")), "driver_cot_size": clean(z.get("cot_size")),
            "driver_coa_size": clean(z.get("coa_size")), "driver_ioa_size": clean(z.get("ioa_size")),
            "driver_t1": clean(z.get("t1")), "driver_t2": clean(z.get("t2")), "driver_t3": clean(z.get("t3")),
            "driver_k": clean(z.get("k_value")), "driver_w": clean(z.get("w_value")), "driver_net_address": clean(z.get("net_address")),
            "zsld_device_type": z_device_type,
            "zsld_feeder": z_feeder, "zsld_rmu": clean(x.get("rmu")),
            "zsld_screen_name": screen_name, "zsld_type": z_type, "zsld_smart": clean(x.get("smart")),
            "adb_rmu": clean(a.get("rmu")), "adb_gss_fid": adb_feeder,
            "adb_y1": clean(a.get("y1")), "adb_y2": clean(a.get("y2")), "adb_y3": clean(a.get("y3")),
            "adb_y4": clean(a.get("y4")), "adb_q1": clean(a.get("q1")), "adb_q2": clean(a.get("q2")), "adb_type": clean(a.get("rmu_type")),
            "adb_smart": adb_smart_raw,
            "adms_channel_ip": channel_ip, "adms_channel_port": channel_port,
            "asld_rmu": clean(g.get("rmu")), "asld_type": clean(g.get("rmu_type")),
            "asld_smart": smart_raw, "asld_link": asld_link_raw,
            "analysis_name": name_result.display, "analysis_feeder": feeder_result.display,
            "analysis_smart": smart_result.display, "analysis_type": type_result.display,
            "analysis_ip": ip_result.display, "analysis_link": "",
            "analysis_name_detail": _consistency_tooltip("NAME", name_result),
            "analysis_feeder_detail": _consistency_tooltip("FEEDER", feeder_result),
            "analysis_smart_detail": _consistency_tooltip("SMART", smart_result),
            "analysis_type_detail": _consistency_tooltip("TYPE", type_result),
            "analysis_ip_detail": _consistency_tooltip("IP", ip_result),
            "analysis_link_detail": "",
            "resolution_candidates": {
                "NAME": _resolution_candidates(name_result),
                "FEEDER": _resolution_candidates(feeder_result),
                "SMART": _resolution_candidates(smart_result),
                "TYPE": _resolution_candidates(type_result),
                "IP": _resolution_candidates(ip_result),
            },
            "status": status, "remarks": "; ".join(remarks), "comments": "",
            # Audit-only provenance used by the next refresh to explain source
            # value changes for equipment that has Needs Action history.
            "_source_context": source_context,
        }

        # Added App columns are normally reference/display values only.  The
        # reserved business key ``ip`` is the exception: when a source maps an
        # IP field, it participates in the source-aware IP Analysis above.
        source_rows = {
            "se_list": s,
            "zenon_db": z,
            "zenon_sld": x,
            "adms_db": a,
            "adms_sld": g,
        }
        for source_type in RMU_CUSTOM_GROUP_BY_SOURCE:
            source_row = source_rows.get(source_type) or {}
            try:
                custom_fields = store.custom_source_fields(source_type)
            except Exception:
                custom_fields = []
            for item in custom_fields or []:
                field_key = clean((item or {}).get("field_key"))
                if field_key:
                    # The App-column definition is global across sites. If this
                    # site's source field is absent/unmapped, SourceAdapter puts
                    # None/blank on the canonical row and the UI must keep the
                    # column visible with an empty cell rather than borrowing a
                    # value from another table.
                    row_data[custom_review_column_key(source_type, field_key)] = clean(source_row.get(field_key))

        rows.append(row_data)
    summary = Counter(r["status"] for r in rows)
    return rows, dict(summary)
