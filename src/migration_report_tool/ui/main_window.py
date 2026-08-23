from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, QRect, QSettings, QEvent, QModelIndex, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QShortcut, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QStyledItemDelegate,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from ..utils.paths import standard_reference_path, standard_reference_origin, bundled_standard_reference_path
from ..core import (
    APP_NAME,
    APP_VERSION,
    COLUMNS,
    DATA_GROUPS,
    COMPARISON_COLUMNS,
    COMPARISON_GROUPS,
    COMPARISON_COLUMN_SCHEMA_VERSION,
    migrate_comparison_visible_columns,
    EDITABLE_COLUMNS,
    SOURCE_TYPES,
    ProjectStore,
    build_comparison,
    clean,
    export_report,
    is_inside_workspace,
    parse_zenon_xml,
    read_csv_rows,
    read_excel_rows,
    resource_root,
    workspace_root,
    write_zenon_sld_csv,
    import_source,
)
from ..db_smart import DBSmartReport, build_signal_mapping_report
from ..review_status import analysis_review_state

from ..config.sources import schema_for
from ..config.source_modules import MODULE_SOURCE_GROUPS
from ..infrastructure.parsers import validate_source_file
from ..services.schema_service import (
    get_source_overrides, set_source_overrides, get_source_display_names, set_source_display_names,
    default_display_name, apply_display_names_to_groups, RMU_REVIEW_DISPLAY_BINDINGS, SIGNAL_REVIEW_DISPLAY_BINDINGS,
    validation_summary,
)
from ..services.standard_reference_service import (
    current_standard_reference_info, install_standard_reference, restore_bundled_standard_reference,
)
from ..services.zenon_sld_service import regenerate_site_zenon_sld

from ..repository import (
    SOURCE_DEFINITIONS,
    SiteInfo,
    load_repository_root,
    load_last_site,
    save_repository_root,
    save_last_site,
    scan_repository,
    source_status,
    sync_site_to_project,
)


COLORS = {
    "nav": "#0F2742",
    "nav_hover": "#173A5E",
    "nav_selected": "#1D4F7A",
    "accent": "#0EA5A8",
    "accent_dark": "#0B8386",
    "canvas": "#F5F7FA",
    "surface": "#FFFFFF",
    "border": "#DCE3EA",
    "text": "#18212F",
    "muted": "#667085",
    "success": "#12805C",
    "warning": "#B7791F",
    "danger": "#B42318",
    "info": "#2365A8",
}


APP_QSS = f"""
QMainWindow {{ background: {COLORS['canvas']}; }}
QWidget {{ font-family: 'Segoe UI'; font-size: 10pt; color: {COLORS['text']}; }}
QFrame#Sidebar {{ background: {COLORS['nav']}; border: none; }}
QFrame#Topbar {{ background: {COLORS['surface']}; border-bottom: 1px solid {COLORS['border']}; }}
QFrame#Card {{ background: {COLORS['surface']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}
QFrame#SoftCard {{ background: #F8FAFC; border: 1px solid {COLORS['border']}; border-radius: 10px; }}
QLabel#BrandTitle {{ color: white; font-size: 15pt; font-weight: 750; letter-spacing: 0.4px; }}
QLabel#BrandSub {{ color: #A9C0D5; font-size: 8.5pt; font-weight: 650; }}
QLabel#BrandProject {{ color: #79D6D1; font-size: 8pt; font-weight: 700; }}
QLabel#ProjectKicker {{ color: #5D7187; font-size: 8.5pt; font-weight: 700; }}
QLabel#ProjectTag {{
    color: #087C80; background: #E7F7F6; border: 1px solid #BFE9E6;
    border-radius: 9px; padding: 3px 8px; font-size: 8.5pt; font-weight: 700;
}}
QLabel#ProjectStateTag {{
    color: #315069; background: #F1F6F9; border: 1px solid #D1DEE7;
    border-radius: 9px; padding: 4px 9px; font-size: 8.5pt; font-weight: 700;
}}
QFrame#WorkflowCard {{ background: #FFFFFF; border: 1px solid #DCE3EA; border-radius: 11px; }}
QLabel#WorkflowTitle {{ color: #18212F; font-size: 10pt; font-weight: 700; }}
QLabel#WorkflowDone {{ color: #087C80; background: #E7F7F6; border: 1px solid #BFE9E6; border-radius: 8px; padding: 6px 10px; font-weight: 700; }}
QLabel#WorkflowCurrent {{ color: #805B12; background: #FFF8E6; border: 1px solid #F1D493; border-radius: 8px; padding: 6px 10px; font-weight: 700; }}
QLabel#WorkflowPending {{ color: #667085; background: #F7F9FB; border: 1px solid #E0E6ED; border-radius: 8px; padding: 6px 10px; font-weight: 650; }}
QLabel#ModuleIcon {{ background: #EEF8F8; border: 1px solid #D2ECEA; border-radius: 8px; padding: 5px; }}
QProgressBar {{ background: #EEF2F6; border: 1px solid #DCE3EA; border-radius: 6px; text-align: center; color: #32465A; height: 16px; font-size: 8.5pt; }}
QProgressBar::chunk {{ background: #0EA5A8; border-radius: 5px; }}
QFrame#ProjectBanner {{ background: #F8FBFC; border: 1px solid #D8E5E8; border-radius: 11px; }}
QLabel#ProjectMetaTitle {{ color: #667085; font-size: 8pt; font-weight: 650; }}
QLabel#ProjectMetaValue {{ color: #20354A; font-size: 10pt; font-weight: 700; }}
QLabel#PageTitle {{ color: {COLORS['text']}; font-size: 20pt; font-weight: 700; }}
QLabel#PageSub {{ color: {COLORS['muted']}; font-size: 9.5pt; }}
QLabel#MetricValue {{ color: {COLORS['text']}; font-size: 22pt; font-weight: 700; }}
QLabel#MetricLabel {{ color: {COLORS['muted']}; font-size: 9pt; }}
QLabel#SectionTitle {{ color: {COLORS['text']}; font-size: 12pt; font-weight: 650; }}
QLabel#Muted {{ color: {COLORS['muted']}; }}
QPushButton {{
    background: {COLORS['surface']}; border: 1px solid #CCD5DF; border-radius: 7px;
    padding: 7px 13px; font-weight: 600;
}}
QPushButton:hover {{ background: #F4F7FA; border-color: #AEBBC8; }}
QPushButton:pressed {{ background: #EAF0F5; }}
QPushButton#Primary {{ background: {COLORS['accent']}; color: white; border: 1px solid {COLORS['accent']}; }}
QPushButton#Primary:hover {{ background: {COLORS['accent_dark']}; border-color: {COLORS['accent_dark']}; }}
QPushButton#Danger {{ background: #FFF4F2; color: {COLORS['danger']}; border-color: #F4C7C3; }}
QPushButton#NavButton {{
    background: transparent; color: #C6D5E4; border: none; border-radius: 8px;
    padding: 10px 12px; text-align: left; font-weight: 600;
}}
QPushButton#NavButton:hover {{ background: {COLORS['nav_hover']}; color: white; }}
QPushButton#NavButton:checked {{ background: {COLORS['nav_selected']}; color: white; }}
QLineEdit, QComboBox, QTextEdit {{
    background: white; border: 1px solid #CBD5E1; border-radius: 7px; padding: 7px 9px;
    selection-background-color: {COLORS['accent']};
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border: 1px solid {COLORS['accent']}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QTableWidget {{
    background: white; border: 1px solid {COLORS['border']}; border-radius: 10px;
    gridline-color: #E7ECF1; selection-background-color: transparent; selection-color: #102A43;
    alternate-background-color: #FAFBFC;
}}
QTableWidget::item:selected {{
    border-top: 1px solid #4A90E2;
    border-bottom: 1px solid #4A90E2;
}}
QHeaderView::section {{
    background: #F4F6F8; color: #24364B; border: none; border-right: 1px solid #CBD5E1;
    border-bottom: 1px solid #CBD5E1; padding: 8px 7px; font-weight: 650;
}}
QTableCornerButton::section {{ background: #E8EDF3; border: 1px solid #CBD5E1; }}
QScrollBar:vertical {{ background: #EFF3F7; width: 12px; margin: 0; border: none; }}
QScrollBar::handle:vertical {{ background: #B7C2CE; border-radius: 6px; min-height: 30px; }}
QScrollBar:horizontal {{ background: #EFF3F7; height: 12px; margin: 0; border: none; }}
QScrollBar::handle:horizontal {{ background: #B7C2CE; border-radius: 6px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid #EDF1F5; }}
QListWidget::item:selected {{ background: #E9F4F5; color: {COLORS['text']}; }}
QSplitter::handle {{ background: #E7ECF1; }}
QSplitter::handle:horizontal {{ width: 6px; margin: 4px 0; border-radius: 3px; }}
QSplitter::handle:hover {{ background: #C8D4DF; }}
QFrame#EmptyState {{ background: #FFFFFF; border: 1px solid #E1E7EE; border-radius: 12px; }}
QFrame#EmptyStateContent {{ background: transparent; border: none; }}
QLabel#EmptyIcon {{
    background: #EEF4F8; color: #60758A; border: none; border-radius: 20px;
    font-size: 13pt; font-weight: 700;
}}
QLabel#EmptyTitle {{ color: #344054; font-size: 13pt; font-weight: 700; border: none; }}
QLabel#EmptySub {{ color: #7A8699; font-size: 9.5pt; border: none; }}
"""


def set_object_name(widget, name: str):
    widget.setObjectName(name)
    return widget


def app_icon(name: str) -> QIcon:
    path = resource_root() / "icons" / f"{name}.svg"
    return QIcon(str(path)) if path.exists() else QIcon()


def icon_label(name: str, size: int = 30) -> QLabel:
    label = QLabel()
    label.setObjectName("ModuleIcon")
    label.setFixedSize(size + 12, size + 12)
    icon = app_icon(name)
    if not icon.isNull():
        label.setPixmap(icon.pixmap(QSize(size, size)))
    label.setAlignment(Qt.AlignCenter)
    return label


def signal_review_row_hash(row, analysis_column: int | None = None) -> str:
    values = list(getattr(row, "values", ()))
    # Comparison Summary columns are report-level aggregates rendered on the
    # first few rows. They must never invalidate an otherwise unchanged signal
    # row merely because a different signal changed somewhere else.
    if analysis_column is not None and analysis_column >= 0:
        values = values[:analysis_column + 1]
    payload = {
        "rmu": clean(getattr(row, "rmu", "")),
        "values": [clean(value) for value in values],
        "analysis_detail": clean(getattr(row, "analysis_detail", "")),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


# DATA sheet inspired header palette. The layout mirrors the customer's
# two-row A:BB header while keeping the rest of the desktop UI modern.
REPORT_HEADER_COLORS = {
    # Table header color communicates hierarchy only. Business/status colors
    # are reserved for table data (row state and FALSE analysis cells).
    "Index": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "RMU": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "SE": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "ZENON DB": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "Driver Info": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "ZENON SLD XML": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "ADMS DB": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "ADMS Channel": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "ADMS SLD": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "Analysis": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "Remarks": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "Comments": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "Resolution": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "Review": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "ZENON": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "ADMS": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "STANDARD DATABASE I/O list": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "Comparison Summary": ("#E8EDF3", "#F4F6F8", "#24364B"),
}



class GroupedReportHeader(QHeaderView):
    """Reusable two-level horizontal header for application review tables.

    Row 1 contains merged logical groups (Analysis, Index, SE, ZENON DB, ADMS DB, ...).
    Row 2 contains field names. Single-column review fields such as Remarks
    and Comments span both header rows. Header colors are intentionally neutral;
    business colors are reserved for data status.
    """

    TOP_HEIGHT = 30
    BOTTOM_HEIGHT = 40

    def __init__(self, groups, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.groups = ()
        self._column_meta = []
        self._group_ranges = []
        self.setDefaultAlignment(Qt.AlignCenter)
        self.setSectionsClickable(True)
        self.setSectionsMovable(False)
        self.setHighlightSections(False)
        self.setMinimumHeight(self.TOP_HEIGHT + self.BOTTOM_HEIGHT)
        self.setFixedHeight(self.TOP_HEIGHT + self.BOTTOM_HEIGHT)
        self.set_groups(groups)

    def set_groups(self, groups):
        """Update group metadata without replacing the QHeaderView instance.

        Reusing the same header is important inside stacked pages: replacing a
        custom QHeaderView every time a page is revisited can leave Qt with a
        stale/deferred-deleted header and the grouped titles disappear.
        """
        self.groups = tuple(groups or ())
        self._column_meta = []
        self._group_ranges = []
        cursor = 0
        for group, _color, columns in self.groups:
            start = cursor
            for key, label, width in columns:
                self._column_meta.append((group, key, label, width))
                cursor += 1
            self._group_ranges.append((group, start, cursor - 1))
        self.setMinimumHeight(self.TOP_HEIGHT + self.BOTTOM_HEIGHT)
        self.setFixedHeight(self.TOP_HEIGHT + self.BOTTOM_HEIGHT)
        self.updateGeometry()
        self.viewport().update()

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(hint.width(), self.TOP_HEIGHT + self.BOTTOM_HEIGHT)

    def _section_rect(self, logical_index: int, y: int, height: int) -> QRect:
        x = self.sectionViewportPosition(logical_index)
        return QRect(x, y, self.sectionSize(logical_index), height)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(self.viewport().rect(), QColor("#FFFFFF"))

        border = QColor("#CAD3DD")
        strong_border = QColor("#AEB8C4")
        text_font = QFont("Segoe UI", 9)
        text_font.setWeight(QFont.Weight.DemiBold)
        group_font = QFont("Segoe UI", 9)
        group_font.setWeight(QFont.Weight.Bold)

        # Bottom field row. Group colors are intentionally neutral.
        for index, (group, _key, label, _width) in enumerate(self._column_meta):
            if self.isSectionHidden(index):
                continue
            x = self.sectionViewportPosition(index)
            width = self.sectionSize(index)
            if width <= 0 or x + width < 0 or x > self.viewport().width():
                continue
            top_color, bottom_color, text_color = REPORT_HEADER_COLORS.get(
                group, ("#E5E7EB", "#F3F4F6", "#18212F")
            )
            if group in {"Remarks", "Comments", "Resolution"}:
                continue

            bottom_rect = self._section_rect(index, self.TOP_HEIGHT, self.BOTTOM_HEIGHT)
            painter.fillRect(bottom_rect, QColor(bottom_color))
            painter.setPen(QPen(border, 1))
            painter.drawRect(bottom_rect.adjusted(0, 0, -1, -1))
            painter.setFont(text_font)
            painter.setPen(QColor(text_color))
            painter.drawText(bottom_rect.adjusted(5, 2, -5, -2), Qt.AlignCenter | Qt.TextWordWrap, label)

        # Merged group row. Painting the complete span after individual cells
        # removes internal top-row borders and visually creates the Excel merge.
        for group, start, end in self._group_ranges:
            visible = [i for i in range(start, end + 1) if not self.isSectionHidden(i)]
            if not visible:
                continue
            first, last = visible[0], visible[-1]
            left = self.sectionViewportPosition(first)
            right = self.sectionViewportPosition(last) + self.sectionSize(last)
            if right <= left or right < 0 or left > self.viewport().width():
                continue
            top_color, bottom_color, text_color = REPORT_HEADER_COLORS.get(
                group, ("#E5E7EB", "#F3F4F6", "#18212F")
            )
            if group in {"Remarks", "Comments", "Resolution"}:
                rect = QRect(left, 0, right - left, self.TOP_HEIGHT + self.BOTTOM_HEIGHT)
            else:
                rect = QRect(left, 0, right - left, self.TOP_HEIGHT)
            painter.fillRect(rect, QColor(top_color))
            painter.setPen(QPen(strong_border, 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.setFont(group_font)
            painter.setPen(QColor(text_color))
            painter.drawText(rect.adjusted(6, 2, -6, -2), Qt.AlignCenter | Qt.TextWordWrap, group)

        painter.end()


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "0", accent: str = "#0EA5A8", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(110)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        strip = QFrame()
        strip.setFixedHeight(4)
        strip.setStyleSheet(f"background:{accent}; border-radius:2px;")
        layout.addWidget(strip)
        layout.addSpacing(4)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)
        layout.addStretch()

    def set_value(self, value):
        self.value_label.setText(str(value))


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSub")
        subtitle_label.setWordWrap(True)
        subtitle_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)


class EmptyState(QFrame):
    """Stable, centered empty state that never clips wrapped explanatory text.

    The previous implementation centered each QLabel independently. On Windows
    with some DPI/font combinations QLabel's wrapped sizeHint could be only one
    line high, which clipped the second line even though the surrounding page had
    plenty of space. A bounded inner content frame gives the subtitle a real width
    before Qt calculates height-for-width.
    """

    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setObjectName("EmptyState")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(220)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)
        outer.addStretch(1)

        center_row = QHBoxLayout()
        center_row.setContentsMargins(0, 0, 0, 0)
        center_row.setSpacing(0)
        center_row.addStretch(1)

        content = QFrame()
        content.setObjectName("EmptyStateContent")
        content.setMinimumWidth(420)
        content.setMaximumWidth(680)
        content.setMinimumHeight(176)
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        box = QVBoxLayout(content)
        box.setContentsMargins(22, 18, 22, 18)
        box.setSpacing(8)

        icon = QLabel("i")
        icon.setObjectName("EmptyIcon")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(40, 40)

        title_label = QLabel(title)
        title_label.setObjectName("EmptyTitle")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setMinimumHeight(28)

        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("EmptySub")
        subtitle_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        subtitle_label.setWordWrap(True)
        subtitle_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        subtitle_label.setMinimumHeight(50)

        box.addWidget(icon, 0, Qt.AlignHCenter)
        box.addWidget(title_label)
        box.addWidget(subtitle_label)

        center_row.addWidget(content, 1)
        center_row.addStretch(1)
        outer.addLayout(center_row)
        outer.addStretch(1)


class RowTrackingDelegate(QStyledItemDelegate):
    """Paint row tracking without covering business/status fills.

    Hover uses a subtle blue guide line; the active/current row uses a stronger
    line.  Because the delegate paints only borders after the normal item paint,
    PASS / Issue severity colors and FALSE-field colors remain fully visible.
    """

    def __init__(self, table, parent=None):
        super().__init__(parent or table)
        self.table = table

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        row = index.row()
        active = row == getattr(self.table, "tracked_active_row", -1)
        hover = row == getattr(self.table, "tracked_hover_row", -1)
        if not (active or hover):
            return
        painter.save()
        color = QColor("#2F80ED") if active else QColor("#8CB7E6")
        width = 2 if active else 1
        painter.setPen(QPen(color, width))
        rect = option.rect.adjusted(0, 0, -1, -1)
        painter.drawLine(rect.topLeft(), rect.topRight())
        painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        painter.restore()


class SpreadsheetTableWidget(QTableWidget):
    """QTableWidget with Excel-like multi-range selection and row tracking.

    - Drag: select a rectangular block.
    - Ctrl+click/drag: add or remove non-contiguous cells/ranges.
    - Shift: extend from the current anchor.
    - Click an empty area inside the grid: clear the current selection.
    - Hover: track the same business row across a very wide grid.
    - Current cell: keep a persistent active-row guide while scrolling right.

    Selection painting stays transparent so business/status background colors
    remain visible.  Row tracking is painted as border lines only.
    """

    hoverRowChanged = Signal(int)
    activeRowChanged = Signal(int)

    def __init__(self, rows: int = 0, columns: int = 0, parent=None):
        super().__init__(rows, columns, parent)
        self.tracked_hover_row = -1
        self.tracked_active_row = -1
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.setItemDelegate(RowTrackingDelegate(self, self))
        self.currentCellChanged.connect(self._on_current_cell_changed)

    def set_tracked_hover_row(self, row: int) -> None:
        row = int(row) if row is not None else -1
        if self.tracked_hover_row == row:
            return
        self.tracked_hover_row = row
        self.viewport().update()

    def set_tracked_active_row(self, row: int) -> None:
        row = int(row) if row is not None else -1
        if self.tracked_active_row == row:
            return
        self.tracked_active_row = row
        self.viewport().update()

    def _on_current_cell_changed(self, current_row: int, _current_col: int, _previous_row: int, _previous_col: int) -> None:
        row = current_row if current_row >= 0 else -1
        self.set_tracked_active_row(row)
        self.activeRowChanged.emit(row)

    def clear_spreadsheet_selection(self) -> None:
        self.clearSelection()
        self.setCurrentIndex(QModelIndex())
        self.set_tracked_active_row(-1)
        self.activeRowChanged.emit(-1)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        index = self.indexAt(pos)
        row = index.row() if index.isValid() else -1
        if row != self.tracked_hover_row:
            self.set_tracked_hover_row(row)
            self.hoverRowChanged.emit(row)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self.tracked_hover_row != -1:
            self.set_tracked_hover_row(-1)
            self.hoverRowChanged.emit(-1)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if not self.indexAt(pos).isValid():
                self.clear_spreadsheet_selection()
        super().mousePressEvent(event)


def _configure_table_base(table: QTableWidget) -> None:
    """Shared behavior for normal responsive tables (not the 54-column DATA grid)."""
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setSectionsMovable(False)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setMinimumSectionSize(60)
    table.horizontalHeader().setMinimumHeight(40)
    table.verticalHeader().setDefaultSectionSize(36)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)


def _set_fixed_column(table: QTableWidget, column: int, width: int) -> None:
    table.horizontalHeader().setSectionResizeMode(column, QHeaderView.Fixed)
    table.setColumnWidth(column, width)


def _set_interactive_column(table: QTableWidget, column: int, width: int) -> None:
    table.horizontalHeader().setSectionResizeMode(column, QHeaderView.Interactive)
    table.setColumnWidth(column, width)


def _set_stretch_column(table: QTableWidget, column: int) -> None:
    table.horizontalHeader().setSectionResizeMode(column, QHeaderView.Stretch)


class EditValueDialog(QDialog):
    def __init__(self, rmu: str, label: str, old_value: str, parent=None, multiline: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Review / Edit Value")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        title = QLabel(f"RMU {rmu}  ·  {label}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        sub = QLabel("Every accepted change is written to the SQLite audit history.")
        sub.setObjectName("Muted")
        layout.addWidget(sub)
        layout.addSpacing(10)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        self.multiline = multiline
        if multiline:
            self.value_edit = QTextEdit()
            self.value_edit.setPlainText(old_value)
            self.value_edit.setMinimumHeight(120)
        else:
            self.value_edit = QLineEdit(old_value)
        self.reason_edit = QTextEdit()
        self.reason_edit.setPlaceholderText("Reason / comment for this modification")
        self.reason_edit.setFixedHeight(90)
        form.addRow("New value", self.value_edit)
        form.addRow("Reason", self.reason_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        save = buttons.button(QDialogButtonBox.Save)
        save.setObjectName("Primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        reason = self.reason_edit.toPlainText().strip() or "Manual correction"
        value = self.value_edit.toPlainText() if self.multiline else self.value_edit.text()
        return value.strip(), reason


class RMUResolutionDialog(QDialog):
    """One structured decision row for every active RMU Analysis error.

    A reviewer never types free-form Comments here.  Each FALSE field receives
    its own decision selector, so N automatic errors always require N explicit
    Resolution decisions before Review can become Reviewed.
    """

    FIELD_ORDER = ("NAME", "FEEDER", "SMART", "TYPE", "IP", "LINK")

    def __init__(self, rmu: str, row_data: dict, current_resolutions: dict, parent=None):
        super().__init__(parent)
        self.rmu = clean(rmu)
        self.row_data = row_data or {}
        self.current_resolutions = current_resolutions or {}
        self.issue_fields = [
            field for field in self.FIELD_ORDER
            if clean(self.row_data.get(f"analysis_{field.lower()}" )).upper() == "FALSE"
        ]
        self.combos: dict[str, QComboBox] = {}

        self.setWindowTitle(f"Resolve RMU {self.rmu} Issues")
        self.resize(980, min(760, 300 + max(1, len(self.issue_fields)) * 95))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        title = QLabel(f"RMU {self.rmu} · {len(self.issue_fields)} issue{'s' if len(self.issue_fields) != 1 else ''} require {len(self.issue_fields)} Resolution decision{'s' if len(self.issue_fields) != 1 else ''}")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        desc = QLabel(
            "Choose one decision for every FALSE Analysis field. Source choices use the exact values found during the latest Validation. "
            "If any issue remains Unresolved, Review stays Unreviewed. If any issue is marked Needs Action, Review becomes Needs Action."
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        table = QTableWidget(len(self.issue_fields), 3)
        table.setHorizontalHeaderLabels(["Issue", "Source Values from Validation", "Resolution Decision"] )
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.setColumnWidth(0, 115)
        table.setColumnWidth(2, 330)
        table.horizontalHeader().setMinimumHeight(38)

        candidates_by_field = self.row_data.get("resolution_candidates") or {}
        for row_index, field in enumerate(self.issue_fields):
            issue_item = QTableWidgetItem(field)
            font = issue_item.font(); font.setBold(True); issue_item.setFont(font)
            issue_item.setTextAlignment(Qt.AlignCenter)
            issue_item.setBackground(QColor("#F7D7D7"))
            issue_item.setToolTip(clean(self.row_data.get(f"analysis_{field.lower()}_detail")))
            table.setItem(row_index, 0, issue_item)

            candidates = list(candidates_by_field.get(field, []) or [])
            source_lines = []
            for candidate in candidates:
                source = clean(candidate.get("source"))
                raw = clean(candidate.get("value"))
                normalized = clean(candidate.get("normalized"))
                line = f"{source}: {raw or '<blank>'}"
                if normalized and normalized != raw:
                    line += f"  →  {normalized}"
                source_lines.append(line)
            if field == "LINK" and not source_lines:
                source_lines.append("ADMS SLD LINK: <missing>")
            values_item = QTableWidgetItem("\n".join(source_lines) or "No selectable source value is available")
            values_item.setToolTip(clean(self.row_data.get(f"analysis_{field.lower()}_detail")))
            table.setItem(row_index, 1, values_item)

            combo = QComboBox()
            combo.setToolTip(f"Select exactly one Resolution for {field}")
            combo.addItem("Unresolved", None)
            # Cross-source mismatches allow the reviewer to choose which source
            # is authoritative. LINK is an ADMS association flag rather than a
            # multi-source value, so it uses action decisions only.
            if field != "LINK":
                for candidate in candidates:
                    source = clean(candidate.get("source"))
                    raw = clean(candidate.get("value"))
                    normalized = clean(candidate.get("normalized"))
                    label = f"Use {source} — {raw or normalized or '<blank>'}"
                    if normalized and raw and normalized != raw:
                        label += f"  → {normalized}"
                    combo.addItem(label, {
                        "decision_type": "USE_SOURCE",
                        "selected_source": source,
                        "selected_value": raw,
                        "normalized_value": normalized,
                    })
            combo.addItem("Needs Action — correction required", {"decision_type": "NEEDS_ACTION"})
            combo.addItem("Accept Exception — no source correction", {"decision_type": "ACCEPT_EXCEPTION"})

            current = self.current_resolutions.get(field) or {}
            if current:
                decision = clean(current.get("decision_type")).upper()
                source = clean(current.get("selected_source"))
                for index in range(combo.count()):
                    data = combo.itemData(index)
                    if not isinstance(data, dict):
                        continue
                    if clean(data.get("decision_type")).upper() != decision:
                        continue
                    if decision != "USE_SOURCE" or clean(data.get("selected_source")) == source:
                        combo.setCurrentIndex(index)
                        break
            self.combos[field] = combo
            table.setCellWidget(row_index, 2, combo)
            table.setRowHeight(row_index, max(56, 24 + 18 * max(1, len(source_lines))))

        layout.addWidget(table, 1)
        footer = QLabel("Review is derived automatically: all issues resolved → Reviewed; any Needs Action → Needs Action; any Unresolved → Unreviewed.")
        footer.setObjectName("Muted")
        footer.setWordWrap(True)
        layout.addWidget(footer)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Save Resolutions")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def decisions(self) -> dict[str, dict | None]:
        return {field: combo.currentData() for field, combo in self.combos.items()}


class ColumnVisibilityDialog(QDialog):
    """Select which Comparison source groups/fields are visible on screen.

    This changes only the desktop review view. The formal Excel DATA export
    always keeps the customer A:BB schema and column order.
    """

    REVIEW_KEYS = {
        "no", "rmu", "analysis_name", "analysis_feeder", "analysis_smart",
        "analysis_type", "analysis_ip", "analysis_link", "remarks", "comments", "se_station", "se_feeder",
        "se_rmu", "se_smart", "se_oh_ug", "zsld_screen_name", "zsld_feeder",
        "zsld_rmu", "zsld_type", "asld_rmu", "asld_type", "asld_smart", "asld_link",
    }

    def __init__(self, groups, visible_keys: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("RMU Data Review Columns")
        self.resize(720, 700)
        self.groups = groups
        self._checks: dict[str, QCheckBox] = {}
        self._group_checks: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)
        title = QLabel("Choose visible RMU Data Review columns")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel("Hide source groups or individual fields to create a focused review view. No columns are removed from SQLite or the exported Excel report.")
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        root.addWidget(desc)

        preset = QHBoxLayout()
        full_btn = QPushButton("Full View")
        review_btn = QPushButton("Review View")
        all_off_btn = QPushButton("Hide Source Details")
        full_btn.clicked.connect(lambda: self._set_visible({k for _g, _c, cols in self.groups for k, _l, _w in cols}))
        review_btn.clicked.connect(lambda: self._set_visible(self.REVIEW_KEYS))
        all_off_btn.clicked.connect(lambda: self._set_visible({"no", "rmu", "analysis_name", "analysis_feeder", "analysis_smart", "analysis_type", "analysis_ip", "analysis_link", "remarks", "comments"}))
        preset.addWidget(review_btn)
        preset.addWidget(full_btn)
        preset.addWidget(all_off_btn)
        preset.addStretch()
        root.addLayout(preset)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget()
        body = QVBoxLayout(holder)
        body.setContentsMargins(2, 6, 8, 6)
        body.setSpacing(10)

        for group, _color, columns in groups:
            card = QFrame()
            card.setObjectName("SoftCard")
            box = QVBoxLayout(card)
            box.setContentsMargins(14, 10, 14, 10)
            gcheck = QCheckBox(group if group != "Index" else "Keys")
            gcheck.setStyleSheet("font-weight:700;")
            self._group_checks[group] = gcheck
            box.addWidget(gcheck)
            grid = QGridLayout()
            for pos, (key, label, _width) in enumerate(columns):
                cb = QCheckBox(label)
                cb.setChecked(key in visible_keys)
                if key in {"no", "rmu"}:
                    cb.setChecked(True)
                    cb.setEnabled(False)
                self._checks[key] = cb
                grid.addWidget(cb, pos // 3, pos % 3)
            box.addLayout(grid)
            child_keys = [key for key, _label, _width in columns if key not in {"no", "rmu"}]
            if child_keys:
                gcheck.setChecked(all(self._checks[key].isChecked() for key in child_keys))
                gcheck.clicked.connect(lambda checked, keys=child_keys: self._set_group(keys, checked))
                for key in child_keys:
                    self._checks[key].toggled.connect(lambda _checked, g=group, keys=child_keys: self._sync_group(g, keys))
            else:
                gcheck.setChecked(True)
                gcheck.setEnabled(False)
            body.addWidget(card)
        body.addStretch()
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _set_group(self, keys: list[str], checked: bool):
        for key in keys:
            self._checks[key].setChecked(checked)

    def _sync_group(self, group: str, keys: list[str]):
        cb = self._group_checks[group]
        cb.blockSignals(True)
        cb.setChecked(all(self._checks[key].isChecked() for key in keys))
        cb.blockSignals(False)

    def _set_visible(self, keys: set[str]):
        keys = set(keys) | {"no", "rmu"}
        for key, cb in self._checks.items():
            if cb.isEnabled():
                cb.setChecked(key in keys)

    def visible_keys(self) -> set[str]:
        return {key for key, cb in self._checks.items() if cb.isChecked()} | {"no", "rmu"}




class NoWheelComboBox(QComboBox):
    """ComboBox that cannot change selection from the mouse wheel.

    Source Mapping is a data-governance screen.  Accidental wheel changes are
    particularly risky because they can silently create a site override.
    The user must open the drop-down (or use the keyboard) to change a mapping.
    """

    def wheelEvent(self, event):
        event.ignore()


class SourceMappingDialog(QDialog):
    """Show and optionally override external header -> canonical field mapping."""

    def __init__(self, source_type: str, source_path: Path, store, user_name: str, parent=None):
        super().__init__(parent)
        self.source_type = source_type
        self.source_path = Path(source_path)
        self.store = store
        self.user_name = user_name
        self.schema = schema_for(source_type)
        self.current_overrides = get_source_overrides(store, source_type)
        self.current_display_names = get_source_display_names(store, source_type)
        self.setWindowTitle(f"Source Mapping · {self.schema.label if self.schema else source_type}")
        self.resize(980, 650)
        root = QVBoxLayout(self)
        title = QLabel(f"{self.schema.label if self.schema else source_type} column mapping")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel(
            "System Field / Internal Key are the fixed business contract. Global Display Name is application-wide: one change applies to every site, "
            "the App review grids and formal Excel exports. Actual Column (Current Site) is the physical CSV/XLSX header for this site's source file only. "
            "Changing a Display Name never renames the Internal Key or the source file; changing an Actual Column mapping never affects other sites."
        )
        desc.setObjectName("Muted"); desc.setWordWrap(True); root.addWidget(desc)
        file_label = QLabel(str(self.source_path)); file_label.setObjectName("Muted"); file_label.setWordWrap(True); root.addWidget(file_label)

        self.validation = validate_source_file(source_type, self.source_path, self.current_overrides)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "System Field", "Global Display Name", "Name Source", "Internal Key", "Required",
            "Actual Column (Current Site)", "Status", "Column Mapping"
        ])
        _configure_table_base(self.table)
        _set_interactive_column(self.table, 0, 175)
        _set_interactive_column(self.table, 1, 210)
        _set_fixed_column(self.table, 2, 120)
        _set_fixed_column(self.table, 3, 135)
        _set_fixed_column(self.table, 4, 90)
        _set_stretch_column(self.table, 5)
        _set_fixed_column(self.table, 6, 120)
        _set_fixed_column(self.table, 7, 150)
        self._combos: dict[str, QComboBox] = {}
        self._display_edits: dict[str, QLineEdit] = {}
        self._populate()
        root.addWidget(self.table, 1)

        self.result_label = QLabel(self._summary_text(self.validation)); self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)
        button_row = QHBoxLayout()
        reset_btn = QPushButton("Reset Mapping to Auto")
        reset_btn.setToolTip("Clear Actual Column overrides for the current site only and return to automatic source-header mapping.")
        reset_btn.clicked.connect(self._reset_all_to_auto)
        button_row.addWidget(reset_btn)
        reset_names_btn = QPushButton("Reset Global Names")
        reset_names_btn.setToolTip("Restore this source's application-wide Display Names to the built-in App headers for every site.")
        reset_names_btn.clicked.connect(self._reset_display_names)
        button_row.addWidget(reset_names_btn)
        button_row.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Save Changes")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        root.addLayout(button_row)

    def _summary_text(self, result):
        if result is None:
            return "This source does not use a tabular schema."
        text = f"Schema: {validation_summary(result)}"
        if result.errors:
            text += " · Run Review is blocked until required mapping errors are resolved."
        elif result.warnings:
            text += " · Optional columns are missing; affected fields remain blank and do not participate in Analysis."
        else:
            text += " · All configured columns were resolved."
        return text

    def _populate(self):
        result = self.validation
        if result is None or self.schema is None:
            return
        by_key = result.mapping_by_key
        self.table.setRowCount(len(self.schema.fields))
        for row, spec in enumerate(self.schema.fields):
            mapping = by_key[spec.key]
            label_item = QTableWidgetItem(spec.label)
            label_item.setToolTip(spec.description or ("Accepted names: " + ", ".join(spec.aliases)))
            self.table.setItem(row, 0, label_item)

            built_in_display = default_display_name(self.source_type, spec.key, spec.label)
            display_edit = QLineEdit(self.current_display_names.get(spec.key, built_in_display) or built_in_display)
            display_edit.setPlaceholderText(built_in_display)
            display_edit.setMaxLength(80)
            display_edit.setToolTip(
                f"Application-global presentation label. Built-in App header: {built_in_display}. "
                "Saving a change updates every site's App/Excel review header; Internal Key and physical source header stay unchanged."
            )
            self._display_edits[spec.key] = display_edit
            self.table.setCellWidget(row, 1, display_edit)

            name_source = QTableWidgetItem("Global Override" if spec.key in self.current_display_names else "Built-in")
            name_source.setTextAlignment(Qt.AlignCenter)
            name_source.setToolTip(
                "Global Override = saved application-wide and used by every site. Built-in = the default App review header."
            )
            if spec.key in self.current_display_names:
                name_source.setForeground(QColor(COLORS["success"]))
                f = name_source.font(); f.setBold(True); name_source.setFont(f)
            self.table.setItem(row, 2, name_source)

            key_item = QTableWidgetItem(spec.key)
            key_item.setToolTip("Stable internal field key used by business logic; this key cannot be renamed.")
            self.table.setItem(row, 3, key_item)
            req = QTableWidgetItem("Yes" if spec.required else "No"); req.setTextAlignment(Qt.AlignCenter); self.table.setItem(row, 4, req)
            combo = NoWheelComboBox()
            combo.setToolTip("Current-site mapping only. Auto uses the recognized source header; choose a column only when this site's file requires an override. Mouse wheel is disabled.")
            auto_text = "Auto"
            if mapping.actual_column and spec.key not in self.current_overrides:
                auto_text += f" ({mapping.actual_column})"
            combo.addItem(auto_text, "")
            for header in result.headers:
                combo.addItem(header, header)
            override = self.current_overrides.get(spec.key, "")
            if override:
                index = combo.findData(override)
                if index >= 0:
                    combo.setCurrentIndex(index)
            self._combos[spec.key] = combo
            self.table.setCellWidget(row, 5, combo)
            status = mapping.kind.value
            item = QTableWidgetItem(status)
            if mapping.kind.value in {"Missing", "Ambiguous"}:
                item.setForeground(QColor(COLORS["danger"] if spec.required else COLORS["warning"]))
            else:
                item.setForeground(QColor(COLORS["success"]))
            f=item.font(); f.setBold(True); item.setFont(f); self.table.setItem(row, 6, item)
            source = "Site Override" if spec.key in self.current_overrides else mapping.kind.value
            self.table.setItem(row, 7, QTableWidgetItem(source))
            tip = mapping.message or ("Accepted names: " + ", ".join(spec.aliases))
            for col in (0, 3, 6, 7):
                if self.table.item(row, col): self.table.item(row, col).setToolTip(tip)

    def _reset_all_to_auto(self):
        for combo in self._combos.values():
            combo.setCurrentIndex(0)
        self.result_label.setText("Pending: Actual Column overrides for the current site will be cleared when you click Save Changes.")

    def _reset_display_names(self):
        if self.schema is None:
            return
        for spec in self.schema.fields:
            edit = self._display_edits.get(spec.key)
            if edit is not None:
                edit.setText(default_display_name(self.source_type, spec.key, spec.label))
        self.result_label.setText("Pending: Global Display Names will be restored to the built-in App headers for every site when you click Save Changes.")

    def _save(self):
        overrides = {key: clean(combo.currentData()) for key, combo in self._combos.items() if clean(combo.currentData())}
        result = validate_source_file(self.source_type, self.source_path, overrides)
        if result is not None and result.errors:
            QMessageBox.critical(self, "Source Mapping", result.error_message(self.source_path.name))
            return
        display_names = {key: clean(edit.text()) for key, edit in self._display_edits.items()}
        if any(not value for value in display_names.values()):
            QMessageBox.warning(self, "Source Mapping", "Global Display Name cannot be blank. Use Reset Global Names to restore built-in App headers.")
            return
        set_source_overrides(self.store, self.source_type, overrides, self.user_name)
        set_source_display_names(self.store, self.source_type, display_names, self.user_name)
        self.accept()


class DynamicColumnVisibilityDialog(QDialog):
    """Reusable column selector for dynamically sourced report sheets."""

    def __init__(self, title_text: str, groups, visible_keys: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.resize(700, 680)
        self.groups = groups
        self._checks: dict[str, QCheckBox] = {}
        root = QVBoxLayout(self)
        title = QLabel(title_text)
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel("Choose which source columns are visible. This changes only the desktop review view; the source workbook remains read-only.")
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        root.addWidget(desc)
        preset = QHBoxLayout()
        all_btn = QPushButton("Show All")
        source_btn = QPushButton("Source Only")
        all_btn.clicked.connect(lambda: self._set_visible({k for _g, _c, cols in groups for k, _l, _w in cols}))
        source_btn.clicked.connect(lambda: self._set_visible({k for _g, _c, cols in groups for k, _l, _w in cols if k.startswith("excel_")} | {"db_review_status", "db_review_comments"}))
        preset.addWidget(all_btn); preset.addWidget(source_btn); preset.addStretch()
        root.addLayout(preset)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget(); body = QVBoxLayout(holder); body.setSpacing(10)
        for group, _color, columns in groups:
            card = QFrame(); card.setObjectName("SoftCard")
            box = QGridLayout(card); box.setContentsMargins(14, 10, 14, 10)
            heading = QLabel(group if group != "Index" else "Source fields")
            heading.setStyleSheet("font-weight:700;")
            box.addWidget(heading, 0, 0, 1, 3)
            for pos, (key, label, _width) in enumerate(columns):
                cb = QCheckBox(label or f"Column {pos + 1}")
                cb.setChecked(key in visible_keys)
                self._checks[key] = cb
                box.addWidget(cb, 1 + pos // 3, pos % 3)
            body.addWidget(card)
        body.addStretch(); scroll.setWidget(holder); root.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _set_visible(self, keys: set[str]):
        for key, cb in self._checks.items():
            cb.setChecked(key in keys)

    def visible_keys(self) -> set[str]:
        return {key for key, cb in self._checks.items() if cb.isChecked()}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  ·  v{APP_VERSION}")
        self.resize(1600, 920)
        self.setMinimumSize(1180, 720)
        self.store: ProjectStore | None = None
        self.user_name = os.environ.get("USERNAME") or os.environ.get("USER") or "User"
        self.import_edits: dict[str, QLineEdit] = {}
        self._nav_buttons: list[QPushButton] = []
        self.repository_root: Path | None = load_repository_root()
        self.repository_sites: list[SiteInfo] = []
        self.selected_site: SiteInfo | None = None
        self.db_smart_report: DBSmartReport | None = None
        self.db_smart_visible_keys: set[str] = set()
        self._repository_refreshing = False
        self._spreadsheet_tables: list[SpreadsheetTableWidget] = []
        self.settings = QSettings()
        saved_columns = self.settings.value("comparison/visible_columns", [], type=list)
        saved_column_schema = self.settings.value("comparison/column_schema_version", 0)
        self.comparison_visible_keys = migrate_comparison_visible_columns(
            saved_columns, saved_column_schema
        )
        # Persist the schema marker immediately.  This makes the migration
        # one-shot: after v0.7.1, a reviewer may intentionally hide IP/LINK and
        # that preference will remain respected on later launches.
        self.settings.setValue("comparison/column_schema_version", COMPARISON_COLUMN_SCHEMA_VERSION)

        icon_path = resource_root() / "assets" / "logo.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._build_shell()
        self._build_pages()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._wire_shortcuts()
        self.set_page(0)
        self.refresh_all()

    # ------------------------- shell -------------------------
    def _build_shell(self):
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(248)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(14, 18, 14, 16)
        side.setSpacing(8)

        brand = QHBoxLayout()
        logo_path = resource_root() / "assets" / "logo.png"
        logo = QLabel()
        if logo_path.exists():
            logo.setPixmap(QIcon(str(logo_path)).pixmap(QSize(42, 42)))
        logo.setFixedSize(44, 44)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        bt = QLabel("NARI")
        bt.setObjectName("BrandTitle")
        bp = QLabel("SAUDI ADMS PROJECT")
        bp.setObjectName("BrandProject")
        bs = QLabel("MIGRATION REPORT  ·  v" + APP_VERSION)
        bs.setObjectName("BrandSub")
        brand_text.addWidget(bt)
        brand_text.addWidget(bp)
        brand_text.addWidget(bs)
        brand.addWidget(logo)
        brand.addSpacing(7)
        brand.addLayout(brand_text)
        side.addLayout(brand)
        side.addSpacing(18)

        nav_items = [
            ("Project Overview", 0, "overview"),
            ("Site Data Sources", 1, "database"),
            ("RMU Data Review", 2, "rmu"),
            ("Signal Mapping Review", 3, "signal"),
            ("Change Audit", 4, "audit"),
            ("Review Versions", 5, "versions"),
            ("Report Export", 6, "report"),
            ("Settings", 7, "settings"),
        ]
        for text, index, icon_name in nav_items:
            btn = QPushButton(text)
            btn.setIcon(app_icon(icon_name))
            btn.setIconSize(QSize(18, 18))
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, i=index: self.set_page(i))
            side.addWidget(btn)
            self._nav_buttons.append(btn)
        side.addStretch()

        workspace_caption = QLabel("PROJECT APP WORKSPACE")
        workspace_caption.setStyleSheet("color:#7F9AB2;font-size:8pt;font-weight:700;")
        side.addWidget(workspace_caption)
        self.sidebar_workspace = QLabel(str(workspace_root()))
        self.sidebar_workspace.setWordWrap(True)
        self.sidebar_workspace.setStyleSheet("color:#AFC3D4;font-size:8pt;")
        side.addWidget(self.sidebar_workspace)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("Topbar")
        topbar.setFixedHeight(82)
        top = QHBoxLayout(topbar)
        top.setContentsMargins(24, 10, 24, 10)
        left = QVBoxLayout()
        left.setSpacing(1)
        kicker = QLabel("NARI · SAUDI ADMS PROJECT · DATA MIGRATION")
        kicker.setObjectName("ProjectKicker")
        self.project_title = QLabel("No site selected")
        self.project_title.setStyleSheet("font-size:13pt;font-weight:750;")
        self.project_subtitle = QLabel("Migration Report · Select a site to validate and review migration data")
        self.project_subtitle.setObjectName("Muted")
        left.addWidget(kicker)
        left.addWidget(self.project_title)
        left.addWidget(self.project_subtitle)
        top.addLayout(left)
        top.addStretch()
        self.project_delivery_state = "SOURCES INCOMPLETE"
        self.project_state_label = QLabel("STATUS · SOURCES INCOMPLETE")
        self.project_state_label.setObjectName("ProjectStateTag")
        self.project_state_label.setToolTip("Automatically calculated from source readiness, validation and human Review progress.")
        refresh_btn = QPushButton("Refresh Sources")
        refresh_btn.setIcon(app_icon("database"))
        refresh_btn.clicked.connect(self.refresh_site_repository)
        run_btn = QPushButton("Run Validation")
        run_btn.setIcon(app_icon("overview"))
        run_btn.setObjectName("Primary")
        run_btn.clicked.connect(self.run_comparison)
        top.addWidget(self.project_state_label, alignment=Qt.AlignVCenter)
        top.addSpacing(6)
        top.addWidget(refresh_btn)
        top.addWidget(run_btn)

        self.stack = QStackedWidget()
        content_layout.addWidget(topbar)
        content_layout.addWidget(self.stack, 1)
        shell.addWidget(self.sidebar)
        shell.addWidget(content, 1)

        self.statusBar().setStyleSheet("QStatusBar{background:#FFFFFF;border-top:1px solid #DCE3EA;color:#667085;}")
        self.statusBar().showMessage("Ready")

    def _build_pages(self):
        self.dashboard_page = self._build_dashboard()
        self.import_page = self._build_import_page()
        self.comparison_page = self._build_comparison_page()
        self.db_smart_page = self._build_db_smart_page()
        self.changes_page = self._build_changes_page()
        self.versions_page = self._build_versions_page()
        self.export_page = self._build_export_page()
        self.settings_page = self._build_settings_page()
        for page in (
            self.dashboard_page,
            self.import_page,
            self.comparison_page,
            self.db_smart_page,
            self.changes_page,
            self.versions_page,
            self.export_page,
            self.settings_page,
        ):
            self.stack.addWidget(page)

    def _page_container(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)
        return page, layout

    # ------------------------- dashboard -------------------------
    def _build_dashboard(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader(
            "Saudi ADMS Migration Overview",
            "NARI delivery view for data-source readiness, automatic validation, human Review progress and formal Migration Report handover.",
        ))

        project_banner = QFrame()
        project_banner.setObjectName("ProjectBanner")
        banner = QHBoxLayout(project_banner)
        banner.setContentsMargins(18, 12, 18, 12)
        banner.setSpacing(28)
        for title_text, value_text in (
            ("Organization", "NARI"),
            ("Project", "Saudi ADMS"),
            ("Workstream", "Data Migration"),
            ("Deliverable", "Migration Report"),
        ):
            block = QVBoxLayout()
            block.setSpacing(1)
            title = QLabel(title_text)
            title.setObjectName("ProjectMetaTitle")
            value = QLabel(value_text)
            value.setObjectName("ProjectMetaValue")
            block.addWidget(title)
            block.addWidget(value)
            banner.addLayout(block)
        banner.addStretch()
        current_block = QVBoxLayout()
        current_block.setSpacing(1)
        current_title = QLabel("Current Site")
        current_title.setObjectName("ProjectMetaTitle")
        self.dashboard_context_site = QLabel("Not selected")
        self.dashboard_context_site.setObjectName("ProjectMetaValue")
        current_block.addWidget(current_title)
        current_block.addWidget(self.dashboard_context_site)
        banner.addLayout(current_block)
        layout.addWidget(project_banner)

        # Formal delivery workflow.  The top-right project state and these four
        # steps are calculated from live source readiness + stored review state.
        workflow_card = QFrame()
        workflow_card.setObjectName("WorkflowCard")
        workflow_box = QVBoxLayout(workflow_card)
        workflow_box.setContentsMargins(16, 11, 16, 11)
        workflow_box.setSpacing(7)
        workflow_title_row = QHBoxLayout()
        workflow_title = QLabel("Migration Workflow")
        workflow_title.setObjectName("WorkflowTitle")
        self.workflow_detail = QLabel("Select a site to begin")
        self.workflow_detail.setObjectName("Muted")
        workflow_title_row.addWidget(workflow_title)
        workflow_title_row.addSpacing(12)
        workflow_title_row.addWidget(self.workflow_detail)
        workflow_title_row.addStretch()
        workflow_box.addLayout(workflow_title_row)
        workflow_steps = QHBoxLayout()
        workflow_steps.setSpacing(8)
        self.workflow_step_labels = {}
        for index, (key, title) in enumerate((
            ("sources", "1  Data Sources"),
            ("validation", "2  Validation"),
            ("review", "3  Human Review"),
            ("report", "4  Migration Report"),
        )):
            label = QLabel(title)
            label.setObjectName("WorkflowPending")
            label.setAlignment(Qt.AlignCenter)
            self.workflow_step_labels[key] = label
            workflow_steps.addWidget(label, 1)
            if index < 3:
                arrow = QLabel("→")
                arrow.setObjectName("Muted")
                arrow.setAlignment(Qt.AlignCenter)
                workflow_steps.addWidget(arrow)
        workflow_box.addLayout(workflow_steps)
        layout.addWidget(workflow_card)

        # RMU review workstream.
        rmu_title_row = QHBoxLayout()
        rmu_title_row.addWidget(icon_label("rmu", 24))
        rmu_title = QLabel("RMU Data Review")
        rmu_title.setObjectName("SectionTitle")
        self.dashboard_rmu_issue_summary = QLabel("No RMU validation loaded")
        self.dashboard_rmu_issue_summary.setObjectName("Muted")
        rmu_title_row.addWidget(rmu_title)
        rmu_title_row.addSpacing(12)
        rmu_title_row.addWidget(self.dashboard_rmu_issue_summary)
        rmu_title_row.addStretch()
        layout.addLayout(rmu_title_row)

        rmu_cards = QGridLayout()
        rmu_cards.setHorizontalSpacing(12)
        rmu_cards.setVerticalSpacing(12)
        self.metric_rmu_total = MetricCard("Total RMUs", "0", "#2365A8")
        self.metric_rmu_pass = MetricCard("Pass", "0", "#12805C")
        self.metric_rmu_issues = MetricCard("With Issues", "0", "#C9871A")
        self.metric_rmu_reviewed = MetricCard("Reviewed", "0 / 0", "#6F4DA5")
        self.metric_rmu_needs_action = MetricCard("Needs Action", "0", "#B42318")
        for i, card in enumerate((
            self.metric_rmu_total, self.metric_rmu_pass, self.metric_rmu_issues,
            self.metric_rmu_reviewed, self.metric_rmu_needs_action,
        )):
            rmu_cards.addWidget(card, 0, i)
        layout.addLayout(rmu_cards)
        rmu_review_row = QHBoxLayout()
        self.dashboard_rmu_review_summary = QLabel("Review progress: 0 / 0 · 0%")
        self.dashboard_rmu_review_summary.setObjectName("Muted")
        self.dashboard_rmu_review_progress = QProgressBar()
        self.dashboard_rmu_review_progress.setRange(0, 100)
        self.dashboard_rmu_review_progress.setValue(0)
        self.dashboard_rmu_review_progress.setFormat("0%")
        rmu_review_row.addWidget(self.dashboard_rmu_review_summary)
        rmu_review_row.addWidget(self.dashboard_rmu_review_progress, 1)
        layout.addLayout(rmu_review_row)

        # Signal Mapping review workstream. Checked/Unchecked is explicit so the
        # total always reconciles and the match-rate denominator is obvious.
        signal_title_row = QHBoxLayout()
        signal_title_row.addWidget(icon_label("signal", 24))
        signal_title = QLabel("Signal Mapping Review")
        signal_title.setObjectName("SectionTitle")
        self.dashboard_signal_summary = QLabel("ZENON-ADMS IOA · ADMS SLD · active STANDARD")
        self.dashboard_signal_summary.setObjectName("Muted")
        signal_title_row.addWidget(signal_title)
        signal_title_row.addSpacing(12)
        signal_title_row.addWidget(self.dashboard_signal_summary)
        signal_title_row.addStretch()
        layout.addLayout(signal_title_row)

        signal_cards = QGridLayout()
        signal_cards.setHorizontalSpacing(10)
        signal_cards.setVerticalSpacing(12)
        self.metric_signal_total = MetricCard("Total Signals", "0", "#2365A8")
        self.metric_signal_checked = MetricCard("Checked", "0", "#2365A8")
        self.metric_signal_matched = MetricCard("Matched", "0", "#12805C")
        self.metric_signal_mismatched = MetricCard("Mismatched", "0", "#C9871A")
        self.metric_signal_unchecked = MetricCard("Unchecked", "0", "#7B8794")
        self.metric_signal_needs_action = MetricCard("Needs Action", "0", "#B42318")
        for i, card in enumerate((
            self.metric_signal_total, self.metric_signal_checked, self.metric_signal_matched,
            self.metric_signal_mismatched, self.metric_signal_unchecked, self.metric_signal_needs_action,
        )):
            signal_cards.addWidget(card, 0, i)
        layout.addLayout(signal_cards)
        signal_review_row = QHBoxLayout()
        self.dashboard_signal_review_summary = QLabel("Review progress: 0 / 0 · 0%")
        self.dashboard_signal_review_summary.setObjectName("Muted")
        self.dashboard_signal_review_progress = QProgressBar()
        self.dashboard_signal_review_progress.setRange(0, 100)
        self.dashboard_signal_review_progress.setValue(0)
        self.dashboard_signal_review_progress.setFormat("0%")
        signal_review_row.addWidget(self.dashboard_signal_review_summary)
        signal_review_row.addWidget(self.dashboard_signal_review_progress, 1)
        layout.addLayout(signal_review_row)

        lower = QHBoxLayout()
        lower.setSpacing(14)

        project_card = QFrame()
        project_card.setObjectName("Card")
        pbox = QVBoxLayout(project_card)
        pbox.setContentsMargins(20, 18, 20, 18)
        ptitle = QLabel("Current Migration Site")
        ptitle.setObjectName("SectionTitle")
        pbox.addWidget(ptitle)
        self.dash_project_name = QLabel("No site selected")
        self.dash_project_name.setStyleSheet("font-size:15pt;font-weight:700;color:#173A5E;")
        self.dash_project_path = QLabel(str(workspace_root()))
        self.dash_project_path.setWordWrap(True)
        self.dash_project_path.setObjectName("Muted")
        self.dash_last_version = QLabel("Latest version: —")
        self.dash_last_version.setObjectName("Muted")
        pbox.addSpacing(10)
        pbox.addWidget(self.dash_project_name)
        pbox.addWidget(self.dash_project_path)
        pbox.addSpacing(8)
        pbox.addWidget(self.dash_last_version)
        pbox.addStretch()
        quick = QHBoxLayout()
        b1 = QPushButton("Site Data Sources")
        b1.setIcon(app_icon("database"))
        b1.clicked.connect(lambda: self.set_page(1))
        self.dashboard_rmu_issues_button = QPushButton("Review RMU Issues")
        self.dashboard_rmu_issues_button.setIcon(app_icon("rmu"))
        self.dashboard_rmu_issues_button.setObjectName("Primary")
        self.dashboard_rmu_issues_button.setToolTip("Open RMU Data Review and show only RMUs with automatic Analysis issues.")
        self.dashboard_rmu_issues_button.clicked.connect(self.open_dashboard_rmu_issues)
        self.dashboard_signal_mismatch_button = QPushButton("Review Signal Mismatches")
        self.dashboard_signal_mismatch_button.setIcon(app_icon("signal"))
        self.dashboard_signal_mismatch_button.setToolTip("Open Signal Mapping Review and show only mismatched signals.")
        self.dashboard_signal_mismatch_button.clicked.connect(self.open_dashboard_signal_mismatches)
        quick.addWidget(b1)
        quick.addWidget(self.dashboard_rmu_issues_button)
        quick.addWidget(self.dashboard_signal_mismatch_button)
        quick.addStretch()
        pbox.addLayout(quick)

        source_card = QFrame()
        source_card.setObjectName("Card")
        sbox = QVBoxLayout(source_card)
        sbox.setContentsMargins(20, 18, 20, 18)
        stitle_row = QHBoxLayout()
        stitle_row.addWidget(icon_label("database", 20))
        stitle = QLabel("Active Data Sources")
        stitle.setObjectName("SectionTitle")
        stitle_row.addWidget(stitle)
        stitle_row.addStretch()
        sbox.addLayout(stitle_row)
        self.dashboard_sources = QListWidget()
        self.dashboard_sources.setMinimumHeight(230)
        sbox.addWidget(self.dashboard_sources)

        lower.addWidget(project_card, 1)
        lower.addWidget(source_card, 1)
        layout.addLayout(lower, 1)
        return page

    # ------------------------- site repository -------------------------
    def _build_import_page(self):
        """Repository-first site/source management page.

        The user maintains one root folder with one subfolder per site. The app
        normally scans those folders read-only and binds the selected site to its private
        application workspace automatically. No manual project creation is required.
        """
        page, layout = self._page_container()

        header_row = QHBoxLayout()
        header_row.addWidget(PageHeader(
            "Site Data Sources",
            "Manage the source tables used by Saudi ADMS migration review. Sources are organized by business module so each RMU Data Review and Signal Mapping Review dependency is visible and auditable.",
        ), 1)
        header_row.addStretch()
        open_root_btn = QPushButton("Open Workspace")
        open_root_btn.clicked.connect(self.open_repository_root)
        change_btn = QPushButton("Select Workspace")
        change_btn.setObjectName("Primary")
        change_btn.clicked.connect(self.choose_repository_root)
        header_row.addWidget(open_root_btn, alignment=Qt.AlignBottom)
        header_row.addWidget(change_btn, alignment=Qt.AlignBottom)
        layout.addLayout(header_row)

        root_card = QFrame()
        root_card.setObjectName("SoftCard")
        root_box = QHBoxLayout(root_card)
        root_box.setContentsMargins(14, 10, 14, 10)
        root_box.addWidget(QLabel("Workspace"))
        self.repository_root_edit = QLineEdit()
        self.repository_root_edit.setReadOnly(True)
        self.repository_root_edit.setPlaceholderText("Choose a workspace folder such as D:\\Workspace\\SS")
        root_box.addWidget(self.repository_root_edit, 1)
        self.repository_summary = QLabel("0 sites")
        self.repository_summary.setObjectName("Muted")
        root_box.addWidget(self.repository_summary)
        layout.addWidget(root_card)

        # Resizable master/detail layout. The site list remains compact by default,
        # but the reviewer can drag the splitter when site names become longer.
        self.site_splitter = QSplitter(Qt.Horizontal)
        self.site_splitter.setChildrenCollapsible(False)
        self.site_splitter.setHandleWidth(6)

        # Left: site discovery / status list.
        site_card = QFrame()
        site_card.setObjectName("Card")
        site_card.setMinimumWidth(240)
        site_box = QVBoxLayout(site_card)
        site_box.setContentsMargins(16, 16, 16, 16)
        site_title = QLabel("Sites")
        site_title.setObjectName("SectionTitle")
        site_box.addWidget(site_title)
        self.site_search_edit = QLineEdit()
        self.site_search_edit.setPlaceholderText("Search site...")
        self.site_search_edit.setClearButtonEnabled(True)
        self.site_search_edit.textChanged.connect(self._render_site_list)
        site_box.addWidget(self.site_search_edit)
        self.site_list = QListWidget()
        self.site_list.currentItemChanged.connect(self._site_item_changed)
        site_box.addWidget(self.site_list, 1)
        self.site_splitter.addWidget(site_card)

        # Right: current site's live source inventory.
        detail_card = QFrame()
        detail_card.setObjectName("Card")
        detail_box = QVBoxLayout(detail_card)
        detail_box.setContentsMargins(18, 16, 18, 16)
        detail_top = QHBoxLayout()
        detail_names = QVBoxLayout()
        self.site_detail_title = QLabel("Select a site")
        self.site_detail_title.setObjectName("SectionTitle")
        self.site_detail_path = QLabel("Choose a repository root, then select a detected site.")
        self.site_detail_path.setObjectName("Muted")
        self.site_detail_path.setWordWrap(True)
        detail_names.addWidget(self.site_detail_title)
        detail_names.addWidget(self.site_detail_path)
        detail_top.addLayout(detail_names, 1)
        self.site_status_label = QLabel("—")
        self.site_status_label.setStyleSheet("font-weight:700;color:#667085;")
        detail_top.addWidget(self.site_status_label)
        self.regenerate_zenon_sld_btn = QPushButton("Regenerate ZENON SLD")
        self.regenerate_zenon_sld_btn.setToolTip(
            "Parse the selected site's ZENON XML and safely replace <site>/ZENON-SLD.csv. "
            "The existing CSV is kept if parsing or writing fails."
        )
        self.regenerate_zenon_sld_btn.setEnabled(False)
        self.regenerate_zenon_sld_btn.clicked.connect(self.regenerate_zenon_sld)
        detail_top.addWidget(self.regenerate_zenon_sld_btn)
        open_site_btn = QPushButton("Open Site Folder")
        open_site_btn.clicked.connect(self.open_selected_site_folder)
        detail_top.addWidget(open_site_btn)
        detail_box.addLayout(detail_top)

        note = QLabel(
            "Recommended standard names: SE.xlsx · ZENON.XML · ZENON-DB.csv · ZENON-SLD.csv · "
            "ADMS-DB.csv · ADMS-SLD.csv · ZENON-ADMS-IOA.csv. "
            "Legacy names such as ADF-SE.xlsx and ADF.XML are also recognized. "
            "ZENON XML is the graphical source of truth; ZENON-SLD.csv is a derived/fallback file and can be regenerated explicitly. "
            "Combined XML files (for example ABN-ABN2.XML) are filtered by the selected site's parsed feeder, so ABN and ABN2 stay isolated."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        detail_box.addWidget(note)

        # Business-module dependency view. A shared physical table deliberately
        # appears in every module that consumes it (for example ADMS SLD). This
        # is much clearer than a flat file inventory because reviewers can see
        # exactly which tables feed RMU Data Review vs Signal Mapping Review.
        self.module_source_tabs = QTabWidget()
        self.module_source_tables: dict[str, QTableWidget] = {}
        for module in MODULE_SOURCE_GROUPS:
            module_page = QWidget()
            module_box = QVBoxLayout(module_page)
            module_box.setContentsMargins(8, 10, 8, 8)
            module_box.setSpacing(8)
            module_desc = QLabel(module.description)
            module_desc.setObjectName("Muted")
            module_desc.setWordWrap(True)
            module_box.addWidget(module_desc)

            table = QTableWidget(0, 8)
            table.setHorizontalHeaderLabels([
                "Table", "Role in Module", "Expected Name", "Detected File",
                "File Status", "Schema", "Modified", "Size"
            ])
            _configure_table_base(table)
            _set_interactive_column(table, 0, 165)
            _set_interactive_column(table, 1, 255)
            _set_interactive_column(table, 2, 180)
            _set_stretch_column(table, 3)
            _set_fixed_column(table, 4, 120)
            _set_fixed_column(table, 5, 120)
            _set_fixed_column(table, 6, 175)
            _set_fixed_column(table, 7, 90)
            table.itemDoubleClicked.connect(self.open_source_mapping)
            self.module_source_tables[module.key] = table
            module_box.addWidget(table, 1)
            module_icon = app_icon("rmu" if module.key == "rmu_review" else "signal")
            self.module_source_tabs.addTab(module_page, module_icon, module.label)
        detail_box.addWidget(self.module_source_tabs, 1)

        footer = QHBoxLayout()
        self.repository_last_scan = QLabel("Last scan: —")
        self.repository_last_scan.setObjectName("Muted")
        footer.addWidget(self.repository_last_scan)
        footer.addStretch()
        mapping_btn = QPushButton("Edit Selected Table Mapping")
        mapping_btn.setToolTip("Edit column mapping and Display Names for the selected table in the current module.")
        mapping_btn.clicked.connect(self.open_source_mapping)
        footer.addWidget(mapping_btn)
        advanced_btn = QPushButton("Advanced Manual Import")
        advanced_btn.clicked.connect(self.advanced_manual_import)
        footer.addWidget(advanced_btn)
        detail_box.addLayout(footer)

        self.site_splitter.addWidget(detail_card)
        self.site_splitter.setStretchFactor(0, 0)
        self.site_splitter.setStretchFactor(1, 1)
        self.site_splitter.setSizes([300, 1200])
        layout.addWidget(self.site_splitter, 1)
        return page

    def _source_description(self, key: str) -> str:
        return {
            "se_list": "SE equipment detail list (SS / FEEDER / EQUIPMENT / EQUIP. TYPE / OH / UG)",
            "zenon_xml": "Zenon XML; combined files are filtered by the selected site feeder; Picture/@ShortName maps to DATA Screen name",
            "zenon_db": "Zenon device and driver database export",
            "zenon_sld": "Derived from Zenon XML; used as fallback when XML is unavailable",
            "adms_db": "ADMS database migration reference",
            "adms_sld": "ADMS SLD / RMU association result",
            "ioa": "ZENON–ADMS IOA point mapping source",
        }.get(key, "Project source file")

    def open_dashboard_rmu_issues(self):
        """Open RMU Data Review with only automatic Analysis issues visible."""
        if not self.store:
            return
        issue_count = sum(analysis_review_state(row).issue_count > 0 for row in self.store.rows())
        if issue_count <= 0:
            return
        self.set_page(2)
        self.search_edit.clear()
        self.rmu_review_filter_combo.setCurrentText("ALL REVIEWS")
        self.analysis_combo.setCurrentText("ANY MISMATCH")
        self.refresh_comparison()
        self.statusBar().showMessage(f"Showing {issue_count} RMU(s) with Analysis issues", 4000)

    def open_dashboard_signal_mismatches(self):
        """Open Signal Mapping Review with only automatic mismatches visible."""
        if not self.store:
            return
        self.set_page(3)
        if not self.db_smart_report:
            self.refresh_db_smart_report()
        if not self.db_smart_report:
            return
        mismatch_count = 0
        if self.db_smart_report.analysis_column is not None:
            mismatch_count = sum(
                clean(row.values[self.db_smart_report.analysis_column]).upper() == "FALSE"
                for row in self.db_smart_report.rows
            )
        if mismatch_count <= 0:
            return
        self.db_smart_search.clear()
        self.db_smart_review_combo.setCurrentText("ALL REVIEWS")
        self.db_smart_result_combo.setCurrentText("MISMATCHED")
        self._render_db_smart_rows()
        self.statusBar().showMessage(f"Showing {mismatch_count} mismatched signal row(s)", 4000)

    # ------------------------- comparison -------------------------
    def _build_comparison_page(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader(
            "RMU Data Review",
            "Saudi ADMS RMU migration consistency review across SE, zenOn and ADMS. Analysis is calculated automatically; Review is a separate human workflow state. Drag to select cells; Ctrl adds non-contiguous blocks; double-click a value for an audited correction or SE Comment.",
        ))

        controls = QFrame()
        controls.setObjectName("Card")
        cbox = QHBoxLayout(controls)
        cbox.setContentsMargins(14, 10, 14, 10)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search RMU, feeder, IP, type, remarks, resolution...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.refresh_comparison)
        self.search_edit.setMinimumWidth(330)
        self.rmu_review_filter_combo = QComboBox()
        self.rmu_review_filter_combo.addItems(["ALL REVIEWS", "UNREVIEWED", "REVIEWED", "NEEDS ACTION"])
        self.rmu_review_filter_combo.setToolTip("Filter only by the manual human Review state. Automated Analysis is filtered separately.")
        self.rmu_review_filter_combo.currentTextChanged.connect(self.refresh_comparison)
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems([
            "ALL ANALYSIS", "PASSED", "ANY MISMATCH",
            "1 ISSUE", "2 ISSUES", "MULTIPLE ISSUES", "CRITICAL",
            "NAME MISMATCH", "FEEDER MISMATCH", "SMART MISMATCH", "TYPE MISMATCH",
            "IP MISMATCH", "LINK MISMATCH",
        ])
        self.analysis_combo.setToolTip("Filter by Analysis result")
        self.analysis_combo.currentTextChanged.connect(self.refresh_comparison)
        review_btn = QPushButton("Set Review")
        review_btn.setToolTip("Set the manual Review state for selected RMUs: UNREVIEWED, REVIEWED, or NEEDS ACTION")
        review_btn.clicked.connect(self.set_comparison_review_status)
        columns_btn = QPushButton("Columns")
        columns_btn.setToolTip("Show or hide RMU Data Review groups and fields")
        columns_btn.clicked.connect(self.open_comparison_columns)
        reset_btn = QPushButton("Reset View")
        reset_btn.setToolTip("Restore all RMU Data Review columns")
        reset_btn.clicked.connect(self.reset_comparison_columns)
        self.comparison_summary = QLabel("No validation data")
        self.comparison_summary.setObjectName("Muted")
        self.comparison_summary.setWordWrap(True)
        self.comparison_summary.setMinimumWidth(620)
        self.comparison_summary.setToolTip(
            "Total = all RMU rows. Shown = rows after filters. "
            "Each displayed issue count is the number of RMU rows where that Analysis field is FALSE. Zero-count fields are hidden."
        )
        cbox.addWidget(self.search_edit)
        cbox.addWidget(self.rmu_review_filter_combo)
        cbox.addWidget(self.analysis_combo)
        cbox.addWidget(review_btn)
        cbox.addWidget(columns_btn)
        cbox.addWidget(reset_btn)
        cbox.addStretch()
        layout.addWidget(controls)

        summary_card = QFrame()
        summary_card.setObjectName("SoftCard")
        summary_box = QVBoxLayout(summary_card)
        summary_box.setContentsMargins(12, 9, 12, 9)
        summary_box.setSpacing(3)
        summary_box.addWidget(self.comparison_summary)
        self.comparison_review_progress = QLabel("Review 0 / 0 · Resolution 0 / 0 issues")
        self.comparison_review_progress.setObjectName("Muted")
        self.comparison_review_progress.setWordWrap(True)
        self.comparison_review_progress.setToolTip(
            "Review is the human workflow state. Resolution counts structured decisions for active FALSE Analysis fields."
        )
        summary_box.addWidget(self.comparison_review_progress)
        layout.addWidget(summary_card)

        # Minimal review legend: three row severities plus one universal FALSE
        # mismatch highlight. The field name itself identifies the issue, so
        # NAME/FEEDER/SMART/TYPE/IP/LINK do not need separate colors.
        legend = QFrame()
        legend.setObjectName("SoftCard")
        legend_box = QHBoxLayout(legend)
        legend_box.setContentsMargins(12, 7, 12, 7)
        legend_box.setSpacing(10)
        legend_title = QLabel("Analysis")
        legend_title.setStyleSheet("font-weight:700;")
        legend_box.addWidget(legend_title)
        for color, label, tip in [
            ("#EAF7F0", "Pass", "No Analysis field is FALSE"),
            ("#FFF8D8", "Has Issues", "One or two Analysis fields are FALSE"),
            ("#FDECEC", "Critical", "NAME is FALSE or three or more Analysis fields are FALSE"),
            ("#F7D7D7", "FALSE = mismatch", "All FALSE Analysis cells use the same mismatch highlight"),
        ]:
            swatch = QLabel()
            swatch.setFixedSize(13, 13)
            swatch.setStyleSheet(f"background:{color};border:1px solid #C9D2DC;border-radius:3px;")
            swatch.setToolTip(tip)
            text = QLabel(label)
            text.setObjectName("Muted")
            text.setToolTip(tip)
            legend_box.addWidget(swatch)
            legend_box.addWidget(text)
        note = QLabel("The column name identifies which field failed; Review and Resolution stay neutral.")
        note.setObjectName("Muted")
        legend_box.addSpacing(8)
        legend_box.addWidget(note)
        legend_box.addStretch()
        layout.addWidget(legend)

        self.comparison_table = SpreadsheetTableWidget(0, len(COMPARISON_COLUMNS))
        self.comparison_header = GroupedReportHeader(self._comparison_groups(), self.comparison_table)
        self.comparison_table.setHorizontalHeader(self.comparison_header)
        self.comparison_table.setAlternatingRowColors(True)
        self.comparison_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._register_spreadsheet_table(self.comparison_table)
        self.comparison_table.verticalHeader().setVisible(False)
        self.comparison_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.comparison_table.horizontalHeader().setMinimumSectionSize(55)
        self.comparison_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_table.setWordWrap(False)
        self.comparison_table.setSortingEnabled(False)
        self.comparison_table.cellDoubleClicked.connect(self.edit_comparison_cell)
        self.comparison_table.verticalHeader().setDefaultSectionSize(32)
        self._configure_comparison_headers()

        # Frozen row locator: keep row identity visible while the business grid
        # scrolls horizontally across dozens of source columns.  It is a
        # presentation companion only; the source of truth remains the main
        # RMU Data Review table/store.
        self.comparison_locator = SpreadsheetTableWidget(0, 4)
        locator_groups = (("Row Locator", "#E8EDF3", (
            ("locator_no", "No.", 55),
            ("locator_rmu", "RMU", 90),
            ("locator_analysis", "Analysis", 115),
            ("locator_review", "Review", 115),
        )),)
        self.comparison_locator_header = GroupedReportHeader(locator_groups, self.comparison_locator)
        self.comparison_locator.setHorizontalHeader(self.comparison_locator_header)
        self.comparison_locator.setHorizontalHeaderLabels(["No.", "RMU", "Analysis", "Review"])
        self.comparison_locator.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.comparison_locator.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.comparison_locator.verticalHeader().setVisible(False)
        self.comparison_locator.verticalHeader().setDefaultSectionSize(32)
        self.comparison_locator.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.comparison_locator.setColumnWidth(0, 55)
        self.comparison_locator.setColumnWidth(1, 90)
        self.comparison_locator.setColumnWidth(2, 115)
        self.comparison_locator.setColumnWidth(3, 115)
        self.comparison_locator.setFixedWidth(55 + 90 + 115 + 115 + 4)
        self.comparison_locator.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comparison_locator.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comparison_locator.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_locator.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_locator.setWordWrap(False)
        self.comparison_locator.setFocusPolicy(Qt.NoFocus)
        self.comparison_locator.cellClicked.connect(self._activate_comparison_row_from_locator)
        self.comparison_locator.cellDoubleClicked.connect(self._edit_comparison_locator_review)

        # Synchronize the two views.  Hover/current-row state is mirrored but
        # selection remains owned by the main spreadsheet grid so Ctrl/Shift
        # multi-range selection keeps its normal Excel-like behavior.
        self.comparison_table.verticalScrollBar().valueChanged.connect(self.comparison_locator.verticalScrollBar().setValue)
        self.comparison_locator.verticalScrollBar().valueChanged.connect(self.comparison_table.verticalScrollBar().setValue)
        self.comparison_table.hoverRowChanged.connect(self.comparison_locator.set_tracked_hover_row)
        self.comparison_locator.hoverRowChanged.connect(self.comparison_table.set_tracked_hover_row)
        self.comparison_table.activeRowChanged.connect(self.comparison_locator.set_tracked_active_row)

        grid_host = QWidget()
        grid_layout = QHBoxLayout(grid_host)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(6)
        grid_layout.addWidget(self.comparison_locator, 0)
        grid_layout.addWidget(self.comparison_table, 1)
        layout.addWidget(grid_host, 1)
        return page

    def _activate_comparison_row_from_locator(self, row: int, _column: int = 0) -> None:
        """Make a locator click activate the same row without moving horizontally."""
        if not hasattr(self, "comparison_table") or row < 0 or row >= self.comparison_table.rowCount():
            return
        old_h = self.comparison_table.horizontalScrollBar().value()
        current_col = self.comparison_table.currentColumn()
        if current_col < 0 or current_col >= self.comparison_table.columnCount() or self.comparison_table.isColumnHidden(current_col):
            current_col = next((c for c in range(self.comparison_table.columnCount()) if not self.comparison_table.isColumnHidden(c)), 0)
        item = self.comparison_table.item(row, current_col)
        if item is not None:
            self.comparison_table.clear_spreadsheet_selection()
            item.setSelected(True)
            self.comparison_table.setCurrentItem(item)
            self.comparison_table.scrollToItem(item, QAbstractItemView.EnsureVisible)
        self.comparison_table.set_tracked_active_row(row)
        self.comparison_locator.set_tracked_active_row(row)
        QTimer.singleShot(0, lambda value=old_h: self.comparison_table.horizontalScrollBar().setValue(value))

    def _edit_comparison_locator_review(self, row: int, column: int) -> None:
        """Double-click the frozen Review cell to edit one RMU directly."""
        if column != 3:
            return
        self._activate_comparison_row_from_locator(row, column)
        self.set_comparison_review_status()

    def _refresh_comparison_locator(self, shown) -> None:
        """Render the fixed No./RMU/Status identity strip for current rows."""
        if not hasattr(self, "comparison_locator"):
            return
        self.comparison_locator.setRowCount(len(shown))
        review_labels = {"UNREVIEWED": "Unreviewed", "REVIEWED": "Reviewed", "NEEDS ACTION": "Needs Action"}
        review_colors = {"UNREVIEWED": "#F3F4F6", "REVIEWED": "#EAF7F0", "NEEDS ACTION": "#FFF0E0"}
        for r, (data, review_status) in enumerate(shown):
            state = analysis_review_state(data)
            values = [
                clean(data.get("no", "")),
                clean(data.get("rmu", "")),
                state.row_label,
                review_labels.get(review_status, review_status.title()),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                tooltip = (
                    f"RMU {clean(data.get('rmu', ''))} · Analysis: {state.row_label} · Review: {review_status}" +
                    (f" · Mismatch: {', '.join(state.false_fields)}" if state.false_fields else "")
                )
                if c == 3:
                    tooltip += " · Double-click: pass rows set Review directly; issue rows open structured Resolution"
                item.setToolTip(tooltip)
                if c < 2:
                    item.setBackground(QColor("#FFFFFF"))
                elif c == 2:
                    item.setBackground(QColor("#" + state.row_color))
                else:
                    item.setBackground(QColor(review_colors.get(review_status, "#F3F4F6")))
                if c in {0, 1, 2, 3}:
                    font = item.font(); font.setBold(True); item.setFont(font)
                if c in {2, 3}:
                    item.setTextAlignment(Qt.AlignCenter)
                self.comparison_locator.setItem(r, c, item)
        # Keep the same vertical viewport after search/filter refreshes.
        self.comparison_locator.verticalScrollBar().setValue(self.comparison_table.verticalScrollBar().value())

    def _comparison_groups(self):
        return apply_display_names_to_groups(
            COMPARISON_GROUPS, self.store, RMU_REVIEW_DISPLAY_BINDINGS
        )

    def _configure_comparison_headers(self):
        # Internal keys remain fixed; application-global Display Names affect only the
        # visible App/Excel presentation labels.
        groups = self._comparison_groups()
        columns = [column for _group, _color, cols in groups for column in cols]
        if hasattr(self, "comparison_header"):
            self.comparison_header.set_groups(groups)
        self.comparison_table.setHorizontalHeaderLabels([label for _key, label, _width in columns])
        for index, (key, label, width) in enumerate(columns):
            self.comparison_table.setColumnWidth(index, max(70, int(width * 1.05)))
            item = self.comparison_table.horizontalHeaderItem(index)
            if item:
                group = next((g for g, _c, cols in groups if any(k == key for k, _l, _w in cols)), "")
                item.setToolTip(f"{group} / {label}" if group and group != "Index" else label)
        self._apply_comparison_column_visibility()

    def _apply_comparison_column_visibility(self):
        if not hasattr(self, "comparison_table"):
            return
        for index, (key, _label, _width) in enumerate(COMPARISON_COLUMNS):
            self.comparison_table.setColumnHidden(index, key not in self.comparison_visible_keys)
        header = self.comparison_table.horizontalHeader()
        header.viewport().update()

    def open_comparison_columns(self):
        dialog = ColumnVisibilityDialog(self._comparison_groups(), self.comparison_visible_keys, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.comparison_visible_keys = dialog.visible_keys()
        self.settings.setValue("comparison/visible_columns", sorted(self.comparison_visible_keys))
        self._apply_comparison_column_visibility()
        self.statusBar().showMessage("RMU Data Review column view saved", 4000)

    def reset_comparison_columns(self):
        self.comparison_visible_keys = {key for key, _label, _width in COMPARISON_COLUMNS}
        self.settings.setValue("comparison/visible_columns", sorted(self.comparison_visible_keys))
        self._apply_comparison_column_visibility()
        self.statusBar().showMessage("RMU Data Review view reset to all columns", 4000)

    # ------------------------- DB Smart Report -------------------------
    def _build_db_smart_page(self):
        page, layout = self._page_container()
        header_row = QHBoxLayout()
        header_row.addWidget(PageHeader(
            "Signal Mapping Review",
            "Saudi ADMS signal migration review built from ZENON-ADMS IOA, ADMS SLD and the active application STANDARD reference. Drag to select cells; Ctrl adds non-contiguous blocks; click outside the grid to clear selection.",
        ), 1)
        standard_btn = QPushButton("Update STANDARD...")
        standard_btn.setToolTip("Validate and install a new application-wide IOA STANDARD.xlsx reference table.")
        standard_btn.clicked.connect(self.update_standard_reference)
        header_row.addWidget(standard_btn, alignment=Qt.AlignBottom)
        refresh_btn = QPushButton("Refresh Mapping")
        refresh_btn.setObjectName("Primary")
        refresh_btn.clicked.connect(self.refresh_db_smart_report)
        header_row.addWidget(refresh_btn, alignment=Qt.AlignBottom)
        layout.addLayout(header_row)

        source_card = QFrame(); source_card.setObjectName("Card")
        source_box = QGridLayout(source_card); source_box.setContentsMargins(16, 12, 16, 12)
        self.db_smart_source_label = QLabel("Source: —")
        self.db_smart_sheet_label = QLabel("Sheet: —")
        self.db_smart_meta_label = QLabel("Rows: 0")
        self.db_smart_source_label.setObjectName("Muted")
        self.db_smart_sheet_label.setObjectName("Muted")
        self.db_smart_meta_label.setObjectName("Muted")
        self.db_smart_source_label.setWordWrap(True)
        open_btn = QPushButton("Open IOA File")
        open_btn.clicked.connect(self.open_db_smart_source)
        source_box.addWidget(self.db_smart_source_label, 0, 0, 1, 3)
        source_box.addWidget(self.db_smart_sheet_label, 1, 0)
        source_box.addWidget(self.db_smart_meta_label, 1, 1)
        source_box.addWidget(open_btn, 0, 3, 2, 1)
        source_box.setColumnStretch(0, 1); source_box.setColumnStretch(1, 1); source_box.setColumnStretch(2, 1)
        layout.addWidget(source_card)

        controls = QFrame(); controls.setObjectName("Card")
        cbox = QHBoxLayout(controls); cbox.setContentsMargins(14, 10, 14, 10)
        self.db_smart_search = QLineEdit(); self.db_smart_search.setClearButtonEnabled(True)
        self.db_smart_search.setPlaceholderText("Search RMU, signal, GSS-FID, DOT number, comments...")
        self.db_smart_search.textChanged.connect(self._render_db_smart_rows)
        self.db_smart_review_combo = QComboBox()
        self.db_smart_review_combo.addItems(["ALL REVIEWS", "UNREVIEWED", "REVIEWED", "NEEDS ACTION"])
        self.db_smart_review_combo.currentTextChanged.connect(self._render_db_smart_rows)
        self.db_smart_result_combo = QComboBox()
        self.db_smart_result_combo.addItems(["ALL RESULTS", "MATCHED", "MISMATCHED", "UNCHECKED"])
        self.db_smart_result_combo.setToolTip("Filter by automatic Signal Mapping validation result.")
        self.db_smart_result_combo.currentTextChanged.connect(self._render_db_smart_rows)
        signal_review_btn = QPushButton("Set Review")
        signal_review_btn.setToolTip("Set the manual Review state for selected signal rows")
        signal_review_btn.clicked.connect(self.set_db_smart_review_status)
        columns_btn = QPushButton("Columns")
        columns_btn.clicked.connect(self.open_db_smart_columns)
        self.db_smart_summary = QLabel("No Signal Mapping Review loaded")
        self.db_smart_summary.setObjectName("Muted")
        self.db_smart_summary.setWordWrap(True)
        self.db_smart_summary.setMinimumWidth(620)
        cbox.addWidget(self.db_smart_search, 1)
        cbox.addWidget(self.db_smart_review_combo)
        cbox.addWidget(self.db_smart_result_combo)
        cbox.addWidget(signal_review_btn)
        cbox.addWidget(columns_btn)
        cbox.addStretch()
        layout.addWidget(controls)

        db_summary_card = QFrame()
        db_summary_card.setObjectName("SoftCard")
        db_summary_box = QVBoxLayout(db_summary_card)
        db_summary_box.setContentsMargins(12, 9, 12, 9)
        db_summary_box.setSpacing(3)
        db_summary_box.addWidget(self.db_smart_summary)
        signal_review_guide = QLabel(
            "Review workflow: Matched/Mismatched is automatic. Mark Reviewed after verification; use Needs Action for mapping corrections. "
            "If the validation content for a reviewed signal changes, that row automatically returns to Unreviewed while Comments and Audit history remain available."
        )
        signal_review_guide.setObjectName("Muted")
        signal_review_guide.setWordWrap(True)
        db_summary_box.addWidget(signal_review_guide)
        layout.addWidget(db_summary_card)

        self.db_smart_stack = QStackedWidget()
        self.db_smart_empty = EmptyState(
            "Signal Mapping Review is not available",
            "This module requires site ZENON-ADMS-IOA.csv and ADMS-SLD.csv. STANDARD is application-managed: a validated user override is used when present, otherwise the bundled default is used. No site REPORT workbook is read.",
        )
        self.db_smart_table = SpreadsheetTableWidget(0, 0)
        # Keep one persistent custom header for the lifetime of the page.
        # Replacing QHeaderView objects on each stacked-page visit caused the
        # two-level Excel-style titles to disappear after navigation.
        self.db_smart_header = GroupedReportHeader((), self.db_smart_table)
        self.db_smart_table.setHorizontalHeader(self.db_smart_header)
        self.db_smart_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._register_spreadsheet_table(self.db_smart_table)
        self.db_smart_table.verticalHeader().setVisible(False)
        self.db_smart_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.db_smart_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.db_smart_table.setWordWrap(False)
        self.db_smart_table.cellDoubleClicked.connect(self.edit_db_smart_cell)
        self.db_smart_table.verticalHeader().setDefaultSectionSize(32)

        # Signal Mapping Review is also a wide grid.  Keep RMU / Type / Review
        # visible in a compact locator while ZENON / ADMS / STANDARD columns
        # scroll horizontally.
        self.db_smart_locator = SpreadsheetTableWidget(0, 3)
        db_locator_groups = (("Row Locator", "#E8EDF3", (
            ("locator_rmu", "RMU", 90),
            ("locator_type", "Type", 75),
            ("locator_review", "Review", 105),
        )),)
        self.db_smart_locator_header = GroupedReportHeader(db_locator_groups, self.db_smart_locator)
        self.db_smart_locator.setHorizontalHeader(self.db_smart_locator_header)
        self.db_smart_locator.setHorizontalHeaderLabels(["RMU", "Type", "Review"])
        self.db_smart_locator.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.db_smart_locator.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.db_smart_locator.verticalHeader().setVisible(False)
        self.db_smart_locator.verticalHeader().setDefaultSectionSize(32)
        self.db_smart_locator.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.db_smart_locator.setColumnWidth(0, 90)
        self.db_smart_locator.setColumnWidth(1, 75)
        self.db_smart_locator.setColumnWidth(2, 105)
        self.db_smart_locator.setFixedWidth(90 + 75 + 105 + 4)
        self.db_smart_locator.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.db_smart_locator.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.db_smart_locator.setFocusPolicy(Qt.NoFocus)
        self.db_smart_locator.cellClicked.connect(self._activate_db_smart_row_from_locator)
        self.db_smart_locator.cellDoubleClicked.connect(self._edit_db_smart_locator_review)

        self.db_smart_table.verticalScrollBar().valueChanged.connect(self.db_smart_locator.verticalScrollBar().setValue)
        self.db_smart_locator.verticalScrollBar().valueChanged.connect(self.db_smart_table.verticalScrollBar().setValue)
        self.db_smart_table.hoverRowChanged.connect(self.db_smart_locator.set_tracked_hover_row)
        self.db_smart_locator.hoverRowChanged.connect(self.db_smart_table.set_tracked_hover_row)
        self.db_smart_table.activeRowChanged.connect(self.db_smart_locator.set_tracked_active_row)

        self.db_smart_table_host = QWidget()
        host_layout = QHBoxLayout(self.db_smart_table_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(6)
        host_layout.addWidget(self.db_smart_locator, 0)
        host_layout.addWidget(self.db_smart_table, 1)

        self.db_smart_stack.addWidget(self.db_smart_empty)
        self.db_smart_stack.addWidget(self.db_smart_table_host)
        layout.addWidget(self.db_smart_stack, 1)
        return page

    def _activate_db_smart_row_from_locator(self, row: int, _column: int = 0) -> None:
        if not hasattr(self, "db_smart_table") or row < 0 or row >= self.db_smart_table.rowCount():
            return
        old_h = self.db_smart_table.horizontalScrollBar().value()
        current_col = self.db_smart_table.currentColumn()
        if current_col < 0 or current_col >= self.db_smart_table.columnCount() or self.db_smart_table.isColumnHidden(current_col):
            current_col = next((c for c in range(self.db_smart_table.columnCount()) if not self.db_smart_table.isColumnHidden(c)), 0)
        item = self.db_smart_table.item(row, current_col)
        if item is not None:
            self.db_smart_table.clear_spreadsheet_selection()
            item.setSelected(True)
            self.db_smart_table.setCurrentItem(item)
            self.db_smart_table.scrollToItem(item, QAbstractItemView.EnsureVisible)
        self.db_smart_table.set_tracked_active_row(row)
        self.db_smart_locator.set_tracked_active_row(row)
        QTimer.singleShot(0, lambda value=old_h: self.db_smart_table.horizontalScrollBar().setValue(value))

    def _edit_db_smart_locator_review(self, row: int, column: int) -> None:
        """Double-click the frozen Signal Review cell to edit one signal directly."""
        if column != 2:
            return
        self._activate_db_smart_row_from_locator(row, column)
        self.set_db_smart_review_status()

    def _db_smart_groups(self, report: DBSmartReport):
        review_group = ("Review", "#D8E1EA", (
            ("db_review_status", "Review", 125),
            ("db_review_comments", "Comments", 300),
        ))
        source_groups = apply_display_names_to_groups(
            report.group_definitions, self.store, SIGNAL_REVIEW_DISPLAY_BINDINGS
        )
        return (review_group,) + tuple(source_groups)

    def _configure_db_smart_table(self, report: DBSmartReport):
        groups = self._db_smart_groups(report)
        columns = [column for _group, _color, cols in groups for column in cols]
        self.db_smart_columns = columns
        all_keys = {key for key, _label, _width in columns}
        saved = self.settings.value("db_smart/visible_columns", [], type=list)
        if not self.db_smart_visible_keys:
            self.db_smart_visible_keys = (set(saved) & all_keys) if saved else set(all_keys)
        else:
            self.db_smart_visible_keys &= all_keys
            self.db_smart_visible_keys |= {"db_review_status", "db_review_comments"}
        self.db_smart_table.setColumnCount(len(columns))
        # Reuse the same QHeaderView instance across refresh/navigation cycles.
        # This avoids a PySide/Qt ownership race where a replaced custom header
        # can be deferred-deleted after the page is switched away and back.
        if not hasattr(self, "db_smart_header") or self.db_smart_table.horizontalHeader() is not self.db_smart_header:
            self.db_smart_header = GroupedReportHeader(groups, self.db_smart_table)
            self.db_smart_table.setHorizontalHeader(self.db_smart_header)
        else:
            self.db_smart_header.set_groups(groups)
        self.db_smart_table.setHorizontalHeaderLabels([label for _key, label, _width in columns])
        self.db_smart_header.setVisible(True)
        self.db_smart_header.setFixedHeight(self.db_smart_header.TOP_HEIGHT + self.db_smart_header.BOTTOM_HEIGHT)
        self.db_smart_header.setSectionResizeMode(QHeaderView.Fixed)
        self.db_smart_header.setMinimumSectionSize(50)
        for index, (key, _label, width) in enumerate(columns):
            self.db_smart_table.setColumnWidth(index, max(55, int(width)))
            self.db_smart_table.setColumnHidden(index, key not in self.db_smart_visible_keys)

    def open_db_smart_columns(self):
        if not self.db_smart_report:
            QMessageBox.information(self, "Signal Mapping Review", "Load a Signal Mapping Review first.")
            return
        groups = self._db_smart_groups(self.db_smart_report)
        dialog = DynamicColumnVisibilityDialog("Signal Mapping Review Columns", groups, self.db_smart_visible_keys, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.db_smart_visible_keys = dialog.visible_keys()
        self.settings.setValue("db_smart/visible_columns", sorted(self.db_smart_visible_keys))
        self._apply_db_smart_visibility()

    def _apply_db_smart_visibility(self):
        if not hasattr(self, "db_smart_table") or not hasattr(self, "db_smart_columns"):
            return
        for index, (key, _label, _width) in enumerate(self.db_smart_columns):
            self.db_smart_table.setColumnHidden(index, key not in self.db_smart_visible_keys)
        header = self.db_smart_table.horizontalHeader()
        header.setVisible(True)
        header.viewport().update()

    def _restore_db_smart_header(self):
        """Force the persistent grouped header visible after stack navigation."""
        if not hasattr(self, "db_smart_table") or not hasattr(self, "db_smart_header"):
            return
        if self.db_smart_table.horizontalHeader() is not self.db_smart_header:
            self.db_smart_table.setHorizontalHeader(self.db_smart_header)
        self.db_smart_header.setVisible(True)
        self.db_smart_header.setFixedHeight(self.db_smart_header.TOP_HEIGHT + self.db_smart_header.BOTTOM_HEIGHT)
        self.db_smart_header.updateGeometry()
        self.db_smart_header.viewport().update()
        self.db_smart_table.viewport().update()

    def _live_signal_mapping_sources(self) -> dict[str, Path]:
        if not self.selected_site:
            return {}
        # Re-scan before every refresh so regenerated CSV/XLSX inputs are used
        # immediately. The source repository remains read-only.
        if self.repository_root:
            live = next((x for x in scan_repository(self.repository_root) if x.name == self.selected_site.name), None)
            if live:
                self.selected_site = live
        return dict(self.selected_site.sources) if self.selected_site else {}

    def refresh_db_smart_report(self):
        if not hasattr(self, "db_smart_table"):
            return
        sources = self._live_signal_mapping_sources()
        ioa_path = sources.get("ioa")
        adms_sld_path = sources.get("adms_sld")
        standard_path = standard_reference_path()
        required = {
            "ZENON-ADMS-IOA.csv": ioa_path,
            "ADMS-SLD.csv": adms_sld_path,
            "active IOA STANDARD.xlsx": standard_path if standard_path.exists() else None,
        }
        missing = [label for label, path in required.items() if not path]
        if not self.selected_site or not self.store or missing:
            self.db_smart_report = None
            self.db_smart_table.setRowCount(0)
            if hasattr(self, "db_smart_locator"):
                self.db_smart_locator.setRowCount(0)
            self.db_smart_stack.setCurrentWidget(self.db_smart_empty)
            self.db_smart_source_label.setText("Inputs: " + ("missing " + ", ".join(missing) if missing else "—"))
            self.db_smart_sheet_label.setText("Mode: calculated")
            self.db_smart_meta_label.setText("Rows: 0")
            self.db_smart_summary.setText("Signal Mapping Review unavailable")
            return
        try:
            report = build_signal_mapping_report(
                ioa_path, adms_sld_path, standard_path,
                ioa_overrides=self.store.source_column_overrides("ioa"),
                adms_sld_overrides=self.store.source_column_overrides("adms_sld"),
                standard_overrides=self.store.source_column_overrides("standard_reference"),
            )
        except Exception as exc:
            self.db_smart_report = None
            self.db_smart_table.setRowCount(0)
            if hasattr(self, "db_smart_locator"):
                self.db_smart_locator.setRowCount(0)
            self.db_smart_stack.setCurrentWidget(self.db_smart_empty)
            self.db_smart_source_label.setText(f"Inputs: {ioa_path.name} · {adms_sld_path.name} · {standard_reference_origin()} {standard_path.name}")
            self.db_smart_sheet_label.setText("Mode: calculated")
            self.db_smart_meta_label.setText(f"Error: {type(exc).__name__}: {exc}")
            self.db_smart_summary.setText("Signal Mapping Review unavailable")
            return
        self.db_smart_report = report
        reset_count = self._sync_signal_review_fingerprints(report)
        self._configure_db_smart_table(report)
        modified_ts = max(path.stat().st_mtime for path in report.input_paths)
        modified = datetime.fromtimestamp(modified_ts).strftime("%Y-%m-%d %H:%M:%S")
        self.db_smart_source_label.setText(
            f"Inputs: {ioa_path} · {adms_sld_path} · {standard_reference_origin()} {standard_path}"
        )
        self.db_smart_sheet_label.setText(f"Mode: calculated from site CSV + ADMS SLD + {standard_reference_origin()} STANDARD")
        reset_note = f" · Review reset {reset_count}" if reset_count else ""
        self.db_smart_meta_label.setText(f"Rows: {len(report.rows)} · Latest input: {modified}{reset_note}")
        self.db_smart_stack.setCurrentWidget(self.db_smart_table_host)
        self._render_db_smart_rows()
        self.refresh_dashboard()
        self.refresh_export_page()
        QTimer.singleShot(0, self._restore_db_smart_header)

    def _render_db_smart_rows(self):
        if not hasattr(self, "db_smart_table") or not self.db_smart_report or not self.store:
            return
        report = self.db_smart_report
        review_map = self.store.db_smart_review_map()
        term = self.db_smart_search.text().strip().casefold() if hasattr(self, "db_smart_search") else ""
        review_filter = self.db_smart_review_combo.currentText() if hasattr(self, "db_smart_review_combo") else "ALL REVIEWS"
        result_filter = self.db_smart_result_combo.currentText() if hasattr(self, "db_smart_result_combo") else "ALL RESULTS"
        shown = []
        for row in report.rows:
            review = review_map.get(row.row_key, {})
            status = clean(review.get("review_status")) or "UNREVIEWED"
            comments = clean(review.get("comments"))
            if review_filter != "ALL REVIEWS" and status != review_filter:
                continue
            analysis_result = ""
            if report.analysis_column is not None and report.analysis_column < len(row.values):
                analysis_result = clean(row.values[report.analysis_column]).upper()
            if result_filter == "MATCHED" and analysis_result != "TRUE":
                continue
            if result_filter == "MISMATCHED" and analysis_result != "FALSE":
                continue
            if result_filter == "UNCHECKED" and analysis_result in {"TRUE", "FALSE"}:
                continue
            searchable = " | ".join((status, comments, *row.values)).casefold()
            if term and term not in searchable:
                continue
            shown.append((row, status, comments))

        self.db_smart_table.setRowCount(len(shown))
        if hasattr(self, "db_smart_locator"):
            self.db_smart_locator.setRowCount(len(shown))
        self.db_smart_row_keys = []
        source_analysis_true = 0
        source_analysis_false = 0
        for visual_row, (row, status, comments) in enumerate(shown):
            self.db_smart_row_keys.append(row.row_key)
            values = [status, comments, *row.values]
            row_fill = QColor("#FFFFFF")
            if status == "REVIEWED": row_fill = QColor("#EAF7F0")
            elif status == "NEEDS ACTION": row_fill = QColor("#FFF0E0")

            if hasattr(self, "db_smart_locator"):
                row_type = clean(row.values[1]) if len(row.values) > 1 else ""
                locator_values = [clean(row.rmu), row_type, status]
                for locator_col, locator_value in enumerate(locator_values):
                    locator_item = QTableWidgetItem(locator_value)
                    locator_tip = f"RMU {clean(row.rmu)} · {row_type or '—'} · {status}"
                    if locator_col == 2:
                        locator_tip += " · Double-click Review to change the human review state"
                    locator_item.setToolTip(locator_tip)
                    locator_item.setBackground(row_fill if locator_col == 2 else QColor("#FFFFFF"))
                    if locator_col in {0, 2}:
                        font = locator_item.font(); font.setBold(True); locator_item.setFont(font)
                    if locator_col == 2:
                        locator_item.setTextAlignment(Qt.AlignCenter)
                    self.db_smart_locator.setItem(visual_row, locator_col, locator_item)

            for col, value in enumerate(values):
                item = QTableWidgetItem(clean(value))
                item.setBackground(row_fill)
                item.setToolTip(clean(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, row.row_key)
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setForeground(QColor(COLORS["success"] if status == "REVIEWED" else COLORS["warning"] if status == "NEEDS ACTION" else COLORS["muted"]))
                if col == 1 and comments:
                    font = item.font(); font.setBold(True); item.setFont(font)
                source_col = col - 2
                if source_col == report.analysis_column:
                    normalized = clean(value).upper()
                    if normalized == "TRUE":
                        item.setBackground(QColor("#DDF5E7")); source_analysis_true += 1
                    elif normalized == "FALSE":
                        item.setBackground(QColor("#F7D7D7")); source_analysis_false += 1
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setToolTip(row.analysis_detail or clean(value))
                self.db_smart_table.setItem(visual_row, col, item)

        self._apply_db_smart_visibility()
        if hasattr(self, "db_smart_locator"):
            self.db_smart_locator.verticalScrollBar().setValue(self.db_smart_table.verticalScrollBar().value())
        active_keys = {row.row_key for row in report.rows}
        total_reviews = Counter(
            (clean(review_map.get(key, {}).get("review_status")) or "UNREVIEWED")
            for key in active_keys
        )
        # Count source analysis from the whole report, not only the current filter.
        all_true = all_false = 0
        if report.analysis_column is not None:
            for row in report.rows:
                value = clean(row.values[report.analysis_column]).upper()
                all_true += value == "TRUE"
                all_false += value == "FALSE"
        checked = all_true + all_false
        unchecked = max(0, len(report.rows) - checked)
        self.db_smart_summary.setText(
            f"Total {len(report.rows)} · Shown {len(shown)} · Checked {checked} · Matched {all_true} · "
            f"Mismatched {all_false} · Unchecked {unchecked} · Reviewed {total_reviews['REVIEWED']} · "
            f"Needs Action {total_reviews['NEEDS ACTION']}"
        )

    def _selected_db_smart_row_keys(self) -> list[str]:
        if not hasattr(self, "db_smart_table"):
            return []
        rows = sorted({index.row() for index in self.db_smart_table.selectedIndexes()})
        if not rows and self.db_smart_table.currentRow() >= 0:
            rows = [self.db_smart_table.currentRow()]
        keys = []
        for row in rows:
            if 0 <= row < len(getattr(self, "db_smart_row_keys", [])):
                key = self.db_smart_row_keys[row]
                if key and key not in keys:
                    keys.append(key)
        return keys

    def set_db_smart_review_status(self):
        if not self.store or not self.db_smart_report:
            return
        row_keys = self._selected_db_smart_row_keys()
        if not row_keys:
            QMessageBox.information(self, "Signal Mapping Review", "Select one or more signal rows first.")
            return
        review_map = self.store.db_smart_review_map()
        statuses = ["UNREVIEWED", "REVIEWED", "NEEDS ACTION"]
        display_options = ["Unreviewed", "Reviewed", "Needs Action"]
        current = clean(review_map.get(row_keys[0], {}).get("review_status")).upper() or "UNREVIEWED"
        index = statuses.index(current) if len(row_keys) == 1 and current in statuses else 0
        selected_label, ok = QInputDialog.getItem(
            self, "Set Signal Review",
            ("Selected signal" if len(row_keys) == 1 else f"{len(row_keys)} selected signals") +
            "\nReviewed = verified/accepted · Needs Action = mapping correction required",
            display_options, index, False,
        )
        if not ok:
            return
        value = statuses[display_options.index(selected_label)]
        rows_by_key = {row.row_key: row for row in self.db_smart_report.rows}
        site_name = self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name
        for row_key in row_keys:
            row = rows_by_key.get(row_key)
            if not row:
                continue
            self.store.update_db_smart_review(
                row_key=row_key, rmu=row.rmu, field="review_status", value=value,
                modified_by=self.user_name, source_hash=self.db_smart_report.source_hash,
                row_hash=signal_review_row_hash(row, self.db_smart_report.analysis_column), site_name=site_name, reason="Signal Mapping Review status changed",
            )
        self._render_db_smart_rows()
        self.refresh_dashboard()
        self.refresh_export_page()
        self.statusBar().showMessage(f"Review status updated for {len(row_keys)} signal row(s): {value}", 5000)

    def edit_db_smart_cell(self, row_index: int, column_index: int):
        if not self.db_smart_report or not self.store or row_index >= len(getattr(self, "db_smart_row_keys", [])):
            return
        if column_index not in {0, 1}:
            QMessageBox.information(self, "Read-only source", "Signal Mapping source columns are read-only. Review Status and Comments are stored separately in project.db.")
            return
        row_key = self.db_smart_row_keys[row_index]
        row = next((item for item in self.db_smart_report.rows if item.row_key == row_key), None)
        if not row:
            return
        review = self.store.db_smart_review_map().get(row_key, {})
        if column_index == 0:
            old = clean(review.get("review_status")).upper() or "UNREVIEWED"
            statuses = ["UNREVIEWED", "REVIEWED", "NEEDS ACTION"]
            display_options = ["Unreviewed", "Reviewed", "Needs Action"]
            selected_label, ok = QInputDialog.getItem(
                self, "Set Signal Review", f"RMU {row.rmu or '—'} review status",
                display_options, statuses.index(old) if old in statuses else 0, False
            )
            if not ok:
                return
            value = statuses[display_options.index(selected_label)]
            field = "review_status"
            reason = "Signal Mapping review status changed"
        else:
            old = clean(review.get("comments"))
            value, ok = QInputDialog.getMultiLineText(self, "Signal Mapping Comments", f"RMU {row.rmu or '—'} review comments", old)
            if not ok:
                return
            field = "comments"
            reason = "Signal Mapping review comments updated"
        self.store.update_db_smart_review(
            row_key=row_key, rmu=row.rmu, field=field, value=value, modified_by=self.user_name,
            source_hash=self.db_smart_report.source_hash, row_hash=signal_review_row_hash(row, self.db_smart_report.analysis_column),
            site_name=self.selected_site.name if self.selected_site else "", reason=reason,
        )
        self._render_db_smart_rows()
        self.refresh_changes()
        self.refresh_dashboard()
        self.refresh_export_page()

    def open_db_smart_source(self):
        if not self.db_smart_report:
            QMessageBox.information(self, "Signal Mapping Review", "No Signal Mapping source is loaded.")
            return
        self._open_path(self.db_smart_report.source_path)

    # ------------------------- manual changes -------------------------
    def _build_changes_page(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader("Change Audit", "Read-only trace of migration-review corrections, structured RMU Resolutions, display-name changes and Signal Mapping comments saved for project handover and traceability."))
        info = QFrame()
        info.setObjectName("SoftCard")
        ibox = QVBoxLayout(info)
        ibox.setContentsMargins(16, 12, 16, 12)
        ititle = QLabel("What is the Audit Log?")
        ititle.setObjectName("SectionTitle")
        idesc = QLabel("Whenever a reviewer changes an RMU Data Review value, selects a structured RMU Resolution, or reviews a Signal Mapping row, the application stores the record, field, original value, new value, reason, Windows user and timestamp. This page is intentionally read-only and is used for traceability, review handover and version auditing.")
        idesc.setWordWrap(True)
        idesc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        idesc.setObjectName("Muted")
        ibox.addWidget(ititle)
        ibox.addWidget(idesc)
        layout.addWidget(info)

        self.changes_table = QTableWidget(0, 8)
        headers = ["ID", "RMU / Record", "Field", "Original Value", "New Value", "Reason", "Modified By", "Modified At"]
        self.changes_table.setHorizontalHeaderLabels(headers)
        _configure_table_base(self.changes_table)
        _set_fixed_column(self.changes_table, 0, 64)
        _set_interactive_column(self.changes_table, 1, 170)
        _set_interactive_column(self.changes_table, 2, 155)
        _set_interactive_column(self.changes_table, 3, 220)
        _set_interactive_column(self.changes_table, 4, 220)
        _set_stretch_column(self.changes_table, 5)
        _set_fixed_column(self.changes_table, 6, 130)
        _set_fixed_column(self.changes_table, 7, 180)

        self.changes_stack = QStackedWidget()
        self.changes_stack.addWidget(self.changes_table)
        self.changes_empty = EmptyState(
            "No audit records yet",
            "Changes made in RMU Data Review or Signal Mapping Review will appear here automatically with original value, new value, reviewer and timestamp.",
        )
        self.changes_stack.addWidget(self.changes_empty)
        layout.addWidget(self.changes_stack, 1)
        return page

    # ------------------------- versions -------------------------
    def _build_versions_page(self):
        page, layout = self._page_container()
        row = QHBoxLayout()
        row.addWidget(PageHeader("Review Versions", "Create named Saudi ADMS migration-review snapshots before handover, rework or another migration cycle."), 1)
        row.addStretch()
        save = QPushButton("Save Version")
        save.setObjectName("Primary")
        save.clicked.connect(self.save_version)
        row.addWidget(save, alignment=Qt.AlignBottom)
        layout.addLayout(row)
        self.versions_table = QTableWidget(0, 5)
        self.versions_table.setHorizontalHeaderLabels(["ID", "Version", "Description", "Created By", "Created At"])
        _configure_table_base(self.versions_table)
        _set_fixed_column(self.versions_table, 0, 70)
        _set_fixed_column(self.versions_table, 1, 145)
        _set_stretch_column(self.versions_table, 2)
        _set_fixed_column(self.versions_table, 3, 150)
        _set_fixed_column(self.versions_table, 4, 190)

        self.versions_stack = QStackedWidget()
        self.versions_stack.addWidget(self.versions_table)
        self.versions_empty = EmptyState(
            "No saved versions yet",
            "Save a named version before handover or another migration cycle. Version snapshots preserve RMU Data Review state, structured Resolutions and Signal Mapping review metadata.",
        )
        self.versions_stack.addWidget(self.versions_empty)
        layout.addWidget(self.versions_stack, 1)
        return page

    # ------------------------- export -------------------------
    def _build_export_page(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader("Migration Report Export", "Generate the formal auditable Excel migration-review workbook for the selected Saudi ADMS site."))
        card = QFrame()
        card.setObjectName("Card")
        box = QVBoxLayout(card)
        box.setContentsMargins(24, 22, 24, 22)
        title = QLabel("Unified site review workbook")
        title.setObjectName("SectionTitle")
        box.addWidget(title)
        desc = QLabel("The export contains exactly five sheets. RMU Data Review and Signal Mapping Review are generated from the App review models; STANDARD is copied from the currently active application reference; Import Sources and Change Audit Log provide traceability.")
        desc.setWordWrap(True)
        desc.setObjectName("Muted")
        box.addWidget(desc)
        box.addSpacing(14)
        self.export_project_label = QLabel("Saudi ADMS Site: —")
        self.export_readiness_label = QLabel("Delivery status: —")
        self.export_readiness_label.setObjectName("Muted")
        self.export_readiness_label.setWordWrap(True)
        self.export_path_label = QLabel("Report folder: —")
        self.export_path_label.setWordWrap(True)
        self.export_path_label.setObjectName("Muted")
        box.addWidget(self.export_project_label)
        box.addWidget(self.export_readiness_label)
        box.addWidget(self.export_path_label)
        box.addSpacing(18)
        buttons = QHBoxLayout()
        export_btn = QPushButton("Export Migration Report")
        export_btn.setObjectName("Primary")
        export_btn.clicked.connect(self.export_excel)
        folder_btn = QPushButton("Open Site Workspace")
        folder_btn.clicked.connect(self.open_folder)
        buttons.addWidget(export_btn)
        buttons.addWidget(folder_btn)
        buttons.addStretch()
        box.addLayout(buttons)
        layout.addWidget(card)
        layout.addStretch()
        return page

    # ------------------------- settings -------------------------
    def _build_settings_page(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader("Settings", "NARI Saudi ADMS Migration Report application identity, workspace policy, STANDARD management and deployment settings."))
        card = QFrame()
        card.setObjectName("Card")
        form = QFormLayout(card)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(14)
        app_label = QLabel(f"{APP_NAME} v{APP_VERSION}")
        ws_label = QLabel(str(workspace_root()))
        ws_label.setWordWrap(True)
        user_label = QLabel(self.user_name)
        self.settings_repo_label = QLabel(str(self.repository_root) if self.repository_root else "Not configured")
        self.settings_repo_label.setWordWrap(True)
        repo_widget = QWidget()
        repo_line = QHBoxLayout(repo_widget); repo_line.setContentsMargins(0, 0, 0, 0)
        repo_line.addWidget(self.settings_repo_label, 1)
        repo_btn = QPushButton("Change..."); repo_btn.clicked.connect(self.choose_repository_root); repo_line.addWidget(repo_btn)
        policy = QLabel("This NARI Saudi ADMS migration workspace treats each site folder as the project data identity. Normal validation/import operations read and snapshot source files without modifying them; the explicit Regenerate ZENON SLD action safely replaces only the derived ZENON-SLD.csv after a successful XML parse. project.db, source snapshots and formal migration reports remain in the private App Workspace. Every validation run re-scans live files and zenOn XML is filtered by the selected site's feeder token.")
        policy.setWordWrap(True)
        form.addRow("Application", app_label)
        form.addRow("Current user", user_label)
        form.addRow("Site Repository", repo_widget)
        form.addRow("App Workspace", ws_label)
        form.addRow("Data policy", policy)
        layout.addWidget(card)

        standard_card = QFrame()
        standard_card.setObjectName("Card")
        standard_box = QVBoxLayout(standard_card)
        standard_box.setContentsMargins(24, 22, 24, 22)
        standard_title = QLabel("Signal Mapping STANDARD reference")
        standard_title.setObjectName("SectionTitle")
        standard_box.addWidget(standard_title)
        standard_desc = QLabel(
            "Signal Mapping Review and formal Excel export use one application-wide STANDARD table. "
            "A validated user upload overrides the bundled default for every site; Site Repository files are never modified."
        )
        standard_desc.setObjectName("Muted")
        standard_desc.setWordWrap(True)
        standard_box.addWidget(standard_desc)
        self.settings_standard_label = QLabel("STANDARD: —")
        self.settings_standard_label.setWordWrap(True)
        self.settings_standard_label.setObjectName("Muted")
        standard_box.addWidget(self.settings_standard_label)
        standard_buttons = QHBoxLayout()
        upload_btn = QPushButton("Upload / Replace STANDARD...")
        upload_btn.setObjectName("Primary")
        upload_btn.clicked.connect(self.update_standard_reference)
        restore_btn = QPushButton("Restore Built-in")
        restore_btn.clicked.connect(self.restore_standard_reference)
        open_standard_btn = QPushButton("Open Current")
        open_standard_btn.clicked.connect(self.open_standard_reference)
        standard_buttons.addWidget(upload_btn)
        standard_buttons.addWidget(restore_btn)
        standard_buttons.addWidget(open_standard_btn)
        standard_buttons.addStretch()
        standard_box.addLayout(standard_buttons)
        layout.addWidget(standard_card)
        self._refresh_standard_reference_ui()
        layout.addStretch()
        return page

    def _refresh_standard_reference_ui(self):
        if not hasattr(self, "settings_standard_label"):
            return
        try:
            info = current_standard_reference_info()
            self.settings_standard_label.setText(
                f"Active: {info.origin} · {info.path}\n"
                f"Rows: {info.row_count} · Updated: {info.updated_at} · SHA256: {info.sha256[:16]}…"
            )
        except Exception as exc:
            self.settings_standard_label.setText(f"STANDARD unavailable: {type(exc).__name__}: {exc}")

    def update_standard_reference(self):
        initial = str(Path.home())
        current = standard_reference_path()
        if current.exists():
            initial = str(current.parent)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select IOA STANDARD workbook", initial, "Excel Workbook (*.xlsx)"
        )
        if not path:
            return
        try:
            previous = current_standard_reference_info()
            info = install_standard_reference(Path(path), self.user_name)
        except Exception as exc:
            QMessageBox.critical(
                self, "STANDARD Validation Failed",
                "The selected workbook was not installed.\n\n" + f"{type(exc).__name__}: {exc}",
            )
            return
        if self.store:
            try:
                now = datetime.now().isoformat(timespec="seconds")
                self.store.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    ("STANDARD", "standard_reference", f"{previous.origin}: {previous.path}", f"{info.origin}: {info.path}",
                     f"Application STANDARD updated from {Path(path).name}", self.user_name, now),
                )
                self.store.db.commit()
            except Exception:
                pass
        self._refresh_standard_reference_ui()
        self.refresh_db_smart_report()
        QMessageBox.information(
            self, "STANDARD Updated",
            f"The new STANDARD table is active for all sites.\n\nRows: {info.row_count}\nPath: {info.path}",
        )

    def restore_standard_reference(self):
        if standard_reference_origin() != "User Override":
            QMessageBox.information(self, "STANDARD Reference", "The bundled STANDARD table is already active.")
            return
        answer = QMessageBox.question(
            self, "Restore Built-in STANDARD",
            "Remove the user STANDARD override and return to the bundled reference table?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            previous = current_standard_reference_info()
            info = restore_bundled_standard_reference()
        except Exception as exc:
            QMessageBox.critical(self, "STANDARD Reference", f"{type(exc).__name__}: {exc}")
            return
        if self.store:
            try:
                now = datetime.now().isoformat(timespec="seconds")
                self.store.db.execute(
                    "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                    ("STANDARD", "standard_reference", f"{previous.origin}: {previous.path}", f"{info.origin}: {info.path}",
                     "Application STANDARD restored to bundled reference", self.user_name, now),
                )
                self.store.db.commit()
            except Exception:
                pass
        self._refresh_standard_reference_ui()
        self.refresh_db_smart_report()
        self.statusBar().showMessage(f"Built-in STANDARD restored: {info.path}", 5000)

    def open_standard_reference(self):
        path = standard_reference_path()
        if not path.exists():
            QMessageBox.information(self, "STANDARD Reference", f"File not found: {path}")
            return
        self._open_path(path)

    # ------------------------- spreadsheet selection -------------------------
    def _register_spreadsheet_table(self, table: SpreadsheetTableWidget) -> None:
        """Register a review grid for Excel-like selection behavior."""
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        if table not in self._spreadsheet_tables:
            self._spreadsheet_tables.append(table)

    @staticmethod
    def _widget_is_inside(widget, ancestor: QWidget) -> bool:
        if widget is ancestor:
            return True
        return isinstance(widget, QWidget) and ancestor.isAncestorOf(widget)

    def _clear_spreadsheet_selections(self, except_table: SpreadsheetTableWidget | None = None) -> None:
        for table in getattr(self, "_spreadsheet_tables", []):
            if table is except_table:
                continue
            if table.selectionModel() is not None and (table.selectionModel().hasSelection() or table.currentIndex().isValid()):
                table.clear_spreadsheet_selection()

    def eventFilter(self, obj, event):
        """Clear grid selection whenever the user clicks outside that grid.

        This intentionally works at QApplication level because clicking a plain
        page background does not always move keyboard focus away from a
        QTableWidget on Windows, so focusOutEvent alone is not reliable.
        """
        if event.type() == QEvent.Type.MouseButtonPress:
            clicked_table = None
            if isinstance(obj, QWidget):
                for table in getattr(self, "_spreadsheet_tables", []):
                    if self._widget_is_inside(obj, table):
                        clicked_table = table
                        break
            self._clear_spreadsheet_selections(except_table=clicked_table)
        return super().eventFilter(obj, event)

    # ------------------------- navigation -------------------------
    def set_page(self, index: int):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        if index == 1 and hasattr(self, "site_list"):
            self.refresh_site_repository()
        elif index == 3 and hasattr(self, "db_smart_table"):
            self.refresh_db_smart_report()
            # QStackedWidget geometry settles after the page becomes current;
            # repaint the persistent grouped header on the next event-loop turn.
            QTimer.singleShot(0, self._restore_db_smart_header)

    def _wire_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.run_comparison)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_excel)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.set_page(2), self.search_edit.setFocus()))

    # ------------------------- site repository actions -------------------------
    def choose_repository_root(self):
        initial = str(self.repository_root) if self.repository_root else str(Path.home())
        path = QFileDialog.getExistingDirectory(self, "Select Workspace", initial)
        if not path:
            return
        self.repository_root = Path(path).resolve()
        save_repository_root(self.repository_root)
        if hasattr(self, "settings_repo_label"):
            self.settings_repo_label.setText(str(self.repository_root))
        self.selected_site = None
        self.refresh_site_repository()
        self.statusBar().showMessage(f"Site Repository: {self.repository_root}", 5000)

    def open_repository_root(self):
        if not self.repository_root or not self.repository_root.exists():
            QMessageBox.information(self, "Site Repository", "Choose a valid Workspace first.")
            return
        self._open_path(self.repository_root)

    def refresh_site_repository(self):
        if not hasattr(self, "site_list"):
            return
        selected_name = self.selected_site.name if self.selected_site else None
        if not selected_name and self.store:
            selected_name = self.store.config.get("repository_site")
        if not selected_name:
            selected_name = load_last_site() or None
        self.repository_sites = scan_repository(self.repository_root) if self.repository_root else []
        if hasattr(self, "repository_root_edit"):
            self.repository_root_edit.setText(str(self.repository_root) if self.repository_root else "")
        ready = sum(1 for site in self.repository_sites if site.ready)
        if hasattr(self, "repository_summary"):
            self.repository_summary.setText(f"{len(self.repository_sites)} sites · {ready} ready")
        if hasattr(self, "repository_last_scan"):
            self.repository_last_scan.setText("Last scan: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._render_site_list(selected_name)

    def _render_site_list(self, preferred_name: str | None = None):
        if not hasattr(self, "site_list"):
            return
        # When invoked by the search box, keep the current selection when possible.
        if preferred_name is None and self.selected_site:
            preferred_name = self.selected_site.name
        term = self.site_search_edit.text().strip().casefold() if hasattr(self, "site_search_edit") else ""
        self.site_list.blockSignals(True)
        self.site_list.clear()
        selected_row = -1
        visible_sites = []
        for site in self.repository_sites:
            if term and term not in site.name.casefold():
                continue
            visible_sites.append(site)
            present = len(site.sources)
            status = "READY" if site.ready else "WARNING"
            missing = "" if site.ready else " · missing " + ", ".join(site.missing_required)
            item = QListWidgetItem(f"{site.name}\n{status} · {present}/{len(SOURCE_DEFINITIONS)} sources{missing}")
            item.setData(Qt.ItemDataRole.UserRole, site.name)
            item.setForeground(QColor(COLORS["success"] if site.ready else COLORS["warning"]))
            self.site_list.addItem(item)
            if preferred_name and site.name.casefold() == str(preferred_name).casefold():
                selected_row = self.site_list.count() - 1
        if selected_row < 0 and self.site_list.count():
            selected_row = 0
        if selected_row >= 0:
            self.site_list.setCurrentRow(selected_row)
        self.site_list.blockSignals(False)
        if selected_row >= 0:
            item = self.site_list.item(selected_row)
            self._site_item_changed(item, None)
        else:
            self.selected_site = None
            self._refresh_site_source_table()

    def _site_item_changed(self, current, previous):
        if not current:
            self.selected_site = None
            self._refresh_site_source_table()
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        site = next((x for x in self.repository_sites if x.name == name), None)
        if not site:
            return
        self.selected_site = site
        # Site folder name is the identity. Private app workspace data remains separate
        # from the repository root; no manual project creation is exposed. The
        # explicit Regenerate ZENON SLD action is the only derived-file write.
        save_last_site(site.name)
        self._activate_site_workspace(site)
        if hasattr(self, "comparison_table"):
            self._configure_comparison_headers()
        self.refresh_comparison()
        self.db_smart_report = None
        if self.stack.currentIndex() == 3:
            self.refresh_db_smart_report()
        self.refresh_changes()
        self.refresh_versions()
        self.refresh_dashboard()
        self.refresh_export_page()
        self._refresh_site_source_table()

    def _refresh_site_source_table(self):
        if not hasattr(self, "module_source_tables"):
            return
        for table in self.module_source_tables.values():
            table.setRowCount(0)

        site = self.selected_site
        if not site:
            self.site_detail_title.setText("Select a site")
            self.site_detail_path.setText("Choose a repository root, then select a detected site.")
            self.site_status_label.setText("—")
            if hasattr(self, "regenerate_zenon_sld_btn"):
                self.regenerate_zenon_sld_btn.setEnabled(False)
            return

        self.site_detail_title.setText(site.name)
        self.site_detail_path.setText(f"{site.path}\nXML scope: exact feeder token {site.name}")
        self.site_status_label.setText("READY" if site.ready else "WARNING")
        self.site_status_label.setStyleSheet(
            f"font-weight:700;color:{COLORS['success'] if site.ready else COLORS['warning']};"
        )
        if hasattr(self, "regenerate_zenon_sld_btn"):
            has_xml = bool(site.sources.get("zenon_xml") and Path(site.sources["zenon_xml"]).exists())
            self.regenerate_zenon_sld_btn.setEnabled(has_xml)
            self.regenerate_zenon_sld_btn.setToolTip(
                "Parse the selected site's ZENON XML and safely replace <site>/ZENON-SLD.csv. "
                "The existing CSV is kept if parsing or writing fails." if has_xml
                else "ZENON XML is required to regenerate ZENON-SLD.csv."
            )

        active_store = self.store if self.store and self.store.config.get("repository_site", "").casefold() == site.name.casefold() else None
        statuses = source_status(site, active_store)
        status_color = {
            "CURRENT": COLORS["success"],
            "NEW": COLORS["info"],
            "UPDATED": COLORS["warning"],
            "MISSING": COLORS["danger"],
            "OPTIONAL": COLORS["muted"],
            "BUILT-IN": COLORS["info"],
            "USER OVERRIDE": COLORS["warning"],
        }

        for module in MODULE_SOURCE_GROUPS:
            table = self.module_source_tables[module.key]
            table.setRowCount(len(module.tables))
            for row, ref in enumerate(module.tables):
                source_type = ref.source_type
                if source_type == "standard_reference":
                    path = standard_reference_path()
                    path = path if path.exists() else None
                    file_status = standard_reference_origin().upper() if path else "MISSING"
                else:
                    info = statuses.get(source_type, {})
                    path = info.get("path")
                    file_status = info.get("status", "MISSING")

                if path:
                    path = Path(path)
                    stat = path.stat()
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    size = self._format_size(stat.st_size)
                    detected = path.name
                else:
                    modified, size, detected = "—", "—", "Not found"

                schema_text = "N/A"
                schema_tip = "This source is non-tabular and has no CSV/XLSX column mapping."
                schema = schema_for(source_type)
                if path and schema is not None:
                    try:
                        validation = validate_source_file(
                            source_type, path, get_source_overrides(active_store, source_type)
                        )
                        if validation is not None:
                            schema_text = validation_summary(validation)
                            schema_tip = validation.error_message(path.name) if validation.errors else (
                                "Mapped columns:\n" + "\n".join(
                                    f"{m.canonical_label} -> {m.actual_column or '<missing>'} [{m.kind.value}]"
                                    for m in validation.mappings
                                )
                            )
                    except Exception as exc:
                        schema_text = "ERROR"
                        schema_tip = f"{type(exc).__name__}: {exc}"

                values = [
                    ref.label, ref.role, ref.expected_name, detected,
                    file_status, schema_text, modified, size,
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, source_type)
                        font = item.font(); font.setBold(True); item.setFont(font)
                    if col == 5:
                        item.setToolTip(schema_tip)
                    elif path:
                        item.setToolTip(str(path))
                    else:
                        item.setToolTip(ref.expected_name)
                    if col == 4:
                        item.setForeground(QColor(status_color.get(file_status, COLORS["text"])))
                        font = item.font(); font.setBold(True); item.setFont(font)
                    if col == 5:
                        color = (
                            COLORS["danger"] if schema_text.startswith("ERROR") else
                            COLORS["warning"] if schema_text.startswith("WARNING") else
                            COLORS["success"] if schema_text == "READY" else COLORS["muted"]
                        )
                        item.setForeground(QColor(color))
                        font = item.font(); font.setBold(True); item.setFont(font)
                    table.setItem(row, col, item)
            if table.rowCount() and table.currentRow() < 0:
                table.setCurrentCell(0, 0)

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"

    def open_selected_site_folder(self):
        if not self.selected_site:
            QMessageBox.information(self, "Site Repository", "Select a site first.")
            return
        self._open_path(self.selected_site.path)

    def regenerate_zenon_sld(self):
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Regenerate ZENON SLD", "Select a site first.")
            return
        if not self.selected_site.sources.get("zenon_xml"):
            QMessageBox.information(self, "Regenerate ZENON SLD", "ZENON XML was not found for this site.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = regenerate_site_zenon_sld(self.selected_site, self.store)
            # Re-scan immediately so the newly replaced derived CSV is visible
            # in the repository table and marked NEW/UPDATED against the last run.
            self.refresh_site_repository()
            self.statusBar().showMessage(
                f"ZENON-SLD.csv regenerated successfully · {result.row_count} RMUs · {result.target_path}", 8000
            )
            QMessageBox.information(
                self, "ZENON SLD Regenerated",
                f"ZENON-SLD.csv was regenerated successfully.\n\nRMUs: {result.row_count}\nXML: {result.xml_path.name}\nOutput: {result.target_path}"
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Regenerate ZENON SLD",
                f"{type(exc).__name__}: {exc}\n\nThe existing ZENON-SLD.csv was not changed unless the replacement completed successfully."
            )
        finally:
            QApplication.restoreOverrideCursor()

    def _current_module_source_selection(self):
        if not hasattr(self, "module_source_tabs") or not hasattr(self, "module_source_tables"):
            return None, None, None
        sender = self.sender()
        table = sender if isinstance(sender, QTableWidget) else None
        module = None
        if table is not None:
            module = next((m for m in MODULE_SOURCE_GROUPS if self.module_source_tables.get(m.key) is table), None)
        if table is None:
            index = self.module_source_tabs.currentIndex()
            if index < 0 or index >= len(MODULE_SOURCE_GROUPS):
                return None, None, None
            module = MODULE_SOURCE_GROUPS[index]
            table = self.module_source_tables.get(module.key)
        if table is None or module is None:
            return None, None, None
        row = table.currentRow()
        if row < 0 and table.rowCount():
            row = 0
        if row < 0:
            return module, None, None
        item = table.item(row, 0)
        source_type = item.data(Qt.ItemDataRole.UserRole) if item else None
        ref = next((x for x in module.tables if x.source_type == source_type), None)
        return module, ref, table

    def open_source_mapping(self, *_args):
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Source Mapping", "Select a site first.")
            return
        module, ref, _table = self._current_module_source_selection()
        if ref is None:
            QMessageBox.information(self, "Source Mapping", "Select a table in the current module first.")
            return
        source_type = ref.source_type
        if source_type == "standard_reference":
            path = standard_reference_path()
        else:
            path = self.selected_site.sources.get(source_type)
        if not path or not Path(path).exists():
            QMessageBox.information(
                self, "Source Mapping",
                f"{ref.label} was not found. Expected: {ref.expected_name}"
            )
            return
        if schema_for(source_type) is None:
            if source_type == "zenon_xml":
                QMessageBox.information(
                    self, "ZENON XML",
                    "ZENON XML is a non-tabular graphical source. It has no column mapping. "
                    "Use Regenerate ZENON SLD to parse it into ZENON-SLD.csv, then edit the ZENON SLD table mapping."
                )
            else:
                QMessageBox.information(self, "Source Mapping", f"{ref.label} does not use a CSV/XLSX column schema.")
            return
        try:
            dialog = SourceMappingDialog(source_type, Path(path), self.store, self.user_name, self)
        except Exception as exc:
            QMessageBox.critical(self, "Source Mapping", f"{type(exc).__name__}: {exc}")
            return
        if dialog.exec() == QDialog.Accepted:
            self._refresh_site_source_table()
            if hasattr(self, "comparison_table"):
                self._configure_comparison_headers()
            # Rebuild Signal Mapping when any of its input mappings or Display
            # Names change, including the application STANDARD reference.
            signal_sources = {"ioa", "adms_sld", "standard_reference"}
            if source_type in signal_sources and hasattr(self, "db_smart_table"):
                self.refresh_db_smart_report()
            self.statusBar().showMessage(
                f"{module.label} · {ref.label}: current-site column mapping and global Display Names saved", 5000
            )

    def advanced_manual_import(self):
        """Compatibility escape hatch for non-standard site deliveries."""
        if not self.require_site():
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Manual Import")
        dialog.resize(900, 560)
        layout = QVBoxLayout(dialog)
        title = QLabel("Manual source override")
        title.setObjectName("SectionTitle")
        desc = QLabel("Use this only when a site does not follow the repository naming convention. Selected files are copied into the selected site workspace and become auditable inputs.")
        desc.setObjectName("Muted"); desc.setWordWrap(True)
        layout.addWidget(title); layout.addWidget(desc)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        holder = QWidget(); rows = QVBoxLayout(holder); edits = {}
        for key, (label, filetypes) in SOURCE_TYPES.items():
            line = QHBoxLayout()
            lab = QLabel(label); lab.setMinimumWidth(180)
            edit = QLineEdit(); current = self.store.source_path(key); edit.setText(str(current) if current else "")
            btn = QPushButton("Browse")
            def browse(checked=False, k=key, e=edit, l=label, fts=filetypes):
                filters = [f"{friendly} ({pattern})" for friendly, pattern in fts] + ["All files (*.*)"]
                path, _ = QFileDialog.getOpenFileName(dialog, f"Select {l}", "", ";;".join(filters))
                if path: e.setText(path)
            btn.clicked.connect(browse)
            line.addWidget(lab); line.addWidget(edit, 1); line.addWidget(btn)
            rows.addLayout(line); edits[key] = edit
        rows.addStretch(); scroll.setWidget(holder); layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Import")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.rejected.connect(dialog.reject)
        def do_import():
            try:
                imported = []
                for key, edit in edits.items():
                    value = edit.text().strip()
                    if not value: continue
                    selected = Path(value)
                    current = self.store.source_path(key)
                    if current:
                        try:
                            if selected.resolve() == current.resolve(): continue
                        except OSError:
                            pass
                    imported.append(import_source(self.store, key, selected))
                dialog.accept()
                self.refresh_all()
                QMessageBox.information(self, "Manual Import", f"Imported {len(imported)} source file(s).")
            except Exception as exc:
                QMessageBox.critical(dialog, "Import failed", f"{type(exc).__name__}: {exc}")
        buttons.accepted.connect(do_import)
        layout.addWidget(buttons)
        dialog.exec()

    # ------------------------- site workspace actions -------------------------
    def require_site(self) -> bool:
        if self.selected_site and self.store:
            return True
        QMessageBox.warning(
            self,
            "Site required",
            "Select a site from Site Repository first. No separate Project needs to be created.",
        )
        return False

    def _activate_site_workspace(self, site: SiteInfo) -> None:
        """Bind one repository site to its private application workspace."""
        folder = workspace_root() / re.sub(r"[^A-Za-z0-9._-]+", "_", site.name)
        if not is_inside_workspace(folder):
            QMessageBox.critical(self, "Workspace restriction", f"Site workspaces must stay inside:\n{workspace_root()}")
            return
        if self.store and self.store.folder.resolve() == folder.resolve():
            self.store.config["project_name"] = site.name  # backward compatibility
            self.store.config["site_name"] = site.name
            self.store.config["repository_site"] = site.name
            self.store.config["repository_path"] = str(site.path.resolve())
            self.store.save_config()
        else:
            if self.store:
                try:
                    self.store.db.close()
                except Exception:
                    pass
            self.store = ProjectStore(folder)
            self.store.config["project_name"] = site.name  # backward compatibility
            self.store.config["site_name"] = site.name
            self.store.config["repository_site"] = site.name
            self.store.config["repository_path"] = str(site.path.resolve())
            self.store.save_config()
        self.project_title.setText(site.name)
        self.project_subtitle.setText(f"Migration Report · User: {self.user_name} · Site DB: project.db")
        self.statusBar().showMessage(f"Site selected: {site.name}", 5000)

    # ------------------------- comparison actions -------------------------
    def run_comparison(self):
        # Site Repository is the only primary workflow. Selecting a site binds its
        # private workspace automatically; every run re-scans live files first.
        if not self.selected_site:
            QMessageBox.warning(self, "Site required", "Select a site from Site Data Sources before running validation.")
            self.set_page(1)
            return
        if not self.selected_site.ready:
            QMessageBox.warning(
                self,
                "Source validation failed",
                "Cannot run validation for " + self.selected_site.name +
                ".\n\nMissing required source(s):\n" + "\n".join(self.selected_site.missing_required),
            )
            return
        self._activate_site_workspace(self.selected_site)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            imported_count = 0
            changed_keys = []
            snapshot_text = ""
            # Re-scan the selected folder at the moment Run is pressed so a
            # file replaced after the last UI refresh is always picked up.
            live = next((x for x in scan_repository(self.repository_root) if x.name == self.selected_site.name), None) if self.repository_root else None
            if live:
                self.selected_site = live
            if not self.selected_site.ready:
                raise ValueError("Missing required site source(s): " + ", ".join(self.selected_site.missing_required))
            sync = sync_site_to_project(self.store, self.selected_site)
            imported_count = len(sync.imported)
            changed_keys = list(sync.changed_keys)
            snapshot_text = str(sync.snapshot_dir)

            rows, summary = build_comparison(self.store)
            if not rows:
                QMessageBox.warning(self, "No data", "No valid migration records were found in the current site sources.")
                return
            self.store.save_comparison(rows)

            signal_report = None
            signal_matched = signal_mismatched = signal_unchecked = 0
            try:
                ioa_path = self.store.source_path("ioa")
                adms_sld_path = self.store.source_path("adms_sld")
                standard_path = standard_reference_path()
                if ioa_path and adms_sld_path and standard_path.exists():
                    signal_report = build_signal_mapping_report(
                        ioa_path, adms_sld_path, standard_path,
                        ioa_overrides=self.store.source_column_overrides("ioa"),
                        adms_sld_overrides=self.store.source_column_overrides("adms_sld"),
                        standard_overrides=self.store.source_column_overrides("standard_reference"),
                    )
                    self._sync_signal_review_fingerprints(signal_report)
                    if signal_report.analysis_column is not None:
                        for signal_row in signal_report.rows:
                            result = clean(signal_row.values[signal_report.analysis_column]).upper()
                            signal_matched += result == "TRUE"
                            signal_mismatched += result == "FALSE"
                    signal_unchecked = max(0, len(signal_report.rows) - signal_matched - signal_mismatched)
                    self.db_smart_report = signal_report
            except Exception:
                signal_report = None

            self.refresh_all()
            self.set_page(2)
            changed = ", ".join(changed_keys) if changed_keys else "none"
            repo_note = (
                f"\nSite: {self.selected_site.name}\nXML scope: feeder token {self.selected_site.name}"
                f"\nChanged sources: {changed}\nSnapshot: {snapshot_text}"
            )
            states = [analysis_review_state(row) for row in rows]
            pass_count = sum(state.is_pass for state in states)
            issue_count = sum(state.issue_count > 0 for state in states)
            issue_fields = Counter(field for state in states for field in state.false_fields)
            breakdown = " · ".join(
                f"{name} {issue_fields[name]}" for name in ("NAME", "FEEDER", "SMART", "TYPE", "IP", "LINK") if issue_fields[name]
            ) or "No analysis mismatches"
            signal_text = (
                f"\n\nSignal Mapping\nTotal: {len(signal_report.rows)}\nMatched: {signal_matched}\n"
                f"Mismatched: {signal_mismatched}\nUnchecked: {signal_unchecked}"
                if signal_report is not None else
                "\n\nSignal Mapping\nUnavailable - check ZENON-ADMS IOA / ADMS SLD / STANDARD."
            )
            QMessageBox.information(
                self,
                "Migration Validation complete",
                f"Validated site {self.selected_site.name}.\nUpdated source files: {imported_count}{repo_note}\n\n"
                f"RMU Data Review\nTotal: {len(rows)}\nPass: {pass_count}\nWith Issues: {issue_count}\n{breakdown}"
                f"{signal_text}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Migration Validation failed", f"{type(exc).__name__}: {exc}")
        finally:
            QApplication.restoreOverrideCursor()

    def _selected_comparison_rmus(self) -> list[str]:
        """Return unique RMUs represented by the current spreadsheet selection."""
        if not hasattr(self, "comparison_table"):
            return []
        rmu_col = next((i for i, (key, _label, _width) in enumerate(COMPARISON_COLUMNS) if key == "rmu"), -1)
        if rmu_col < 0:
            return []
        rows = sorted({index.row() for index in self.comparison_table.selectedIndexes()})
        if not rows and self.comparison_table.currentRow() >= 0:
            rows = [self.comparison_table.currentRow()]
        result = []
        for row in rows:
            item = self.comparison_table.item(row, rmu_col)
            rmu = clean(item.text() if item else "")
            if rmu and rmu not in result:
                result.append(rmu)
        return result

    def _comparison_row_by_rmu(self, rmu: str) -> dict | None:
        if not self.store:
            return None
        target = clean(rmu)
        return next((row for row in self.store.rows() if clean(row.get("rmu")) == target), None)

    def open_rmu_resolution_dialog(self, rmu: str) -> None:
        if not self.store:
            return
        data = self._comparison_row_by_rmu(rmu)
        if not data:
            return
        state = analysis_review_state(data)
        if state.issue_count <= 0:
            QMessageBox.information(
                self, "RMU Resolution",
                f"RMU {rmu} has no active Analysis mismatch. No Resolution decision is required."
            )
            return
        current = self.store.rmu_resolution_map(rmu)
        dialog = RMUResolutionDialog(rmu, data, current, self)
        if dialog.exec() != QDialog.Accepted:
            return
        decisions = dialog.decisions()
        for field in state.false_fields:
            payload = decisions.get(field)
            if not payload:
                self.store.clear_rmu_resolution(
                    rmu, field, self.user_name, reason="RMU Resolution set to Unresolved"
                )
                continue
            self.store.set_rmu_resolution(
                rmu=rmu, analysis_field=field, decision_type=payload.get("decision_type", ""),
                selected_source=payload.get("selected_source", ""),
                selected_value=payload.get("selected_value", ""),
                normalized_value=payload.get("normalized_value", ""),
                analysis_fingerprint=self.store._rmu_field_fingerprint(data, field),
                modified_by=self.user_name,
                reason="Structured RMU Resolution decision",
            )
        review_status = self.store.sync_rmu_review_from_resolutions(rmu, data, self.user_name)
        summary = self.store.rmu_resolution_summary(rmu) or "Unresolved"
        self.refresh_all()
        self._select_comparison_rmu(rmu)
        self.statusBar().showMessage(
            f"RMU {rmu} Resolution saved · Review: {review_status} · {summary}", 7000
        )

    def set_comparison_review_status(self):
        if not self.store:
            return
        rmus = self._selected_comparison_rmus()
        if not rmus:
            QMessageBox.information(self, "RMU Review", "Select one or more RMU rows first.")
            return
        issue_rmus = []
        for rmu in rmus:
            data = self._comparison_row_by_rmu(rmu)
            if data and analysis_review_state(data).issue_count > 0:
                issue_rmus.append(rmu)
        if issue_rmus:
            if len(rmus) == 1:
                self.open_rmu_resolution_dialog(rmus[0])
            else:
                QMessageBox.information(
                    self, "Structured Resolution required",
                    f"{len(issue_rmus)} selected RMU(s) contain Analysis errors.\n\n"
                    "Each error requires its own Resolution decision, so issue rows cannot be bulk-marked Reviewed. "
                    "Open each issue RMU and resolve every FALSE field. Pass rows can still be reviewed in bulk."
                )
            return

        review_map = self.store.rmu_review_map()
        statuses = ["UNREVIEWED", "REVIEWED", "NEEDS ACTION"]
        display_options = ["Unreviewed", "Reviewed", "Needs Action"]
        current = clean(review_map.get(rmus[0], {}).get("review_status")).upper() or "UNREVIEWED"
        index = statuses.index(current) if len(rmus) == 1 and current in statuses else 0
        selected_label, ok = QInputDialog.getItem(
            self,
            "Set RMU Review",
            (f"RMU {rmus[0]}" if len(rmus) == 1 else f"{len(rmus)} selected pass RMUs") +
            "\nPass rows have no mismatch Resolution requirement.",
            display_options,
            index,
            False,
        )
        if not ok:
            return
        value = statuses[display_options.index(selected_label)]
        for rmu in rmus:
            self.store.update_rmu_review_status(
                rmu=rmu, review_status=value, modified_by=self.user_name,
                reason="RMU Data Review status changed for pass row",
            )
        self.refresh_all()
        if len(rmus) == 1:
            self._select_comparison_rmu(rmus[0])
        self.statusBar().showMessage(f"Review status updated for {len(rmus)} RMU(s): {value}", 5000)

    def edit_comparison_cell(self, row_index: int, column_index: int):
        if not self.store:
            return
        field, label, _ = COMPARISON_COLUMNS[column_index]
        rmu_col = next((i for i, (key, _label, _width) in enumerate(COMPARISON_COLUMNS) if key == "rmu"), -1)
        rmu_item = self.comparison_table.item(row_index, rmu_col) if rmu_col >= 0 else None
        value_item = self.comparison_table.item(row_index, column_index)
        if not rmu_item:
            return
        rmu = rmu_item.text()
        value = value_item.text() if value_item else ""
        analysis_fields = {
            "analysis_name", "analysis_feeder", "analysis_smart",
            "analysis_type", "analysis_ip", "analysis_link",
        }
        if field == "comments":
            self.open_rmu_resolution_dialog(rmu)
            return
        if field in analysis_fields:
            if clean(value).upper() == "FALSE":
                self.open_rmu_resolution_dialog(rmu)
            else:
                QMessageBox.information(
                    self, "Automatic Analysis",
                    f"{label} is calculated automatically. Resolution is required only when the Analysis result is FALSE."
                )
            return
        if field not in EDITABLE_COLUMNS:
            QMessageBox.information(self, "Read-only field", f"{label} is generated as a protected key and cannot be edited here.")
            return
        old_value = value
        dialog = EditValueDialog(rmu, label, old_value, self, multiline=field in {"remarks"})
        if dialog.exec() != QDialog.Accepted:
            return
        new_value, reason = dialog.values()
        if clean(new_value) == clean(old_value):
            return
        self.store.update_value(rmu, field, new_value, self.user_name, reason)
        self.refresh_all()
        self._select_comparison_rmu(rmu)
        self.statusBar().showMessage(f"Audit entry recorded for RMU {rmu}: {label}", 5000)

    # ------------------------- version/export -------------------------
    def save_version(self):
        if not self.require_site():
            return
        if not self.store.rows():
            QMessageBox.warning(self, "No RMU review data", "Run Validation before saving a version.")
            return
        default = f"v{len(self.store.versions()) + 1}.0"
        name, ok = QInputDialog.getText(self, "Save Version", "Version name", text=default)
        if not ok or not name.strip():
            return
        description, ok = QInputDialog.getMultiLineText(self, "Version Description", "What changed in this version?", "Manual snapshot")
        if not ok:
            return
        self.store.save_version(name.strip(), description.strip() or "Manual snapshot", self.user_name)
        self.refresh_versions()
        self.refresh_dashboard()
        QMessageBox.information(self, "Version saved", f"{name.strip()} has been saved in the site audit database.")

    def export_excel(self):
        if not self.require_site():
            return
        if not self.store.rows():
            QMessageBox.warning(self, "No RMU review data", "Run Validation before exporting.")
            return
        delivery_state = getattr(self, "project_delivery_state", "")
        if delivery_state != "READY FOR EXPORT":
            answer = QMessageBox.question(
                self, "Review not complete",
                f"Current delivery state: {delivery_state or 'Review incomplete'}\n\n"
                "The workbook can still be exported as a review draft, but it should not be used as the final handover until all Review items are complete and no Needs Action remains.\n\nExport review draft now?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            target = export_report(self.store)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", f"{type(exc).__name__}: {exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        answer = QMessageBox.question(
            self,
            "Export complete",
            f"Report saved successfully:\n\n{target}\n\nOpen the report now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        self.refresh_dashboard()
        if answer == QMessageBox.Yes:
            self._open_path(target)

    def open_folder(self):
        if not self.require_site():
            return
        self._open_path(self.store.folder)

    def _open_path(self, path: Path):
        if os.name == "nt":
            os.startfile(str(path))
        elif os.sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

    # ------------------------- refresh -------------------------
    def refresh_all(self):
        self.refresh_import_page()
        self.refresh_comparison()
        self.refresh_changes()
        self.refresh_versions()
        self.refresh_dashboard()
        self.refresh_export_page()

    def refresh_import_page(self):
        if not hasattr(self, "site_list"):
            return
        self.refresh_site_repository()
        self._refresh_site_source_table()

    @staticmethod
    def _analysis_filter_match(data: dict, selected: str) -> bool:
        if selected == "ALL ANALYSIS":
            return True
        state = analysis_review_state(data)
        false_keys = set(state.false_fields)
        if selected == "PASSED":
            return state.is_pass
        if selected == "ANY MISMATCH":
            return state.issue_count > 0
        if selected == "1 ISSUE":
            return state.issue_count == 1
        if selected == "2 ISSUES":
            return state.issue_count == 2
        if selected == "MULTIPLE ISSUES":
            return state.issue_count >= 3
        if selected == "CRITICAL":
            return state.is_critical
        if selected.endswith(" MISMATCH"):
            return selected.removesuffix(" MISMATCH") in false_keys
        return True

    @staticmethod
    def _analysis_row_fill(data: dict) -> QColor:
        """Row color communicates severity only, never a field combination."""
        return QColor("#" + analysis_review_state(data).row_color)

    @staticmethod
    def _analysis_cell_fill(key: str, value: str) -> QColor | None:
        # One universal FALSE highlight keeps the Analysis grid readable. The
        # column header already identifies NAME / FEEDER / SMART / TYPE / IP / LINK.
        return QColor("#F7D7D7") if value.upper() == "FALSE" else None

    def refresh_comparison(self):
        if not hasattr(self, "comparison_table"):
            return
        self.comparison_table.setRowCount(0)
        if not self.store:
            self.comparison_summary.setText("No site selected")
            if hasattr(self, "comparison_review_progress"):
                self.comparison_review_progress.setText("Review 0 / 0 · Resolution 0 / 0 issues")
            if hasattr(self, "comparison_locator"):
                self.comparison_locator.setRowCount(0)
            return
        rows = self.store.rows()
        term = self.search_edit.text().strip().lower()
        review_filter = self.rmu_review_filter_combo.currentText() if hasattr(self, "rmu_review_filter_combo") else "ALL REVIEWS"
        analysis_filter = self.analysis_combo.currentText() if hasattr(self, "analysis_combo") else "ALL ANALYSIS"
        review_map = self.store.rmu_review_map()
        shown = []
        for data in rows:
            rmu = clean(data.get("rmu"))
            review_status = clean(review_map.get(rmu, {}).get("review_status")).upper() or "UNREVIEWED"
            if review_filter != "ALL REVIEWS" and review_status != review_filter:
                continue
            if not self._analysis_filter_match(data, analysis_filter):
                continue
            resolution_summary = self.store.rmu_resolution_summary(rmu)
            searchable = " | ".join(clean(data.get(k)) for k, _, _ in COLUMNS) + " | " + resolution_summary
            if term and term not in searchable.lower():
                continue
            shown.append((data, review_status))

        self.comparison_table.setRowCount(len(shown))
        analysis_keys = {"analysis_name", "analysis_feeder", "analysis_smart", "analysis_type", "analysis_ip", "analysis_link"}
        neutral_review_keys = analysis_keys | {"remarks", "comments"}
        for r, (data, tag) in enumerate(shown):
            row_fill = self._analysis_row_fill(data)
            rmu = clean(data.get("rmu"))
            resolution_summary = self.store.rmu_resolution_summary(rmu)
            for c, (key, _label, _) in enumerate(COMPARISON_COLUMNS):
                value = resolution_summary if key == "comments" else clean(data.get(key, ""))
                item = QTableWidgetItem(value)
                # The review block stays visually neutral.  Starting with
                # No./RMU, all actual source-data columns carry the row-level
                # business color so the issue remains visible while scrolling.
                item.setBackground(QColor("#FFFFFF") if key in neutral_review_keys else row_fill)
                if key in analysis_keys:
                    detail = clean(data.get(f"{key}_detail", ""))
                    item.setToolTip(detail or value)
                    analysis_fill = self._analysis_cell_fill(key, value)
                    if analysis_fill:
                        item.setBackground(analysis_fill)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    if key == "comments":
                        tooltip = self.store.rmu_resolution_tooltip(rmu)
                        state = analysis_review_state(data)
                        if state.issue_count > 0:
                            tooltip += "\n\nDouble-click to resolve every active FALSE Analysis field."
                        item.setToolTip(tooltip)
                    else:
                        item.setToolTip(value)
                if key in {"no", "rmu"}:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                if key == "comments" and value:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.comparison_table.setItem(r, c, item)

        # Refresh the frozen identity strip from the exact same filtered row
        # sequence before applying column visibility.  This guarantees that the
        # locator cannot drift from the main review table.
        self._refresh_comparison_locator(shown)

        # Visibility can be changed while data is loaded; re-apply it after row refresh.
        self._apply_comparison_column_visibility()
        analysis_fields = (
            ("analysis_name", "NAME"),
            ("analysis_feeder", "FEEDER"),
            ("analysis_smart", "SMART"),
            ("analysis_type", "TYPE"),
            ("analysis_ip", "IP"),
            ("analysis_link", "LINK"),
        )
        field_false_counts = Counter()
        for row in rows:
            for key, _label in analysis_fields:
                if clean(row.get(key)).upper() == "FALSE":
                    field_false_counts[key] += 1

        issue_parts = [
            f"{label} {field_false_counts[key]}"
            for key, label in analysis_fields
            if field_false_counts[key] > 0
        ]
        issue_text = " · ".join(issue_parts) if issue_parts else "No analysis mismatches"
        self.comparison_summary.setText(
            f"Total {len(rows)} · Shown {len(shown)} · {issue_text}"
        )

        active_rmus = [clean(row.get("rmu")) for row in rows if clean(row.get("rmu"))]
        active_rmus = list(dict.fromkeys(active_rmus))
        review_counts = Counter(
            clean(review_map.get(rmu, {}).get("review_status")).upper() or "UNREVIEWED"
            for rmu in active_rmus
        )
        reviewed_or_action = review_counts["REVIEWED"] + review_counts["NEEDS ACTION"]
        review_pct = int(round((reviewed_or_action / len(active_rmus) * 100.0) if active_rmus else 0.0))
        all_resolutions = self.store.rmu_resolution_map()
        total_issue_decisions = 0
        resolved_issue_decisions = 0
        for row in rows:
            rmu = clean(row.get("rmu"))
            state = analysis_review_state(row)
            total_issue_decisions += state.issue_count
            saved = all_resolutions.get(rmu, {}) if isinstance(all_resolutions, dict) else {}
            resolved_issue_decisions += sum(1 for field in state.false_fields if field in saved)
        if hasattr(self, "comparison_review_progress"):
            self.comparison_review_progress.setText(
                f"Review {reviewed_or_action} / {len(active_rmus)} · {review_pct}% · "
                f"Resolution {resolved_issue_decisions} / {total_issue_decisions} issues · "
                f"Needs Action {review_counts['NEEDS ACTION']}"
            )


    def _select_comparison_rmu(self, rmu: str):
        """Restore a reviewed row selection after the table refreshes."""
        rmu_col = next((i for i, (key, _label, _width) in enumerate(COMPARISON_COLUMNS) if key == "rmu"), -1)
        for row in range(self.comparison_table.rowCount()):
            item = self.comparison_table.item(row, rmu_col) if rmu_col >= 0 else None
            if item and item.text() == str(rmu):
                self.comparison_table.clear_spreadsheet_selection()
                item.setSelected(True)
                self.comparison_table.setCurrentItem(item)
                self.comparison_table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                break

    def refresh_changes(self):
        if not hasattr(self, "changes_table"):
            return
        changes = self.store.changes() if self.store else []
        if hasattr(self, "changes_stack"):
            self.changes_stack.setCurrentWidget(self.changes_table if changes else self.changes_empty)
        self.changes_table.setRowCount(len(changes))
        keys = ["id", "rmu", "field_name", "old_value", "new_value", "reason", "modified_by", "modified_at"]
        for r, data in enumerate(changes):
            for c, key in enumerate(keys):
                item = QTableWidgetItem(clean(data.get(key, "")))
                item.setToolTip(item.text())
                self.changes_table.setItem(r, c, item)

    def refresh_versions(self):
        if not hasattr(self, "versions_table"):
            return
        versions = self.store.versions() if self.store else []
        if hasattr(self, "versions_stack"):
            self.versions_stack.setCurrentWidget(self.versions_table if versions else self.versions_empty)
        self.versions_table.setRowCount(len(versions))
        keys = ["id", "version_name", "description", "created_by", "created_at"]
        for r, data in enumerate(versions):
            for c, key in enumerate(keys):
                item = QTableWidgetItem(clean(data.get(key, "")))
                item.setToolTip(item.text())
                self.versions_table.setItem(r, c, item)

    def _sync_signal_review_fingerprints(self, report: DBSmartReport | None) -> int:
        if not self.store or report is None:
            return 0
        fingerprints = {
            row.row_key: {
                "row_hash": signal_review_row_hash(row, report.analysis_column),
                "source_hash": report.source_hash,
            }
            for row in report.rows
        }
        return self.store.sync_db_smart_review_fingerprints(fingerprints, modified_by="SYSTEM")

    @staticmethod
    def _set_workflow_badge(label: QLabel, state: str) -> None:
        object_name = {"done": "WorkflowDone", "current": "WorkflowCurrent"}.get(state, "WorkflowPending")
        if label.objectName() != object_name:
            label.setObjectName(object_name)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

    def _update_delivery_workflow(
        self, *, sources_complete: bool, validation_complete: bool,
        review_total: int, reviewed: int, needs_action: int, report_exported: bool,
    ) -> None:
        """Refresh the current delivery stage from live validation/review state.

        Validation completion is a technical milestone, not the final project
        status. Once validation exists, the top-right status represents the
        human Review stage until every active RMU and signal record has been
        processed and no Needs Action remains.
        """
        processed = reviewed + needs_action
        unreviewed = max(0, review_total - processed)
        review_pct = int(round((processed / review_total * 100.0) if review_total else 0.0))
        review_complete = bool(review_total) and unreviewed == 0 and needs_action == 0

        if not sources_complete:
            state = "SOURCES INCOMPLETE"
            display_state = state
        elif not validation_complete:
            state = "VALIDATION REQUIRED"
            display_state = state
        elif needs_action:
            state = "ACTION REQUIRED"
            display_state = f"ACTION REQUIRED · {needs_action}"
        elif review_complete:
            state = "READY FOR EXPORT"
            display_state = state
        else:
            state = "REVIEW PENDING"
            display_state = f"REVIEW PENDING · {review_pct}%"

        self.project_delivery_state = state
        if hasattr(self, "project_state_label"):
            self.project_state_label.setText(f"STATUS · {display_state}")
            if state in {"ACTION REQUIRED", "SOURCES INCOMPLETE"}:
                self.project_state_label.setStyleSheet(
                    "color:#8B3A2B;background:#FFF1EF;border:1px solid #F0C3BC;border-radius:9px;padding:4px 9px;font-size:8.5pt;font-weight:700;"
                )
            elif state == "READY FOR EXPORT":
                self.project_state_label.setStyleSheet(
                    "color:#087C80;background:#E7F7F6;border:1px solid #BFE9E6;border-radius:9px;padding:4px 9px;font-size:8.5pt;font-weight:700;"
                )
            elif state == "REVIEW PENDING":
                self.project_state_label.setStyleSheet(
                    "color:#805B12;background:#FFF8E6;border:1px solid #F1D493;border-radius:9px;padding:4px 9px;font-size:8.5pt;font-weight:700;"
                )
            else:
                self.project_state_label.setStyleSheet(
                    "color:#315069;background:#F1F6F9;border:1px solid #D1DEE7;border-radius:9px;padding:4px 9px;font-size:8.5pt;font-weight:700;"
                )

        if not hasattr(self, "workflow_step_labels"):
            return
        self._set_workflow_badge(self.workflow_step_labels["sources"], "done" if sources_complete else "current")
        self._set_workflow_badge(
            self.workflow_step_labels["validation"],
            "done" if validation_complete else ("current" if sources_complete else "pending"),
        )
        self._set_workflow_badge(
            self.workflow_step_labels["review"],
            "done" if review_complete else ("current" if validation_complete else "pending"),
        )
        self._set_workflow_badge(
            self.workflow_step_labels["report"],
            "done" if (report_exported and review_complete) else ("current" if review_complete else "pending"),
        )

        if not sources_complete:
            detail = "Complete the required RMU and Signal Mapping source tables."
        elif not validation_complete:
            detail = "Sources are ready. Run Validation to calculate RMU and Signal Mapping results."
        elif needs_action:
            detail = (
                f"Human Review {processed}/{review_total} · {review_pct}% · "
                f"{needs_action} Needs Action · {unreviewed} Unreviewed"
            )
        elif review_complete and report_exported:
            detail = "Human Review 100% complete · current Migration Report export is up to date."
        elif review_complete:
            detail = "Human Review 100% complete · Migration Report is ready for export."
        else:
            detail = f"Human Review {processed}/{review_total} · {review_pct}% · {unreviewed} Unreviewed"
        self.workflow_detail.setText(detail)

    def refresh_dashboard(self):
        if not hasattr(self, "metric_rmu_total"):
            return

        rmu_cards = (
            self.metric_rmu_total, self.metric_rmu_pass, self.metric_rmu_issues,
            self.metric_rmu_reviewed, self.metric_rmu_needs_action,
        )
        signal_cards = (
            self.metric_signal_total, self.metric_signal_checked, self.metric_signal_matched,
            self.metric_signal_mismatched, self.metric_signal_unchecked, self.metric_signal_needs_action,
        )
        if not self.store:
            for card in rmu_cards + signal_cards:
                card.set_value("0")
            self.metric_rmu_reviewed.set_value("0 / 0")
            self.dashboard_rmu_issue_summary.setText("No RMU validation loaded")
            self.dashboard_signal_summary.setText("No Signal Mapping validation loaded")
            self.dashboard_rmu_review_summary.setText("Review progress: 0 / 0 · 0%")
            self.dashboard_signal_review_summary.setText("Review progress: 0 / 0 · 0%")
            self.dashboard_rmu_review_progress.setValue(0)
            self.dashboard_signal_review_progress.setValue(0)
            self.dash_project_name.setText("No site selected")
            if hasattr(self, "dashboard_context_site"):
                self.dashboard_context_site.setText("Not selected")
            self.dash_project_path.setText(str(workspace_root()))
            self.dash_last_version.setText("Latest version: —")
            self.dashboard_sources.clear()
            if hasattr(self, "dashboard_rmu_issues_button"):
                self.dashboard_rmu_issues_button.setText("Run Validation First")
                self.dashboard_rmu_issues_button.setEnabled(False)
            if hasattr(self, "dashboard_signal_mismatch_button"):
                self.dashboard_signal_mismatch_button.setText("Run Validation First")
                self.dashboard_signal_mismatch_button.setEnabled(False)
            self.project_title.setText("No site selected")
            self.project_subtitle.setText("Migration Report · Select a site to validate and review migration data")
            self._update_delivery_workflow(
                sources_complete=False, validation_complete=False, review_total=0,
                reviewed=0, needs_action=0, report_exported=False,
            )
            return

        # RMU module: automated Analysis and human Review are independent.
        rows = self.store.rows()
        rmu_states = [analysis_review_state(row) for row in rows]
        rmu_pass = sum(state.is_pass for state in rmu_states)
        rmu_issues = sum(state.issue_count > 0 for state in rmu_states)
        rmu_no_analysis = sum(not state.has_result for state in rmu_states)
        review_map = self.store.rmu_review_map()
        active_rmus = {clean(row.get("rmu")) for row in rows if clean(row.get("rmu"))}
        rmu_review_counts = Counter(
            clean(review_map.get(rmu, {}).get("review_status")).upper() or "UNREVIEWED"
            for rmu in active_rmus
        )
        rmu_total = len(rows)
        rmu_reviewed = rmu_review_counts["REVIEWED"]
        rmu_needs = rmu_review_counts["NEEDS ACTION"]
        rmu_processed = rmu_reviewed + rmu_needs
        rmu_unreviewed = max(0, rmu_total - rmu_processed)
        rmu_review_pct = int(round((rmu_processed / rmu_total * 100.0) if rmu_total else 0.0))

        self.metric_rmu_total.set_value(rmu_total)
        self.metric_rmu_pass.set_value(rmu_pass)
        self.metric_rmu_issues.set_value(rmu_issues)
        self.metric_rmu_reviewed.set_value(f"{rmu_reviewed} / {rmu_total}")
        self.metric_rmu_needs_action.set_value(rmu_needs)
        self.dashboard_rmu_review_progress.setValue(rmu_review_pct)
        self.dashboard_rmu_review_progress.setFormat(f"{rmu_review_pct}%")
        self.dashboard_rmu_review_summary.setText(
            f"Review progress: {rmu_processed} / {rmu_total} processed · Reviewed {rmu_reviewed} · Unreviewed {rmu_unreviewed} · Needs Action {rmu_needs}"
        )

        issue_counts = Counter(field for state in rmu_states for field in state.false_fields)
        issue_parts = [
            f"{name} {issue_counts[name]}"
            for name in ("NAME", "FEEDER", "SMART", "TYPE", "IP", "LINK")
            if issue_counts[name]
        ]
        if rmu_no_analysis:
            issue_parts.append(f"NO ANALYSIS {rmu_no_analysis}")
        self.dashboard_rmu_issue_summary.setText(
            "Affected RMUs by field: " + (" · ".join(issue_parts) if issue_parts else "None")
        )
        if hasattr(self, "dashboard_rmu_issues_button"):
            if not rmu_total:
                self.dashboard_rmu_issues_button.setText("Run Validation First")
                self.dashboard_rmu_issues_button.setEnabled(False)
                self.dashboard_rmu_issues_button.setToolTip("Run Validation before reviewing RMU issues.")
            elif rmu_issues:
                self.dashboard_rmu_issues_button.setText(f"Review RMU Issues ({rmu_issues})")
                self.dashboard_rmu_issues_button.setEnabled(True)
                self.dashboard_rmu_issues_button.setToolTip("Open RMU Data Review filtered to ANY MISMATCH.")
            else:
                self.dashboard_rmu_issues_button.setText("No RMU Issues")
                self.dashboard_rmu_issues_button.setEnabled(False)
                self.dashboard_rmu_issues_button.setToolTip("No RMU Analysis issues were found. Use the left navigation to open the full RMU Data Review.")

        # Signal Mapping module. Build from the same live snapshots used by the
        # review page and invalidate only rows whose validation fingerprint changed.
        signal_report = self.db_smart_report
        if signal_report is None:
            try:
                ioa_path = self.store.source_path("ioa")
                adms_sld_path = self.store.source_path("adms_sld")
                standard_path = standard_reference_path()
                if ioa_path and adms_sld_path and standard_path.exists():
                    signal_report = build_signal_mapping_report(
                        ioa_path, adms_sld_path, standard_path,
                        ioa_overrides=self.store.source_column_overrides("ioa"),
                        adms_sld_overrides=self.store.source_column_overrides("adms_sld"),
                        standard_overrides=self.store.source_column_overrides("standard_reference"),
                    )
            except Exception:
                signal_report = None

        signal_total = signal_checked = signal_matched = signal_mismatched = signal_unchecked = 0
        signal_reviewed = signal_needs = signal_unreviewed = 0
        if signal_report is None:
            for card in signal_cards:
                card.set_value("0")
            self.dashboard_signal_summary.setText("Signal Mapping validation unavailable · check IOA / ADMS SLD / STANDARD")
            self.dashboard_signal_review_summary.setText("Review progress: 0 / 0 · 0%")
            self.dashboard_signal_review_progress.setValue(0)
            if hasattr(self, "dashboard_signal_mismatch_button"):
                self.dashboard_signal_mismatch_button.setText("Signal Validation Unavailable")
                self.dashboard_signal_mismatch_button.setEnabled(False)
                self.dashboard_signal_mismatch_button.setToolTip("Signal Mapping validation requires IOA, ADMS SLD and STANDARD.")
        else:
            self._sync_signal_review_fingerprints(signal_report)
            signal_total = len(signal_report.rows)
            if signal_report.analysis_column is not None:
                for row in signal_report.rows:
                    result = clean(row.values[signal_report.analysis_column]).upper()
                    signal_matched += result == "TRUE"
                    signal_mismatched += result == "FALSE"
            signal_checked = signal_matched + signal_mismatched
            signal_unchecked = max(0, signal_total - signal_checked)
            signal_review_map = self.store.db_smart_review_map()
            active_keys = {row.row_key for row in signal_report.rows}
            signal_review_counts = Counter(
                clean(signal_review_map.get(key, {}).get("review_status")).upper() or "UNREVIEWED"
                for key in active_keys
            )
            signal_reviewed = signal_review_counts["REVIEWED"]
            signal_needs = signal_review_counts["NEEDS ACTION"]
            signal_processed = signal_reviewed + signal_needs
            signal_unreviewed = max(0, signal_total - signal_processed)
            signal_review_pct = int(round((signal_processed / signal_total * 100.0) if signal_total else 0.0))
            rate = (signal_matched / signal_checked * 100.0) if signal_checked else 0.0

            self.metric_signal_total.set_value(signal_total)
            self.metric_signal_checked.set_value(signal_checked)
            self.metric_signal_matched.set_value(signal_matched)
            self.metric_signal_mismatched.set_value(signal_mismatched)
            self.metric_signal_unchecked.set_value(signal_unchecked)
            self.metric_signal_needs_action.set_value(signal_needs)
            self.dashboard_signal_review_progress.setValue(signal_review_pct)
            self.dashboard_signal_review_progress.setFormat(f"{signal_review_pct}%")
            self.dashboard_signal_review_summary.setText(
                f"Review progress: {signal_processed} / {signal_total} processed · Reviewed {signal_reviewed} · Unreviewed {signal_unreviewed} · Needs Action {signal_needs}"
            )
            self.dashboard_signal_summary.setText(
                f"Matched / Checked = {signal_matched} / {signal_checked} · Match rate {rate:.2f}% · Unchecked {signal_unchecked}"
            )
            if hasattr(self, "dashboard_signal_mismatch_button"):
                if signal_mismatched:
                    self.dashboard_signal_mismatch_button.setText(f"Review Signal Mismatches ({signal_mismatched})")
                    self.dashboard_signal_mismatch_button.setEnabled(True)
                    self.dashboard_signal_mismatch_button.setToolTip("Open Signal Mapping Review filtered to MISMATCHED.")
                else:
                    self.dashboard_signal_mismatch_button.setText("No Signal Mismatches")
                    self.dashboard_signal_mismatch_button.setEnabled(False)
                    self.dashboard_signal_mismatch_button.setToolTip("No signal mismatches were found. Use the left navigation to open the full Signal Mapping Review.")

        site_name = self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name
        self.dash_project_name.setText(site_name)
        if hasattr(self, "dashboard_context_site"):
            self.dashboard_context_site.setText(site_name)
        repository_path = self.store.config.get("repository_path", "")
        self.dash_project_path.setText(
            (f"Repository: {repository_path}\n" if repository_path else "") + f"Workspace: {self.store.folder}"
        )
        versions = self.store.versions()
        self.dash_last_version.setText(
            f"Latest version: {versions[0]['version_name']}  ·  {versions[0]['created_at']}" if versions else "Latest version: —"
        )

        self.dashboard_sources.clear()
        site_for_sources = self.selected_site
        if site_for_sources is None or site_for_sources.name.casefold() != site_name.casefold():
            site_for_sources = next((site for site in self.repository_sites if site.name.casefold() == site_name.casefold()), None)
        for key, (label, _) in SOURCE_TYPES.items():
            live_path = site_for_sources.sources.get(key) if site_for_sources else None
            path = Path(live_path) if live_path else self.store.source_path(key)
            origin = "Site Repository" if live_path else ("Workspace snapshot" if path else "")
            item = QListWidgetItem(
                f"{'READY' if path else 'MISSING'}   {label}\n"
                f"{path.name if path else 'Not available'}{f' · {origin}' if origin else ''}"
            )
            item.setIcon(app_icon("database"))
            item.setForeground(QColor(COLORS["success"] if path else COLORS["muted"]))
            self.dashboard_sources.addItem(item)
        standard_path = standard_reference_path()
        standard_item = QListWidgetItem(
            f"{'READY' if standard_path.exists() else 'MISSING'}   IOA STANDARD ({standard_reference_origin()})\n"
            f"{standard_path.name if standard_path.exists() else 'Reference not available'}"
        )
        standard_item.setIcon(app_icon("signal"))
        standard_item.setForeground(QColor(COLORS["success"] if standard_path.exists() else COLORS["danger"]))
        self.dashboard_sources.addItem(standard_item)

        # Project state uses both business modules. IOA + STANDARD are required
        # for formal Signal Mapping delivery even though the repository scanner
        # remains backward-compatible with older RMU-only site folders.
        repository_site = self.selected_site
        if repository_site is None or repository_site.name.casefold() != site_name.casefold():
            repository_site = next((site for site in self.repository_sites if site.name.casefold() == site_name.casefold()), None)
        base_sources_ready = bool(repository_site and repository_site.ready)
        signal_sources_ready = bool(
            (repository_site.sources.get("ioa") if repository_site else self.store.source_path("ioa"))
            and standard_path.exists()
        )
        sources_complete = base_sources_ready and signal_sources_ready
        validation_complete = bool(rows) and signal_report is not None
        review_total = rmu_total + signal_total
        reviewed_total = rmu_reviewed + signal_reviewed
        needs_total = rmu_needs + signal_needs
        latest_state_ts = 0.0
        for table_name in ("comparison", "rmu_reviews", "db_smart_reviews"):
            try:
                value = self.store.db.execute(f"SELECT MAX(updated_at) FROM {table_name}").fetchone()[0]
                if value:
                    latest_state_ts = max(latest_state_ts, datetime.fromisoformat(str(value)).timestamp())
            except Exception:
                pass
        if signal_report is not None:
            for path in signal_report.input_paths:
                try:
                    latest_state_ts = max(latest_state_ts, Path(path).stat().st_mtime)
                except OSError:
                    pass
        report_times = []
        if self.store.reports_dir.exists():
            for report_path in self.store.reports_dir.glob("*.xlsx"):
                try:
                    report_times.append(report_path.stat().st_mtime)
                except OSError:
                    pass
        latest_report_ts = max(report_times, default=0.0)
        report_exported = bool(latest_report_ts and latest_report_ts >= latest_state_ts)
        self._update_delivery_workflow(
            sources_complete=sources_complete, validation_complete=validation_complete,
            review_total=review_total, reviewed=reviewed_total, needs_action=needs_total,
            report_exported=report_exported,
        )

    def refresh_export_page(self):
        if not hasattr(self, "export_project_label"):
            return
        if not self.store:
            self.export_project_label.setText("Saudi ADMS Site: —")
            self.export_readiness_label.setText("Delivery status: select a site and run validation")
            self.export_readiness_label.setStyleSheet("")
            self.export_path_label.setText("Report folder: —")
        else:
            self.export_project_label.setText(f"Saudi ADMS Site: {self.store.config.get('site_name') or self.store.config.get('repository_site') or self.store.folder.name}")
            state = getattr(self, "project_delivery_state", "—")
            if state == "READY FOR EXPORT":
                self.export_readiness_label.setText("Delivery status: Ready for formal Migration Report export")
                self.export_readiness_label.setStyleSheet(f"color:{COLORS['success']};font-weight:700;")
            else:
                self.export_readiness_label.setText(
                    f"Delivery status: {state} · Export is available as a review draft; complete Human Review before formal handover."
                )
                self.export_readiness_label.setStyleSheet(f"color:{COLORS['warning']};font-weight:650;")
            self.export_path_label.setText(f"Report folder: {self.store.reports_dir}")

    def closeEvent(self, event):
        if self.store:
            try:
                self.store.db.close()
            except Exception:
                pass
        super().closeEvent(event)
