"""Shared RMU review-status semantics used by UI and Excel export.

Color has two independent meanings:

* row color = severity / number of failed Analysis checks;
* FALSE cell color = the exact field that failed.

The Analysis block currently contains NAME / FEEDER / SMART / TYPE / IP / LINK.
Keeping row severity independent from field combinations prevents an explosion of
special-case colors as checks are added.
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
    "one_issue": "FFF8D8",
    "two_issues": "FFF0E0",
    "critical": "FDECEC",
}

# Stronger, low-saturation field colors.  These identify the exact mismatch,
# not its severity.
FALSE_CELL_COLORS = {
    "NAME": "F7D7D7",      # red
    "FEEDER": "FFF0A8",    # yellow
    "SMART": "D8E9FF",     # blue
    "TYPE": "FFDDB8",      # orange
    "IP": "E6DEFF",        # violet
    "LINK": "F5DCEE",      # rose
}


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
