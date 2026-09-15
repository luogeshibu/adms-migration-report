"""Shared RMU review-status semantics used by UI and Excel export.

The review UI intentionally uses a minimal color system:

* row color = pass / issue / critical severity;
* every FALSE Analysis cell uses one shared mismatch highlight.

The column header already identifies NAME / FEEDER / SMART / TYPE / IP,
so field-specific colors are deliberately avoided. This keeps the formal review
grid readable and prevents color meaning from becoming ambiguous.
"""
from __future__ import annotations

from dataclasses import dataclass

ANALYSIS_FIELDS = (
    ("NAME", "analysis_name"),
    ("FEEDER", "analysis_feeder"),
    ("SMART", "analysis_smart"),
    ("TYPE", "analysis_type"),
    ("IP", "analysis_ip"),
)

ROW_COLORS = {
    "none": "FFFFFF",
    "pass": "EAF7F0",
    # One-issue and two-issue rows intentionally share one issue color. The
    # Analysis label still shows the exact count, so another color is redundant.
    "one_issue": "FFF8D8",
    "two_issues": "FFF8D8",
    "critical": "FDECEC",
}

FALSE_MISMATCH_COLOR = "F7D7D7"
FALSE_CELL_COLORS = {label: FALSE_MISMATCH_COLOR for label, _key in ANALYSIS_FIELDS}


@dataclass(frozen=True)
class AnalysisReviewState:
    has_result: bool
    false_fields: tuple[str, ...]
    issue_count: int
    row_status: str
    row_label: str
    row_color: str

    @property
    def is_pass(self) -> bool:
        return self.has_result and self.issue_count == 0

    @property
    def is_critical(self) -> bool:
        return self.row_status == "critical"


def analysis_review_state(data: dict) -> AnalysisReviewState:
    # v0.8.178: Equipment Data Review may expose a site-configured set of
    # comparison rules.  Rows carry stable internal rule ids plus the generated
    # value keys.  Legacy NAME/FEEDER/SMART/TYPE/IP rows remain fully supported.
    dynamic_order = list((data or {}).get("analysis_field_order") or [])
    dynamic_keys = dict((data or {}).get("analysis_field_keys") or {})
    dynamic_labels = dict((data or {}).get("analysis_field_labels") or {})
    if dynamic_order:
        normalized = {
            field_id: str((data or {}).get(dynamic_keys.get(field_id) or f"analysis__{field_id}") or "").strip().upper()
            for field_id in dynamic_order
        }
        has_result = any(value in {"TRUE", "FALSE"} for value in normalized.values())
        false_fields = tuple(field_id for field_id in dynamic_order if normalized.get(field_id) == "FALSE")
        issue_count = len(false_fields)
        false_display = {str(dynamic_labels.get(field_id) or field_id).strip().upper() for field_id in false_fields}
    else:
        normalized = {
            label: str(data.get(key) or "").strip().upper()
            for label, key in ANALYSIS_FIELDS
        }
        has_result = any(value in {"TRUE", "FALSE"} for value in normalized.values())
        false_fields = tuple(label for label, _key in ANALYSIS_FIELDS if normalized[label] == "FALSE")
        issue_count = len(false_fields)
        false_display = set(false_fields)

    if not has_result:
        status = "none"
        label = "No analysis"
    elif issue_count == 0:
        status = "pass"
        label = "Pass"
    elif "NAME" in false_display or issue_count >= 3:
        # Preserve the historical NAME priority when a configured rule is named
        # NAME.  Otherwise 3+ independent configured mismatches are Critical.
        status = "critical"
        label = "Critical / NAME" if "NAME" in false_display else "Critical"
    elif issue_count == 1:
        status = "one_issue"
        label = "1 Issue"
    else:
        status = "two_issues"
        label = "2 Issues"

    return AnalysisReviewState(
        has_result=has_result,
        false_fields=false_fields,
        issue_count=issue_count,
        row_status=status,
        row_label=label,
        row_color=ROW_COLORS[status],
    )


def field_false_color(field_label: str) -> str | None:
    return FALSE_CELL_COLORS.get(str(field_label).strip().upper())


def normalize_review_status(stored_status: object) -> str:
    """Normalize legacy review values to the three-state workflow.

    v0.8.47 intentionally exposes only UNREVIEWED, CLOSED and NEEDS ACTION.
    Historical REVIEWED records are semantically completed work and therefore
    map to CLOSED without discarding their audit history.
    """
    value = str(stored_status or "").strip().upper() or "UNREVIEWED"
    if value == "REVIEWED":
        return "CLOSED"
    if value in {"UNREVIEWED", "CLOSED", "NEEDS ACTION"}:
        return value
    return "UNREVIEWED"


def review_record_is_explicit(review_record: object) -> bool:
    """Return True when a stored review row represents an explicit workflow state."""
    if not isinstance(review_record, dict):
        return False
    raw = str(review_record.get("review_status") or "").strip().upper()
    # CLOSED / NEEDS ACTION / legacy REVIEWED are always explicit.  UNREVIEWED
    # is explicit only when reviewer metadata exists; automatically-created RMU
    # fingerprint rows also store UNREVIEWED but deliberately leave metadata blank.
    if raw in {"CLOSED", "NEEDS ACTION", "REVIEWED"}:
        return True
    return bool(str(review_record.get("reviewed_by") or "").strip() or str(review_record.get("reviewed_at") or "").strip())


def rmu_review_display_status(data: dict, review_record: object = None) -> str:
    """Return one of UNREVIEWED / CLOSED / NEEDS ACTION for an RMU row.

    Automatic Analysis remains unchanged.  A passing RMU defaults to CLOSED;
    exception or not-yet-analysed rows default to UNREVIEWED.  Any explicit
    three-state human decision overrides that default.
    """
    record = review_record if isinstance(review_record, dict) else {}
    stored = normalize_review_status(record.get("review_status"))
    if review_record_is_explicit(record):
        return stored
    return "CLOSED" if analysis_review_state(data).is_pass else "UNREVIEWED"


def signal_review_display_status(
    analysis_result: object,
    stored_status: object = None,
    *,
    explicit: bool = False,
    zenon_only: bool = False,
) -> str:
    """Return the visible three-state Signal Mapping review status.

    Rules:
    * explicit human state wins;
    * matched/TRUE signals default to CLOSED;
    * ZENON-only signals also default to CLOSED (accepted legacy-only points);
    * all remaining rows default to UNREVIEWED.

    Automatic validation values are not rewritten by this display rule.
    """
    stored = normalize_review_status(stored_status)
    raw = str(stored_status or "").strip().upper()
    if explicit or raw in {"CLOSED", "NEEDS ACTION", "REVIEWED"}:
        return stored
    result = str(analysis_result or "").strip().upper()
    if result == "TRUE" or zenon_only:
        return "CLOSED"
    return "UNREVIEWED"
