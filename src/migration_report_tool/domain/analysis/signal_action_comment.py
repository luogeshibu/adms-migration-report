"""Structured reviewer action + remark text for Signal Mapping comments.

The UI intentionally persists both the selected rectification verb and the
reviewer's note in the existing ``db_smart_reviews.comments`` field so older
projects and exports remain compatible.  The canonical stored form is::

    MODIFY | align point name with approved STANDARD

The parser also accepts a couple of legacy/manual variants so upgrades do not
lose previously-entered text.
"""
from __future__ import annotations

import re

SIGNAL_ACTIONS = ("ADD", "MODIFY", "DELETE")


def parse_signal_action_comment(value: object) -> tuple[str, str]:
    text = "" if value is None else str(value).strip()
    if not text:
        return "", ""

    # Canonical compact representation used by the app.
    match = re.match(r"^\s*(ADD|MODIFY|DELETE)\s*\|\s*(.+?)\s*$", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).upper(), match.group(2).strip()

    # Backward/hand-edited variants that may already exist in project.db.
    match = re.match(
        r"^\s*Action\s*:\s*(ADD|MODIFY|DELETE)\s*(?:\r?\n|;)+\s*Remark\s*:\s*(.+?)\s*$",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).upper(), match.group(2).strip()

    match = re.match(r"^\s*\[(ADD|MODIFY|DELETE)\]\s*(.+?)\s*$", text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).upper(), match.group(2).strip()

    return "", text


def format_signal_action_comment(action: object, remark: object) -> str:
    normalized_action = "" if action is None else str(action).strip().upper()
    normalized_remark = "" if remark is None else str(remark).strip()
    if normalized_action not in SIGNAL_ACTIONS:
        raise ValueError("Signal action must be ADD, MODIFY or DELETE")
    if not normalized_remark:
        raise ValueError("Signal action requires a reviewer remark")
    # Keep the grid one-line/high-performance while preserving all meaningful
    # reviewer text. The PDF renders the remark independently from the action.
    normalized_remark = re.sub(r"\s+", " ", normalized_remark).strip()
    return f"{normalized_action} | {normalized_remark}"
