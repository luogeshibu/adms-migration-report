"""Printable site modification / issue-closure sign-off PDF export.

The PDF is generated from a frozen snapshot and then registered in the site's
persistent SQLite project database.  The source repository is never modified.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
import json
import re

from PySide6.QtCore import QLineF, QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen, QTextDocument

from ...version import __version__
from ...parsers import clean
from ...utils.paths import resource_root
from ...domain.analysis.resolution_text import compact_resolution_text, resolution_display_text
from ...domain.analysis.signal_action_comment import parse_signal_action_comment
from ...domain.analysis.severity import (
    analysis_review_state, review_record_is_explicit, rmu_review_display_status,
    signal_review_display_status,
)
from ...domain.mapping.signal_mapping import (
    build_signal_mapping_report_from_store, signal_review_alias_map, signal_review_metadata,
    signal_row_is_zenon_only,
)




def _report_header_geometry(writer: QPdfWriter, header: QImage) -> tuple[float, float, float, float]:
    page_width = float(writer.width())
    page_height = float(writer.height())
    natural_height = page_width * float(header.height()) / max(1.0, float(header.width()))
    header_height = min(natural_height, page_height * 0.075)
    divider_y = header_height + 4.0
    content_top = divider_y + 8.0
    return page_width, page_height, header_height, content_top


def _paint_report_header(painter: QPainter, writer: QPdfWriter, header: QImage) -> float:
    page_width, _page_height, header_height, content_top = _report_header_geometry(writer, header)
    painter.drawImage(
        QRectF(0.0, 0.0, page_width, header_height),
        header,
        QRectF(header.rect()),
    )
    painter.setPen(QPen(QColor("#cfd6de"), 1.0))
    painter.drawLine(QLineF(0.0, header_height + 4.0, page_width, header_height + 4.0))
    return content_top


def _body_page_number_height(writer: QPdfWriter) -> float:
    """Reserve a small footer band for body-page numbering only."""
    return max(20.0, float(writer.height()) * 0.024)


def _paint_body_page_number(
    painter: QPainter,
    writer: QPdfWriter,
    *,
    page_number: int,
    page_count: int,
) -> None:
    """Paint body numbering; the dedicated cover deliberately has no page number."""
    page_width = float(writer.width())
    page_height = float(writer.height())
    footer_height = _body_page_number_height(writer)
    font = QFont("Segoe UI", 7)
    painter.setFont(font)
    painter.setPen(QColor("#7b8794"))
    painter.drawText(
        QRectF(0.0, page_height - footer_height, page_width, footer_height * 0.72),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        f"Page {page_number} of {page_count}",
    )


def _paint_cover_page(
    painter: QPainter,
    writer: QPdfWriter,
    *,
    header: QImage,
    site: str,
    revision_name: str,
    report_date: str,
    prepared_by: str,
    company: str,
) -> None:
    """Paint the first-page data-migration cover inspired by the supplied project report.

    The content report remains unchanged and begins on the following page.  The
    cover deliberately reuses the same project logo strip as the body pages and
    the supplied NARI city artwork so exported site reports have one consistent
    customer-facing identity.
    """
    page_width, page_height, _header_height, _content_top = _report_header_geometry(writer, header)
    content_top = _paint_report_header(painter, writer, header)

    hero_path = resource_root() / "assets" / "data_migration_cover.png"
    hero = QImage(str(hero_path))
    margin_x = page_width * 0.085
    hero_top = content_top + page_height * 0.025
    hero_width = page_width - 2.0 * margin_x
    if not hero.isNull():
        hero_height = hero_width * float(hero.height()) / max(1.0, float(hero.width()))
        max_hero_height = page_height * 0.56
        if hero_height > max_hero_height:
            scale = max_hero_height / hero_height
            hero_height *= scale
            hero_width *= scale
            margin_x = (page_width - hero_width) / 2.0
        painter.drawImage(
            QRectF(margin_x, hero_top, hero_width, hero_height),
            hero,
            QRectF(hero.rect()),
        )
    else:
        hero_height = page_height * 0.48
        painter.fillRect(QRectF(margin_x, hero_top, hero_width, hero_height), QColor("#e9f1f8"))

    title_top = hero_top + hero_height + page_height * 0.018
    painter.setPen(QColor("#0f2742"))
    # Keep the formal report title on one balanced line.  The slightly smaller
    # font and wider title box prevent clipping while leaving clear separation
    # from the project subtitle below.
    title_font = QFont("Segoe UI", 15)
    title_font.setBold(True)
    painter.setFont(title_font)
    title_text = "DISTRIBUTION NETWORK DATA MIGRATION REPORT"
    title_left = page_width * 0.06
    title_width = page_width * 0.88
    title_height = page_height * 0.040
    painter.drawText(
        QRectF(title_left, title_top, title_width, title_height),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        title_text,
    )

    subtitle_top = title_top + page_height * 0.055
    subtitle_font = QFont("Segoe UI", 10)
    subtitle_font.setBold(True)
    painter.setFont(subtitle_font)
    painter.setPen(QColor("#52667a"))
    painter.drawText(
        QRectF(margin_x, subtitle_top, hero_width, page_height * 0.035),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        "SAUDI ADMS PROJECT - DATA MIGRATION",
    )

    accent_y = subtitle_top + page_height * 0.045
    painter.fillRect(
        QRectF(page_width * 0.22, accent_y, page_width * 0.56, 2.0),
        QColor("#168a84"),
    )

    info_top = accent_y + page_height * 0.024
    info_left = page_width * 0.19
    label_width = page_width * 0.18
    value_left = info_left + label_width
    value_width = page_width * 0.43
    row_height = page_height * 0.027
    info = [
        ("Project", "Saudi ADMS Project - Data Migration"),
        ("Station / Site", clean(site) or "-"),
        ("Revision", clean(revision_name) or f"v{__version__}"),
        ("Report Date", clean(report_date) or "-"),
        ("Prepared By", clean(prepared_by) or "-"),
    ]
    label_font = QFont("Segoe UI", 8)
    label_font.setBold(True)
    value_font = QFont("Segoe UI", 8)
    for idx, (label, value) in enumerate(info):
        y = info_top + idx * row_height
        painter.setPen(QColor("#9aa8b6"))
        painter.drawLine(QLineF(info_left, y + row_height, value_left + value_width, y + row_height))
        painter.setFont(label_font)
        painter.setPen(QColor("#0f2742"))
        painter.drawText(
            QRectF(info_left, y, label_width, row_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            label,
        )
        painter.setFont(value_font)
        painter.setPen(QColor("#263645"))
        painter.drawText(
            QRectF(value_left, y, value_width, row_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            str(value),
        )

    footer_font = QFont("Segoe UI", 7)
    painter.setFont(footer_font)
    painter.setPen(QColor("#7b8794"))
    painter.drawText(
        QRectF(margin_x, page_height - page_height * 0.045, hero_width, page_height * 0.02),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        f"Migration Report Tool v{__version__}",
    )


def _print_document_with_repeating_header(
    document: QTextDocument,
    writer: QPdfWriter,
    *,
    cover: dict | None = None,
) -> None:
    """Paint a dedicated cover, then paginate body content with the project header."""
    header_path = resource_root() / "assets" / "report_header.png"
    header = QImage(str(header_path))
    page_width = float(writer.width())
    page_height = float(writer.height())

    if header.isNull() or page_width <= 0 or page_height <= 0:
        document.setPageSize(QSizeF(page_width, page_height))
        document.print_(writer)
        return

    _page_width, _page_height, _header_height, content_top = _report_header_geometry(writer, header)
    page_number_height = _body_page_number_height(writer)
    content_height = max(120.0, page_height - content_top - page_number_height)
    document.setPageSize(QSizeF(page_width, content_height))
    page_count = max(1, int(document.pageCount()))

    painter = QPainter(writer)
    try:
        if cover is not None:
            _paint_cover_page(
                painter,
                writer,
                header=header,
                site=clean(cover.get("site")),
                revision_name=clean(cover.get("revision_name")),
                report_date=clean(cover.get("report_date")),
                prepared_by=clean(cover.get("prepared_by")),
                company=clean(cover.get("company")),
            )

        for page_index in range(page_count):
            if cover is not None or page_index:
                writer.newPage()

            _paint_report_header(painter, writer, header)
            painter.save()
            try:
                page_y = page_index * content_height
                painter.translate(0.0, content_top - page_y)
                document.drawContents(
                    painter,
                    QRectF(0.0, page_y, page_width, content_height),
                )
            finally:
                painter.restore()

            _paint_body_page_number(
                painter,
                writer,
                page_number=page_index + 1,
                page_count=page_count,
            )
    finally:
        painter.end()

def _safe_name(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", clean(value))
    return text.strip("._-") or "SITE"


def _status_counts(records: list[dict]) -> dict[str, int]:
    counter = Counter(clean(item.get("review_status")).upper() or "UNREVIEWED" for item in records)
    return dict(counter)



def _source_values_text(snapshot: dict) -> str:
    values = []
    for item in list((snapshot or {}).get("source_values") or []):
        source = clean((item or {}).get("source")) or "Source"
        raw = clean((item or {}).get("value"))
        normalized = clean((item or {}).get("normalized"))
        text = f"{source}: {raw or '<blank>'}"
        if normalized and normalized != raw:
            text += f" -> {normalized}"
        values.append(text)
    detail = clean((snapshot or {}).get("analysis_detail"))
    if values:
        return "\n".join(values)
    return detail or "Validation source values unavailable in this legacy decision."


def _structured_resolution_snapshot(store, rows: list[dict]) -> list[dict]:
    """Freeze current structured RMU resolutions into report-ready records."""
    rows_by_rmu = {}
    for row in rows:
        key = clean(row.get("review_key") or row.get("rmu"))
        if key:
            rows_by_rmu[key] = row
    flattened = []
    all_resolutions = store.rmu_resolution_map()
    for rmu in sorted(all_resolutions, key=lambda value: (not str(value).isdigit(), int(value) if str(value).isdigit() else str(value))):
        by_field = all_resolutions.get(rmu) or {}
        current_row = rows_by_rmu.get(rmu, {})
        field_order = (
            store._ordered_resolution_fields(by_field)
            if hasattr(store, "_ordered_resolution_fields")
            else list(getattr(store, "_RMU_ANALYSIS_FIELDS", ("NAME", "FEEDER", "SMART", "TYPE", "IP")))
        )
        for field in field_order:
            record = dict(by_field.get(field) or {})
            if not record:
                continue
            try:
                issue_snapshot = json.loads(clean(record.get("issue_snapshot_json")) or "{}")
            except Exception:
                issue_snapshot = {}
            if not issue_snapshot and current_row:
                issue_snapshot = store._resolution_issue_snapshot(current_row, field)
            decision = clean(record.get("decision_type")).upper()
            issue_label = clean(issue_snapshot.get("analysis_label")) or field
            flattened.append({
                "rmu": rmu,
                "issue": issue_label,
                "validation_values": _source_values_text(issue_snapshot),
                "analysis_detail": clean(issue_snapshot.get("analysis_detail")),
                "resolution": resolution_display_text(record),
                "customer_comment": clean(record.get("customer_comment")),
                "decision_type": decision,
                "status": "NEEDS ACTION" if decision == "NEEDS_ACTION" else "CLOSED",
                "modified_by": clean(record.get("modified_by")),
                "modified_at": clean(record.get("modified_at")),
            })
    return flattened

def _signal_row_value(report, row, key: str) -> str:
    index = next(
        (idx for idx, (column_key, _label, _width) in enumerate(report.columns) if column_key == key),
        None,
    )
    if index is None or index >= len(row.values):
        return ""
    return clean(row.values[index])


def _signal_point_number(report, row) -> int | None:
    """Use the same Signal Mapping point-number precedence as the UI."""
    for key in ("adms_dot_no", "standard_dot_no", "zenon_dot_no"):
        text = _signal_row_value(report, row, key)
        if not text:
            continue
        try:
            return int(float(text))
        except (TypeError, ValueError):
            match = re.search(r"-?\d+(?:\.\d+)?", text)
            if match:
                try:
                    return int(float(match.group(0)))
                except ValueError:
                    pass
    return None


def _signal_need_action_snapshot(store, report=None) -> tuple[list[dict], dict[str, int]]:
    """Freeze every site Signal row currently marked NEEDS ACTION.

    The export is a point-in-time view of the site's persistent review state.
    It therefore includes both newly-created and older unresolved NEEDS ACTION
    records.  Current STANDARD-driven rows, legacy source-row aliases, and saved
    per-review metadata are all used to keep Status/Cmd vs Analog classification
    complete without treating ZENON as part of STANDARD validation.
    """
    review_map = store.db_smart_review_map()
    site_name = clean(store.config.get("site_name") or store.config.get("repository_site") or store.folder.name)

    def belongs_to_site(review: dict) -> bool:
        recorded = clean((review or {}).get("site_name"))
        return not recorded or not site_name or recorded.casefold() == site_name.casefold()

    need_action_reviews = {
        key: value for key, value in review_map.items()
        if clean((value or {}).get("review_status")).upper() == "NEEDS ACTION" and belongs_to_site(value or {})
    }
    counts = {"TOTAL": len(need_action_reviews), "ANALOG": 0, "STATUS_CMD": 0, "UNCLASSIFIED": 0}
    if not need_action_reviews:
        return [], counts

    try:
        if report is None:
            report = build_signal_mapping_report_from_store(store)
    except Exception:
        report = None

    rows_by_key = {row.row_key: row for row in report.rows} if report is not None else {}
    aliases = signal_review_alias_map(report) if report is not None else {}

    # Older exported snapshots are a final recovery source for very old review
    # records created before point/category metadata was persisted.
    historical_by_key: dict[str, dict] = {}
    try:
        for exported in store.signoff_reports():
            try:
                snapshot = json.loads(clean(exported.get("snapshot_json")) or "{}")
            except Exception:
                continue
            for item in snapshot.get("signal_need_action_items", []) or []:
                key = clean((item or {}).get("row_key"))
                if key and key not in historical_by_key:
                    historical_by_key[key] = dict(item or {})
    except Exception:
        pass

    def review_snapshot(review: dict) -> dict:
        try:
            return json.loads(clean(review.get("signal_snapshot_json")) or "{}")
        except Exception:
            return {}

    def category_from(point_text: str, saved: str = "") -> tuple[str, str]:
        saved = clean(saved).upper()
        if saved in {"ANALOG", "STATUS_CMD"}:
            return saved, "Analog / Telemetry" if saved == "ANALOG" else "Status / Cmd"
        point_no = None
        try:
            point_no = int(float(clean(point_text))) if clean(point_text) else None
        except (TypeError, ValueError):
            match = re.search(r"-?\d+(?:\.\d+)?", clean(point_text))
            if match:
                try:
                    point_no = int(float(match.group(0)))
                except ValueError:
                    point_no = None
        if point_no is None:
            return "UNCLASSIFIED", "Unclassified"
        return ("ANALOG", "Analog / Telemetry") if point_no >= 13000 else ("STATUS_CMD", "Status / Cmd")

    items: list[dict] = []
    for stored_key, review in need_action_reviews.items():
        canonical_key = aliases.get(stored_key, stored_key)
        row = rows_by_key.get(canonical_key)
        saved_snapshot = review_snapshot(review)
        historical = historical_by_key.get(stored_key) or historical_by_key.get(canonical_key) or {}

        if row is not None and report is not None:
            current_meta = signal_review_metadata(report, row)
            point_text = clean(current_meta.get("point_no"))
            category_key, category_label = category_from(point_text, current_meta.get("signal_category"))
            standard_signal = _signal_row_value(report, row, "standard_signal_name")
            standard_dot = _signal_row_value(report, row, "standard_dot_no")
            adms_signal = _signal_row_value(report, row, "adms_signal_name")
            adms_dot = _signal_row_value(report, row, "adms_dot_no")
            zenon_signal = _signal_row_value(report, row, "zenon_signal_name")
            zenon_dot = _signal_row_value(report, row, "zenon_dot_no")
            rmu = clean(row.rmu) or clean(review.get("rmu"))
            detail = clean(getattr(row, "analysis_detail", ""))
        else:
            point_text = clean(review.get("point_no")) or clean(saved_snapshot.get("adms_dot")) or clean(saved_snapshot.get("standard_dot")) or clean(saved_snapshot.get("zenon_dot")) or clean(historical.get("adms_dot")) or clean(historical.get("standard_dot")) or clean(historical.get("zenon_dot"))
            category_key, category_label = category_from(point_text, review.get("signal_category") or historical.get("type"))
            standard_signal = clean(saved_snapshot.get("standard_signal")) or clean(historical.get("standard_signal"))
            standard_dot = clean(saved_snapshot.get("standard_dot")) or clean(historical.get("standard_dot"))
            adms_signal = clean(saved_snapshot.get("adms_signal")) or clean(historical.get("adms_signal"))
            adms_dot = clean(saved_snapshot.get("adms_dot")) or clean(historical.get("adms_dot"))
            zenon_signal = clean(saved_snapshot.get("zenon_signal")) or clean(historical.get("zenon_signal"))
            zenon_dot = clean(saved_snapshot.get("zenon_dot")) or clean(historical.get("zenon_dot"))
            rmu = clean(review.get("rmu")) or clean(saved_snapshot.get("rmu")) or clean(historical.get("rmu"))
            detail = clean(saved_snapshot.get("analysis_detail")) or clean(historical.get("required_action"))

        counts[category_key] += 1
        analysis = ""
        suggested_comment = ""
        if row is not None and report is not None:
            if report.analysis_column is not None and report.analysis_column < len(row.values):
                analysis = clean(row.values[report.analysis_column])
            suggested_comment = clean(getattr(row, "suggested_comment", ""))
        else:
            analysis = clean(saved_snapshot.get("analysis")) or clean(historical.get("analysis"))
            suggested_comment = clean(saved_snapshot.get("suggested_comment")) or clean(historical.get("suggested_comment"))

        # Keep the formal Signal register deterministic and traceable:
        # source structure decides ADD / DELETE / MODIFY; the application then
        # generates a compact customer-facing action remark.  Any reviewer text
        # is appended afterwards and never drives the normal STANDARD/ADMS action.
        item = {
            "row_key": stored_key,
            "canonical_row_key": canonical_key,
            "type": category_label,
            "rmu": rmu,
            "zenon_signal": zenon_signal,
            "zenon_dot": zenon_dot,
            "adms_signal": adms_signal,
            "adms_dot": adms_dot,
            "standard_signal": standard_signal,
            "standard_dot": standard_dot,
            "analysis": analysis,
            "analysis_detail": detail,
            "suggested_comment": suggested_comment,
            "user_comment": clean(review.get("comments")),
            "reviewed_by": clean(review.get("reviewed_by")),
            "reviewed_at": clean(review.get("reviewed_at")),
        }
        manual_action, manual_remark = parse_signal_action_comment(item.get("user_comment"))
        item["manual_action"] = manual_action
        item["manual_remark"] = manual_remark if manual_action else ""
        item["action"] = _signal_action_label(item)
        if manual_action:
            item["action"] = manual_action
        item["auto_remark"] = _signal_auto_resolution_text(item)
        item["required_action"] = _signal_combined_remarks(item)
        if manual_action:
            item["required_action"] = manual_remark
        items.append(item)

    type_order = {"Analog / Telemetry": 0, "Status / Cmd": 1, "Unclassified": 2}
    items.sort(key=lambda item: (
        type_order.get(clean(item.get("type")), 9),
        clean(item.get("rmu")),
        clean(item.get("adms_signal") or item.get("standard_signal") or item.get("zenon_signal")),
    ))
    return items, counts


def _signal_validation_summary(report) -> dict[str, float | int]:
    """Summarize current STANDARD ↔ ADMS Signal Mapping validation.

    ``differences`` is an analysis-only indicator: every current row whose
    STANDARD-vs-ADMS Analysis is FALSE.  It is deliberately *not* treated as an
    action/issue total.  Formal issue counts come only from persistent rows that
    the reviewer explicitly marks NEEDS ACTION.
    """
    if report is None:
        return {"standard_points": 0, "adms_points": 0, "matched": 0, "mismatched": 0, "differences": 0, "match_rate": 0.0}
    standard_points = 0
    adms_points = 0
    matched = 0
    adms_mismatched = 0
    differences = 0
    analysis_index = report.analysis_column
    for row in report.rows:
        result = clean(row.values[analysis_index]).upper() if analysis_index is not None and analysis_index < len(row.values) else ""
        if result == "FALSE":
            differences += 1

        standard_dot = _signal_row_value(report, row, "standard_dot_no")
        if standard_dot:
            standard_points += 1

        adms_dot = _signal_row_value(report, row, "adms_dot_no")
        if not adms_dot:
            continue
        adms_points += 1
        if result == "TRUE":
            matched += 1
        elif result == "FALSE":
            adms_mismatched += 1
    match_rate = (matched / adms_points * 100.0) if adms_points else 0.0
    return {
        "standard_points": standard_points,
        "adms_points": adms_points,
        "matched": matched,
        "mismatched": adms_mismatched,
        "differences": differences,
        "match_rate": match_rate,
    }


def _signal_review_state_summary(store, report, *, fallback_difference_count: int = 0) -> dict[str, int]:
    """Summarize only the formal Signal Needs Action lifecycle.

    ``need_action_total`` is the persistent set of Signal rows that have ever
    entered Needs Action. ``closed`` and ``pending`` are a partition of that set,
    therefore ``closed + pending == need_action_total`` by construction. Automatic
    mismatch/difference analysis is deliberately excluded from these workflow counts.
    """
    review_map = store.db_smart_review_map()
    site_name = clean(store.config.get("site_name") or store.config.get("repository_site") or store.folder.name)

    def belongs_to_site(review: dict) -> bool:
        recorded = clean((review or {}).get("site_name"))
        return not recorded or not site_name or recorded.casefold() == site_name.casefold()

    aliases = signal_review_alias_map(report) if report is not None else {}
    canonical_reviews: dict[str, dict] = {}
    for stored_key, record in review_map.items():
        record = record or {}
        if not belongs_to_site(record):
            continue
        canonical_key = aliases.get(stored_key, stored_key)
        existing = canonical_reviews.get(canonical_key)
        if existing is None or stored_key == canonical_key:
            canonical_reviews[canonical_key] = record
        elif int(record.get("ever_needs_action") or 0) and not int(existing.get("ever_needs_action") or 0):
            # Preserve the one-way lifecycle flag when a legacy alias and current
            # canonical key coexist during source-refresh identity migration.
            merged = dict(existing)
            merged["ever_needs_action"] = 1
            canonical_reviews[canonical_key] = merged

    total = 0
    closed = 0
    pending = 0
    needs_current = 0
    for record in canonical_reviews.values():
        raw_status = clean(record.get("review_status")).upper() or "UNREVIEWED"
        if raw_status == "REVIEWED":
            raw_status = "CLOSED"
        tracked = bool(int(record.get("ever_needs_action") or 0)) or raw_status == "NEEDS ACTION"
        if not tracked:
            continue
        total += 1
        if raw_status == "CLOSED":
            closed += 1
        else:
            pending += 1
        if raw_status == "NEEDS ACTION":
            needs_current += 1

    return {
        "differences": max(0, int(fallback_difference_count or 0)),
        "need_action_total": total,
        "closed": closed,
        "needs_action_current": needs_current,
        "pending": pending,
    }


def _load_issue_snapshot(record: dict) -> dict:
    try:
        return json.loads(clean((record or {}).get("issue_snapshot_json")) or "{}")
    except Exception:
        return {}


def _resolution_original_target_source(field: str, record: dict) -> tuple[str, str, str]:
    """Return compact original/target/source text for the RMU action register."""
    field = clean(field).upper()
    decision = clean((record or {}).get("decision_type")).upper()
    selected_source = clean((record or {}).get("selected_source"))
    selected_value = clean((record or {}).get("selected_value")) or clean((record or {}).get("normalized_value"))
    snapshot = _load_issue_snapshot(record)
    values = list(snapshot.get("source_values") or [])

    target = selected_value
    original_parts: list[str] = []
    for item in values:
        source = clean((item or {}).get("source")) or "Source"
        raw = clean((item or {}).get("value"))
        normalized = clean((item or {}).get("normalized"))
        display = raw or normalized or "<blank>"
        if decision == "USE_SOURCE" and selected_source and source.upper() == selected_source.upper():
            if not target:
                target = raw or normalized
            continue
        original_parts.append(f"{source}: {display}")

    if not original_parts and values:
        original_parts = [
            f"{clean((item or {}).get('source')) or 'Source'}: {clean((item or {}).get('value')) or clean((item or {}).get('normalized')) or '<blank>'}"
            for item in values
        ]

    if decision == "NEEDS_ACTION":
        target = target or "Not specified after corrective review"
        source_text = selected_source or "Corrective review"
    elif decision == "OTHER":
        target = target or "Per agreed comment"
        source_text = selected_source or "Manual review"
    elif decision == "ACCEPT_EXCEPTION":
        target = target or "Retain current value"
        source_text = selected_source or "Approved exception"
    else:
        source_text = selected_source or "Resolution"

    original = " | ".join(original_parts) or clean(snapshot.get("analysis_detail")) or "Current validated value(s)"
    return original, target or "<blank>", source_text


def _signal_source_present(item: dict, source: str) -> bool:
    source = clean(source).casefold()
    return bool(
        clean(item.get(f"{source}_signal"))
        or clean(item.get(f"{source}_dot"))
    )


def _signal_explicit_comment_action(item: dict) -> str:
    """Return an explicit action only for rows outside the STANDARD/ADMS pair.

    Normal Signal Mapping rows never use free-text keywords to decide their
    action.  This fallback exists only for ZENON-only/manual review rows where
    STANDARD and ADMS provide no structural action at all.
    """
    raw_text = clean(item.get("user_comment") or item.get("comments") or item.get("required_action"))
    structured_action, _structured_remark = parse_signal_action_comment(raw_text)
    if structured_action:
        return structured_action
    text = raw_text.casefold()
    if re.search(r"\b(delete|remove|drop)\b", text):
        return "DELETE"
    if re.search(r"\b(add|create|insert|new point)\b", text):
        return "ADD"
    if re.search(r"\b(modify|change|correct|update|align|replace)\b", text):
        return "MODIFY"
    return ""


def _signal_action_label(item: dict) -> str:
    """Derive a concrete ADD / MODIFY / DELETE rectification action.

    The formal register contains only rows explicitly marked NEEDS ACTION, so
    ``REVIEW`` is not a valid action. STANDARD remains authoritative for the
    normal comparison pair:

    * STANDARD exists, ADMS missing  -> ADD
    * STANDARD missing, ADMS exists  -> DELETE
    * STANDARD and ADMS both exist   -> MODIFY

    ZENON-only rows are outside STANDARD↔ADMS truth, but once the reviewer marks
    one NEEDS ACTION the PDF still needs a concrete field action.  If the App's
    semantic lookup found an existing ADMS implementation, use MODIFY; if no ADMS
    implementation is mapped, use ADD.  An explicit add/modify/delete reviewer
    comment may override this ZENON-only fallback only.
    """
    manual_action, _manual_remark = parse_signal_action_comment(
        item.get("user_comment") or item.get("comments")
    )
    if manual_action:
        return manual_action

    standard_present = _signal_source_present(item, "standard")
    adms_present = _signal_source_present(item, "adms")

    if standard_present and not adms_present:
        return "ADD"
    if adms_present and not standard_present:
        return "DELETE"
    if standard_present and adms_present:
        return "MODIFY"

    explicit = _signal_explicit_comment_action(item)
    if explicit:
        return explicit

    zenon_present = _signal_source_present(item, "zenon")
    if zenon_present:
        hint = clean(item.get("suggested_comment") or item.get("analysis_detail")).casefold()
        if "adms implementation:" in hint or "adms implementations:" in hint:
            return "MODIFY"
        return "ADD"

    # Legacy/manual NEEDS ACTION rows must still have a rectification verb in the
    # formal register. With no source shape available, MODIFY is the conservative
    # fallback and the Remarks retain the reviewer text for traceability.
    return "MODIFY"


def _signal_label(signal: str, dot: str) -> str:
    signal = clean(signal)
    dot = clean(dot)
    if dot and signal:
        return f"point {dot} '{signal}'"
    if dot:
        return f"point {dot}"
    if signal:
        return f"signal '{signal}'"
    return "signal point"


def _signal_auto_resolution_text(item: dict) -> str:
    """Build the compact App-generated remark for the Signal PDF register."""
    action = clean(item.get("action")) or _signal_action_label(item)
    standard_signal = clean(item.get("standard_signal"))
    standard_dot = clean(item.get("standard_dot"))
    adms_signal = clean(item.get("adms_signal"))
    adms_dot = clean(item.get("adms_dot"))
    zenon_signal = clean(item.get("zenon_signal"))
    zenon_dot = clean(item.get("zenon_dot"))

    if action == "ADD":
        if standard_signal or standard_dot:
            return (
                f"STANDARD requires {_signal_label(standard_signal, standard_dot)}, but ADMS has no corresponding point; "
                "add the STANDARD point to ADMS and re-run Validation."
            )
        if zenon_signal or zenon_dot:
            return (
                f"ZENON {_signal_label(zenon_signal, zenon_dot)} is marked Needs Action and no mapped ADMS implementation "
                "is available in the STANDARD/ADMS pair; add the agreed ADMS implementation and re-run Validation."
            )
        return "Add the agreed missing signal implementation and re-run Validation."

    if action == "DELETE":
        if adms_signal or adms_dot:
            return (
                f"ADMS {_signal_label(adms_signal, adms_dot)} is not defined in STANDARD for this RMU Type; "
                "remove the extra ADMS point and re-run Validation."
            )
        if zenon_signal or zenon_dot:
            return (
                f"ZENON {_signal_label(zenon_signal, zenon_dot)} is explicitly marked for removal; "
                "delete the agreed extra point and re-run Validation."
            )
        return "Delete the agreed extra signal implementation and re-run Validation."

    if action == "MODIFY":
        if standard_signal or standard_dot or adms_signal or adms_dot:
            mismatches: list[str] = []
            if standard_dot and adms_dot and standard_dot != adms_dot:
                mismatches.append(f"point number STANDARD {standard_dot} / ADMS {adms_dot}")
            if standard_signal and adms_signal and standard_signal.casefold() != adms_signal.casefold():
                mismatches.append(f"signal STANDARD '{standard_signal}' / ADMS '{adms_signal}'")
            if not mismatches:
                mismatches.append(
                    f"STANDARD {_signal_label(standard_signal, standard_dot)} / ADMS {_signal_label(adms_signal, adms_dot)}"
                )
            return "Mismatch: " + "; ".join(mismatches) + "; modify ADMS to the STANDARD value and re-run Validation."

        suggested = clean(item.get("suggested_comment"))
        if zenon_signal or zenon_dot:
            base = (
                f"ZENON {_signal_label(zenon_signal, zenon_dot)} is marked Needs Action; "
                "modify/align the located implementation according to the agreed value and re-run Validation."
            )
            return f"{suggested} {base}" if suggested else base
        return "Modify the agreed signal implementation and re-run Validation."

    return "Apply the agreed signal rectification and re-run Validation."


def _signal_combined_remarks(item: dict) -> str:
    """Use the paired reviewer remark for structured actions; preserve legacy exports."""
    auto = clean(item.get("auto_remark")) or _signal_auto_resolution_text(item)
    user = clean(item.get("user_comment") or item.get("comments"))
    manual_action, manual_remark = parse_signal_action_comment(user)
    if manual_action and manual_remark:
        return manual_remark

    # Legacy free-text comments keep the prior behavior so existing projects do
    # not silently lose the App-generated rectification context. New structured
    # Action / Remark entries intentionally output only the reviewer's remark.
    parts: list[str] = []
    if auto:
        parts.append(auto)
    if user and user.casefold() != auto.casefold():
        parts.append(f"User comment: {user}")
    return "\n".join(parts)


def _signal_register_point_no(item: dict) -> str:
    """Show the point number that belongs to the requested rectification target."""
    action = clean(item.get("action")) or _signal_action_label(item)
    if action == "ADD":
        return clean(item.get("standard_dot")) or clean(item.get("zenon_dot")) or "-"
    if action == "DELETE":
        return clean(item.get("adms_dot")) or clean(item.get("zenon_dot")) or clean(item.get("standard_dot")) or "-"
    if action == "MODIFY":
        adms_dot = clean(item.get("adms_dot"))
        if adms_dot:
            return adms_dot
        # ZENON-only rows can locate an existing ADMS implementation through the
        # App's semantic hint even though the row itself has no paired ADMS cell.
        hint = clean(item.get("suggested_comment") or item.get("analysis_detail"))
        match = re.search(r"\bADMS DOT\s+(-?\d+(?:\.\d+)?)", hint, re.IGNORECASE)
        if match:
            raw = match.group(1)
            try:
                value = float(raw)
                return str(int(value)) if value.is_integer() else raw
            except ValueError:
                return raw
        return clean(item.get("standard_dot")) or clean(item.get("zenon_dot")) or "-"
    return clean(item.get("zenon_dot")) or clean(item.get("adms_dot")) or clean(item.get("standard_dot")) or "-"


def _infer_manual_issue_types(*texts: object) -> list[str]:
    """Infer useful customer-facing issue categories from manual review text.

    Manual Needs Action can be created without a structured FALSE Analysis field.
    The PDF should still identify *what kind of issue* the reviewer is flagging
    instead of printing the review status itself as a fake "Modification Item".
    Inference is intentionally conservative: it recognizes common engineering
    field names/phrases and falls back to MANUAL REVIEW when no category is clear.
    """
    merged = " ".join(clean(value) for value in texts if clean(value))
    upper = merged.upper()
    if not upper:
        return ["MANUAL REVIEW"]

    result: list[str] = []

    def add(label: str) -> None:
        if label not in result:
            result.append(label)

    if re.search(r"\b(NAME|NAMING)\b", upper):
        add("NAME")
    if re.search(r"\bFEEDER\b", upper) or re.search(r"\b(MOVE|TRANSFER|REASSIGN)\b.{0,60}\bTO\b", upper):
        add("FEEDER")
    if re.search(r"\b(SMART|NONSMART|NOP)\b", upper):
        add("SMART")
    if re.search(r"\bTYPE\b", upper) or re.search(r"\b\d+\s*L\s*\d+\s*T?\b", upper):
        add("TYPE")
    if re.search(r"\bIP\b", upper) or re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", upper):
        add("IP")
    if re.search(r"\bBRAND\b", upper):
        add("BRAND")
    if re.search(r"\bDEVICE\b", upper) and "DEVICE TYPE" not in upper:
        add("DEVICE DATA")

    if not result and re.search(r"\b(MISSING DATA|NO DATA|SOURCE DATA|NO MATCH|ZENON DB|ADMS DB)\b", upper):
        add("SOURCE DATA")

    return result or ["MANUAL REVIEW"]


def _rmu_open_action_snapshot(store, rows: list[dict], tracking_rows: list[dict]) -> list[dict]:
    """Build the open equipment rectification register as one row per issue type.

    Any equipment can have multiple configured comparison issues. Older exports compressed all
    of them into one tall multi-line table row, which was hard to read and could
    split across a PDF page boundary. The formal snapshot now emits one compact
    row per issue/category. This also guarantees that every exported issue carries
    an explicit Issue Type wherever the available review data supports one.
    """
    rows_by_rmu = {}
    for row in rows:
        key = clean(row.get("review_key") or row.get("rmu"))
        if key:
            rows_by_rmu[key] = row
    reviews = store.rmu_review_map() if hasattr(store, "rmu_review_map") else {}
    all_resolutions = store.rmu_resolution_map() if hasattr(store, "rmu_resolution_map") else {}
    legacy_field_order = tuple(getattr(store, "_RMU_ANALYSIS_FIELDS", ("NAME", "FEEDER", "SMART", "TYPE", "IP")))

    def _field_order(row: dict, resolutions: dict) -> list[str]:
        configured = [clean(value).upper() for value in ((row or {}).get("analysis_field_order") or []) if clean(value)]
        if configured:
            return configured
        extras = sorted(field for field in resolutions if field not in legacy_field_order)
        return list(legacy_field_order) + extras

    def _field_label(row: dict, field: str) -> str:
        labels = dict((row or {}).get("analysis_field_labels") or {})
        for key, value in labels.items():
            if clean(key).upper() == clean(field).upper():
                return clean(value) or field
        return field

    def _analysis_value(row: dict, field: str) -> str:
        keys = dict((row or {}).get("analysis_field_keys") or {})
        for key, value_key in keys.items():
            if clean(key).upper() == clean(field).upper():
                return clean((row or {}).get(value_key)).upper()
        return clean((row or {}).get(f"analysis_{clean(field).lower()}")).upper()

    def _candidate_for_source(row: dict, field: str, source_name: str) -> dict:
        candidates = []
        for key, values in dict((row or {}).get("resolution_candidates") or {}).items():
            if clean(key).upper() == clean(field).upper():
                candidates = list(values or [])
                break
        wanted = clean(source_name).upper()
        for candidate in candidates:
            if clean((candidate or {}).get("source")).upper() == wanted:
                return dict(candidate or {})
        return {}

    def _snapshot_candidate(record: dict, source_name: str) -> dict:
        snapshot = _load_issue_snapshot(record)
        wanted = clean(source_name).upper()
        for candidate in list(snapshot.get("source_values") or []):
            if clean((candidate or {}).get("source")).upper() == wanted:
                return dict(candidate or {})
        return {}

    def _display_candidate(candidate: dict) -> str:
        return clean((candidate or {}).get("value")) or clean((candidate or {}).get("normalized")) or "Blank"

    def _equipment_identity(review_key: str, row: dict) -> tuple[str, str]:
        key = clean(review_key)
        display_name = clean((row or {}).get("rmu"))
        device_type = clean((row or {}).get("equipment_device_type")).upper()
        if key.startswith("EQ::"):
            parts = key.split("::", 2)
            if not device_type and len(parts) >= 2:
                device_type = clean(parts[1]).upper()
            if not display_name and len(parts) == 3:
                display_name = clean(parts[2])
        return display_name or key, device_type or ("RMU" if not key.startswith("EQ::") else "EQUIPMENT")

    def _action_row(
        *,
        rmu: str,
        equipment_name: str,
        equipment_type: str,
        issue_type: str,
        original_value: str,
        target_value: str,
        source: str,
        remarks: str,
        review: dict,
        tracker: dict,
    ) -> dict:
        issue_type = clean(issue_type) or "MANUAL REVIEW"
        original_value = clean(original_value) or "Not available in ADMS DB"
        target_value = clean(target_value) or "Not specified"
        source = clean(source) or "Manual review"
        remarks = clean(remarks)
        return {
            "rmu": rmu,
            "equipment_key": rmu,
            "equipment_name": equipment_name,
            "equipment_type": equipment_type,
            "issue_type": issue_type,
            "issues": issue_type,
            "adms_db_value": original_value,
            "user_value": target_value,
            "source": source,
            "comments": remarks,
            "original_value": original_value,
            "target_value": target_value,
            "remarks": remarks,
            "required_action": remarks,
            "reviewed_by": clean(review.get("reviewed_by")) or clean(tracker.get("opened_by")),
            "reviewed_at": clean(review.get("reviewed_at")) or clean(tracker.get("last_need_action_at")),
        }

    result: list[dict] = []
    for tracker in tracking_rows:
        if clean(tracker.get("tracking_status")).upper() != "OPEN":
            continue

        rmu = clean(tracker.get("equipment_key") or tracker.get("rmu"))
        row = rows_by_rmu.get(rmu, {})
        equipment_name, equipment_type = _equipment_identity(rmu, row)
        review = dict(reviews.get(rmu) or {})
        resolutions = dict(all_resolutions.get(rmu) or {})
        manual_comment = clean(review.get("manual_comment"))
        tracking_reason = clean(tracker.get("last_reason"))

        field_order = _field_order(row, resolutions)
        active_fields = [
            field for field in field_order
            if _analysis_value(row, field) == "FALSE"
        ]

        issue_fields = list(active_fields)
        if not issue_fields:
            issue_fields = [
                field for field in field_order
                if clean((resolutions.get(field) or {}).get("decision_type")).upper()
                in {"USE_SOURCE", "NEEDS_ACTION", "OTHER", "ACCEPT_EXCEPTION"}
            ]

        if issue_fields:
            for field_index, field in enumerate(issue_fields):
                record = dict(resolutions.get(field) or {})
                decision = clean(record.get("decision_type")).upper()

                remarks_parts: list[str] = []
                if decision:
                    generated_remark = clean(compact_resolution_text(record))
                    if generated_remark:
                        remarks_parts.append(generated_remark)
                customer_comment = clean(record.get("customer_comment"))
                if customer_comment:
                    remarks_parts.append(f"Customer comment: {customer_comment}")

                if manual_comment and field_index == 0:
                    remarks_parts.append(f"User comment: {manual_comment}")

                adms_candidate = (
                    _candidate_for_source(row, field, "ADMS DB")
                    or _snapshot_candidate(record, "ADMS DB")
                )
                original_value = (
                    _display_candidate(adms_candidate)
                    if adms_candidate
                    else "Not available in ADMS DB"
                )

                selected_source = clean(record.get("selected_source"))
                selected_value = clean(record.get("selected_value")) or clean(record.get("normalized_value"))

                if decision == "USE_SOURCE":
                    source_candidate = (
                        _candidate_for_source(row, field, selected_source)
                        or _snapshot_candidate(record, selected_source)
                    )
                    if not selected_value and source_candidate:
                        selected_value = _display_candidate(source_candidate)
                    target_value = selected_value or "Not specified"
                    source_text = selected_source or "Resolution"
                elif decision == "OTHER":
                    target_value = "See Remarks"
                    source_text = selected_source or "Others"
                elif decision == "NEEDS_ACTION":
                    target_value = selected_value or "Not specified"
                    source_text = selected_source or "Manual review"
                elif decision == "ACCEPT_EXCEPTION":
                    target_value = selected_value or (
                        _display_candidate(adms_candidate) if adms_candidate else "Not specified"
                    )
                    source_text = selected_source or "Approved exception"
                else:
                    target_value = "Not specified"
                    source_text = "Manual review"

                result.append(_action_row(
                    rmu=rmu,
                    equipment_name=equipment_name,
                    equipment_type=equipment_type,
                    issue_type=_field_label(row, field),
                    original_value=original_value,
                    target_value=target_value,
                    source=source_text,
                    remarks="\n".join(dict.fromkeys(part for part in remarks_parts if clean(part))),
                    review=review,
                    tracker=tracker,
                ))
            continue

        manual_types = _infer_manual_issue_types(manual_comment, tracking_reason)
        fallback_remarks = manual_comment
        if not fallback_remarks:
            generic_reason = tracking_reason.casefold()
            if generic_reason not in {
                "rmu needs action",
                "equipment data review marked needs action",
                "needs action",
            }:
                fallback_remarks = tracking_reason
        fallback_remarks = (
            f"User comment: {fallback_remarks}"
            if fallback_remarks
            else "Manual follow-up required; reviewer target value has not been specified."
        )

        for issue_type in manual_types:
            field = issue_type if issue_type in field_order else ""
            adms_candidate = _candidate_for_source(row, field, "ADMS DB") if field else {}
            original_value = (
                _display_candidate(adms_candidate)
                if adms_candidate
                else "Not available in ADMS DB"
            )
            result.append(_action_row(
                rmu=rmu,
                equipment_name=equipment_name,
                equipment_type=equipment_type,
                issue_type=issue_type,
                original_value=original_value,
                target_value="Not specified",
                source="Manual review",
                remarks=fallback_remarks,
                review=review,
                tracker=tracker,
            ))

    return result

def build_site_signoff_snapshot(store, *, revision: dict | None = None) -> dict:
    """Build a serializable point-in-time snapshot for the formal migration report."""
    rows = store.rows()
    rmu_review_map = store.rmu_review_map()
    rmu_reviews = list(rmu_review_map.values())
    signal_review_map = store.db_smart_review_map()
    signal_reviews = list(signal_review_map.values())
    issue_actions = store.issue_actions(revision.get("id") if revision else None)

    # Parse Signal Mapping once for both the summary and action registers.
    try:
        signal_report = build_signal_mapping_report_from_store(store)
    except Exception:
        signal_report = None
    signal_need_action_items, signal_need_action_counts = _signal_need_action_snapshot(store, signal_report)
    signal_validation = _signal_validation_summary(signal_report)
    if signal_report is None:
        persisted = dict(store.config.get("signal_validation_summary", {}) or {})
        checked = int(persisted.get("matched") or 0) + int(persisted.get("mismatched") or 0)
        signal_validation = {
            "standard_points": int(persisted.get("standard_points") or 0),
            "adms_points": int(persisted.get("adms_points") or persisted.get("total") or checked),
            "matched": int(persisted.get("matched") or 0),
            "mismatched": int(persisted.get("mismatched") or 0),
            "differences": int(persisted.get("mismatched") or 0),
            "match_rate": ((int(persisted.get("matched") or 0) / checked * 100.0) if checked else 0.0),
        }
    signal_review_state = _signal_review_state_summary(
        store,
        signal_report,
        fallback_difference_count=int(signal_validation.get("differences") or signal_validation.get("mismatched") or 0),
    )

    structured_resolutions = _structured_resolution_snapshot(store, rows)
    rmu_action_tracking = (
        store.equipment_action_tracking()
        if hasattr(store, "equipment_action_tracking")
        else (store.rmu_action_tracking() if hasattr(store, "rmu_action_tracking") else [])
    )
    rmu_action_tracking_counts = (
        store.equipment_action_tracking_counts()
        if hasattr(store, "equipment_action_tracking_counts")
        else (store.rmu_action_tracking_counts() if hasattr(store, "rmu_action_tracking_counts") else {"OPEN": 0, "CLOSED": 0, "TOTAL": 0})
    )
    rmu_open_actions = _rmu_open_action_snapshot(store, rows, rmu_action_tracking)
    site_name = (
        store.config.get("site_name")
        or store.config.get("repository_site")
        or store.folder.name
    )

    manual_rmu_checks = [
        {
            "rmu": clean(item.get("rmu")),
            "status": "PASS",
            "checked_by": clean(item.get("check_passed_by")),
            "checked_at": clean(item.get("check_passed_at")),
        }
        for item in rmu_reviews if bool(int(item.get("check_passed") or 0))
    ]

    # RMU automatic validation summary mirrors Project Overview semantics.
    rmu_states = [analysis_review_state(row) for row in rows]
    rmu_validation_pass = sum(state.is_pass for state in rmu_states)
    rmu_with_issues = sum(state.issue_count > 0 for state in rmu_states)
    rmu_review_closed = 0
    rmu_review_needs_current = 0
    for row, state in zip(rows, rmu_states):
        if state.issue_count <= 0:
            continue
        status = rmu_review_display_status(row, rmu_review_map.get(clean(row.get("rmu")), {}))
        if status == "CLOSED":
            rmu_review_closed += 1
        elif status == "NEEDS ACTION":
            rmu_review_needs_current += 1
    rmu_review_pending = max(0, rmu_with_issues - rmu_review_closed - rmu_review_needs_current)

    rmu_counts = _status_counts(rmu_reviews)
    signal_counts = _status_counts(signal_reviews)
    issue_result_counts = Counter(clean(item.get("result")).upper() or "OPEN" for item in issue_actions)
    needs_action = (
        int(rmu_action_tracking_counts.get("OPEN", 0))
        + signal_counts.get("NEEDS ACTION", 0)
        + issue_result_counts.get("NEEDS ACTION", 0)
        + issue_result_counts.get("OPEN", 0)
    )
    reviewed_or_closed = (
        rmu_counts.get("REVIEWED", 0)
        + rmu_counts.get("CLOSED", 0)
        + signal_counts.get("REVIEWED", 0)
        + signal_counts.get("CLOSED", 0)
        + issue_result_counts.get("PASS", 0)
        + issue_result_counts.get("CLOSED", 0)
    )

    return {
        "site": site_name,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "application_version": __version__,
        "revision": dict(revision or {}),
        "summary": {
            "rmu_records": len(rows),
            "rmu_validation_pass": rmu_validation_pass,
            "rmu_with_issues": rmu_with_issues,
            "rmu_review_closed": rmu_review_closed,
            "rmu_review_needs_current": rmu_review_needs_current,
            "rmu_review_pending": rmu_review_pending,
            "rmu_review_records": len(rmu_reviews),
            "rmu_checked_passed": len(manual_rmu_checks),
            "signal_review_records": len(signal_reviews),
            "signal_standard_points": int(signal_validation.get("standard_points", 0)),
            "signal_adms_points": int(signal_validation.get("adms_points", 0)),
            "signal_standard_matched": int(signal_validation.get("matched", 0)),
            "signal_standard_mismatched": int(signal_validation.get("mismatched", 0)),
            "signal_mismatch_info": int(signal_validation.get("differences", 0)),
            # Backward-compatible alias: in v0.8.115 an "issue" means an
            # explicitly open NEEDS ACTION item, not an automatic mismatch.
            "signal_with_issues": int(signal_need_action_counts.get("TOTAL", 0)),
            "signal_review_closed": int(signal_review_state.get("closed", 0)),
            "signal_review_needs_current": int(signal_review_state.get("needs_action_current", 0)),
            "signal_review_pending": int(signal_review_state.get("pending", 0)),
            "signal_match_rate": float(signal_validation.get("match_rate", 0.0)),
            "signal_need_action_total": int(signal_review_state.get("need_action_total", 0)),
            "signal_need_action_analog": int(signal_need_action_counts.get("ANALOG", 0)),
            "signal_need_action_status_cmd": int(signal_need_action_counts.get("STATUS_CMD", 0)),
            "signal_need_action_unclassified": int(signal_need_action_counts.get("UNCLASSIFIED", 0)),
            "manual_issue_actions": len(issue_actions),
            "structured_rmu_resolutions": len(structured_resolutions),
            "structured_rmu_needs_action": sum(1 for item in structured_resolutions if item.get("status") == "NEEDS ACTION"),
            "reviewed_or_closed": reviewed_or_closed,
            "needs_action": needs_action,
            "rmu_followup_open": int(rmu_action_tracking_counts.get("OPEN", 0)),
            "rmu_followup_closed": int(rmu_action_tracking_counts.get("CLOSED", 0)),
            "rmu_followup_total": int(rmu_action_tracking_counts.get("TOTAL", 0)),
            "rmu_open_issue_items": len(rmu_open_actions),
            # Generic aliases used by the current Equipment Data Review UI/PDF.
            # Legacy RMU keys remain for backward-compatible snapshots/tests.
            "equipment_records": len(rows),
            "equipment_validation_pass": rmu_validation_pass,
            "equipment_with_issues": rmu_with_issues,
            "equipment_review_closed": rmu_review_closed,
            "equipment_review_pending": rmu_review_pending,
            "equipment_followup_open": int(rmu_action_tracking_counts.get("OPEN", 0)),
            "equipment_followup_closed": int(rmu_action_tracking_counts.get("CLOSED", 0)),
            "equipment_followup_total": int(rmu_action_tracking_counts.get("TOTAL", 0)),
            "equipment_open_issue_items": len(rmu_open_actions),
        },
        "rmu_review_counts": rmu_counts,
        "signal_review_counts": signal_counts,
        "signal_validation_summary": signal_validation,
        "signal_need_action_items": signal_need_action_items,
        "signal_need_action_counts": signal_need_action_counts,
        "issue_result_counts": dict(issue_result_counts),
        "manual_rmu_checks": manual_rmu_checks,
        "rmu_action_tracking": rmu_action_tracking,
        "rmu_open_actions": rmu_open_actions,
        "structured_rmu_resolutions": structured_resolutions,
        "issue_actions": issue_actions,
    }


def _td(value: object, *, cls: str = "") -> str:
    klass = f' class="{cls}"' if cls else ""
    return f"<td{klass}>{escape(str(value or '')).replace(chr(10), '<br>')}</td>"


def _check_td() -> str:
    # Printed verification box: reviewers mark the placeholder with a check or
    # cross during issue confirmation / final verification.
    return '<td class="check-cell">&#9633;</td>'


def _rmu_action_tracking_rows(snapshot: dict) -> str:
    """Render the equipment rectification register (legacy function name retained)."""
    rows = []
    for idx, item in enumerate(snapshot.get("rmu_open_actions", []), 1):
        rows.append(
            "<tr>"
            + _td(idx, cls="num")
            + _td(item.get("equipment_type") or "EQUIPMENT")
            + _td(item.get("equipment_name") or item.get("rmu"))
            + _td(item.get("issue_type") or item.get("issues"), cls="issue-type")
            + _td(item.get("adms_db_value") or item.get("original_value"), cls="compact-text")
            + _td(item.get("user_value") or item.get("target_value"), cls="compact-text")
            + _td(item.get("source"), cls="compact-text")
            + _td(item.get("comments") or item.get("remarks"), cls="remarks-text")
            + _check_td()
            + _check_td()
            + "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="10" class="empty">No equipment is currently open for rectification.</td></tr>')
    return "".join(rows)

def _signal_need_action_rows(snapshot: dict, category: str) -> str:
    """Render one Status/Cmd or Analog register ordered by Point No. ascending."""
    rows = []
    items = [
        item for item in snapshot.get("signal_need_action_items", [])
        if clean(item.get("type")) == clean(category)
    ]

    def point_sort_key(item: dict):
        raw = clean(_signal_register_point_no(item))
        try:
            return (0, float(raw), clean(item.get("rmu")))
        except (TypeError, ValueError):
            match = re.search(r"-?\d+(?:\.\d+)?", raw)
            if match:
                try:
                    return (0, float(match.group(0)), clean(item.get("rmu")))
                except ValueError:
                    pass
        return (1, float("inf"), clean(item.get("rmu")), raw)

    items.sort(key=point_sort_key)
    for idx, item in enumerate(items, 1):
        rows.append(
            "<tr>"
            + _td(idx, cls="num")
            + _td(item.get("rmu"))
            + _td(_signal_register_point_no(item))
            + _td(item.get("action") or _signal_action_label(item), cls="action-cell")
            + _td(item.get("required_action") or _signal_combined_remarks(item), cls="remarks-text")
            + _check_td()
            + _check_td()
            + "</tr>"
        )
    if not rows:
        rows.append(
            f'<tr><td colspan="7" class="empty">No {escape(category)} signals are currently marked Needs Action.</td></tr>'
        )
    return "".join(rows)


def _display_revision_name(revision: dict | None) -> str:
    """Return a customer-facing revision label without an ambiguous Current fallback."""
    raw = clean((revision or {}).get("revision_name"))
    if raw and raw.upper() not in {"CURRENT", "LATEST"}:
        return raw
    return f"v{__version__}"


def _html(snapshot: dict, *, prepared_by: str = "", company: str = "NARI") -> str:
    revision = snapshot.get("revision") or {}
    summary = snapshot.get("summary") or {}
    site = snapshot.get("site") or "-"
    generated = snapshot.get("generated_at") or ""
    report_date = generated[:10]
    revision_name = _display_revision_name(revision)
    revision_desc = revision.get("description") or ""
    document_status = clean(snapshot.get("document_status"))
    draft_banner = (
        '<div class="draft-banner">REVIEW DRAFT · VALIDATION REQUIRED · NOT FOR FINAL HANDOVER / SIGNATURE</div>'
        if document_status == "REVIEW DRAFT"
        else ""
    )

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 9pt; color: #18212f; line-height: 1.30; }}
h1 {{ text-align:center; font-size:18pt; margin:0; color:#0f2742; }}
h2 {{ font-size:12.5pt; color:#0f2742; margin:18px 0 8px 0; border-bottom:1px solid #cfd8e3; padding-bottom:4px; page-break-after:avoid; }}
.subtitle {{ text-align:center; color:#52667a; font-size:10pt; margin:4px 0 16px 0; }}
.draft-banner {{ text-align:center; border:2px solid #b54708; background:#fff4e5; color:#8a3208; font-weight:800; font-size:10pt; padding:8px 10px; margin:0 0 12px 0; }}
.meta, .summary, .grid {{ width:100%; min-width:100%; border-collapse:collapse; margin:6px 0 12px 0; table-layout:fixed; }}
.meta td, .summary td {{ border:1px solid #d7e0e8; padding:6px 7px; }}
.meta .label, .summary .label {{ background:#f2f6f9; font-weight:600; }}
.summary .group {{ background:#dfeaf4; color:#0f2742; font-weight:700; font-size:9.5pt; letter-spacing:.1px; }}
.grid thead {{ display:table-header-group; }}
.grid tbody {{ display:table-row-group; }}
.grid tr {{ page-break-inside:avoid; break-inside:avoid; }}
.grid thead tr {{ page-break-after:avoid; break-after:avoid; }}
.grid th {{ background:#0f2742; color:white; border:1px solid #0f2742; padding:5px 3px; font-size:7.6pt; vertical-align:middle; }}
.grid td {{ border:1px solid #cfd8e3; padding:4px 3px; vertical-align:top; font-size:7.3pt; overflow-wrap:break-word; word-wrap:break-word; }}
.grid .num {{ text-align:center; }}
.grid .issue-type {{ font-weight:700; }}
.grid .compact-text {{ font-size:7.0pt; line-height:1.25; }}
.grid .remarks-text {{ font-size:7.0pt; line-height:1.30; }}
.grid .action-cell {{ text-align:center; font-weight:700; }}
.grid .check-cell {{ text-align:center; vertical-align:middle; font-size:17pt; font-weight:700; line-height:1; }}
.empty {{ color:#667085; text-align:center; padding:12px !important; }}
.small {{ color:#667085; font-size:8pt; margin:4px 0 8px 0; }}
.verification-note {{ color:#52667a; font-size:7.8pt; margin:2px 0 7px 0; padding:5px 7px; background:#f8fafc; border-left:3px solid #28578a; }}
.signoff {{ width:100%; min-width:100%; border-collapse:collapse; margin-top:18px; table-layout:fixed; page-break-inside:avoid; }}
.signoff th, .signoff td {{ border:1px solid #263645; padding:8px; vertical-align:middle; }}
.signoff thead th {{ background:#28578a; color:white; text-align:center; font-size:10pt; font-weight:600; height:40px; }}
.signoff thead th.stub {{ background:white; border-top:1px solid #263645; color:#18212f; }}
.signoff tbody th {{ background:#28578a; color:white; text-align:center; font-size:9.5pt; font-weight:600; }}
.signoff tbody td {{ height:58px; }}
.workflow-note {{ background:#f8fafc; border:1px solid #d7e0e8; padding:7px 9px; color:#52667a; margin:6px 0 8px 0; }}
.signoff-block {{ page-break-inside:avoid; margin-top:22px; }}
.signoff-block + .signoff-block {{ margin-top:46px; padding-top:8px; }}
.signoff-gap {{ height:32px; line-height:32px; font-size:1px; }}
.signoff-heading {{ margin-top:0; page-break-after:avoid; }}
</style>
</head>
<body>
<h1>STATION MODIFICATION &amp; ISSUE CLOSURE REPORT</h1>
<div class="subtitle">Saudi ADMS Project - Distribution Network Data Migration Review</div>
{draft_banner}

<table class="meta" width="100%" cellspacing="0" cellpadding="0">
<colgroup><col width="18%"><col width="22%"><col width="18%"><col width="42%"></colgroup>
<tr><td class="label">Station / Site</td><td>{escape(str(site))}</td><td class="label">Revision</td><td>{escape(str(revision_name))}</td></tr>
<tr><td class="label">Report Date</td><td>{escape(report_date)}</td><td class="label">Prepared By</td><td>{escape(clean(prepared_by) or '-')}</td></tr>
<tr><td class="label">Application</td><td>Migration Report Tool v{escape(__version__)}</td><td class="label">Revision Notes</td><td>{escape(str(revision_desc or '-'))}</td></tr>
</table>

<h2>Equipment Data Summary</h2>
<table class="summary" width="100%" cellspacing="0" cellpadding="0">
<colgroup><col width="23%"><col width="10%"><col width="23%"><col width="10%"><col width="24%"><col width="10%"></colgroup>
<tr><td class="label">Total Equipment</td><td>{summary.get('equipment_records', summary.get('rmu_records', 0))}</td><td class="label">Validation Pass</td><td>{summary.get('equipment_validation_pass', summary.get('rmu_validation_pass', 0))}</td><td class="label">Equipment With Issues</td><td>{summary.get('equipment_with_issues', summary.get('rmu_with_issues', 0))}</td></tr>
<tr><td class="label">Review Passed / Closed</td><td>{summary.get('equipment_review_closed', summary.get('rmu_review_closed', 0))}</td><td class="label">Need Action / Open</td><td>{summary.get('equipment_followup_open', summary.get('rmu_followup_open', 0))}</td><td class="label">Pending Review</td><td>{summary.get('equipment_review_pending', summary.get('rmu_review_pending', 0))}</td></tr>
</table>

<h2>Signal Data Summary</h2>
<table class="summary" width="100%" cellspacing="0" cellpadding="0">
<colgroup><col width="23%"><col width="10%"><col width="23%"><col width="10%"><col width="24%"><col width="10%"></colgroup>
<tbody>
<tr><td class="label">STANDARD Point Numbers</td><td>{summary.get('signal_standard_points', 0)}</td><td class="label">ADMS Point Numbers</td><td>{summary.get('signal_adms_points', 0)}</td><td class="label">Matched to STANDARD</td><td>{summary.get('signal_standard_matched', 0)}</td></tr>
<tr><td class="label">Need Action Total</td><td>{summary.get('signal_need_action_total', 0)}</td><td class="label">Closed</td><td>{summary.get('signal_review_closed', 0)}</td><td class="label">Pending / Open</td><td>{summary.get('signal_review_pending', 0)}</td></tr>
</tbody></table>

<h2>Equipment Need Action Register ({summary.get('equipment_followup_open', summary.get('rmu_followup_open', 0))} equipment / {summary.get('equipment_open_issue_items', summary.get('rmu_open_issue_items', 0))} issues)</h2>
<p class="small">One row represents one issue type / field. Issue Type identifies the affected category (for example FEEDER, SMART, TYPE, IP or SOURCE DATA). Original Value shows the current ADMS-DB value when available. Target Value shows the agreed reviewer value; <b>Not specified</b> means no target value has been provided yet. Remarks contains the App-generated Resolution text plus any reviewer-entered comment.</p>
<p class="verification-note">Verification marking: mark &#10003; in the box to confirm/accept, or &#10007; to reject/not confirm.</p>
<table class="grid" width="100%" cellspacing="0" cellpadding="0">
<colgroup>
<col width="4%"><col width="8%"><col width="10%"><col width="10%"><col width="13%"><col width="13%"><col width="10%"><col width="18%"><col width="7%"><col width="7%">
</colgroup>
<thead><tr><th>No.</th><th>Type</th><th>Equipment</th><th>Issue Type</th><th>Original Value</th><th>Target Value</th><th>Source</th><th>Remarks</th><th>NARI Confirm</th><th>SE/DNV Verify</th></tr></thead>
<tbody>{_rmu_action_tracking_rows(snapshot)}</tbody>
</table>

<h2>Status / Cmd Need Action Register ({summary.get('signal_need_action_status_cmd', 0)})</h2>
<p class="small">Status / Cmd uses the application boundary DOT &lt; 13000. Signal Action is taken from the reviewer's Action / Remark entry in the App (ADD / MODIFY / DELETE), and PDF Remarks contains the paired reviewer remark. For legacy Needs Action rows without a structured entry, the source fallback remains: missing ADMS = ADD, extra ADMS = DELETE, existing STANDARD/ADMS pair = MODIFY.</p>
<p class="verification-note">Verification marking: mark &#10003; in the box to confirm/accept, or &#10007; to reject/not confirm.</p>
<table class="grid" width="100%" cellspacing="0" cellpadding="0">
<colgroup><col width="5%"><col width="12%"><col width="13%"><col width="12%"><col width="42%"><col width="8%"><col width="8%"></colgroup>
<thead><tr><th>No.</th><th>RMU</th><th>Point No.</th><th>Action</th><th>Remarks</th><th>NARI Confirm</th><th>SE/DNV Verify</th></tr></thead>
<tbody>{_signal_need_action_rows(snapshot, "Status / Cmd")}</tbody>
</table>

<h2>Analog Need Action Register ({summary.get('signal_need_action_analog', 0)})</h2>
<p class="small">Analog uses the application boundary DOT &gt;= 13000.</p>
<p class="verification-note">Verification marking: mark &#10003; in the box to confirm/accept, or &#10007; to reject/not confirm.</p>
<table class="grid" width="100%" cellspacing="0" cellpadding="0">
<colgroup><col width="5%"><col width="12%"><col width="13%"><col width="12%"><col width="42%"><col width="8%"><col width="8%"></colgroup>
<thead><tr><th>No.</th><th>RMU</th><th>Point No.</th><th>Action</th><th>Remarks</th><th>NARI Confirm</th><th>SE/DNV Verify</th></tr></thead>
<tbody>{_signal_need_action_rows(snapshot, "Analog / Telemetry")}</tbody>
</table>

<div class="signoff-block">
<h2 class="signoff-heading">Issue Confirmation / Acceptance</h2>
<div class="workflow-note">SE confirms the identified issues on the left. ALF/CET/NARI acknowledges the listed issues and accepts them for rectification on the right.</div>
<table class="signoff" width="100%" cellspacing="0" cellpadding="0">
<colgroup><col width="9%"><col width="45.5%"><col width="45.5%"></colgroup>
<thead>
<tr><th class="stub" width="9%"></th><th>SE</th><th>ALF/CET/NARI</th></tr>
</thead>
<tbody>
<tr><th width="9%">Name</th><td></td><td>Jia Wei</td></tr>
<tr><th width="9%">Signature</th><td></td><td></td></tr>
<tr><th width="9%">Job Title</th><td></td><td></td></tr>
<tr><th width="9%">Date</th><td></td><td></td></tr>
</tbody>
</table>
</div>

<div class="signoff-gap">&nbsp;</div>

<div class="signoff-block">
<h2 class="signoff-heading">Final Rectification Sign-off</h2>
<div class="workflow-note">After all listed rectification items are completed, ALF/CET/NARI resubmits the updated data. PDC/DNV and SE review the completed rectification for final closure.</div>
<table class="signoff" width="100%" cellspacing="0" cellpadding="0">
<colgroup><col width="9%"><col width="30.33%"><col width="30.33%"><col width="30.34%"></colgroup>
<thead>
<tr><th class="stub" width="9%"></th><th>ALF/CET/NARI</th><th>PDC/DNV</th><th>SE</th></tr>
</thead>
<tbody>
<tr><th width="9%">Name</th><td>Jia Wei</td><td></td><td></td></tr>
<tr><th width="9%">Signature</th><td></td><td></td><td></td></tr>
<tr><th width="9%">Job Title</th><td></td><td></td><td></td></tr>
<tr><th width="9%">Date</th><td></td><td></td><td></td></tr>
</tbody>
</table>
</div>
</body>
</html>"""


def export_site_signoff_pdf(
    store,
    *,
    revision: dict | None,
    prepared_by: str,
    company: str = "NARI",
    review_draft: bool = False,
    target_path: Path | None = None,
) -> tuple[Path, dict]:
    """Generate the PDF in the persistent site report directory.

    Returns ``(path, snapshot)``. Registration in ``signoff_reports`` is kept
    outside this function so callers can handle errors before committing metadata.
    """
    snapshot = build_site_signoff_snapshot(store, revision=revision)
    snapshot["document_status"] = "REVIEW DRAFT" if review_draft else "FORMAL"
    snapshot["validation_required_at_export"] = bool(
        store.config.get("validation_required_after_source_import", False)
    )
    site = _safe_name(snapshot.get("site") or store.folder.name)
    rev = _safe_name(_display_revision_name(revision))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    draft_token = "_DRAFT" if review_draft else ""
    if target_path is None:
        target = store.reports_dir / f"{site}_{rev}_Issue_Closure{draft_token}_{stamp}.pdf"
    else:
        target = Path(target_path).expanduser()
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
        target.parent.mkdir(parents=True, exist_ok=True)

    writer = QPdfWriter(str(target))
    writer.setTitle(f"{site} Distribution Network Data Migration Report")
    writer.setCreator(f"Migration Report Tool v{__version__}")
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter)
    writer.setResolution(120)

    document = QTextDocument()
    document.setDocumentMargin(8)
    document.setHtml(_html(snapshot, prepared_by=prepared_by, company=company))
    _print_document_with_repeating_header(
        document,
        writer,
        cover={
            "site": snapshot.get("site"),
            "revision_name": _display_revision_name(snapshot.get("revision") or {}),
            "report_date": clean(snapshot.get("generated_at"))[:10],
            "prepared_by": prepared_by,
            "company": company,
        },
    )
    return target, snapshot
