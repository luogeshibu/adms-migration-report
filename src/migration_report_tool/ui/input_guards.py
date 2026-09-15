"""Global input-safety guards for reviewer-facing selection controls.

v0.8.182 makes mouse-wheel changes impossible on selection/value widgets.
Reviewers may still scroll normal pages/tables and may open a combo popup then
use explicit click/keyboard selection.  The guard is installed once on the
QApplication so dynamically created dialogs are protected too.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox


class SelectionWheelGuard(QObject):
    """Consume wheel events that could silently change a selected value."""

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API name
        if event.type() == QEvent.Type.Wheel and isinstance(obj, (QComboBox, QAbstractSpinBox)):
            event.accept()
            return True
        return super().eventFilter(obj, event)


def install_selection_wheel_guard(app):
    """Install and retain one application-wide wheel guard.

    Keeping the object on ``app`` is required because Qt event filters are not
    ownership-retained strongly enough for a short-lived local Python variable.
    """
    guard = SelectionWheelGuard(app)
    app.installEventFilter(guard)
    app._selection_wheel_guard = guard
    return guard
