"""RMU comparison service and generated Zenon SLD export."""
from __future__ import annotations
import csv
from collections import Counter
from pathlib import Path
from ..adapters import SourceAdapter, WorkspaceFileAdapter
from ..analysis import (
    compare_consistency, first_value, normalize_feeder_for_compare,
    normalize_ip, normalize_name, normalize_smart, normalize_type,
)
from ..parsers import clean, normalize_key, parse_zenon_xml, feeder_matches_site
from ..storage import ProjectStore


def _consistency_tooltip(label: str, result) -> str:
    lines = [f"{label} consistency check"]
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


def build_comparison(store: ProjectStore, adapter: SourceAdapter | None = None) -> tuple[list[dict], dict]:
    adapter = adapter or WorkspaceFileAdapter(store)

    se = adapter.load_rows("se_list")
    zdb = adapter.load_rows("zenon_db")
    adb = adapter.load_rows("adms_db")
    asld = adapter.load_rows("adms_sld")
    xml_path = adapter.zenon_xml_path()
    site_name = clean(store.config.get("repository_site") or store.config.get("site_name"))
    se_feeders = [clean(row.get("feeder")) for row in se]
    se_feeders = [value for value in se_feeders if value]
    if xml_path:
        zsld = parse_zenon_xml(xml_path, site_name=site_name or None, allowed_feeders=se_feeders)
    else:
        zsld = adapter.load_rows("zenon_sld")
        if site_name:
            zsld = [
                row for row in zsld
                if feeder_matches_site(clean(row.get("feeder")), site_name, se_feeders)
            ]

    se_i, se_n = list_index(se, "rmu")
    zdb_i, zdb_n = list_index(zdb, "rmu")
    adb_i, adb_n = list_index(adb, "rmu")
    asld_i, asld_n = list_index(asld, "rmu")
    zsld_i, zsld_n = list_index(zsld, "rmu")

    keys = set(se_i) | set(zdb_i) | set(adb_i) | set(asld_i) | set(zsld_i)
    rows = []
    for no, rmu in enumerate(sorted(keys, key=lambda x: (not x.isdigit(), int(x) if x.isdigit() else x)), 1):
        s, z, x, a, g = se_i.get(rmu, {}), zdb_i.get(rmu, {}), zsld_i.get(rmu, {}), adb_i.get(rmu, {}), asld_i.get(rmu, {})
        z_feeder = clean(x.get("feeder"))
        z_type = clean(x.get("cabinet_type"))
        screen_name = clean(x.get("screen_name"))
        smart_raw = clean(g.get("smart"))
        smart = normalize_smart(smart_raw)
        se_feeder = clean(s.get("feeder"))
        adb_feeder = clean(a.get("gss_fid"))
        asld_feeder = clean(g.get("feeder"))
        driver_ip, driver_port = clean(z.get("ip")), clean(z.get("port"))
        channel_ip, channel_port = clean(a.get("channel_ip")), clean(a.get("channel_port"))
        asld_link_raw = clean(g.get("link"))

        name_result = compare_consistency({
            "SE": s.get("rmu"),
            "ZENON DB": z.get("rmu"),
            "ZENON SLD XML": x.get("rmu"),
            "ADMS DB": a.get("rmu"),
            "ADMS SLD": g.get("rmu"),
        }, normalize_name)
        feeder_result = compare_consistency({
            "SE": se_feeder,
            "ZENON DB": z.get("feeder"),
            "ZENON SLD XML": z_feeder,
            "ADMS DB": adb_feeder,
            "ADMS SLD": asld_feeder,
        }, lambda value: normalize_feeder_for_compare(value, site_name))
        smart_result = compare_consistency({
            "SE": s.get("smart"),
            "ZENON DB": z.get("smart"),
            "ZENON SLD XML": x.get("smart"),
            # ADMS DB has no SMART business field. On the ADMS side SMART is
            # sourced only from ADMS SLD, so ADMS DB must never participate in
            # SMART consistency or appear as a missing mapping requirement.
            "ADMS SLD": g.get("smart"),
        }, normalize_smart)
        type_result = compare_consistency({
            "SE": s.get("rmu_type"),
            "ZENON DB": z.get("rmu_type"),
            "ZENON SLD XML": z_type,
            "ADMS DB": a.get("rmu_type"),
            "ADMS SLD": g.get("rmu_type"),
        }, normalize_type)
        ip_result = compare_consistency({
            "Driver info": driver_ip,
            "ADMS Channel": channel_ip,
        }, normalize_ip)
        if g:
            link_display, link_detail = _link_analysis(asld_link_raw)
            link_value = link_display == "TRUE"
        else:
            link_display = ""
            link_value = None
            link_detail = "\n".join([
                "LINK association check", "", "ADMS SLD row: <missing>", "Result: N/A",
                "No ADMS SLD row is available, so LINK is not evaluated.",
            ])

        analysis_values = {
            "NAME": name_result.value,
            "FEEDER": feeder_result.value,
            "SMART": smart_result.value,
            "TYPE": type_result.value,
            "IP": ip_result.value,
            "LINK": link_value,
        }
        remarks = []
        missing = []
        for label, present in (("SE LIST", bool(s)), ("ZENON DB", bool(z)), ("ZENON SLD", bool(x)), ("ADMS DB", bool(a)), ("ADMS SLD", bool(g))):
            if not present:
                missing.append(label)
        if missing:
            remarks.append("Missing: " + ", ".join(missing))
        duplicates = [
            label for label, n in (
                ("SE LIST", se_n.get(rmu, 0)), ("ZENON DB", zdb_n.get(rmu, 0)),
                ("ZENON SLD", zsld_n.get(rmu, 0)), ("ADMS DB", adb_n.get(rmu, 0)),
                ("ADMS SLD", asld_n.get(rmu, 0)),
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
        if link_value is False:
            remarks.append(f"RMU not linked in ADMS SLD: LINK={asld_link_raw or '<blank>'}")

        warning = clean(x.get("warning"))
        if warning:
            remarks.append(warning)

        status = "MATCHED"
        type_mismatch = type_result.value is False
        failed_analysis = bool(mismatch_labels)
        if missing or duplicates or type_mismatch or failed_analysis:
            status = "FAILED" if type_mismatch or duplicates else "WARNING"

        rows.append({
            "no": no, "rmu": rmu,
            "se_station": clean(s.get("station")), "se_feeder": se_feeder,
            "se_rmu": normalize_key(s.get("rmu")), "se_smart": clean(s.get("smart")), "se_oh_ug": clean(s.get("oh_ug")),
            "zdb_feeder": clean(z.get("feeder")), "zdb_rmu": normalize_key(z.get("rmu")),
            "zdb_brand": clean(z.get("brand")), "zdb_device": clean(z.get("rmu_type")),
            "zdb_nop": clean(z.get("nop")), "zdb_smart": clean(z.get("smart")), "zdb_vip": clean(z.get("vip")),
            "zdb_function_location": clean(z.get("function_location")),
            "driver_ip": driver_ip, "driver_port": driver_port, "driver_link_address": clean(z.get("link_address")),
            "driver_link_address_size": clean(z.get("link_address_size")), "driver_cot_size": clean(z.get("cot_size")),
            "driver_coa_size": clean(z.get("coa_size")), "driver_ioa_size": clean(z.get("ioa_size")),
            "driver_t1": clean(z.get("t1")), "driver_t2": clean(z.get("t2")), "driver_t3": clean(z.get("t3")),
            "driver_k": clean(z.get("k_value")), "driver_w": clean(z.get("w_value")), "driver_net_address": clean(z.get("net_address")),
            "zsld_feeder": z_feeder, "zsld_rmu": normalize_key(x.get("rmu")),
            "zsld_screen_name": screen_name, "zsld_type": z_type,
            "adb_rmu": normalize_key(a.get("rmu")), "adb_gss_fid": adb_feeder,
            "adb_y1": clean(a.get("y1")), "adb_y2": clean(a.get("y2")), "adb_y3": clean(a.get("y3")),
            "adb_y4": clean(a.get("y4")), "adb_q1": clean(a.get("q1")), "adb_q2": clean(a.get("q2")), "adb_type": clean(a.get("rmu_type")),
            "adms_channel_ip": channel_ip, "adms_channel_port": channel_port,
            "asld_rmu": normalize_key(g.get("rmu")), "asld_type": clean(g.get("rmu_type")),
            "asld_smart": smart, "asld_link": asld_link_raw,
            "analysis_name": name_result.display, "analysis_feeder": feeder_result.display,
            "analysis_smart": smart_result.display, "analysis_type": type_result.display,
            "analysis_ip": ip_result.display, "analysis_link": link_display,
            "analysis_name_detail": _consistency_tooltip("NAME", name_result),
            "analysis_feeder_detail": _consistency_tooltip("FEEDER", feeder_result),
            "analysis_smart_detail": _consistency_tooltip("SMART", smart_result),
            "analysis_type_detail": _consistency_tooltip("TYPE", type_result),
            "analysis_ip_detail": _consistency_tooltip("IP", ip_result),
            "analysis_link_detail": link_detail,
            "status": status, "remarks": "; ".join(remarks), "comments": "",
        })
    summary = Counter(r["status"] for r in rows)
    return rows, dict(summary)


ZENON_SLD_HEADERS = [
    "No.", "XMLFile", "Screen name", "CabinetType", "Feeder", "RMU",
    "LinkName", "SubstituteDestination", "DuplicateCount", "Warning",
]


def write_zenon_sld_csv_path(target: Path, xml_path: Path, rows: list[dict]) -> Path:
    """Write parsed zenOn RMUs to an explicit CSV path.

    The caller controls replacement policy. Keeping this writer path-oriented
    allows the Site Repository action to write a temporary file beside the
    target and atomically replace ZENON-SLD.csv only after successful parsing.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=ZENON_SLD_HEADERS)
        writer.writeheader()
        for i, r in enumerate(rows, 1):
            writer.writerow({
                "No.": i, "XMLFile": xml_path.name, "Screen name": r.get("screen_name", r.get("picture", "")),
                "CabinetType": r.get("cabinet_type", ""), "Feeder": r.get("feeder", ""), "RMU": r.get("rmu", ""),
                "LinkName": r.get("link_name", ""), "SubstituteDestination": r.get("destination", ""),
                "DuplicateCount": r.get("duplicate_count", ""), "Warning": r.get("warning", ""),
            })
    return target


def write_zenon_sld_csv(store: ProjectStore, xml_path: Path, rows: list[dict]) -> Path:
    return write_zenon_sld_csv_path(store.generated_dir / "ZENON-SLD.csv", xml_path, rows)
