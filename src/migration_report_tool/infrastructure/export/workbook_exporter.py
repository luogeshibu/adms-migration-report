"""Formal Excel export for the two application review workspaces.

The delivery workbook intentionally mirrors the *application review views* rather
than renaming/copying the customer's DATA / DB-smart worksheets.

Exactly five worksheets are exported, in this order:

1. RMU Data Review          - generated from the App RMU review model/layout
2. Signal Mapping Review    - generated from the App signal review model/layout
3. STANDARD                 - copied from the active application IOA STANDARD.xlsx
4. Import Sources           - active source inventory
5. Change Audit Log         - immutable application audit trail

STANDARD is copied from the active application IOA STANDARD workbook.  The first two
worksheets are application-owned deliverables and therefore use the same grouped
header hierarchy, neutral header palette, review columns and status colors that
are shown in the desktop application.
"""
from __future__ import annotations

from copy import copy
from datetime import datetime
from pathlib import Path
from ...utils.paths import standard_reference_path, standard_reference_origin

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.comments import Comment
from openpyxl.utils import get_column_letter

from ...db_smart import DBSmartReport, build_signal_mapping_report_from_store
from ...paths import resource_root
from ...schema import COMPARISON_GROUPS, SOURCE_TYPES
from ...storage import ProjectStore
from ...review_status import analysis_review_state, field_false_color, signal_review_display_status
from ...config.sources import schema_for
from ...services.audit_presentation import present_audit_item
from ...services.schema_service import (
    get_source_display_names, field_display_name, apply_display_names_to_groups,
    RMU_REVIEW_DISPLAY_BINDINGS, SIGNAL_REVIEW_DISPLAY_BINDINGS,
)
from ..parsers import validate_source_file


RMU_REVIEW_SHEET = "RMU Data Review"
SIGNAL_REVIEW_SHEET = "Signal Mapping Review"
STANDARD_SHEET = "STANDARD"
IMPORT_SOURCES_SHEET = "Import Sources"
AUDIT_LOG_SHEET = "Change Audit Log"
EXPORT_SHEETS = (
    RMU_REVIEW_SHEET,
    SIGNAL_REVIEW_SHEET,
    STANDARD_SHEET,
    IMPORT_SOURCES_SHEET,
    AUDIT_LOG_SHEET,
)

# App visual system (same intent as ui.py REPORT_HEADER_COLORS / status palette).
HEADER_TOP = "E8EDF3"
HEADER_BOTTOM = "F4F6F8"
HEADER_TEXT = "24364B"
GRID = "D5DEE8"
WHITE = "FFFFFF"

ROW_PASS = "EAF7F0"
ROW_ONE_ISSUE = "FFF8D8"
ROW_TWO_ISSUES = "FFF8D8"
ROW_CRITICAL = "FDECEC"

FALSE_NAME = "F7D7D7"
FALSE_FEEDER = "F7D7D7"
FALSE_SMART = "F7D7D7"
FALSE_TYPE = "F7D7D7"

REVIEW_NOT_REQUIRED = "EEF4F8"
REVIEW_UNREVIEWED = "F3F4F6"
REVIEWED = "DDF5E7"
NEEDS_ACTION = "FDECEC"
REVIEW_VALIDATION_REQUIRED = "FFF4D6"
ANALYSIS_TRUE = "DDF5E7"
ANALYSIS_FALSE = "F7D7D7"

_THIN = Side(style="thin", color=GRID)
_CELL_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_FILL_CACHE: dict[str, PatternFill] = {}
_FONT_NORMAL = Font(bold=False, color="18212F")
_FONT_BOLD = Font(bold=True, color="18212F")
_ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=False)
_ALIGN_LEFT_WRAP = Alignment(horizontal="left", vertical="center", wrap_text=True)
_ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=False)
_ALIGN_CENTER_WRAP = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _fill(color: str) -> PatternFill:
    value = _FILL_CACHE.get(color)
    if value is None:
        value = PatternFill("solid", fgColor=color)
        _FILL_CACHE[color] = value
    return value


def _builtin_standard_reference() -> Path:
    return standard_reference_path()


def _excel_width(pixel_width: int) -> float:
    """Approximate Qt pixel column widths using Excel character units."""
    return max(8.0, min(65.0, round(float(pixel_width) / 7.2, 1)))


def _header_cell(cell, *, top: bool) -> None:
    cell.fill = PatternFill("solid", fgColor=HEADER_TOP if top else HEADER_BOTTOM)
    cell.font = Font(bold=True, color=HEADER_TEXT)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = _CELL_BORDER


def _body_cell(cell, *, fill: str = WHITE, bold: bool = False, center: bool = False, wrap: bool = False) -> None:
    cell.fill = _fill(fill)
    cell.font = _FONT_BOLD if bold else _FONT_NORMAL
    if center:
        cell.alignment = _ALIGN_CENTER_WRAP if wrap else _ALIGN_CENTER
    else:
        cell.alignment = _ALIGN_LEFT_WRAP if wrap else _ALIGN_LEFT
    cell.border = _CELL_BORDER


def _write_grouped_headers(ws, groups, *, vertical_merge_groups: set[str] | None = None):
    """Write the same two-level grouped header hierarchy used by the App grids.

    Returns the flattened column definitions in visual order.
    """
    vertical_merge_groups = vertical_merge_groups or set()
    flat_columns = []
    col = 1
    for group_name, _legacy_color, columns in groups:
        columns = tuple(columns)
        if not columns:
            continue
        start = col
        end = col + len(columns) - 1
        display_group = "" if not str(group_name).strip() else str(group_name)

        if len(columns) == 1 and group_name in vertical_merge_groups:
            ws.merge_cells(start_row=1, start_column=start, end_row=2, end_column=end)
            top_cell = ws.cell(1, start, display_group)
            _header_cell(top_cell, top=True)
        else:
            if end > start:
                ws.merge_cells(start_row=1, start_column=start, end_row=1, end_column=end)
            top_cell = ws.cell(1, start, display_group)
            _header_cell(top_cell, top=True)
            # Apply borders/fill to all physical cells in the merged span so the
            # exported header looks continuous in Excel/WPS/LibreOffice.
            for physical_col in range(start, end + 1):
                c = ws.cell(1, physical_col)
                c.fill = PatternFill("solid", fgColor=HEADER_TOP)
                c.border = _CELL_BORDER
            for offset, column in enumerate(columns):
                key, label, width = column
                c = ws.cell(2, start + offset, label)
                _header_cell(c, top=False)
                ws.column_dimensions[get_column_letter(start + offset)].width = _excel_width(width)
                flat_columns.append(column)
        if len(columns) == 1 and group_name in vertical_merge_groups:
            key, _label, width = columns[0]
            ws.column_dimensions[get_column_letter(start)].width = _excel_width(width)
            flat_columns.append(columns[0])
        col = end + 1

    ws.row_dimensions[1].height = 27
    ws.row_dimensions[2].height = 28
    return tuple(flat_columns)


def _analysis_row_fill(data: dict) -> str:
    """Excel row fill mirrors the App severity-only row-color contract."""
    return analysis_review_state(data).row_color


def _analysis_false_fill(key: str, value: str) -> str | None:
    if str(value or "").strip().upper() != "FALSE":
        return None
    labels = {
        "analysis_name": "NAME",
        "analysis_feeder": "FEEDER",
        "analysis_smart": "SMART",
        "analysis_type": "TYPE",
        "analysis_ip": "IP",
        "analysis_link": "LINK",
    }
    return field_false_color(labels.get(key, "")) or FALSE_NAME


def _add_rmu_color_explanation(ws) -> None:
    """Keep the export compact while embedding the App color meaning in Excel."""
    explanation = (
        "RMU Data Review color rules:\n"
        "Pass = pale green; any non-critical issue row = pale yellow; Critical = pale red. "
        "NAME=FALSE is always Critical; 3+ FALSE fields are also Critical.\n"
        "Every FALSE Analysis cell uses the same pale-red mismatch highlight. The column name identifies the failed field.\n"
        "Analysis / Remarks / Resolution stay neutral; row status color starts at Index and continues through source data."
    )
    ws["A1"].comment = Comment(explanation, "NARI Saudi ADMS Migration Report")
    # Add field-specific comments to the four Analysis subheaders when present.
    for cell in ws[2]:
        label = str(cell.value or "").strip().upper()
        if label in {"NAME", "FEEDER", "SMART", "TYPE", "IP", "LINK"}:
            cell.comment = Comment(
                f"FALSE means {label} is inconsistent across available sources. All FALSE cells use the same mismatch highlight.",
                "NARI Saudi ADMS Migration Report",
            )


def _build_rmu_data_review_sheet(wb, store: ProjectStore):
    if RMU_REVIEW_SHEET in wb.sheetnames:
        del wb[RMU_REVIEW_SHEET]
    ws = wb.create_sheet(RMU_REVIEW_SHEET, 0)

    review_group = (
        "Review",
        "#E8EDF3",
        (("rmu_review_status", "Review", 125),),
    )
    rmu_groups = (review_group,) + tuple(apply_display_names_to_groups(
        COMPARISON_GROUPS, store, RMU_REVIEW_DISPLAY_BINDINGS
    ))
    columns = _write_grouped_headers(
        ws,
        rmu_groups,
        vertical_merge_groups={"Remarks", "Resolution"},
    )
    _add_rmu_color_explanation(ws)
    analysis_keys = {"analysis_name", "analysis_feeder", "analysis_smart", "analysis_type", "analysis_ip", "analysis_link"}
    neutral_review_keys = analysis_keys | {"remarks", "comments", "rmu_review_status"}
    review_map = store.rmu_review_map()
    review_fills = {
        "NOT REQUIRED": REVIEW_NOT_REQUIRED,
        "UNREVIEWED": REVIEW_UNREVIEWED,
        "REVIEWED": REVIEWED,
        "NEEDS ACTION": NEEDS_ACTION,
        "VALIDATION REQUIRED": REVIEW_VALIDATION_REQUIRED,
    }

    for row_idx, data in enumerate(store.rows(), 3):
        row_fill = _analysis_row_fill(data)
        rmu = str(data.get("rmu", "") or "").strip()
        analysis_state = analysis_review_state(data)
        stored_review = str(review_map.get(rmu, {}).get("review_status") or "UNREVIEWED").strip().upper()
        review_status = (
            stored_review if analysis_state.issue_count > 0
            else stored_review if analysis_state.has_result and stored_review in {"REVIEWED", "NEEDS ACTION"}
            else "NOT REQUIRED" if analysis_state.has_result
            else "VALIDATION REQUIRED"
        )
        for col_idx, (key, _label, _width) in enumerate(columns, 1):
            value = (
                review_status if key == "rmu_review_status"
                else (
                    store.rmu_resolution_summary(rmu)
                    if analysis_state.issue_count > 0
                    else store.rmu_manual_review_comment(rmu)
                ) if key == "comments"
                else data.get(key, "")
            )
            if value is None:
                value = ""
            cell = ws.cell(row_idx, col_idx, value)

            # App contract: Analysis / Remarks / Resolution stay neutral. Only a
            # FALSE Analysis cell is emphasized. Index + source data carry the
            # row-level business status color.
            fill = WHITE if key in neutral_review_keys else row_fill
            if key == "rmu_review_status":
                fill = review_fills.get(review_status, "F3F4F6")
            false_fill = _analysis_false_fill(key, value) if key in analysis_keys else None
            if false_fill:
                fill = false_fill
            bold = key in analysis_keys or key in {"no", "rmu", "rmu_review_status"} or (key == "comments" and bool(str(value).strip()))
            center = key in analysis_keys or key in {"no", "rmu", "rmu_review_status"}
            wrap = key in {"remarks", "comments"}
            _body_cell(cell, fill=fill, bold=bold, center=center, wrap=wrap)
        ws.row_dimensions[row_idx].height = 22

    # Freeze the full App review block (Review + Analysis + Remarks + Resolution + Index).
    review_width = sum(len(cols) for group, _color, cols in rmu_groups if group in {"Review", "Analysis", "Remarks", "Resolution", "Index"})
    ws.freeze_panes = f"{get_column_letter(review_width + 1)}3"
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    return ws


def _signal_groups(report: DBSmartReport, store: ProjectStore):
    review_group = (
        "Review",
        "#E8EDF3",
        (
            ("db_review_status", "Review", 125),
            ("db_review_comments", "Comments", 300),
        ),
    )
    source_groups = apply_display_names_to_groups(
        report.group_definitions, store, SIGNAL_REVIEW_DISPLAY_BINDINGS
    )
    return (review_group,) + tuple(source_groups)


def _build_signal_mapping_review_sheet(wb, store: ProjectStore):
    if SIGNAL_REVIEW_SHEET in wb.sheetnames:
        del wb[SIGNAL_REVIEW_SHEET]
    ws = wb.create_sheet(SIGNAL_REVIEW_SHEET, 1)

    report = build_signal_mapping_report_from_store(store)
    groups = _signal_groups(report, store)
    columns = _write_grouped_headers(ws, groups)
    review_map = store.db_smart_review_map()

    signal_review_fills = {
        "NOT REQUIRED": REVIEW_NOT_REQUIRED,
        "UNREVIEWED": REVIEW_UNREVIEWED,
        "REVIEWED": REVIEWED,
        "NEEDS ACTION": NEEDS_ACTION,
        "VALIDATION REQUIRED": REVIEW_VALIDATION_REQUIRED,
    }
    for row_idx, source_row in enumerate(report.rows, 3):
        review = review_map.get(source_row.row_key, {})
        stored_status = str(review.get("review_status") or "UNREVIEWED").strip().upper() or "UNREVIEWED"
        analysis_result = ""
        if report.analysis_column is not None and report.analysis_column < len(source_row.values):
            analysis_result = str(source_row.values[report.analysis_column] or "").strip().upper()
        status = signal_review_display_status(analysis_result, stored_status)
        comments = str(review.get("comments") or "")
        values = [status, comments, *source_row.values]

        # Automatic validation determines the row tint; Human Review uses only
        # the Review cell. This keeps Matched and Reviewed visually distinct.
        base_fill = ROW_PASS if analysis_result == "TRUE" else ROW_ONE_ISSUE if analysis_result == "FALSE" else REVIEW_VALIDATION_REQUIRED
        for col_idx, ((key, _label, _width), value) in enumerate(zip(columns, values), 1):
            cell = ws.cell(row_idx, col_idx, value)
            fill = signal_review_fills.get(status, REVIEW_UNREVIEWED) if key == "db_review_status" else WHITE if key == "db_review_comments" else base_fill
            bold = key == "db_review_status"
            center = key == "db_review_status"
            wrap = key == "db_review_comments"

            # Source analysis column is highlighted exactly like the App view.
            source_index = col_idx - 3  # Review/Comments occupy the first two columns.
            if source_index == report.analysis_column:
                normalized = str(value or "").strip().upper()
                if normalized == "TRUE":
                    fill = ANALYSIS_TRUE
                elif normalized == "FALSE":
                    fill = ANALYSIS_FALSE
                bold = True
                center = True
                if source_row.analysis_detail:
                    cell.comment = Comment(source_row.analysis_detail, "NARI Saudi ADMS Migration Report")
            _body_cell(cell, fill=fill, bold=bold, center=center, wrap=wrap)
        ws.row_dimensions[row_idx].height = 22

    ws.freeze_panes = "C3"  # Review + Comments remain visible while scanning the mapping.
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    return ws


def _find_standard_sheet(wb):
    for name in wb.sheetnames:
        if name.strip().casefold() == STANDARD_SHEET.casefold():
            ws = wb[name]
            if ws.title != STANDARD_SHEET:
                ws.title = STANDARD_SHEET
            return ws
    raise ValueError("STANDARD sheet not found in the active IOA STANDARD workbook.")


def _build_import_sources_sheet(wb, store: ProjectStore):
    if IMPORT_SOURCES_SHEET in wb.sheetnames:
        del wb[IMPORT_SOURCES_SHEET]
    ws = wb.create_sheet(IMPORT_SOURCES_SHEET)
    headers = ["Source Type", "File", "System Field", "Display Name", "Actual Column", "Required", "Mapping Type", "Schema Status", "Site Workspace Path"]
    ws.append(headers)
    for key, label_and_filter in SOURCE_TYPES.items():
        path = store.source_path(key)
        schema = schema_for(key)
        if path and schema is not None:
            try:
                validation = validate_source_file(key, path, store.source_column_overrides(key))
            except Exception as exc:
                validation = None
                ws.append([label_and_filter[0], path.name, "", "", "", "", "", f"ERROR: {exc}", str(path)])
                continue
            if validation is not None:
                display_names = get_source_display_names(store, key)
                for mapping in validation.mappings:
                    ws.append([
                        label_and_filter[0], path.name, mapping.canonical_label,
                        field_display_name(store, key, mapping.canonical_key, mapping.canonical_label),
                        mapping.actual_column or "", "YES" if mapping.required else "NO", mapping.kind.value,
                        validation.level.value, str(path),
                    ])
                continue
        ws.append([label_and_filter[0], path.name if path else "", "", "", "", "", "", "N/A" if schema is None else "MISSING", str(path) if path else ""])

    # Application-owned STANDARD reference is deliberately not a Site Repository
    # source, but it is recorded here for full report traceability.
    standard_path = standard_reference_path()
    try:
        validation = validate_source_file("standard_reference", standard_path, store.source_column_overrides("standard_reference"))
        if validation is not None:
            display_names = get_source_display_names(store, "standard_reference")
            for mapping in validation.mappings:
                ws.append([
                    "IOA STANDARD Reference", standard_path.name, mapping.canonical_label,
                    field_display_name(store, "standard_reference", mapping.canonical_key, mapping.canonical_label),
                    mapping.actual_column or "", "YES" if mapping.required else "NO",
                    mapping.kind.value, validation.level.value, f"{standard_reference_origin()} application STANDARD",
                ])
    except Exception as exc:
        ws.append(["IOA STANDARD Reference", standard_path.name, "", "", "", "", "", f"ERROR: {exc}", f"{standard_reference_origin()} application STANDARD"])

    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="173A5E")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _CELL_BORDER
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = _CELL_BORDER
            cell.alignment = Alignment(vertical="center")
    for i, width in enumerate([28, 38, 25, 25, 28, 12, 18, 16, 75], 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.showGridLines = False
    return ws


def _build_audit_log_sheet(wb, store: ProjectStore):
    if AUDIT_LOG_SHEET in wb.sheetnames:
        del wb[AUDIT_LOG_SHEET]
    ws = wb.create_sheet(AUDIT_LOG_SHEET)
    headers = ["ID", "Module", "Record", "Field", "Original Value", "New Value", "Reason", "Modified By", "Modified At"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="173A5E")
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _CELL_BORDER
    for item in reversed(store.changes()):
        presented = present_audit_item(item)
        ws.append([presented[k] for k in ("id", "module", "record", "field", "original_value", "new_value", "reason", "modified_by", "modified_at")])
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = _CELL_BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column in {5, 6, 7})
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, width in enumerate([8, 24, 18, 28, 30, 30, 38, 18, 22], 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.sheet_view.showGridLines = False
    return ws


def export_report(store: ProjectStore) -> Path:
    """Export the App's two review views plus STANDARD and traceability sheets.

    The active STANDARD workbook is always closed deterministically.  This is
    important on Windows, where an exception before ``Workbook.close()`` would
    otherwise keep the source XLSX locked and could make release/test cleanup
    fail with ``WinError 32``.
    """
    source_report = standard_reference_path()
    if not source_report.exists():
        raise FileNotFoundError(f"Active STANDARD reference not found: {source_report}")

    wb = load_workbook(source_report)
    try:
        # STANDARD is application-managed. The active validated reference is used. Site
        # REPORT workbooks are intentionally not read by export or Signal Mapping.
        standard_ws = _find_standard_sheet(wb)

        # The active workbook should contain STANDARD only, but keep this
        # defensive cleanup so the formal delivery contract stays exactly five sheets.
        for sheet in list(wb.worksheets):
            if sheet is not standard_ws:
                wb.remove(sheet)

        rmu_ws = _build_rmu_data_review_sheet(wb, store)
        signal_ws = _build_signal_mapping_review_sheet(wb, store)
        sources_ws = _build_import_sources_sheet(wb, store)
        audit_ws = _build_audit_log_sheet(wb, store)

        wb._sheets = [rmu_ws, signal_ws, standard_ws, sources_ws, audit_ws]

        try:
            wb.calculation.calcMode = "auto"
            wb.calculation.fullCalcOnLoad = True
            wb.calculation.forceFullCalc = True
        except Exception:
            pass

        site_name = (
            store.config.get("site_name")
            or store.config.get("repository_site")
            or store.config.get("project_name")
            or store.folder.name
            or "Migration"
        )
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = store.reports_dir / f"{site_name}-REVIEW-{timestamp}.xlsx"
        wb.save(target)
        return target
    finally:
        wb.close()
