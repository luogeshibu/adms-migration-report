"""Shared RMU review-status semantics used by UI and Excel export.

The review UI intentionally uses a minimal color system:

* row color = pass / issue / critical severity;
* every FALSE Analysis cell uses one shared mismatch highlight.

The column header already identifies NAME / FEEDER / SMART / TYPE / IP / LINK,
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
    ("LINK", "analysis_link"),
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
    normalized = {
        label: str(data.get(key) or "").strip().upper()
        for label, key in ANALYSIS_FIELDS
    }
    has_result = any(value in {"TRUE", "FALSE"} for value in normalized.values())
    false_fields = tuple(label for label, _key in ANALYSIS_FIELDS if normalized[label] == "FALSE")
    issue_count = len(false_fields)

    if not has_result:
        status = "none"
        label = "No analysis"
    elif issue_count == 0:
        status = "pass"
        label = "Pass"
    elif "NAME" in false_fields or issue_count >= 3:
        # NAME remains a high-priority identity/linkage failure.  Any 3+ issues
        # are also Critical even when NAME itself passes.
        status = "critical"
        label = "Critical / NAME" if "NAME" in false_fields else "Critical"
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


def signal_review_display_status(analysis_result: object, stored_status: object) -> str:
    """Return the visible Human Review state for one Signal Mapping row.

    Automatic validation and Human Review are deliberately separate:
    * MATCHED/TRUE defaults to ``NOT REQUIRED`` but a reviewer may explicitly
      mark it ``REVIEWED`` or ``NEEDS ACTION``.
    * MISMATCHED/FALSE is a required Human Review item and therefore uses the
      stored ``UNREVIEWED``/``REVIEWED``/``NEEDS ACTION`` state.
    * unchecked rows remain ``VALIDATION REQUIRED`` even if stale review data
      exists, because validation coverage must be restored first.
    """
    result = str(analysis_result or "").strip().upper()
    stored = str(stored_status or "").strip().upper() or "UNREVIEWED"
    if result == "FALSE":
        return stored if stored in {"UNREVIEWED", "REVIEWED", "NEEDS ACTION"} else "UNREVIEWED"
    if result == "TRUE":
        return stored if stored in {"REVIEWED", "NEEDS ACTION"} else "NOT REQUIRED"
    return "VALIDATION REQUIRED"
