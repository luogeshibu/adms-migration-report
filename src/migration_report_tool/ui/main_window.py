from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import os
import queue
import re
import subprocess
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer, QRect, QSettings, QEvent, QModelIndex, Signal, QItemSelection, QItemSelectionModel, QObject, QRunnable, QThreadPool, Slot, QEventLoop
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QKeySequence, QShortcut, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QCheckBox,
    QDialog as _QtDialog,
    QDialogButtonBox,
    QFileDialog as _QtFileDialog,
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
    QMessageBox as _QtMessageBox,
    QMenu,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QStatusBar,
    QSizePolicy,
    QSpacerItem,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QInputDialog as _QtInputDialog,
)

from ..utils.paths import standard_reference_path, standard_reference_origin, bundled_standard_reference_path
from ..core import (
    APP_NAME,
    APP_VERSION,
    COLUMNS,
    DATA_GROUPS,
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
    read_csv_rows,
    read_excel_rows,
    resource_root,
    project_data_root,
    project_data_root_is_configured,
    confirm_project_data_root,
    set_project_data_root,
    workspace_root,
    import_source,
)
from ..db_smart import (
    DBSmartReport, build_signal_mapping_report, signal_row_is_zenon_only, zenon_only_adms_match_rows,
    signal_review_alias_map, signal_review_metadata,
)
from ..review_status import (
    analysis_review_state, rmu_review_display_status, signal_review_display_status,
    normalize_review_status, review_record_is_explicit,
)

from ..domain.analysis.resolution_text import (
    build_resolution_description, compact_resolution_text, resolution_display_text,
)
from ..domain.analysis.signal_action_comment import (
    SIGNAL_ACTIONS, format_signal_action_comment, parse_signal_action_comment,
)
from ..infrastructure.database.global_settings_store import (
    review_hidden_columns as load_review_hidden_columns,
    replace_review_hidden_columns as save_review_hidden_columns,
)

from ..config.sources import schema_for
from ..config.column_schema import EQUIPMENT_SOURCE_GROUPS
from ..domain.schema import (BLANK_OVERRIDE_TOKEN, MappingKind, resolve_schema, encode_manual_override, decode_manual_override, is_manual_override)
from ..config.source_modules import MODULE_SOURCE_GROUPS
from ..infrastructure.parsers import validate_source_file, list_excel_sheets, resolve_source_excel_sheet_name
from ..services.schema_service import (
    get_source_overrides, set_source_overrides, get_source_display_names, set_source_display_names,
    default_display_name, canonical_system_field_label, apply_display_names_to_groups, RMU_REVIEW_DISPLAY_BINDINGS, SIGNAL_REVIEW_DISPLAY_BINDINGS,
    custom_review_column_key, rmu_review_groups, equipment_source_review_groups, validation_summary,
    system_logic_field_keys, equipment_review_protected_column_keys, get_hidden_source_fields, set_hidden_source_fields,
    get_resolved_source_mappings, set_resolved_source_mappings, module_field_mapping_lines,
    get_source_column_order, set_source_column_order,
)
from ..services.standard_reference_service import (
    current_standard_reference_info, list_standard_references, add_standard_reference,
    activate_standard_reference, restore_bundled_standard_reference,
)
from ..services.rmu_review_service import (
    rmu_type_issue_map, build_equipment_source_view, equipment_inventory_type_counts,
)
from ..services.configurable_comparison_service import (
    get_config as get_equipment_comparison_config, save_config as save_equipment_comparison_config,
    source_path as configurable_source_path, encode_source_path as encode_configurable_source_path,
    inspect_table as inspect_configurable_table, list_sheets as list_configurable_sheets,
    config_status as configurable_comparison_status, source_column_catalog as configurable_source_columns,
    analysis_column_key as configurable_analysis_column_key, analysis_detail_key as configurable_analysis_detail_key,
    scan_site_tabular_files as scan_configurable_site_files, file_family_key as configurable_file_family_key,
    family_candidates as configurable_family_candidates, file_pool_usage as configurable_file_pool_usage,
    save_signal_source_assignment as save_configurable_signal_assignment,
    resolve_signal_source_assignment as resolve_configurable_signal_assignment,
    get_signal_source_assignments as get_configurable_signal_assignments,
    configured_live_source_changes, remember_configured_live_source_metadata,
    configured_live_source_metadata,
    list_comparison_profiles as list_equipment_comparison_profiles,
    get_comparison_profile as get_equipment_comparison_profile,
    save_comparison_profile as save_equipment_comparison_profile,
    delete_comparison_profile as delete_equipment_comparison_profile,
    apply_comparison_profile as apply_equipment_comparison_profile,
    get_profile_link as get_equipment_comparison_profile_link,
    save_profile_link as save_equipment_comparison_profile_link,
    COMPARISON_MODE_DEFAULT, COMPARISON_MODE_STRICT, COMPARISON_MODE_IGNORE_BLANK,
)
from ..services.audit_presentation import present_audit_item
from ..services.derived_table_service import (
    available_source_types, build_derived_table, default_derived_config, export_derived_csv,
    export_derived_xlsx, slug_key, source_alias, source_field_catalog, source_label,
)
from ..infrastructure.export.signoff_pdf import export_site_signoff_pdf
from .i18n import (
    LANG_EN, LANG_ZH_CN, SUPPORTED_LANGUAGES, current_language, mark_combo_for_translation,
    normalize_language, set_current_language, tr as ui_tr, translate_widget_tree,
)


# Centralized bilingual wrappers.  They cover modal/static Qt dialogs as well as
# all custom QDialog subclasses, so switching language is not limited to the
# main window's widget tree.  Business keys/source headers are passed through by
# ui_tr when they intentionally have no translation.
class QDialog(_QtDialog):
    def showEvent(self, event):
        translate_widget_tree(self, current_language())
        super().showEvent(event)


class QMessageBox(_QtMessageBox):
    @staticmethod
    def _localized_call(method, parent, title, text, *args, **kwargs):
        return method(parent, ui_tr(title, current_language()), ui_tr(text, current_language()), *args, **kwargs)

    @staticmethod
    def information(parent, title, text, *args, **kwargs):
        return QMessageBox._localized_call(_QtMessageBox.information, parent, title, text, *args, **kwargs)

    @staticmethod
    def warning(parent, title, text, *args, **kwargs):
        return QMessageBox._localized_call(_QtMessageBox.warning, parent, title, text, *args, **kwargs)

    @staticmethod
    def critical(parent, title, text, *args, **kwargs):
        return QMessageBox._localized_call(_QtMessageBox.critical, parent, title, text, *args, **kwargs)

    @staticmethod
    def question(parent, title, text, *args, **kwargs):
        return QMessageBox._localized_call(_QtMessageBox.question, parent, title, text, *args, **kwargs)


class QInputDialog(_QtInputDialog):
    @staticmethod
    def getItem(parent, title, label, *args, **kwargs):
        """Localized item picker with an explicit Save/Cancel commit action.

        Qt's Simplified-Chinese translation renders the stock OK button as
        ``正常`` on some Windows/PySide6 builds, which looks like a status value
        instead of an action.  Build the dialog explicitly so every selection
        dialog uses ``保存`` / ``取消`` in Chinese (Save / Cancel in English)
        while preserving the exact item value returned to existing callers.
        """
        items = list(args[0] if len(args) >= 1 else kwargs.pop("items", []))
        current = int(args[1] if len(args) >= 2 else kwargs.pop("current", 0) or 0)
        editable = bool(args[2] if len(args) >= 3 else kwargs.pop("editable", True))
        dialog = _QtInputDialog(parent)
        dialog.setWindowTitle(ui_tr(title, current_language()))
        dialog.setLabelText(ui_tr(label, current_language()))
        dialog.setComboBoxItems(items)
        dialog.setComboBoxEditable(editable)
        combo = dialog.findChild(QComboBox)
        if combo is not None and items:
            combo.setCurrentIndex(max(0, min(current, len(items) - 1)))
        dialog.setOkButtonText(ui_tr("Save", current_language()))
        dialog.setCancelButtonText(ui_tr("Cancel", current_language()))
        if dialog.exec() != _QtDialog.Accepted:
            return "", False
        return dialog.textValue(), True

    @staticmethod
    def getText(parent, title, label, *args, **kwargs):
        return _QtInputDialog.getText(parent, ui_tr(title, current_language()), ui_tr(label, current_language()), *args, **kwargs)

    @staticmethod
    def getMultiLineText(parent, title, label, *args, **kwargs):
        return _QtInputDialog.getMultiLineText(parent, ui_tr(title, current_language()), ui_tr(label, current_language()), *args, **kwargs)


class I18nStatusBar(QStatusBar):
    """Status bar that localizes transient presentation messages at write time."""

    def showMessage(self, message, timeout=0):
        super().showMessage(ui_tr(message, current_language()), timeout)


class QFileDialog(_QtFileDialog):
    @staticmethod
    def getExistingDirectory(parent=None, caption='', *args, **kwargs):
        return _QtFileDialog.getExistingDirectory(parent, ui_tr(caption, current_language()), *args, **kwargs)

    @staticmethod
    def getOpenFileName(parent=None, caption='', *args, **kwargs):
        return _QtFileDialog.getOpenFileName(parent, ui_tr(caption, current_language()), *args, **kwargs)

    @staticmethod
    def getOpenFileNames(parent=None, caption='', *args, **kwargs):
        return _QtFileDialog.getOpenFileNames(parent, ui_tr(caption, current_language()), *args, **kwargs)

    @staticmethod
    def getSaveFileName(parent=None, caption='', *args, **kwargs):
        return _QtFileDialog.getSaveFileName(parent, ui_tr(caption, current_language()), *args, **kwargs)

from ..repository import (
    SOURCE_DEFINITIONS,
    SiteInfo,
    load_repository_root,
    load_last_site,
    save_repository_root,
    save_last_site,
    scan_repository,
    site_has_tabular_files,
    source_status,
    sync_site_to_project,
    load_source_detection_keywords,
    save_source_detection_keywords,
    load_source_detection_categories,
    save_source_detection_categories,
    classify_source_detection_hint,
    save_manual_source_assignment,
    rank_source_candidates,
    source_version_candidates,
    source_file_version_label,
    has_explicit_source_version,
    selected_repository_source_path,
    source_user_visible_name,
    source_user_visible_path,
    fingerprint,
    discover_site_sources,
)




# v0.8.47 uses one simple three-state Review workflow in both review modules.
# Automatic Analysis/Validation remains separate; only the Review cell uses this palette.
REVIEW_VISUALS = {
    "UNREVIEWED": ("Unreviewed", "#F3F4F6", "#475467"),
    "CLOSED": ("Closed", "#2E7D32", "#FFFFFF"),
    "NEEDS ACTION": ("Needs Action", "#D92D20", "#FFFFFF"),
}

def _review_visual(status: str) -> tuple[str, QColor, QColor]:
    key = clean(status).upper() or "UNREVIEWED"
    label, fill, text = REVIEW_VISUALS.get(key, (key.title(), "#F3F4F6", "#475467"))
    return ui_tr(label, current_language()), QColor(fill), QColor(text)

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


class BackgroundTaskSignals(QObject):
    """Signals used by the shared QThreadPool worker.

    Heavy file parsing, repository scans and validation work must never execute
    on the Qt GUI thread.  Results are delivered back to the main thread using
    queued Qt signals.
    """

    succeeded = Signal(object)
    failed = Signal(str)
    progressed = Signal(int, str)


class BackgroundTask(QRunnable):
    """Run one callable on the application's shared worker pool."""

    def __init__(self, fn, *, with_progress: bool = False):
        super().__init__()
        self.fn = fn
        self.with_progress = bool(with_progress)
        self.signals = BackgroundTaskSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            if self.with_progress:
                self.signals.succeeded.emit(self.fn(self.signals.progressed.emit))
            else:
                self.signals.succeeded.emit(self.fn())
        except Exception:
            self.signals.failed.emit(traceback.format_exc())


class BusyMarqueeProgressBar(QProgressBar):
    """Fixed-width marquee segment that visibly travels left/right while busy.

    QProgressBar's determinate value paints a chunk from the left edge, so a
    changing value can look like a static percentage bar in screenshots and on
    slower Windows desktops.  This subclass paints a constant-width segment
    whose *position* changes every timer tick.  As long as the Qt event loop is
    responsive, motion is unambiguous to the reviewer.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0, 100)
        self.setTextVisible(False)
        self.setMinimumHeight(10)
        self.setMaximumHeight(10)
        self._marquee_position = 0.0
        self._marquee_direction = 1.0
        self._marquee_timer = QTimer(self)
        self._marquee_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._marquee_timer.setInterval(16)
        self._marquee_timer.timeout.connect(self._advance_marquee)

    def start(self) -> None:
        if not self._marquee_timer.isActive():
            self._marquee_timer.start()
        self.update()

    def stop(self) -> None:
        self._marquee_timer.stop()

    def _advance_marquee(self) -> None:
        self._marquee_position += 2.8 * self._marquee_direction
        if self._marquee_position >= 100.0:
            self._marquee_position = 100.0
            self._marquee_direction = -1.0
        elif self._marquee_position <= 0.0:
            self._marquee_position = 0.0
            self._marquee_direction = 1.0
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        track = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QPen(QColor('#CFE3E5'), 1))
        painter.setBrush(QColor('#EEF6F7'))
        painter.drawRoundedRect(track, 4, 4)

        chunk_width = max(38, int(track.width() * 0.24))
        travel = max(0, track.width() - chunk_width)
        x = track.left() + int(travel * (self._marquee_position / 100.0))
        chunk = QRect(x, track.top() + 1, chunk_width, max(1, track.height() - 2))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#0EA5A8'))
        painter.drawRoundedRect(chunk, 3, 3)


class BusyOperationPopup(QFrame):
    """Small animated, non-modal progress popup for visible UI work.

    The App already pushes file parsing and validation onto worker threads.
    This popup complements that design by giving the reviewer immediate visual
    feedback for both background jobs and GUI-side table repaint operations
    such as Show All.  It intentionally stays non-modal so the application
    never feels frozen; buttons that must not be repeated are disabled by their
    existing task/render state.
    """

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("BusyOperationPopup")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFixedWidth(430)
        self.setStyleSheet(
            "QFrame#BusyOperationPopup{"
            "background:#FFFFFF;border:1px solid #B8CBDD;border-radius:12px;}"
            "QLabel#BusyPopupTitle{font-size:11pt;font-weight:750;color:#173A5E;border:none;}"
            "QLabel#BusyPopupDetail{font-size:9pt;color:#667085;border:none;}"
            "QProgressBar#BusyPopupProgress{border:1px solid #CFE3E5;border-radius:5px;"
            "background:#EEF6F7;min-height:8px;max-height:8px;text-align:center;}"
            "QProgressBar#BusyPopupProgress::chunk{background:#0EA5A8;border-radius:4px;}"
        )
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 14, 18, 14)
        box.setSpacing(7)
        self.title_label = QLabel("Loading...")
        self.title_label.setObjectName("BusyPopupTitle")
        self.detail_label = QLabel("Please wait while the current view is prepared.")
        self.detail_label.setObjectName("BusyPopupDetail")
        self.detail_label.setWordWrap(True)
        self.progress = BusyMarqueeProgressBar()
        self.progress.setObjectName("BusyPopupProgress")
        box.addWidget(self.title_label)
        box.addWidget(self.detail_label)
        box.addWidget(self.progress)
        self.hide()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.progress.start()

    def hideEvent(self, event) -> None:
        self.progress.stop()
        super().hideEvent(event)

    def set_message(self, title: str, detail: str = "", progress_value: int | None = None) -> None:
        self.title_label.setText(clean(title) or "Loading...")
        self.detail_label.setText(clean(detail) or "Please wait while the current view is prepared.")
        # Logical percentages belong in the detail text.  The bar itself is a
        # liveness indicator and therefore always remains a moving marquee.
        if self.isVisible():
            self.progress.start()
        self.adjustSize()
        self.setFixedWidth(430)


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
        "suggested_comment": clean(getattr(row, "suggested_comment", "")),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_repository_site(repository_root: Path, site_name: str, *, deep: bool) -> SiteInfo:
    """Discover one active site without parsing every other site in the Workspace."""
    site_dir = Path(repository_root) / site_name
    if not site_dir.exists() or not site_dir.is_dir():
        raise RuntimeError(f"Site {site_name} was not found under {repository_root}")
    sources, detections, unmapped = discover_site_sources(site_dir, deep=deep)
    return SiteInfo(site_name, site_dir, sources, detections, unmapped)


def _path_text_equal(left: str, right: str) -> bool:
    try:
        return Path(left).resolve() == Path(right).resolve()
    except (OSError, ValueError):
        return clean(left).casefold() == clean(right).casefold()


def _worker_effective_source_path(site: SiteInfo, store: ProjectStore, source_type: str) -> Path | None:
    """Resolve the same active source a reviewer sees, but without touching Qt.

    v0.8.181: explicit Site File Pool assignments for Signal Mapping win first.
    Equipment Data Review has its own configurable source engine and therefore
    never depends on these legacy role lookups. For remaining legacy roles,
    persistent version pins win first, then manual override, repository AUTO,
    then the last project snapshot.
    """
    if source_type in {"ioa", "adms_sld"}:
        assigned = resolve_configurable_signal_assignment(store, source_type)
        if assigned is not None and assigned.exists():
            return assigned
    selected = selected_repository_source_path(site, store, source_type)
    if selected is not None and selected.exists():
        return selected
    manual = (store.manual_source_overrides().get(source_type) or {})
    original_text = str(manual.get("original_path") or "").strip()
    if original_text:
        original = Path(original_text)
        if original.exists() and original.is_file():
            return original
    discovered = site.sources.get(source_type)
    if discovered and Path(discovered).exists():
        return Path(discovered)
    cached = store.source_path(source_type)
    if cached is not None and cached.exists():
        return cached
    return None


def _background_signal_mapping_module_job(
    project_folder: str, repository_root: str, site_name: str, progress=None
) -> dict:
    """Lazy-load Signal Mapping when the reviewer opens that module.

    This is intentionally narrower than Run Validation: it reads only the
    Signal Mapping inputs (STANDARD, ADMS and ZENON/IOA) and reconciles the
    persisted signal-review fingerprints.  No RMU validation is forced.
    """
    emit = progress or (lambda _value, _text: None)
    root = Path(repository_root)
    emit(5, "Resolving Signal Mapping sources")
    site = _load_repository_site(root, site_name, deep=False)
    store = ProjectStore(Path(project_folder))
    try:
        ioa_path = _worker_effective_source_path(site, store, "ioa")
        adms_sld_path = _worker_effective_source_path(site, store, "adms_sld")
        standard_path = standard_reference_path()

        # Filename-only startup discovery is deliberately cheap. If one of the
        # two site inputs is still unresolved, do one active-site deep scan here
        # while the progress strip is visible instead of asking the user to run
        # a completely unrelated full validation.
        if ioa_path is None or adms_sld_path is None:
            emit(15, "Checking the active site for Signal Mapping files")
            site = _load_repository_site(root, site_name, deep=True)
            ioa_path = _worker_effective_source_path(site, store, "ioa")
            adms_sld_path = _worker_effective_source_path(site, store, "adms_sld")

        missing = []
        if ioa_path is None:
            missing.append("ZENON-ADMS-IOA.csv")
        if adms_sld_path is None:
            missing.append("ADMS-SLD.csv")
        if not standard_path.exists():
            missing.append("IOA STANDARD.xlsx")
        if missing:
            return {"site": site, "report": None, "missing": missing}

        emit(30, "Reading STANDARD → ADMS → ZENON signal data")
        report = build_signal_mapping_report(
            ioa_path, adms_sld_path, standard_path,
            ioa_overrides=store.source_column_overrides("ioa"),
            adms_sld_overrides=store.source_column_overrides("adms_sld"),
            standard_overrides=store.source_column_overrides("standard_reference"),
            ioa_sheet_name=store.source_sheet_name("ioa") if hasattr(store, "source_sheet_name") else None,
            adms_sld_sheet_name=store.source_sheet_name("adms_sld") if hasattr(store, "source_sheet_name") else None,
        )

        emit(82, "Restoring Signal review / Need Action state")
        fingerprints = {
            item.row_key: {
                "row_hash": signal_review_row_hash(item, report.analysis_column),
                "source_hash": report.source_hash,
            }
            for item in report.rows
        }
        store.sync_db_smart_review_fingerprints(
            fingerprints, modified_by="SYSTEM",
            aliases=signal_review_alias_map(report),
            metadata={item.row_key: signal_review_metadata(report, item) for item in report.rows},
        )

        matched = mismatched = 0
        if report.analysis_column is not None:
            for item in report.rows:
                result = clean(item.values[report.analysis_column]).upper()
                matched += result == "TRUE"
                mismatched += result == "FALSE"
        zenon_extra = sum(signal_row_is_zenon_only(item) for item in report.rows)
        value_index = {key: i for i, (key, _label, _width) in enumerate(report.columns)}
        standard_dot_index = value_index.get("standard_dot_no")
        adms_dot_index = value_index.get("adms_dot_no")
        standard_points = sum(
            standard_dot_index is not None
            and standard_dot_index < len(item.values)
            and bool(clean(item.values[standard_dot_index]))
            for item in report.rows
        )
        adms_points = sum(
            adms_dot_index is not None
            and adms_dot_index < len(item.values)
            and bool(clean(item.values[adms_dot_index]))
            for item in report.rows
        )
        store.config["signal_validation_summary"] = {
            "total": int(adms_points),
            "standard_points": int(standard_points),
            "adms_points": int(adms_points),
            "matched": int(matched),
            "mismatched": int(mismatched),
            "zenon_extra": int(zenon_extra),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        store.save_config()
        emit(97, "Preparing Signal Mapping Review")
        return {
            "site": site, "report": report, "missing": [],
            "matched": int(matched), "mismatched": int(mismatched),
            "zenon_extra": int(zenon_extra), "standard_points": int(standard_points),
            "adms_points": int(adms_points),
        }
    finally:
        store.close()


def _build_active_equipment_review(store) -> tuple[list[dict], dict]:
    """Build the active Equipment Data Review projection.

    v0.8.178 uses the site-local configurable engine only after a comparison
    configuration has explicitly been saved. Legacy sites keep their existing
    five-source behavior until the reviewer opens Configure Comparison and
    saves the migrated/editable source definition.
    """
    config = get_equipment_comparison_config(store, bootstrap=False)
    if config.get("sources"):
        return build_equipment_source_view(store, "__ALL__")
    return build_comparison(store)


def _background_rmu_review_module_job(
    project_folder: str, repository_root: str, site_name: str, progress=None
) -> dict:
    """Build RMU review data on first module open when project.db has no rows."""
    emit = progress or (lambda _value, _text: None)
    root = Path(repository_root)
    emit(5, "Resolving RMU Data Review sources")
    site = _load_repository_site(root, site_name, deep=False)
    store = ProjectStore(Path(project_folder))
    try:
        configurable = get_equipment_comparison_config(store, bootstrap=False)
        changed_keys = []
        if configurable.get("sources"):
            emit(20, "Reading configured Equipment Data Review source tables")
        else:
            emit(20, "Loading changed RMU source files")
            sync = sync_site_to_project(store, site)
            changed_keys = list(sync.changed_keys)
        emit(62, "Calculating Equipment Data Review")
        rows, _summary = _build_active_equipment_review(store)
        if rows:
            store.save_comparison(rows)
        if configurable.get("sources"):
            remember_configured_live_source_metadata(store)
        emit(95, "Preparing Equipment Data Review")
        return {
            "site": site, "row_count": len(rows),
            "changed_keys": changed_keys,
        }
    finally:
        store.close()



def _background_rmu_render_prepare_job(
    project_folder: str,
    term: str,
    search_field: str,
    review_filter: str,
    analysis_filter: str,
    columns: tuple,
    profile: str = "RMU",
    progress=None,
) -> dict:
    """Prepare universal Equipment Data Review rows outside the Qt GUI thread.

    The row source may be the legacy five-source projection or the v0.8.178
    site-local configurable comparison engine. Review/Resolution/Comments and
    lifecycle semantics are shared by both modes.
    """
    emit = progress or (lambda _value, _text: None)
    store = ProjectStore(Path(project_folder))
    try:
        profile_token = clean(profile).upper() or "RMU"
        # v0.8.160: Equipment Data Review has one universal five-source data
        # model. RMU no longer takes a separate legacy table/render path; its
        # existing raw review key is preserved inside build_equipment_source_view
        # so all historical RMU comments/status/resolutions remain intact.
        inventory_mode = True
        term_cf = clean(term).casefold()
        search_field = clean(search_field) or "*"
        column_keys = [clean(item[0]) for item in tuple(columns or ()) if item]

        if inventory_mode:
            emit(8, "Reading configured equipment source tables")
            rows, source_summary = build_equipment_source_view(store, profile_token)
            emit(28, "Loading equipment review decisions")
            review_map = store.rmu_review_map()
            all_resolutions = store.rmu_resolution_map()
            tracking_rows = store.equipment_action_tracking() if hasattr(store, "equipment_action_tracking") else store.rmu_action_tracking()
            action_tracking_keys = [
                clean(item.get("equipment_key") or item.get("rmu")) for item in tracking_rows
                if clean(item.get("equipment_key") or item.get("rmu"))
            ]
            review_filter = clean(review_filter) or "ALL REVIEWS"
            analysis_filter = clean(analysis_filter) or "ALL ANALYSIS"

            def analysis_filter_match(data: dict) -> bool:
                if analysis_filter == "ALL ANALYSIS":
                    return True
                state = analysis_review_state(data)
                false_keys = set(state.false_fields)
                if analysis_filter == "PASSED":
                    return state.is_pass
                if analysis_filter == "ANY MISMATCH":
                    return state.issue_count > 0
                if analysis_filter == "1 ISSUE":
                    return state.issue_count == 1
                if analysis_filter == "2 ISSUES":
                    return state.issue_count == 2
                if analysis_filter == "MULTIPLE ISSUES":
                    return state.issue_count >= 3
                if analysis_filter == "CRITICAL":
                    return state.is_critical
                if analysis_filter.startswith("RULE::"):
                    return analysis_filter.split("::", 1)[1].upper() in {clean(value).upper() for value in false_keys}
                if analysis_filter.endswith(" MISMATCH"):
                    return analysis_filter.removesuffix(" MISMATCH") in false_keys
                return True

            def resolution_summary_for(review_key: str, data: dict) -> str:
                saved = all_resolutions.get(review_key, {}) if isinstance(all_resolutions, dict) else {}
                if not saved:
                    return ""
                labels = {clean(key).upper(): clean(value) for key, value in dict(data.get("analysis_field_labels") or {}).items()}
                order = [clean(value).upper() for value in (data.get("analysis_field_order") or []) if clean(value)]
                if not order:
                    order = ["NAME", "FEEDER", "SMART", "TYPE", "IP"]
                parts = []
                for field in order:
                    record = saved.get(field) or {}
                    if clean(record.get("decision_type")):
                        parts.append(compact_resolution_text(record))
                        customer_comment = clean(record.get("customer_comment"))
                        if customer_comment:
                            parts.append(f"{labels.get(field) or field} comment: {customer_comment}")
                return "\n".join(parts)

            emit(45, "Filtering configured equipment review")
            shown = []
            for data in rows:
                review_key = clean(data.get("review_key") or data.get("rmu"))
                state = analysis_review_state(data)
                review_record = review_map.get(review_key, {})
                review_status = rmu_review_display_status(data, review_record)
                if review_filter != "ALL REVIEWS" and review_status != review_filter:
                    continue
                if not analysis_filter_match(data):
                    continue
                resolution_summary = resolution_summary_for(review_key, data)
                manual_review_comment = clean(review_record.get("manual_comment"))
                review_text = resolution_summary if state.issue_count > 0 else manual_review_comment
                if search_field == "comments":
                    searchable = clean(review_text)
                elif search_field and search_field != "*":
                    searchable = clean(data.get(search_field))
                else:
                    searchable = " | ".join(clean(data.get(key)) for key in column_keys) + " | " + clean(review_text)
                if term_cf and term_cf not in searchable.casefold():
                    continue
                shown.append({
                    "data": data,
                    "review_status": review_status,
                    "state": state,
                    "resolution_summary": resolution_summary,
                    "manual_review_comment": manual_review_comment,
                    "resolution_display": review_text,
                })

            type_counts = Counter(clean(row.get("equipment_device_type")) or "UNCLASSIFIED" for row in rows)
            type_text = " · ".join(f"{key} {value}" for key, value in sorted(type_counts.items()))
            coverage_summary = dict((source_summary or {}).get("coverage") or {})
            coverage_text = " · ".join(
                f"{key} {value}" for key, value in sorted(coverage_summary.items(), reverse=True)
            ) or "No source coverage"
            label = "ALL EQUIPMENT" if profile_token == "__ALL__" else profile_token
            issue_rows = sum(analysis_review_state(row).issue_count > 0 for row in rows)
            pass_rows = sum(analysis_review_state(row).is_pass for row in rows)
            review_counts = Counter(
                rmu_review_display_status(row, review_map.get(clean(row.get("review_key") or row.get("rmu")), {}))
                for row in rows
            )
            summary_text = (
                f"{label} · Total {len(rows)} · Shown {len(shown)} · Pass {pass_rows} · With Issues {issue_rows} · "
                f"Unreviewed {review_counts.get('UNREVIEWED', 0)} · Closed {review_counts.get('CLOSED', 0)} · "
                f"Needs Action {review_counts.get('NEEDS ACTION', 0)} · Sources {coverage_text}"
            )
            if type_text and profile_token == "__ALL__":
                summary_text += " · " + type_text

            total_issue_decisions = resolved_issue_decisions = needs_action_decisions = 0
            for row in rows:
                review_key = clean(row.get("review_key") or row.get("rmu"))
                state = analysis_review_state(row)
                saved = all_resolutions.get(review_key, {}) if isinstance(all_resolutions, dict) else {}
                for field in state.false_fields:
                    total_issue_decisions += 1
                    decision = clean((saved.get(field) or {}).get("decision_type")).upper()
                    if decision:
                        resolved_issue_decisions += 1
                        if decision == "NEEDS_ACTION":
                            needs_action_decisions += 1
            resolution_pct = int(round((resolved_issue_decisions / total_issue_decisions * 100.0) if total_issue_decisions else 100.0))
            progress_text = (
                f"Resolution {resolved_issue_decisions} / {total_issue_decisions} issue decision(s) · {resolution_pct}% · "
                f"Unresolved {max(0, total_issue_decisions - resolved_issue_decisions)} · Needs Action {needs_action_decisions}"
            )
            emit(92, "Preparing equipment review rows")
            return {
                "mode": "equipment_review",
                "profile": profile_token,
                "rows": rows,
                "shown": shown,
                "review_map": review_map,
                "all_resolutions": all_resolutions,
                "action_tracking_keys": action_tracking_keys,
                "summary_text": summary_text,
                "progress_text": progress_text,
            }

        emit(8, "Reading cached RMU review rows")
        rows = store.rows()
        emit(28, "Loading RMU review decisions")
        review_map = store.rmu_review_map()
        all_resolutions = store.rmu_resolution_map()
        review_filter = clean(review_filter) or "ALL REVIEWS"
        analysis_filter = clean(analysis_filter) or "ALL ANALYSIS"

        def analysis_filter_match(data: dict) -> bool:
            if analysis_filter == "ALL ANALYSIS":
                return True
            state = analysis_review_state(data)
            false_keys = set(state.false_fields)
            if analysis_filter == "PASSED":
                return state.is_pass
            if analysis_filter == "ANY MISMATCH":
                return state.issue_count > 0
            if analysis_filter == "1 ISSUE":
                return state.issue_count == 1
            if analysis_filter == "2 ISSUES":
                return state.issue_count == 2
            if analysis_filter == "MULTIPLE ISSUES":
                return state.issue_count >= 3
            if analysis_filter == "CRITICAL":
                return state.is_critical
            if analysis_filter.endswith(" MISMATCH"):
                return analysis_filter.removesuffix(" MISMATCH") in false_keys
            return True

        def resolution_summary_for(rmu: str) -> str:
            saved = all_resolutions.get(rmu, {}) if isinstance(all_resolutions, dict) else {}
            parts = []
            for field in ("NAME", "FEEDER", "SMART", "TYPE", "IP"):
                record = saved.get(field) or {}
                if clean(record.get("decision_type")):
                    parts.append(compact_resolution_text(record))
                    customer_comment = clean(record.get("customer_comment"))
                    if customer_comment:
                        parts.append(f"{field} comment: {customer_comment}")
            return "\n".join(parts)

        emit(45, "Filtering RMU Data Review")
        shown = []
        for data in rows:
            rmu = clean(data.get("rmu"))
            state = analysis_review_state(data)
            review_record = review_map.get(rmu, {})
            review_status = rmu_review_display_status(data, review_record)
            if review_filter != "ALL REVIEWS" and review_status != review_filter:
                continue
            if not analysis_filter_match(data):
                continue
            resolution_summary = resolution_summary_for(rmu)
            manual_review_comment = clean(review_record.get("manual_comment"))
            review_text = resolution_summary if state.issue_count > 0 else manual_review_comment
            if search_field == "comments":
                searchable = clean(review_text)
            elif search_field and search_field != "*":
                searchable = clean(data.get(search_field))
            else:
                searchable = " | ".join(clean(data.get(key)) for key in column_keys) + " | " + clean(review_text)
            if term_cf and term_cf not in searchable.casefold():
                continue
            shown.append({
                "data": data,
                "review_status": review_status,
                "state": state,
                "resolution_summary": resolution_summary,
                "manual_review_comment": manual_review_comment,
                "resolution_display": review_text,
            })

        emit(68, "Calculating RMU review summary")
        analysis_fields = (
            ("analysis_name", "NAME"),
            ("analysis_feeder", "FEEDER"),
            ("analysis_smart", "SMART"),
            ("analysis_type", "TYPE"),
            ("analysis_ip", "IP"),
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
        summary_text = f"RMU · Total {len(rows)} · Shown {len(shown)} · {issue_text}"

        total_issue_decisions = 0
        resolved_issue_decisions = 0
        needs_action_decisions = 0
        for row in rows:
            rmu = clean(row.get("rmu"))
            state = analysis_review_state(row)
            saved = all_resolutions.get(rmu, {}) if isinstance(all_resolutions, dict) else {}
            for field in state.false_fields:
                total_issue_decisions += 1
                decision = clean((saved.get(field) or {}).get("decision_type")).upper()
                if decision:
                    resolved_issue_decisions += 1
                    if decision == "NEEDS_ACTION":
                        needs_action_decisions += 1
        resolution_pct = int(round((resolved_issue_decisions / total_issue_decisions * 100.0) if total_issue_decisions else 100.0))
        progress_text = (
            f"Resolution {resolved_issue_decisions} / {total_issue_decisions} issue decision(s) · {resolution_pct}% · "
            f"Unresolved {max(0, total_issue_decisions - resolved_issue_decisions)} · Needs Action {needs_action_decisions}"
        )
        emit(92, "Preparing RMU rows for display")
        return {
            "mode": "rmu",
            "profile": "RMU",
            "rows": rows,
            "shown": shown,
            "review_map": review_map,
            "all_resolutions": all_resolutions,
            "summary_text": summary_text,
            "progress_text": progress_text,
        }
    finally:
        store.close()


def _background_refresh_sources_job(
    project_folder: str, repository_root: str, site_name: str, progress=None
) -> dict:
    """Refresh active site sources off the GUI thread.

    v0.8.182 keeps the legacy snapshot synchronizer only for projects that have
    not adopted configurable Equipment Data Review.  Configurable sites read the
    live CSV/XLSX/XLSM files directly and never copy them into Project Data.
    """
    emit = progress or (lambda _value, _text: None)
    root = Path(repository_root)
    emit(5, "Scanning live source files")
    site = _load_repository_site(root, site_name, deep=True)
    store = ProjectStore(Path(project_folder))
    try:
        configurable = get_equipment_comparison_config(store, bootstrap=False)
        if configurable.get("sources"):
            emit(25, "Re-reading configured live Equipment Data Review files")
            changed_keys, _signature = configured_live_source_changes(store)
            rows, _summary = _build_active_equipment_review(store)
            # Replace the projection even when the live configuration currently
            # yields zero rows so stale data can never survive a source change.
            store.save_comparison(rows)
            remember_configured_live_source_metadata(store)
            store.config["validation_required_after_source_import"] = True
            store.save_config()
            emit(95, "Preparing refreshed direct-source view")
            return {
                "site": site,
                "changed_keys": list(changed_keys),
                "row_count": len(rows),
                "configurable_mode": True,
                "direct_read": True,
            }

        emit(25, "Comparing live source files with the last loaded snapshot")
        sync = sync_site_to_project(store, site)
        changed_keys = list(sync.changed_keys)
        rmu_sources = {"se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"}
        if changed_keys and set(changed_keys) & rmu_sources:
            emit(55, "Refreshing RMU data affected by changed sources")
            rows, _summary = _build_active_equipment_review(store)
            if rows:
                store.save_comparison(rows)
            row_count = len(rows)
        else:
            if changed_keys:
                emit(70, "Changed sources loaded; RMU data is unaffected")
            else:
                emit(70, "No source content changes detected")
            row_count = len(store.rows())
        if changed_keys:
            store.config["validation_required_after_source_import"] = True
            store.save_config()
        emit(95, "Preparing refreshed source view")
        return {
            "site": site,
            "changed_keys": changed_keys,
            "row_count": row_count,
            "configurable_mode": False,
            "direct_read": False,
        }
    finally:
        store.close()


def _background_validation_job(
    project_folder: str, repository_root: str, site_name: str, progress=None
) -> dict:
    """Run source sync + RMU + Signal validation on a worker thread.

    Only pure data/SQLite work runs here.  No QWidget is touched from the
    worker; the GUI consumes the returned summary on the main thread.
    """
    emit = progress or (lambda _value, _text: None)
    root = Path(repository_root)
    emit(5, "Scanning workspace and resolving active source files")
    site = _load_repository_site(root, site_name, deep=True)
    store = ProjectStore(Path(project_folder))
    try:
        configurable = get_equipment_comparison_config(store, bootstrap=False)
        configurable_mode = bool(configurable.get("sources"))

        if configurable_mode:
            # v0.8.180: Equipment Data Review now has a fully configurable
            # source contract. Do NOT run the legacy repository synchronizer
            # first: it validates SE/ZENON/ADMS files against the historical
            # fixed schemas and can reject a perfectly valid configured table
            # before the configurable comparison engine gets a chance to read
            # the user's selected Key / Index and comparison bindings.
            #
            # build_configurable_review() reads every configured CSV/XLSX/XLSM
            # directly, so this path still force re-reads the active equipment
            # files on every Run Validation.
            emit(20, "Re-reading configured Equipment Data Review source tables")
            sync = None
        else:
            emit(20, "Re-reading all active source files")
            sync = sync_site_to_project(store, site, force_all=True)

        emit(48, "Running Equipment Data Review validation")
        rows, _summary = _build_active_equipment_review(store)
        if not rows:
            raise RuntimeError("No valid migration records were found in the current site sources.")
        store.save_comparison(rows)
        if configurable_mode:
            # Record only path/stat metadata.  The workbook itself stays in the
            # site/user location and is never copied into Project Data.
            remember_configured_live_source_metadata(store)
        store.config["validation_required_after_source_import"] = False

        emit(65, "Running Signal Mapping validation")
        signal_report = None
        signal_matched = signal_mismatched = signal_zenon_extra = 0
        signal_standard_points = signal_adms_points = 0
        # Configurable Equipment Data Review must not force the unrelated
        # Signal Mapping inputs through the legacy equipment-source importer.
        # Resolve the same live IOA/ADMS-SLD files the Signal Mapping module
        # itself uses. Legacy projects keep the original snapshot behavior.
        if configurable_mode:
            ioa_path = _worker_effective_source_path(site, store, "ioa")
            adms_sld_path = _worker_effective_source_path(site, store, "adms_sld")
        else:
            ioa_path = store.source_path("ioa")
            adms_sld_path = store.source_path("adms_sld")
        standard_path = standard_reference_path()
        if ioa_path and adms_sld_path and standard_path.exists():
            signal_report = build_signal_mapping_report(
                ioa_path, adms_sld_path, standard_path,
                ioa_overrides=store.source_column_overrides("ioa"),
                adms_sld_overrides=store.source_column_overrides("adms_sld"),
                standard_overrides=store.source_column_overrides("standard_reference"),
                ioa_sheet_name=store.source_sheet_name("ioa") if hasattr(store, "source_sheet_name") else None,
                adms_sld_sheet_name=store.source_sheet_name("adms_sld") if hasattr(store, "source_sheet_name") else None,
            )
            fingerprints = {
                item.row_key: {
                    "row_hash": signal_review_row_hash(item, signal_report.analysis_column),
                    "source_hash": signal_report.source_hash,
                }
                for item in signal_report.rows
            }
            store.sync_db_smart_review_fingerprints(
                fingerprints, modified_by="SYSTEM",
                aliases=signal_review_alias_map(signal_report),
                metadata={item.row_key: signal_review_metadata(signal_report, item) for item in signal_report.rows},
            )
            if signal_report.analysis_column is not None:
                for item in signal_report.rows:
                    result = clean(item.values[signal_report.analysis_column]).upper()
                    signal_matched += result == "TRUE"
                    signal_mismatched += result == "FALSE"
            signal_zenon_extra = sum(signal_row_is_zenon_only(item) for item in signal_report.rows)
            value_index = {key: i for i, (key, _label, _width) in enumerate(signal_report.columns)}
            standard_dot_index = value_index.get("standard_dot_no")
            adms_dot_index = value_index.get("adms_dot_no")
            signal_standard_points = sum(
                standard_dot_index is not None
                and standard_dot_index < len(item.values)
                and bool(clean(item.values[standard_dot_index]))
                for item in signal_report.rows
            )
            signal_adms_points = sum(
                adms_dot_index is not None
                and adms_dot_index < len(item.values)
                and bool(clean(item.values[adms_dot_index]))
                for item in signal_report.rows
            )

        emit(88, "Saving validation summary and review fingerprints")
        store.config["signal_validation_summary"] = {
            "total": int(signal_adms_points),
            "standard_points": int(signal_standard_points),
            "adms_points": int(signal_adms_points),
            "matched": int(signal_matched),
            "mismatched": int(signal_mismatched),
            "zenon_extra": int(signal_zenon_extra),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        store.save_config()

        emit(97, "Finalizing validation results")
        states = [analysis_review_state(row) for row in rows]
        issue_fields = Counter(field for state in states for field in state.false_fields)
        issue_field_labels: dict[str, str] = {}
        issue_field_order: list[str] = []
        for row in rows:
            labels = dict(row.get("analysis_field_labels") or {})
            for field_id in row.get("analysis_field_order") or ():
                field_id = clean(field_id)
                if not field_id:
                    continue
                issue_field_labels.setdefault(field_id, clean(labels.get(field_id)) or field_id)
                if field_id not in issue_field_order:
                    issue_field_order.append(field_id)
        return {
            "site": site,
            "configurable_mode": configurable_mode,
            "imported_count": len(sync.imported) if sync is not None else 0,
            "changed_keys": list(sync.changed_keys) if sync is not None else [],
            "snapshot_dir": str(sync.snapshot_dir) if sync is not None else "Live configured source files",
            "row_count": len(rows),
            "pass_count": sum(state.is_pass for state in states),
            "issue_count": sum(state.issue_count > 0 for state in states),
            "issue_fields": dict(issue_fields),
            "issue_field_labels": issue_field_labels,
            "issue_field_order": issue_field_order,
            "signal_report": signal_report,
            "signal_matched": int(signal_matched),
            "signal_mismatched": int(signal_mismatched),
            "signal_zenon_extra": int(signal_zenon_extra),
            "signal_standard_points": int(signal_standard_points),
            "signal_adms_points": int(signal_adms_points),
        }
    finally:
        store.close()


def _background_reload_live_sources_job(
    project_folder: str, repository_root: str, site_name: str, source_types, progress=None
) -> dict:
    """Re-read only the requested live source files and refresh affected derived data.

    This is the fast path used by Source File selection and the live metadata
    watcher. It deliberately does not deep-scan or hash unrelated source files.
    """
    emit = progress or (lambda _value, _text: None)
    keys = [clean(key) for key in source_types if clean(key)]
    if not keys:
        return {"site": None, "changed_keys": [], "row_count": 0, "signal_report": None}
    root = Path(repository_root)
    emit(5, "Resolving selected source file")
    site = _load_repository_site(root, site_name, deep=False)
    store = ProjectStore(Path(project_folder))
    try:
        manual_records = store.manual_source_overrides()
        loaded = []
        mapping_required: dict[str, dict] = {}
        total = max(1, len(keys))
        live_meta = dict(store.config.get("live_source_metadata", {}) or {})
        repository_fps = dict(store.config.get("repository_fingerprints", {}) or {})
        pending_source_mappings = dict(store.config.get("pending_source_mappings", {}) or {})
        for index, key in enumerate(keys):
            pct = 15 + int(index / total * 35)
            emit(pct, f"Reading {key} source")
            selected_repo = selected_repository_source_path(site, store, key)
            path = selected_repo
            manual_record = manual_records.get(key, {}) or {}
            manual_origin = str(manual_record.get("original_path") or "").strip()
            is_manual_external = False
            if path is None and manual_origin:
                candidate = Path(manual_origin)
                if candidate.exists() and candidate.is_file():
                    path = candidate
                    is_manual_external = True
            if path is None:
                candidate = site.sources.get(key)
                if candidate and Path(candidate).exists():
                    path = Path(candidate)
            if path is None or not Path(path).exists():
                # If a repository-managed source disappeared, deactivate only
                # that source role; archived copies remain available in history.
                if not is_manual_external:
                    store.clear_source(key)
                live_meta.pop(key, None)
                repository_fps.pop(key, None)
                loaded.append(key)
                continue
            path = Path(path)
            # Source File replacement is deliberately remap-first. A physical
            # table with renamed/new headers is staged instead of rejected so
            # the reviewer can immediately map App Columns to the new headers.
            imported = import_source(store, key, path, allow_unresolved_mapping=True)
            if imported.mapping_required:
                pending_record = {
                    "message": imported.mapping_message,
                    "headers": list(imported.detected_headers),
                    "source_name": path.name,
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                }
                mapping_required[key] = pending_record
                pending_source_mappings[key] = pending_record
            else:
                pending_source_mappings.pop(key, None)
            if is_manual_external:
                store.mark_manual_source_override(key, path)
                repository_fps.pop(key, None)
            try:
                stat = path.stat()
                live_meta[key] = {
                    "path": str(path.resolve()),
                    "size": int(stat.st_size),
                    "mtime_ns": int(stat.st_mtime_ns),
                }
                if not is_manual_external:
                    repository_fps[key] = fingerprint(path)
            except OSError:
                pass
            loaded.append(key)

        store.config["live_source_metadata"] = live_meta
        store.config["repository_fingerprints"] = repository_fps
        store.config["pending_source_mappings"] = pending_source_mappings
        store.config["repository_last_sync"] = datetime.now().isoformat(timespec="seconds")
        store.config["validation_required_after_source_import"] = True
        store.save_config()

        rmu_sources = {"se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"}
        signal_sources = {"ioa", "adms_sld"}
        row_count = len(store.rows())
        pending_keys = set(mapping_required)
        if set(keys) & rmu_sources and not (pending_keys & rmu_sources):
            emit(58, "Refreshing affected RMU review data")
            rows, _summary = _build_active_equipment_review(store)
            if rows:
                store.save_comparison(rows)
            row_count = len(rows)
        elif pending_keys & rmu_sources:
            emit(58, "Source staged · field mapping required before RMU Analysis")

        signal_report = None
        if set(keys) & signal_sources and not (pending_keys & signal_sources):
            emit(76, "Refreshing affected Signal Mapping data")
            ioa_path = store.source_path("ioa")
            adms_sld_path = store.source_path("adms_sld")
            standard_path = standard_reference_path()
            if ioa_path and adms_sld_path and standard_path.exists():
                signal_report = build_signal_mapping_report(
                    ioa_path, adms_sld_path, standard_path,
                    ioa_overrides=store.source_column_overrides("ioa"),
                    adms_sld_overrides=store.source_column_overrides("adms_sld"),
                    standard_overrides=store.source_column_overrides("standard_reference"),
                    ioa_sheet_name=store.source_sheet_name("ioa") if hasattr(store, "source_sheet_name") else None,
                    adms_sld_sheet_name=store.source_sheet_name("adms_sld") if hasattr(store, "source_sheet_name") else None,
                )
                fingerprints = {
                    item.row_key: {
                        "row_hash": signal_review_row_hash(item, signal_report.analysis_column),
                        "source_hash": signal_report.source_hash,
                    }
                    for item in signal_report.rows
                }
                store.sync_db_smart_review_fingerprints(
                    fingerprints, modified_by="SYSTEM",
                    aliases=signal_review_alias_map(signal_report),
                    metadata={item.row_key: signal_review_metadata(signal_report, item) for item in signal_report.rows},
                )
        emit(95, "Updating application view")
        return {
            "site": site,
            "changed_keys": loaded,
            "row_count": row_count,
            "signal_report": signal_report,
            "mapping_required": mapping_required,
        }
    finally:
        store.close()


def _background_reload_configurable_live_sources_job(
    project_folder: str, repository_root: str, site_name: str, changed_keys, progress=None
) -> dict:
    """Re-read changed configurable sources directly from their live files.

    No source workbook/CSV is copied into Project Data.  Equipment changes
    rebuild only the dynamic Equipment Data Review projection; Signal Mapping
    changes rebuild the existing Signal Mapping report from its assigned live
    files.  Human review/lifecycle state remains persisted in project.db.
    """
    emit = progress or (lambda _value, _text: None)
    keys = [clean(key) for key in changed_keys if clean(key)]
    root = Path(repository_root)
    emit(5, "Resolving live configurable source paths")
    site = _load_repository_site(root, site_name, deep=False)
    store = ProjectStore(Path(project_folder))
    try:
        equipment_changed = any(key.startswith("equipment:") for key in keys)
        signal_changed = any(key.startswith("signal:") for key in keys)

        row_count = store.comparison_row_count()
        if equipment_changed:
            emit(28, "Re-reading changed Equipment Data Review files")
            rows, _summary = _build_active_equipment_review(store)
            store.save_comparison(rows)
            row_count = len(rows)

        signal_report = None
        if signal_changed:
            emit(62, "Re-reading changed Signal Mapping files")
            ioa_path = _worker_effective_source_path(site, store, "ioa")
            adms_sld_path = _worker_effective_source_path(site, store, "adms_sld")
            standard_path = standard_reference_path()
            if ioa_path and adms_sld_path and standard_path.exists():
                signal_report = build_signal_mapping_report(
                    ioa_path, adms_sld_path, standard_path,
                    ioa_overrides=store.source_column_overrides("ioa"),
                    adms_sld_overrides=store.source_column_overrides("adms_sld"),
                    standard_overrides=store.source_column_overrides("standard_reference"),
                    ioa_sheet_name=store.source_sheet_name("ioa") if hasattr(store, "source_sheet_name") else None,
                    adms_sld_sheet_name=store.source_sheet_name("adms_sld") if hasattr(store, "source_sheet_name") else None,
                )
                fingerprints = {
                    item.row_key: {
                        "row_hash": signal_review_row_hash(item, signal_report.analysis_column),
                        "source_hash": signal_report.source_hash,
                    }
                    for item in signal_report.rows
                }
                store.sync_db_smart_review_fingerprints(
                    fingerprints, modified_by="SYSTEM",
                    aliases=signal_review_alias_map(signal_report),
                    metadata={item.row_key: signal_review_metadata(signal_report, item) for item in signal_report.rows},
                )

        # Reset the watcher baseline only after the new live contents were read
        # successfully.  This prevents a failed/locked workbook from being
        # silently accepted as the new baseline.
        remember_configured_live_source_metadata(store)
        store.config["validation_required_after_source_import"] = True
        store.save_config()
        emit(95, "Updating direct-source review view")
        return {
            "site": site,
            "changed_keys": keys,
            "row_count": row_count,
            "signal_report": signal_report,
            "direct_read": True,
        }
    finally:
        store.close()


def _background_equipment_check_batch_job(
    project_folder: str, updates: list[tuple[str, bool]], modified_by: str
) -> dict:
    """Persist manual Equipment checks on a worker connection in one transaction."""
    store = ProjectStore(Path(project_folder))
    try:
        saved: list[tuple[str, bool]] = []
        for review_key, checked in updates:
            key = clean(review_key)
            if not key:
                continue
            store.update_rmu_check_passed(
                key, bool(checked), modified_by,
                reason="Equipment manually checked / passed in Row Locator",
                _commit=False,
            )
            saved.append((key, bool(checked)))
        store.db.commit()
        return {"saved": saved, "count": len(saved)}
    finally:
        store.close()


def _background_review_status_batch_job(
    project_folder: str, updates: list[tuple[str, str, str]], modified_by: str
) -> dict:
    """Persist Equipment Review statuses on a worker connection in one transaction.

    Review-status changes are a high-frequency reviewer interaction.  Keep the
    GUI optimistic and responsive: the visible row/cache is patched first,
    while this worker serializes the durable SQLite/lifecycle writes.
    """
    store = ProjectStore(Path(project_folder))
    try:
        saved: list[tuple[str, str]] = []
        for review_key, status, reason in updates:
            key = clean(review_key)
            if not key:
                continue
            normalized = normalize_review_status(status)
            store.update_rmu_review_status(
                key, normalized, modified_by, reason=clean(reason), _commit=False
            )
            saved.append((key, normalized))
        store.db.commit()
        return {"saved": saved, "count": len(saved)}
    finally:
        store.close()


def _background_excel_export_job(project_folder: str, target_path: str) -> str:
    """Build the formal workbook off the Qt GUI thread."""
    store = ProjectStore(Path(project_folder))
    try:
        return str(export_report(store, target_path=Path(target_path)))
    finally:
        store.close()


def _background_resolution_save_job(
    project_folder: str, rmu: str, row_data: dict, decisions: dict, modified_by: str
) -> dict:
    """Persist one RMU's structured resolutions without blocking Qt."""
    store = ProjectStore(Path(project_folder))
    try:
        review_status, summary = store.save_rmu_resolution_decisions(
            rmu, row_data, decisions, modified_by
        )
        tracking = store.rmu_action_tracking_counts()
        return {
            "rmu": rmu,
            "review_status": review_status,
            "summary": summary,
            "tracking": tracking,
        }
    finally:
        store.close()


def _background_mapping_refresh_job(
    project_folder: str, repository_root: str, site_name: str, source_type: str, progress=None
) -> dict:
    """Apply one saved Map Fields configuration and rebuild only affected data.

    Mapping persistence itself happens immediately in the dialog.  This worker
    performs the potentially slow source re-read / comparison rebuild away from
    the Qt GUI process so the Save action always has a continuously animated
    liveness indicator.
    """
    emit = progress or (lambda _value, _text: None)
    source_type = clean(source_type)
    if source_type != "standard_reference":
        return _background_reload_live_sources_job(
            project_folder, repository_root, site_name, [source_type], progress=emit
        )

    # STANDARD is application-managed rather than a site repository source.
    # Rebuild Signal Mapping with the newly saved global STANDARD mapping while
    # keeping the active site and all persisted human review records intact.
    emit(10, "Loading active site after mapping save")
    root = Path(repository_root)
    site = _load_repository_site(root, site_name, deep=False)
    store = ProjectStore(Path(project_folder))
    try:
        emit(45, "Rebuilding Signal Mapping with saved field mapping")
        signal_report = None
        ioa_path = store.source_path("ioa")
        adms_sld_path = store.source_path("adms_sld")
        standard_path = standard_reference_path()
        if ioa_path and adms_sld_path and standard_path.exists():
            signal_report = build_signal_mapping_report(
                ioa_path, adms_sld_path, standard_path,
                ioa_overrides=store.source_column_overrides("ioa"),
                adms_sld_overrides=store.source_column_overrides("adms_sld"),
                standard_overrides=store.source_column_overrides("standard_reference"),
                ioa_sheet_name=store.source_sheet_name("ioa") if hasattr(store, "source_sheet_name") else None,
                adms_sld_sheet_name=store.source_sheet_name("adms_sld") if hasattr(store, "source_sheet_name") else None,
            )
            fingerprints = {
                item.row_key: {
                    "row_hash": signal_review_row_hash(item, signal_report.analysis_column),
                    "source_hash": signal_report.source_hash,
                }
                for item in signal_report.rows
            }
            store.sync_db_smart_review_fingerprints(
                fingerprints, modified_by="SYSTEM",
                aliases=signal_review_alias_map(signal_report),
                metadata={item.row_key: signal_review_metadata(signal_report, item) for item in signal_report.rows},
            )
        store.config["validation_required_after_source_import"] = True
        store.save_config()
        emit(95, "Updating application view")
        return {
            "site": site,
            "changed_keys": [source_type],
            "row_count": len(store.rows()),
            "signal_report": signal_report,
        }
    finally:
        store.close()


def _launch_review_process(job_name: str, args: tuple):
    """Create and start one review worker process outside the Qt GUI thread.

    On Windows/PyInstaller, ``Process.start()`` itself may take noticeable time
    while a spawned interpreter is created.  Calling it on the GUI thread makes
    an already-visible progress bar appear frozen before the child even begins
    useful work.  This helper is therefore invoked by a QThreadPool launcher; it
    returns the live Process and Queue to the GUI only after spawning completes.
    """
    ctx = mp.get_context("spawn")
    message_queue = ctx.Queue()
    process = ctx.Process(
        target=_background_process_job_entry,
        args=(job_name, tuple(args), message_queue),
        daemon=True,
        name=f"MigrationReportTool-{job_name}",
    )
    try:
        process.start()
    except Exception:
        try:
            message_queue.close()
            message_queue.cancel_join_thread()
        except Exception:
            pass
        raise
    return process, message_queue


def _background_process_job_entry(job_name: str, args: tuple, message_queue) -> None:
    """Run one CPU-heavy review preparation job in a separate process.

    QThreadPool remains the right default for small I/O/database jobs, but the
    first RMU/Signal review build can spend long stretches in Python parsing and
    comparison code.  A Python thread still shares the GIL with the Qt GUI
    process, which can make the progress animation look stalled on large sites.
    These two first-open review jobs therefore use a spawned child process.

    Only plain Python/domain objects cross the queue; no QWidget/QObject is ever
    created or touched in the worker process.
    """
    jobs = {
        "module-rmu-load": _background_rmu_review_module_job,
        "module-signal-load": _background_signal_mapping_module_job,
        "mapping-refresh": _background_mapping_refresh_job,
        "rmu-render-prepare": _background_rmu_render_prepare_job,
    }
    try:
        fn = jobs[job_name]

        def emit(value: int, text: str) -> None:
            message_queue.put(("progress", int(value), clean(text)))

        result = fn(*args, progress=emit)
        message_queue.put(("success", result))
    except Exception:
        message_queue.put(("failed", traceback.format_exc()))
    finally:
        # Sentinel lets the GUI distinguish a normally drained queue from a
        # process that vanished before publishing a result.
        try:
            message_queue.put(("done",))
        except Exception:
            pass


# DATA sheet inspired header palette. The layout mirrors the customer's
# two-row A:BB header while keeping the rest of the desktop UI modern.
REPORT_HEADER_COLORS = {
    # Table header color communicates hierarchy only. Business/status colors
    # are reserved for table data (row state and FALSE analysis cells).
    "Index": ("#E8EDF3", "#F4F6F8", "#24364B"),
    "RMU": ("#E8EDF3", "#F4F6F8", "#24364B"),
    # Physical source blocks use deliberately subtle, low-saturation tints.
    # The tint is only a navigational cue; row/analysis status colors remain primary.
    "SE": ("#EEF3F7", "#F8FAFC", "#24364B"),
    "ZENON DB": ("#EEF5F5", "#F8FBFB", "#24364B"),
    "ZENON SLD": ("#EFF4F8", "#F9FBFC", "#24364B"),
    "ADMS DB": ("#F4F2EE", "#FBFAF8", "#24364B"),
    "ADMS SLD": ("#F0F5F1", "#F9FBF9", "#24364B"),
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
            source_groups = {"SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"}
            # Physical source blocks and Analysis field tokens are engineering
            # contracts and stay English. UI/meta columns (Index, Source
            # Coverage, Row Locator, Remarks, Resolution...) follow the selected
            # interface language.
            display_label = label if group in source_groups or group == "Analysis" else ui_tr(label, current_language())
            painter.drawText(bottom_rect.adjusted(5, 2, -5, -2), Qt.AlignCenter | Qt.TextWordWrap, display_label)

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
            source_groups = {"SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"}
            display_group = group if group in source_groups else ui_tr(group, current_language())
            painter.drawText(rect.adjusted(6, 2, -6, -2), Qt.AlignCenter | Qt.TextWordWrap, display_group)

        # Light source-block boundaries: enough structure to identify the five
        # physical sources without competing with mismatch/status highlights.
        source_groups = {"SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"}
        painter.setPen(QPen(QColor("#D5DEE7"), 1))
        for group, start, end in self._group_ranges:
            if group not in source_groups:
                continue
            visible = [i for i in range(start, end + 1) if not self.isSectionHidden(i)]
            if not visible:
                continue
            left = self.sectionViewportPosition(visible[0])
            right = self.sectionViewportPosition(visible[-1]) + self.sectionSize(visible[-1])
            if -2 <= left <= self.viewport().width() + 2:
                painter.drawLine(left, 0, left, self.height())
            if -2 <= right <= self.viewport().width() + 2:
                painter.drawLine(right, 0, right, self.height())

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
    """Paint selection as an outline without touching business/status fills.

    Qt normally paints selected cells with the palette Highlight brush, which
    can hide the application's Pass / Issue / Unreviewed / Closed / Needs Action
    colors.  This delegate deliberately removes State_Selected while the base
    item is painted, then draws only the *outer perimeter* of the selected
    cells.  Adjacent selected cells share no internal blue borders, so a
    Ctrl/Shift multi-row block reads as one selection rectangle while every
    underlying business color remains visible.
    """

    SELECTION_COLOR = QColor("#2F80ED")

    def __init__(self, table, parent=None):
        super().__init__(parent or table)
        self.table = table

    def _selected(self, row: int, column: int) -> bool:
        if row < 0 or column < 0:
            return False
        if row >= self.table.rowCount() or column >= self.table.columnCount():
            return False
        model = self.table.selectionModel()
        if model is None:
            return False
        return model.isSelected(self.table.model().index(row, column))

    def paint(self, painter, option, index):
        selected = bool(option.state & QStyle.State_Selected)

        # Paint the real item first with State_Selected removed.  This is the
        # key guarantee that selection can never replace status/background
        # colors, including dark Closed cells and yellow/red analysis
        # cells.
        base_option = QStyleOptionViewItem(option)
        if selected:
            base_option.state &= ~QStyle.State_Selected
        super().paint(painter, base_option, index)

        if not selected:
            return

        row, column = index.row(), index.column()
        top_edge = not self._selected(row - 1, column)
        bottom_edge = not self._selected(row + 1, column)
        left_edge = not self._selected(row, column - 1)
        right_edge = not self._selected(row, column + 1)

        # Only draw boundaries exposed to a non-selected neighbour.  This
        # removes the old blue stripe between every selected row/cell and leaves
        # one clean outline around each contiguous selection block.
        painter.save()
        painter.setPen(QPen(self.SELECTION_COLOR, 2))
        rect = option.rect.adjusted(0, 0, -1, -1)
        if top_edge:
            painter.drawLine(rect.topLeft(), rect.topRight())
        if bottom_edge:
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
        if left_edge:
            painter.drawLine(rect.topLeft(), rect.bottomLeft())
        if right_edge:
            painter.drawLine(rect.topRight(), rect.bottomRight())
        painter.restore()


class SpreadsheetTableWidget(QTableWidget):
    """QTableWidget with persistent Excel-like selection and row tracking.

    - Drag: select a rectangular block.
    - Ctrl+click/drag: add or remove non-contiguous cells/ranges.
    - Shift: extend from the current anchor.
    - Frozen Row Locator clicks select complete business rows; Ctrl/Shift follow
      normal spreadsheet multi-selection semantics.
    - Selection survives scrollbar dragging and clicks outside the grid.
    - Clear Selection is explicit so review actions never lose a chosen set.
    - Selection is rendered only as the outer blue perimeter of each selected
      block; adjacent selected rows/cells do not get internal blue stripes.

    Selection never replaces business/status background or foreground colors.
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
        # The current delegate does not paint a hover-row overlay. Updating the
        # whole viewport here caused a full repaint on every mouse move and made
        # 1,000+ row review grids feel sluggish. Keep the logical tracking value
        # for frozen-view synchronization without forcing a repaint.
        self.tracked_hover_row = row

    def set_tracked_active_row(self, row: int) -> None:
        row = int(row) if row is not None else -1
        if self.tracked_active_row == row:
            return
        # Active-row state is also logical only; selection painting is handled
        # by RowTrackingDelegate from the selection model itself.
        self.tracked_active_row = row

    def _on_current_cell_changed(self, current_row: int, _current_col: int, _previous_row: int, _previous_col: int) -> None:
        row = current_row if current_row >= 0 else -1
        self.set_tracked_active_row(row)
        self.activeRowChanged.emit(row)

    def clear_spreadsheet_selection(self) -> None:
        self.clearSelection()
        self.setCurrentIndex(QModelIndex())
        self.set_tracked_active_row(-1)
        self.activeRowChanged.emit(-1)

    def set_source_group_boundaries(self, groups, source_groups=None) -> None:
        """Draw subtle vertical separators around each physical source block.

        Source boundaries are intentionally only slightly stronger than the normal
        grid. Combined with the softly tinted group headers, they identify
        SE / ZENON DB / ZENON SLD / ADMS DB / ADMS SLD without drawing attention
        away from actual mismatch and review-state colors.
        """
        source_groups = set(source_groups or {"SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"})
        boundaries = set()
        cursor = 0
        for group, _color, columns in groups or ():
            count = len(columns or ())
            if group in source_groups and count:
                boundaries.add(cursor)
                boundaries.add(cursor + count)
            cursor += count
        self._source_group_boundaries = sorted(boundaries)
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        boundaries = getattr(self, "_source_group_boundaries", ())
        if not boundaries:
            return
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor("#D5DEE7"), 1))
        height = self.viewport().height()
        for boundary in boundaries:
            if boundary <= 0:
                continue
            if boundary >= self.columnCount():
                if self.columnCount() <= 0:
                    continue
                x = self.columnViewportPosition(self.columnCount() - 1) + self.columnWidth(self.columnCount() - 1)
            else:
                x = self.columnViewportPosition(boundary)
            if -2 <= x <= self.viewport().width() + 2:
                painter.drawLine(x, 0, x, height)
        painter.end()

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
                # Empty-space clicks must not destroy a deliberate review
                # selection. Use the explicit Clear Selection action instead.
                event.accept()
                return
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
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)
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


class RMUReviewCommentDialog(QDialog):
    """Append a new RMU review comment without editing prior history.

    The latest saved comment is intentionally read-only.  The default editor is
    blank so opening the dialog can never erase or silently modify a previous
    review note.  Reviewers can either add a completely new note or copy the
    latest note into the new editor and continue from it.  Every accepted Save
    creates a new immutable review-history event.
    """

    def __init__(self, rmu: str, latest_comment: str, history_events: list[dict], parent=None, equipment_type: str = "RMU"):
        super().__init__(parent)
        self.rmu = clean(rmu)
        self.equipment_type = clean(equipment_type).upper() or "RMU"
        self.latest_comment = str(latest_comment or "").strip()
        self.history_events = [dict(item or {}) for item in (history_events or [])]

        self.setWindowTitle(f"{self.equipment_type} {self.rmu} Review Comments")
        self.resize(760, 650 if self.history_events else 500)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        title = QLabel(f"{self.equipment_type} {self.rmu} · Add Review Comment")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        desc = QLabel(
            "Previous comments are immutable. Add a new comment below, or use Continue from Latest to copy the latest saved text into the new editor and extend it. "
            "Opening or cancelling this dialog never changes an existing comment."
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        history_label = QLabel(f"Review Comment History · {len(self.history_events)} record(s)")
        history_label.setStyleSheet("font-weight:700;color:#334A5E;")
        layout.addWidget(history_label)

        if self.history_events:
            self.history_table = QTableWidget(len(self.history_events), 4)
            self.history_table.setHorizontalHeaderLabels(["Time", "Status", "Comment", "User"])
            self.history_table.verticalHeader().setVisible(False)
            self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
            self.history_table.setWordWrap(True)
            self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
            self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
            self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
            self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
            self.history_table.setColumnWidth(0, 165)
            self.history_table.setColumnWidth(1, 105)
            self.history_table.setColumnWidth(3, 105)
            self.history_table.setMinimumHeight(145)
            self.history_table.setMaximumHeight(220)
            for row, event in enumerate(self.history_events):
                values = [
                    clean(event.get("modified_at")),
                    clean(event.get("review_status")) or "UNREVIEWED",
                    clean(event.get("comment")) or "—",
                    clean(event.get("modified_by")),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(value)
                    self.history_table.setItem(row, col, item)
                self.history_table.setRowHeight(row, 38)
            layout.addWidget(self.history_table)
        else:
            none = QLabel("No previous equipment review comment has been recorded.")
            none.setObjectName("Muted")
            none.setStyleSheet("QLabel { background:#F7FAFC;border:1px solid #E2E8F0;border-radius:6px;padding:10px; }")
            layout.addWidget(none)

        latest_header = QHBoxLayout()
        latest_label = QLabel("Latest Saved Comment (read-only)")
        latest_label.setStyleSheet("font-weight:700;color:#52697A;")
        latest_header.addWidget(latest_label)
        latest_header.addStretch()
        self.continue_btn = QPushButton("Continue from Latest")
        self.continue_btn.setEnabled(bool(self.latest_comment))
        self.continue_btn.setToolTip("Copy the latest saved comment into the New Review Comment editor. The saved history is not changed until you save a new comment.")
        latest_header.addWidget(self.continue_btn)
        layout.addLayout(latest_header)

        self.latest_view = QTextEdit()
        self.latest_view.setReadOnly(True)
        self.latest_view.setPlainText(self.latest_comment or "No saved comment")
        self.latest_view.setFixedHeight(76)
        self.latest_view.setStyleSheet(
            "QTextEdit { background:#F7FAFC; border:1px solid #DCE5EC; border-radius:6px; padding:7px 9px; color:#52697A; }"
        )
        layout.addWidget(self.latest_view)

        new_label = QLabel("New Review Comment")
        new_label.setStyleSheet("font-weight:800;color:#243B4A;margin-top:4px;")
        layout.addWidget(new_label)
        self.new_comment_edit = QTextEdit()
        self.new_comment_edit.setPlaceholderText(
            "Enter a new review comment. Save adds one new history record; it never edits or deletes an earlier comment."
        )
        self.new_comment_edit.setMinimumHeight(120)
        self.new_comment_edit.setStyleSheet(
            "QTextEdit { background:#FFFFFF; border:1px solid #9FB6C8; border-radius:6px; padding:7px 9px; color:#243B4A; }"
        )
        layout.addWidget(self.new_comment_edit, 1)

        helper = QLabel(
            "Tip: use Continue from Latest when the new review is an extension of the previous note. Use a blank New Review Comment only to cancel—blank Save is blocked so prior text cannot be accidentally cleared."
        )
        helper.setObjectName("Muted")
        helper.setWordWrap(True)
        layout.addWidget(helper)

        self.continue_btn.clicked.connect(self._continue_from_latest)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        save = buttons.button(QDialogButtonBox.Save)
        save.setText("Add Comment")
        save.setObjectName("Primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.new_comment_edit.setFocus()

    def _continue_from_latest(self) -> None:
        if not self.latest_comment:
            return
        current = self.new_comment_edit.toPlainText().strip()
        if current:
            answer = QMessageBox.question(
                self,
                "Replace Draft?",
                "The New Review Comment editor already contains text. Replace the draft with the latest saved comment?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.new_comment_edit.setPlainText(self.latest_comment)
        cursor = self.new_comment_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.new_comment_edit.setTextCursor(cursor)
        self.new_comment_edit.setFocus()

    def accept(self) -> None:
        if not self.comment():
            QMessageBox.information(
                self,
                "New Comment Required",
                "Enter a new Review comment before saving. Existing comments are read-only and remain unchanged.",
            )
            self.new_comment_edit.setFocus()
            return
        super().accept()

    def comment(self) -> str:
        return self.new_comment_edit.toPlainText().strip()


class RMUResolutionDialog(QDialog):
    """One structured, customer-facing decision for every active RMU issue.

    The selector remains structured, but the selected action is also rendered as
    a complete sign-off sentence so the reviewer sees exactly what will be frozen
    into the audit trail and formal PDF.
    """

    FIELD_ORDER = ("NAME", "FEEDER", "SMART", "TYPE", "IP")

    def _analysis_value_key(self, field: str) -> str:
        key = clean(self._field_value_keys.get(clean(field).upper()))
        if key:
            return key
        original = self._field_original.get(clean(field).upper(), clean(field))
        return f"analysis_{clean(original).lower()}"

    def _analysis_detail(self, field: str) -> str:
        key = self._analysis_value_key(field)
        return clean(self.row_data.get(f"{key}__detail") or self.row_data.get(f"{key}_detail"))

    def _field_label(self, field: str) -> str:
        return clean(self._field_labels.get(clean(field).upper())) or clean(field)

    def _field_candidates(self, field: str) -> list[dict]:
        wanted = clean(field).upper()
        for key, value in dict(self.row_data.get("resolution_candidates") or {}).items():
            if clean(key).upper() == wanted:
                return list(value or [])
        return []

    def __init__(self, rmu: str, row_data: dict, current_resolutions: dict, parent=None, equipment_type: str = "RMU"):
        super().__init__(parent)
        self.rmu = clean(rmu)
        self.equipment_type = clean(equipment_type).upper() or "RMU"
        self.row_data = row_data or {}
        self.current_resolutions = current_resolutions or {}
        configured_order = [clean(value) for value in (self.row_data.get("analysis_field_order") or []) if clean(value)]
        self._field_original = {value.upper(): value for value in configured_order}
        self._field_labels = {clean(key).upper(): clean(value) for key, value in dict(self.row_data.get("analysis_field_labels") or {}).items()}
        self._field_value_keys = {clean(key).upper(): clean(value) for key, value in dict(self.row_data.get("analysis_field_keys") or {}).items()}
        field_order = [value.upper() for value in configured_order] if configured_order else list(self.FIELD_ORDER)
        self.issue_fields = [
            field for field in field_order
            if clean(self.row_data.get(self._analysis_value_key(field))).upper() == "FALSE"
        ]
        self.combos: dict[str, QComboBox] = {}
        self.previews: dict[str, QLabel] = {}
        self.other_comments: dict[str, QTextEdit] = {}
        self.customer_comments: dict[str, QTextEdit] = {}
        self.customer_existing_comments: dict[str, str] = {}
        self.issue_snapshots: dict[str, dict] = {}

        self.setWindowTitle(f"Resolve {self.equipment_type} {self.rmu} Issues")
        self.resize(1380, min(900, 360 + max(1, len(self.issue_fields)) * 205))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)

        title = QLabel(
            f"{self.equipment_type} {self.rmu} · {len(self.issue_fields)} issue{'s' if len(self.issue_fields) != 1 else ''} "
            f"require {len(self.issue_fields)} Resolution decision{'s' if len(self.issue_fields) != 1 else ''}"
        )
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        if configured_order:
            resolution_help = (
                "Choose one resolution for each FALSE configured Analysis field. Customer Comments are optional and independent from the Resolution choice; "
                "changing a comment never changes Analysis or the selected Resolution. Both the latest comment and every historical comment change are retained. "
                "Resolution choices record the agreed handling only and never change Review Status. Use the separate Review Status control to mark Needs Action, Closed, or Unreviewed. A Needs Action item stays open until a reviewer explicitly changes its Review Status."
            )
        else:
            resolution_help = (
                "Choose one resolution for each FALSE Analysis field. Customer Comments are optional and independent from the Resolution choice; "
                "changing a comment never changes Analysis or the selected Resolution. Both the latest comment and every historical comment change are retained. "
                "Resolution choices record the agreed handling only and never change Review Status. Choosing a value equal to ADMS DB does not close the equipment, and choosing a different source does not open it automatically. "
                "Use the separate Review Status control to mark Needs Action, Closed, or Unreviewed."
            )
        desc = QLabel(resolution_help)
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        table = QTableWidget(len(self.issue_fields), 3)
        table.setHorizontalHeaderLabels(["Issue", "Source Values from Validation", "Customer Resolution / Agreed Action"])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.setColumnWidth(0, 120)
        table.setColumnWidth(2, 650)
        table.horizontalHeader().setMinimumHeight(42)

        # Building multiple nested cell widgets can trigger repeated geometry
        # calculations. Freeze painting until the dialog is fully populated.
        table.setUpdatesEnabled(False)
        for row_index, field in enumerate(self.issue_fields):
            field_label = self._field_label(field)
            issue_item = QTableWidgetItem(field_label)
            font = issue_item.font(); font.setBold(True); issue_item.setFont(font)
            issue_item.setTextAlignment(Qt.AlignCenter)
            issue_item.setBackground(QColor("#F7D7D7"))
            issue_item.setToolTip(self._analysis_detail(field))
            table.setItem(row_index, 0, issue_item)

            candidates = self._field_candidates(field)
            source_lines = []
            for candidate in candidates:
                source = clean(candidate.get("source"))
                raw = clean(candidate.get("value"))
                normalized = clean(candidate.get("normalized"))
                line = f"{source}: {raw or '<blank>'}"
                if normalized and normalized != raw:
                    line += f"  →  {normalized}"
                source_lines.append(line)
            values_item = QTableWidgetItem("\n".join(source_lines) or "No selectable source value is available")
            values_item.setToolTip(self._analysis_detail(field))
            table.setItem(row_index, 1, values_item)

            self.issue_snapshots[field] = {
                "analysis_field": field,
                "analysis_label": field_label,
                "analysis_result": clean(self.row_data.get(self._analysis_value_key(field))),
                "analysis_detail": self._analysis_detail(field),
                "source_values": [dict(candidate or {}) for candidate in candidates],
            }

            cell = QWidget()
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(8, 7, 8, 7)
            cell_layout.setSpacing(6)
            combo = QComboBox()
            combo.setToolTip(f"Select exactly one Resolution for {field_label}")
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(34)
            combo.setMaxVisibleItems(12)
            combo.addItem("Unresolved", None)
            # Cross-source mismatches allow the reviewer to choose the authoritative source.
            for candidate in candidates:
                source = clean(candidate.get("source"))
                raw = clean(candidate.get("value"))
                normalized = clean(candidate.get("normalized"))
                description = build_resolution_description(
                    rmu=self.rmu, field=field_label, decision_type="USE_SOURCE",
                    selected_source=source, selected_value=raw, normalized_value=normalized,
                    equipment_type=self.equipment_type,
                )
                combo.addItem(
                    f"Use {source} · {raw or normalized or '<blank>'}",
                    {
                        "decision_type": "USE_SOURCE",
                        "selected_source": source,
                        "selected_value": raw,
                        "normalized_value": normalized,
                        "decision_description": description,
                    },
                )
            needs_action_description = build_resolution_description(
                rmu=self.rmu, field=field_label, decision_type="NEEDS_ACTION", equipment_type=self.equipment_type
            )
            combo.addItem(
                "Needs Action · correction required",
                {"decision_type": "NEEDS_ACTION", "decision_description": needs_action_description},
            )
            exception_description = build_resolution_description(
                rmu=self.rmu, field=field_label, decision_type="ACCEPT_EXCEPTION", equipment_type=self.equipment_type
            )
            combo.addItem(
                "Accept Exception · no source correction",
                {"decision_type": "ACCEPT_EXCEPTION", "decision_description": exception_description},
            )
            combo.addItem(
                "Others · custom resolution",
                {"decision_type": "OTHER"},
            )

            preview = QLabel()
            preview.setWordWrap(True)
            preview.setObjectName("Muted")
            preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
            # Keep the cell geometry stable when the combo changes. A wrapping
            # QLabel with a changing sizeHint caused Qt to relayout the whole
            # QTableWidget on every Resolution click.
            preview.setMinimumHeight(66)
            preview.setMaximumHeight(78)
            preview.setStyleSheet(
                "QLabel { background:#F7FAFC; border:1px solid #D6E1EA; border-radius:6px; "
                "padding:7px 9px; color:#334A5E; }"
            )

            other_comment = QTextEdit()
            other_comment.setPlaceholderText("Enter the agreed custom Resolution value / instruction...")
            other_comment.setFixedHeight(72)
            other_comment.setVisible(False)
            other_comment.setStyleSheet(
                "QTextEdit { background:#FFFFFF; border:1px solid #8FB7C9; border-radius:6px; "
                "padding:6px 8px; color:#243B4A; }"
            )

            current_for_comment = self.current_resolutions.get(field) or {}
            existing_customer_comment = clean(current_for_comment.get("customer_comment"))
            self.customer_existing_comments[field] = existing_customer_comment

            previous_comment_label = QLabel("Latest Customer Comment (read-only)")
            previous_comment_label.setStyleSheet("font-weight:700;color:#6B7F8E;margin-top:2px;")
            previous_comment_label.setVisible(bool(existing_customer_comment))
            previous_comment_row = QWidget()
            previous_comment_row_layout = QHBoxLayout(previous_comment_row)
            previous_comment_row_layout.setContentsMargins(0, 0, 0, 0)
            previous_comment_row_layout.setSpacing(6)
            previous_comment_view = QLabel(existing_customer_comment)
            previous_comment_view.setWordWrap(True)
            previous_comment_view.setTextInteractionFlags(Qt.TextSelectableByMouse)
            previous_comment_view.setStyleSheet(
                "QLabel { background:#F7FAFC; border:1px solid #DCE5EC; border-radius:6px; "
                "padding:6px 8px; color:#52697A; }"
            )
            continue_comment_btn = QPushButton("Continue from Latest")
            continue_comment_btn.setToolTip(
                "Copy the latest saved comment into the new comment editor. Existing history remains read-only."
            )
            previous_comment_row_layout.addWidget(previous_comment_view, 1)
            previous_comment_row_layout.addWidget(continue_comment_btn, 0)
            previous_comment_row.setVisible(bool(existing_customer_comment))

            comment_label = QLabel("New Customer Comment (Optional)")
            comment_label.setStyleSheet("font-weight:700;color:#52697A;margin-top:2px;")
            customer_comment = QTextEdit()
            customer_comment.setPlaceholderText(
                "Add a new reviewer/customer comment for this issue. Leave blank to keep the latest saved comment unchanged. Previous comments are never edited or deleted."
            )
            customer_comment.setFixedHeight(64)
            customer_comment.setStyleSheet(
                "QTextEdit { background:#FFFFFF; border:1px solid #D3DEE7; border-radius:6px; "
                "padding:6px 8px; color:#243B4A; }"
            )

            def continue_issue_comment(*_args, _editor=customer_comment, _existing=existing_customer_comment):
                if not _existing:
                    return
                if _editor.toPlainText().strip():
                    answer = QMessageBox.question(
                        self, "Replace Draft?",
                        "The New Customer Comment editor already contains text. Replace the draft with the latest saved comment?",
                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                    )
                    if answer != QMessageBox.Yes:
                        return
                _editor.setPlainText(_existing)
                cursor = _editor.textCursor(); cursor.movePosition(QTextCursor.End); _editor.setTextCursor(cursor)
                _editor.setFocus()

            continue_comment_btn.clicked.connect(continue_issue_comment)

            def refresh_preview(
                _index=0, *, _combo=combo, _preview=preview, _other=other_comment,
                _field=field, _row=row_index, _source_count=len(source_lines),
                _has_previous_comment=bool(existing_customer_comment)
            ):
                data = _combo.currentData()
                decision = clean((data or {}).get("decision_type") if isinstance(data, dict) else "").upper()
                is_other = decision == "OTHER"
                _other.setVisible(is_other)
                _preview.setVisible(not is_other)
                base_height = (275 if _has_previous_comment else 205) if not is_other else (350 if _has_previous_comment else 282)
                table.setRowHeight(_row, max(base_height, 136 + 18 * max(1, _source_count)))
                if is_other:
                    comment = _other.toPlainText().strip()
                    text = build_resolution_description(
                        rmu=self.rmu, field=self._field_label(_field), decision_type="OTHER",
                        selected_source="Others", selected_value=comment,
                    )
                    _combo.setToolTip(text)
                    _other.setToolTip(text)
                    return
                if isinstance(data, dict):
                    text = clean(data.get("decision_description")) or build_resolution_description(
                        rmu=self.rmu,
                        field=_field,
                        decision_type=data.get("decision_type", ""),
                        selected_source=data.get("selected_source", ""),
                        selected_value=data.get("selected_value", ""),
                        normalized_value=data.get("normalized_value", ""),
                    )
                else:
                    text = build_resolution_description(
                        rmu=self.rmu, field=self._field_label(_field), decision_type="UNRESOLVED"
                    )
                _preview.setText(text)
                _combo.setToolTip(text)

            combo.currentIndexChanged.connect(refresh_preview)

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
                        # Preserve the exact previously frozen wording when present.
                        if clean(current.get("decision_description")) and decision != "OTHER":
                            data = dict(data)
                            data["decision_description"] = clean(current.get("decision_description"))
                            combo.setItemData(index, data)
                        if decision == "OTHER":
                            other_comment.setPlainText(
                                clean(current.get("selected_value")) or clean(current.get("decision_description"))
                            )
                        combo.setCurrentIndex(index)
                        break

            self.combos[field] = combo
            self.previews[field] = preview
            self.other_comments[field] = other_comment
            self.customer_comments[field] = customer_comment
            cell_layout.addWidget(combo)
            cell_layout.addWidget(preview)
            cell_layout.addWidget(other_comment)
            cell_layout.addWidget(previous_comment_label)
            cell_layout.addWidget(previous_comment_row)
            cell_layout.addWidget(comment_label)
            cell_layout.addWidget(customer_comment)
            table.setCellWidget(row_index, 2, cell)
            refresh_preview()

        table.setUpdatesEnabled(True)
        layout.addWidget(table, 1)
        footer = QLabel(
            "Resolution and Customer Comments are stored independently. Existing comments are read-only in this dialog. Leave New Customer Comment blank to keep the latest comment unchanged, or add/continue a comment to append a new review-history record. RMU Action Tracking / Full Lifecycle retains the full history once the RMU has a Needs Action case."
        )
        footer.setObjectName("Muted")
        footer.setWordWrap(True)
        layout.addWidget(footer)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Save Resolutions & Comments")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        for field, combo in self.combos.items():
            data = combo.currentData()
            decision = clean((data or {}).get("decision_type") if isinstance(data, dict) else "").upper()
            if decision == "OTHER":
                editor = self.other_comments.get(field)
                comment = editor.toPlainText().strip() if editor else ""
                if not comment:
                    QMessageBox.warning(
                        self,
                        "Comment Required",
                        f"Enter a custom Resolution value / instruction for {self._field_label(field)} before saving.",
                    )
                    if editor:
                        editor.setFocus()
                    return
        super().accept()

    def decisions(self) -> dict[str, dict | None]:
        result: dict[str, dict | None] = {}
        for field, combo in self.combos.items():
            data = combo.currentData()
            if isinstance(data, dict):
                payload = dict(data)
                decision = clean(payload.get("decision_type")).upper()
                if decision == "OTHER":
                    # v0.8.195: resolve the configured/display label inside
                    # this loop.  The previous branch referenced an undefined
                    # ``field_label`` local, so choosing "Others · custom
                    # resolution" failed before the background SQLite save
                    # could even start.
                    field_label = self._field_label(field)
                    editor = self.other_comments.get(field)
                    comment = editor.toPlainText().strip() if editor else ""
                    payload.update({
                        "selected_source": "Others",
                        "selected_value": comment,
                        "normalized_value": "",
                        "decision_description": build_resolution_description(
                            rmu=self.rmu, field=field_label, decision_type="OTHER",
                            selected_source="Others", selected_value=comment,
                        ),
                    })
                comment_editor = self.customer_comments.get(field)
                new_comment = comment_editor.toPlainText().strip() if comment_editor else ""
                existing_comment = clean(self.customer_existing_comments.get(field))
                payload["customer_comment"] = new_comment if new_comment else existing_comment
                payload["customer_comment_submitted"] = bool(new_comment)
                payload["issue_snapshot"] = dict(self.issue_snapshots.get(field) or {})
                result[field] = payload
            else:
                result[field] = None
        return result


class ColumnVisibilityDialog(QDialog):
    """Choose Equipment Data Review presentation columns.

    Visibility is presentation-only. Columns whose App fields feed system
    matching/Analysis/validation are locked on and cannot be hidden. Optional
    built-in fields and USER App columns remain reviewer controlled.
    """

    def __init__(self, groups, visible_keys: set[str], protected_keys: set[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equipment Data Review Columns")
        self.resize(820, 760)
        self.groups = groups
        self.protected_keys = set(protected_keys or set()) | {"no", "rmu"}
        self._checks: dict[str, QCheckBox] = {}
        self._group_checks: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)
        title = QLabel("Choose visible Equipment Data Review columns")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel(
            "This dialog controls App/meta columns such as Index, Source Coverage, Analysis, Remarks and Resolution. "
            "Physical source columns follow the Show checkboxes in the configurable Equipment Data Review source editor, so each site has one visibility setting per source field. "
            "SYSTEM calculation fields are always visible because they feed matching, Analysis or validation. No source mapping, SQLite review data or exported report history is deleted by changing this view."
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        root.addWidget(desc)

        preset = QHBoxLayout()
        review_btn = QPushButton("Review View")
        full_btn = QPushButton("Full View")
        system_btn = QPushButton("System Required")
        review_btn.setToolTip("Show all protected system columns plus Remarks and Resolution / Comments.")
        full_btn.setToolTip("Show every current App field in Equipment Data Review.")
        system_btn.setToolTip("Show only fields that the application requires for identity, source coverage and system calculations.")
        all_keys = {k for _g, _c, cols in self.groups for k, _l, _w in cols}
        review_keys = self.protected_keys | {"remarks", "comments"}
        full_btn.clicked.connect(lambda: self._set_visible(all_keys))
        review_btn.clicked.connect(lambda: self._set_visible(review_keys))
        system_btn.clicked.connect(lambda: self._set_visible(self.protected_keys))
        preset.addWidget(review_btn)
        preset.addWidget(full_btn)
        preset.addWidget(system_btn)
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
                locked = key in self.protected_keys
                cb = QCheckBox(f"{label}  ·  SYSTEM" if locked else label)
                cb.setChecked(True if locked else key in visible_keys)
                if locked:
                    cb.setEnabled(False)
                    cb.setToolTip("Required by system calculation / matching / validation. This column cannot be hidden.")
                else:
                    cb.setToolTip("Presentation-only column. Hide/show does not change source mapping or calculation logic.")
                self._checks[key] = cb
                grid.addWidget(cb, pos // 3, pos % 3)
            box.addLayout(grid)

            child_keys = [key for key, _label, _width in columns]
            editable_keys = [key for key in child_keys if key not in self.protected_keys]
            if editable_keys:
                gcheck.setChecked(all(self._checks[key].isChecked() for key in child_keys))
                gcheck.clicked.connect(lambda checked, keys=editable_keys: self._set_group(keys, checked))
                for key in editable_keys:
                    self._checks[key].toggled.connect(lambda _checked, g=group, keys=child_keys: self._sync_group(g, keys))
            else:
                gcheck.setChecked(True)
                gcheck.setEnabled(False)
                gcheck.setToolTip("All columns in this group are required by the system.")
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
            cb = self._checks.get(key)
            if cb is not None and cb.isEnabled():
                cb.setChecked(checked)

    def _sync_group(self, group: str, keys: list[str]):
        cb = self._group_checks[group]
        cb.blockSignals(True)
        cb.setChecked(all(self._checks[key].isChecked() for key in keys))
        cb.blockSignals(False)

    def _set_visible(self, keys: set[str]):
        keys = set(keys) | self.protected_keys
        for key, cb in self._checks.items():
            if cb.isEnabled():
                cb.setChecked(key in keys)
            elif key in self.protected_keys:
                cb.setChecked(True)

    def visible_keys(self) -> set[str]:
        return {key for key, cb in self._checks.items() if cb.isChecked()} | self.protected_keys


class NoWheelComboBox(QComboBox):
    """ComboBox that cannot change selection from the mouse wheel.

    Source Mapping is a data-governance screen. Accidental wheel changes are
    particularly risky because they can silently create a site override.
    The user must open the drop-down (or use the keyboard) to change a mapping.
    """

    def wheelEvent(self, event):
        event.ignore()


class SourceColumnOrderDialog(QDialog):
    """Presentation-only column order editor for one physical source group.

    The list stores canonical App field keys and never source-file column
    indexes. Drag/drop therefore changes only RMU Data Review / workbook
    presentation and cannot alter parsing, Analysis, reviews or source data.
    """

    def __init__(self, source_label: str, items: list[tuple[str, str, str]], current_order: list[str], default_order: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Move Columns · {source_label}")
        self.resize(560, 650)
        self._item_meta = {key: (label, role) for key, label, role in items}
        self._default_order = [key for key in default_order if key in self._item_meta]

        root = QVBoxLayout(self)
        title = QLabel(f"{source_label} column order")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel(
            "Drag columns into any order, or use the move buttons. This changes only how columns are displayed inside this source group; "
            "Source Field mapping and automatic Analysis are not changed."
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        root.addWidget(desc)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setAlternatingRowColors(True)
        root.addWidget(self.list, 1)

        tools = QHBoxLayout()
        for text, callback in (
            ("Top", self._move_top),
            ("Up", lambda: self._move_delta(-1)),
            ("Down", lambda: self._move_delta(1)),
            ("Bottom", self._move_bottom),
        ):
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            tools.addWidget(btn)
        tools.addStretch()
        reset = QPushButton("Reset Default Order")
        reset.clicked.connect(self._reset_default)
        tools.addWidget(reset)
        root.addLayout(tools)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Apply Order")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        normalized = [key for key in current_order if key in self._item_meta]
        normalized.extend(key for key in self._default_order if key not in normalized)
        self._load(normalized)

    def _load(self, order: list[str]):
        self.list.clear()
        for key in order:
            label, role = self._item_meta[key]
            item = QListWidgetItem(f"{label}    [{role}]")
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(f"Stable App field: {key}")
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _move_delta(self, delta: int):
        row = self.list.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)

    def _move_top(self):
        row = self.list.currentRow()
        if row <= 0:
            return
        item = self.list.takeItem(row)
        self.list.insertItem(0, item)
        self.list.setCurrentRow(0)

    def _move_bottom(self):
        row = self.list.currentRow()
        if row < 0 or row >= self.list.count() - 1:
            return
        item = self.list.takeItem(row)
        target = self.list.count()
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)

    def _reset_default(self):
        self._load(self._default_order)

    def order_keys(self) -> list[str]:
        return [
            clean(self.list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.list.count())
            if clean(self.list.item(row).data(Qt.ItemDataRole.UserRole))
        ]


class SystemMappingEditorDialog(QDialog):
    """Explicit editor for protected SYSTEM semantics.

    The main Map Fields grid remains strictly source-driven (one physical
    source column = one visible App row).  When a non-standard file does not
    contain any declared alias for a required SYSTEM field, there is therefore
    no canonical row to unlock in that grid.  This companion editor closes that
    gap without creating phantom source rows: reviewers bind each protected
    SYSTEM semantic directly to one of the live physical headers.
    """

    def __init__(self, source_type: str, schema, headers, locked_keys, current_overrides, parent=None):
        super().__init__(parent)
        self.source_type = str(source_type or "")
        self.schema = schema
        self.headers = tuple(clean(h) for h in (headers or ()) if clean(h))
        self.locked_keys = set(locked_keys or ())
        self.current_overrides = dict(current_overrides or {})
        self._result_overrides = dict(self.current_overrides)
        self._combos: dict[str, QComboBox] = {}

        self.setWindowTitle("Edit System Mappings")
        self.resize(760, 520)
        root = QVBoxLayout(self)
        title = QLabel("System Mapping Assignments")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel(
            "Bind protected SYSTEM semantics to the current physical source headers. "
            "Use this when the file uses non-standard names such as DE_NAME instead of EQUIPMENT. "
            "This does not add phantom source columns: the main Map Fields table still mirrors the physical file exactly."
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        root.addWidget(desc)

        specs = [spec for spec in (self.schema.fields if self.schema else ()) if spec.key in self.locked_keys]
        self.table = QTableWidget(len(specs), 4)
        self.table.setHorizontalHeaderLabels(["System Field", "Source Field", "Requirement", "Current Status"])
        _configure_table_base(self.table)
        _set_interactive_column(self.table, 0, 220)
        _set_stretch_column(self.table, 1)
        _set_fixed_column(self.table, 2, 110)
        _set_fixed_column(self.table, 3, 150)

        validation = resolve_schema(self.schema, self.headers, self.current_overrides) if self.schema else None
        by_key = validation.mapping_by_key if validation is not None else {}
        for row, spec in enumerate(specs):
            mapping = by_key.get(spec.key)
            app_item = QTableWidgetItem(canonical_system_field_label(self.source_type, spec.key, spec.label))
            app_item.setToolTip(spec.description or spec.label)
            self.table.setItem(row, 0, app_item)

            combo = NoWheelComboBox()
            combo.addItem("Auto", "")
            if not spec.required:
                combo.addItem("Blank · no source field", BLANK_OVERRIDE_TOKEN)
            if self.headers:
                combo.insertSeparator(combo.count())
            for header in self.headers:
                combo.addItem(header, header)

            saved = clean(self.current_overrides.get(spec.key, ""))
            selected = ""
            if saved == BLANK_OVERRIDE_TOKEN:
                selected = BLANK_OVERRIDE_TOKEN
            elif is_manual_override(saved):
                selected = decode_manual_override(saved)
            elif mapping is not None and mapping.kind == MappingKind.OVERRIDE and mapping.actual_column:
                selected = clean(mapping.actual_column)
            idx = combo.findData(selected)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            self._combos[spec.key] = combo
            self.table.setCellWidget(row, 1, combo)

            req = QTableWidgetItem("Required" if spec.required else "System")
            req.setForeground(QColor(COLORS["warning"] if spec.required else COLORS["info"]))
            self.table.setItem(row, 2, req)

            if mapping is None:
                status_text = "Missing"
            elif mapping.actual_column:
                status_text = f"{mapping.kind.value} → {mapping.actual_column}"
            else:
                status_text = mapping.kind.value
            status = QTableWidgetItem(status_text)
            status.setForeground(QColor(
                COLORS["warning"] if mapping is None or mapping.kind in {MappingKind.MISSING, MappingKind.AMBIGUOUS, MappingKind.BLANK}
                else COLORS["success"]
            ))
            self.table.setItem(row, 3, status)

        root.addWidget(self.table, 1)
        note = QLabel(
            "Required SYSTEM fields must resolve before Save. Manual selections are stored as explicit source-header bindings; "
            "Auto continues to use the declared aliases when they exist."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        root.addWidget(note)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        save_btn = self.buttons.button(QDialogButtonBox.Save)
        save_btn.setText("Apply System Mappings")
        save_btn.setObjectName("Primary")
        self.buttons.accepted.connect(self._accept_mappings)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def _candidate_overrides(self) -> dict[str, str]:
        candidate = dict(self.current_overrides)
        for key, combo in self._combos.items():
            value = clean(combo.currentData())
            if value == BLANK_OVERRIDE_TOKEN:
                candidate[key] = BLANK_OVERRIDE_TOKEN
            elif value:
                candidate[key] = encode_manual_override(value)
            else:
                candidate.pop(key, None)
        return candidate

    def _accept_mappings(self):
        candidate = self._candidate_overrides()
        result = resolve_schema(self.schema, self.headers, candidate) if self.schema else None
        if result is not None and result.errors:
            QMessageBox.warning(
                self,
                "System Mapping Required",
                result.error_message("current source")
                + "\n\nSelect a physical Source Field for every required SYSTEM field before applying.",
            )
            return
        self._result_overrides = candidate
        self.accept()

    def overrides(self) -> dict[str, str]:
        return dict(self._result_overrides)


class SourceMappingDialog(QDialog):
    """Simple App-column <-> source-column mapping editor.

    The table mirrors the active physical header: one source column equals one
    App row. Canonical system semantics attach to matching rows, while unmatched
    source headers become optional App fields with the same default name. App
    labels and visibility remain configurable without creating phantom columns.
    """

    def __init__(self, source_type: str, source_path: Path, store, user_name: str, parent=None):
        super().__init__(parent)
        self.source_type = source_type
        self.source_path = Path(source_path)
        self.store = store
        self.user_name = user_name
        self.schema = schema_for(source_type)
        self.current_overrides = get_source_overrides(store, source_type)
        self.current_display_names = get_source_display_names(store, source_type)
        self.current_custom_fields = list(store.custom_source_fields(source_type) if store else [])
        self.current_hidden_fields = set(get_hidden_source_fields(store, source_type))
        self.current_column_order = list(get_source_column_order(store, source_type) or [])
        self.locked_system_fields = system_logic_field_keys(source_type)
        # v0.8.148: system calculation mappings are protected by default.
        # Reviewers may explicitly unlock them for this dialog after acknowledging
        # that a remap changes the fields used by Analysis/validation for all sites.
        self.system_mapping_unlocked = False
        self._initial_locked_selections: dict[str, str] = {}
        self.sheet_name = ""
        if self.source_path.suffix.lower() in {".xlsx", ".xlsm"}:
            preferred = store.source_sheet_name(source_type) if store and hasattr(store, "source_sheet_name") else ""
            self.sheet_name = resolve_source_excel_sheet_name(source_type, self.source_path, preferred or None)
        self.validation = validate_source_file(
            source_type, self.source_path, self.current_overrides, sheet_name=self.sheet_name or None
        )
        # Snapshot every protected semantic, including currently-missing ones.
        # v0.8.174 uses this complete state for the Save confirmation so a
        # missing -> manual binding (for example Equipment Name -> DE_NAME) is
        # never mistaken for an unchanged mapping simply because the row did not
        # exist when the dialog first opened.
        self._initial_locked_mapping_state = self._locked_mapping_state(
            self.validation, self.current_overrides
        )
        # v0.8.167: Map Fields is source-driven.  The live physical header is
        # the row contract: one physical source column = one App row.  Existing
        # canonical SYSTEM semantics are attached to the matching physical row;
        # every other physical header becomes an automatic App field whose
        # default display name is exactly the source header.
        self._inactive_custom_fields: list[dict] = []
        self._source_file_signature = self._file_signature()
        self._sync_live_source_columns()
        self._combos: dict[str, QComboBox] = {}
        self._display_edits: dict[str, QLineEdit] = {}
        self._custom_widgets: dict[str, dict] = {}
        self._visibility_checks: dict[str, QCheckBox] = {}

        self.setWindowTitle(ui_tr(f"Map Fields · {self.schema.label if self.schema else source_type}"))
        self.resize(820, 620)
        root = QVBoxLayout(self)
        title = QLabel(f"{self.schema.label if self.schema else source_type}  →  App")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel(
            "This table mirrors the live physical source header: one physical source column equals one App row. "
            "A newly added Excel/CSV column is detected after the file is saved and appears automatically; its default App name is the source header itself. "
            "You may rename the App label later without changing the physical Source Field. Canonical SYSTEM semantics are attached to the matching physical row and stay locked visible because they feed matching, Analysis or validation. "
            "Optional rows are hidden by default and can be shown/hidden for Equipment Data Review without deleting their mapping. "
            "Map Fields settings are global by App/source type: mapping, App display names, Show/Hide and column order saved at one station are reused by every station. "
            "The physical source file and Excel sheet remain station-specific. Absent physical columns are not rendered as phantom rows."
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        root.addWidget(desc)
        file_label = QLabel(f"Active source file: {self.source_path.resolve()}")
        file_label.setObjectName("Muted")
        file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        file_label.setToolTip(str(self.source_path.resolve()))
        root.addWidget(file_label)
        if self.sheet_name:
            sheet_label = QLabel(f"Active sheet: {self.sheet_name}")
            sheet_label.setObjectName("Muted")
            sheet_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            root.addWidget(sheet_label)

        protection_row = QHBoxLayout()
        self.system_protection_label = QLabel(
            "System calculation fields are protected. Their Source Field mapping feeds Analysis and validation across all sites."
        )
        self.system_protection_label.setObjectName("Muted")
        self.system_protection_label.setWordWrap(True)
        protection_row.addWidget(self.system_protection_label, 1)
        self.unlock_system_btn = QPushButton("Unlock System Mappings...")
        self.unlock_system_btn.setToolTip(
            "Allow remapping of SYSTEM · LOCKED fields for this dialog only. A confirmation is required because these mappings feed system calculations."
        )
        self.unlock_system_btn.clicked.connect(self._unlock_system_mappings)
        protection_row.addWidget(self.unlock_system_btn)
        root.addLayout(protection_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Show", "App Column", "Source Field", "Type", "Status"])
        _configure_table_base(self.table)
        _set_fixed_column(self.table, 0, 70)
        _set_interactive_column(self.table, 1, 250)
        _set_stretch_column(self.table, 2)
        _set_fixed_column(self.table, 3, 145)
        _set_fixed_column(self.table, 4, 115)
        self._populate()
        root.addWidget(self.table, 1)

        # Watch only file metadata on the GUI thread.  When Excel/CSV is saved
        # with new/removed headers, the header is re-read once and the dialog
        # rebuilds itself automatically without repeatedly parsing the workbook.
        self._live_header_timer = QTimer(self)
        self._live_header_timer.setInterval(1500)
        self._live_header_timer.timeout.connect(self._refresh_if_source_changed)
        self._live_header_timer.start()

        self.result_label = QLabel(self._summary_text(self.validation))
        self.result_label.setObjectName("Muted")
        self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)

        button_row = QHBoxLayout()
        show_all_btn = QPushButton("Show All Fields")
        show_all_btn.setToolTip("Show every optional and USER App field in Equipment Data Review. SYSTEM calculation fields are always shown.")
        show_all_btn.clicked.connect(self._show_all_fields)
        button_row.addWidget(show_all_btn)
        hide_optional_btn = QPushButton("Hide Optional Fields")
        hide_optional_btn.setToolTip("Hide every optional and USER App field at once. SYSTEM calculation fields stay visible and cannot be hidden.")
        hide_optional_btn.clicked.connect(self._hide_optional_fields)
        button_row.addWidget(hide_optional_btn)
        move_column_btn = QPushButton("Move Column...")
        move_column_btn.setToolTip("Reorder App columns inside this source group. This changes presentation only.")
        move_column_btn.clicked.connect(self._move_columns)
        button_row.addWidget(move_column_btn)
        reset_btn = QPushButton("Reset Auto Mapping")
        reset_btn.clicked.connect(self._reset_all_to_auto)
        button_row.addWidget(reset_btn)
        button_row.addStretch()
        self.button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        self.save_button = self.button_box.button(QDialogButtonBox.Save)
        self.save_button.setText("Save")
        self.save_button.setObjectName("Primary")
        self.button_box.accepted.connect(self._save)
        self.button_box.rejected.connect(self.reject)
        button_row.addWidget(self.button_box)
        root.addLayout(button_row)

    def _file_signature(self):
        try:
            stat = self.source_path.stat()
            return (int(stat.st_mtime_ns), int(stat.st_size))
        except OSError:
            return None

    def _header_key(self, value: str) -> str:
        return clean(value).casefold()

    def _built_in_owner_by_header(self) -> dict[str, str]:
        """Return one canonical App key for each live physical header.

        A physical header may satisfy more than one legacy alias.  The table must
        still contain one row only, so SYSTEM/required semantics win, followed by
        schema order.
        """
        if self.validation is None or self.schema is None:
            return {}
        header_lookup = {self._header_key(h): h for h in self.validation.headers}
        candidates: dict[str, list[tuple[int, int, str]]] = {}
        by_key = self.validation.mapping_by_key
        for index, spec in enumerate(self.schema.fields):
            mapping = by_key.get(spec.key)
            actual = clean(mapping.actual_column if mapping else '')
            hk = self._header_key(actual)
            if not hk or hk not in header_lookup:
                continue
            priority = 0
            if spec.key in self.locked_system_fields:
                priority += 100
            if spec.required:
                priority += 20
            if getattr(mapping, 'kind', None) == MappingKind.EXACT:
                priority += 5
            candidates.setdefault(hk, []).append((-priority, index, spec.key))
        return {hk: sorted(values)[0][2] for hk, values in candidates.items()}

    def _stable_auto_custom_key(self, header: str, reserved: set[str]) -> str:
        base = f"source_{slug_key(header)}"
        key = base
        index = 2
        while key in reserved:
            key = f"{base}_{index}"
            index += 1
        return key

    def _sync_live_source_columns(self) -> None:
        """Make App rows mirror the current physical source header exactly.

        Existing USER mappings that are not present in this site's current file
        are retained as inactive metadata so a different station can still use
        them, but they are not rendered as phantom rows in this dialog.
        """
        if self.validation is None or self.schema is None:
            return
        headers = [clean(h) for h in self.validation.headers if clean(h)]
        header_keys = {self._header_key(h) for h in headers}
        owners = self._built_in_owner_by_header()
        existing = [dict(item or {}) for item in self.current_custom_fields]
        by_actual = {}
        for item in existing:
            actual = clean(item.get('actual_column'))
            if actual:
                by_actual.setdefault(self._header_key(actual), item)

        active_custom: list[dict] = []
        inactive_custom: list[dict] = []
        reserved = {spec.key for spec in self.schema.fields}
        reserved.update(clean(item.get('field_key')) for item in existing if clean(item.get('field_key')))
        used_custom_keys: set[str] = set()

        for header in headers:
            hk = self._header_key(header)
            if hk in owners:
                continue
            item = by_actual.get(hk)
            if item is None:
                key = self._stable_auto_custom_key(header, reserved)
                reserved.add(key)
                item = {
                    'field_key': key,
                    'display_name': header,
                    'actual_column': header,
                    'auto_source_field': True,
                }
            else:
                item = dict(item)
                item['actual_column'] = header
                if not clean(item.get('display_name')):
                    item['display_name'] = header
            active_custom.append(item)
            used_custom_keys.add(clean(item.get('field_key')))

        for item in existing:
            key = clean(item.get('field_key'))
            actual = clean(item.get('actual_column'))
            if key in used_custom_keys:
                continue
            # A USER App mapping to a currently absent source header remains
            # globally persistent but is not a row in this source-driven view.
            # Any pre-existing USER metadata not selected as the one visible
            # owner of a physical header stays persisted but inactive. This also
            # protects legacy duplicate mappings from being deleted on Save.
            inactive_custom.append(item)

        self.current_custom_fields = active_custom
        self._inactive_custom_fields = inactive_custom

    def _refresh_if_source_changed(self):
        signature = self._file_signature()
        if signature is None or signature == self._source_file_signature:
            return
        self._source_file_signature = signature
        try:
            self._capture_unsaved_state()
            validation = validate_source_file(
                self.source_type, self.source_path, self.current_overrides,
                sheet_name=self.sheet_name or None,
            )
            if validation is None:
                return
            self.validation = validation
            # Include currently active and inactive USER metadata before syncing
            # so renamed App labels survive a live header refresh.
            self._sync_live_source_columns()
            self._combos.clear()
            self._display_edits.clear()
            self._custom_widgets.clear()
            self._visibility_checks.clear()
            self._initial_locked_selections.clear()
            self._populate()
            self.result_label.setText(self._summary_text(self.validation))
        except Exception as exc:
            # Excel can be momentarily locked while the user saves it.  Keep the
            # last valid header and retry on the next metadata change/open.
            self.result_label.setText(f"Source changed; waiting for a readable header: {type(exc).__name__}: {exc}")

    def _unlock_system_mappings(self):
        # Once unlocked, this button remains useful: it reopens the dedicated
        # SYSTEM semantic editor.  v0.8.173 disabled the button after Unlock,
        # which meant a required semantic with no alias row (e.g. Equipment
        # Name in a DE_NAME file) could never actually be mapped.
        if self.system_mapping_unlocked:
            self._edit_system_mappings()
            return
        text = (
            "SYSTEM · LOCKED fields are used by system-level Analysis, matching, and validation calculations.\n\n"
            "Changing a protected Source Field changes how that App Column is interpreted for ALL sites that use this source type. "
            "Only remap a system field when the new physical source column has been verified.\n\n"
            "Unlock protected system mappings for this dialog?"
        )
        answer = QMessageBox.warning(
            self,
            ui_tr("Unlock System Mappings"),
            ui_tr(text),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.system_mapping_unlocked = True
        self._apply_system_mapping_protection()
        self.system_protection_label.setText(
            "System mappings are UNLOCKED for this dialog. Use Edit System Mappings to bind missing or non-standard source headers; Save will ask for confirmation again."
        )
        self.unlock_system_btn.setText("Edit System Mappings...")
        self.unlock_system_btn.setEnabled(True)
        self.unlock_system_btn.setToolTip(
            "Edit every protected SYSTEM semantic, including required fields that have no automatic alias match in the current physical header."
        )
        self.result_label.setText(
            "Protected system mappings unlocked. Bind any missing SYSTEM field to a verified physical source header before Save."
        )
        # Open the real assignment editor immediately so Unlock is an actionable
        # operation rather than only changing the colour/enabled state of rows
        # that already happened to auto-match.
        self._edit_system_mappings()

    def _edit_system_mappings(self):
        if not self.system_mapping_unlocked or self.schema is None or self.validation is None:
            return
        # Preserve unsaved labels/visibility and any edits to already-visible
        # SYSTEM rows before presenting the full semantic assignment list.
        self._capture_unsaved_state()
        dialog = SystemMappingEditorDialog(
            self.source_type,
            self.schema,
            self.validation.headers,
            self.locked_system_fields,
            self.current_overrides,
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        self.current_overrides = dialog.overrides()
        # Re-resolve against the cached physical header.  A newly-bound required
        # semantic now takes ownership of that existing physical row; no phantom
        # row is added and the one-source-column/one-App-row invariant remains.
        self.validation = resolve_schema(self.schema, self.validation.headers, self.current_overrides)
        self._sync_live_source_columns()
        self._combos.clear()
        self._display_edits.clear()
        self._custom_widgets.clear()
        self._visibility_checks.clear()
        self._populate()
        self._apply_system_mapping_protection()
        self.result_label.setText(
            "SYSTEM mappings updated in this dialog. Review the promoted rows, then Save to persist and refresh calculated data."
        )

    def _apply_system_mapping_protection(self):
        """Enable/disable protected mapping selectors without affecting labels.

        App Column display names remain editable because renaming is presentation-only;
        only the Source Field relationship that feeds system calculations is protected.
        """
        for key, combo in self._combos.items():
            if key in self.locked_system_fields:
                combo.setEnabled(self.system_mapping_unlocked)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 3)
            meta = item.data(Qt.ItemDataRole.UserRole) if item else None
            if not isinstance(meta, dict) or not bool(meta.get("locked")):
                continue
            item.setText("SYSTEM · UNLOCKED" if self.system_mapping_unlocked else "SYSTEM · LOCKED")
            item.setForeground(QColor(COLORS["warning"] if self.system_mapping_unlocked else COLORS["info"]))
            item.setToolTip(
                "System calculation field. Source Field remapping is enabled for this dialog and will require Save confirmation."
                if self.system_mapping_unlocked else
                "System calculation field. Click 'Unlock System Mappings...' before changing its Source Field mapping."
            )

    def _locked_mapping_state(self, validation, overrides) -> dict[str, tuple[str, str, str]]:
        by_key = validation.mapping_by_key if validation is not None else {}
        state: dict[str, tuple[str, str, str]] = {}
        for key in self.locked_system_fields:
            mapping = by_key.get(key)
            actual = clean(mapping.actual_column if mapping else "")
            kind = mapping.kind.value if mapping is not None else "Missing"
            override = clean((overrides or {}).get(key, ""))
            state[key] = (actual, kind, override)
        return state

    def _changed_locked_mapping_keys(self) -> list[str]:
        if self.schema is None or self.validation is None:
            return []
        current_validation = resolve_schema(self.schema, self.validation.headers, self.current_overrides)
        current_state = self._locked_mapping_state(current_validation, self.current_overrides)
        changed: list[str] = []
        for key in self.locked_system_fields:
            if current_state.get(key) != self._initial_locked_mapping_state.get(key):
                changed.append(key)
        return changed

    def _confirm_locked_mapping_save(self, changed_keys: list[str]) -> bool:
        if not changed_keys:
            return True
        labels = []
        specs = {spec.key: spec for spec in (self.schema.fields if self.schema else ())}
        for key in changed_keys:
            spec = specs.get(key)
            labels.append(canonical_system_field_label(self.source_type, key, spec.label if spec else key))
        fields = ", ".join(labels)
        text = (
            "You changed protected system Source Field mapping(s):\n\n"
            f"{fields}\n\n"
            "These mappings feed system-level Analysis and validation and are shared across ALL sites for this source type. "
            "Saving may change equipment comparison results after Refresh/Validation.\n\n"
            "Save these protected system mapping changes?"
        )
        answer = QMessageBox.warning(
            self,
            "Confirm System Mapping Changes",
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _summary_text(self, result):
        if result is None:
            return "No tabular field mapping is available for this source."
        physical_count = len(tuple(result.headers or ()))
        missing_required = [
            m.canonical_key for m in result.mappings
            if getattr(m, 'kind', None) in {MappingKind.MISSING, MappingKind.AMBIGUOUS}
            and next((spec.required for spec in self.schema.fields if spec.key == m.canonical_key), False)
        ] if self.schema else []
        if missing_required:
            return (f"{physical_count} physical source column(s) loaded. "
                    f"Missing required system mapping(s): {', '.join(missing_required)}. "
                    "Unlock System Mappings and assign the verified physical Source Field; non-standard headers are supported.")
        return f"{physical_count} physical source column(s) loaded · one source column = one App row."

    def _source_combo(self, actual_column: str = "", *, custom: bool = False, auto_resolved: str = ""):
        combo = NoWheelComboBox()
        headers = list(self.validation.headers if self.validation is not None else ())
        if custom:
            combo.addItem("Choose source column...", "")
        else:
            # Auto is a mode, not a fixed physical mapping.  When Auto has a
            # valid current result, show that result inline so the reviewer can
            # see exactly which header will feed the App field.  When Auto has
            # already run but cannot resolve a declared header, say so explicitly
            # instead of showing a visually ambiguous plain ``Auto`` value.
            auto_resolved = clean(auto_resolved)
            auto_label = f"Auto → {auto_resolved}" if auto_resolved else "Auto · No match"
            combo.addItem(auto_label, "")
            combo.setItemData(
                0,
                (f"Automatic mapping. Current resolved Source Field: {auto_resolved}. "
                 "Refresh/Validation will re-evaluate this if the file header changes."
                 if auto_resolved else
                 "Automatic mapping has already been evaluated, but no declared Source Field matches the current file. "
                 "The App value will remain blank. You may keep Auto so a future matching header can be picked up, "
                 "choose Blank for an intentional permanent blank, or select a physical Source Field manually."),
                Qt.ItemDataRole.ToolTipRole,
            )
            combo.addItem("Blank · no source field", BLANK_OVERRIDE_TOKEN)
            if headers:
                combo.insertSeparator(combo.count())
        for header in headers:
            combo.addItem(header, header)
        if actual_column:
            idx = combo.findData(actual_column)
            if idx < 0:
                combo.addItem(f"{actual_column}  [not found]", actual_column)
                idx = combo.count() - 1
            combo.setCurrentIndex(idx)
        return combo

    def _visibility_widget(self, field_key: str, *, locked: bool = False) -> QWidget:
        """Build one persistent Show/Hide selector for an App field.

        Visibility is presentation-only. Hidden fields stay in the mapping model,
        retain their Source Field mapping and remain available for later re-show.
        SYSTEM calculation fields are always checked and cannot be hidden.
        """
        checkbox = QCheckBox()
        checkbox.setChecked(True if locked else field_key not in self.current_hidden_fields)
        checkbox.setEnabled(not locked)
        checkbox.setToolTip(
            "SYSTEM calculation field. It is always shown because it feeds matching, Analysis or validation."
            if locked else
            "Show this App field in Equipment Data Review. Uncheck to hide it without deleting its mapping or App definition."
        )
        self._visibility_checks[field_key] = checkbox
        holder = QWidget()
        layout = QHBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        layout.addWidget(checkbox)
        layout.addStretch()
        return holder

    def _populate(self):
        if self.validation is None or self.schema is None:
            return
        by_key = self.validation.mapping_by_key
        headers = [clean(h) for h in self.validation.headers if clean(h)]
        owners = self._built_in_owner_by_header()
        specs_by_key = {spec.key: spec for spec in self.schema.fields}
        custom_by_header = {
            self._header_key(clean(item.get('actual_column'))): dict(item)
            for item in self.current_custom_fields
            if clean(item.get('actual_column'))
        }

        # Build exactly one row for every physical source header, in source order.
        rows: list[tuple[str, str, object]] = []
        for header in headers:
            hk = self._header_key(header)
            owner_key = owners.get(hk)
            if owner_key:
                rows.append(('built_in', owner_key, header))
            else:
                item = custom_by_header.get(hk)
                if item is not None:
                    rows.append(('custom', clean(item.get('field_key')), item))

        # Preserve a user-defined presentation order only among rows that still
        # exist in the live file. New headers join automatically without creating
        # phantom absent fields.
        row_by_key = {key: row for row in rows for key in [row[1]] if key}
        source_order = [row[1] for row in rows if row[1]]
        ordered_keys = [k for k in self.current_column_order if k in row_by_key]
        ordered_keys.extend(k for k in source_order if k not in ordered_keys)
        rows = [row_by_key[k] for k in ordered_keys]
        self.current_column_order = list(ordered_keys)

        self.table.setRowCount(len(rows))
        for row, (kind, field_key, payload) in enumerate(rows):
            if kind == 'custom':
                self._populate_custom_row(row, payload)
                continue

            spec = specs_by_key[field_key]
            mapping = by_key[spec.key]
            locked = spec.key in self.locked_system_fields
            source_header = clean(payload)
            self.table.setCellWidget(row, 0, self._visibility_widget(spec.key, locked=locked))

            historical_default = default_display_name(self.source_type, spec.key, spec.label)
            saved_name = clean(self.current_display_names.get(spec.key, ''))
            # Earlier builds persisted their own canonical default labels. Treat
            # those as defaults, not as an intentional rename.  A real user rename
            # is retained.
            display_name = source_header
            if saved_name and saved_name not in {historical_default, clean(spec.label)}:
                display_name = saved_name
            display_edit = QLineEdit(display_name)
            display_edit.setMaxLength(80)
            display_edit.setToolTip(
                "Defaults to the physical source header. You may rename the App label; the underlying system key/mapping does not change."
            )
            self._display_edits[spec.key] = display_edit
            self.table.setCellWidget(row, 1, display_edit)

            saved_override = self.current_overrides.get(spec.key, '')
            if mapping.kind == MappingKind.BLANK:
                active_override = BLANK_OVERRIDE_TOKEN
            elif is_manual_override(saved_override):
                active_override = decode_manual_override(saved_override)
            elif mapping.kind == MappingKind.OVERRIDE:
                active_override = decode_manual_override(saved_override)
            else:
                active_override = ''
            auto_resolved = source_header
            combo = self._source_combo(active_override, custom=False, auto_resolved=auto_resolved)
            self._combos[spec.key] = combo
            self.table.setCellWidget(row, 2, combo)

            if locked:
                self._initial_locked_selections.setdefault(spec.key, clean(combo.currentData()))
                combo.setEnabled(self.system_mapping_unlocked)
                if not self.system_mapping_unlocked:
                    combo.setToolTip(
                        "SYSTEM calculation mapping is protected. Click 'Unlock System Mappings...' to remap this Source Field."
                    )
            role_key = (
                'SYSTEM · UNLOCKED' if locked and self.system_mapping_unlocked
                else 'SYSTEM · LOCKED' if locked
                else 'SYSTEM · OPTIONAL'
            )
            role = QTableWidgetItem(role_key)
            role.setData(Qt.ItemDataRole.UserRole, {'kind': 'built_in', 'field_key': spec.key, 'locked': locked})
            role.setForeground(QColor(
                COLORS['muted'] if not locked
                else COLORS['warning'] if self.system_mapping_unlocked
                else COLORS['info']
            ))
            self.table.setItem(row, 3, role)

            status_text = 'Manual' if mapping.kind == MappingKind.OVERRIDE else mapping.kind.value
            status = QTableWidgetItem(status_text)
            status.setData(Qt.ItemDataRole.UserRole, {'kind': 'built_in', 'field_key': spec.key, 'locked': locked})
            status.setForeground(QColor(
                COLORS['warning'] if mapping.kind in {MappingKind.MISSING, MappingKind.AMBIGUOUS, MappingKind.BLANK}
                else COLORS['success']
            ))
            f = status.font(); f.setBold(True); status.setFont(f)
            status.setToolTip((mapping.message or spec.description or '') + '\nPhysical source column: ' + source_header)
            self.table.setItem(row, 4, status)

    def _populate_custom_row(self, row: int, item: dict):
        field_key = clean((item or {}).get("field_key"))
        display_name = clean((item or {}).get("display_name")) or field_key
        actual_column = clean((item or {}).get("actual_column"))
        self.table.setCellWidget(row, 0, self._visibility_widget(field_key, locked=False))
        display_edit = QLineEdit(display_name)
        display_edit.setMaxLength(80)
        display_edit.setToolTip("Application-global App column name. The same column is shown for every site.")
        self.table.setCellWidget(row, 1, display_edit)
        combo = self._source_combo(actual_column, custom=True)
        combo.setEnabled(False)
        combo.setToolTip(
            "Source-driven row: this App field is bound to this physical source header. Rename the App label if needed; the physical column remains unchanged."
        )
        self.table.setCellWidget(row, 2, combo)
        headers = set(self.validation.headers if self.validation is not None else ())
        mapped = bool(actual_column and actual_column in headers)
        role = QTableWidgetItem("SOURCE · OPTIONAL")
        role.setData(Qt.ItemDataRole.UserRole, {"kind": "added", "field_key": field_key, "locked": False})
        role.setForeground(QColor(COLORS["success"]))
        role.setToolTip("Physical source column discovered from the live file. The App display name can be changed; visibility is presentation-only.")
        self.table.setItem(row, 3, role)
        status = QTableWidgetItem("Mapped" if mapped else "Unmapped · blank")
        status.setData(Qt.ItemDataRole.UserRole, {"kind": "added", "field_key": field_key, "locked": False})
        status.setForeground(QColor(COLORS["success"] if mapped else COLORS["warning"]))
        f = status.font(); f.setBold(True); status.setFont(f)
        status.setToolTip("Physical source column")
        self.table.setItem(row, 4, status)
        self._custom_widgets[field_key] = {"display": display_edit, "combo": combo}

    def _current_table_order(self) -> list[str]:
        order: list[str] = []
        for row in range(self.table.rowCount()):
            meta_item = self.table.item(row, 3) or self.table.item(row, 4)
            meta = meta_item.data(Qt.ItemDataRole.UserRole) if meta_item else None
            key = clean((meta or {}).get("field_key")) if isinstance(meta, dict) else ""
            if key and key not in order:
                order.append(key)
        return order

    def _sync_hidden_from_visibility(self) -> None:
        hidden: set[str] = set()
        for key, checkbox in self._visibility_checks.items():
            if key in self.locked_system_fields:
                checkbox.setChecked(True)
                continue
            if not checkbox.isChecked():
                hidden.add(key)
        self.current_hidden_fields = hidden

    def _visibility_summary(self) -> str:
        total = len(self._visibility_checks)
        hidden = sum(1 for key, checkbox in self._visibility_checks.items() if key not in self.locked_system_fields and not checkbox.isChecked())
        visible = total - hidden
        if current_language() == LANG_ZH_CN:
            return f"显示 {visible} 个字段 · 隐藏 {hidden} 个字段。保存后应用到设备数据审核。"
        return f"{visible} field(s) shown · {hidden} hidden. Save to apply visibility to Equipment Data Review."

    def _show_all_fields(self):
        for checkbox in self._visibility_checks.values():
            checkbox.setChecked(True)
        self._sync_hidden_from_visibility()
        self.result_label.setText(self._visibility_summary())

    def _hide_optional_fields(self):
        for key, checkbox in self._visibility_checks.items():
            checkbox.setChecked(key in self.locked_system_fields)
        self._sync_hidden_from_visibility()
        self.result_label.setText(self._visibility_summary())

    def _capture_unsaved_state(self):
        # v0.8.166: visibility is independent from mapping. Unchecked fields
        # remain fully defined and mapped; only review presentation is hidden.
        self._sync_hidden_from_visibility()
        for key, combo in self._combos.items():
            value = clean(combo.currentData())
            if value == BLANK_OVERRIDE_TOKEN:
                self.current_overrides[key] = BLANK_OVERRIDE_TOKEN
            elif value:
                # Physical header selected by the user = explicit Manual mode.
                # Prefixing lets the resolver distinguish this current decision
                # from legacy raw overrides that must remain fallback-only.
                self.current_overrides[key] = encode_manual_override(value)
            else:
                # Auto is represented by no override at all.
                self.current_overrides.pop(key, None)
        for key, edit in self._display_edits.items():
            value = clean(edit.text())
            if value:
                self.current_display_names[key] = value

        custom_fields: list[dict] = []
        for key in self._current_table_order():
            widgets = self._custom_widgets.get(key)
            if not widgets:
                continue
            custom_fields.append({
                "field_key": key,
                "display_name": clean(widgets["display"].text()),
                "actual_column": clean(widgets["combo"].currentData()),
            })
        # Keep USER mappings that belong to other station/file schemas even
        # though this source-driven dialog does not render absent physical rows.
        inactive_by_key = {clean(item.get('field_key')): dict(item) for item in self._inactive_custom_fields if clean(item.get('field_key'))}
        active_keys = {clean(item.get('field_key')) for item in custom_fields}
        merged = list(custom_fields)
        merged.extend(item for key, item in inactive_by_key.items() if key not in active_keys)
        self.current_custom_fields = merged
        self.current_column_order = self._current_table_order()

    def _move_columns(self):
        if self.schema is None:
            return
        self._capture_unsaved_state()
        custom_by_key = {clean(item.get("field_key")): item for item in self.current_custom_fields}
        items: list[tuple[str, str, str]] = []
        default_order: list[str] = []
        for spec in self.schema.fields:
            if spec.key not in self._display_edits:
                continue
            default_name = default_display_name(self.source_type, spec.key, spec.label)
            label = clean(self._display_edits[spec.key].text()) or default_name
            items.append((spec.key, label, "SYSTEM" if spec.key in self.locked_system_fields else "OPTIONAL"))
            default_order.append(spec.key)
        for item in self.current_custom_fields:
            key = clean(item.get("field_key"))
            label = clean(item.get("display_name")) or key
            if key and key in self._custom_widgets:
                items.append((key, label, "USER"))
                default_order.append(key)

        dialog = SourceColumnOrderDialog(
            self.schema.label if self.schema else self.source_type,
            items, self.current_column_order, default_order, self,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        self.current_column_order = dialog.order_keys()
        self._combos.clear()
        self._display_edits.clear()
        self._custom_widgets.clear()
        self._visibility_checks.clear()
        self._populate()
        self.result_label.setText("Column display order changed. Save to apply it to RMU Data Review and workbook exports.")

    def _unique_custom_key(self, display_name: str) -> str:
        base = slug_key(display_name)
        reserved = {spec.key for spec in self.schema.fields} | set(self._custom_widgets)
        key = base
        index = 2
        while key in reserved:
            key = f"{base}_{index}"
            index += 1
        return key

    def _add_custom_field(self):
        if self.schema is None:
            return
        display_name, ok = QInputDialog.getText(self, "Add App Column", "New App column name:")
        display_name = clean(display_name)
        if not ok or not display_name:
            return
        field_key = self._unique_custom_key(display_name)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._populate_custom_row(row, {"field_key": field_key, "display_name": display_name, "actual_column": ""})
        if field_key not in self.current_column_order:
            self.current_column_order.append(field_key)
        # If the source already has an exact same-named field, select it immediately.
        combo = self._custom_widgets[field_key]["combo"]
        for idx in range(combo.count()):
            if clean(combo.itemData(idx)).casefold() == display_name.casefold():
                combo.setCurrentIndex(idx)
                break
        self.table.setCurrentCell(row, 1)
        self.result_label.setText(ui_tr(f"Added '{display_name}'. Choose its Source Field, then Save; both will apply to every station.", current_language()))

    def _delete_custom_field(self):
        """Legacy internal entry point retained for compatibility.

        v0.8.166 intentionally no longer deletes App fields. If an older caller
        invokes this method, it behaves as Hide for the selected optional/USER
        field so mapping metadata is never destroyed.
        """
        row = self.table.currentRow()
        if row < 0:
            return
        meta_item = self.table.item(row, 3) or self.table.item(row, 4)
        meta = meta_item.data(Qt.ItemDataRole.UserRole) if meta_item else None
        if not isinstance(meta, dict):
            return
        field_key = clean(meta.get("field_key"))
        if not field_key or field_key in self.locked_system_fields:
            self.result_label.setText("SYSTEM calculation fields are always shown and cannot be hidden.")
            return
        checkbox = self._visibility_checks.get(field_key)
        if checkbox is not None:
            checkbox.setChecked(False)
        self._sync_hidden_from_visibility()
        self.result_label.setText(self._visibility_summary())

    def _restore_hidden_builtin_fields(self):
        """Legacy compatibility alias; the Restore button was removed in v0.8.166."""
        self._show_all_fields()

    def _reset_all_to_auto(self):
        protected_skipped = 0
        for key, combo in self._combos.items():
            if key in self.locked_system_fields and not self.system_mapping_unlocked:
                protected_skipped += 1
                continue
            combo.setCurrentIndex(0)
        if protected_skipped:
            self.result_label.setText(
                "Optional built-in fields will use Auto mapping after Save. Protected SYSTEM mappings were left unchanged; unlock them first if you intend to reset those mappings too."
            )
        else:
            self.result_label.setText("Built-in source fields will use Auto mapping after Save. Explicit blank selections are cleared.")

    def _set_save_state(self, busy: bool, message: str = "") -> None:
        button = getattr(self, "save_button", None)
        if button is not None:
            button.setEnabled(not busy)
            button.setText("Saving..." if busy else "Save")
        if getattr(self, "button_box", None) is not None:
            cancel = self.button_box.button(QDialogButtonBox.Cancel)
            if cancel is not None:
                cancel.setEnabled(not busy)
        if message:
            self.result_label.setText(message)
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def _save(self):
        # Capture every visible edit first.  This is also required for mappings
        # made in the v0.8.174 SYSTEM assignment editor, including semantics that
        # were missing (and therefore had no row) when Map Fields first opened.
        self._capture_unsaved_state()
        # v0.8.148: protected system mappings require an explicit second
        # confirmation at Save. This is deliberately separate from the Unlock
        # acknowledgement so an accidental selector change cannot silently alter
        # Analysis/validation mappings shared by every site.
        changed_locked = self._changed_locked_mapping_keys()
        if changed_locked and not self._confirm_locked_mapping_save(changed_locked):
            self.result_label.setText("Protected system mapping changes were not saved. Review the mappings or Cancel.")
            return

        # Give immediate feedback before any validation/persistence work.  The
        # expensive source re-read and dependent review rebuild is deliberately
        # deferred to MainWindow and runs in a spawned background process after
        # this dialog closes.
        self._set_save_state(True, "Saving field mapping settings... Please wait.")
        try:
            self._capture_unsaved_state()
            overrides = {key: value for key, value in self.current_overrides.items() if clean(value)}

            # The dialog already read the physical header when it opened.
            # Re-resolve the new mapping against that cached header rather than
            # reading the whole CSV/XLSX again on the GUI thread.  The background
            # mapping-refresh worker performs the authoritative live re-read next.
            result = resolve_schema(self.schema, self.validation.headers, overrides)
            if result is not None and result.errors:
                self._set_save_state(False)
                if self.system_mapping_unlocked:
                    QMessageBox.warning(
                        self,
                        "Source Mapping",
                        result.error_message(self.source_path.name)
                        + "\n\nSYSTEM mappings are unlocked. Use Edit System Mappings to bind every required semantic to a physical Source Field.",
                    )
                    self._edit_system_mappings()
                else:
                    QMessageBox.critical(
                        self,
                        "Source Mapping",
                        result.error_message(self.source_path.name)
                        + "\n\nClick Unlock System Mappings... to map a non-standard physical header to the missing required SYSTEM field.",
                    )
                return

            display_names = {key: clean(value) for key, value in self.current_display_names.items() if clean(value)}
            visible_builtin_keys = {key for key in self._display_edits if key not in self.current_hidden_fields}
            if any(not display_names.get(key) for key in visible_builtin_keys):
                self._set_save_state(False)
                QMessageBox.warning(self, "Source Mapping", "App Column name cannot be blank.")
                return

            custom_fields = []
            for item in self.current_custom_fields:
                field_key = clean((item or {}).get("field_key"))
                display = clean((item or {}).get("display_name"))
                actual = clean((item or {}).get("actual_column"))
                if not field_key:
                    continue
                if not display:
                    self._set_save_state(False)
                    QMessageBox.warning(self, "Source Mapping", "Added App Column name cannot be blank.")
                    return
                custom_fields.append({"field_key": field_key, "display_name": display, "actual_column": actual})

            set_source_overrides(self.store, self.source_type, overrides, self.user_name)
            set_resolved_source_mappings(
                self.store, self.source_type,
                {m.canonical_key: m.actual_column for m in result.mappings if m.actual_column},
            )
            set_source_display_names(self.store, self.source_type, display_names, self.user_name)
            set_hidden_source_fields(self.store, self.source_type, self.current_hidden_fields, self.user_name)
            self.store.replace_custom_source_fields(self.source_type, custom_fields, self.user_name)

            # Persist stable App-field keys, not physical source-column positions.
            # Hidden optional fields are appended so restoring them later is safe.
            order_to_save = list(self.current_column_order)
            all_known = [spec.key for spec in self.schema.fields] + [clean(item.get("field_key")) for item in custom_fields]
            order_to_save.extend(key for key in all_known if key and key not in order_to_save)
            set_source_column_order(self.store, self.source_type, order_to_save, self.user_name)
            self.result_label.setText("Mapping saved. Refreshing affected data in the background...")
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
            self.accept()
        except Exception as exc:
            self._set_save_state(False)
            QMessageBox.critical(self, "Source Mapping", f"{type(exc).__name__}: {exc}")




class ConfigurableEquipmentComparisonDialog(QDialog):
    """Site-local editor for arbitrary Excel/CSV Equipment Data Review inputs.

    This dialog intentionally operates on physical source columns.  There is no
    built-in SE/ZENON/ADMS schema in this workflow: each source chooses its own
    key column, source title, worksheet and visible fields; comparison rules bind
    logical review fields to any physical column from any configured source.
    """

    def __init__(self, store, user_name: str, parent=None):
        super().__init__(parent)
        self.store = store
        self.user_name = clean(user_name) or "system"
        self.ui_language = normalize_language(getattr(parent, "ui_language", current_language()))
        self.config = json.loads(json.dumps(get_equipment_comparison_config(store, bootstrap=True), ensure_ascii=False))
        self.profile_link = dict(get_equipment_comparison_profile_link(store) or {})
        self._profile_pending_mode = clean(self.profile_link.get("mode")) or "local"
        self._profile_pending_name = clean(self.profile_link.get("profile_name"))
        self._profile_pending_modified_at = clean(self.profile_link.get("profile_modified_at"))
        self._profile_pending_synced_at = clean(self.profile_link.get("synced_at"))
        self._loading_profile_controls = False
        self._loading_source = False
        self._current_source_id = ""
        self._columns_cache: dict[str, tuple] = {}

        self.setWindowTitle("Configure Equipment Comparison")
        self.resize(1600, 920)
        self.setMinimumSize(1280, 760)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel("Equipment Data Review · Configurable Sources")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel(
            "Add any number of CSV/XLSX/XLSM tables. For every table choose the key/index field used to join rows. "
            "Then define exactly which fields should be compared. All physical columns are shown by default; uncheck Show to hide a field for this site only. "
            "Source titles default to filenames and can be renamed. Filenames, worksheets and physical field names are never fixed by the App."
        )
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # Reusable/global comparison profile ---------------------------------
        profile_card = QFrame(); profile_card.setObjectName("Card")
        profile_layout = QGridLayout(profile_card); profile_layout.setContentsMargins(12, 9, 12, 9); profile_layout.setHorizontalSpacing(8); profile_layout.setVerticalSpacing(5)
        profile_layout.setColumnStretch(1, 1); profile_layout.setColumnStretch(3, 2); profile_layout.setColumnStretch(4, 1)
        profile_title = QLabel("Configuration Reuse / Inheritance"); profile_title.setObjectName("SectionTitle")
        profile_layout.addWidget(profile_title, 0, 0, 1, 6)
        profile_layout.addWidget(QLabel("Mode"), 1, 0)
        self.profile_mode_combo = QComboBox()
        self.profile_mode_combo.addItem(ui_tr("Local · this site only", self.ui_language), "local")
        self.profile_mode_combo.addItem(ui_tr("Inherit global profile · explicit sync", self.ui_language), "inherit")
        self.profile_mode_combo.currentIndexChanged.connect(self._profile_mode_changed)
        profile_layout.addWidget(self.profile_mode_combo, 1, 1)
        profile_layout.addWidget(QLabel("Profile"), 1, 2)
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._profile_selection_changed)
        profile_layout.addWidget(self.profile_combo, 1, 3, 1, 2)
        sync_profile_btn = QPushButton("Apply / Sync")
        sync_profile_btn.setObjectName("Primary")
        sync_profile_btn.clicked.connect(self._apply_selected_profile)
        profile_layout.addWidget(sync_profile_btn, 1, 5)
        save_profile_btn = QPushButton("Save Current as Profile...")
        save_profile_btn.clicked.connect(self._save_current_as_profile)
        update_profile_btn = QPushButton("Update Selected Profile")
        update_profile_btn.clicked.connect(self._update_selected_profile)
        delete_profile_btn = QPushButton("Delete Profile")
        delete_profile_btn.clicked.connect(self._delete_selected_profile)
        profile_layout.addWidget(save_profile_btn, 2, 1)
        profile_layout.addWidget(update_profile_btn, 2, 2, 1, 2)
        profile_layout.addWidget(delete_profile_btn, 2, 4)
        self.profile_status_label = QLabel("")
        self.profile_status_label.setObjectName("Muted"); self.profile_status_label.setWordWrap(True)
        profile_layout.addWidget(self.profile_status_label, 3, 0, 1, 6)
        profile_note = QLabel("A profile reuses source roles/order/titles, Key/Index defaults, Show/Hide defaults, default/per-field comparison modes and comparison field mappings. Physical file paths are never inherited; the target site keeps its own live files. Global profile changes never silently rewrite a site: press Apply / Sync, review the result, then Save & Rebuild Review.")
        profile_note.setObjectName("Muted"); profile_note.setWordWrap(True)
        profile_layout.addWidget(profile_note, 4, 0, 1, 6)
        root.addWidget(profile_card)
        self._refresh_profile_controls()

        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(6)

        # Site file pool + configured source list --------------------------
        left = QFrame(); left.setObjectName("Card")
        left_box = QVBoxLayout(left); left_box.setContentsMargins(12, 12, 12, 12); left_box.setSpacing(8)
        pool_title_row = QHBoxLayout()
        pool_title = QLabel("Available Site Files"); pool_title.setObjectName("SectionTitle")
        refresh_pool_btn = QPushButton("Refresh")
        refresh_pool_btn.setToolTip("Re-scan this site's folders for CSV/XLSX/XLSM files. Discovery never silently adds a file to a review.")
        refresh_pool_btn.clicked.connect(self._refresh_file_pool)
        pool_title_row.addWidget(pool_title); pool_title_row.addStretch(); pool_title_row.addWidget(refresh_pool_btn)
        left_box.addLayout(pool_title_row)
        pool_note = QLabel("Files may stay Unused, be added to Equipment Review, or be assigned to a Signal Mapping role. Optional Equipment/ and SignalMapping/ subfolders are supported.")
        pool_note.setObjectName("Muted"); pool_note.setWordWrap(True)
        left_box.addWidget(pool_note)
        self.file_pool_list = QListWidget()
        self.file_pool_list.setMinimumHeight(190)
        self.file_pool_list.setMinimumWidth(300)
        left_box.addWidget(self.file_pool_list, 1)
        pool_buttons = QHBoxLayout()
        add_pool_btn = QPushButton("Add → Equipment"); add_pool_btn.setObjectName("Primary"); add_pool_btn.clicked.connect(self._add_pool_to_equipment)
        signal_pool_btn = QPushButton("Use for Signal..."); signal_pool_btn.clicked.connect(self._assign_pool_to_signal)
        pool_buttons.addWidget(add_pool_btn); pool_buttons.addWidget(signal_pool_btn)
        left_box.addLayout(pool_buttons)

        source_separator = QFrame(); source_separator.setFrameShape(QFrame.HLine); source_separator.setFrameShadow(QFrame.Sunken)
        left_box.addWidget(source_separator)
        left_title = QLabel("Equipment Sources"); left_title.setObjectName("SectionTitle")
        left_box.addWidget(left_title)
        self.source_list = QListWidget()
        self.source_list.setMinimumWidth(300)
        self.source_list.currentItemChanged.connect(self._source_selection_changed)
        left_box.addWidget(self.source_list, 1)
        left_buttons = QHBoxLayout()
        add_btn = QPushButton("Add File(s)"); add_btn.clicked.connect(self._add_sources)
        toggle_btn = QPushButton("Enable / Disable"); toggle_btn.clicked.connect(self._toggle_source_enabled)
        remove_btn = QPushButton("Remove"); remove_btn.clicked.connect(self._remove_source)
        left_buttons.addWidget(add_btn); left_buttons.addWidget(toggle_btn); left_buttons.addWidget(remove_btn)
        left_box.addLayout(left_buttons)
        split.addWidget(left)

        # Selected source editor ------------------------------------------
        middle = QFrame(); middle.setObjectName("Card")
        middle_box = QVBoxLayout(middle); middle_box.setContentsMargins(14, 12, 14, 12); middle_box.setSpacing(8)
        source_title = QLabel("Selected Source"); source_title.setObjectName("SectionTitle")
        middle_box.addWidget(source_title)
        form = QFormLayout()
        self.source_title_edit = QLineEdit()
        self.source_title_edit.editingFinished.connect(self._save_current_source_editor)
        form.addRow("Module Title", self.source_title_edit)
        self.source_enabled_check = QCheckBox("Participate in Equipment Data Review")
        self.source_enabled_check.toggled.connect(self._source_enabled_changed)
        form.addRow("Review Participation", self.source_enabled_check)
        self.version_mode_combo = QComboBox()
        self.version_mode_combo.addItem(ui_tr("Latest file in family (AUTO)", self.ui_language), "latest_family")
        self.version_mode_combo.addItem(ui_tr("Pin this exact file", self.ui_language), "pinned")
        self.version_mode_combo.currentIndexChanged.connect(self._version_mode_changed)
        form.addRow("Version Mode", self.version_mode_combo)
        self.family_key_edit = QLineEdit()
        self.family_key_edit.setPlaceholderText("Automatically derived from filename; editable for similar versions")
        self.family_key_edit.editingFinished.connect(self._family_key_changed)
        form.addRow("File Family", self.family_key_edit)
        file_row = QHBoxLayout()
        self.source_path_edit = QLineEdit(); self.source_path_edit.setReadOnly(True)
        self.source_path_edit.setMinimumWidth(320); self.source_path_edit.setMinimumHeight(34)
        replace_btn = QPushButton("Replace File..."); replace_btn.clicked.connect(self._replace_current_file)
        replace_btn.setMinimumWidth(112); replace_btn.setMinimumHeight(34)
        file_row.setSpacing(8)
        file_row.addWidget(self.source_path_edit, 1); file_row.addWidget(replace_btn)
        file_host = QWidget(); file_host.setLayout(file_row); file_host.setMinimumHeight(38)
        form.addRow("Active Source File", file_host)
        self.sheet_combo = QComboBox(); self.sheet_combo.currentIndexChanged.connect(self._sheet_changed)
        form.addRow("Worksheet", self.sheet_combo)
        self.header_row_edit = QLineEdit("1"); self.header_row_edit.setMaximumWidth(100); self.header_row_edit.editingFinished.connect(self._header_row_changed)
        form.addRow("Header Row", self.header_row_edit)
        self.key_combo = QComboBox(); self.key_combo.currentIndexChanged.connect(self._key_changed)
        form.addRow("Key / Index Field", self.key_combo)
        middle_box.addLayout(form)

        fields_label = QLabel("Physical Fields · Show / Hide")
        fields_label.setStyleSheet("font-weight:700;")
        middle_box.addWidget(fields_label)
        fields_note = QLabel("Every detected source field is visible by default. Hiding a field changes only this site's Equipment Data Review presentation; it does not remove the field from comparison rules.")
        fields_note.setObjectName("Muted"); fields_note.setWordWrap(True)
        middle_box.addWidget(fields_note)
        self.fields_table = QTableWidget(0, 2)
        self.fields_table.setHorizontalHeaderLabels(["Show", "Physical Field"])
        _configure_table_base(self.fields_table)
        self.fields_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.fields_table.setColumnWidth(0, 70)
        self.fields_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.fields_table.itemChanged.connect(self._field_show_changed)
        middle_box.addWidget(self.fields_table, 1)
        split.addWidget(middle)

        # Comparison rules -------------------------------------------------
        right = QFrame(); right.setObjectName("Card")
        right_box = QVBoxLayout(right); right_box.setContentsMargins(14, 12, 14, 12); right_box.setSpacing(8)
        right_title = QLabel("Comparison Rules"); right_title.setObjectName("SectionTitle")
        right_box.addWidget(right_title)
        default_mode_row = QHBoxLayout()
        default_mode_row.addWidget(QLabel("Default Comparison Mode"))
        self.default_compare_mode_combo = QComboBox()
        self.default_compare_mode_combo.addItem(ui_tr("Strict equality · blank participates", self.ui_language), COMPARISON_MODE_STRICT)
        self.default_compare_mode_combo.addItem(ui_tr("Ignore blank values", self.ui_language), COMPARISON_MODE_IGNORE_BLANK)
        default_mode = clean(self.config.get("default_comparison_mode")) or COMPARISON_MODE_STRICT
        default_index = self.default_compare_mode_combo.findData(default_mode)
        self.default_compare_mode_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        self.default_compare_mode_combo.currentIndexChanged.connect(self._default_comparison_mode_changed)
        self.default_compare_mode_combo.setToolTip(ui_tr(
            "This is the site default. Each comparison field can inherit it or override it independently.",
            self.ui_language,
        ))
        default_mode_row.addWidget(self.default_compare_mode_combo, 1)
        right_box.addLayout(default_mode_row)
        compare_note = QLabel(
            "Each row is one Analysis field. Choose which physical field from each source participates and choose its comparison mode. "
            "Strict mode treats blank as a real value; Ignore Blank keeps the legacy behavior and excludes blank values from the comparison."
        )
        compare_note.setObjectName("Muted"); compare_note.setWordWrap(True)
        right_box.addWidget(compare_note)
        self.rule_table = QTableWidget(0, 1)
        _configure_table_base(self.rule_table)
        self.rule_table.verticalHeader().setVisible(False)
        self.rule_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        right_box.addWidget(self.rule_table, 1)
        rule_buttons = QHBoxLayout()
        add_rule = QPushButton("Add Comparison Field"); add_rule.setObjectName("Primary"); add_rule.clicked.connect(self._add_rule)
        remove_rule = QPushButton("Remove Rule"); remove_rule.clicked.connect(self._remove_rule)
        rule_buttons.addWidget(add_rule); rule_buttons.addWidget(remove_rule); rule_buttons.addStretch()
        right_box.addLayout(rule_buttons)
        split.addWidget(right)

        left.setMinimumWidth(310); middle.setMinimumWidth(500); right.setMinimumWidth(560)
        split.setStretchFactor(0, 0); split.setStretchFactor(1, 1); split.setStretchFactor(2, 2)
        split.setSizes([320, 530, 750])
        root.addWidget(split, 1)

        self.validation_label = QLabel("")
        self.validation_label.setObjectName("Muted"); self.validation_label.setWordWrap(True)
        root.addWidget(self.validation_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Save & Rebuild Review")
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self._accept_config)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh_file_pool()
        self._refresh_source_list()
        self._rebuild_rule_table()
        if self.source_list.count():
            self.source_list.setCurrentRow(0)
        else:
            self._load_source_editor(None)
        self._update_validation_text()
        translate_widget_tree(self, self.ui_language)

    def _selected_profile_name(self) -> str:
        if not hasattr(self, "profile_combo"):
            return ""
        return clean(self.profile_combo.currentData()) or clean(self.profile_combo.currentText())

    def _refresh_profile_controls(self, select_name: str = ""):
        if not hasattr(self, "profile_combo"):
            return
        wanted = clean(select_name) or clean(self._profile_pending_name)
        self._loading_profile_controls = True
        try:
            self.profile_combo.blockSignals(True)
            self.profile_mode_combo.blockSignals(True)
            self.profile_combo.clear()
            self.profile_combo.addItem(ui_tr("— Select reusable profile —", self.ui_language), "")
            profiles = list_equipment_comparison_profiles()
            for item in profiles:
                name = clean(item.get("name"))
                if name:
                    self.profile_combo.addItem(name, name)
            mode_index = self.profile_mode_combo.findData(
                "inherit" if clean(self._profile_pending_mode) == "inherit" else "local"
            )
            self.profile_mode_combo.setCurrentIndex(max(0, mode_index))
            if wanted:
                index = self.profile_combo.findData(wanted)
                if index >= 0:
                    self.profile_combo.setCurrentIndex(index)
                else:
                    self.profile_combo.setCurrentIndex(0)
            else:
                self.profile_combo.setCurrentIndex(0)
        finally:
            self.profile_mode_combo.blockSignals(False)
            self.profile_combo.blockSignals(False)
            self._loading_profile_controls = False
        self._update_profile_status()

    def _profile_mode_changed(self, _index):
        if self._loading_profile_controls:
            return
        mode = clean(self.profile_mode_combo.currentData()) or "local"
        self._profile_pending_mode = mode
        if mode == "local":
            # Keep the selected profile in the combo so it can still be applied as
            # a one-time copy; only the saved inheritance link is removed.
            self._profile_pending_name = ""
            self._profile_pending_modified_at = ""
            self._profile_pending_synced_at = ""
        else:
            selected = self._selected_profile_name()
            if selected:
                self._profile_pending_name = selected
        self._update_profile_status()

    def _profile_selection_changed(self, _index):
        if self._loading_profile_controls:
            return
        selected = self._selected_profile_name()
        if clean(self.profile_mode_combo.currentData()) == "inherit":
            self._profile_pending_name = selected
        self._update_profile_status()

    def _update_profile_status(self):
        if not hasattr(self, "profile_status_label"):
            return
        selected = self._selected_profile_name()
        mode = clean(self.profile_mode_combo.currentData()) if hasattr(self, "profile_mode_combo") else "local"
        zh = self.ui_language == LANG_ZH_CN
        if mode != "inherit":
            self.profile_status_label.setText(
                "本地模式：当前站点独立维护。也可以先选择一个模板执行一次“应用 / 同步”，然后继续保持本地模式。"
                if zh else
                "Local mode: this site is independent. You can still choose a profile and Apply / Sync once, then remain Local."
            )
            return
        if not selected:
            self.profile_status_label.setText(
                "继承模式：请选择一个全局模板，然后点击“应用 / 同步”。"
                if zh else
                "Inheritance mode: select a global profile, then Apply / Sync."
            )
            return
        profile = get_equipment_comparison_profile(selected)
        if not profile:
            self.profile_status_label.setText(
                f"模板“{selected}”已不存在。请选择其他模板，或切换回本地模式。"
                if zh else
                f"Profile '{selected}' no longer exists. Choose another profile or switch to Local."
            )
            return
        modified = clean(profile.get("modified_at"))
        linked_same = clean(self._profile_pending_name) == selected
        if linked_same and self._profile_pending_modified_at and modified and modified != self._profile_pending_modified_at:
            self.profile_status_label.setText(
                f"已继承模板：{selected} · 检测到模板更新（{modified}）。请点击“应用 / 同步”检查后，再保存当前站点。"
                if zh else
                f"Inherited profile: {selected} · profile update available ({modified}). Press Apply / Sync to review it before saving this site."
            )
        elif linked_same and self._profile_pending_synced_at:
            self.profile_status_label.setText(
                f"已继承模板：{selected} · 上次同步 {self._profile_pending_synced_at or '-'} · 全局模板变化不会静默覆盖当前站点。"
                if zh else
                f"Inherited profile: {selected} · last synced {self._profile_pending_synced_at or '-'} · global changes are never applied silently."
            )
        else:
            self.profile_status_label.setText(
                f"已选择模板：{selected} · 点击“应用 / 同步”可将模板规则合并到当前站点的实时源文件配置。"
                if zh else
                f"Selected profile: {selected} · press Apply / Sync to merge it with this site's live source files."
            )

    def _save_current_as_profile(self):
        self._save_current_source_editor()
        self._capture_rule_table()
        name, ok = QInputDialog.getText(
            self, ui_tr("Reusable Comparison Profile", self.ui_language), ui_tr("Profile name:", self.ui_language)
        )
        name = clean(name)
        if not ok or not name:
            return
        existing = get_equipment_comparison_profile(name)
        if existing and QMessageBox.question(
            self,
            ui_tr("Reusable Comparison Profile", self.ui_language),
            (f"模板“{name}”已经存在。是否用当前配置替换它？" if self.ui_language == LANG_ZH_CN else f"Profile '{name}' already exists. Replace it with the current configuration?"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            saved = save_equipment_comparison_profile(name, self.config, self.user_name)
        except Exception as exc:
            QMessageBox.critical(self, ui_tr("Reusable Comparison Profile", self.ui_language), f"{type(exc).__name__}: {exc}")
            return
        self._profile_pending_mode = "inherit"
        self._profile_pending_name = name
        self._profile_pending_modified_at = clean(saved.get("modified_at"))
        self._profile_pending_synced_at = datetime.now().isoformat(timespec="seconds")
        self._refresh_profile_controls(name)
        QMessageBox.information(
            self,
            ui_tr("Reusable Comparison Profile", self.ui_language),
            (
                f"已将“{name}”保存为应用级可复用模板。\n\n模板不会保存任何站点的物理源文件路径；其他站点只复用逻辑配置，并绑定各自的实时源文件。"
                if self.ui_language == LANG_ZH_CN else
                f"Saved '{name}' as an application-wide reusable profile.\n\nPhysical source-file paths were NOT stored in the profile. Other sites can reuse the logical mapping and bind their own live files."
            ),
        )

    def _update_selected_profile(self):
        self._save_current_source_editor()
        self._capture_rule_table()
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(self, ui_tr("Reusable Comparison Profile", self.ui_language), ui_tr("Select a profile first.", self.ui_language))
            return
        if QMessageBox.question(
            self,
            ui_tr("Update Reusable Profile", self.ui_language),
            (
                f"是否用当前站点的逻辑对比配置替换全局模板“{name}”？\n\n其他站点不会被静默修改；它们只会看到模板有更新，必须手工执行“应用 / 同步”。"
                if self.ui_language == LANG_ZH_CN else
                f"Replace global profile '{name}' with the current site's logical comparison configuration?\n\nOther sites are not changed silently; they will see an update available and must Apply / Sync explicitly."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            saved = save_equipment_comparison_profile(name, self.config, self.user_name)
        except Exception as exc:
            QMessageBox.critical(self, ui_tr("Update Reusable Profile", self.ui_language), f"{type(exc).__name__}: {exc}")
            return
        if clean(self._profile_pending_name) == name:
            self._profile_pending_modified_at = clean(saved.get("modified_at"))
            self._profile_pending_synced_at = datetime.now().isoformat(timespec="seconds")
        self._refresh_profile_controls(name)

    def _delete_selected_profile(self):
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(self, ui_tr("Reusable Comparison Profile", self.ui_language), ui_tr("Select a profile first.", self.ui_language))
            return
        if QMessageBox.question(
            self,
            ui_tr("Delete Reusable Profile", self.ui_language),
            (f"删除全局模板“{name}”？\n\n现有站点配置不会改变。" if self.ui_language == LANG_ZH_CN else f"Delete global profile '{name}'?\n\nExisting site configurations remain unchanged."),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            delete_equipment_comparison_profile(name, self.user_name)
        except Exception as exc:
            QMessageBox.critical(self, ui_tr("Delete Reusable Profile", self.ui_language), f"{type(exc).__name__}: {exc}")
            return
        if clean(self._profile_pending_name) == name:
            self._profile_pending_mode = "local"
            self._profile_pending_name = ""
            self._profile_pending_modified_at = ""
            self._profile_pending_synced_at = ""
        self._refresh_profile_controls()

    def _apply_selected_profile(self):
        self._save_current_source_editor()
        self._capture_rule_table()
        name = self._selected_profile_name()
        if not name:
            QMessageBox.information(self, ui_tr("Reusable Comparison Profile", self.ui_language), ui_tr("Select a profile first.", self.ui_language))
            return
        try:
            merged, metadata = apply_equipment_comparison_profile(
                self.store, name, current_config=self.config
            )
        except Exception as exc:
            QMessageBox.critical(self, ui_tr("Apply Comparison Profile", self.ui_language), f"{type(exc).__name__}: {exc}")
            return
        self.config = json.loads(json.dumps(merged, ensure_ascii=False))
        self._profile_pending_mode = "inherit"
        self._profile_pending_name = clean(metadata.get("profile_name")) or name
        self._profile_pending_modified_at = clean(metadata.get("profile_modified_at"))
        self._profile_pending_synced_at = clean(metadata.get("applied_at")) or datetime.now().isoformat(timespec="seconds")
        self._columns_cache.clear()
        self._current_source_id = ""
        self._refresh_source_list()
        self._rebuild_rule_table()
        self._refresh_file_pool()
        if self.source_list.count():
            self.source_list.setCurrentRow(0)
        else:
            self._load_source_editor(None)
        self._refresh_profile_controls(name)
        self._update_validation_text()

    def _source_by_id(self, source_id: str):
        return next((source for source in self.config.get("sources", []) if clean(source.get("id")) == clean(source_id)), None)

    def _current_source(self):
        return self._source_by_id(self._current_source_id)

    def _source_columns(self, source: dict, *, refresh: bool = False):
        source_id = clean((source or {}).get("id"))
        if not source_id:
            return ()
        if not refresh and source_id in self._columns_cache:
            return self._columns_cache[source_id]
        try:
            columns = configurable_source_columns(self.store, source)
        except Exception:
            columns = ()
        self._columns_cache[source_id] = tuple(columns)
        return tuple(columns)

    def _refresh_source_list(self):
        """Rebuild the source list without generating a synthetic selection change.

        v0.8.178 restored the selected row *after* signals were unblocked.  Qt then
        emitted currentItemChanged for that programmatic restore, which could run
        inside a real user selection change and overwrite/load the wrong source
        editor.  Keep signals blocked through the restore so only a real user click
        changes the selected source.
        """
        current = self._current_source_id
        self.source_list.blockSignals(True)
        try:
            self.source_list.clear()
            for source in self.config.get("sources", []):
                path = configurable_source_path(self.store, source)
                title = clean(source.get("title")) or (path.stem if path else "Source")
                key_id = clean(source.get("key_column"))
                key_label = next((column.label for column in self._source_columns(source) if column.id == key_id), ui_tr("Key not set", self.ui_language))
                active = bool(source.get("enabled", True))
                state = ui_tr("ON" if active else "OFF", self.ui_language)
                item = QListWidgetItem(f"{title}  [{state}]\n{key_label}")
                item.setData(Qt.ItemDataRole.UserRole, source.get("id"))
                if not active:
                    item.setForeground(QColor(COLORS["muted"]))
                elif not path or not path.exists() or not key_id:
                    item.setForeground(QColor(COLORS["warning"]))
                self.source_list.addItem(item)
            restore = next((i for i in range(self.source_list.count()) if self.source_list.item(i).data(Qt.ItemDataRole.UserRole) == current), -1)
            if restore >= 0:
                self.source_list.setCurrentRow(restore)
        finally:
            self.source_list.blockSignals(False)

    def _source_selection_changed(self, current, previous):
        """Commit the previous editor, then load exactly the source the user clicked.

        The save path must not rebuild the QListWidget while Qt is delivering its
        currentItemChanged signal.  Doing so invalidates/replaces the current/previous
        QListWidgetItems and was the root cause of the source name changing while the
        Source File field stayed on another workbook.
        """
        if self._loading_source:
            return
        previous_id = clean(previous.data(Qt.ItemDataRole.UserRole)) if previous is not None else clean(self._current_source_id)
        source_id = clean(current.data(Qt.ItemDataRole.UserRole)) if current is not None else ""
        if previous_id and previous_id != source_id:
            self._save_source_editor(previous_id, refresh_ui=False)
        self._current_source_id = source_id
        self._load_source_editor(self._source_by_id(source_id))
        self._rebuild_rule_table()
        self._update_validation_text()

    def _load_source_editor(self, source: dict | None):
        self._loading_source = True
        enabled = bool(source)
        for widget in (self.source_title_edit, self.source_enabled_check, self.version_mode_combo, self.family_key_edit, self.sheet_combo, self.header_row_edit, self.key_combo, self.fields_table):
            widget.setEnabled(enabled)
        if not source:
            self.source_title_edit.clear(); self.source_enabled_check.setChecked(False); self.version_mode_combo.setCurrentIndex(0); self.family_key_edit.clear(); self.source_path_edit.clear(); self.sheet_combo.clear(); self.key_combo.clear(); self.fields_table.setRowCount(0)
            self._loading_source = False
            return
        path = configurable_source_path(self.store, source)
        self.source_title_edit.setText(clean(source.get("title")) or (path.stem if path else "Source"))
        self.source_enabled_check.setChecked(bool(source.get("enabled", True)))
        mode_index = self.version_mode_combo.findData(clean(source.get("selection_mode")) or "pinned")
        self.version_mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 1)
        family = clean(source.get("family_key")) or (configurable_file_family_key(path) if path else "")
        self.family_key_edit.setText(family)
        self.source_path_edit.setText(str(path or ""))
        mode_tip = ui_tr("AUTO latest family resolution" if clean(source.get("selection_mode")) == "latest_family" else "Pinned physical file", self.ui_language)
        resolved_prefix = ui_tr("Resolved:", self.ui_language)
        self.source_path_edit.setToolTip(mode_tip + (("\n" + resolved_prefix + " " + str(path)) if path else ""))
        self.header_row_edit.setText(str(max(1, int(source.get("header_row") or 1))))

        self.sheet_combo.clear()
        if path and path.exists() and path.suffix.lower() in {".xlsx", ".xlsm"}:
            try:
                sheets = list_configurable_sheets(path)
            except Exception:
                sheets = ()
            for name in sheets:
                self.sheet_combo.addItem(name, name)
            selected = clean(source.get("sheet_name"))
            index = self.sheet_combo.findData(selected)
            if index < 0 and self.sheet_combo.count(): index = 0
            self.sheet_combo.setCurrentIndex(index)
        else:
            self.sheet_combo.addItem(ui_tr("CSV / no worksheet", self.ui_language), "")

        self._populate_current_source_fields(source)
        self._loading_source = False

    def _populate_current_source_fields(self, source: dict):
        columns = self._source_columns(source, refresh=True)
        hidden = set(source.get("hidden_columns") or [])
        key_id = clean(source.get("key_column"))
        self.key_combo.blockSignals(True); self.key_combo.clear(); self.key_combo.addItem(ui_tr("Select key / index field...", self.ui_language), "")
        for column in columns:
            self.key_combo.addItem(column.label, column.id)
        key_index = self.key_combo.findData(key_id)
        self.key_combo.setCurrentIndex(key_index if key_index >= 0 else 0)
        self.key_combo.blockSignals(False)

        self.fields_table.blockSignals(True)
        self.fields_table.setRowCount(len(columns))
        for row, column in enumerate(columns):
            show_item = QTableWidgetItem("")
            show_item.setFlags((show_item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsEditable)
            show_item.setCheckState(Qt.Unchecked if column.id in hidden else Qt.Checked)
            show_item.setData(Qt.ItemDataRole.UserRole, column.id)
            show_item.setTextAlignment(Qt.AlignCenter)
            field_item = QTableWidgetItem(column.label)
            field_item.setFlags(field_item.flags() & ~Qt.ItemIsEditable)
            field_item.setToolTip(
                f"{ui_tr('Physical header:', self.ui_language)} {column.header}\n"
                f"{ui_tr('Column position:', self.ui_language)} {column.index + 1}"
            )
            self.fields_table.setItem(row, 0, show_item); self.fields_table.setItem(row, 1, field_item)
        self.fields_table.blockSignals(False)

    def _save_source_editor(self, source_id: str, *, refresh_ui: bool = True):
        """Persist the visible editor widgets into one explicit source record.

        Using an explicit source id is important during currentItemChanged: at that
        moment the editor still belongs to the previous row even though Qt already
        knows which row is becoming current.
        """
        if self._loading_source:
            return
        source = self._source_by_id(source_id)
        if not source:
            return
        path = configurable_source_path(self.store, source)
        source["title"] = clean(self.source_title_edit.text()) or (path.stem if path else "Source")
        source["enabled"] = bool(self.source_enabled_check.isChecked())
        source["selection_mode"] = clean(self.version_mode_combo.currentData()) or "pinned"
        source["family_key"] = clean(self.family_key_edit.text()) or (configurable_file_family_key(path) if path else "")
        source["family_suffix"] = (path.suffix.lower() if path else clean(source.get("family_suffix")))
        try:
            header_row = max(1, int(clean(self.header_row_edit.text()) or 1))
        except (TypeError, ValueError):
            header_row = 1
        self.header_row_edit.setText(str(header_row))
        source["header_row"] = header_row
        source["sheet_name"] = clean(self.sheet_combo.currentData())
        source["key_column"] = clean(self.key_combo.currentData())
        hidden = []
        for row in range(self.fields_table.rowCount()):
            item = self.fields_table.item(row, 0)
            if item and item.checkState() != Qt.Checked:
                column_id = clean(item.data(Qt.ItemDataRole.UserRole))
                if column_id:
                    hidden.append(column_id)
        source["hidden_columns"] = sorted(set(hidden))
        if refresh_ui:
            self._refresh_source_list()
            self._rebuild_rule_table()
            self._update_validation_text()

    def _save_current_source_editor(self):
        self._save_source_editor(self._current_source_id, refresh_ui=True)

    # v0.8.181 ------------------------------------------------------------
    # Site File Pool: discovery and review membership are deliberately
    # separate. A file appearing in the folder is inventory only until the
    # reviewer explicitly assigns it to Equipment Review or Signal Mapping.
    def _refresh_file_pool(self):
        current_path = ""
        item = self.file_pool_list.currentItem() if hasattr(self, "file_pool_list") else None
        if item:
            current_path = clean(item.data(Qt.ItemDataRole.UserRole))
        paths = scan_configurable_site_files(self.store)
        self.file_pool_list.blockSignals(True)
        self.file_pool_list.clear()
        restore_row = -1
        root_text = str((self.store.config or {}).get("repository_path") or "").strip()
        root = Path(root_text) if root_text else None
        for row, path in enumerate(paths):
            try:
                rel = str(path.relative_to(root)) if root is not None else path.name
            except (ValueError, OSError):
                rel = path.name
            usages = configurable_file_pool_usage(self.store, path)
            family = configurable_file_family_key(path)
            family_files = configurable_family_candidates(self.store, family, suffix=path.suffix.lower())
            latest = bool(family_files and family_files[0] == path)
            status = " · ".join(ui_tr(value, self.ui_language) for value in usages) if usages else ui_tr("Unused", self.ui_language)
            version_note = " · " + ui_tr("latest", self.ui_language) if latest and len(family_files) > 1 else ""
            hints = classify_source_detection_hint(path)
            hint_label = clean((hints[0] or {}).get("label")) if hints else ""
            hint_note = (f" · {ui_tr('Recognition hint:', self.ui_language)} {hint_label}" if hint_label else "")
            pool_item = QListWidgetItem(f"{rel}\n{status}{version_note}{hint_note}")
            pool_item.setData(Qt.ItemDataRole.UserRole, str(path))
            pool_item.setData(Qt.ItemDataRole.UserRole + 1, hint_label)
            pool_item.setToolTip(
                f"{ui_tr('File:', self.ui_language)} {path}\n{ui_tr('Family:', self.ui_language)} {family or '-'}\n"
                f"{ui_tr('Family versions:', self.ui_language)} {len(family_files)}\n{ui_tr('Usage:', self.ui_language)} {status}"
                + (f"\n{ui_tr('Recognition hint:', self.ui_language)} {hint_label} ({', '.join((hints[0] or {}).get('keywords') or [])})" if hint_label else "")
                + f"\n{ui_tr('Recognition is optional; manual source configuration is authoritative.', self.ui_language)}"
            )
            self.file_pool_list.addItem(pool_item)
            if current_path and _path_text_equal(current_path, str(path)):
                restore_row = row
        if restore_row >= 0:
            self.file_pool_list.setCurrentRow(restore_row)
        elif self.file_pool_list.count():
            self.file_pool_list.setCurrentRow(0)
        self.file_pool_list.blockSignals(False)

    def _selected_pool_path(self) -> Path | None:
        item = self.file_pool_list.currentItem()
        if not item:
            return None
        text = clean(item.data(Qt.ItemDataRole.UserRole))
        return Path(text) if text else None

    def _append_equipment_source_from_path(self, path: Path, *, auto_family: bool = True) -> dict | None:
        path = Path(path)
        try:
            sheets = list_configurable_sheets(path) if path.suffix.lower() in {".xlsx", ".xlsm"} else ()
            sheet = sheets[0] if sheets else ""
            structure = inspect_configurable_table(path, sheet_name=sheet, header_row=1)
        except Exception as exc:
            QMessageBox.warning(self, ui_tr("Source File", self.ui_language), f"{path.name}: {type(exc).__name__}: {exc}")
            return None
        encoded, path_mode = encode_configurable_source_path(self.store, path)
        source_id = "src_" + hashlib.sha1((str(path.resolve()) + datetime.now().isoformat()).encode("utf-8")).hexdigest()[:12]
        while self._source_by_id(source_id):
            source_id = "src_" + hashlib.sha1((source_id + "x").encode("utf-8")).hexdigest()[:12]
        hints = classify_source_detection_hint(path)
        suggested_title = clean((hints[0] or {}).get("label")) if hints else ""
        source = {
            "id": source_id,
            "title": suggested_title or path.stem,
            "path": encoded,
            "path_mode": path_mode,
            "sheet_name": structure.sheet_name,
            "header_row": 1,
            "key_column": "",
            "hidden_columns": [],
            "enabled": True,
            "selection_mode": "latest_family" if auto_family else "pinned",
            "family_key": configurable_file_family_key(path),
            "family_suffix": path.suffix.lower(),
        }
        self.config.setdefault("sources", []).append(source)
        return source

    def _add_pool_to_equipment(self):
        path = self._selected_pool_path()
        if path is None:
            QMessageBox.information(self, ui_tr("Site File Pool", self.ui_language), ui_tr("Select a site file first.", self.ui_language))
            return
        # If the exact file is already represented, select and enable it rather
        # than creating an accidental duplicate source.
        for existing in self.config.get("sources", []):
            active = configurable_source_path(self.store, existing)
            stored_text = str(existing.get("path") or "").strip()
            stored = None
            if stored_text:
                stored = (Path(str((self.store.config or {}).get("repository_path") or "")) / stored_text) if clean(existing.get("path_mode")) == "site_relative" else Path(stored_text)
            if (active and _path_text_equal(str(active), str(path))) or (stored and _path_text_equal(str(stored), str(path))):
                existing["enabled"] = True
                self._refresh_source_list()
                for row in range(self.source_list.count()):
                    if clean(self.source_list.item(row).data(Qt.ItemDataRole.UserRole)) == clean(existing.get("id")):
                        self.source_list.setCurrentRow(row); break
                self._refresh_file_pool(); self._update_validation_text()
                return
        self._save_current_source_editor()
        source = self._append_equipment_source_from_path(path, auto_family=True)
        if source is None:
            return
        self._columns_cache.clear(); self._refresh_source_list(); self._rebuild_rule_table(); self._refresh_file_pool()
        for row in range(self.source_list.count()):
            if clean(self.source_list.item(row).data(Qt.ItemDataRole.UserRole)) == source["id"]:
                self.source_list.setCurrentRow(row); break
        self._update_validation_text()

    def _assign_pool_to_signal(self):
        path = self._selected_pool_path()
        if path is None:
            QMessageBox.information(self, ui_tr("Site File Pool", self.ui_language), ui_tr("Select a site file first.", self.ui_language))
            return
        role_options = [
            ui_tr("ZENON / IOA source", self.ui_language),
            ui_tr("ADMS SLD source", self.ui_language),
        ]
        role_label, ok = QInputDialog.getItem(
            self, ui_tr("Signal Mapping Source", self.ui_language), ui_tr("Use selected file as:", self.ui_language),
            role_options, 0, False
        )
        if not ok:
            return
        role = "ioa" if role_options.index(role_label) == 0 else "adms_sld"
        mode_options = [
            ui_tr("Latest file in same family (AUTO)", self.ui_language),
            ui_tr("Pin this exact file", self.ui_language),
        ]
        mode_label, ok = QInputDialog.getItem(
            self, ui_tr("Version Selection", self.ui_language), ui_tr("Source version mode:", self.ui_language),
            mode_options, 0, False
        )
        if not ok:
            return
        selection_mode = "latest_family" if mode_options.index(mode_label) == 0 else "pinned"
        save_configurable_signal_assignment(self.store, role, path, selection_mode=selection_mode, title=path.stem)
        self._refresh_file_pool()
        if self.ui_language == LANG_ZH_CN:
            detail = "自动模式会持续跟随该文件系列中的最新版本。" if selection_mode == "latest_family" else "当前物理文件已固定使用。"
            message = f"{path.name} 已指定为 {role_label}。\n\n{detail}"
        else:
            detail = "AUTO will follow the newest file in this filename family." if selection_mode == "latest_family" else "This exact file is pinned."
            message = f"{path.name} is now assigned to {role_label}.\n\n{detail}"
        QMessageBox.information(self, ui_tr("Signal Mapping Source", self.ui_language), message)

    def _toggle_source_enabled(self):
        source = self._current_source()
        if not source:
            return
        source["enabled"] = not bool(source.get("enabled", True))
        self._loading_source = True
        self.source_enabled_check.setChecked(bool(source["enabled"]))
        self._loading_source = False
        self._refresh_source_list(); self._rebuild_rule_table(); self._refresh_file_pool(); self._update_validation_text()

    def _source_enabled_changed(self, checked: bool):
        if self._loading_source:
            return
        source = self._current_source()
        if source:
            source["enabled"] = bool(checked)
            self._refresh_source_list(); self._rebuild_rule_table(); self._refresh_file_pool(); self._update_validation_text()

    def _version_mode_changed(self, _index):
        if self._loading_source:
            return
        source = self._current_source()
        if not source:
            return
        source["selection_mode"] = clean(self.version_mode_combo.currentData()) or "pinned"
        if not clean(source.get("family_key")):
            current = configurable_source_path(self.store, source)
            if current:
                source["family_key"] = configurable_file_family_key(current)
                source["family_suffix"] = current.suffix.lower()
        self._columns_cache.pop(source["id"], None)
        self._load_source_editor(source); self._refresh_source_list(); self._rebuild_rule_table(); self._refresh_file_pool(); self._update_validation_text()

    def _family_key_changed(self):
        if self._loading_source:
            return
        source = self._current_source()
        if not source:
            return
        source["family_key"] = clean(self.family_key_edit.text())
        self._columns_cache.pop(source["id"], None)
        if clean(source.get("selection_mode")) == "latest_family":
            self._load_source_editor(source); self._refresh_source_list(); self._rebuild_rule_table(); self._refresh_file_pool(); self._update_validation_text()

    def _add_sources(self):
        initial = str((Path(str((self.store.config or {}).get("repository_path") or Path.home()))))
        paths, _ = QFileDialog.getOpenFileNames(
            self, ui_tr("Add Comparison Source Tables", self.ui_language), initial,
            ("表格文件 (*.csv *.xlsx *.xlsm)" if self.ui_language == LANG_ZH_CN else "Tabular files (*.csv *.xlsx *.xlsm)")
        )
        if not paths:
            return
        self._save_current_source_editor()
        for text in paths:
            self._append_equipment_source_from_path(Path(text), auto_family=True)
        self._columns_cache.clear()
        self._refresh_source_list(); self._rebuild_rule_table(); self._refresh_file_pool()
        if self.source_list.count(): self.source_list.setCurrentRow(self.source_list.count() - 1)
        self._update_validation_text()

    def _remove_source(self):
        source = self._current_source()
        if not source:
            return
        title = clean(source.get("title")) or "this source"
        remove_text = (
            f"从设备数据审核中移除“{title}”？不会删除物理源文件。"
            if self.ui_language == LANG_ZH_CN else
            f"Remove {title} from Equipment Data Review? The physical file will not be deleted."
        )
        if QMessageBox.question(self, ui_tr("Remove Source", self.ui_language), remove_text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        source_id = source["id"]
        self.config["sources"] = [item for item in self.config.get("sources", []) if item.get("id") != source_id]
        for rule in self.config.get("comparisons", []):
            rule["bindings"] = {k: v for k, v in dict(rule.get("bindings") or {}).items() if k != source_id}
        self._columns_cache.pop(source_id, None)
        self._current_source_id = ""
        self._refresh_source_list(); self._rebuild_rule_table()
        if self.source_list.count(): self.source_list.setCurrentRow(0)
        else: self._load_source_editor(None)
        self._update_validation_text()

    def _replace_current_file(self):
        source = self._current_source()
        if not source:
            return
        old_path = configurable_source_path(self.store, source)
        initial = str(old_path.parent if old_path else Path.home())
        text, _ = QFileDialog.getOpenFileName(
            self, ui_tr("Replace Comparison Source File", self.ui_language), initial,
            ("表格文件 (*.csv *.xlsx *.xlsm)" if self.ui_language == LANG_ZH_CN else "Tabular files (*.csv *.xlsx *.xlsm)")
        )
        if not text:
            return
        path = Path(text)
        try:
            sheets = list_configurable_sheets(path) if path.suffix.lower() in {".xlsx", ".xlsm"} else ()
            sheet = sheets[0] if sheets else ""
            inspect_configurable_table(path, sheet_name=sheet, header_row=1)
        except Exception as exc:
            QMessageBox.warning(self, ui_tr("Source File", self.ui_language), f"{type(exc).__name__}: {exc}")
            return
        encoded, mode = encode_configurable_source_path(self.store, path)
        source["path"] = encoded; source["path_mode"] = mode; source["sheet_name"] = sheet; source["header_row"] = 1
        # Preserve bindings when the same headers exist; missing column ids simply
        # become unbound/invalid and are highlighted by validation until remapped.
        self._columns_cache.pop(source["id"], None)
        self._load_source_editor(source); self._rebuild_rule_table(); self._refresh_source_list(); self._update_validation_text()

    def _sheet_changed(self, _index):
        if self._loading_source:
            return
        source = self._current_source()
        if not source:
            return
        source["sheet_name"] = clean(self.sheet_combo.currentData())
        self._columns_cache.pop(source["id"], None)
        self._populate_current_source_fields(source)
        self._rebuild_rule_table(); self._update_validation_text()

    def _header_row_changed(self):
        if self._loading_source:
            return
        source = self._current_source()
        if not source:
            return
        try:
            value = max(1, int(clean(self.header_row_edit.text()) or 1))
        except ValueError:
            value = 1
        self.header_row_edit.setText(str(value)); source["header_row"] = value
        self._columns_cache.pop(source["id"], None)
        self._populate_current_source_fields(source)
        self._rebuild_rule_table(); self._update_validation_text()

    def _key_changed(self, _index):
        if self._loading_source:
            return
        source = self._current_source()
        if source:
            source["key_column"] = clean(self.key_combo.currentData())
            self._refresh_source_list(); self._update_validation_text()

    def _field_show_changed(self, _item):
        if not self._loading_source:
            self._save_current_source_editor()

    def _default_comparison_mode_changed(self, _index):
        if not hasattr(self, "default_compare_mode_combo"):
            return
        mode = clean(self.default_compare_mode_combo.currentData())
        self.config["default_comparison_mode"] = (
            mode if mode in {COMPARISON_MODE_STRICT, COMPARISON_MODE_IGNORE_BLANK} else COMPARISON_MODE_STRICT
        )
        self._update_validation_text()

    def _rebuild_rule_table(self):
        # Save edited rule names/bindings first when the table already exists.
        self._capture_rule_table()
        sources = list(self.config.get("sources", []))
        headers = [ui_tr("Comparison Field", self.ui_language), ui_tr("Comparison Mode", self.ui_language)] + [
            clean(source.get("title")) or ui_tr("Source", self.ui_language) for source in sources
        ]
        self.rule_table.blockSignals(True)
        self.rule_table.clearContents(); self.rule_table.setColumnCount(len(headers)); self.rule_table.setHorizontalHeaderLabels(headers)
        self.rule_table.setRowCount(len(self.config.get("comparisons", [])))
        self.rule_table.setColumnWidth(0, 180)
        self.rule_table.setColumnWidth(1, 220)
        for col in range(2, len(headers)):
            self.rule_table.setColumnWidth(col, 190)
        for row, rule in enumerate(self.config.get("comparisons", [])):
            name_item = QTableWidgetItem(clean(rule.get("title")) or f"Comparison {row + 1}")
            name_item.setData(Qt.ItemDataRole.UserRole, rule.get("id"))
            self.rule_table.setItem(row, 0, name_item)
            mode_combo = QComboBox()
            mode_combo.addItem(ui_tr("Use site default", self.ui_language), COMPARISON_MODE_DEFAULT)
            mode_combo.addItem(ui_tr("Strict equality · blank participates", self.ui_language), COMPARISON_MODE_STRICT)
            mode_combo.addItem(ui_tr("Ignore blank values", self.ui_language), COMPARISON_MODE_IGNORE_BLANK)
            mode_value = clean(rule.get("comparison_mode")) or COMPARISON_MODE_DEFAULT
            mode_index = mode_combo.findData(mode_value)
            mode_combo.setCurrentIndex(mode_index if mode_index >= 0 else 0)
            self.rule_table.setCellWidget(row, 1, mode_combo)
            bindings = dict(rule.get("bindings") or {})
            for col, source in enumerate(sources, start=2):
                combo = QComboBox(); combo.addItem(ui_tr("— Not compared —", self.ui_language), "")
                for physical in self._source_columns(source):
                    combo.addItem(physical.label, physical.id)
                selected = combo.findData(clean(bindings.get(source.get("id"))))
                combo.setCurrentIndex(selected if selected >= 0 else 0)
                self.rule_table.setCellWidget(row, col, combo)
        self.rule_table.blockSignals(False)

    def _capture_rule_table(self):
        if not hasattr(self, "rule_table") or self.rule_table.rowCount() == 0:
            return
        by_id = {clean(rule.get("id")): rule for rule in self.config.get("comparisons", [])}
        sources = list(self.config.get("sources", []))
        for row in range(self.rule_table.rowCount()):
            item = self.rule_table.item(row, 0)
            if not item:
                continue
            rule_id = clean(item.data(Qt.ItemDataRole.UserRole))
            rule = by_id.get(rule_id)
            if not rule:
                continue
            rule["title"] = clean(item.text()) or "Comparison"
            mode_combo = self.rule_table.cellWidget(row, 1)
            mode = clean(mode_combo.currentData()) if isinstance(mode_combo, QComboBox) else COMPARISON_MODE_DEFAULT
            rule["comparison_mode"] = mode if mode in {COMPARISON_MODE_DEFAULT, COMPARISON_MODE_STRICT, COMPARISON_MODE_IGNORE_BLANK} else COMPARISON_MODE_DEFAULT
            bindings = {}
            for col, source in enumerate(sources, start=2):
                combo = self.rule_table.cellWidget(row, col)
                if isinstance(combo, QComboBox):
                    column_id = clean(combo.currentData())
                    if column_id:
                        bindings[source["id"]] = column_id
            rule["bindings"] = bindings

    def _add_rule(self):
        self._capture_rule_table()
        name, ok = QInputDialog.getText(
            self, ui_tr("Comparison Field", self.ui_language), ui_tr("Field / Analysis title:", self.ui_language)
        )
        name = clean(name)
        if not ok or not name:
            return
        rule_id = "cmp_" + hashlib.sha1((name + datetime.now().isoformat()).encode("utf-8")).hexdigest()[:12]
        self.config.setdefault("comparisons", []).append({
            "id": rule_id, "title": name, "comparison_mode": COMPARISON_MODE_DEFAULT, "bindings": {}
        })
        self._rebuild_rule_table(); self.rule_table.setCurrentCell(self.rule_table.rowCount() - 1, 0); self._update_validation_text()

    def _remove_rule(self):
        self._capture_rule_table()
        row = self.rule_table.currentRow()
        if row < 0 or row >= len(self.config.get("comparisons", [])):
            return
        self.config["comparisons"].pop(row)
        self._rebuild_rule_table(); self._update_validation_text()

    def _validation_errors(self) -> list[str]:
        self._capture_rule_table()
        errors = []
        zh = self.ui_language == LANG_ZH_CN
        if not self.config.get("sources"):
            errors.append("请至少添加一个设备审核数据源。" if zh else "Add at least one source table.")
            return errors
        active_sources = [source for source in self.config.get("sources", []) if bool(source.get("enabled", True))]
        if not active_sources:
            errors.append("请至少启用一个设备数据审核数据源。" if zh else "Enable at least one Equipment Data Review source.")
            return errors
        title_counts = Counter(
            (clean(source.get("title")) or (configurable_source_path(self.store, source).stem if configurable_source_path(self.store, source) else "Source")).casefold()
            for source in self.config.get("sources", [])
        )
        for source in self.config.get("sources", []):
            if not bool(source.get("enabled", True)):
                continue
            path = configurable_source_path(self.store, source)
            title = clean(source.get("title")) or (path.stem if path else "Source")
            if title_counts.get(title.casefold(), 0) > 1:
                errors.append(f"{title}：当前站点内的数据源/模块标题不能重复。" if zh else f"{title}: source/module titles must be unique within this site.")
            if not path or not path.exists():
                errors.append(f"{title}：源文件不存在。" if zh else f"{title}: source file is missing.")
                continue
            columns = self._source_columns(source, refresh=True)
            valid_ids = {column.id for column in columns}
            if not clean(source.get("key_column")) or source.get("key_column") not in valid_ids:
                errors.append(f"{title}：请选择有效的主键 / 索引字段。" if zh else f"{title}: choose a valid Key / Index field.")
        for rule in self.config.get("comparisons", []):
            title = clean(rule.get("title")) or "Comparison"
            valid_binding_count = 0
            for source in active_sources:
                column_id = clean((rule.get("bindings") or {}).get(source.get("id")))
                if column_id and any(column.id == column_id for column in self._source_columns(source)):
                    valid_binding_count += 1
            if valid_binding_count < 2:
                errors.append(
                    f"{title}：至少需要绑定两个数据源字段，才能生成 TRUE/FALSE 比较结果。"
                    if zh else
                    f"{title}: bind at least two source fields so this comparison can produce TRUE/FALSE."
                )
        return errors

    def _update_validation_text(self):
        errors = self._validation_errors() if self.config.get("sources") else [
            "当前还没有配置设备审核数据源。" if self.ui_language == LANG_ZH_CN else "No source table configured yet."
        ]
        if errors:
            prefix = "配置需要处理：" if self.ui_language == LANG_ZH_CN else "Configuration requires attention: "
            self.validation_label.setText(prefix + "  |  ".join(errors[:5]) + (" ..." if len(errors) > 5 else ""))
            self.validation_label.setStyleSheet(f"color:{COLORS['warning']};font-weight:600;")
        else:
            active_count = sum(bool(source.get("enabled", True)) for source in self.config.get("sources", []))
            comparison_count = len(self.config.get("comparisons", []))
            if self.ui_language == LANG_ZH_CN:
                text = f"就绪 · 已启用 {active_count} 个设备审核数据源 · {comparison_count} 个比较字段 · 数据源数量不设固定上限"
            else:
                text = f"Ready · {active_count} Equipment source(s) enabled · {comparison_count} comparison field(s) · no fixed source-count limit"
            self.validation_label.setText(text)
            self.validation_label.setStyleSheet(f"color:{COLORS['success']};font-weight:600;")

    def _accept_config(self):
        self._save_current_source_editor()
        self._capture_rule_table()
        errors = self._validation_errors()
        if errors:
            QMessageBox.warning(self, "Comparison Configuration", "Fix the following before saving:\n\n" + "\n".join(f"• {item}" for item in errors[:12]))
            return
        self.config = save_equipment_comparison_config(self.store, self.config, self.user_name)
        mode = clean(self.profile_mode_combo.currentData()) if hasattr(self, "profile_mode_combo") else "local"
        selected_profile = self._selected_profile_name() if mode == "inherit" else ""
        if mode == "inherit" and not selected_profile:
            QMessageBox.warning(
                self, ui_tr("Comparison Configuration", self.ui_language),
                ui_tr("Inheritance mode requires a reusable profile. Select a profile or switch Mode to Local.", self.ui_language)
            )
            return
        if mode == "inherit":
            profile = get_equipment_comparison_profile(selected_profile) or {}
            # Persist only the inheritance relationship/sync marker. The site's
            # concrete source paths remain entirely in its own configuration.
            save_equipment_comparison_profile_link(
                self.store,
                mode="inherit",
                profile_name=selected_profile,
                profile_modified_at=clean(self._profile_pending_modified_at) or clean(profile.get("modified_at")),
                synced_at=clean(self._profile_pending_synced_at) or datetime.now().isoformat(timespec="seconds"),
            )
        else:
            save_equipment_comparison_profile_link(self.store, mode="local")
        super().accept()


class DerivedTableBuilderDialog(QDialog):
    """Project-local visual ETL builder for derived CSV/XLSX tables.

    The builder is intentionally independent from RMU Data Review and Signal
    Mapping Review. It reuses source mappings, adds optional project-local
    custom fields, joins mapped source tables and calculates output fields.
    """

    def __init__(self, store, source_paths: dict[str, Path | None], user_name: str, parent=None):
        super().__init__(parent)
        self.store = store
        self.source_paths = dict(source_paths or {})
        self.user_name = user_name
        self._loading = False
        self._current_original_name = ""
        self._last_result = None
        self.setWindowTitle("Derived Table Builder")
        self.resize(1420, 860)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        title = QLabel("Derived Table Builder")
        title.setObjectName("SectionTitle")
        root.addWidget(title)
        desc = QLabel(
            "Map existing source tables, add project-local fields, join by business keys, calculate new fields, preview the result and export a new CSV/XLSX. "
            "This builder does not change the existing RMU or Signal validation algorithms."
        )
        desc.setObjectName("Muted"); desc.setWordWrap(True); root.addWidget(desc)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        left = QFrame(); left.setObjectName("SoftCard"); left.setMinimumWidth(230)
        left_box = QVBoxLayout(left); left_box.setContentsMargins(12, 12, 12, 12)
        left_box.addWidget(QLabel("Output Tables"))
        self.derived_list = QListWidget()
        self.derived_list.currentItemChanged.connect(self._table_selected)
        left_box.addWidget(self.derived_list, 1)
        left_buttons = QHBoxLayout()
        new_btn = QPushButton("+ New Table"); new_btn.clicked.connect(self._new_table)
        del_btn = QPushButton("Delete"); del_btn.clicked.connect(self._delete_table)
        left_buttons.addWidget(new_btn); left_buttons.addWidget(del_btn)
        left_box.addLayout(left_buttons)
        splitter.addWidget(left)

        right = QWidget()
        right_box = QVBoxLayout(right); right_box.setContentsMargins(8, 0, 0, 0); right_box.setSpacing(10)
        form_card = QFrame(); form_card.setObjectName("SoftCard")
        form = QGridLayout(form_card); form.setContentsMargins(12, 10, 12, 10)
        form.addWidget(QLabel("Table Name"), 0, 0)
        self.derived_name = QLineEdit(); self.derived_name.setPlaceholderText("e.g. RMU_FINAL")
        form.addWidget(self.derived_name, 0, 1)
        form.addWidget(QLabel("Base Source"), 0, 2)
        self.derived_base = NoWheelComboBox()
        for source_type in available_source_types():
            path = self.source_paths.get(source_type)
            label = source_label(source_type) + ("" if path and Path(path).exists() else "  [Unavailable]")
            self.derived_base.addItem(label, source_type)
        form.addWidget(self.derived_base, 0, 3)
        form.addWidget(QLabel("Description"), 1, 0)
        self.derived_description = QLineEdit(); self.derived_description.setPlaceholderText("Optional business purpose")
        form.addWidget(self.derived_description, 1, 1, 1, 3)
        right_box.addWidget(form_card)

        self.derived_tabs = QTabWidget()
        self.derived_tabs.addTab(self._build_derived_fields_tab(), "Fields")
        self.derived_tabs.addTab(self._build_derived_joins_tab(), "Joins")
        self.derived_tabs.addTab(self._build_derived_preview_tab(), "Preview")
        right_box.addWidget(self.derived_tabs, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0); splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1120])
        root.addWidget(splitter, 1)

        footer = QHBoxLayout()
        self.derived_status = QLabel("Ready")
        self.derived_status.setObjectName("Muted")
        footer.addWidget(self.derived_status, 1)
        save_btn = QPushButton("Save Configuration"); save_btn.clicked.connect(self._save_configuration)
        preview_btn = QPushButton("Preview"); preview_btn.setObjectName("Primary"); preview_btn.clicked.connect(self._preview)
        csv_btn = QPushButton("Export CSV"); csv_btn.clicked.connect(self._export_csv)
        xlsx_btn = QPushButton("Export Excel"); xlsx_btn.clicked.connect(self._export_xlsx)
        close_btn = QPushButton("Close"); close_btn.clicked.connect(self.accept)
        for button in (save_btn, preview_btn, csv_btn, xlsx_btn, close_btn): footer.addWidget(button)
        root.addLayout(footer)
        self._reload_table_list()

    def _build_derived_fields_tab(self):
        page = QWidget(); box = QVBoxLayout(page); box.setContentsMargins(6, 8, 6, 6); box.setSpacing(8)
        helper = QHBoxLayout()
        helper.addWidget(QLabel("Insert Source Field"))
        self.field_source_combo = NoWheelComboBox()
        for source_type in available_source_types(): self.field_source_combo.addItem(source_label(source_type), source_type)
        self.field_source_combo.currentIndexChanged.connect(self._refresh_field_helper)
        self.field_key_combo = NoWheelComboBox()
        insert_btn = QPushButton("Insert Reference")
        insert_btn.clicked.connect(self._insert_field_reference)
        helper.addWidget(self.field_source_combo); helper.addWidget(self.field_key_combo, 1); helper.addWidget(insert_btn)
        box.addLayout(helper)
        formula_help = QLabel(
            "Expressions: adms_db.rmu · COALESCE(adms_db.smart, adms_sld.smart, se.smart) · "
            "IF(NORMALIZE(zenon_sld.feeder) == NORMALIZE(adms_db.gss_fid), \"Closed\", \"Needs Action\") · CONCAT(se.station, \"-\", adms_db.rmu)"
        )
        formula_help.setObjectName("Muted"); formula_help.setWordWrap(True); box.addWidget(formula_help)
        self.derived_fields_table = QTableWidget(0, 3)
        self.derived_fields_table.setHorizontalHeaderLabels(["Output Field", "Internal Key", "Mapping / Formula"])
        _configure_table_base(self.derived_fields_table)
        _set_interactive_column(self.derived_fields_table, 0, 220)
        _set_interactive_column(self.derived_fields_table, 1, 180)
        _set_stretch_column(self.derived_fields_table, 2)
        box.addWidget(self.derived_fields_table, 1)
        buttons = QHBoxLayout(); buttons.addStretch()
        add_btn = QPushButton("+ Add Field"); add_btn.clicked.connect(self._add_output_field)
        remove_btn = QPushButton("Remove Field"); remove_btn.clicked.connect(self._remove_output_field)
        buttons.addWidget(add_btn); buttons.addWidget(remove_btn); box.addLayout(buttons)
        self._refresh_field_helper()
        return page

    def _build_derived_joins_tab(self):
        page = QWidget(); box = QVBoxLayout(page); box.setContentsMargins(6, 8, 6, 6); box.setSpacing(8)
        help_label = QLabel(
            "Start from Base Source, then add joins in order. Left Expression references a source already joined; Right Field belongs to the source on this row. "
            "Example: adms_db.rmu = zenon_sld.rmu. LEFT keeps base rows, INNER keeps matches, FULL also keeps unmatched right-side rows."
        )
        help_label.setObjectName("Muted"); help_label.setWordWrap(True); box.addWidget(help_label)
        self.derived_joins_table = QTableWidget(0, 4)
        self.derived_joins_table.setHorizontalHeaderLabels(["Join Source", "Join Type", "Left Expression", "Right Field"])
        _configure_table_base(self.derived_joins_table)
        _set_interactive_column(self.derived_joins_table, 0, 220)
        _set_fixed_column(self.derived_joins_table, 1, 110)
        _set_stretch_column(self.derived_joins_table, 2)
        _set_interactive_column(self.derived_joins_table, 3, 220)
        box.addWidget(self.derived_joins_table, 1)
        buttons = QHBoxLayout(); buttons.addStretch()
        add_btn = QPushButton("+ Add Join"); add_btn.clicked.connect(self._add_join)
        remove_btn = QPushButton("Remove Join"); remove_btn.clicked.connect(self._remove_join)
        buttons.addWidget(add_btn); buttons.addWidget(remove_btn); box.addLayout(buttons)
        return page

    def _build_derived_preview_tab(self):
        page = QWidget(); box = QVBoxLayout(page); box.setContentsMargins(6, 8, 6, 6)
        self.derived_preview_table = QTableWidget(0, 0)
        _configure_table_base(self.derived_preview_table)
        self.derived_preview_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        box.addWidget(self.derived_preview_table, 1)
        self.preview_note = QLabel("Click Preview to calculate the table. Preview shows up to 500 rows; export writes all rows.")
        self.preview_note.setObjectName("Muted"); box.addWidget(self.preview_note)
        return page

    def _refresh_field_helper(self):
        if not hasattr(self, "field_key_combo"):
            return
        source_type = clean(self.field_source_combo.currentData())
        self.field_key_combo.clear()
        for field in source_field_catalog(self.store, source_type):
            suffix = "  [Custom]" if field.get("custom") else ""
            self.field_key_combo.addItem(f"{field['label']}  ({field['key']}){suffix}", field["key"])

    def _insert_field_reference(self):
        row = self.derived_fields_table.currentRow()
        if row < 0:
            self._add_output_field(); row = self.derived_fields_table.currentRow()
        source_type = clean(self.field_source_combo.currentData())
        field_key = clean(self.field_key_combo.currentData())
        if not source_type or not field_key:
            return
        reference = f"{source_alias(source_type)}.{field_key}"
        item = self.derived_fields_table.item(row, 2)
        if item is None:
            item = QTableWidgetItem(); self.derived_fields_table.setItem(row, 2, item)
        item.setText(reference)

    def _add_output_field(self):
        row = self.derived_fields_table.rowCount(); self.derived_fields_table.insertRow(row)
        name = f"FIELD_{row + 1}"
        self.derived_fields_table.setItem(row, 0, QTableWidgetItem(name))
        self.derived_fields_table.setItem(row, 1, QTableWidgetItem(slug_key(name)))
        source_type = clean(self.field_source_combo.currentData())
        field_key = clean(self.field_key_combo.currentData())
        expression = f"{source_alias(source_type)}.{field_key}" if source_type and field_key else ""
        self.derived_fields_table.setItem(row, 2, QTableWidgetItem(expression))
        self.derived_fields_table.setCurrentCell(row, 0)

    def _remove_output_field(self):
        row = self.derived_fields_table.currentRow()
        if row >= 0: self.derived_fields_table.removeRow(row)

    def _join_source_changed(self, row: int):
        source_combo = self.derived_joins_table.cellWidget(row, 0)
        field_combo = self.derived_joins_table.cellWidget(row, 3)
        if source_combo is None or field_combo is None: return
        source_type = clean(source_combo.currentData())
        current = clean(field_combo.currentData())
        field_combo.clear()
        for field in source_field_catalog(self.store, source_type):
            field_combo.addItem(f"{field['label']} ({field['key']})", field["key"])
        idx = field_combo.findData(current)
        if idx >= 0: field_combo.setCurrentIndex(idx)

    def _join_source_widget_changed(self, combo):
        for row in range(self.derived_joins_table.rowCount()):
            if self.derived_joins_table.cellWidget(row, 0) is combo:
                self._join_source_changed(row)
                return

    def _add_join(self, join: dict | None = None):
        join = dict(join or {})
        row = self.derived_joins_table.rowCount(); self.derived_joins_table.insertRow(row)
        source_combo = NoWheelComboBox()
        for source_type in available_source_types(): source_combo.addItem(source_label(source_type), source_type)
        wanted_source = clean(join.get("source_type"))
        idx = source_combo.findData(wanted_source)
        if idx >= 0: source_combo.setCurrentIndex(idx)
        source_combo.currentIndexChanged.connect(lambda _index, combo=source_combo: self._join_source_widget_changed(combo))
        self.derived_joins_table.setCellWidget(row, 0, source_combo)
        type_combo = NoWheelComboBox()
        for value in ("LEFT", "INNER", "FULL"): type_combo.addItem(value, value)
        idx = type_combo.findData(clean(join.get("join_type") or "LEFT").upper())
        if idx >= 0: type_combo.setCurrentIndex(idx)
        self.derived_joins_table.setCellWidget(row, 1, type_combo)
        left_expression = clean(join.get("left_expression"))
        if not left_expression:
            base_source = clean(self.derived_base.currentData())
            base_catalog = source_field_catalog(self.store, base_source)
            default_left_key = "rmu" if any(item.get("key") == "rmu" for item in base_catalog) else (base_catalog[0]["key"] if base_catalog else "")
            left_expression = f"{source_alias(base_source)}.{default_left_key}" if base_source and default_left_key else ""
        self.derived_joins_table.setItem(row, 2, QTableWidgetItem(left_expression))
        field_combo = NoWheelComboBox(); self.derived_joins_table.setCellWidget(row, 3, field_combo)
        self._join_source_changed(row)
        wanted_field = clean(join.get("right_field"))
        if not wanted_field and field_combo.findData("rmu") >= 0:
            wanted_field = "rmu"
        idx = field_combo.findData(wanted_field)
        if idx >= 0: field_combo.setCurrentIndex(idx)
        self.derived_joins_table.setCurrentCell(row, 2)

    def _remove_join(self):
        row = self.derived_joins_table.currentRow()
        if row >= 0: self.derived_joins_table.removeRow(row)

    def _config_from_ui(self) -> dict:
        name = clean(self.derived_name.text())
        if not name:
            raise ValueError("Table Name cannot be blank.")
        base_source = clean(self.derived_base.currentData())
        fields = []
        seen_names = set()
        for row in range(self.derived_fields_table.rowCount()):
            name_item = self.derived_fields_table.item(row, 0)
            key_item = self.derived_fields_table.item(row, 1)
            expr_item = self.derived_fields_table.item(row, 2)
            field_name = clean(name_item.text() if name_item else "")
            field_key = slug_key(key_item.text() if key_item else field_name, f"field_{row+1}")
            expression = clean(expr_item.text() if expr_item else "")
            if not field_name:
                raise ValueError(f"Output Field row {row + 1} needs a name.")
            if field_name.casefold() in seen_names:
                raise ValueError(f"Duplicate Output Field name: {field_name}")
            seen_names.add(field_name.casefold())
            if not expression:
                raise ValueError(f"Output Field '{field_name}' needs a Mapping / Formula.")
            fields.append({"name": field_name, "key": field_key, "expression": expression})
        joins = []
        for row in range(self.derived_joins_table.rowCount()):
            source_combo = self.derived_joins_table.cellWidget(row, 0)
            type_combo = self.derived_joins_table.cellWidget(row, 1)
            field_combo = self.derived_joins_table.cellWidget(row, 3)
            left_item = self.derived_joins_table.item(row, 2)
            joins.append({
                "source_type": clean(source_combo.currentData() if source_combo else ""),
                "join_type": clean(type_combo.currentData() if type_combo else "LEFT").upper(),
                "left_expression": clean(left_item.text() if left_item else ""),
                "right_field": clean(field_combo.currentData() if field_combo else ""),
            })
        return {
            "table_name": name,
            "description": clean(self.derived_description.text()),
            "base_source_type": base_source,
            "joins": joins,
            "fields": fields,
        }

    def _load_config(self, config: dict):
        self._loading = True
        try:
            self.derived_name.setText(clean(config.get("table_name")))
            self.derived_description.setText(clean(config.get("description")))
            idx = self.derived_base.findData(clean(config.get("base_source_type")))
            if idx >= 0: self.derived_base.setCurrentIndex(idx)
            self.derived_fields_table.setRowCount(0)
            for field in list(config.get("fields") or []):
                row = self.derived_fields_table.rowCount(); self.derived_fields_table.insertRow(row)
                self.derived_fields_table.setItem(row, 0, QTableWidgetItem(clean(field.get("name"))))
                self.derived_fields_table.setItem(row, 1, QTableWidgetItem(clean(field.get("key"))))
                self.derived_fields_table.setItem(row, 2, QTableWidgetItem(clean(field.get("expression"))))
            self.derived_joins_table.setRowCount(0)
            for join in list(config.get("joins") or []): self._add_join(join)
            self._last_result = None
            self.derived_preview_table.setRowCount(0); self.derived_preview_table.setColumnCount(0)
        finally:
            self._loading = False

    def _reload_table_list(self, select_name: str = ""):
        self.derived_list.blockSignals(True)
        self.derived_list.clear()
        configs = self.store.derived_table_configs()
        for item in configs:
            entry = QListWidgetItem(item["table_name"])
            entry.setData(Qt.ItemDataRole.UserRole, item["table_name"])
            self.derived_list.addItem(entry)
        self.derived_list.blockSignals(False)
        if self.derived_list.count():
            target = 0
            for i in range(self.derived_list.count()):
                if clean(self.derived_list.item(i).data(Qt.ItemDataRole.UserRole)) == clean(select_name): target = i; break
            self.derived_list.setCurrentRow(target)
            self._table_selected(self.derived_list.currentItem(), None)
        else:
            config = default_derived_config("RMU_FINAL")
            self._current_original_name = ""
            self._load_config(config)

    def _table_selected(self, current, _previous):
        if not current or self._loading: return
        name = clean(current.data(Qt.ItemDataRole.UserRole) or current.text())
        record = self.store.derived_table_config(name)
        if not record: return
        config = dict(record.get("config") or {})
        config.setdefault("table_name", record.get("table_name"))
        config.setdefault("description", record.get("description"))
        config.setdefault("base_source_type", record.get("base_source_type"))
        self._current_original_name = name
        self._load_config(config)

    def _new_table(self):
        name, ok = QInputDialog.getText(self, "New Output Table", "Table Name:", text="RMU_FINAL")
        name = clean(name)
        if not ok or not name: return
        if self.store.derived_table_config(name):
            QMessageBox.warning(self, "New Output Table", f"A derived table named '{name}' already exists.")
            return
        self._current_original_name = ""
        self._load_config(default_derived_config(name))
        self.derived_name.setFocus()

    def _delete_table(self):
        current = self.derived_list.currentItem()
        if not current: return
        name = clean(current.data(Qt.ItemDataRole.UserRole) or current.text())
        if QMessageBox.question(self, "Delete Output Table", f"Delete derived table configuration '{name}'?\n\nGenerated/exported files are not deleted.") != QMessageBox.Yes:
            return
        self.store.delete_derived_table_config(name, self.user_name)
        self._current_original_name = ""
        self._reload_table_list()

    def _save_configuration(self):
        try:
            config = self._config_from_ui()
            new_name = config["table_name"]
            if self._current_original_name and self._current_original_name != new_name:
                if self.store.derived_table_config(new_name):
                    raise ValueError(f"A derived table named '{new_name}' already exists.")
                self.store.delete_derived_table_config(self._current_original_name, self.user_name)
            self.store.save_derived_table_config(config, self.user_name)
            self._current_original_name = new_name
            self._reload_table_list(new_name)
            self.derived_status.setText(ui_tr(f"Saved · {new_name}", current_language()))
        except Exception as exc:
            QMessageBox.critical(self, "Derived Table Builder", f"{type(exc).__name__}: {exc}")

    def _preview(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            config = self._config_from_ui()
            result = build_derived_table(config, self.store, self.source_paths)
            self._last_result = result
            self.derived_preview_table.clear()
            self.derived_preview_table.setColumnCount(len(result.columns))
            self.derived_preview_table.setHorizontalHeaderLabels(list(result.columns))
            preview_rows = list(result.rows[:500])
            self.derived_preview_table.setRowCount(len(preview_rows))
            for row, values in enumerate(preview_rows):
                for col, name in enumerate(result.columns):
                    self.derived_preview_table.setItem(row, col, QTableWidgetItem(clean(values.get(name))))
            self.derived_preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            for col in range(len(result.columns)):
                self.derived_preview_table.setColumnWidth(col, 170)
            note = f"Rows: {len(result.rows)} · Columns: {len(result.columns)}"
            if result.warnings: note += f" · Formula warnings: {len(result.warnings)} (first: {result.warnings[0]})"
            self.preview_note.setText(ui_tr(note, current_language()))
            self.derived_status.setText(ui_tr(note, current_language()))
            self.derived_tabs.setCurrentIndex(2)
            return result
        except Exception as exc:
            QMessageBox.critical(self, "Derived Table Preview", f"{type(exc).__name__}: {exc}")
            return None
        finally:
            QApplication.restoreOverrideCursor()

    def _result_for_export(self):
        return self._preview()

    def _export_csv(self):
        result = self._result_for_export()
        if result is None: return
        name = slug_key(self.derived_name.text(), "derived_table").upper()
        path, _ = QFileDialog.getSaveFileName(self, "Export Derived CSV", str(self.store.generated_dir / f"{name}.csv"), "CSV (*.csv)")
        if not path: return
        try:
            target = export_derived_csv(result, Path(path))
            self.derived_status.setText(ui_tr(f"Exported · {target}", current_language()))
        except Exception as exc: QMessageBox.critical(self, "Export Derived CSV", f"{type(exc).__name__}: {exc}")

    def _export_xlsx(self):
        result = self._result_for_export()
        if result is None: return
        name = slug_key(self.derived_name.text(), "derived_table").upper()
        path, _ = QFileDialog.getSaveFileName(self, "Export Derived Excel", str(self.store.generated_dir / f"{name}.xlsx"), "Excel Workbook (*.xlsx)")
        if not path: return
        try:
            target = export_derived_xlsx(result, Path(path))
            self.derived_status.setText(ui_tr(f"Exported · {target}", current_language()))
        except Exception as exc: QMessageBox.critical(self, "Export Derived Excel", f"{type(exc).__name__}: {exc}")


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


class SignalActionRemarkDialog(QDialog):
    """Capture one concrete signal rectification action and its mandatory remark.

    Both values are persisted together in the existing Comments field.  The PDF
    later splits the structured text into Action and Remarks columns.
    """

    def __init__(self, *, rmu: str = "", current_comment: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Signal Action / Remark")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        title = QLabel(f"RMU {clean(rmu) or '—'} · Signal rectification")
        title.setStyleSheet("font-size:12pt;font-weight:750;")
        root.addWidget(title)

        hint = QLabel(
            "Choose the actual rectification action, then enter the reviewer remark. "
            "Both are required and are saved together in Comments."
        )
        hint.setWordWrap(True)
        hint.setObjectName("Muted")
        root.addWidget(hint)

        form = QFormLayout()
        self.action_combo = QComboBox()
        self.action_combo.addItem("Choose action...", "")
        for action in SIGNAL_ACTIONS:
            self.action_combo.addItem(action, action)
        self.remark_edit = QTextEdit()
        self.remark_edit.setPlaceholderText("Required remark / agreed rectification note...")
        self.remark_edit.setMinimumHeight(110)
        form.addRow("Action", self.action_combo)
        form.addRow("Remark", self.remark_edit)
        root.addLayout(form)

        current_action, current_remark = parse_signal_action_comment(current_comment)
        if current_action:
            index = self.action_combo.findData(current_action)
            if index >= 0:
                self.action_combo.setCurrentIndex(index)
        if current_remark:
            self.remark_edit.setPlainText(current_remark)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._accept_checked)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self._update_ok_state()
        self.action_combo.currentIndexChanged.connect(self._update_ok_state)
        self.remark_edit.textChanged.connect(self._update_ok_state)

    def _update_ok_state(self) -> None:
        button = self.buttons.button(QDialogButtonBox.Ok)
        if button is not None:
            button.setEnabled(bool(clean(self.action_combo.currentData()) and clean(self.remark_edit.toPlainText())))

    def _accept_checked(self) -> None:
        if not clean(self.action_combo.currentData()) or not clean(self.remark_edit.toPlainText()):
            QMessageBox.information(self, "Signal Action / Remark", "Select ADD / MODIFY / DELETE and enter a remark before saving.")
            return
        self.accept()

    def action(self) -> str:
        return clean(self.action_combo.currentData()).upper()

    def remark(self) -> str:
        return clean(self.remark_edit.toPlainText())

    def stored_comment(self) -> str:
        return format_signal_action_comment(self.action(), self.remark())


class IssueLifecycleDialog(QDialog):
    """Read-only case/timeline viewer for RMU and Signal Needs Action history."""

    def __init__(self, store: ProjectStore, entity_type: str, entity_key: str, parent=None):
        super().__init__(parent)
        self.store = store
        self.entity_type = clean(entity_type).upper()
        self.entity_key = clean(entity_key)
        self.cases = store.issue_lifecycle(self.entity_type, self.entity_key)
        self.setWindowTitle(f"{self.entity_type} Need Action Lifecycle")
        self.resize(1180, 720)

        root = QVBoxLayout(self)
        latest = self.cases[0] if self.cases else {}
        identity = clean(latest.get("rmu")) or self.entity_key
        if self.entity_type == "SIGNAL":
            point = clean(latest.get("point_no"))
            signal = clean(latest.get("signal_name"))
            identity = f"RMU {clean(latest.get('rmu')) or '—'} · Point {point or '—'} · {signal or 'Signal'}"
        title = QLabel(f"{self.entity_type} Lifecycle · {identity}")
        title.setStyleSheet("font-size:14pt;font-weight:800;")
        root.addWidget(title)
        note = QLabel(
            "Append-only lifecycle history from the first formal Needs Action through comments/resolutions/actions, "
            "validation changes and explicit closure. Closed items reopened later start a new case."
        )
        note.setObjectName("Muted"); note.setWordWrap(True)
        root.addWidget(note)

        summary = QLabel()
        summary.setObjectName("Muted")
        if self.cases:
            participants = set()
            total_events = 0
            for case in self.cases:
                total_events += len(case.get("events") or [])
                for event in case.get("events") or []:
                    user = clean(event.get("modified_by"))
                    if user.upper() not in {"", "SYSTEM", "MIGRATION"}:
                        participants.add(user)
            summary.setText(
                f"Cases {len(self.cases)} · Current {clean(latest.get('status')) or '—'} · "
                f"Participants {len(participants)} · Events {total_events}"
            )
        else:
            summary.setText("No formal Needs Action lifecycle has been recorded for this item.")
        root.addWidget(summary)

        splitter = QSplitter(Qt.Vertical)
        self.case_table = QTableWidget(0, 10)
        self.case_table.setHorizontalHeaderLabels([
            "Case", "Status", "Opened", "Opened By", "Closed", "Closed By",
            "Participants", "Events", "Reason", "App Version"
        ])
        _configure_table_base(self.case_table)
        for col, width in enumerate((72, 90, 165, 120, 165, 120, 95, 78, 300, 100)):
            if col == 8:
                _set_stretch_column(self.case_table, col)
            else:
                _set_fixed_column(self.case_table, col, width)
        self.case_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.case_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.case_table.itemSelectionChanged.connect(self._case_selection_changed)
        splitter.addWidget(self.case_table)

        lower = QWidget(); lower_box = QVBoxLayout(lower); lower_box.setContentsMargins(0, 0, 0, 0)
        self.event_table = QTableWidget(0, 8)
        self.event_table.setHorizontalHeaderLabels([
            "Time", "User", "Event", "Field", "Before", "After", "Reason", "App Version"
        ])
        _configure_table_base(self.event_table)
        _set_fixed_column(self.event_table, 0, 170)
        _set_fixed_column(self.event_table, 1, 120)
        _set_fixed_column(self.event_table, 2, 155)
        _set_fixed_column(self.event_table, 3, 170)
        _set_interactive_column(self.event_table, 4, 230)
        _set_interactive_column(self.event_table, 5, 230)
        _set_stretch_column(self.event_table, 6)
        _set_fixed_column(self.event_table, 7, 100)
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.event_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.event_table.itemSelectionChanged.connect(self._event_selection_changed)
        lower_box.addWidget(self.event_table, 1)
        self.snapshot_view = QTextEdit(); self.snapshot_view.setReadOnly(True)
        self.snapshot_view.setPlaceholderText("Select an event to inspect the frozen lifecycle snapshot.")
        self.snapshot_view.setMaximumHeight(155)
        lower_box.addWidget(self.snapshot_view)
        splitter.addWidget(lower)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject); buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
        self._load_cases()

    def _load_cases(self) -> None:
        self.case_table.setRowCount(len(self.cases))
        for r, case in enumerate(self.cases):
            reason = clean(case.get("close_reason")) if clean(case.get("status")).upper() == "CLOSED" else clean(case.get("open_reason"))
            values = [
                f"#{int(case.get('case_no') or 0):03d}", case.get("status"), case.get("opened_at"), case.get("opened_by"),
                case.get("closed_at"), case.get("closed_by"), case.get("participant_count"), case.get("event_count"),
                reason, case.get("app_version"),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(clean(value)); item.setToolTip(item.text())
                if c == 1:
                    status = clean(value).upper()
                    if status == "OPEN":
                        item.setBackground(QColor("#FDECEC")); item.setForeground(QColor("#B42318"))
                    elif status == "CLOSED":
                        item.setBackground(QColor("#E8F5EE")); item.setForeground(QColor("#116A4D"))
                self.case_table.setItem(r, c, item)
        if self.cases:
            self.case_table.selectRow(0)
            self._render_case_events(0)

    def _case_selection_changed(self) -> None:
        row = self.case_table.currentRow()
        if row >= 0:
            self._render_case_events(row)

    def _render_case_events(self, case_row: int) -> None:
        if not (0 <= case_row < len(self.cases)):
            self.event_table.setRowCount(0); self.snapshot_view.clear(); return
        events = list(self.cases[case_row].get("events") or [])
        self.event_table.setRowCount(len(events))
        for r, event in enumerate(events):
            values = [
                event.get("modified_at"), event.get("modified_by"), event.get("event_type"), event.get("field_name"),
                event.get("old_value"), event.get("new_value"), event.get("reason"), event.get("app_version"),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(clean(value)); item.setToolTip(item.text())
                self.event_table.setItem(r, c, item)
        if events:
            self.event_table.selectRow(len(events) - 1)
            self._render_event_snapshot(events[-1])
        else:
            self.snapshot_view.clear()

    def _event_selection_changed(self) -> None:
        case_row = self.case_table.currentRow(); event_row = self.event_table.currentRow()
        if not (0 <= case_row < len(self.cases)):
            return
        events = list(self.cases[case_row].get("events") or [])
        if 0 <= event_row < len(events):
            self._render_event_snapshot(events[event_row])

    def _render_event_snapshot(self, event: dict) -> None:
        raw = event.get("snapshot_json") or "{}"
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
            text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception:
            text = str(raw)
        self.snapshot_view.setPlainText(text)


class RMUFullLifecycleDialog(QDialog):
    """Read-only equipment lifecycle viewer; RMU may additionally include child Signal cases."""

    def __init__(self, store: ProjectStore, rmu: str, parent=None, *, equipment_type: str = "RMU", display_name: str = ""):
        super().__init__(parent)
        self.store = store
        self.rmu = clean(rmu)
        self.equipment_type = clean(equipment_type).upper() or "RMU"
        self.display_name = clean(display_name) or self.rmu
        self.include_signals = self.equipment_type == "RMU" and not self.rmu.upper().startswith("EQ::")
        self.payload = (store.equipment_full_lifecycle(self.rmu) if hasattr(store, "equipment_full_lifecycle") else store.rmu_full_lifecycle(self.rmu))
        if not self.include_signals:
            # Non-RMU equipment reuses the durable legacy lifecycle engine but
            # intentionally excludes Signal Mapping rows from its equipment story.
            self.payload = dict(self.payload)
            self.payload["cases"] = [c for c in (self.payload.get("cases") or []) if clean(c.get("entity_type")).upper() == "RMU"]
            self.payload["events"] = [e for e in (self.payload.get("events") or []) if clean(e.get("entity_type")).upper() == "RMU"]
            self.payload["case_count"] = len(self.payload["cases"])
            self.payload["open_count"] = sum(clean(c.get("status")).upper() == "OPEN" for c in self.payload["cases"])
            self.payload["closed_count"] = sum(clean(c.get("status")).upper() == "CLOSED" for c in self.payload["cases"])
            self.payload["signal_case_count"] = 0
            self.payload["rmu_case_count"] = len(self.payload["cases"])
            self.payload["event_count"] = len(self.payload["events"])
        formal_events = [
            event for event in (self.payload.get("events") or [])
            if not (
                clean(event.get("entity_type")).upper() == "RMU"
                and clean(event.get("event_type")).upper() == "COMMENT_CHANGED"
            )
        ]
        review_events = []
        for event in (self.payload.get("review_events") or []):
            field = clean(event.get("analysis_field")).upper()
            comment = clean(event.get("comment"))
            review_events.append({
                "id": int(event.get("id") or 0),
                "modified_at": clean(event.get("modified_at")),
                "entity_type": "RMU",
                "case_no": int(event.get("case_no") or 0),
                "event_state": clean(event.get("review_status")) or "UNREVIEWED",
                "point_no": "",
                "signal_name": "",
                "event_type": clean(event.get("event_type")) or "COMMENT_RECORDED",
                "field_name": f"comment.{field}" if field else "comment",
                "old_value": "",
                "new_value": comment or ("<cleared>" if clean(event.get("event_type")).upper().endswith("CLEARED") else ""),
                "reason": "Independent customer/reviewer comment",
                "modified_by": clean(event.get("modified_by")),
                "snapshot_json": event.get("snapshot_json") or "{}",
                "_review_note": True,
            })
        self.events = formal_events + review_events
        self.events.sort(key=lambda event: (clean(event.get("modified_at")), 1 if event.get("_review_note") else 0, int(event.get("id") or 0)))
        self.setWindowTitle(f"{self.equipment_type} {self.display_name} Full Lifecycle")
        self.resize(1380, 780)

        root = QVBoxLayout(self)
        title = QLabel(f"{self.equipment_type} Full Lifecycle · {self.display_name}")
        title.setStyleSheet("font-size:14pt;font-weight:800;")
        root.addWidget(title)
        note = QLabel(
            (
                "Combined append-only history for this RMU and every Signal Mapping Needs Action case linked to it. "
                "Independent RMU customer/reviewer comments are also included, including comments recorded before the first Needs Action case. "
                if self.include_signals else
                "Append-only equipment review history. Signal Mapping child cases are included only when this equipment is an RMU. "
            )
            + "The timeline preserves reopen/close cycles, Resolution choices, review comments, manual checks and validation-result changes."
        )
        note.setObjectName("Muted"); note.setWordWrap(True)
        root.addWidget(note)

        self.summary = QLabel(self._summary_text())
        self.summary.setObjectName("Muted")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        splitter = QSplitter(Qt.Vertical)
        self.case_table = QTableWidget(0, 12)
        self.case_table.setHorizontalHeaderLabels([
            "Scope", "Case", "Final Status", "Point", "Signal", "Opened", "Opened By",
            "Closed", "Closed By", "Participants", "Events", "Reason"
        ])
        _configure_table_base(self.case_table)
        for col, width in enumerate((82, 72, 90, 90, 260, 165, 120, 165, 120, 95, 78, 320)):
            if col in {4, 11}:
                _set_stretch_column(self.case_table, col)
            else:
                _set_fixed_column(self.case_table, col, width)
        self.case_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.case_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.case_table.cellDoubleClicked.connect(self._open_exact_case)
        splitter.addWidget(self.case_table)

        lower = QWidget(); lower_box = QVBoxLayout(lower); lower_box.setContentsMargins(0, 0, 0, 0)
        self.event_table = QTableWidget(0, 11)
        self.event_table.setHorizontalHeaderLabels([
            "Time", "Scope", "Case", "State at Event", "Point", "Signal", "Event",
            "Field", "Before → After", "Reason", "User"
        ])
        _configure_table_base(self.event_table)
        for col, width in enumerate((170, 82, 72, 95, 90, 250, 155, 160, 320, 360, 120)):
            if col in {5, 8, 9}:
                _set_stretch_column(self.event_table, col)
            else:
                _set_fixed_column(self.event_table, col, width)
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.event_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.event_table.itemSelectionChanged.connect(self._event_selection_changed)
        lower_box.addWidget(self.event_table, 1)
        self.snapshot_view = QTextEdit(); self.snapshot_view.setReadOnly(True)
        self.snapshot_view.setPlaceholderText("Select an event to inspect its frozen lifecycle snapshot.")
        self.snapshot_view.setMaximumHeight(160)
        lower_box.addWidget(self.snapshot_view)
        splitter.addWidget(lower)
        splitter.setStretchFactor(0, 1); splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject); buttons.accepted.connect(self.accept)
        root.addWidget(buttons)
        self._load_cases()
        self._load_events()

    def _summary_text(self) -> str:
        p = self.payload
        if not p.get("case_count"):
            return "No formal Needs Action lifecycle has been recorded for this equipment."
        scope_text = (
            f"RMU cases {p.get('rmu_case_count', 0)} · Signal cases {p.get('signal_case_count', 0)} · "
            if self.include_signals else f"Equipment cases {p.get('rmu_case_count', 0)} · "
        )
        return (
            f"Cases {p.get('case_count', 0)} · Open {p.get('open_count', 0)} · Closed {p.get('closed_count', 0)} · "
            + scope_text +
            f"Formal events {p.get('event_count', 0)} · Review notes {p.get('review_event_count', 0)} · "
            f"Participants {p.get('participant_count', 0)} · First {clean(p.get('first_activity_at')) or '—'} · "
            f"Last {clean(p.get('last_activity_at')) or '—'}"
        )

    def _load_cases(self) -> None:
        cases = list(self.payload.get("cases") or [])
        self.case_table.setRowCount(len(cases))
        for r, case in enumerate(cases):
            status = clean(case.get("status")).upper()
            reason = clean(case.get("close_reason")) if status == "CLOSED" else clean(case.get("open_reason"))
            values = [
                case.get("entity_type"), f"#{int(case.get('case_no') or 0):03d}", status,
                case.get("point_no"), case.get("signal_name"), case.get("opened_at"), case.get("opened_by"),
                case.get("closed_at"), case.get("closed_by"), case.get("participant_count"), case.get("event_count"), reason,
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(clean(value)); item.setToolTip(item.text())
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, (clean(case.get("entity_type")), clean(case.get("entity_key"))))
                if c == 2:
                    if status == "OPEN":
                        item.setBackground(QColor("#FDECEC")); item.setForeground(QColor("#B42318"))
                    elif status == "CLOSED":
                        item.setBackground(QColor("#E8F5EE")); item.setForeground(QColor("#116A4D"))
                    font = item.font(); font.setBold(True); item.setFont(font)
                self.case_table.setItem(r, c, item)

    def _load_events(self) -> None:
        self.event_table.setRowCount(len(self.events))
        for r, event in enumerate(self.events):
            before = clean(event.get("old_value")); after = clean(event.get("new_value"))
            change = f"{before} → {after}" if before or after else "—"
            values = [
                event.get("modified_at"), event.get("entity_type"), f"#{int(event.get('case_no') or 0):03d}",
                event.get("event_state"), event.get("point_no"), event.get("signal_name"), event.get("event_type"),
                event.get("field_name"), change, event.get("reason"), event.get("modified_by"),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(clean(value)); item.setToolTip(item.text())
                if c == 3:
                    status = clean(value).upper()
                    if status in {"OPEN", "NEEDS ACTION"}:
                        item.setBackground(QColor("#FDECEC")); item.setForeground(QColor("#B42318"))
                    elif status == "UNREVIEWED":
                        item.setBackground(QColor("#FFF8D8")); item.setForeground(QColor("#6B4F00"))
                    elif status == "CLOSED":
                        item.setBackground(QColor("#E8F5EE")); item.setForeground(QColor("#116A4D"))
                self.event_table.setItem(r, c, item)
        if self.events:
            self.event_table.selectRow(len(self.events) - 1)
            self.event_table.scrollToBottom()
            self._render_event_snapshot(self.events[-1])

    def _open_exact_case(self, row: int, _column: int = 0) -> None:
        item = self.case_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if data and len(data) == 2:
            IssueLifecycleDialog(self.store, data[0], data[1], self).exec()

    def _event_selection_changed(self) -> None:
        row = self.event_table.currentRow()
        if 0 <= row < len(self.events):
            self._render_event_snapshot(self.events[row])

    def _render_event_snapshot(self, event: dict) -> None:
        raw = event.get("snapshot_json") or "{}"
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
            text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception:
            text = str(raw)
        self.snapshot_view.setPlainText(text)


class IssueActionDialog(QDialog):
    """Small business-facing editor for the persistent site issue/action register."""

    def __init__(self, revisions: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Issue / Action")
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        title = QLabel("Site Issue / Action Record")
        title.setObjectName("SectionTitle")
        subtitle = QLabel(
            "This record is stored in the selected site's persistent Project Data and remains available after application upgrades."
        )
        subtitle.setObjectName("Muted")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)

        form = QFormLayout()
        form.setSpacing(10)
        self.revision_combo = QComboBox()
        self.revision_combo.addItem("Current / No named revision", None)
        for revision in revisions:
            self.revision_combo.addItem(
                f"{clean(revision.get('revision_name'))} · {clean(revision.get('created_at'))}",
                revision.get("id"),
            )

        self.category_combo = QComboBox()
        self.category_combo.addItems(["RMU", "Analog", "Feeder", "Signal Mapping", "SLD", "Database", "Other"])
        self.equipment_edit = QLineEdit()
        self.equipment_edit.setPlaceholderText("RMU name / feeder / signal / equipment ID")
        self.issue_edit = QTextEdit()
        self.issue_edit.setMinimumHeight(86)
        self.issue_edit.setPlaceholderText("Describe the issue found at this site")
        self.action_edit = QTextEdit()
        self.action_edit.setMinimumHeight(86)
        self.action_edit.setPlaceholderText("Describe the action taken or required")
        self.result_combo = QComboBox()
        self.result_combo.addItems(["OPEN", "NEEDS ACTION", "PASS", "CLOSED", "N/A"])
        self.comments_edit = QTextEdit()
        self.comments_edit.setMinimumHeight(68)
        self.comments_edit.setPlaceholderText("Optional notes")

        form.addRow("Revision", self.revision_combo)
        form.addRow("Category", self.category_combo)
        form.addRow("Equipment", self.equipment_edit)
        form.addRow("Issue", self.issue_edit)
        form.addRow("Action Taken", self.action_edit)
        form.addRow("Result", self.result_combo)
        form.addRow("Comments", self.comments_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setObjectName("Primary")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self):
        if not self.issue_edit.toPlainText().strip():
            QMessageBox.warning(self, "Issue required", "Enter the issue description before saving.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "revision_id": self.revision_combo.currentData(),
            "category": self.category_combo.currentText(),
            "equipment": self.equipment_edit.text().strip(),
            "issue": self.issue_edit.toPlainText().strip(),
            "action_taken": self.action_edit.toPlainText().strip(),
            "result": self.result_combo.currentText(),
            "comments": self.comments_edit.toPlainText().strip(),
        }


class InitialSetupDialog(QDialog):
    """First-run storage/source guidance without changing validation logic."""

    def __init__(self, repository_root: Path | None, project_root: Path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set up Migration Report Tool")
        self.setModal(True)
        self.resize(760, 430)
        self._repository_root = Path(repository_root).resolve() if repository_root else None
        self._project_root = Path(project_root).resolve()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Choose your source workspace and Project Data storage")
        title.setObjectName("SectionTitle")
        title.setStyleSheet("font-size:16pt;font-weight:750;color:#173A5E;")
        layout.addWidget(title)
        desc = QLabel(
            "The app reads migration source files from the Source Workspace and stores review history, "
            "comments, resolutions, revisions and generated reports under Project Data. "
            "These locations are remembered for future launches and can be changed later in Settings."
        )
        desc.setWordWrap(True)
        desc.setObjectName("Muted")
        layout.addWidget(desc)

        source_card = QFrame(); source_card.setObjectName("SoftCard")
        source_box = QVBoxLayout(source_card); source_box.setContentsMargins(16, 14, 16, 14); source_box.setSpacing(7)
        source_title = QLabel("1  Source Workspace (read-only)"); source_title.setStyleSheet("font-weight:700;color:#173A5E;")
        source_help = QLabel("Choose the folder that contains one subfolder per site and the source CSV/XLSX files used by the migration review.")
        source_help.setWordWrap(True); source_help.setObjectName("Muted")
        source_line = QHBoxLayout()
        self.source_edit = QLineEdit(str(self._repository_root) if self._repository_root else "")
        self.source_edit.setReadOnly(True); self.source_edit.setPlaceholderText("Not configured")
        source_browse = QPushButton("Browse..."); source_browse.clicked.connect(self._browse_source)
        source_line.addWidget(self.source_edit, 1); source_line.addWidget(source_browse)
        source_box.addWidget(source_title); source_box.addWidget(source_help); source_box.addLayout(source_line)
        layout.addWidget(source_card)

        project_card = QFrame(); project_card.setObjectName("SoftCard")
        project_box = QVBoxLayout(project_card); project_box.setContentsMargins(16, 14, 16, 14); project_box.setSpacing(7)
        project_title = QLabel("2  Project Data Storage (writable)"); project_title.setStyleSheet("font-weight:700;color:#173A5E;")
        project_help = QLabel("Choose where the app keeps project.db, Review/Needs Action decisions, Comments, Change Audit, revisions and report snapshots. Keep this outside the release folder.")
        project_help.setWordWrap(True); project_help.setObjectName("Muted")
        project_line = QHBoxLayout()
        self.project_edit = QLineEdit(str(self._project_root)); self.project_edit.setReadOnly(True)
        project_browse = QPushButton("Browse..."); project_browse.clicked.connect(self._browse_project)
        project_line.addWidget(self.project_edit, 1); project_line.addWidget(project_browse)
        project_box.addWidget(project_title); project_box.addWidget(project_help); project_box.addLayout(project_line)
        layout.addWidget(project_card)

        note = QLabel("You can choose Configure Later. The app will keep showing a setup reminder until the required locations are configured.")
        note.setWordWrap(True); note.setObjectName("Muted")
        layout.addWidget(note)

        buttons = QHBoxLayout(); buttons.addStretch()
        later = QPushButton("Configure Later"); later.clicked.connect(self.reject)
        save = QPushButton("Save & Continue"); save.setObjectName("Primary"); save.clicked.connect(self._save)
        buttons.addWidget(later); buttons.addWidget(save)
        layout.addLayout(buttons)

    def _browse_source(self):
        initial = self.source_edit.text().strip() or str(Path.home())
        value = QFileDialog.getExistingDirectory(self, "Select Source Workspace", initial)
        if value:
            self.source_edit.setText(str(Path(value).resolve()))

    def _browse_project(self):
        initial = self.project_edit.text().strip() or str(Path.home())
        value = QFileDialog.getExistingDirectory(self, "Select Project Data Storage", initial)
        if value:
            self.project_edit.setText(str(Path(value).resolve()))

    def _save(self):
        source = Path(self.source_edit.text().strip()).expanduser() if self.source_edit.text().strip() else None
        project = Path(self.project_edit.text().strip()).expanduser() if self.project_edit.text().strip() else None
        if source is None or not source.exists() or not source.is_dir():
            QMessageBox.warning(self, "Source Workspace required", "Choose an existing Source Workspace folder before continuing.")
            return
        if project is None:
            QMessageBox.warning(self, "Project Data required", "Choose a Project Data storage folder before continuing.")
            return
        try:
            project.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Project Data unavailable", f"The selected Project Data folder cannot be created or opened:\n{exc}")
            return
        source_resolved = source.resolve()
        project_resolved = project.resolve()
        try:
            project_resolved.relative_to(source_resolved)
            nested = True
        except ValueError:
            nested = False
        try:
            source_resolved.relative_to(project_resolved)
            nested = True
        except ValueError:
            pass
        if nested:
            QMessageBox.warning(
                self, "Use separate folders",
                "Source Workspace and Project Data Storage must be separate locations. "
                "Project Data should not be stored inside the read-only source workspace."
            )
            return
        self._repository_root = source_resolved
        self._project_root = project_resolved
        self.accept()

    def selected_paths(self) -> tuple[Path | None, Path]:
        return self._repository_root, self._project_root


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
        # Signal Mapping is expensive to rebuild (CSV/XLSX parsing + thousands
        # of QTableWidgetItems). Keep one in-memory report per active site and
        # only rebuild it after an explicit source/mapping refresh or validation.
        self._db_smart_report_site: str = ""
        self._db_smart_ui_ready = False
        self._db_smart_selected_rmu: str = ""
        self._db_smart_signal_category: str = "STATUS_CMD"
        self._site_source_status_cache: dict[str, tuple[tuple, dict]] = {}
        self._schema_validation_cache: dict[tuple, object] = {}
        self._active_site_signature: tuple = ()
        self._repository_refreshing = False
        # Heavy pages are populated lazily.  Site switching only binds the
        # persistent store and updates the lightweight source inventory; large
        # QTableWidget grids are rebuilt only when their module is opened.
        self._dirty_pages: set[int] = set(range(9))
        self._startup_repository_loaded = False
        self._startup_setup_checked = False
        self._spreadsheet_tables: list[SpreadsheetTableWidget] = []
        # Shared worker pool: file scans, source parsing, validation and
        # resolution persistence run outside the Qt GUI thread.  This machine is
        # expected to have abundant CPU/RAM, so allow multiple independent jobs
        # to progress concurrently without serializing unrelated I/O.
        self.thread_pool = QThreadPool(self)
        self.thread_pool.setMaxThreadCount(max(8, min(32, (os.cpu_count() or 4) * 2)))
        self._background_tasks: dict[str, object] = {}
        # One shared popup is the only operational progress surface. Keys allow
        # overlapping work to coexist without creating multiple progress bars.
        # Tuple = (title, detail, determinate percent or None for busy animation).
        self._busy_popup_operations: dict[str, tuple[str, str, int | None]] = {}
        # Cheap live-source watcher: only stat() the seven active source files.
        # It never opens CSV/XLSX content on the GUI thread. Changed files are
        # re-read in the background and only affected review modules are rebuilt.
        self._source_watch_timer = QTimer(self)
        self._source_watch_timer.setInterval(5000)
        self._source_watch_timer.timeout.connect(self._check_live_source_changes)
        self._source_watch_last_trigger: tuple = ()
        # RMU Data Review contains many thousands of QTableWidgetItems once all
        # source columns are visible.  Rendering those cells in one GUI-thread
        # burst makes navigation appear frozen even though the underlying RMU
        # calculation is already cached in project.db.  Render the grid in
        # short event-loop batches instead, and cancel stale batches whenever a
        # new filter/site refresh starts.
        self._comparison_render_generation = 0
        self._comparison_render_in_progress = False
        self._comparison_render_batch_size = 24
        self._comparison_render_context: dict | None = None
        # v0.8.196 interaction cache.  Once a site's Equipment Review payload
        # has been prepared, reviewer operations must not rebuild live Excel/CSV
        # projections or requery whole SQLite maps.  Keep one canonical row/
        # entry/review/resolution cache and use row hiding for search/filters.
        self._comparison_row_cache: dict[str, dict] = {}
        self._comparison_entry_cache: dict[str, dict] = {}
        self._comparison_row_index_cache: dict[str, int] = {}
        self._comparison_review_map_cache: dict[str, dict] = {}
        self._comparison_resolution_map_cache: dict[str, dict] = {}
        self._comparison_last_entries: list[dict] = []
        self._comparison_action_tracking_keys: set[str] = set()
        self._comparison_dataset_ready = False
        self.settings = QSettings()
        # Equipment Data Review column widths are user presentation preferences.
        # Persist them by stable column key so a reviewer can drag any header
        # divider wider/narrower and keep that width across refreshes, site
        # switches and application restarts even when the dynamic source-column
        # order changes.  JSON avoids QVariant-map differences across PySide6
        # versions and keeps the QSettings value portable.
        try:
            _saved_widths = json.loads(str(self.settings.value("comparison/column_widths_json", "{}") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            _saved_widths = {}
        self.comparison_column_widths = {
            str(key): max(55, min(2400, int(value)))
            for key, value in (_saved_widths.items() if isinstance(_saved_widths, dict) else ())
            if str(key).strip() and str(value).strip().lstrip("-").isdigit()
        }
        self._comparison_column_keys: list[str] = []
        self._comparison_applying_column_widths = False
        self._comparison_width_save_timer = QTimer(self)
        self._comparison_width_save_timer.setSingleShot(True)
        self._comparison_width_save_timer.setInterval(350)
        self._comparison_width_save_timer.timeout.connect(self._persist_comparison_column_widths)
        self.ui_language = normalize_language(self.settings.value("ui/language", LANG_EN))
        # Keep runtime language in memory so custom-painted headers/dialogs do
        # not wait for QSettings disk synchronization before reflecting a switch.
        set_current_language(self.ui_language)
        # Column visibility is persisted as an explicit HIDDEN set in the
        # application-wide SQLite settings DB.  This is more robust than saving
        # a snapshot of visible columns: any column added by a future release or
        # by a new USER App-column definition is automatically visible until the
        # reviewer explicitly hides it.  The setting lives outside the release
        # folder, so replacing/upgrading the App does not reset the review view.
        stored_hidden = load_review_hidden_columns("rmu_data_review")
        if stored_hidden is None:
            # One-time migration from the older QSettings visible-column model.
            # Only columns that were already known to that older UI can become
            # hidden; genuinely new dynamic fields must still appear on first use.
            saved_columns = self.settings.value("comparison/visible_columns", [], type=list) or []
            known_dynamic = set(self.settings.value("comparison/known_dynamic_columns", [], type=list) or [])
            saved_column_schema = self.settings.value("comparison/column_schema_version", 0)
            migrated_visible = migrate_comparison_visible_columns(saved_columns, saved_column_schema)
            # COMPARISON_GROUPS is nested; build the known key set explicitly.
            legacy_known = {key for _group, _color, cols in COMPARISON_GROUPS for key, _label, _width in cols}
            legacy_known |= known_dynamic
            stored_hidden = (legacy_known - set(migrated_visible)) - {"no", "rmu"}
            save_review_hidden_columns(stored_hidden, "rmu_data_review")
        self.comparison_hidden_keys = set(stored_hidden or set()) - {"no", "rmu"}
        base_keys = {key for _group, _color, cols in COMPARISON_GROUPS for key, _label, _width in cols}
        self.comparison_visible_keys = (base_keys - self.comparison_hidden_keys) | {"no", "rmu"}
        self.settings.setValue("comparison/column_schema_version", COMPARISON_COLUMN_SCHEMA_VERSION)

        # Prefer PNG for the live Qt window icon. The ICO is reserved for the
        # Windows executable resource and native WM_SETICON fallback.
        icon_path = resource_root() / "assets" / "logo.png"
        if not icon_path.exists():
            icon_path = resource_root() / "assets" / "logo.ico"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                self.setWindowIcon(icon)

        self._build_shell()
        self._build_pages()
        self._apply_ui_language()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._wire_shortcuts()
        self.set_page(0)
        # Show the window first, then perform a filename-only repository scan on
        # the next event-loop turn.  Deep CSV/XLSX inspection is explicit via
        # Refresh Sources / Run Validation, so startup is no longer blocked by
        # opening every site's spreadsheets.
        QTimer.singleShot(0, self._load_initial_workspace)

    def _apply_ui_language(self) -> None:
        """Apply the saved presentation language immediately in both directions.

        Project/source field names, physical headers, review-state tokens in the
        database and workbook schema stay language-neutral. Only QWidget
        presentation is translated. Switching zh-CN <-> English must not require
        a restart or a page reload.
        """
        self.ui_language = normalize_language(getattr(self, "ui_language", LANG_EN))
        set_current_language(self.ui_language)
        translate_widget_tree(self, self.ui_language)
        if hasattr(self, "equipment_profile_combo") and getattr(self, "store", None):
            self._refresh_equipment_profile_options(force=True)
        if hasattr(self, "settings_language_combo"):
            index = self.settings_language_combo.findData(self.ui_language)
            if index >= 0 and index != self.settings_language_combo.currentIndex():
                self.settings_language_combo.blockSignals(True)
                self.settings_language_combo.setCurrentIndex(index)
                self.settings_language_combo.blockSignals(False)

        # Grouped spreadsheet headers paint their labels themselves rather than
        # relying only on QTableWidget horizontalHeaderItem text. Force those
        # presentation surfaces to recompute/repaint now so a language change is
        # visible immediately, especially when switching Chinese back to English.
        if hasattr(self, "comparison_table"):
            self._configure_comparison_headers()
            self._populate_comparison_search_fields()
        for table in list(getattr(self, "_spreadsheet_tables", []) or []):
            try:
                header = table.horizontalHeader()
                header.viewport().update()
                table.viewport().update()
            except Exception:
                pass
        try:
            self.centralWidget().update()
        except Exception:
            pass
        # Re-translate any currently open top-level dialog as well, then flush
        # paint events.  This removes the old "switch saved now, visible after
        # page reload" behavior, especially for zh-CN -> English.
        app = QApplication.instance()
        if app is not None:
            for widget in app.topLevelWidgets():
                try:
                    translate_widget_tree(widget, self.ui_language)
                    widget.update()
                except Exception:
                    pass
            QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def _change_ui_language(self, _index: int = -1) -> None:
        if not hasattr(self, "settings_language_combo"):
            return
        language = normalize_language(self.settings_language_combo.currentData())
        if language == getattr(self, "ui_language", LANG_EN):
            return
        self.ui_language = language
        set_current_language(language)
        self.settings.setValue("ui/language", language)
        self.settings.sync()
        self._apply_ui_language()
        message = (
            "界面语言已切换为简体中文。技术字段名和源文件表头保持不变。"
            if language == LANG_ZH_CN else
            "Interface language changed to English. Technical field names and source headers remain unchanged."
        )
        self.statusBar().showMessage(message, 6000)

    # ------------------------- shell -------------------------
    def _build_shell(self):
        # Centralize translation of transient status messages. This also covers
        # messages produced after a page has already been translated.
        self.setStatusBar(I18nStatusBar(self))
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
            ("Equipment Data Review", 2, "rmu"),
            ("Signal Mapping Review", 3, "signal"),
            ("Change Audit", 4, "audit"),
            ("Review Versions", 5, "versions"),
            ("Site History", 6, "audit"),
            ("Report Export", 7, "report"),
            ("Settings", 8, "settings"),
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

        workspace_caption = QLabel("PROJECT DATA")
        workspace_caption.setStyleSheet("color:#7F9AB2;font-size:8pt;font-weight:700;")
        side.addWidget(workspace_caption)
        self.sidebar_workspace = QLabel(str(project_data_root()))
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
        self.refresh_sources_btn = QPushButton("Refresh Sources")
        self.refresh_sources_btn.setIcon(app_icon("database"))
        self.refresh_sources_btn.setToolTip(
            "Re-scan source versions and re-read only active files whose content changed. "
            "AUTO switches to the highest V version; pinned files remain pinned."
        )
        self.refresh_sources_btn.clicked.connect(self.refresh_sources_and_reload)
        self.run_validation_btn = QPushButton("Run Validation")
        self.run_validation_btn.setIcon(app_icon("overview"))
        self.run_validation_btn.setObjectName("Primary")
        self.run_validation_btn.setToolTip(
            "Force re-read every active source file, then run full RMU and Signal Mapping validation."
        )
        self.run_validation_btn.clicked.connect(self.run_comparison)
        top.addWidget(self.project_state_label, alignment=Qt.AlignVCenter)
        top.addSpacing(6)
        top.addWidget(self.refresh_sources_btn)
        top.addWidget(self.run_validation_btn)

        self.stack = QStackedWidget()

        # A single shared floating progress popup is the only operational
        # waiting indicator.  Do not add a second top progress strip here:
        # validation/source loading/table rendering must all reuse the popup.
        content_layout.addWidget(topbar)
        content_layout.addWidget(self.stack, 1)

        # Floating progress feedback for operations that need visible waiting
        # time (Show All, source refresh, validation, lazy module loading, etc.).
        # It is deliberately not part of the stack layout, so it can float over
        # whichever review page is currently visible without changing geometry.
        self.busy_operation_popup = BusyOperationPopup(self.stack)
        self.busy_operation_popup.raise_()

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
        self.site_history_page = self._build_site_history_page()
        self.export_page = self._build_export_page()
        self.settings_page = self._build_settings_page()
        for page in (
            self.dashboard_page,
            self.import_page,
            self.comparison_page,
            self.db_smart_page,
            self.changes_page,
            self.versions_page,
            self.site_history_page,
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
        # Preserve dashboard geometry on smaller screens / Windows DPI scaling.
        # The whole Overview scrolls instead of crushing the bottom cards.
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        content.setMinimumHeight(760)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.dashboard_scroll = scroll
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

        # First-run / incomplete-configuration guidance. This stays hidden for
        # established users and appears only when Source Workspace or Project
        # Data still needs attention. It is deliberately non-blocking after the
        # first-run dialog so reviewers are not interrupted on every launch.
        self.setup_guidance_card = QFrame()
        self.setup_guidance_card.setObjectName("SetupGuidance")
        self.setup_guidance_card.setStyleSheet(
            "QFrame#SetupGuidance{background:#FFF8E6;border:1px solid #F1D493;border-radius:10px;}"
        )
        setup_row = QHBoxLayout(self.setup_guidance_card)
        setup_row.setContentsMargins(16, 11, 16, 11)
        setup_row.setSpacing(12)
        setup_text_box = QVBoxLayout(); setup_text_box.setSpacing(2)
        setup_title = QLabel("Setup required")
        setup_title.setStyleSheet("font-weight:750;color:#805B12;")
        self.setup_guidance_label = QLabel("")
        self.setup_guidance_label.setWordWrap(True)
        self.setup_guidance_label.setStyleSheet("color:#805B12;")
        setup_text_box.addWidget(setup_title); setup_text_box.addWidget(self.setup_guidance_label)
        setup_row.addLayout(setup_text_box, 1)
        setup_now = QPushButton("Configure Now")
        setup_now.setObjectName("Primary")
        setup_now.clicked.connect(self.open_setup_dialog)
        setup_settings = QPushButton("Open Settings")
        setup_settings.clicked.connect(lambda: self.set_page(8))
        setup_row.addWidget(setup_now); setup_row.addWidget(setup_settings)
        self.setup_guidance_card.hide()
        layout.addWidget(self.setup_guidance_card)

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

        # Equipment review workstream. The current active profile remains RMU.
        rmu_title_row = QHBoxLayout()
        rmu_title_row.addWidget(icon_label("rmu", 24))
        rmu_title = QLabel("Equipment Data Review")
        rmu_title.setObjectName("SectionTitle")
        self.dashboard_rmu_issue_summary = QLabel("No equipment validation loaded")
        self.dashboard_rmu_issue_summary.setObjectName("Muted")
        rmu_title_row.addWidget(rmu_title)
        rmu_title_row.addSpacing(12)
        rmu_title_row.addWidget(self.dashboard_rmu_issue_summary)
        rmu_title_row.addStretch()
        layout.addLayout(rmu_title_row)

        rmu_cards = QGridLayout()
        rmu_cards.setHorizontalSpacing(12)
        rmu_cards.setVerticalSpacing(12)
        self.metric_rmu_total = MetricCard("Total Equipment", "0", "#2365A8")
        self.metric_rmu_pass = MetricCard("Pass", "0", "#12805C")
        self.metric_rmu_issues = MetricCard("With Issues", "0", "#C9871A")
        self.metric_rmu_reviewed = MetricCard("Closed / Issues", "0 / 0", "#2E7D32")
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

        # Dynamic equipment-type dashboard. DeviceType values come directly
        # from the mapped ZENON-SLD source, so LBS / TRANSFORMER / SFI / RMU /
        # REC / FUSE and future types appear without hard-coded UI changes.
        self.dashboard_equipment_type_table = QTableWidget(0, 8)
        self.dashboard_equipment_type_table.setHorizontalHeaderLabels([
            "Equipment Type", "Total", "Pass", "With Issues",
            "Unreviewed", "Closed", "Needs Action", "Review Progress",
        ])
        _configure_table_base(self.dashboard_equipment_type_table)
        self.dashboard_equipment_type_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.dashboard_equipment_type_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.dashboard_equipment_type_table.verticalHeader().setVisible(False)
        self.dashboard_equipment_type_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dashboard_equipment_type_table.setMinimumHeight(150)
        self.dashboard_equipment_type_table.setMaximumHeight(250)
        layout.addWidget(self.dashboard_equipment_type_table)

        # Signal Mapping review workstream. STANDARD drives expected points;
        # ADMS points are compared TRUE/FALSE and ZENON extras are tracked separately.
        signal_title_row = QHBoxLayout()
        signal_title_row.addWidget(icon_label("signal", 24))
        signal_title = QLabel("Signal Mapping Review")
        signal_title.setObjectName("SectionTitle")
        self.dashboard_signal_summary = QLabel("STANDARD → ADMS → ZENON · ADMS/ZENON from combined IOA")
        self.dashboard_signal_summary.setObjectName("Muted")
        signal_title_row.addWidget(signal_title)
        signal_title_row.addSpacing(12)
        signal_title_row.addWidget(self.dashboard_signal_summary)
        signal_title_row.addStretch()
        layout.addLayout(signal_title_row)

        signal_cards = QGridLayout()
        signal_cards.setHorizontalSpacing(10)
        signal_cards.setVerticalSpacing(12)
        self.metric_signal_total = MetricCard("ADMS Points", "0", "#2365A8")
        self.metric_signal_matched = MetricCard("Matched", "0", "#12805C")
        self.metric_signal_mismatched = MetricCard("Mismatched", "0", "#C9871A")
        self.metric_signal_zenon_extra = MetricCard("ZENON Extra", "0", "#7B8794")
        self.metric_signal_needs_action = MetricCard("Needs Action", "0", "#B42318")
        for i, card in enumerate((
            self.metric_signal_total, self.metric_signal_matched, self.metric_signal_mismatched,
            self.metric_signal_zenon_extra, self.metric_signal_needs_action,
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
        project_card.setMinimumHeight(250)
        pbox = QVBoxLayout(project_card)
        pbox.setContentsMargins(20, 18, 20, 18)
        ptitle = QLabel("Current Migration Site")
        ptitle.setObjectName("SectionTitle")
        pbox.addWidget(ptitle)
        self.dash_project_name = QLabel("No site selected")
        self.dash_project_name.setStyleSheet("font-size:15pt;font-weight:700;color:#173A5E;")
        self.dash_project_path = QLabel(str(project_data_root()))
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
        self.dashboard_rmu_issues_button = QPushButton("Review Equipment Issues")
        self.dashboard_rmu_issues_button.setIcon(app_icon("rmu"))
        self.dashboard_rmu_issues_button.setObjectName("Primary")
        self.dashboard_rmu_issues_button.setToolTip("Open Equipment Data Review and show all equipment with automatic Analysis issues.")
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
        source_card.setMinimumHeight(250)
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
            "Choose the file each App table reads and review the exact fields used by this module.",
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
        open_site_btn = QPushButton("Open Site Folder")
        open_site_btn.clicked.connect(self.open_selected_site_folder)
        detail_top.addWidget(open_site_btn)
        detail_box.addLayout(detail_top)

        note = QLabel(
            "Equipment Data Review is fully configurable per site: add any number of CSV/Excel tables, choose each table's key/index field, and define the fields to compare. "
            "Every detected physical field is visible by default and may be hidden for that site. Source titles default to filenames and can be renamed. "
            "Signal Mapping Review keeps its existing source roles and mapping workflow. "
            "AUTO still uses published V versions / detection rules as convenient discovery hints. Click Source File to return to AUTO, pin a version, or browse any supported table. "
            "For Excel, Sheet defaults to AUTO (the source-preferred business sheet when available, otherwise the first usable sheet) and can be pinned per site without changing the global field mapping. "
            "File Path shows the reviewer-facing location. Fields Used shows exactly which App fields this module reads from that file. "
            "Missing source fields stay blank. Changing one Source File re-reads only that table. "
            "Refresh Sources re-scans versions and re-reads changed files; Run Validation force re-reads all active files. "
            "While the App is open, live file metadata is watched and changed inputs are refreshed in the background."
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
            module_description = (
                "Equipment Data Review accepts any number of CSV/XLSX/XLSM tables. Each site independently defines source titles, worksheets, header rows, Key / Index fields, comparison rules and visible physical fields."
                if module.key == "rmu_review" else module.description
            )
            module_desc = QLabel(module_description)
            module_desc.setObjectName("Muted")
            module_desc.setWordWrap(True)
            module_box.addWidget(module_desc)

            table = QTableWidget(0, 6)
            table.setHorizontalHeaderLabels([
                "App Table", "Source File", "Sheet", "File Path",
                "Fields Used in This Module (App ← Source)", "Status"
            ])
            _configure_table_base(table)
            _set_interactive_column(table, 0, 175)
            _set_interactive_column(table, 1, 210)
            _set_interactive_column(table, 2, 180)
            _set_interactive_column(table, 3, 390)
            _set_stretch_column(table, 4)
            _set_fixed_column(table, 5, 105)
            table.itemDoubleClicked.connect(self.open_source_mapping)
            self.module_source_tables[module.key] = table
            module_box.addWidget(table, 1)
            module_icon = app_icon("rmu" if module.key == "rmu_review" else "signal")
            self.module_source_tabs.addTab(module_page, module_icon, module.label)
        detail_box.addWidget(self.module_source_tabs, 1)

        self.unmapped_card = QFrame()
        self.unmapped_card.setObjectName("SoftCard")
        unmapped_row = QHBoxLayout(self.unmapped_card)
        unmapped_row.setContentsMargins(12, 8, 12, 8)
        self.unmapped_files_label = QLabel("Unmapped Files")
        self.unmapped_files_label.setStyleSheet("font-weight:700;")
        self.unmapped_file_combo = QComboBox()
        self.unmapped_file_combo.setMinimumWidth(300)
        self.unmapped_file_combo.setToolTip("Files deliberately left unmapped because no source type was sufficiently certain.")
        self.assign_unmapped_btn = QPushButton("Assign Source...")
        self.assign_unmapped_btn.clicked.connect(self.assign_unmapped_source)
        unmapped_row.addWidget(self.unmapped_files_label)
        unmapped_row.addWidget(self.unmapped_file_combo, 1)
        unmapped_row.addWidget(self.assign_unmapped_btn)
        detail_box.addWidget(self.unmapped_card)

        footer = QHBoxLayout()
        self.repository_last_scan = QLabel("Last scan: —")
        self.repository_last_scan.setObjectName("Muted")
        footer.addWidget(self.repository_last_scan)
        footer.addStretch()
        comparison_config_btn = QPushButton("Configure Equipment Comparison...")
        comparison_config_btn.setObjectName("Primary")
        comparison_config_btn.setToolTip("Add/remove arbitrary Equipment Data Review source tables and configure each Key / Index, comparison field, title and site-local field visibility.")
        comparison_config_btn.clicked.connect(self.open_equipment_comparison_config)
        footer.addWidget(comparison_config_btn)
        mapping_btn = QPushButton("Map Signal Fields...")
        mapping_btn.setObjectName("Primary")
        mapping_btn.setToolTip("Map fields for the currently selected legacy Signal Mapping source. Equipment Data Review uses Configure Equipment Comparison.")
        mapping_btn.clicked.connect(self.open_source_mapping)
        footer.addWidget(mapping_btn)
        detail_box.addLayout(footer)

        self.site_splitter.addWidget(detail_card)
        self.site_splitter.setStretchFactor(0, 0)
        self.site_splitter.setStretchFactor(1, 1)
        self.site_splitter.setSizes([300, 1200])
        layout.addWidget(self.site_splitter, 1)
        return page

    def _source_description(self, key: str) -> str:
        return {
            "se_list": "SE equipment detail list (SS / FEEDER / EQUIPMENT / Device Type / TYPE / SMART / OH / UG when provided)",
            "zenon_db": "Zenon device and driver database export",
            "zenon_sld": "Authoritative all-equipment ZENON SLD inventory used by every equipment review profile.",
            "adms_db": "ADMS database migration reference",
            "adms_sld": "ADMS SLD all-equipment result with separate Device Type and Type / Subtype fields",
            "ioa": "ZENON–ADMS IOA point mapping source",
        }.get(key, "Project source file")

    def open_dashboard_rmu_issues(self):
        """Open Equipment Data Review with all automatic Analysis issues visible."""
        if not self.store:
            return
        try:
            equipment_rows, _summary = build_equipment_source_view(self.store, "__ALL__")
            issue_count = sum(analysis_review_state(row).issue_count > 0 for row in equipment_rows)
        except Exception:
            equipment_rows = []
            issue_count = sum(analysis_review_state(row).issue_count > 0 for row in self.store.rows())
        if issue_count <= 0:
            return
        self.set_page(2)
        self._refresh_equipment_profile_options(force=True)
        all_index = self.equipment_profile_combo.findData("__ALL__") if hasattr(self, "equipment_profile_combo") else -1
        if all_index >= 0:
            self.equipment_profile_combo.setCurrentIndex(all_index)
        self.search_edit.clear()
        self.rmu_review_filter_combo.setCurrentIndex(max(0, self.rmu_review_filter_combo.findData("ALL REVIEWS")))
        self.analysis_combo.setCurrentIndex(max(0, self.analysis_combo.findData("ANY MISMATCH")))
        self.refresh_comparison()
        message = ui_tr("Showing equipment with Analysis issues", self.ui_language)
        self.statusBar().showMessage(f"{message}: {issue_count}", 4000)

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
        self.db_smart_review_combo.setCurrentIndex(max(0, self.db_smart_review_combo.findData("ALL REVIEWS")))
        self.db_smart_result_combo.setCurrentText("MISMATCHED")
        self.db_smart_result_combo.setCurrentIndex(max(0, self.db_smart_result_combo.findData("MISMATCHED")))
        self.db_smart_rmu_filter.setCurrentIndex(max(0, self.db_smart_rmu_filter.findData("ISSUES ONLY")))
        self._show_db_smart_rmu_overview()
        self.statusBar().showMessage(
            f"Showing RMUs containing {mismatch_count} mismatched signal row(s)", 4000
        )

    # ------------------------- comparison -------------------------
    def _build_comparison_page(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader(
            "Equipment Data Review",
            "Compare any number of site-specific CSV/Excel tables. Choose the Key / Index field for every table, configure exactly which fields are compared, and keep the existing Review Status, Resolution, Comments and Needs Action lifecycle workflow.",
        ))

        controls = QFrame()
        controls.setObjectName("Card")
        cbox = QHBoxLayout(controls)
        cbox.setContentsMargins(14, 10, 14, 10)
        self.equipment_profile_label = QLabel("Scope")
        self.equipment_profile_label.setObjectName("Muted")
        self.equipment_profile_combo = QComboBox()
        self.equipment_profile_combo.setMinimumWidth(220)
        # Universal review starts from the complete ZENON SLD inventory.
        # Individual DeviceType entries are filters only; RMU is not a special
        # review mode and is populated later from the same source-driven list.
        self.equipment_profile_combo.addItem("All Equipment", "__ALL__")
        self.equipment_profile_combo.setToolTip(
            "Configurable comparison mode uses the union of the configured Key / Index values. Legacy projects retain the historical Equipment Type filters until a configurable source contract is saved."
        )
        self.equipment_profile_combo.currentIndexChanged.connect(self._on_equipment_profile_changed)
        self.comparison_search_field = QComboBox()
        self.comparison_search_field.setMinimumWidth(190)
        self.comparison_search_field.setToolTip("Choose the exact table column to search. Use All Columns only when a cross-column fuzzy search is intended.")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search selected column...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumWidth(300)
        self._comparison_search_timer = QTimer(self)
        self._comparison_search_timer.setSingleShot(True)
        self._comparison_search_timer.setInterval(180)
        self._comparison_search_timer.timeout.connect(self._apply_comparison_filters_local)
        self.search_edit.textChanged.connect(lambda _text: self._comparison_search_timer.start())
        self.comparison_search_field.currentIndexChanged.connect(self._apply_comparison_filters_local)
        self._populate_comparison_search_fields()
        self.rmu_review_filter_combo = QComboBox()
        self.rmu_review_filter_combo.addItems(["ALL REVIEWS", "UNREVIEWED", "CLOSED", "NEEDS ACTION"])
        for i, key in enumerate(("ALL REVIEWS", "UNREVIEWED", "CLOSED", "NEEDS ACTION")):
            self.rmu_review_filter_combo.setItemData(i, key)
        mark_combo_for_translation(self.rmu_review_filter_combo)
        self.rmu_review_filter_combo.setToolTip("Filter only by the manual human Review state. Automated Analysis is filtered separately.")
        self.rmu_review_filter_combo.currentIndexChanged.connect(self._apply_comparison_filters_local)
        self.analysis_combo = QComboBox()
        for key in (
            "ALL ANALYSIS", "PASSED", "ANY MISMATCH",
            "1 ISSUE", "2 ISSUES", "MULTIPLE ISSUES", "CRITICAL",
            "NAME MISMATCH", "FEEDER MISMATCH", "SMART MISMATCH", "TYPE MISMATCH",
            "IP MISMATCH", "LINK MISMATCH",
        ):
            self.analysis_combo.addItem(key, key)
        mark_combo_for_translation(self.analysis_combo)
        self.analysis_combo.setToolTip("Filter by Analysis result")
        self.analysis_combo.currentIndexChanged.connect(self._apply_comparison_filters_local)
        self.comparison_show_all_btn = QPushButton("Show All")
        self.comparison_show_all_btn.setToolTip("Clear search and every Equipment Review/Analysis filter; keep column layout and review data unchanged.")
        self.comparison_show_all_btn.clicked.connect(self._show_all_comparison)
        self.comparison_clear_selection_btn = QPushButton("Clear Selection")
        self.comparison_clear_selection_btn.setToolTip("Explicitly clear the current Equipment Data Review selection")
        self.comparison_clear_selection_btn.clicked.connect(self._clear_comparison_selection)
        review_btn = QPushButton("Set Status")
        self.comparison_set_status_btn = review_btn
        review_btn.setToolTip("Set the selected equipment row(s) to Unreviewed, Closed or Needs Action. Structured Resolution remains available by double-clicking FALSE/Resolution cells.")
        review_btn.clicked.connect(self.set_comparison_review_status)
        configure_sources_btn = QPushButton("Configure Sources")
        configure_sources_btn.setObjectName("Primary")
        configure_sources_btn.setToolTip("Add/remove arbitrary CSV/Excel tables, choose each Key / Index field, comparison fields, source titles and site-local source-field visibility")
        configure_sources_btn.clicked.connect(self.open_equipment_comparison_config)
        columns_btn = QPushButton("Columns")
        columns_btn.setToolTip("Show or hide application/meta columns. Physical source fields are shown/hidden in Configure Sources.")
        columns_btn.clicked.connect(self.open_comparison_columns)
        reset_btn = QPushButton("Reset Columns")
        reset_btn.setToolTip("Restore the default Equipment Data Review column visibility; filters are controlled by Show All")
        reset_btn.clicked.connect(self.reset_comparison_columns)
        self.comparison_summary = QLabel("No validation data")
        self.comparison_summary.setObjectName("Muted")
        self.comparison_summary.setWordWrap(True)
        self.comparison_summary.setMinimumWidth(620)
        self.comparison_summary.setToolTip(
            "Total = all rows for the active Equipment Type. Shown = rows after filters. "
            "Each displayed issue count is the number of equipment rows where that Analysis field is FALSE. Zero-count fields are hidden."
        )
        cbox.addWidget(self.equipment_profile_label)
        cbox.addWidget(self.equipment_profile_combo)
        cbox.addWidget(self.comparison_search_field)
        cbox.addWidget(self.search_edit, 1)
        cbox.addWidget(self.rmu_review_filter_combo)
        cbox.addWidget(self.analysis_combo)
        cbox.addWidget(self.comparison_show_all_btn)
        cbox.addWidget(self.comparison_clear_selection_btn)
        cbox.addWidget(review_btn)
        cbox.addWidget(configure_sources_btn)
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
        self.comparison_analysis_legend = legend
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
            ("#FDECEC", "Critical", "Three or more Analysis fields are FALSE; a configured Analysis field titled NAME also keeps the historical critical priority"),
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

        # RMU grid painting uses the same shared floating BusyOperationPopup as
        # source refresh/validation/Show All.  Keeping the progress surface in
        # one place avoids showing a page-local bar and a global bar together.

        self.comparison_table = SpreadsheetTableWidget(0, len(self._comparison_columns()))
        self.comparison_header = GroupedReportHeader(self._comparison_groups(), self.comparison_table)
        self.comparison_table.setHorizontalHeader(self.comparison_header)
        self.comparison_table.setAlternatingRowColors(True)
        self.comparison_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._register_spreadsheet_table(self.comparison_table)
        self.comparison_table.verticalHeader().setVisible(False)
        self.comparison_table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # v0.8.188: every Equipment Data Review business/source column is
        # explicitly user-resizable.  Fixed mode made long values such as
        # processed_name / Functional Location impossible to inspect without
        # editing the schema.  Interactive mode keeps the existing initial
        # widths but lets the reviewer drag any header divider at runtime.
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.comparison_table.horizontalHeader().setMinimumSectionSize(55)
        self.comparison_table.horizontalHeader().sectionResized.connect(self._on_comparison_column_resized)
        # v0.8.190: double-clicking a header section returns that column to
        # content-aware auto sizing.  This deliberately clears only that
        # column's manual-width override; ordinary single-click/drag behavior
        # remains unchanged.
        self.comparison_table.horizontalHeader().sectionDoubleClicked.connect(self._auto_fit_comparison_section)
        self.comparison_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_table.setWordWrap(True)
        self.comparison_table.setSortingEnabled(False)
        self.comparison_table.cellDoubleClicked.connect(self.edit_comparison_cell)
        self.comparison_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.comparison_table.customContextMenuRequested.connect(self._show_comparison_status_context_menu)
        self.comparison_table.verticalHeader().setDefaultSectionSize(32)
        self._configure_comparison_headers()

        # Frozen row locator: keep row identity visible while the business grid
        # scrolls horizontally across dozens of source columns.  It is a
        # presentation companion only; the source of truth remains the main
        # RMU Data Review table/store.
        self.comparison_locator = SpreadsheetTableWidget(0, 5)
        locator_groups = (("Row Locator", "#E8EDF3", (
            ("locator_no", "No.", 55),
            ("locator_rmu", "Index / Key", 150),
            ("locator_checked", "Checked", 74),
            ("locator_analysis", "Analysis", 115),
            ("locator_review", "Review", 115),
        )),)
        self.comparison_locator_header = GroupedReportHeader(locator_groups, self.comparison_locator)
        self.comparison_locator.setHorizontalHeader(self.comparison_locator_header)
        self.comparison_locator.setHorizontalHeaderLabels(["No.", "Index / Key", "Checked", "Analysis", "Review"])
        self.comparison_locator.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.comparison_locator.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.comparison_locator.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.comparison_locator.verticalHeader().setVisible(False)
        self.comparison_locator.verticalHeader().setDefaultSectionSize(32)
        self.comparison_locator.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.comparison_locator.setColumnWidth(0, 55)
        self.comparison_locator.setColumnWidth(1, 150)
        self.comparison_locator.setColumnWidth(2, 74)
        self.comparison_locator.setColumnWidth(3, 115)
        self.comparison_locator.setColumnWidth(4, 115)
        self.comparison_locator.setFixedWidth(55 + 150 + 74 + 115 + 115 + 4)
        self.comparison_locator.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comparison_locator.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.comparison_locator.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_locator.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.comparison_locator.setWordWrap(False)
        self.comparison_locator.setFocusPolicy(Qt.ClickFocus)
        self.comparison_locator.cellClicked.connect(self._activate_comparison_row_from_locator)
        self.comparison_locator.cellDoubleClicked.connect(self._edit_comparison_locator_review)
        self.comparison_locator.setContextMenuPolicy(Qt.CustomContextMenu)
        self.comparison_locator.customContextMenuRequested.connect(self._show_comparison_locator_status_context_menu)
        self.comparison_locator.itemSelectionChanged.connect(self._sync_comparison_selection_from_locator)
        self.comparison_locator.itemChanged.connect(self._on_comparison_locator_item_changed)
        self.comparison_table.itemSelectionChanged.connect(self._sync_comparison_locator_selection)
        self._comparison_lifecycle_timer = QTimer(self)
        self._comparison_lifecycle_timer.setSingleShot(True)
        self._comparison_lifecycle_timer.setInterval(220)
        self._comparison_lifecycle_timer.timeout.connect(self.refresh_selected_rmu_lifecycle)
        self.comparison_table.currentCellChanged.connect(
            lambda _row, _column, _prev_row, _prev_column: self._schedule_comparison_lifecycle_refresh()
        )
        self.comparison_locator.currentCellChanged.connect(
            lambda _row, _column, _prev_row, _prev_column: self._schedule_comparison_lifecycle_refresh()
        )
        # The main grid may use taller rows when a structured Resolution summary
        # is present. Mirror every row-height change into the frozen locator so
        # pixel-based vertical scrolling can never drift by one or more RMUs.
        self.comparison_table.verticalHeader().sectionResized.connect(self._mirror_comparison_locator_row_height)

        # Synchronize the two views. Main-grid cell selections remain Excel-like,
        # while selecting rows in the frozen locator selects those complete rows
        # in the business grid with normal Ctrl/Shift ExtendedSelection semantics.
        self.comparison_table.verticalScrollBar().valueChanged.connect(self.comparison_locator.verticalScrollBar().setValue)
        self.comparison_locator.verticalScrollBar().valueChanged.connect(self.comparison_table.verticalScrollBar().setValue)
        self.comparison_table.hoverRowChanged.connect(self.comparison_locator.set_tracked_hover_row)
        self.comparison_locator.hoverRowChanged.connect(self.comparison_table.set_tracked_hover_row)
        self.comparison_table.activeRowChanged.connect(self.comparison_locator.set_tracked_active_row)

        grid_host = QWidget()
        grid_layout = QHBoxLayout(grid_host)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(6)
        self.comparison_locator_host = QWidget()
        comparison_locator_layout = QVBoxLayout(self.comparison_locator_host)
        comparison_locator_layout.setContentsMargins(0, 0, 0, 0)
        comparison_locator_layout.setSpacing(0)
        comparison_locator_layout.addWidget(self.comparison_locator, 1)
        self.comparison_locator_scroll_spacer = QWidget()
        self.comparison_locator_scroll_spacer.setFixedHeight(0)
        comparison_locator_layout.addWidget(self.comparison_locator_scroll_spacer, 0)
        self.comparison_locator_host.setFixedWidth(55 + 150 + 74 + 115 + 115 + 4)
        grid_layout.addWidget(self.comparison_locator_host, 0)
        grid_layout.addWidget(self.comparison_table, 1)
        self.comparison_table.horizontalScrollBar().rangeChanged.connect(
            lambda _minimum, _maximum: QTimer.singleShot(0, self._sync_comparison_locator_geometry)
        )

        # Equipment lifecycle is visible on the same page as the universal
        # review grid. Historical RMU lifecycle records remain compatible while
        # non-RMU equipment uses namespaced review keys.
        lifecycle_card = QFrame()
        lifecycle_card.setObjectName("SoftCard")
        self.comparison_lifecycle_card = lifecycle_card
        lifecycle_card.setVisible(False)
        lifecycle_box = QVBoxLayout(lifecycle_card)
        lifecycle_box.setContentsMargins(10, 8, 10, 8)
        lifecycle_box.setSpacing(6)
        lifecycle_header = QHBoxLayout()
        self.comparison_lifecycle_title = QLabel("Equipment Action Tracking")
        self.comparison_lifecycle_title.setStyleSheet("font-weight:800;")
        self.comparison_lifecycle_summary = QLabel(
            "Shown only when the selected equipment has a formal Needs Action history. Signal tracking is intentionally excluded for now."
        )
        self.comparison_lifecycle_summary.setObjectName("Muted")
        self.comparison_lifecycle_summary.setWordWrap(True)
        self.comparison_lifecycle_open_btn = QPushButton("Open Full Lifecycle")
        self.comparison_lifecycle_open_btn.setEnabled(False)
        self.comparison_lifecycle_open_btn.setToolTip(
            "Open a larger read-only lifecycle viewer including cases, events and frozen snapshots."
        )
        self.comparison_lifecycle_open_btn.clicked.connect(self._open_selected_rmu_lifecycle)
        lifecycle_header.addWidget(self.comparison_lifecycle_title)
        lifecycle_header.addStretch()
        lifecycle_header.addWidget(self.comparison_lifecycle_open_btn)
        lifecycle_box.addLayout(lifecycle_header)
        lifecycle_box.addWidget(self.comparison_lifecycle_summary)

        self.comparison_lifecycle_table = QTableWidget(0, 6)
        self.comparison_lifecycle_table.setHorizontalHeaderLabels([
            "Time", "Equipment Case", "Status", "Issue", "Comments", "User"
        ])
        _configure_table_base(self.comparison_lifecycle_table)
        self.comparison_lifecycle_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.comparison_lifecycle_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.comparison_lifecycle_table.setMinimumHeight(160)
        self.comparison_lifecycle_table.setMaximumHeight(310)
        _set_fixed_column(self.comparison_lifecycle_table, 0, 165)
        _set_fixed_column(self.comparison_lifecycle_table, 1, 125)
        _set_fixed_column(self.comparison_lifecycle_table, 2, 105)
        _set_interactive_column(self.comparison_lifecycle_table, 3, 230)
        _set_stretch_column(self.comparison_lifecycle_table, 4)
        _set_fixed_column(self.comparison_lifecycle_table, 5, 110)
        lifecycle_box.addWidget(self.comparison_lifecycle_table)

        self.comparison_page_splitter = QSplitter(Qt.Vertical)
        self.comparison_page_splitter.addWidget(grid_host)
        self.comparison_page_splitter.addWidget(lifecycle_card)
        self.comparison_page_splitter.setStretchFactor(0, 4)
        self.comparison_page_splitter.setStretchFactor(1, 1)
        self.comparison_page_splitter.setChildrenCollapsible(False)
        self.comparison_page_splitter.setSizes([620, 210])
        layout.addWidget(self.comparison_page_splitter, 1)
        return page

    def _set_comparison_loading(self, active: bool, text: str = "Loading Equipment Data Review... Please wait.") -> None:
        """Route RMU table-paint feedback through the one shared progress popup."""
        self._comparison_render_in_progress = bool(active)
        if hasattr(self, "comparison_table"):
            self.comparison_table.setEnabled(not active)
        if hasattr(self, "comparison_locator"):
            self.comparison_locator.setEnabled(not active)
        if hasattr(self, "comparison_show_all_btn"):
            self.comparison_show_all_btn.setEnabled(not active)
        if active:
            self._show_busy_operation("rmu-render", "Loading Equipment Data Review", text)
            self.statusBar().showMessage(text)
        else:
            self._hide_busy_operation("rmu-render")

    def _cancel_comparison_render(self) -> None:
        """Invalidate any queued RMU row-render callbacks without blocking Qt."""
        self._comparison_render_generation += 1
        self._comparison_render_context = None
        if hasattr(self, "comparison_table"):
            self.comparison_table.setUpdatesEnabled(True)
            self.comparison_table.setEnabled(True)
        if hasattr(self, "comparison_locator"):
            self.comparison_locator.setUpdatesEnabled(True)
            self.comparison_locator.setEnabled(True)
        if self._comparison_render_in_progress:
            self._set_comparison_loading(False)
        self._hide_busy_operation("rmu-show-all")

    def _mirror_comparison_locator_row_height(self, logical_row: int, _old_height: int, new_height: int) -> None:
        """Keep the frozen RMU locator geometrically identical to the main grid.

        Both tables use ScrollPerPixel. If even one earlier business row is taller
        in only one table, identical scrollbar values point at different RMUs.
        """
        if not hasattr(self, "comparison_locator"):
            return
        if 0 <= logical_row < self.comparison_locator.rowCount():
            height = max(1, int(new_height))
            if self.comparison_locator.rowHeight(logical_row) != height:
                self.comparison_locator.setRowHeight(logical_row, height)

    def _sync_comparison_locator_geometry(self) -> None:
        if not hasattr(self, "comparison_locator_scroll_spacer") or not hasattr(self, "comparison_table"):
            return
        hbar = self.comparison_table.horizontalScrollBar()
        reserve = hbar.sizeHint().height() if hbar.maximum() > hbar.minimum() else 0
        self.comparison_locator_scroll_spacer.setFixedHeight(max(0, reserve))
        self.comparison_locator.verticalScrollBar().setValue(self.comparison_table.verticalScrollBar().value())

    @staticmethod
    def _selected_table_rows(table: QTableWidget) -> list[int]:
        return sorted({index.row() for index in table.selectedIndexes()})

    @staticmethod
    def _select_complete_rows(table: QTableWidget, rows: list[int]) -> None:
        """Select complete rows efficiently while keeping the table in cell mode."""
        model = table.model()
        selection_model = table.selectionModel()
        if model is None or selection_model is None:
            return
        selection = QItemSelection()
        last_col = max(0, table.columnCount() - 1)
        for row in sorted(set(rows)):
            if 0 <= row < table.rowCount():
                selection.select(model.index(row, 0), model.index(row, last_col))
        selection_model.clearSelection()
        if len(selection):
            selection_model.select(selection, QItemSelectionModel.SelectionFlag.Select)

    def _show_all_comparison(self) -> None:
        """Clear every Equipment filter without rebuilding the data grid."""
        widgets = [self.comparison_search_field, self.search_edit, self.rmu_review_filter_combo, self.analysis_combo]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.comparison_search_field.setCurrentIndex(0)
            self.search_edit.clear()
            self.rmu_review_filter_combo.setCurrentIndex(0)
            self.analysis_combo.setCurrentIndex(0)
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self._apply_comparison_filters_local()
        self.statusBar().showMessage(ui_tr("Equipment filters cleared · showing all rows", self.ui_language), 2500)

    def _complete_show_all_comparison(self) -> None:
        # Compatibility hook retained for older tests/callers. Filtering is now
        # local and does not reconstruct the comparison dataset.
        self._apply_comparison_filters_local()

    def _sync_comparison_selection_from_locator(self) -> None:
        if getattr(self, "_syncing_comparison_selection", False):
            return
        if not hasattr(self, "comparison_table") or not hasattr(self, "comparison_locator"):
            return
        self._syncing_comparison_selection = True
        try:
            rows = self._selected_table_rows(self.comparison_locator)
            self._select_complete_rows(self.comparison_table, rows)
        finally:
            self._syncing_comparison_selection = False

    def _sync_comparison_locator_selection(self) -> None:
        if getattr(self, "_syncing_comparison_selection", False):
            return
        if not hasattr(self, "comparison_table") or not hasattr(self, "comparison_locator"):
            return
        self._syncing_comparison_selection = True
        try:
            rows = self._selected_table_rows(self.comparison_table)
            self._select_complete_rows(self.comparison_locator, rows)
        finally:
            self._syncing_comparison_selection = False

    def _comparison_locator_checkbox(self, row: int):
        """Compatibility helper returning the lightweight checkable item."""
        if not hasattr(self, "comparison_locator") or row < 0 or row >= self.comparison_locator.rowCount():
            return None
        return self.comparison_locator.item(row, 2)

    def _on_comparison_locator_item_changed(self, item: QTableWidgetItem) -> None:
        if item is None or item.column() != 2 or getattr(self, "_rendering_comparison_checks", False):
            return
        review_key = clean(item.data(Qt.UserRole))
        if not review_key:
            return
        self._on_comparison_locator_check_passed_toggled(
            review_key, item.checkState() == Qt.CheckState.Checked
        )

    def _on_comparison_locator_check_passed_toggled(self, rmu: str, checked: bool) -> None:
        """Queue one manual verification and return to Qt immediately.

        Even a small SQLite commit can pause the GUI when a background refresh
        briefly owns the database writer lock.  The checkbox itself is already
        painted by Qt, so collect rapid reviewer clicks and persist them through
        a separate ProjectStore connection in one short transaction.
        """
        if getattr(self, "_rendering_comparison_checks", False) or not self.store:
            return
        rmu = clean(rmu)
        if not rmu:
            return
        pending = getattr(self, "_pending_equipment_checks", None)
        if pending is None:
            pending = {}
            self._pending_equipment_checks = pending
        pending[rmu] = bool(checked)

        timer = getattr(self, "_equipment_check_flush_timer", None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(60)
            timer.timeout.connect(self._flush_pending_equipment_checks)
            self._equipment_check_flush_timer = timer
        timer.start()
        state = "PASS" if checked else "cleared"
        self.statusBar().showMessage(
            ui_tr(f"Equipment {rmu} manual check {state} · saving…", self.ui_language), 1800
        )

    def _flush_pending_equipment_checks(self) -> None:
        if not self.store:
            return
        pending = getattr(self, "_pending_equipment_checks", None) or {}
        timer = getattr(self, "_equipment_check_flush_timer", None)
        if not pending:
            return
        if "equipment-check-batch" in self._background_tasks:
            if timer is not None:
                timer.start(80)
            return

        updates = list(pending.items())
        self._pending_equipment_checks = {}
        project_folder = str(self.store.folder)

        def success(result):
            saved = list((result or {}).get("saved") or [])
            self._dirty_pages.update({0, 4, 6, 7})
            if saved:
                self.statusBar().showMessage(
                    ui_tr(f"Equipment manual checks saved · {len(saved)} row(s)", self.ui_language), 2200
                )
            if getattr(self, "_pending_equipment_checks", None):
                QTimer.singleShot(0, self._flush_pending_equipment_checks)

        def failed(details: str):
            # Merge the failed batch back only when the reviewer has not already
            # changed that row again while the worker was running.
            current = getattr(self, "_pending_equipment_checks", None) or {}
            for key, value in updates:
                current.setdefault(key, value)
            self._pending_equipment_checks = current
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.critical(self, "Equipment Check", last_line)
            # Reconcile visually only on the exceptional failure path.
            self.refresh_comparison()

        self._start_background_task(
            "equipment-check-batch",
            "Saving Equipment Checks",
            lambda: _background_equipment_check_batch_job(project_folder, updates, self.user_name),
            success,
            on_error=failed,
        )

    def _clear_comparison_selection(self) -> None:
        self._syncing_comparison_selection = True
        try:
            if hasattr(self, "comparison_table"):
                self.comparison_table.clear_spreadsheet_selection()
            if hasattr(self, "comparison_locator"):
                self.comparison_locator.clear_spreadsheet_selection()
                self.comparison_locator.set_tracked_active_row(-1)
        finally:
            self._syncing_comparison_selection = False
        self.refresh_selected_rmu_lifecycle(force_clear=True)
        self.statusBar().showMessage(ui_tr("Equipment selection cleared", self.ui_language), 2500)

    def _schedule_comparison_lifecycle_refresh(self) -> None:
        """Debounce lifecycle reads while Qt is moving the current row."""
        timer = getattr(self, "_comparison_lifecycle_timer", None)
        if timer is not None:
            timer.start()

    def _active_comparison_rmu(self) -> str:
        """Return the current RMU key without changing spreadsheet selection."""
        table = getattr(self, "comparison_table", None)
        if table is None:
            return ""
        row = table.currentRow()
        if row < 0:
            locator = getattr(self, "comparison_locator", None)
            row = locator.currentRow() if locator is not None else -1
        if row < 0:
            return ""
        rmu_col = next(
            (i for i, (key, _label, _width) in enumerate(self._comparison_columns()) if key == "rmu"),
            -1,
        )
        if rmu_col < 0:
            return ""
        item = table.item(row, rmu_col)
        if item is not None:
            review_key = clean(item.data(Qt.UserRole)) or clean(item.text())
            if review_key:
                return review_key
        locator = getattr(self, "comparison_locator", None)
        locator_item = locator.item(row, 1) if locator is not None and row < locator.rowCount() else None
        return clean(locator_item.text()) if locator_item is not None else ""

    def refresh_selected_rmu_lifecycle(self, *, force_clear: bool = False) -> None:
        """Show the compact equipment review story only after Needs Action exists.

        Human comments are append-only even before Needs Action.  They remain
        hidden while an RMU has never had a formal Needs Action case; once the
        first case is opened, this tracker reveals those earlier notes together
        with the subsequent case/resolution/status history. Signal events stay
        excluded from this compact view.
        """
        table = getattr(self, "comparison_lifecycle_table", None)
        card = getattr(self, "comparison_lifecycle_card", None)
        title = getattr(self, "comparison_lifecycle_title", None)
        summary = getattr(self, "comparison_lifecycle_summary", None)
        open_btn = getattr(self, "comparison_lifecycle_open_btn", None)
        if table is None or card is None or title is None or summary is None:
            return

        rmu = "" if force_clear or not self.store else self._active_comparison_rmu()
        if not rmu:
            table.setRowCount(0)
            card.setVisible(False)
            if open_btn is not None:
                open_btn.setEnabled(False)
            return

        data = self._comparison_row_by_rmu(rmu) or {}
        display_name = self._equipment_display_name(rmu, data)
        device_type = self._equipment_type_from_key(rmu, data)
        # Most equipment has never entered formal Needs Action. Avoid opening
        # several lifecycle/audit tables on every row click; the active review
        # session already knows which keys have durable tracking history.
        tracked_keys = getattr(self, "_comparison_action_tracking_keys", set()) or set()
        if rmu not in tracked_keys:
            table.setRowCount(0)
            card.setVisible(False)
            if open_btn is not None:
                open_btn.setEnabled(False)
            return
        payload = (self.store.equipment_full_lifecycle(rmu) if hasattr(self.store, "equipment_full_lifecycle") else self.store.rmu_full_lifecycle(rmu))
        rmu_cases = [
            case for case in (payload.get("cases") or [])
            if clean(case.get("entity_type")).upper() == "RMU"
        ]
        if not rmu_cases:
            # Comments can already be stored in rmu_review_events, but the user
            # explicitly asked that tracking only appear after real Needs Action.
            table.setRowCount(0)
            card.setVisible(False)
            if open_btn is not None:
                open_btn.setEnabled(False)
            return

        formal_events = [
            event for event in (payload.get("events") or [])
            if clean(event.get("entity_type")).upper() == "RMU"
            and clean(event.get("event_type")).upper() != "COMMENT_CHANGED"
        ]
        review_events = list(payload.get("review_events") or [])

        card.setVisible(True)
        title.setText(f"{device_type} Action Tracking · {display_name}")
        open_cases = sum(1 for case in rmu_cases if clean(case.get("status")).upper() == "OPEN")
        closed_cases = sum(1 for case in rmu_cases if clean(case.get("status")).upper() == "CLOSED")
        summary.setText(
            f"Needs Action history · Cases {len(rmu_cases)} · Open {open_cases} · Closed {closed_cases} · "
            f"Review comments {len(review_events)}. Earlier comments are retained and become visible here once the equipment has Needs Action history. "
            "Signal Mapping is excluded for now."
        )
        if open_btn is not None:
            open_btn.setEnabled(True)

        def snapshot_of(event: dict) -> dict:
            raw = event.get("snapshot_json") or "{}"
            try:
                return json.loads(raw) if isinstance(raw, str) else dict(raw or {})
            except Exception:
                return {}

        def failed_fields(snapshot: dict) -> list[str]:
            analysis = dict(snapshot.get("analysis") or {})
            return [
                clean(name).upper() for name, value in analysis.items()
                if clean(value).upper() == "FALSE"
            ]

        def formal_issue_text(event: dict, snapshot: dict) -> str:
            field = clean(event.get("field_name")).upper()
            event_type = clean(event.get("event_type")).upper()
            if event_type == "SOURCE_VALUE_CHANGED":
                # A source-version diff is its own audit fact. Do not replace it
                # with whichever Analysis mismatch happens to remain active.
                return field or "SOURCE DATA CHANGED"
            if field.startswith("RESOLUTION."):
                field = field.split(".", 1)[1]
            failed = failed_fields(snapshot)
            if field in {"NAME", "FEEDER", "SMART", "TYPE", "IP"} and field not in failed:
                failed.insert(0, field)
            if failed:
                return " / ".join(f"{name} mismatch" for name in dict.fromkeys(failed))
            if event_type == "CASE_CLOSED":
                return "Needs Action closed"
            if event_type in {"CASE_OPENED", "STATUS_CHANGED"}:
                return "Manual / Site Review"
            if event_type == "VALIDATION_CHANGED":
                return "Validation changed"
            return field or "Equipment review"

        def formal_comments_text(event: dict) -> str:
            event_type = clean(event.get("event_type")).upper()
            after = clean(event.get("new_value"))
            reason = clean(event.get("reason"))
            if event_type == "RESOLUTION_CHANGED" and after:
                return after
            ignored = {
                "RMU DATA REVIEW MARKED NEEDS ACTION",
                "RMU DATA REVIEW MARKED CLOSED",
                "AUTOMATIC REVIEW STATE FROM STRUCTURED RESOLUTION DECISIONS",
            }
            if reason and reason.upper() not in ignored:
                return reason
            return "—"

        rows: list[dict] = []
        for event in formal_events:
            snapshot = snapshot_of(event)
            rows.append({
                "time": clean(event.get("modified_at")),
                "case": int(event.get("case_no") or 0),
                "status": clean(event.get("event_state")) or "UNREVIEWED",
                "issue": formal_issue_text(event, snapshot),
                "comments": formal_comments_text(event),
                "user": clean(event.get("modified_by")),
                "sort_id": int(event.get("id") or 0),
                "sort_rank": 0,
            })

        for event in review_events:
            snapshot = snapshot_of(event)
            field = clean(event.get("analysis_field")).upper()
            failed = failed_fields(snapshot)
            if field:
                issue = f"{field} mismatch"
            elif failed:
                issue = " / ".join(f"{name} mismatch" for name in dict.fromkeys(failed))
            else:
                issue = "Manual / Site Review"
            comment = clean(event.get("comment"))
            event_type = clean(event.get("event_type")).upper()
            if not comment and event_type.endswith("CLEARED"):
                comment = "Comment cleared (previous history retained)"
            rows.append({
                "time": clean(event.get("modified_at")),
                "case": int(event.get("case_no") or 0),
                "status": clean(event.get("review_status")) or "UNREVIEWED",
                "issue": issue,
                "comments": comment or "—",
                "user": clean(event.get("modified_by")),
                "sort_id": int(event.get("id") or 0),
                "sort_rank": 1,
            })

        rows.sort(key=lambda item: (item["time"], item["sort_rank"], item["sort_id"]))
        table.setUpdatesEnabled(False)
        try:
            table.setRowCount(len(rows))
            for row_index, event in enumerate(rows):
                case_no = int(event.get("case") or 0)
                values = [
                    event.get("time"),
                    f"{display_name}-{case_no:03d}" if case_no else "—",
                    event.get("status"),
                    event.get("issue"),
                    event.get("comments"),
                    event.get("user"),
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(clean(value)); item.setToolTip(item.text())
                    if col == 2:
                        status = clean(value).upper()
                        if status in {"OPEN", "NEEDS ACTION"}:
                            item.setBackground(QColor("#FDECEC")); item.setForeground(QColor("#B42318"))
                        elif status == "UNREVIEWED":
                            item.setBackground(QColor("#FFF8D8")); item.setForeground(QColor("#6B4F00"))
                        elif status == "CLOSED":
                            item.setBackground(QColor("#E8F5EE")); item.setForeground(QColor("#116A4D"))
                        font = item.font(); font.setBold(True); item.setFont(font)
                    if col in {1, 3}:
                        font = item.font(); font.setBold(True); item.setFont(font)
                    table.setItem(row_index, col, item)
        finally:
            table.setUpdatesEnabled(True)
            table.viewport().update()
        if rows:
            table.scrollToBottom()

    def _prepare_context_cell(self, table: QTableWidget, pos, *, whole_row: bool = False) -> int:
        """Make the right-clicked record part of the persistent selection.

        Right-clicking an already-selected cell/row keeps the existing Ctrl/Shift
        multi-selection intact. Right-clicking outside the current selection
        starts a new target selection, matching common spreadsheet behavior.
        """
        index = table.indexAt(pos)
        if not index.isValid():
            return -1
        selection_model = table.selectionModel()
        if selection_model is None:
            return -1
        if not selection_model.isSelected(index):
            if whole_row:
                self._select_complete_rows(table, [index.row()])
            else:
                table.clearSelection()
                item = table.item(index.row(), index.column())
                if item is not None:
                    item.setSelected(True)
        selection_model.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
        return index.row()

    def _show_comparison_status_context_menu(self, pos) -> None:
        if self._prepare_context_cell(self.comparison_table, pos) < 0:
            return
        menu = QMenu(self)
        menu.addAction(ui_tr("Mark Unreviewed", self.ui_language), lambda: self.set_comparison_review_status("UNREVIEWED"))
        menu.addAction(ui_tr("Mark Closed", self.ui_language), lambda: self.set_comparison_review_status("CLOSED"))
        menu.addAction(ui_tr("Needs Action", self.ui_language), lambda: self.set_comparison_review_status("NEEDS ACTION"))
        menu.addSeparator()
        menu.addAction(ui_tr("Open Resolution / Comment...", self.ui_language), self._open_selected_rmu_resolution_or_comment)
        menu.addAction(ui_tr("View Full Equipment Lifecycle...", self.ui_language), self._open_selected_rmu_lifecycle)
        menu.exec(self.comparison_table.viewport().mapToGlobal(pos))

    def _show_comparison_locator_status_context_menu(self, pos) -> None:
        row = self._prepare_context_cell(self.comparison_locator, pos, whole_row=True)
        if row < 0:
            return
        self._sync_comparison_selection_from_locator()
        menu = QMenu(self)
        menu.addAction(ui_tr("Mark Unreviewed", self.ui_language), lambda: self.set_comparison_review_status("UNREVIEWED"))
        menu.addAction(ui_tr("Mark Closed", self.ui_language), lambda: self.set_comparison_review_status("CLOSED"))
        menu.addAction(ui_tr("Needs Action", self.ui_language), lambda: self.set_comparison_review_status("NEEDS ACTION"))
        menu.addSeparator()
        menu.addAction(ui_tr("Open Resolution / Comment...", self.ui_language), self._open_selected_rmu_resolution_or_comment)
        menu.addAction(ui_tr("View Full Equipment Lifecycle...", self.ui_language), self._open_selected_rmu_lifecycle)
        menu.exec(self.comparison_locator.viewport().mapToGlobal(pos))

    def _open_selected_rmu_resolution_or_comment(self) -> None:
        rmus = self._selected_comparison_rmus()
        if len(rmus) != 1:
            QMessageBox.information(self, "Equipment Review", "Select exactly one equipment row to open Resolution / Comment.")
            return
        rmu = rmus[0]
        data = self._comparison_row_by_rmu(rmu)
        state = analysis_review_state(data or {})
        if state.issue_count > 0:
            self.open_rmu_resolution_dialog(rmu)
        else:
            self.edit_rmu_manual_review_comment(rmu)

    def _open_selected_rmu_lifecycle(self) -> None:
        if not self.store:
            return
        rmu = self._active_comparison_rmu()
        if not rmu:
            rmus = self._selected_comparison_rmus()
            rmu = clean(rmus[0]) if len(rmus) == 1 else ""
        if not rmu:
            QMessageBox.information(self, "Equipment Lifecycle", "Select exactly one equipment row to view its full lifecycle.")
            return
        payload = (self.store.equipment_full_lifecycle(rmu) if hasattr(self.store, "equipment_full_lifecycle") else self.store.rmu_full_lifecycle(rmu))
        if not payload.get("case_count"):
            data = self._comparison_row_by_rmu(rmu) or {}
            QMessageBox.information(
                self, "Equipment Lifecycle",
                f"{self._equipment_type_from_key(rmu, data)} {self._equipment_display_name(rmu, data)} has not entered formal Needs Action yet."
            )
            return
        data = self._comparison_row_by_rmu(rmu) or {}
        RMUFullLifecycleDialog(
            self.store, rmu, self,
            equipment_type=self._equipment_type_from_key(rmu, data),
            display_name=self._equipment_display_name(rmu, data),
        ).exec()

    def _activate_comparison_row_from_locator(self, row: int, _column: int = 0) -> None:
        """Activate the locator row without disturbing Ctrl/Shift multi-selection."""
        if not hasattr(self, "comparison_table") or row < 0 or row >= self.comparison_table.rowCount():
            return
        old_h = self.comparison_table.horizontalScrollBar().value()
        current_col = self.comparison_table.currentColumn()
        if current_col < 0 or current_col >= self.comparison_table.columnCount() or self.comparison_table.isColumnHidden(current_col):
            current_col = next((c for c in range(self.comparison_table.columnCount()) if not self.comparison_table.isColumnHidden(c)), 0)
        item = self.comparison_table.item(row, current_col)
        if item is not None:
            index = self.comparison_table.model().index(row, current_col)
            self.comparison_table.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.comparison_table.scrollToItem(item, QAbstractItemView.EnsureVisible)
        self.comparison_table.set_tracked_active_row(row)
        self.comparison_locator.set_tracked_active_row(row)
        QTimer.singleShot(0, lambda value=old_h: self.comparison_table.horizontalScrollBar().setValue(value))

    def _edit_comparison_locator_review(self, row: int, column: int) -> None:
        """Double-click the frozen Review cell to edit one RMU directly."""
        if column != 4:
            return
        self._activate_comparison_row_from_locator(row, column)
        self.set_comparison_review_status()

    def _populate_comparison_locator_row(self, r: int, data: dict, review_status: str, review_map: dict) -> None:
        """Populate one frozen Row Locator row.

        Keeping this row-level lets RMU Data Review paint in small batches
        instead of building the whole frozen table in one GUI-thread burst.
        """
        if not hasattr(self, "comparison_locator"):
            return
        main_height = max(1, self.comparison_table.rowHeight(r))
        if main_height != self.comparison_locator.verticalHeader().defaultSectionSize():
            self.comparison_locator.setRowHeight(r, main_height)
        state = analysis_review_state(data)
        rmu = clean(data.get("rmu", ""))
        review_key = clean(data.get("review_key") or rmu)
        device_type = clean(data.get("equipment_device_type")).upper() or "RMU"
        common_tip = (
            f"{device_type} {rmu} · Analysis: {state.row_label} · Review: {review_status}"
            + (f" · Mismatch: {', '.join(state.false_fields)}" if state.false_fields else "")
        )

        for c, value in enumerate((clean(data.get("no", "")), rmu)):
            item = QTableWidgetItem(value)
            if c == 1:
                item.setData(Qt.UserRole, review_key)
            item.setBackground(QColor("#FFFFFF"))
            item.setToolTip(common_tip)
            font = item.font(); font.setBold(True); item.setFont(font)
            self.comparison_locator.setItem(r, c, item)

        # Persistent manual verification immediately to the right of Equipment
        # Name. Use a checkable QTableWidgetItem instead of creating a QWidget +
        # QCheckBox for every row; thousands of child widgets were a major
        # source of scrolling/retranslation latency on 1,000+ equipment rows.
        check_record = review_map.get(review_key, {})
        passed = bool(int(check_record.get("check_passed") or 0))
        checked_by = clean(check_record.get("check_passed_by"))
        checked_at = clean(check_record.get("check_passed_at"))
        tooltip = f"{device_type} {rmu} manual verification: {'PASS' if passed else 'not checked'}"
        if passed and (checked_by or checked_at):
            tooltip += f" · {checked_by or '—'} · {checked_at or '—'}"
        check_item = QTableWidgetItem()
        check_item.setData(Qt.UserRole, review_key)
        check_item.setFlags(
            (check_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            & ~Qt.ItemFlag.ItemIsEditable
        )
        check_item.setCheckState(Qt.CheckState.Checked if passed else Qt.CheckState.Unchecked)
        check_item.setTextAlignment(Qt.AlignCenter)
        check_item.setToolTip(tooltip + "\nChecked means the reviewer inspected this equipment and accepted it as passed.")
        self._rendering_comparison_checks = True
        try:
            self.comparison_locator.setItem(r, 2, check_item)
        finally:
            self._rendering_comparison_checks = False

        analysis_item = QTableWidgetItem(state.row_label)
        analysis_item.setBackground(QColor("#" + state.row_color))
        analysis_item.setTextAlignment(Qt.AlignCenter)
        analysis_item.setToolTip(common_tip)
        font = analysis_item.font(); font.setBold(True); analysis_item.setFont(font)
        self.comparison_locator.setItem(r, 3, analysis_item)

        label, review_fill, review_text = _review_visual(review_status)
        review_item = QTableWidgetItem(label)
        review_item.setBackground(review_fill)
        review_item.setForeground(review_text)
        review_item.setTextAlignment(Qt.AlignCenter)
        review_item.setToolTip(
            common_tip
            + (" · Double-click to resolve this RMU's exception(s)" if state.issue_count > 0 else
               " · Automatic Analysis passed; Review defaults to Closed. Double-click for an optional comment")
        )
        font = review_item.font(); font.setBold(True); review_item.setFont(font)
        self.comparison_locator.setItem(r, 4, review_item)

    def _refresh_comparison_locator(self, shown) -> None:
        """Render the fixed No./RMU/Checked/Status identity strip for current rows."""
        if not hasattr(self, "comparison_locator"):
            return
        review_map = self.store.rmu_review_map() if self.store else {}
        self.comparison_locator.setRowCount(len(shown))
        for r, (data, review_status) in enumerate(shown):
            self._populate_comparison_locator_row(r, data, review_status, review_map)
        self.comparison_locator.verticalScrollBar().setValue(self.comparison_table.verticalScrollBar().value())

    def _current_equipment_profile(self) -> str:
        if not hasattr(self, "equipment_profile_combo"):
            return "RMU"
        return clean(self.equipment_profile_combo.currentData()).upper() or "RMU"

    def _refresh_equipment_profile_options(self, *, force: bool = False) -> None:
        """Populate DeviceType choices from the active mapped ZENON-SLD file.

        The list is source-driven rather than hard-coded, so a future extractor
        can introduce a new equipment class and it immediately becomes visible
        in Equipment Data Review without another UI release.
        """
        if not self.store or not hasattr(self, "equipment_profile_combo"):
            return
        try:
            source_path = self.store.source_path("zenon_sld")
            mapping_sig = json.dumps(self.store.source_column_overrides("zenon_sld") or {}, sort_keys=True, ensure_ascii=False)
            sig = (str(self.store.folder), str(source_path or ""), source_path.stat().st_mtime_ns if source_path and source_path.exists() else 0, mapping_sig)
        except Exception:
            sig = (str(getattr(self.store, "folder", "")), "", 0, "")
        previous_profile_sig = getattr(self, "_equipment_profile_source_sig", None)
        if not force and previous_profile_sig == sig:
            return
        self._equipment_profile_source_sig = sig
        try:
            counts = equipment_inventory_type_counts(self.store)
        except Exception:
            counts = {}
        had_source_profile = previous_profile_sig is not None
        current = self._current_equipment_profile()
        saved = clean(self.settings.value("equipment_review/profile", "__ALL__")).upper() or "__ALL__"
        # During the first source-driven population restore the saved filter.
        # Later refreshes preserve the currently selected DeviceType.  RMU is an
        # ordinary filter just like TRANSFORMER/LBS/FUSE/etc.; the universal
        # default is the complete inventory.
        preferred = current if had_source_profile and current else saved
        total = sum(int(v or 0) for v in counts.values())
        zh = normalize_language(getattr(self, "ui_language", LANG_EN)) == LANG_ZH_CN
        all_equipment_label = "全部设备" if zh else "All Equipment"
        combo = self.equipment_profile_combo
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(f"{all_equipment_label} ({total})" if total else all_equipment_label, "__ALL__")
        for device_type, count in sorted(counts.items(), key=lambda item: (-int(item[1]), item[0])):
            token = clean(device_type).upper() or "UNCLASSIFIED"
            combo.addItem(f"{token} ({int(count)})", token)
        restore = combo.findData(preferred)
        if restore < 0:
            restore = combo.findData("__ALL__")
        combo.setCurrentIndex(max(0, restore))
        combo.blockSignals(False)

    def _apply_equipment_profile_ui_mode(self) -> None:
        # v0.8.156: every detected equipment type uses the same mature human
        # review workflow. DeviceType only changes which equipment rows are in
        # scope; it no longer disables Analysis / Review / Resolution / Comments.
        for widget_name in ("rmu_review_filter_combo", "analysis_combo", "comparison_set_status_btn"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setVisible(True)
                widget.setEnabled(True)
        legend = getattr(self, "comparison_analysis_legend", None)
        if legend is not None:
            legend.setVisible(True)
        locator_host = getattr(self, "comparison_locator_host", None)
        if locator_host is not None:
            locator_host.setVisible(True)
        if hasattr(self, "comparison_review_progress"):
            self.comparison_review_progress.setToolTip(
                "Configured comparison fields use the same Unreviewed / Closed / Needs Action, Resolution, Comments and lifecycle workflow as the historical review."
            )

    def _on_equipment_profile_changed(self, _index: int = -1) -> None:
        if not hasattr(self, "comparison_table"):
            return
        profile = self._current_equipment_profile()
        self.settings.setValue("equipment_review/profile", profile)
        self._comparison_render_generation += 1
        self._comparison_render_context = None
        self._apply_equipment_profile_ui_mode()
        self._configure_comparison_headers()
        self._populate_comparison_search_fields()
        self.refresh_comparison()

    def _comparison_groups(self):
        # v0.8.178 generates the layout from the active site's configured source
        # tables/rules; legacy sites retain the historical layout until migrated.
        return equipment_source_review_groups(self.store)

    def _comparison_columns(self):
        return [column for _group, _color, columns in self._comparison_groups() for column in columns]

    def _populate_comparison_search_fields(self) -> None:
        if not hasattr(self, "comparison_search_field"):
            return
        current = self.comparison_search_field.currentData() or "*"
        self.comparison_search_field.blockSignals(True)
        self.comparison_search_field.clear()
        self.comparison_search_field.addItem("All Columns", "*")
        for group, _color, columns in self._comparison_groups():
            for key, label, _width in columns:
                display = label if group in {"Remarks", "Resolution"} else f"{group} · {label}"
                self.comparison_search_field.addItem(display, key)
        restore = self.comparison_search_field.findData(current)
        self.comparison_search_field.setCurrentIndex(restore if restore >= 0 else 0)
        self.comparison_search_field.blockSignals(False)

    def _comparison_source_group_names(self) -> set[str]:
        if self.store:
            config = get_equipment_comparison_config(self.store, bootstrap=False)
            if config.get("sources"):
                names = set()
                for source in config.get("sources", []):
                    path = configurable_source_path(self.store, source)
                    names.add(clean(source.get("title")) or (path.stem if path else "Source"))
                return names
        return {"SE", "ZENON DB", "ZENON SLD", "ADMS DB", "ADMS SLD"}

    def _refresh_analysis_filter_options(self) -> None:
        if not hasattr(self, "analysis_combo"):
            return
        current = clean(self.analysis_combo.currentData()) or "ALL ANALYSIS"
        self.analysis_combo.blockSignals(True)
        self.analysis_combo.clear()
        for label, key in (
            ("ALL ANALYSIS", "ALL ANALYSIS"), ("PASSED", "PASSED"),
            ("ANY MISMATCH", "ANY MISMATCH"), ("1 ISSUE", "1 ISSUE"),
            ("2 ISSUES", "2 ISSUES"), ("MULTIPLE ISSUES", "MULTIPLE ISSUES"),
            ("CRITICAL", "CRITICAL"),
        ):
            self.analysis_combo.addItem(label, key)
        config = get_equipment_comparison_config(self.store, bootstrap=False) if self.store else {"sources": []}
        if config.get("sources"):
            for rule in config.get("comparisons", []):
                rule_id = clean(rule.get("id"))
                if rule_id:
                    self.analysis_combo.addItem(f"{clean(rule.get('title')) or 'Comparison'} MISMATCH", f"RULE::{rule_id.upper()}")
        else:
            for field in ("NAME", "FEEDER", "SMART", "TYPE", "IP"):
                self.analysis_combo.addItem(f"{field} MISMATCH", f"{field} MISMATCH")
        restore = self.analysis_combo.findData(current)
        self.analysis_combo.setCurrentIndex(restore if restore >= 0 else 0)
        self.analysis_combo.blockSignals(False)

    def _comparison_search_text(self, data: dict, field_key: str, review_text: str) -> str:
        if field_key == "comments":
            return clean(review_text)
        if field_key and field_key != "*":
            return clean(data.get(field_key))
        return " | ".join(clean(data.get(k)) for k, _label, _width in self._comparison_columns()) + " | " + clean(review_text)

    def _configure_comparison_headers(self):
        # Internal keys remain fixed; application-global Display Names affect only the
        # visible App/Excel presentation labels.
        groups = self._comparison_groups()
        columns = [column for _group, _color, cols in groups for column in cols]
        if hasattr(self, "comparison_header"):
            self.comparison_header.set_groups(groups)
        self.comparison_table.setColumnCount(len(columns))
        if hasattr(self.comparison_table, "set_source_group_boundaries"):
            self.comparison_table.set_source_group_boundaries(
                groups, self._comparison_source_group_names()
            )

        # Visibility is computed from the explicit hidden set every time the
        # schema is configured.  Therefore a brand-new built-in or USER column
        # is visible automatically, while only columns the reviewer explicitly
        # hid remain hidden.
        current_keys = {key for key, _label, _width in columns}
        protected_keys = equipment_review_protected_column_keys(self.store) & current_keys
        source_group_names = self._comparison_source_group_names()
        source_review_keys = {
            key
            for group, _color, group_columns in groups
            if group in source_group_names
            for key, _label, _width in group_columns
        }
        # v0.8.168: Source Mapping's Show checkbox is the single source-of-truth
        # for physical source-column visibility.  equipment_source_review_groups
        # already removes rows hidden in Map Fields, so every remaining source
        # key must be visible here.  Purge legacy review-level hides to avoid a
        # contradictory state where Map Fields says Show but Review hides it.
        stale_source_hides = self.comparison_hidden_keys & source_review_keys
        if stale_source_hides:
            self.comparison_hidden_keys -= source_review_keys
        # A protected SYSTEM field can never remain hidden, including when an
        # older release persisted it in the explicit hidden set.
        stale_protected = self.comparison_hidden_keys & protected_keys
        if stale_protected:
            self.comparison_hidden_keys -= protected_keys
        if stale_source_hides or stale_protected:
            save_review_hidden_columns(self.comparison_hidden_keys, "rmu_data_review")
        self.comparison_visible_keys = (current_keys - self.comparison_hidden_keys) | protected_keys | source_review_keys

        self.comparison_table.setHorizontalHeaderLabels([label for _key, label, _width in columns])
        self._comparison_column_keys = [key for key, _label, _width in columns]
        self._populate_comparison_search_fields()
        self._refresh_analysis_filter_options()
        # Applying schema/default widths must not overwrite a manual width while
        # the table is being rebuilt.  Saved widths win by stable column key;
        # columns first seen at this site use the schema's normal initial width.
        self._comparison_applying_column_widths = True
        try:
            for index, (key, label, width) in enumerate(columns):
                initial_width = max(70, int(width * 1.05))
                target_width = self.comparison_column_widths.get(key, initial_width)
                self.comparison_table.setColumnWidth(index, max(55, min(2400, int(target_width))))
                item = self.comparison_table.horizontalHeaderItem(index)
                if item:
                    group = next((g for g, _c, cols in groups if any(k == key for k, _l, _w in cols)), "")
                    base_tip = f"{group} / {label}" if group and group != "Index" else label
                    resize_tip = ui_tr(
                        "Drag the header divider to resize; double-click the header to fit content",
                        self.ui_language,
                    )
                    item.setToolTip(f"{base_tip}\n\n{resize_tip}")
        finally:
            self._comparison_applying_column_widths = False
        self._apply_comparison_column_visibility()

    @staticmethod
    def _comparison_width_sample(records, limit: int = 180) -> list[dict]:
        """Return a bounded, evenly distributed sample for column auto-fit.

        Equipment sites commonly contain 2,000+ rows and tens of dynamic
        source fields.  Qt's resizeColumnToContents() scans every cell and can
        make the UI noticeably stall.  Sampling from the whole unfiltered data
        set keeps widths representative and stable across filter/search changes
        while bounding GUI-thread work.
        """
        rows = list(records or [])
        if len(rows) <= max(1, int(limit)):
            return rows
        limit = max(2, int(limit))
        last = len(rows) - 1
        indexes = {round(i * last / (limit - 1)) for i in range(limit)}
        return [rows[index] for index in sorted(indexes)]

    def _comparison_auto_width_for_column(
        self, key: str, label: str, schema_width: int, records: list[dict], shown: list[dict] | None = None
    ) -> int:
        """Calculate a practical content width for one Equipment Review column.

        Width starts from the existing schema default, expands for the header
        and sampled values, and is capped so one abnormal long cell cannot make
        the rest of the review grid unusable.
        """
        table_metrics = QFontMetrics(self.comparison_table.font())
        header_metrics = QFontMetrics(self.comparison_table.horizontalHeader().font())
        minimum = max(70, int(schema_width * 1.05))
        maximum = 520
        target = max(minimum, header_metrics.horizontalAdvance(clean(label)) + 32)

        if key == "comments" and shown:
            source_records = list(shown)
            value_getter = lambda entry: clean(entry.get("resolution_display"))
            sampled_records = self._comparison_width_sample(source_records, 120)
        else:
            source_records = list(records)
            value_getter = lambda record: clean(record.get(key, ""))
            sampled_records = self._comparison_width_sample(source_records, 180)

        # Always include the longest textual value from the full data set in
        # addition to the evenly distributed sample.  This avoids missing a
        # rare long processed_name / Functional Location near an unsampled row
        # while still keeping expensive font-metric work bounded.
        longest_record = max(
            source_records,
            key=lambda record: max((len(line) for line in value_getter(record).splitlines()), default=0),
            default=None,
        )
        if longest_record is not None and longest_record not in sampled_records:
            sampled_records.append(longest_record)
        values = [value_getter(record) for record in sampled_records]

        for value in values:
            if not value:
                continue
            # A multiline Resolution/Remarks cell should fit its longest useful
            # line, not the full joined string.  Measuring a bounded prefix also
            # protects against pasted blobs while the 520 px cap keeps layout
            # readable.
            for line in str(value).splitlines()[:6]:
                line = line.replace("\t", "    ")[:180]
                if not line:
                    continue
                target = max(target, table_metrics.horizontalAdvance(line) + 30)
                if target >= maximum:
                    return maximum
        return max(55, min(maximum, int(target)))

    def _auto_fit_comparison_columns(
        self, rows: list[dict] | None = None, shown: list[dict] | None = None, only_keys: set[str] | None = None
    ) -> None:
        """Auto-size non-manual Equipment Review columns from real content.

        Manual widths saved by v0.8.188 always win.  Columns without a manual
        override are fitted from the header plus an evenly distributed sample
        of the *full* current equipment data set, so changing a search/filter
        does not make widths jump around.
        """
        if not hasattr(self, "comparison_table"):
            return
        columns = list(self._comparison_columns())
        if not columns:
            return
        full_rows = list(rows if rows is not None else (getattr(self, "_comparison_last_rows", []) or []))
        shown_rows = list(shown if shown is not None else (getattr(self, "_comparison_last_shown", []) or []))
        requested = {clean(key) for key in (only_keys or set()) if clean(key)}

        self._comparison_applying_column_widths = True
        try:
            for index, (key, label, schema_width) in enumerate(columns):
                if requested and key not in requested:
                    continue
                # A user drag is an explicit presentation preference and must
                # never be silently overwritten by automatic sizing.
                if key in self.comparison_column_widths:
                    continue
                target = self._comparison_auto_width_for_column(
                    key, label, schema_width, full_rows, shown_rows
                )
                self.comparison_table.setColumnWidth(index, target)
        finally:
            self._comparison_applying_column_widths = False

    def _auto_fit_comparison_section(self, logical_index: int) -> None:
        """Reset one manually resized column back to content-aware auto-fit."""
        if logical_index < 0 or logical_index >= len(self._comparison_column_keys):
            return
        key = clean(self._comparison_column_keys[logical_index])
        if not key:
            return
        if key in self.comparison_column_widths:
            self.comparison_column_widths.pop(key, None)
            self._comparison_width_save_timer.start()
        self._auto_fit_comparison_columns(only_keys={key})
        self.statusBar().showMessage(
            ui_tr("Column width fitted to current content", self.ui_language), 2500
        )

    def _on_comparison_column_resized(self, logical_index: int, _old_size: int, new_size: int) -> None:
        """Remember reviewer-driven Equipment Data Review column widths.

        QHeaderView emits sectionResized continuously while the mouse is being
        dragged.  Keep those updates in memory immediately, but debounce the
        QSettings write so a wide-column drag stays smooth even on slower field
        laptops.
        """
        if self._comparison_applying_column_widths:
            return
        # Hiding/showing a section can emit a transient zero-width resize.
        # That is not a reviewer drag and must not destroy the remembered width.
        if int(new_size) < 55:
            return
        if logical_index < 0 or logical_index >= len(self._comparison_column_keys):
            return
        key = clean(self._comparison_column_keys[logical_index])
        if not key:
            return
        self.comparison_column_widths[key] = max(55, min(2400, int(new_size)))
        self._comparison_width_save_timer.start()

    def _persist_comparison_column_widths(self) -> None:
        if not hasattr(self, "settings"):
            return
        payload = {
            str(key): int(width)
            for key, width in self.comparison_column_widths.items()
            if str(key).strip() and int(width) >= 55
        }
        self.settings.setValue(
            "comparison/column_widths_json",
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def _apply_comparison_column_visibility(self):
        if not hasattr(self, "comparison_table"):
            return
        for index, (key, _label, _width) in enumerate(self._comparison_columns()):
            self.comparison_table.setColumnHidden(index, key not in self.comparison_visible_keys)
        header = self.comparison_table.horizontalHeader()
        header.viewport().update()

    def open_comparison_columns(self):
        all_groups = self._comparison_groups()
        source_group_names = self._comparison_source_group_names()
        # v0.8.168: physical source-field visibility is controlled only in Map
        # Fields.  The generic Columns dialog remains for App/meta columns such
        # as Index, Source Coverage, Analysis, Remarks and Resolution, avoiding
        # two conflicting visibility controls for the same source column.
        dialog_groups = tuple(group for group in all_groups if group[0] not in source_group_names)
        current_keys = {key for _group, _color, cols in dialog_groups for key, _label, _width in cols}
        protected_keys = equipment_review_protected_column_keys(self.store) & current_keys
        dialog = ColumnVisibilityDialog(
            dialog_groups, self.comparison_visible_keys, protected_keys, self
        )
        translate_widget_tree(dialog, self.ui_language)
        if dialog.exec() != QDialog.Accepted:
            return
        requested_visible = set(dialog.visible_keys()) | protected_keys
        # Preserve preferences for columns that are temporarily absent from the
        # current schema, but update the explicit hidden state for every column
        # shown in this dialog. SYSTEM calculation columns are forcibly removed
        # from hidden preferences and therefore stay visible on every site.
        self.comparison_hidden_keys = (self.comparison_hidden_keys - current_keys) | (current_keys - requested_visible)
        self.comparison_hidden_keys -= protected_keys
        save_review_hidden_columns(self.comparison_hidden_keys, "rmu_data_review")
        self.comparison_visible_keys = (current_keys - self.comparison_hidden_keys) | protected_keys
        self._apply_comparison_column_visibility()
        self.statusBar().showMessage(ui_tr("Equipment Data Review column view saved", self.ui_language), 4000)

    def reset_comparison_columns(self):
        # Reset means the real default: ALL columns that exist now are visible.
        # Future columns are also visible automatically because the explicit
        # hidden set is empty until the reviewer hides something again.
        self.comparison_hidden_keys.clear()
        save_review_hidden_columns(set(), "rmu_data_review")
        self.comparison_visible_keys = {key for key, _label, _width in self._comparison_columns()}
        self.comparison_visible_keys |= equipment_review_protected_column_keys(self.store)
        self._apply_comparison_column_visibility()
        self.statusBar().showMessage(
            ui_tr("Equipment Data Review columns reset: all current and future new columns are visible by default", self.ui_language), 5000
        )

    # ------------------------- DB Smart Report -------------------------
    def _build_db_smart_page(self):
        """Build the Signal Mapping module as an RMU-first review workflow.

        The mapping/validation engine is unchanged.  This page only changes
        presentation: reviewers first choose one RMU, then review that RMU's
        signals split into Analog (point number >= 13000) and Status/Cmd
        (point number < 13000).
        """
        page, layout = self._page_container()

        header_row = QHBoxLayout()
        header_row.addWidget(PageHeader(
            "Signal Mapping Review",
            "Review signal mapping grouped by RMU.",
        ), 1)
        standard_btn = QPushButton("Update STANDARD...")
        standard_btn.setToolTip("Open Settings to upload multiple STANDARD workbooks and explicitly choose the active reference.")
        standard_btn.clicked.connect(lambda: self.set_page(8))
        header_row.addWidget(standard_btn, alignment=Qt.AlignBottom)
        self.db_smart_refresh_btn = QPushButton("Refresh Mapping")
        self.db_smart_refresh_btn.setObjectName("Primary")
        self.db_smart_refresh_btn.setToolTip("Re-read the Signal Mapping source files and rebuild validation results in the background.")
        self.db_smart_refresh_btn.clicked.connect(self._refresh_db_smart_mapping_with_feedback)
        header_row.addWidget(self.db_smart_refresh_btn, alignment=Qt.AlignBottom)
        layout.addLayout(header_row)

        # Compact source/status strip. Full paths remain available as tooltips,
        # keeping the main page free of long filesystem descriptions.
        source_card = QFrame(); source_card.setObjectName("Card")
        source_box = QHBoxLayout(source_card); source_box.setContentsMargins(14, 9, 14, 9)
        source_box.setSpacing(14)
        self.db_smart_source_label = QLabel("Sources: —")
        self.db_smart_sheet_label = QLabel("Mode: calculated")
        self.db_smart_meta_label = QLabel("Rows: 0")
        for label in (self.db_smart_source_label, self.db_smart_sheet_label, self.db_smart_meta_label):
            label.setObjectName("Muted")
        source_box.addWidget(self.db_smart_source_label)
        source_box.addWidget(self.db_smart_sheet_label)
        source_box.addWidget(self.db_smart_meta_label)
        source_box.addStretch(1)
        open_btn = QPushButton("Open IOA File")
        open_btn.clicked.connect(self.open_db_smart_source)
        source_box.addWidget(open_btn)
        layout.addWidget(source_card)

        # One concise global status line replaces the previous long workflow
        # explanation. Detailed behavior remains in tooltips/context menus.
        summary_card = QFrame(); summary_card.setObjectName("SoftCard")
        summary_box = QHBoxLayout(summary_card); summary_box.setContentsMargins(12, 8, 12, 8)
        self.db_smart_summary = QLabel("No Signal Mapping Review loaded")
        self.db_smart_summary.setObjectName("Muted")
        summary_box.addWidget(self.db_smart_summary, 1)
        layout.addWidget(summary_card)

        self.db_smart_stack = QStackedWidget()

        # Neutral surface used only while Signal Mapping is being prepared.
        # Never show the failure/unavailable message during a normal load: that
        # message is reserved for a confirmed missing-input or worker failure.
        # The animated busy popup already provides the user-visible loading
        # feedback, so this surface intentionally contains no warning text.
        self.db_smart_loading = QFrame()
        self.db_smart_loading.setObjectName("SignalMappingLoadingSurface")
        self.db_smart_loading.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.db_smart_empty = EmptyState(
            "Signal Mapping Review is not available",
            "Load ZENON-ADMS-IOA.csv and ADMS-SLD.csv, then run validation.",
        )

        # ---------------- RMU overview ----------------
        self.db_smart_rmu_page = QWidget()
        rmu_page_layout = QVBoxLayout(self.db_smart_rmu_page)
        rmu_page_layout.setContentsMargins(0, 0, 0, 0)
        rmu_page_layout.setSpacing(10)

        rmu_controls = QFrame(); rmu_controls.setObjectName("Card")
        rmu_cbox = QHBoxLayout(rmu_controls); rmu_cbox.setContentsMargins(14, 9, 14, 9)
        self.db_smart_rmu_search = QLineEdit()
        self.db_smart_rmu_search.setClearButtonEnabled(True)
        self.db_smart_rmu_search.setPlaceholderText("Search RMU...")
        self.db_smart_rmu_search.setMinimumWidth(260)
        self.db_smart_rmu_filter = QComboBox()
        self.db_smart_rmu_filter.addItems(["ALL RMUS", "ISSUES ONLY"])
        for i, key in enumerate(("ALL RMUS", "ISSUES ONLY")):
            self.db_smart_rmu_filter.setItemData(i, key)
        mark_combo_for_translation(self.db_smart_rmu_filter)
        self.db_smart_rmu_search.textChanged.connect(self._render_db_smart_rmu_list)
        self.db_smart_rmu_filter.currentIndexChanged.connect(self._render_db_smart_rmu_list)
        rmu_cbox.addWidget(self.db_smart_rmu_search, 1)
        rmu_cbox.addWidget(self.db_smart_rmu_filter)
        rmu_page_layout.addWidget(rmu_controls)

        self.db_smart_rmu_table = QTableWidget(0, 9)
        self.db_smart_rmu_table.setHorizontalHeaderLabels([
            "RMU", "Type", "Total", "Analog", "Status/Cmd",
            "Matched", "Mismatched", "Closed", "Need Action",
        ])
        _configure_table_base(self.db_smart_rmu_table)
        self.db_smart_rmu_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.db_smart_rmu_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.db_smart_rmu_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.db_smart_rmu_table.verticalHeader().setVisible(False)
        self.db_smart_rmu_table.verticalHeader().setDefaultSectionSize(38)
        rmu_header = self.db_smart_rmu_table.horizontalHeader()
        # Keep the RMU overview visually balanced.  v0.8.45 stretched the RMU
        # column across all unused width, creating a very large empty cell area
        # on wide screens.  Spread the available width across all summary
        # columns instead; no business data or grouping logic changes.
        rmu_header.setSectionResizeMode(QHeaderView.Stretch)
        rmu_header.setMinimumSectionSize(82)
        self.db_smart_rmu_table.cellClicked.connect(self._open_db_smart_rmu_from_row)
        rmu_page_layout.addWidget(self.db_smart_rmu_table, 1)

        # ---------------- RMU detail ----------------
        self.db_smart_detail_page = QWidget()
        detail_layout = QVBoxLayout(self.db_smart_detail_page)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(10)

        detail_head = QFrame(); detail_head.setObjectName("Card")
        detail_head_box = QHBoxLayout(detail_head); detail_head_box.setContentsMargins(14, 9, 14, 9)
        back_btn = QPushButton("← All RMUs")
        back_btn.clicked.connect(self._show_db_smart_rmu_overview)
        self.db_smart_detail_title = QLabel("RMU —")
        self.db_smart_detail_title.setStyleSheet("font-size:12pt;font-weight:750;")
        self.db_smart_detail_summary = QLabel("")
        self.db_smart_detail_summary.setObjectName("Muted")
        detail_head_box.addWidget(back_btn)
        detail_head_box.addSpacing(6)
        detail_head_box.addWidget(self.db_smart_detail_title)
        detail_head_box.addSpacing(12)
        detail_head_box.addWidget(self.db_smart_detail_summary, 1)
        detail_layout.addWidget(detail_head)

        self.db_smart_category_tabs = QTabBar()
        self.db_smart_category_tabs.setExpanding(False)
        self.db_smart_category_tabs.addTab("Status / Cmd")
        self.db_smart_category_tabs.addTab("Analog")
        self.db_smart_category_tabs.currentChanged.connect(self._db_smart_category_changed)
        detail_layout.addWidget(self.db_smart_category_tabs)

        controls = QFrame(); controls.setObjectName("Card")
        cbox = QHBoxLayout(controls); cbox.setContentsMargins(14, 9, 14, 9)
        self.db_smart_search_field = QComboBox()
        self.db_smart_search_field.setMinimumWidth(185)
        self.db_smart_search_field.setToolTip("Choose a column, or search across all visible signal data.")
        self.db_smart_search = QLineEdit(); self.db_smart_search.setClearButtonEnabled(True)
        self.db_smart_search.setPlaceholderText("Search signal...")
        self._db_smart_search_timer = QTimer(self)
        self._db_smart_search_timer.setSingleShot(True)
        self._db_smart_search_timer.setInterval(180)
        self._db_smart_search_timer.timeout.connect(self._render_db_smart_rows)
        self.db_smart_search.textChanged.connect(lambda _text: self._db_smart_search_timer.start())
        self.db_smart_search_field.currentIndexChanged.connect(self._render_db_smart_rows)
        self.db_smart_review_combo = QComboBox()
        self.db_smart_review_combo.addItems(["ALL REVIEWS", "UNREVIEWED", "CLOSED", "NEEDS ACTION"])
        for i, key in enumerate(("ALL REVIEWS", "UNREVIEWED", "CLOSED", "NEEDS ACTION")):
            self.db_smart_review_combo.setItemData(i, key)
        mark_combo_for_translation(self.db_smart_review_combo)
        self.db_smart_review_combo.currentIndexChanged.connect(self._render_db_smart_rows)
        self.db_smart_result_combo = QComboBox()
        self.db_smart_result_combo.addItems(["ALL RESULTS", "MATCHED", "MISMATCHED", "ZENON EXTRA"])
        for i, key in enumerate(("ALL RESULTS", "MATCHED", "MISMATCHED", "ZENON EXTRA")):
            self.db_smart_result_combo.setItemData(i, key)
        mark_combo_for_translation(self.db_smart_result_combo)
        self.db_smart_result_combo.currentIndexChanged.connect(self._render_db_smart_rows)
        self.db_smart_show_all_btn = QPushButton("Show All")
        self.db_smart_show_all_btn.clicked.connect(self._show_all_db_smart)
        self.db_smart_clear_selection_btn = QPushButton("Clear Selection")
        self.db_smart_clear_selection_btn.clicked.connect(self._clear_db_smart_selection)
        self.db_smart_status_btn = QPushButton("Set Status")
        self.db_smart_status_btn.setToolTip("Set Unreviewed / Closed / Needs Action for the selected signal row(s).")
        self.db_smart_status_btn.clicked.connect(self.set_db_smart_review_status)
        self.db_smart_comment_btn = QPushButton("Action / Remark")
        self.db_smart_comment_btn.setToolTip("Choose ADD / MODIFY / DELETE and enter the required reviewer remark for one selected signal row. Both are saved in Comments.")
        self.db_smart_comment_btn.clicked.connect(self._edit_selected_db_smart_comment)
        columns_btn = QPushButton("Columns")
        columns_btn.clicked.connect(self.open_db_smart_columns)
        cbox.addWidget(self.db_smart_search_field)
        cbox.addWidget(self.db_smart_search, 1)
        cbox.addWidget(self.db_smart_review_combo)
        cbox.addWidget(self.db_smart_result_combo)
        cbox.addWidget(self.db_smart_show_all_btn)
        cbox.addWidget(self.db_smart_clear_selection_btn)
        cbox.addWidget(self.db_smart_status_btn)
        cbox.addWidget(self.db_smart_comment_btn)
        cbox.addWidget(columns_btn)
        detail_layout.addWidget(controls)

        self.db_smart_table = SpreadsheetTableWidget(0, 0)
        self.db_smart_header = GroupedReportHeader((), self.db_smart_table)
        self.db_smart_table.setHorizontalHeader(self.db_smart_header)
        self.db_smart_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._register_spreadsheet_table(self.db_smart_table)
        self.db_smart_table.verticalHeader().setVisible(False)
        self.db_smart_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.db_smart_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.db_smart_table.setWordWrap(False)
        self.db_smart_table.cellDoubleClicked.connect(self.edit_db_smart_cell)
        self.db_smart_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.db_smart_table.customContextMenuRequested.connect(self._show_db_smart_status_context_menu)
        self.db_smart_table.verticalHeader().setDefaultSectionSize(32)

        # In RMU detail the cabinet identity is already in the page header. Keep
        # only the persistent manual Checked flag and Human Review frozen, matching
        # the RMU Data Review workflow without repeating RMU/Type on every row.
        self.db_smart_locator = SpreadsheetTableWidget(0, 2)
        db_locator_groups = (("Review", "#E8EDF3", (
            ("locator_checked", "Checked", 74),
            ("locator_review", "Review", 115),
        )),)
        self.db_smart_locator_header = GroupedReportHeader(db_locator_groups, self.db_smart_locator)
        self.db_smart_locator.setHorizontalHeader(self.db_smart_locator_header)
        self.db_smart_locator.setHorizontalHeaderLabels(["Checked", "Review"])
        self.db_smart_locator.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.db_smart_locator.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.db_smart_locator.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.db_smart_locator.verticalHeader().setVisible(False)
        self.db_smart_locator.verticalHeader().setDefaultSectionSize(32)
        self.db_smart_locator.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.db_smart_locator.setColumnWidth(0, 74)
        self.db_smart_locator.setColumnWidth(1, 115)
        self.db_smart_locator.setFixedWidth(74 + 115 + 4)
        self.db_smart_locator.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.db_smart_locator.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.db_smart_locator.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.db_smart_locator.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.db_smart_locator.setFocusPolicy(Qt.ClickFocus)
        self.db_smart_locator.cellClicked.connect(self._activate_db_smart_row_from_locator)
        self.db_smart_locator.cellDoubleClicked.connect(self._edit_db_smart_locator_review)
        self.db_smart_locator.setContextMenuPolicy(Qt.CustomContextMenu)
        self.db_smart_locator.customContextMenuRequested.connect(self._show_db_smart_locator_status_context_menu)
        self.db_smart_locator.itemSelectionChanged.connect(self._sync_db_smart_selection_from_locator)
        self.db_smart_table.itemSelectionChanged.connect(self._sync_db_smart_locator_selection)
        self.db_smart_table.verticalScrollBar().valueChanged.connect(self.db_smart_locator.verticalScrollBar().setValue)
        self.db_smart_locator.verticalScrollBar().valueChanged.connect(self.db_smart_table.verticalScrollBar().setValue)
        self.db_smart_table.hoverRowChanged.connect(self.db_smart_locator.set_tracked_hover_row)
        self.db_smart_locator.hoverRowChanged.connect(self.db_smart_table.set_tracked_hover_row)
        self.db_smart_table.activeRowChanged.connect(self.db_smart_locator.set_tracked_active_row)

        self.db_smart_table_host = QWidget()
        host_layout = QHBoxLayout(self.db_smart_table_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(6)
        self.db_smart_locator_host = QWidget()
        locator_layout = QVBoxLayout(self.db_smart_locator_host)
        locator_layout.setContentsMargins(0, 0, 0, 0)
        locator_layout.setSpacing(0)
        locator_layout.addWidget(self.db_smart_locator, 1)
        self.db_smart_locator_scroll_spacer = QWidget()
        self.db_smart_locator_scroll_spacer.setFixedHeight(0)
        locator_layout.addWidget(self.db_smart_locator_scroll_spacer, 0)
        self.db_smart_locator_host.setFixedWidth(74 + 115 + 4)
        host_layout.addWidget(self.db_smart_locator_host, 0)
        host_layout.addWidget(self.db_smart_table, 1)

        # Use the otherwise-empty right side of the RMU detail view for a
        # reviewer-facing summary of ZENON-only points and where they are
        # implemented in ADMS.  Clicking a summary item (or the automatic
        # Comments cell in the grid) navigates to and highlights the actual
        # ADMS implementation row(s).
        self.db_smart_impl_panel = QFrame()
        self.db_smart_impl_panel.setObjectName("Card")
        self.db_smart_impl_panel.setMinimumWidth(300)
        self.db_smart_impl_panel.setMaximumWidth(390)
        self.db_smart_impl_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        impl_layout = QVBoxLayout(self.db_smart_impl_panel)
        impl_layout.setContentsMargins(12, 12, 12, 12)
        impl_layout.setSpacing(8)
        # Current-RMU follow-up summary.  This makes the right-side panel useful
        # for both tasks the field reviewer performs here: first identify every
        # signal that still needs modification, then locate where ZENON-only
        # points are implemented in ADMS.
        need_title = QLabel("Need Action Summary")
        need_title.setStyleSheet("font-weight:750;font-size:11pt;")
        impl_layout.addWidget(need_title)
        self.db_smart_need_action_summary = QLabel("Total 0 · Analog 0 · Status/Cmd 0")
        self.db_smart_need_action_summary.setObjectName("Muted")
        self.db_smart_need_action_summary.setWordWrap(True)
        impl_layout.addWidget(self.db_smart_need_action_summary)
        self.db_smart_need_action_list = QListWidget()
        self.db_smart_need_action_list.setWordWrap(True)
        self.db_smart_need_action_list.setAlternatingRowColors(False)
        self.db_smart_need_action_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.db_smart_need_action_list.setMaximumHeight(235)
        self.db_smart_need_action_list.itemClicked.connect(self._locate_db_smart_need_action_from_summary)
        impl_layout.addWidget(self.db_smart_need_action_list, 0)

        impl_title = QLabel("ADMS Implementation Summary")
        impl_title.setStyleSheet("font-weight:750;font-size:11pt;")
        impl_layout.addWidget(impl_title)
        self.db_smart_impl_summary = QLabel("ZENON-only points for this RMU")
        self.db_smart_impl_summary.setObjectName("Muted")
        self.db_smart_impl_summary.setWordWrap(True)
        impl_layout.addWidget(self.db_smart_impl_summary)
        self.db_smart_impl_list = QListWidget()
        self.db_smart_impl_list.setWordWrap(True)
        self.db_smart_impl_list.setAlternatingRowColors(False)
        self.db_smart_impl_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.db_smart_impl_list.itemClicked.connect(self._locate_db_smart_implementation_from_summary)
        impl_layout.addWidget(self.db_smart_impl_list, 1)
        self.db_smart_impl_hint = QLabel("Click a Need Action item to jump to that signal. Click an ADMS implementation item, or its automatic Comments cell, to highlight the ADMS implementation.")
        self.db_smart_impl_hint.setObjectName("Muted")
        self.db_smart_impl_hint.setWordWrap(True)
        impl_layout.addWidget(self.db_smart_impl_hint)
        host_layout.addWidget(self.db_smart_impl_panel, 0)

        self.db_smart_table.cellClicked.connect(self._db_smart_detail_cell_clicked)
        self.db_smart_table.horizontalScrollBar().rangeChanged.connect(
            lambda _minimum, _maximum: QTimer.singleShot(0, self._sync_db_smart_locator_geometry)
        )
        detail_layout.addWidget(self.db_smart_table_host, 1)

        self.db_smart_review_views = QStackedWidget()
        self.db_smart_review_views.addWidget(self.db_smart_rmu_page)
        self.db_smart_review_views.addWidget(self.db_smart_detail_page)
        self.db_smart_stack.addWidget(self.db_smart_loading)
        self.db_smart_stack.addWidget(self.db_smart_empty)
        self.db_smart_stack.addWidget(self.db_smart_review_views)
        layout.addWidget(self.db_smart_stack, 1)
        return page

    def _db_smart_row_value(self, row, key: str) -> str:
        report = getattr(self, "db_smart_report", None)
        if not report:
            return ""
        index = next((i for i, (column_key, _label, _width) in enumerate(report.columns) if column_key == key), None)
        if index is None or index >= len(row.values):
            return ""
        return clean(row.values[index])

    def _refresh_db_smart_need_action_summary(self, rmu: str) -> None:
        if not hasattr(self, "db_smart_need_action_list"):
            return
        self.db_smart_need_action_list.clear()
        report = getattr(self, "db_smart_report", None)
        selected_rmu = clean(rmu)
        if not report or not self.store or not selected_rmu:
            self.db_smart_need_action_summary.setText("Total 0 · Analog 0 · Status/Cmd 0")
            return

        review_map = self.store.db_smart_review_map()
        items = []
        analog_count = 0
        status_count = 0
        for row in report.rows:
            if clean(row.rmu) != selected_rmu:
                continue
            review = review_map.get(row.row_key, {})
            if clean(review.get("review_status")).upper() != "NEEDS ACTION":
                continue
            category_key = self._db_smart_row_category(row)
            category = "Analog" if category_key == "ANALOG" else "Status/Cmd"
            if category_key == "ANALOG":
                analog_count += 1
            else:
                status_count += 1
            adms_name = self._db_smart_row_value(row, "adms_signal_name")
            adms_dot = self._db_smart_row_value(row, "adms_dot_no")
            zenon_name = self._db_smart_row_value(row, "zenon_signal_name")
            zenon_dot = self._db_smart_row_value(row, "zenon_dot_no")
            signal_name = adms_name or zenon_name or "Signal"
            dot = adms_dot or zenon_dot
            comment = clean(review.get("comments")) or clean(getattr(row, "analysis_detail", ""))
            line = f"{category} · {signal_name}" + (f" · DOT {dot}" if dot else "")
            if comment:
                line += f"\nAction: {comment}"
            item = QListWidgetItem(line)
            item.setData(Qt.ItemDataRole.UserRole, row.row_key)
            item.setToolTip(comment or line)
            item.setBackground(QColor("#FDECEC"))
            item.setSizeHint(QSize(0, 70 if comment else 54))
            items.append((0 if category_key == "ANALOG" else 1, signal_name.casefold(), item))

        for _category_order, _signal_name, item in sorted(items, key=lambda value: (value[0], value[1])):
            self.db_smart_need_action_list.addItem(item)

        total = analog_count + status_count
        self.db_smart_need_action_summary.setText(
            f"Total {total} · Analog {analog_count} · Status/Cmd {status_count}"
        )
        if total == 0:
            empty = QListWidgetItem("No signal Needs Action items for this RMU.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setForeground(QColor(COLORS["muted"]))
            empty.setSizeHint(QSize(0, 44))
            self.db_smart_need_action_list.addItem(empty)

    def _locate_db_smart_need_action_from_summary(self, item: QListWidgetItem) -> None:
        row_key = clean(item.data(Qt.ItemDataRole.UserRole))
        if row_key:
            self._locate_db_smart_review_row(row_key)

    def _locate_db_smart_review_row(self, row_key: str) -> None:
        report = getattr(self, "db_smart_report", None)
        if not report or not row_key:
            return
        target = next((row for row in report.rows if row.row_key == row_key), None)
        if not target:
            return

        self._db_smart_implementation_highlight_keys = set()
        self._db_smart_need_action_highlight_keys = {row_key}
        target_category = self._db_smart_row_category(target)
        self._db_smart_signal_category = target_category
        if hasattr(self, "db_smart_category_tabs"):
            self.db_smart_category_tabs.blockSignals(True)
            self.db_smart_category_tabs.setCurrentIndex(1 if target_category == "ANALOG" else 0)
            self.db_smart_category_tabs.blockSignals(False)

        widgets = [self.db_smart_search_field, self.db_smart_search, self.db_smart_review_combo, self.db_smart_result_combo]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.db_smart_search_field.setCurrentIndex(0)
            self.db_smart_search.clear()
            self.db_smart_review_combo.setCurrentIndex(0)
            self.db_smart_result_combo.setCurrentIndex(0)
        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self._render_db_smart_rows()
        row_by_key = {key: i for i, key in enumerate(getattr(self, "db_smart_row_keys", []))}
        visual_row = row_by_key.get(row_key)
        if visual_row is None:
            self.statusBar().showMessage("Need Action signal is not visible in the current RMU view.", 5000)
            return
        self._syncing_db_smart_selection = True
        try:
            self._select_complete_rows(self.db_smart_table, [visual_row])
            self._select_complete_rows(self.db_smart_locator, [visual_row])
        finally:
            self._syncing_db_smart_selection = False
        first_item = self.db_smart_table.item(visual_row, 0)
        if first_item is not None:
            self.db_smart_table.scrollToItem(first_item, QAbstractItemView.PositionAtCenter)
        self.db_smart_table.set_tracked_active_row(visual_row)
        self.db_smart_locator.set_tracked_active_row(visual_row)
        signal_name = self._db_smart_row_value(target, "adms_signal_name") or self._db_smart_row_value(target, "zenon_signal_name") or "signal"
        self.statusBar().showMessage(ui_tr(f"Highlighted Need Action signal: {signal_name}.", self.ui_language), 5000)

    def _refresh_db_smart_implementation_summary(self, rmu: str) -> None:
        if not hasattr(self, "db_smart_impl_list"):
            return
        self.db_smart_impl_list.clear()
        report = getattr(self, "db_smart_report", None)
        selected_rmu = clean(rmu)
        if not report or not selected_rmu:
            self.db_smart_impl_summary.setText("No RMU selected")
            return

        source_rows = [
            row for row in report.rows
            if clean(row.rmu) == selected_rmu and signal_row_is_zenon_only(row)
        ]
        found_count = 0
        for source_row in source_rows:
            zenon_name = self._db_smart_row_value(source_row, "zenon_signal_name") or "ZENON signal"
            matches = zenon_only_adms_match_rows(source_row, report.rows)
            category = "Analog" if self._db_smart_row_category(source_row) == "ANALOG" else "Status/Cmd"
            if matches:
                found_count += 1
                first = matches[0]
                adms_name = self._db_smart_row_value(first, "adms_signal_name") or "ADMS signal"
                adms_dot = self._db_smart_row_value(first, "adms_dot_no")
                target = adms_name + (f" · DOT {adms_dot}" if adms_dot else "")
                if len(matches) > 1:
                    target += f" · +{len(matches) - 1} match(es)"
                text = f"{category} · {zenon_name}\n→ {target}"
            else:
                text = f"{category} · {zenon_name}\n→ ADMS implementation not found"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, source_row.row_key)
            item.setToolTip(clean(getattr(source_row, "suggested_comment", "")) or text)
            item.setBackground(QColor("#EAF7F0") if matches else QColor("#FFF4D6"))
            item.setSizeHint(QSize(0, 58))
            self.db_smart_impl_list.addItem(item)

        if not source_rows:
            empty = QListWidgetItem("No ZENON-only implementation notes for this RMU.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            empty.setForeground(QColor(COLORS["muted"]))
            empty.setSizeHint(QSize(0, 48))
            self.db_smart_impl_list.addItem(empty)
            self.db_smart_impl_summary.setText("0 ZENON-only points")
            return

        unresolved = len(source_rows) - found_count
        suffix = f" · {unresolved} not found" if unresolved else ""
        self.db_smart_impl_summary.setText(
            f"{len(source_rows)} ZENON-only point(s) · {found_count} ADMS implementation(s) located{suffix}"
        )

    def _locate_db_smart_implementation_from_summary(self, item: QListWidgetItem) -> None:
        source_key = clean(item.data(Qt.ItemDataRole.UserRole))
        if source_key:
            self._locate_db_smart_implementation(source_key)

    def _db_smart_detail_cell_clicked(self, visual_row: int, column: int) -> None:
        # Comments is column 1 in the detail grid. Automatic ZENON-only
        # comments are navigational: one click highlights where ADMS actually
        # implements that signal. Manual comments remain normal review text.
        if column != 1 or visual_row < 0 or visual_row >= len(getattr(self, "db_smart_row_keys", [])):
            return
        row_key = self.db_smart_row_keys[visual_row]
        report = getattr(self, "db_smart_report", None)
        if not report:
            return
        row = next((candidate for candidate in report.rows if candidate.row_key == row_key), None)
        if row and signal_row_is_zenon_only(row) and clean(getattr(row, "suggested_comment", "")):
            self._locate_db_smart_implementation(row_key)

    def _locate_db_smart_implementation(self, source_row_key: str) -> None:
        report = getattr(self, "db_smart_report", None)
        if not report or not source_row_key:
            return
        source_row = next((row for row in report.rows if row.row_key == source_row_key), None)
        if not source_row:
            return
        matches = zenon_only_adms_match_rows(source_row, report.rows)
        if not matches:
            self._db_smart_need_action_highlight_keys = set()
            self._db_smart_implementation_highlight_keys = set()
            self._render_db_smart_rows()
            self.statusBar().showMessage("No confident ADMS implementation match was found for this ZENON-only signal.", 5000)
            return

        self._db_smart_need_action_highlight_keys = set()
        self._db_smart_implementation_highlight_keys = {row.row_key for row in matches}
        target_category = self._db_smart_row_category(matches[0])
        self._db_smart_signal_category = target_category
        if hasattr(self, "db_smart_category_tabs"):
            self.db_smart_category_tabs.blockSignals(True)
            self.db_smart_category_tabs.setCurrentIndex(1 if target_category == "ANALOG" else 0)
            self.db_smart_category_tabs.blockSignals(False)

        # Navigation must be reliable even when a search/result filter currently
        # hides the target row.  Reset only the transient Signal Mapping filters;
        # column visibility and review data remain untouched.
        widgets = [self.db_smart_search_field, self.db_smart_search, self.db_smart_review_combo, self.db_smart_result_combo]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.db_smart_search_field.setCurrentIndex(0)
            self.db_smart_search.clear()
            self.db_smart_review_combo.setCurrentIndex(0)
            self.db_smart_result_combo.setCurrentIndex(0)
        finally:
            for widget in widgets:
                widget.blockSignals(False)

        self._render_db_smart_rows()
        row_by_key = {key: i for i, key in enumerate(getattr(self, "db_smart_row_keys", []))}
        visual_rows = [row_by_key[key] for key in self._db_smart_implementation_highlight_keys if key in row_by_key]
        if not visual_rows:
            self.statusBar().showMessage("ADMS implementation was located but is not visible in the current RMU view.", 5000)
            return

        self._syncing_db_smart_selection = True
        try:
            self._select_complete_rows(self.db_smart_table, visual_rows)
            self._select_complete_rows(self.db_smart_locator, visual_rows)
        finally:
            self._syncing_db_smart_selection = False
        first_row = min(visual_rows)
        first_item = self.db_smart_table.item(first_row, 0)
        if first_item is not None:
            self.db_smart_table.scrollToItem(first_item, QAbstractItemView.PositionAtCenter)
        self.db_smart_table.set_tracked_active_row(first_row)
        self.db_smart_locator.set_tracked_active_row(first_row)
        source_name = self._db_smart_row_value(source_row, "zenon_signal_name") or "ZENON signal"
        self.statusBar().showMessage(
            f"Highlighted {len(visual_rows)} ADMS implementation row(s) for {source_name}.", 5000
        )

    def _db_smart_navigation_highlight_active(self) -> bool:
        """Return whether Signal Mapping currently has a transient jump highlight."""
        return bool(
            getattr(self, "_db_smart_implementation_highlight_keys", set())
            or getattr(self, "_db_smart_need_action_highlight_keys", set())
        )

    def _clear_db_smart_navigation_highlight(self, *, clear_selection: bool = False) -> None:
        """Clear temporary Signal Mapping jump/highlight state without rebuilding the grid.

        ADMS implementation / Need Action navigation paints the located source row blue.
        That blue is a temporary locator aid, not review data, so an ordinary click
        elsewhere should remove it immediately.  Restore only the affected visible
        cells to their normal automatic-validation fill instead of re-rendering the
        whole RMU table.
        """
        highlighted = set(getattr(self, "_db_smart_implementation_highlight_keys", set()))
        highlighted.update(getattr(self, "_db_smart_need_action_highlight_keys", set()))
        self._db_smart_implementation_highlight_keys = set()
        self._db_smart_need_action_highlight_keys = set()

        report = getattr(self, "db_smart_report", None)
        table = getattr(self, "db_smart_table", None)
        if highlighted and report is not None and table is not None:
            source_rows = {row.row_key: row for row in report.rows if row.row_key in highlighted}
            visual_rows = {key: index for index, key in enumerate(getattr(self, "db_smart_row_keys", []))}
            table.setUpdatesEnabled(False)
            try:
                for row_key in highlighted:
                    visual_row = visual_rows.get(row_key)
                    row = source_rows.get(row_key)
                    if visual_row is None or row is None:
                        continue
                    analysis_result = ""
                    if report.analysis_column is not None and report.analysis_column < len(row.values):
                        analysis_result = clean(row.values[report.analysis_column]).upper()
                    if analysis_result == "TRUE" or signal_row_is_zenon_only(row):
                        base_fill = QColor("#EAF7F0")
                    elif analysis_result == "FALSE":
                        base_fill = QColor("#FDECEC")
                    else:
                        base_fill = QColor("#FFF4D6")
                    for column in range(table.columnCount()):
                        # Review and Comments own their independent fills; the Analysis
                        # result cell also owns TRUE/FALSE colouring and was never
                        # replaced by the locator blue.
                        if column in (0, 1):
                            continue
                        source_column = column - 2
                        if source_column == report.analysis_column:
                            continue
                        item = table.item(visual_row, column)
                        if item is not None:
                            item.setBackground(base_fill)
            finally:
                table.setUpdatesEnabled(True)
                table.viewport().update()

        if clear_selection:
            self._syncing_db_smart_selection = True
            try:
                if hasattr(self, "db_smart_table"):
                    self.db_smart_table.clear_spreadsheet_selection()
                if hasattr(self, "db_smart_locator"):
                    self.db_smart_locator.clear_spreadsheet_selection()
                    self.db_smart_locator.set_tracked_active_row(-1)
            finally:
                self._syncing_db_smart_selection = False

    def _sync_db_smart_locator_geometry(self) -> None:
        if not hasattr(self, "db_smart_locator_scroll_spacer") or not hasattr(self, "db_smart_table"):
            return
        hbar = self.db_smart_table.horizontalScrollBar()
        reserve = hbar.sizeHint().height() if hbar.maximum() > hbar.minimum() else 0
        self.db_smart_locator_scroll_spacer.setFixedHeight(max(0, reserve))
        self.db_smart_locator.verticalScrollBar().setValue(self.db_smart_table.verticalScrollBar().value())

    def _show_all_db_smart(self) -> None:
        """Clear every Signal Mapping filter with immediate animated feedback."""
        widgets = [self.db_smart_search_field, self.db_smart_search, self.db_smart_review_combo, self.db_smart_result_combo]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self.db_smart_search_field.setCurrentIndex(0)
            self.db_smart_search.clear()
            self.db_smart_review_combo.setCurrentIndex(0)
            self.db_smart_result_combo.setCurrentIndex(0)
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self.db_smart_show_all_btn.setEnabled(False)
        self._show_busy_operation(
            "signal-show-all",
            "Loading all signal rows...",
            "Clearing filters and refreshing the current Signal Mapping view. Please wait.",
        )
        QTimer.singleShot(0, self._complete_show_all_db_smart)

    def _complete_show_all_db_smart(self) -> None:
        try:
            self._render_db_smart_rows()
            self.statusBar().showMessage(ui_tr("Signal Mapping filters cleared · showing all rows", self.ui_language), 2500)
        finally:
            if hasattr(self, "db_smart_show_all_btn"):
                self.db_smart_show_all_btn.setEnabled(True)
            self._hide_busy_operation("signal-show-all")

    def _sync_db_smart_selection_from_locator(self) -> None:
        if getattr(self, "_syncing_db_smart_selection", False):
            return
        if not hasattr(self, "db_smart_table") or not hasattr(self, "db_smart_locator"):
            return
        self._syncing_db_smart_selection = True
        try:
            self._select_complete_rows(self.db_smart_table, self._selected_table_rows(self.db_smart_locator))
        finally:
            self._syncing_db_smart_selection = False

    def _sync_db_smart_locator_selection(self) -> None:
        if getattr(self, "_syncing_db_smart_selection", False):
            return
        if not hasattr(self, "db_smart_table") or not hasattr(self, "db_smart_locator"):
            return
        self._syncing_db_smart_selection = True
        try:
            self._select_complete_rows(self.db_smart_locator, self._selected_table_rows(self.db_smart_table))
        finally:
            self._syncing_db_smart_selection = False

    def _on_db_smart_locator_check_passed_toggled(self, row_key: str, rmu: str, checked: bool) -> None:
        """Persist the Signal locator checkbox as a manual verification/pass record."""
        if getattr(self, "_rendering_db_smart_checks", False) or not self.store or not self.db_smart_report:
            return
        row_key = clean(row_key)
        if not row_key:
            return
        row = next((item for item in self.db_smart_report.rows if item.row_key == row_key), None)
        if row is None:
            return
        try:
            site_name = self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name
            self.store.update_db_smart_check_passed(
                row_key=row_key, rmu=rmu or row.rmu, passed=bool(checked), modified_by=self.user_name,
                source_hash=self.db_smart_report.source_hash,
                row_hash=signal_review_row_hash(row, self.db_smart_report.analysis_column),
                site_name=site_name,
                reason="Signal manually checked / passed in Row Locator",
                metadata=signal_review_metadata(self.db_smart_report, row),
            )
            # Keep checkbox interaction immediate.  Audit/history/export are
            # secondary views and refresh lazily on navigation instead of
            # synchronously rebuilding large tables for every single tick.
            self._dirty_pages.update({0, 4, 6, 7})
            state = "PASS" if checked else "cleared"
            self.statusBar().showMessage(ui_tr(f"Signal manual check {state} · RMU {clean(rmu) or '—'} · saved", self.ui_language), 2500)
        except Exception as exc:
            QMessageBox.critical(self, "Signal Check", f"{type(exc).__name__}: {exc}")
            self._render_db_smart_rows()


    def _clear_db_smart_selection(self) -> None:
        self._clear_db_smart_navigation_highlight(clear_selection=False)
        self._syncing_db_smart_selection = True
        try:
            if hasattr(self, "db_smart_table"):
                self.db_smart_table.clear_spreadsheet_selection()
            if hasattr(self, "db_smart_locator"):
                self.db_smart_locator.clear_spreadsheet_selection()
                self.db_smart_locator.set_tracked_active_row(-1)
        finally:
            self._syncing_db_smart_selection = False
        self.statusBar().showMessage(ui_tr("Signal selection cleared", self.ui_language), 2500)

    def _show_db_smart_status_context_menu(self, pos) -> None:
        if self._prepare_context_cell(self.db_smart_table, pos) < 0:
            return
        menu = QMenu(self)
        menu.addAction(ui_tr("Mark Unreviewed", self.ui_language), lambda: self.set_db_smart_review_status("UNREVIEWED"))
        menu.addAction(ui_tr("Mark Closed", self.ui_language), lambda: self.set_db_smart_review_status("CLOSED"))
        menu.addAction(ui_tr("Needs Action", self.ui_language), lambda: self.set_db_smart_review_status("NEEDS ACTION"))
        menu.addSeparator()
        menu.addAction("Edit Action / Remark...", self._edit_selected_db_smart_comment)
        menu.addAction("View Signal Lifecycle...", self._open_selected_signal_lifecycle)
        menu.exec(self.db_smart_table.viewport().mapToGlobal(pos))

    def _show_db_smart_locator_status_context_menu(self, pos) -> None:
        row = self._prepare_context_cell(self.db_smart_locator, pos, whole_row=True)
        if row < 0:
            return
        self._sync_db_smart_selection_from_locator()
        menu = QMenu(self)
        menu.addAction(ui_tr("Mark Unreviewed", self.ui_language), lambda: self.set_db_smart_review_status("UNREVIEWED"))
        menu.addAction(ui_tr("Mark Closed", self.ui_language), lambda: self.set_db_smart_review_status("CLOSED"))
        menu.addAction(ui_tr("Needs Action", self.ui_language), lambda: self.set_db_smart_review_status("NEEDS ACTION"))
        menu.addSeparator()
        menu.addAction("Edit Action / Remark...", self._edit_selected_db_smart_comment)
        menu.addAction("View Signal Lifecycle...", self._open_selected_signal_lifecycle)
        menu.exec(self.db_smart_locator.viewport().mapToGlobal(pos))

    def _edit_selected_db_smart_comment(self) -> None:
        keys = self._selected_db_smart_row_keys()
        if len(keys) != 1:
            QMessageBox.information(self, "Signal Mapping Review", "Select exactly one signal row, then click Action / Remark.")
            return
        row_index = next((i for i, key in enumerate(getattr(self, "db_smart_row_keys", [])) if key == keys[0]), -1)
        if row_index >= 0:
            self.edit_db_smart_cell(row_index, 1)

    def _open_selected_signal_lifecycle(self) -> None:
        if not self.store:
            return
        keys = self._selected_db_smart_row_keys()
        if len(keys) != 1:
            QMessageBox.information(self, "Signal Lifecycle", "Select exactly one signal row to view its Need Action lifecycle.")
            return
        key = clean(keys[0])
        cases = self.store.issue_lifecycle("SIGNAL", key)
        if not cases:
            QMessageBox.information(self, "Signal Lifecycle", "This signal has not entered formal Needs Action yet.")
            return
        IssueLifecycleDialog(self.store, "SIGNAL", key, self).exec()

    def _activate_db_smart_row_from_locator(self, row: int, _column: int = 0) -> None:
        """Activate the locator row without disturbing Ctrl/Shift multi-selection."""
        if not hasattr(self, "db_smart_table") or row < 0 or row >= self.db_smart_table.rowCount():
            return
        old_h = self.db_smart_table.horizontalScrollBar().value()
        current_col = self.db_smart_table.currentColumn()
        if current_col < 0 or current_col >= self.db_smart_table.columnCount() or self.db_smart_table.isColumnHidden(current_col):
            current_col = next((c for c in range(self.db_smart_table.columnCount()) if not self.db_smart_table.isColumnHidden(c)), 0)
        item = self.db_smart_table.item(row, current_col)
        if item is not None:
            index = self.db_smart_table.model().index(row, current_col)
            self.db_smart_table.selectionModel().setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.db_smart_table.scrollToItem(item, QAbstractItemView.EnsureVisible)
        self.db_smart_table.set_tracked_active_row(row)
        self.db_smart_locator.set_tracked_active_row(row)
        QTimer.singleShot(0, lambda value=old_h: self.db_smart_table.horizontalScrollBar().setValue(value))

    def _edit_db_smart_locator_review(self, row: int, column: int) -> None:
        """Double-click the frozen Signal Review cell to edit one signal directly."""
        if column != 1:
            return
        self._activate_db_smart_row_from_locator(row, column)
        self.set_db_smart_review_status()

    @staticmethod
    def _db_smart_parse_point_number(value: object) -> int | None:
        """Return an integer point number from CSV/Excel-style values."""
        text = clean(value).replace(",", "")
        if not text:
            return None
        try:
            return int(float(text))
        except (TypeError, ValueError):
            match = re.search(r"-?\d+(?:\.\d+)?", text)
            if not match:
                return None
            try:
                return int(float(match.group(0)))
            except ValueError:
                return None

    def _db_smart_point_number(self, row) -> int | None:
        """Resolve the business point number without changing mapping logic.

        ADMS is the primary review target. STANDARD then ZENON are fallbacks so
        rows with a temporarily blank ADMS point remain visible in the same
        Analog/Status-Cmd workflow instead of disappearing from the UI.
        """
        index_map = getattr(self, "_db_smart_value_index", {})
        for key in ("adms_dot_no", "standard_dot_no", "zenon_dot_no"):
            index = index_map.get(key)
            if index is None or index >= len(row.values):
                continue
            number = self._db_smart_parse_point_number(row.values[index])
            if number is not None:
                return number
        return None

    def _db_smart_row_category(self, row) -> str:
        point_no = self._db_smart_point_number(row)
        # Keep a row with no usable point number in Status/Cmd so validation
        # gaps are never hidden. All numeric rows follow the requested rule.
        return "ANALOG" if point_no is not None and point_no >= 13000 else "STATUS_CMD"

    def _db_smart_rmu_metrics_map(self) -> dict[str, dict[str, object]]:
        """Build RMU metrics and include every site-level open Signal action.

        TRUE/FALSE metrics come only from current STANDARD/ADMS validation.
        NEEDS ACTION is a persistent human workflow state, so older unresolved
        records remain counted even if a mapping refresh changes their row key.
        """
        report = self.db_smart_report
        if not report or not self.store:
            return {}
        review_map = self.store.db_smart_review_map()
        type_issue_map = rmu_type_issue_map(self.store)
        alias_map = signal_review_alias_map(report)
        legacy_by_target: dict[str, list[str]] = {}
        for legacy, target in alias_map.items():
            legacy_by_target.setdefault(target, []).append(legacy)
        site_name = clean(self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name)

        def belongs(review: dict) -> bool:
            recorded = clean((review or {}).get("site_name"))
            return not recorded or not site_name or recorded.casefold() == site_name.casefold()

        metrics: dict[str, dict[str, object]] = {}
        consumed_review_keys: set[str] = set()
        for row in report.rows:
            rmu = clean(row.rmu)
            if not rmu:
                continue
            item = metrics.setdefault(rmu, {
                "rmu": rmu, "type": "", "total": 0, "analog": 0, "status_cmd": 0,
                "compared": 0, "matched": 0, "mismatched": 0, "zenon_extra": 0,
                "closed": 0, "needs_action": 0, "unreviewed": 0,
                "unreviewed_mismatch": 0, "historical_need_action": 0,
                "type_issue": rmu in type_issue_map,
                "type_issue_tooltip": type_issue_map.get(rmu, ""),
            })
            if not item["type"] and len(row.values) > 1 and clean(row.values[1]):
                item["type"] = clean(row.values[1])
            item["total"] += 1
            if self._db_smart_row_category(row) == "ANALOG":
                item["analog"] += 1
            else:
                item["status_cmd"] += 1
            result = ""
            if report.analysis_column is not None and report.analysis_column < len(row.values):
                result = clean(row.values[report.analysis_column]).upper()
            if result in {"TRUE", "FALSE"}:
                item["compared"] += 1
            item["matched"] += result == "TRUE"
            item["mismatched"] += result == "FALSE"
            item["zenon_extra"] += signal_row_is_zenon_only(row)

            review_key = row.row_key
            review_record = review_map.get(review_key, {})
            if not review_record:
                for legacy in legacy_by_target.get(row.row_key, []):
                    candidate = review_map.get(legacy, {})
                    if candidate:
                        review_record = candidate
                        review_key = legacy
                        break
            if review_record:
                consumed_review_keys.add(review_key)
            status = signal_review_display_status(
                result, review_record.get("review_status"),
                explicit=review_record_is_explicit(review_record),
                zenon_only=signal_row_is_zenon_only(row),
            )
            item["closed"] += status == "CLOSED"
            item["needs_action"] += status == "NEEDS ACTION"
            item["unreviewed"] += status == "UNREVIEWED"
            item["unreviewed_mismatch"] += result == "FALSE" and status == "UNREVIEWED"

        # Any unresolved review record not represented by the current calculated
        # rows is still an open action for this site and must remain visible in
        # the RMU/global Need Action totals at export time.
        for row_key, review in review_map.items():
            if row_key in consumed_review_keys or not belongs(review):
                continue
            if clean((review or {}).get("review_status")).upper() != "NEEDS ACTION":
                continue
            rmu = clean((review or {}).get("rmu")) or "Historical"
            item = metrics.setdefault(rmu, {
                "rmu": rmu, "type": "", "total": 0, "analog": 0, "status_cmd": 0,
                "compared": 0, "matched": 0, "mismatched": 0, "zenon_extra": 0,
                "closed": 0, "needs_action": 0, "unreviewed": 0,
                "unreviewed_mismatch": 0, "historical_need_action": 0,
                "type_issue": rmu in type_issue_map,
                "type_issue_tooltip": type_issue_map.get(rmu, ""),
            })
            item["needs_action"] += 1
            item["historical_need_action"] += 1
        return metrics

    def _db_smart_rmu_metrics(self, rmu: str) -> dict[str, object]:
        key = clean(rmu)
        return self._db_smart_rmu_metrics_map().get(key, {
            "rmu": key, "type": "", "total": 0, "analog": 0, "status_cmd": 0,
            "compared": 0, "matched": 0, "mismatched": 0, "zenon_extra": 0,
            "closed": 0, "needs_action": 0, "unreviewed": 0,
            "unreviewed_mismatch": 0, "historical_need_action": 0,
            "type_issue": False, "type_issue_tooltip": "",
        })

    @staticmethod
    def _db_smart_rmu_sort_key(value: str):
        text = clean(value)
        return (0, int(text)) if text.isdigit() else (1, text.casefold())

    def _update_db_smart_global_summary(self, metrics_map: dict[str, dict[str, object]] | None = None) -> None:
        if not self.db_smart_report or not self.store:
            self.db_smart_summary.setText("No Signal Mapping Review loaded")
            return
        metrics_map = metrics_map if metrics_map is not None else self._db_smart_rmu_metrics_map()
        matched = sum(int(item["matched"]) for item in metrics_map.values())
        mismatched = sum(int(item["mismatched"]) for item in metrics_map.values())
        zenon_extra = sum(int(item["zenon_extra"]) for item in metrics_map.values())
        needs_action = sum(int(item["needs_action"]) for item in metrics_map.values())
        closed = sum(int(item["closed"]) for item in metrics_map.values())
        self.db_smart_summary.setText(
            f"RMUs {len(metrics_map)}  ·  Signals {len(self.db_smart_report.rows)}  ·  Matched {matched}  ·  "
            f"Mismatched {mismatched}  ·  ZENON Extra {zenon_extra}  ·  Closed {closed}  ·  Need Action {needs_action}"
        )

    def _render_db_smart_rmu_list(self, *_args) -> None:
        if not hasattr(self, "db_smart_rmu_table") or not self.db_smart_report or not self.store:
            return
        report = self.db_smart_report
        term = self.db_smart_rmu_search.text().strip().casefold() if hasattr(self, "db_smart_rmu_search") else ""
        issues_only = hasattr(self, "db_smart_rmu_filter") and clean(self.db_smart_rmu_filter.currentData()).upper() == "ISSUES ONLY"
        metrics_map = self._db_smart_rmu_metrics_map()
        rmus = sorted(metrics_map, key=self._db_smart_rmu_sort_key)
        metrics = []
        for rmu in rmus:
            item = metrics_map[rmu]
            if term and term not in f"{item['rmu']} {item['type']}".casefold():
                continue
            if issues_only and not (item["needs_action"] or item.get("unreviewed", 0)):
                continue
            metrics.append(item)

        table = self.db_smart_rmu_table
        table.setUpdatesEnabled(False)
        table.setRowCount(len(metrics))
        for visual_row, metric in enumerate(metrics):
            values = [
                metric["rmu"], metric["type"], metric["total"], metric["analog"],
                metric["status_cmd"], metric["matched"], metric["mismatched"],
                metric["closed"], metric["needs_action"],
            ]
            has_need_action = bool(metric["needs_action"])
            has_unreviewed = bool(metric.get("unreviewed", 0))
            has_unreviewed_mismatch = bool(metric.get("unreviewed_mismatch", 0))
            has_type_issue = bool(metric.get("type_issue"))
            type_issue_tooltip = clean(metric.get("type_issue_tooltip"))
            if has_need_action:
                # Human workflow state wins for the normal row background: an RMU
                # stays red-tinted while any signal remains explicitly open.
                fill = QColor("#FDECEC")
            elif has_unreviewed:
                # A technical mismatch that has not yet been reviewed is pending,
                # so show an amber row. Once the reviewer closes it, the summary
                # returns to green even though the historical mismatch count remains.
                fill = QColor("#FFF8E6")
            else:
                # All current issues have been reviewed/closed. Keep the overview
                # green; raw TRUE/FALSE colors remain visible in the detail table.
                fill = QColor("#EAF7F0")
            for col, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setBackground(fill)
                if (col == 6 and has_unreviewed_mismatch) or (col == 8 and has_need_action):
                    cell.setBackground(QColor("#D92D20"))
                    cell.setForeground(QColor("#FFFFFF"))
                    error_font = cell.font(); error_font.setBold(True); cell.setFont(error_font)
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, metric["rmu"])
                    font = cell.font(); font.setBold(True); cell.setFont(font)
                    if has_type_issue:
                        # TYPE suspicion is a cross-module hint, not a workflow row
                        # status.  Highlight only the RMU locator cell in purple and
                        # reuse the RMU Data Review TYPE explanation as its tooltip.
                        cell.setBackground(QColor("#F3E8FF"))
                        cell.setForeground(QColor("#6D28D9"))
                        if type_issue_tooltip:
                            cell.setToolTip(type_issue_tooltip)
                    else:
                        cell.setForeground(QColor(COLORS["info"]))
                        cell.setToolTip(f"Open RMU {metric['rmu']}")
                if col >= 2:
                    cell.setTextAlignment(Qt.AlignCenter)
                table.setItem(visual_row, col, cell)
        table.setUpdatesEnabled(True)
        table.viewport().update()
        self._update_db_smart_global_summary(metrics_map)

    def _show_db_smart_rmu_overview(self, *_args) -> None:
        self._db_smart_selected_rmu = ""
        if hasattr(self, "db_smart_review_views"):
            self.db_smart_review_views.setCurrentWidget(self.db_smart_rmu_page)
        self._clear_db_smart_selection()
        self._render_db_smart_rmu_list()

    def _open_db_smart_rmu_from_row(self, row: int, column: int = 0) -> None:
        # Navigation is intentionally attached only to the RMU cell. Clicking
        # Type/metrics selects the cell/row but must not unexpectedly open detail.
        if column != 0 or not hasattr(self, "db_smart_rmu_table") or row < 0:
            return
        item = self.db_smart_rmu_table.item(row, 0)
        if not item:
            return
        rmu = clean(item.data(Qt.ItemDataRole.UserRole) or item.text())
        self._show_db_smart_rmu_detail(rmu, reset_category=True)

    def _show_db_smart_rmu_detail(self, rmu: str, *, reset_category: bool = False) -> None:
        if not self.db_smart_report or not self.store or not clean(rmu):
            return
        next_rmu = clean(rmu)
        if clean(getattr(self, "_db_smart_selected_rmu", "")) != next_rmu:
            self._db_smart_implementation_highlight_keys = set()
            self._db_smart_need_action_highlight_keys = set()
        self._db_smart_selected_rmu = next_rmu
        metrics = self._db_smart_rmu_metrics(self._db_smart_selected_rmu)
        if reset_category:
            # Opening an RMU always starts on Status / Cmd. Reviewers can switch
            # to Analog explicitly after entering the RMU detail page.
            self._db_smart_signal_category = "STATUS_CMD"
        tab_index = 1 if self._db_smart_signal_category == "ANALOG" else 0
        self.db_smart_category_tabs.blockSignals(True)
        self.db_smart_category_tabs.setTabText(0, f"Status / Cmd ({metrics['status_cmd']})")
        self.db_smart_category_tabs.setTabText(1, f"Analog ({metrics['analog']})")
        self.db_smart_category_tabs.setCurrentIndex(tab_index)
        self.db_smart_category_tabs.blockSignals(False)
        self.db_smart_detail_title.setText(f"RMU {metrics['rmu']}")
        type_text = metrics["type"] or "—"
        historical_note = f"  ·  Historical/Open {metrics.get('historical_need_action', 0)}" if metrics.get("historical_need_action") else ""
        self.db_smart_detail_summary.setText(
            f"Type {type_text}  ·  Total {metrics['total']}  ·  Matched {metrics['matched']}  ·  "
            f"Mismatched {metrics['mismatched']}  ·  ZENON Extra {metrics['zenon_extra']}  ·  "
            f"Closed {metrics['closed']}  ·  Need Action {metrics['needs_action']}{historical_note}"
        )
        self.db_smart_review_views.setCurrentWidget(self.db_smart_detail_page)
        self._render_db_smart_rows()
        QTimer.singleShot(0, self._restore_db_smart_header)

    def _db_smart_category_changed(self, index: int) -> None:
        self._db_smart_signal_category = "STATUS_CMD" if index == 0 else "ANALOG"
        if self._db_smart_selected_rmu:
            self._render_db_smart_rows()

    def _db_smart_groups(self, report: DBSmartReport):
        review_group = ("Review", "#D8E1EA", (
            ("db_review_status", "Review", 145),
            ("db_review_comments", "Comments", 300),
        ))
        source_groups = apply_display_names_to_groups(
            report.group_definitions, self.store, SIGNAL_REVIEW_DISPLAY_BINDINGS
        )
        return (review_group,) + tuple(source_groups)

    def _populate_db_smart_search_fields(self, report: DBSmartReport, groups) -> None:
        if not hasattr(self, "db_smart_search_field"):
            return
        current = self.db_smart_search_field.currentData() or "*"
        self.db_smart_search_field.blockSignals(True)
        self.db_smart_search_field.clear()
        self.db_smart_search_field.addItem("All Columns", "*")
        for group, _color, columns in groups:
            for key, label, _width in columns:
                self.db_smart_search_field.addItem(f"{group} · {label}", key)
        restore = self.db_smart_search_field.findData(current)
        self.db_smart_search_field.setCurrentIndex(restore if restore >= 0 else 0)
        self.db_smart_search_field.blockSignals(False)
        self._db_smart_value_index = {key: index for index, (key, _label, _width) in enumerate(report.columns)}

    def _db_smart_search_text(self, row, status: str, comments: str, field_key: str) -> str:
        if field_key == "db_review_status":
            return clean(status)
        if field_key == "db_review_comments":
            return clean(comments)
        if field_key and field_key != "*":
            index = getattr(self, "_db_smart_value_index", {}).get(field_key)
            if index is not None and index < len(row.values):
                return clean(row.values[index])
            return ""
        return " | ".join((clean(status), clean(comments), *(clean(v) for v in row.values)))

    def _configure_db_smart_table(self, report: DBSmartReport):
        groups = self._db_smart_groups(report)
        columns = [column for _group, _color, cols in groups for column in cols]
        self.db_smart_columns = columns
        self._populate_db_smart_search_fields(report, groups)
        all_keys = {key for key, _label, _width in columns}
        saved = self.settings.value("db_smart/visible_columns", [], type=list)
        compact_default = {
            "db_review_comments",
            "zenon_signal_name", "zenon_dot_no",
            "adms_signal_name", "adms_dot_no",
            "standard_signal_name", "standard_dot_no",
            "analysis_adms_standard",
        } & all_keys
        if not self.db_smart_visible_keys:
            self.db_smart_visible_keys = (set(saved) & all_keys) if saved else set(compact_default)
        else:
            self.db_smart_visible_keys &= all_keys

        # v0.8.45 intentionally hid Comments in the compact default, which made
        # the existing comment workflow difficult to discover. Promote Comments
        # exactly once for upgraded profiles while still allowing users to hide
        # it later from Columns.
        comments_key = "db_review_comments"
        comments_promoted_key = "db_smart/comments_promoted_v0846"
        if comments_key in all_keys and not self.settings.value(comments_promoted_key, False, type=bool):
            self.db_smart_visible_keys.add(comments_key)
            self.settings.setValue(comments_promoted_key, True)
            self.settings.setValue("db_smart/visible_columns", sorted(self.db_smart_visible_keys))
        # The Review state is frozen in the locator; RMU/Type are already in the
        # detail header. They remain available through Columns when desired.
        self.db_smart_table.setColumnCount(len(columns))
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

    def _live_signal_mapping_sources(self, *, rescan: bool = False) -> dict[str, Path]:
        if not self.selected_site:
            return {}
        # Source discovery is explicit. A simple module switch reuses the
        # already discovered SiteInfo; Refresh Mapping/Refresh Sources/Run
        # Validation are the operations that deliberately rescan disk.
        if rescan and self.repository_root:
            live = next((x for x in scan_repository(self.repository_root) if x.name == self.selected_site.name), None)
            if live:
                self.selected_site = live
                self._active_site_signature = self._site_metadata_signature(live)
        sources = dict(self.selected_site.sources) if self.selected_site else {}
        # Startup discovery only knows AUTO filenames. Persistent version pins
        # and external manual mappings live in Project Data, so resolve those
        # explicitly before deciding that Signal Mapping inputs are missing.
        for key in ("ioa", "adms_sld"):
            path = self._effective_site_source_path(key)
            if path is not None and path.exists():
                sources[key] = path
        return sources

    def _present_db_smart_report(self, report: DBSmartReport, reset_count: int = 0) -> None:
        """Render an already-built Signal Mapping report without re-reading files."""
        self._configure_db_smart_table(report)
        modified_ts = max((path.stat().st_mtime for path in report.input_paths if path.exists()), default=0.0)
        modified = datetime.fromtimestamp(modified_ts).strftime("%Y-%m-%d %H:%M") if modified_ts else "—"
        ioa_path = report.input_paths[0] if report.input_paths else report.source_path
        adms_sld_path = report.input_paths[1] if len(report.input_paths) > 1 else Path("ADMS-SLD.csv")
        standard_path = report.input_paths[2] if len(report.input_paths) > 2 else standard_reference_path()
        self.db_smart_source_label.setText("Source order: STANDARD → ADMS → ZENON · ADMS/ZENON from ZENON-ADMS-IOA.csv")
        self.db_smart_source_label.setToolTip(
            f"IOA: {ioa_path}\nADMS SLD: {adms_sld_path}\nSTANDARD: {standard_reference_origin()} {standard_path}"
        )
        self.db_smart_sheet_label.setText("Mode: Calculated")
        self.db_smart_sheet_label.setToolTip(
            f"Calculated from site CSV + ADMS SLD + {standard_reference_origin()} STANDARD"
        )
        reset_note = f" · Review reset {reset_count}" if reset_count else ""
        self.db_smart_meta_label.setText(f"Rows {len(report.rows)} · Updated {modified}{reset_note}")
        self.db_smart_stack.setCurrentWidget(self.db_smart_review_views)
        existing_rmus = {clean(row.rmu) for row in report.rows if clean(row.rmu)}
        if self._db_smart_selected_rmu and self._db_smart_selected_rmu in existing_rmus:
            self._show_db_smart_rmu_detail(self._db_smart_selected_rmu, reset_category=False)
        else:
            self._show_db_smart_rmu_overview()
        self._db_smart_ui_ready = True
        translate_widget_tree(self.db_smart_page, self.ui_language)

    def _refresh_db_smart_mapping_with_feedback(self) -> None:
        """Explicit Refresh Mapping uses the worker path plus animated feedback."""
        if self._source_pipeline_busy():
            self.statusBar().showMessage(ui_tr("Source processing is already running. Please wait for it to finish.", self.ui_language), 4000)
            return
        if not self.selected_site or not self.repository_root:
            QMessageBox.information(self, "Refresh Mapping", "Select a site and Source Workspace first.")
            return
        # Invalidate only the in-memory presentation. The worker re-resolves the
        # active physical files and rebuilds STANDARD → ADMS → ZENON mapping.
        self.db_smart_report = None
        self._db_smart_report_site = ""
        self._db_smart_ui_ready = False
        self._dirty_pages.add(3)
        self._start_signal_mapping_module_load()

    def refresh_db_smart_report(self, *, force: bool = True, rescan: bool = True):
        if not hasattr(self, "db_smart_table"):
            return
        site_name = self.selected_site.name if self.selected_site else ""
        if (
            not force
            and self.db_smart_report is not None
            and self._db_smart_report_site.casefold() == site_name.casefold()
        ):
            if not self._db_smart_ui_ready:
                self._present_db_smart_report(self.db_smart_report)
            return
        sources = self._live_signal_mapping_sources(rescan=rescan)
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
            self._db_smart_report_site = site_name
            self._db_smart_ui_ready = False
            self.db_smart_table.setRowCount(0)
            if hasattr(self, "db_smart_locator"):
                self.db_smart_locator.setRowCount(0)
            self.db_smart_stack.setCurrentWidget(self.db_smart_empty)
            self.db_smart_source_label.setText("Inputs: " + ("missing " + ", ".join(missing) if missing else "—"))
            self.db_smart_sheet_label.setText("Mode: calculated")
            self.db_smart_meta_label.setText("Rows: 0")
            self.db_smart_summary.setText("Signal Mapping Review unavailable")
            translate_widget_tree(self.db_smart_page, self.ui_language)
            return
        try:
            report = build_signal_mapping_report(
                ioa_path, adms_sld_path, standard_path,
                ioa_overrides=self.store.source_column_overrides("ioa"),
                adms_sld_overrides=self.store.source_column_overrides("adms_sld"),
                standard_overrides=self.store.source_column_overrides("standard_reference"),
                ioa_sheet_name=self.store.source_sheet_name("ioa") if hasattr(self.store, "source_sheet_name") else None,
                adms_sld_sheet_name=self.store.source_sheet_name("adms_sld") if hasattr(self.store, "source_sheet_name") else None,
            )
        except Exception as exc:
            self.db_smart_report = None
            self._db_smart_report_site = site_name
            self._db_smart_ui_ready = False
            self.db_smart_table.setRowCount(0)
            if hasattr(self, "db_smart_locator"):
                self.db_smart_locator.setRowCount(0)
            self.db_smart_stack.setCurrentWidget(self.db_smart_empty)
            self.db_smart_source_label.setText(f"Inputs: {ioa_path.name} · {adms_sld_path.name} · {standard_reference_origin()} {standard_path.name}")
            self.db_smart_sheet_label.setText("Mode: calculated")
            self.db_smart_meta_label.setText(f"Error: {type(exc).__name__}: {exc}")
            self.db_smart_summary.setText("Signal Mapping Review unavailable")
            translate_widget_tree(self.db_smart_page, self.ui_language)
            return
        self.db_smart_report = report
        self._db_smart_report_site = site_name
        self._db_smart_ui_ready = False
        reset_count = self._sync_signal_review_fingerprints(report)
        self._present_db_smart_report(report, reset_count)
        self.refresh_dashboard()
        self.refresh_export_page()

    def _capture_db_smart_selection_keys(self) -> list[tuple[str, str]]:
        if not hasattr(self, "db_smart_table"):
            return []
        captured = []
        seen = set()
        row_keys = getattr(self, "db_smart_row_keys", [])
        columns = getattr(self, "db_smart_columns", [])
        for index in self.db_smart_table.selectedIndexes():
            if index.row() >= len(row_keys) or index.column() >= len(columns):
                continue
            pair = (row_keys[index.row()], columns[index.column()][0])
            if pair[0] and pair not in seen:
                seen.add(pair)
                captured.append(pair)
        return captured

    def _restore_db_smart_selection_keys(self, captured: list[tuple[str, str]]) -> None:
        if not captured or not hasattr(self, "db_smart_table"):
            return
        row_by_key = {key: row for row, key in enumerate(getattr(self, "db_smart_row_keys", []))}
        col_by_key = {key: col for col, (key, _label, _width) in enumerate(getattr(self, "db_smart_columns", []))}
        for row_key, column_key in captured:
            row = row_by_key.get(row_key)
            col = col_by_key.get(column_key)
            if row is None or col is None:
                continue
            item = self.db_smart_table.item(row, col)
            if item:
                item.setSelected(True)

    def _render_db_smart_rows(self):
        if not hasattr(self, "db_smart_table") or not self.db_smart_report or not self.store:
            return
        if not self._db_smart_selected_rmu:
            self._render_db_smart_rmu_list()
            return

        captured_selection = self._capture_db_smart_selection_keys()
        report = self.db_smart_report
        review_map = self.store.db_smart_review_map()
        term = self.db_smart_search.text().strip().casefold() if hasattr(self, "db_smart_search") else ""
        search_field = self.db_smart_search_field.currentData() if hasattr(self, "db_smart_search_field") else "*"
        search_field = search_field or "*"
        review_filter = clean(self.db_smart_review_combo.currentData()) if hasattr(self, "db_smart_review_combo") else "ALL REVIEWS"
        result_filter = clean(self.db_smart_result_combo.currentData()) if hasattr(self, "db_smart_result_combo") else "ALL RESULTS"

        selected_rmu = clean(self._db_smart_selected_rmu)
        category = self._db_smart_signal_category
        category_rows = []
        shown = []
        for row in report.rows:
            if clean(row.rmu) != selected_rmu:
                continue
            if self._db_smart_row_category(row) != category:
                continue
            review = review_map.get(row.row_key, {})
            comments = clean(review.get("comments")) or clean(getattr(row, "suggested_comment", ""))
            analysis_result = ""
            if report.analysis_column is not None and report.analysis_column < len(row.values):
                analysis_result = clean(row.values[report.analysis_column]).upper()
            zenon_only = signal_row_is_zenon_only(row)
            status = signal_review_display_status(
                analysis_result, review.get("review_status"),
                explicit=review_record_is_explicit(review),
                zenon_only=zenon_only,
            )
            category_rows.append((row, status, comments, analysis_result, zenon_only))
            if review_filter != "ALL REVIEWS" and status != review_filter:
                continue
            if result_filter == "MATCHED" and analysis_result != "TRUE":
                continue
            if result_filter == "MISMATCHED" and analysis_result != "FALSE":
                continue
            if result_filter == "ZENON EXTRA" and not zenon_only:
                continue
            searchable = self._db_smart_search_text(row, status, comments, str(search_field)).casefold()
            if term and term not in searchable:
                continue
            shown.append((row, status, comments, analysis_result, zenon_only))

        self.db_smart_table.setUpdatesEnabled(False)
        self.db_smart_locator.setUpdatesEnabled(False)
        self._rendering_db_smart_checks = True
        self.db_smart_table.setRowCount(len(shown))
        self.db_smart_locator.setRowCount(len(shown))
        self.db_smart_row_keys = []
        for visual_row, (row, status, comments, analysis_result, zenon_only) in enumerate(shown):
            self.db_smart_table.setRowHeight(visual_row, 32)
            self.db_smart_locator.setRowHeight(visual_row, 32)
            self.db_smart_row_keys.append(row.row_key)
            values = [status, comments, *row.values]
            # Automatic validation paints the source row; Human Review
            # color is isolated to the Review cell/frozen locator.
            if analysis_result == "TRUE" or zenon_only:
                row_fill = QColor("#EAF7F0")
            elif analysis_result == "FALSE":
                row_fill = QColor("#FDECEC")
            else:
                row_fill = QColor("#FFF4D6")
            if (
                row.row_key in getattr(self, "_db_smart_implementation_highlight_keys", set())
                or row.row_key in getattr(self, "_db_smart_need_action_highlight_keys", set())
            ):
                row_fill = QColor("#DCEEFF")
            review_label, review_fill, review_text = _review_visual(status)

            main_rmu = clean(row.values[0]) if len(row.values) > 0 else clean(row.rmu)
            row_type = clean(row.values[1]) if len(row.values) > 1 else ""
            # Persistent manual signal verification, identical in principle to
            # RMU Data Review Checked. It is independent from temporary selection
            # and from the automatic TRUE/FALSE validation result.
            check_record = review_map.get(row.row_key, {})
            passed = bool(int(check_record.get("check_passed") or 0))
            check_host = QWidget()
            check_layout = QHBoxLayout(check_host)
            check_layout.setContentsMargins(0, 0, 0, 0)
            check_layout.setSpacing(0)
            checkbox = QCheckBox()
            checkbox.setChecked(passed)
            checked_by = clean(check_record.get("check_passed_by"))
            checked_at = clean(check_record.get("check_passed_at"))
            check_tip = f"Signal manual verification: {'PASS' if passed else 'not checked'} · RMU {main_rmu}"
            if passed and (checked_by or checked_at):
                check_tip += f" · {checked_by or '—'} · {checked_at or '—'}"
            checkbox.setToolTip(check_tip + "\nChecked means the reviewer inspected this signal and accepted it as passed.")
            checkbox.toggled.connect(
                lambda checked, current_key=row.row_key, current_rmu=main_rmu:
                    self._on_db_smart_locator_check_passed_toggled(current_key, current_rmu, checked)
            )
            check_layout.addStretch(1)
            check_layout.addWidget(checkbox, 0, Qt.AlignCenter)
            check_layout.addStretch(1)
            self.db_smart_locator.setCellWidget(visual_row, 0, check_host)

            locator_item = QTableWidgetItem(review_label)
            locator_item.setBackground(review_fill)
            locator_item.setForeground(review_text)
            locator_item.setTextAlignment(Qt.AlignCenter)
            font = locator_item.font(); font.setBold(True); locator_item.setFont(font)
            locator_item.setToolTip(f"RMU {main_rmu} · {row_type or '—'} · {review_label}" + (" · ZENON-only default" if zenon_only and not review_record_is_explicit(review_map.get(row.row_key, {})) else "") + "\nDouble-click to set Review status.")
            self.db_smart_locator.setItem(visual_row, 1, locator_item)

            for col, value in enumerate(values):
                item = QTableWidgetItem(clean(value))
                item.setBackground(row_fill)
                item.setToolTip(clean(value))
                if col == 0:
                    item.setText(review_label)
                    item.setData(Qt.ItemDataRole.UserRole, row.row_key)
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setBackground(review_fill)
                    item.setForeground(review_text)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setToolTip("Human Review: " + review_label)
                elif col == 1:
                    item.setBackground(QColor("#FFFFFF"))
                    item.setToolTip(comments or "Double-click to choose ADD / MODIFY / DELETE and enter the required remark. Saving it also marks the signal Needs Action.")
                source_col = col - 2
                if source_col == report.analysis_column:
                    normalized = clean(value).upper()
                    if normalized == "TRUE":
                        item.setBackground(QColor("#DDF5E7"))
                    elif normalized == "FALSE":
                        # FALSE is a formal STANDARD-vs-ADMS validation error.
                        # Use a strong red cell so it cannot be mistaken for a
                        # warning or an informational ZENON implementation hint.
                        item.setBackground(QColor("#D92D20"))
                        item.setForeground(QColor("#FFFFFF"))
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setToolTip(row.analysis_detail or clean(value))
                self.db_smart_table.setItem(visual_row, col, item)

        self._apply_db_smart_visibility()
        # Filtering/category changes restore selection by stable row_key + column key.
        self._restore_db_smart_selection_keys(captured_selection)
        self.db_smart_table.setUpdatesEnabled(True)
        self.db_smart_table.viewport().update()
        self._rendering_db_smart_checks = False
        self.db_smart_locator.setUpdatesEnabled(True)
        self.db_smart_locator.viewport().update()
        self._sync_db_smart_locator_geometry()
        self.db_smart_locator.verticalScrollBar().setValue(self.db_smart_table.verticalScrollBar().value())

        metrics = self._db_smart_rmu_metrics(selected_rmu)
        self.db_smart_detail_title.setText(f"RMU {selected_rmu}")
        type_text = metrics["type"] or "—"
        matched_category = sum(item[3] == "TRUE" for item in category_rows)
        mismatched_category = sum(item[3] == "FALSE" for item in category_rows)
        zenon_extra_category = sum(item[4] for item in category_rows)
        self.db_smart_detail_summary.setText(
            f"Type {type_text}  ·  {('Analog' if category == 'ANALOG' else 'Status / Cmd')} {len(category_rows)}  ·  "
            f"Shown {len(shown)}  ·  Matched {matched_category}  ·  Mismatched {mismatched_category}  ·  "
            f"ZENON Extra {zenon_extra_category}  ·  Closed {metrics['closed']}  ·  Need Action {metrics['needs_action']}"
        )
        self._refresh_db_smart_need_action_summary(selected_rmu)
        self._refresh_db_smart_implementation_summary(selected_rmu)
        self._update_db_smart_global_summary()

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

    def set_db_smart_review_status(self, requested_status: str | None = None):
        """Set one of the three Signal Mapping Review states."""
        if not self.store or not self.db_smart_report:
            return
        row_keys = self._selected_db_smart_row_keys()
        if not row_keys:
            QMessageBox.information(self, "Signal Mapping Review", "Select one or more signal cells / rows first.")
            return

        rows_by_key = {row.row_key: row for row in self.db_smart_report.rows}
        options = ["Unreviewed", "Closed", "Needs Action"]
        value_by_label = {
            "Unreviewed": "UNREVIEWED",
            "Closed": "CLOSED",
            "Needs Action": "NEEDS ACTION",
        }
        if requested_status:
            value = normalize_review_status(requested_status)
            selected_label = next((label for label, code in value_by_label.items() if code == value), "Unreviewed")
        else:
            review_map = self.store.db_smart_review_map()
            current_values = set()
            for key in row_keys:
                row = rows_by_key.get(key)
                if not row:
                    continue
                review = review_map.get(key, {})
                result = ""
                if self.db_smart_report.analysis_column is not None and self.db_smart_report.analysis_column < len(row.values):
                    result = clean(row.values[self.db_smart_report.analysis_column]).upper()
                current_values.add(signal_review_display_status(
                    result, review.get("review_status"),
                    explicit=review_record_is_explicit(review),
                    zenon_only=signal_row_is_zenon_only(row),
                ))
            current_value = next(iter(current_values)) if len(current_values) == 1 else "UNREVIEWED"
            current_label = next((label for label, code in value_by_label.items() if code == current_value), "Unreviewed")
            selected_label, ok = QInputDialog.getItem(
                self, "Set Signal Review Status",
                f"{len(row_keys)} signal row(s) selected.\n\nChoose: Unreviewed, Closed or Needs Action.",
                options, options.index(current_label), False,
            )
            if not ok:
                return
            value = value_by_label[selected_label]

        site_name = self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name
        reason_by_value = {
            "UNREVIEWED": "Signal Mapping Review marked Unreviewed",
            "CLOSED": "Signal Mapping Review marked Closed",
            "NEEDS ACTION": "Signal Mapping Review marked Needs Action",
        }
        changed = 0
        for row_key in row_keys:
            row = rows_by_key.get(row_key)
            if not row:
                continue
            self.store.update_db_smart_review(
                row_key=row_key, rmu=row.rmu, field="review_status", value=value,
                modified_by=self.user_name, source_hash=self.db_smart_report.source_hash,
                row_hash=signal_review_row_hash(row, self.db_smart_report.analysis_column), site_name=site_name,
                reason=reason_by_value[value],
                metadata=signal_review_metadata(self.db_smart_report, row),
            )
            changed += 1
        self._render_db_smart_rows()
        self.refresh_changes()
        self.refresh_site_history()
        self.refresh_dashboard()
        self.refresh_export_page()
        self.statusBar().showMessage(
            f"Signal Review updated for {changed} row(s): {selected_label}", 5000
        )

    def edit_db_smart_cell(self, row_index: int, column_index: int):
        if not self.db_smart_report or not self.store or row_index >= len(getattr(self, "db_smart_row_keys", [])):
            return
        if column_index not in {0, 1}:
            QMessageBox.information(self, "Read-only source", "Signal Mapping source values are read-only. Right-click any cell (or use Set Status) to mark the row Unreviewed / Closed / Needs Action; Action / Remark is stored in Comments in project.db.")
            return
        row_key = self.db_smart_row_keys[row_index]
        row = next((item for item in self.db_smart_report.rows if item.row_key == row_key), None)
        if not row:
            return
        review = self.store.db_smart_review_map().get(row_key, {})
        if column_index == 0:
            # Any signal row can receive an explicit manual status. Automatic
            # Validation coverage remains a separate project-readiness condition.
            self.db_smart_table.clear_spreadsheet_selection()
            item = self.db_smart_table.item(row_index, 0)
            if item is not None:
                item.setSelected(True)
                self.db_smart_table.setCurrentItem(item)
            self.set_db_smart_review_status()
            return
        else:
            dialog = SignalActionRemarkDialog(
                rmu=row.rmu, current_comment=clean(review.get("comments")), parent=self
            )
            if dialog.exec() != QDialog.Accepted:
                return
            value = dialog.stored_comment()
            field = "comments"
            reason = "Signal Mapping action / remark updated"
        self.store.update_db_smart_review(
            row_key=row_key, rmu=row.rmu, field=field, value=value, modified_by=self.user_name,
            source_hash=self.db_smart_report.source_hash, row_hash=signal_review_row_hash(row, self.db_smart_report.analysis_column),
            site_name=self.selected_site.name if self.selected_site else "", reason=reason,
            metadata=signal_review_metadata(self.db_smart_report, row),
        )
        if column_index == 1:
            # A concrete ADD / MODIFY / DELETE instruction is itself an open
            # rectification decision. Keep the Review state and PDF issue count
            # aligned with the action the reviewer just entered.
            self.store.update_db_smart_review(
                row_key=row_key, rmu=row.rmu, field="review_status", value="NEEDS ACTION", modified_by=self.user_name,
                source_hash=self.db_smart_report.source_hash, row_hash=signal_review_row_hash(row, self.db_smart_report.analysis_column),
                site_name=self.selected_site.name if self.selected_site else "",
                reason="Signal Mapping action / remark requires rectification",
                metadata=signal_review_metadata(self.db_smart_report, row),
            )
        self._render_db_smart_rows()
        self.refresh_changes()
        self.refresh_site_history()
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
        idesc = QLabel("Whenever a reviewer changes RMU Data Review, Signal Mapping Review, source mapping or Resolution data, the application stores an immutable audit record. Module and Field are shown with business-facing names while the original internal field key remains available in the Field tooltip for technical traceability.")
        idesc.setWordWrap(True)
        idesc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        idesc.setObjectName("Muted")
        ibox.addWidget(ititle)
        ibox.addWidget(idesc)
        layout.addWidget(info)

        self.changes_table = QTableWidget(0, 9)
        headers = ["ID", "Module", "Record", "Field", "Original Value", "New Value", "Reason", "Modified By", "Modified At"]
        self.changes_table.setHorizontalHeaderLabels(headers)
        _configure_table_base(self.changes_table)
        _set_fixed_column(self.changes_table, 0, 64)
        _set_interactive_column(self.changes_table, 1, 190)
        _set_interactive_column(self.changes_table, 2, 150)
        _set_interactive_column(self.changes_table, 3, 190)
        _set_interactive_column(self.changes_table, 4, 210)
        _set_interactive_column(self.changes_table, 5, 210)
        _set_stretch_column(self.changes_table, 6)
        _set_fixed_column(self.changes_table, 7, 130)
        _set_fixed_column(self.changes_table, 8, 180)

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

    # ------------------------- durable site history -------------------------
    def _build_site_history_page(self):
        page, layout = self._page_container()
        header_row = QHBoxLayout()
        header_row.addWidget(
            PageHeader(
                "Site History",
                "Persistent station revisions, issue/action records and signed PDF handover history. These records live in Project Data and survive application upgrades.",
            ),
            1,
        )
        header_row.addStretch()
        new_revision_btn = QPushButton("New Revision")
        new_revision_btn.clicked.connect(self.create_site_revision)
        add_issue_btn = QPushButton("Add Issue / Action")
        add_issue_btn.clicked.connect(self.add_site_issue_action)
        pdf_btn = QPushButton("Export Sign-off PDF")
        pdf_btn.setObjectName("Primary")
        pdf_btn.clicked.connect(self.export_signoff_pdf)
        header_row.addWidget(new_revision_btn, alignment=Qt.AlignBottom)
        header_row.addWidget(add_issue_btn, alignment=Qt.AlignBottom)
        header_row.addWidget(pdf_btn, alignment=Qt.AlignBottom)
        layout.addLayout(header_row)

        summary = QFrame()
        summary.setObjectName("SoftCard")
        sbox = QHBoxLayout(summary)
        sbox.setContentsMargins(18, 12, 18, 12)
        self.site_history_site_label = QLabel("Site: —")
        self.site_history_revision_label = QLabel("Latest revision: —")
        self.site_history_issue_label = QLabel("Issue / Action items: 0")
        self.site_history_tracking_label = QLabel("Equipment Follow-up: Open 0 · Closed 0")
        self.site_history_lifecycle_label = QLabel("Lifecycle: Open 0 · Closed 0")
        self.site_history_audit_label = QLabel("Audit records: 0")
        self.site_history_report_label = QLabel("Sign-off PDFs: 0")
        for widget in (
            self.site_history_site_label,
            self.site_history_revision_label,
            self.site_history_issue_label,
            self.site_history_tracking_label,
            self.site_history_lifecycle_label,
            self.site_history_audit_label,
            self.site_history_report_label,
        ):
            widget.setObjectName("Muted")
            sbox.addWidget(widget)
        sbox.addStretch()
        layout.addWidget(summary)

        splitter = QSplitter(Qt.Vertical)

        upper = QFrame()
        upper.setObjectName("Card")
        ubox = QVBoxLayout(upper)
        ubox.setContentsMargins(16, 14, 16, 14)
        revision_title = QLabel("Revision History")
        revision_title.setObjectName("SectionTitle")
        ubox.addWidget(revision_title)
        self.site_revisions_table = QTableWidget(0, 6)
        self.site_revisions_table.setHorizontalHeaderLabels(
            ["ID", "Revision", "Description", "Snapshot Version", "Created By", "Created At"]
        )
        _configure_table_base(self.site_revisions_table)
        _set_fixed_column(self.site_revisions_table, 0, 60)
        _set_fixed_column(self.site_revisions_table, 1, 135)
        _set_stretch_column(self.site_revisions_table, 2)
        _set_fixed_column(self.site_revisions_table, 3, 135)
        _set_fixed_column(self.site_revisions_table, 4, 130)
        _set_fixed_column(self.site_revisions_table, 5, 175)
        ubox.addWidget(self.site_revisions_table, 1)
        splitter.addWidget(upper)

        tabs = QTabWidget()

        issue_tab = QWidget()
        issue_box = QVBoxLayout(issue_tab)
        issue_box.setContentsMargins(0, 10, 0, 0)
        self.site_issue_table = QTableWidget(0, 10)
        self.site_issue_table.setHorizontalHeaderLabels(
            ["ID", "Revision", "Category", "Equipment", "Issue", "Action Taken", "Result", "Comments", "By", "Updated"]
        )
        _configure_table_base(self.site_issue_table)
        _set_fixed_column(self.site_issue_table, 0, 58)
        _set_fixed_column(self.site_issue_table, 1, 110)
        _set_fixed_column(self.site_issue_table, 2, 115)
        _set_interactive_column(self.site_issue_table, 3, 150)
        _set_interactive_column(self.site_issue_table, 4, 260)
        _set_interactive_column(self.site_issue_table, 5, 260)
        _set_fixed_column(self.site_issue_table, 6, 105)
        _set_interactive_column(self.site_issue_table, 7, 200)
        _set_fixed_column(self.site_issue_table, 8, 120)
        _set_fixed_column(self.site_issue_table, 9, 170)
        issue_box.addWidget(self.site_issue_table)
        tabs.addTab(issue_tab, "Issue / Action Register")

        lifecycle_tab = QWidget()
        lifecycle_box = QVBoxLayout(lifecycle_tab)
        lifecycle_box.setContentsMargins(0, 10, 0, 0)
        lifecycle_note = QLabel(
            "Formal Need Action lifecycle for both RMUs and Signals. Every new Needs Action opens a case; comments, "
            "RMU resolutions, Signal ADD/MODIFY/DELETE remarks, validation changes and the explicit close are appended "
            "to its timeline. Reopening a closed item creates a new case. Double-click a case to inspect every event."
        )
        lifecycle_note.setObjectName("Muted")
        lifecycle_note.setWordWrap(True)
        lifecycle_box.addWidget(lifecycle_note)
        self.site_lifecycle_table = QTableWidget(0, 13)
        self.site_lifecycle_table.setHorizontalHeaderLabels([
            "Case", "Type", "RMU", "Point", "Signal", "Status", "Opened", "Opened By",
            "Closed", "Closed By", "Participants", "Events", "Last Activity"
        ])
        _configure_table_base(self.site_lifecycle_table)
        _set_fixed_column(self.site_lifecycle_table, 0, 78)
        _set_fixed_column(self.site_lifecycle_table, 1, 82)
        _set_fixed_column(self.site_lifecycle_table, 2, 100)
        _set_fixed_column(self.site_lifecycle_table, 3, 95)
        _set_stretch_column(self.site_lifecycle_table, 4)
        _set_fixed_column(self.site_lifecycle_table, 5, 90)
        _set_fixed_column(self.site_lifecycle_table, 6, 165)
        _set_fixed_column(self.site_lifecycle_table, 7, 120)
        _set_fixed_column(self.site_lifecycle_table, 8, 165)
        _set_fixed_column(self.site_lifecycle_table, 9, 120)
        _set_fixed_column(self.site_lifecycle_table, 10, 95)
        _set_fixed_column(self.site_lifecycle_table, 11, 75)
        _set_fixed_column(self.site_lifecycle_table, 12, 165)
        self.site_lifecycle_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.site_lifecycle_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.site_lifecycle_table.cellDoubleClicked.connect(self._open_site_lifecycle_case)
        lifecycle_box.addWidget(self.site_lifecycle_table)
        tabs.addTab(lifecycle_tab, "Need Action Lifecycle")

        tracking_tab = QWidget()
        tracking_box = QVBoxLayout(tracking_tab)
        tracking_box.setContentsMargins(0, 10, 0, 0)
        tracking_note = QLabel(
            "Once any equipment enters Needs Action it stays in this follow-up register until that equipment is explicitly Closed. "
            "A later source refresh or Unreviewed reset does not silently remove the open follow-up item."
        )
        tracking_note.setObjectName("Muted")
        tracking_note.setWordWrap(True)
        tracking_box.addWidget(tracking_note)
        self.site_rmu_tracking_table = QTableWidget(0, 10)
        self.site_rmu_tracking_table.setHorizontalHeaderLabels([
            "Equipment", "Type", "Status", "First Needs Action", "Last Needs Action", "Closed At",
            "Open Count", "Opened By", "Closed By", "Last Reason"
        ])
        _configure_table_base(self.site_rmu_tracking_table)
        _set_interactive_column(self.site_rmu_tracking_table, 0, 150)
        _set_fixed_column(self.site_rmu_tracking_table, 1, 110)
        _set_fixed_column(self.site_rmu_tracking_table, 2, 95)
        _set_fixed_column(self.site_rmu_tracking_table, 3, 175)
        _set_fixed_column(self.site_rmu_tracking_table, 4, 175)
        _set_fixed_column(self.site_rmu_tracking_table, 5, 175)
        _set_fixed_column(self.site_rmu_tracking_table, 6, 95)
        _set_fixed_column(self.site_rmu_tracking_table, 7, 120)
        _set_fixed_column(self.site_rmu_tracking_table, 8, 120)
        _set_stretch_column(self.site_rmu_tracking_table, 9)
        tracking_box.addWidget(self.site_rmu_tracking_table)
        tabs.addTab(tracking_tab, "Equipment Needs Action Tracking")

        audit_tab = QWidget()
        audit_box = QVBoxLayout(audit_tab)
        audit_box.setContentsMargins(0, 10, 0, 0)
        audit_note = QLabel(
            "All existing edits from earlier application versions remain here. This is the same immutable per-site audit data used by Change Audit and the sign-off PDF snapshot."
        )
        audit_note.setObjectName("Muted")
        audit_note.setWordWrap(True)
        audit_box.addWidget(audit_note)
        self.site_history_audit_table = QTableWidget(0, 9)
        self.site_history_audit_table.setHorizontalHeaderLabels(
            ["ID", "Module", "Record", "Field", "Original Value", "New Value", "Reason", "Modified By", "Modified At"]
        )
        _configure_table_base(self.site_history_audit_table)
        _set_fixed_column(self.site_history_audit_table, 0, 58)
        _set_fixed_column(self.site_history_audit_table, 1, 170)
        _set_fixed_column(self.site_history_audit_table, 2, 135)
        _set_interactive_column(self.site_history_audit_table, 3, 180)
        _set_interactive_column(self.site_history_audit_table, 4, 190)
        _set_interactive_column(self.site_history_audit_table, 5, 190)
        _set_stretch_column(self.site_history_audit_table, 6)
        _set_fixed_column(self.site_history_audit_table, 7, 120)
        _set_fixed_column(self.site_history_audit_table, 8, 170)
        audit_box.addWidget(self.site_history_audit_table)
        tabs.addTab(audit_tab, "Change Audit History")

        report_tab = QWidget()
        report_box = QVBoxLayout(report_tab)
        report_box.setContentsMargins(0, 10, 0, 0)
        report_actions = QHBoxLayout()
        self.attach_signed_btn = QPushButton("Attach Signed PDF")
        self.attach_signed_btn.clicked.connect(self.attach_signed_signoff_pdf)
        self.open_signoff_btn = QPushButton("Open Selected PDF")
        self.open_signoff_btn.clicked.connect(self.open_selected_signoff_pdf)
        report_actions.addWidget(self.attach_signed_btn)
        report_actions.addWidget(self.open_signoff_btn)
        report_actions.addStretch()
        report_box.addLayout(report_actions)
        self.site_reports_table = QTableWidget(0, 8)
        self.site_reports_table.setHorizontalHeaderLabels(
            ["ID", "Revision", "Status", "Generated PDF", "Generated By", "Generated At", "Signed PDF", "Signed At"]
        )
        _configure_table_base(self.site_reports_table)
        _set_fixed_column(self.site_reports_table, 0, 58)
        _set_fixed_column(self.site_reports_table, 1, 110)
        _set_fixed_column(self.site_reports_table, 2, 100)
        _set_stretch_column(self.site_reports_table, 3)
        _set_fixed_column(self.site_reports_table, 4, 120)
        _set_fixed_column(self.site_reports_table, 5, 170)
        _set_interactive_column(self.site_reports_table, 6, 260)
        _set_fixed_column(self.site_reports_table, 7, 170)
        report_box.addWidget(self.site_reports_table)
        tabs.addTab(report_tab, "PDF Sign-off History")

        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        return page

    # ------------------------- export -------------------------
    def _build_export_page(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader(
            "Migration Report Export",
            "Generate the formal Excel migration-review workbook and a printable station modification / issue-closure PDF for signature.",
        ))
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
        self.export_path_label = QLabel("Export location: choose a path when exporting")
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

        signoff_card = QFrame()
        signoff_card.setObjectName("Card")
        signoff_box = QVBoxLayout(signoff_card)
        signoff_box.setContentsMargins(24, 22, 24, 22)
        signoff_title = QLabel("Station modification & issue-closure sign-off PDF")
        signoff_title.setObjectName("SectionTitle")
        signoff_desc = QLabel(
            "Creates an A4 outstanding-action PDF for the selected site. It shows only open RMU Needs Action items, separates Analog / Telemetry and Status / Cmd signal Needs Action, and includes the reviewer-selected RMU Resolution / next action plus reviewer/time so the field team knows what to do next. Closed records, RMU manual verification, the separate Issue / Action Register and Change Audit are not rendered in the PDF; they remain preserved in Project Data. The PDF snapshot and SHA-256 hash are stored in Project Data."
        )
        signoff_desc.setObjectName("Muted")
        signoff_desc.setWordWrap(True)
        self.export_signoff_status_label = QLabel("Sign-off history: —")
        self.export_signoff_status_label.setObjectName("Muted")
        signoff_box.addWidget(signoff_title)
        signoff_box.addWidget(signoff_desc)
        signoff_box.addSpacing(10)
        signoff_box.addWidget(self.export_signoff_status_label)
        signoff_actions = QHBoxLayout()
        signoff_btn = QPushButton("Export Sign-off PDF")
        signoff_btn.setObjectName("Primary")
        signoff_btn.clicked.connect(self.export_signoff_pdf)
        history_btn = QPushButton("Open Site History")
        history_btn.clicked.connect(lambda: self.set_page(6))
        signoff_actions.addWidget(signoff_btn)
        signoff_actions.addWidget(history_btn)
        signoff_actions.addStretch()
        signoff_box.addLayout(signoff_actions)
        layout.addWidget(signoff_card)
        layout.addStretch()
        return page

    # ------------------------- settings -------------------------
    def _build_settings_page(self):
        page, layout = self._page_container()
        layout.addWidget(PageHeader("Settings", "Application identity, persistent Project Data, Site Repository, STANDARD management and deployment settings."))

        self.settings_setup_card = QFrame()
        self.settings_setup_card.setObjectName("SetupGuidance")
        self.settings_setup_card.setStyleSheet(
            "QFrame#SetupGuidance{background:#F8FAFC;border:1px solid #DCE3EA;border-radius:10px;}"
        )
        setup_box = QVBoxLayout(self.settings_setup_card)
        setup_box.setContentsMargins(18, 15, 18, 15); setup_box.setSpacing(7)
        setup_title = QLabel("Workspace & Project Data Setup")
        setup_title.setObjectName("SectionTitle")
        self.settings_setup_status = QLabel("")
        self.settings_setup_status.setWordWrap(True)
        self.settings_setup_status.setObjectName("Muted")
        setup_actions = QHBoxLayout()
        setup_wizard_btn = QPushButton("Open Setup Guide")
        setup_wizard_btn.setObjectName("Primary")
        setup_wizard_btn.clicked.connect(self.open_setup_dialog)
        setup_actions.addWidget(setup_wizard_btn); setup_actions.addStretch()
        setup_box.addWidget(setup_title); setup_box.addWidget(self.settings_setup_status); setup_box.addLayout(setup_actions)
        layout.addWidget(self.settings_setup_card)

        card = QFrame()
        card.setObjectName("Card")
        form = QFormLayout(card)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(14)
        app_label = QLabel(f"{APP_NAME} v{APP_VERSION}")
        self.settings_project_data_label = QLabel(str(project_data_root()))
        self.settings_project_data_label.setWordWrap(True)
        user_label = QLabel(self.user_name)
        self.settings_repo_label = QLabel(str(self.repository_root) if self.repository_root else "Not configured")
        self.settings_repo_label.setWordWrap(True)
        repo_widget = QWidget()
        repo_line = QHBoxLayout(repo_widget); repo_line.setContentsMargins(0, 0, 0, 0)
        repo_line.addWidget(self.settings_repo_label, 1)
        repo_btn = QPushButton("Change..."); repo_btn.clicked.connect(self.choose_repository_root); repo_line.addWidget(repo_btn)
        policy = QLabel("Source Workspace / Site Repository is read-only input. Project Data Storage is writable persistent application state stored separately from the release and source folders and survives upgrades. Each site keeps project.db, Review/Closed/Needs Action, Comments, Resolution, Change Audit, named revisions, issue/action records, generated sign-off PDFs, signed PDF copies, imported source copies and snapshots under Project Data. Future SQLite schema upgrades are forward-only and create a backup before changing project.db. Automatic validation and review behavior remain unchanged.")
        policy.setWordWrap(True)
        form.addRow("Application", app_label)
        form.addRow("Current user", user_label)
        language_widget = QWidget()
        language_line = QHBoxLayout(language_widget); language_line.setContentsMargins(0, 0, 0, 0)
        self.settings_language_combo = QComboBox()
        for language_key, language_label in SUPPORTED_LANGUAGES:
            self.settings_language_combo.addItem(language_label, language_key)
        language_index = self.settings_language_combo.findData(self.ui_language)
        if language_index >= 0:
            self.settings_language_combo.setCurrentIndex(language_index)
        self.settings_language_combo.currentIndexChanged.connect(self._change_ui_language)
        language_line.addWidget(self.settings_language_combo)
        language_note = QLabel(
            "Language changes are saved for future launches. Technical field names and source headers remain unchanged so mapping/audit data is language-neutral."
        )
        language_note.setObjectName("Muted")
        language_note.setWordWrap(True)
        language_line.addWidget(language_note, 1)
        form.addRow("Interface Language", language_widget)
        form.addRow("Site Repository", repo_widget)
        project_data_widget = QWidget()
        project_data_line = QHBoxLayout(project_data_widget); project_data_line.setContentsMargins(0, 0, 0, 0)
        project_data_line.addWidget(self.settings_project_data_label, 1)
        project_data_btn = QPushButton("Change...")
        project_data_btn.clicked.connect(self.choose_project_data_root)
        project_data_line.addWidget(project_data_btn)
        project_data_open_btn = QPushButton("Open Folder")
        project_data_open_btn.clicked.connect(lambda: self._open_path(project_data_root()))
        project_data_line.addWidget(project_data_open_btn)
        form.addRow("Project Data", project_data_widget)
        form.addRow("Data policy", policy)
        layout.addWidget(card)

        detection_card = QFrame()
        detection_card.setObjectName("Card")
        detection_box = QVBoxLayout(detection_card)
        detection_box.setContentsMargins(24, 22, 24, 22)
        detection_title = QLabel("Source Detection Rules")
        detection_title.setObjectName("SectionTitle")
        detection_box.addWidget(detection_title)
        detection_desc = QLabel(
            "These rules are optional recognition hints, not source requirements. Filenames may be arbitrary; manual file selection, Key/Index and field mapping are authoritative. "
            "Built-in categories help legacy AUTO discovery, and you may add any number of extra categories for your own site/file families."
        )
        detection_desc.setWordWrap(True)
        detection_desc.setObjectName("Muted")
        detection_box.addWidget(detection_desc)

        self.source_detection_table = QTableWidget(0, 3)
        self.source_detection_table.setHorizontalHeaderLabels(["Category / Source Hint", "Filename Keywords", "Type"])
        _configure_table_base(self.source_detection_table)
        self.source_detection_table.verticalHeader().setVisible(False)
        self.source_detection_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.source_detection_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.source_detection_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.source_detection_table.setColumnWidth(0, 220)
        self.source_detection_table.setColumnWidth(2, 120)
        self.source_detection_table.setMinimumHeight(220)
        categories = load_source_detection_categories()
        self.source_detection_table.setRowCount(len(categories))
        for row, category in enumerate(categories):
            label_item = QTableWidgetItem(clean(category.get("label")) or clean(category.get("key")))
            label_item.setData(Qt.ItemDataRole.UserRole, clean(category.get("key")))
            label_item.setData(Qt.ItemDataRole.UserRole + 1, bool(category.get("built_in")))
            keyword_item = QTableWidgetItem(", ".join(category.get("keywords") or []))
            kind_item = QTableWidgetItem("Built-in hint" if category.get("built_in") else "Custom hint")
            kind_item.setFlags(kind_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if category.get("built_in"):
                kind_item.setForeground(QColor(COLORS["muted"]))
            self.source_detection_table.setItem(row, 0, label_item)
            self.source_detection_table.setItem(row, 1, keyword_item)
            self.source_detection_table.setItem(row, 2, kind_item)
        detection_box.addWidget(self.source_detection_table)

        detection_actions = QHBoxLayout()
        add_detection_btn = QPushButton("Add Category")
        add_detection_btn.clicked.connect(self._add_source_detection_category)
        remove_detection_btn = QPushButton("Remove Category")
        remove_detection_btn.clicked.connect(self._remove_source_detection_category)
        save_detection_btn = QPushButton("Save Detection Rules")
        save_detection_btn.setObjectName("Primary")
        save_detection_btn.clicked.connect(self.save_detection_rules)
        detection_actions.addWidget(add_detection_btn)
        detection_actions.addWidget(remove_detection_btn)
        detection_actions.addStretch()
        detection_actions.addWidget(save_detection_btn)
        detection_box.addLayout(detection_actions)
        layout.addWidget(detection_card)

        standard_card = QFrame()
        standard_card.setObjectName("Card")
        standard_box = QVBoxLayout(standard_card)
        standard_box.setContentsMargins(24, 22, 24, 22)
        standard_title = QLabel("Signal Mapping STANDARD reference")
        standard_title.setObjectName("SectionTitle")
        standard_box.addWidget(standard_title)
        standard_desc = QLabel(
            "Signal Mapping Review and every formal export use the explicitly selected application-wide STANDARD workbook. "
            "You may keep multiple validated STANDARD versions in the library. Uploading never changes the active version automatically; "
            "choose the workbook below and click Use Selected. Site Repository files are never modified."
        )
        standard_desc.setObjectName("Muted")
        standard_desc.setWordWrap(True)
        standard_box.addWidget(standard_desc)
        self.settings_standard_label = QLabel("STANDARD: —")
        self.settings_standard_label.setWordWrap(True)
        self.settings_standard_label.setObjectName("Muted")
        standard_box.addWidget(self.settings_standard_label)

        standard_select_row = QHBoxLayout()
        standard_select_row.addWidget(QLabel("Available STANDARD workbooks:"))
        self.settings_standard_combo = QComboBox()
        self.settings_standard_combo.setMinimumWidth(420)
        self.settings_standard_combo.setToolTip(
            "The active STANDARD is chosen manually. The application never switches to a newer file automatically."
        )
        standard_select_row.addWidget(self.settings_standard_combo, 1)
        use_standard_btn = QPushButton("Use Selected")
        use_standard_btn.setObjectName("Primary")
        use_standard_btn.clicked.connect(self.activate_selected_standard_reference)
        standard_select_row.addWidget(use_standard_btn)
        standard_box.addLayout(standard_select_row)

        standard_buttons = QHBoxLayout()
        upload_btn = QPushButton("Upload STANDARD(s)...")
        upload_btn.setToolTip("Upload / Replace STANDARD... supports selecting multiple workbooks; same-name replacement requires confirmation.")
        upload_btn.clicked.connect(self.update_standard_reference)
        restore_btn = QPushButton("Use Built-in")
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

    def _add_source_detection_category(self):
        if not hasattr(self, "source_detection_table"):
            return
        name, ok = QInputDialog.getText(
            self, "Add Source Recognition Category",
            "Category name (for recognition/display only):"
        )
        name = clean(name)
        if not ok or not name:
            return
        row = self.source_detection_table.rowCount()
        self.source_detection_table.insertRow(row)
        label_item = QTableWidgetItem(name)
        label_item.setData(Qt.ItemDataRole.UserRole, "")
        label_item.setData(Qt.ItemDataRole.UserRole + 1, False)
        self.source_detection_table.setItem(row, 0, label_item)
        self.source_detection_table.setItem(row, 1, QTableWidgetItem(""))
        kind_item = QTableWidgetItem("Custom hint")
        kind_item.setFlags(kind_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.source_detection_table.setItem(row, 2, kind_item)
        self.source_detection_table.setCurrentCell(row, 1)
        self.source_detection_table.editItem(self.source_detection_table.item(row, 1))

    def _remove_source_detection_category(self):
        if not hasattr(self, "source_detection_table"):
            return
        row = self.source_detection_table.currentRow()
        if row < 0:
            return
        label_item = self.source_detection_table.item(row, 0)
        built_in = bool(label_item.data(Qt.ItemDataRole.UserRole + 1)) if label_item else False
        if built_in:
            QMessageBox.information(
                self, "Source Detection Rules",
                "Built-in recognition categories are kept for backward-compatible AUTO discovery. Clear their keywords to disable the filename hint; they are never mandatory."
            )
            return
        self.source_detection_table.removeRow(row)

    def save_detection_rules(self):
        if not hasattr(self, "source_detection_table"):
            return
        categories = []
        for row in range(self.source_detection_table.rowCount()):
            label_item = self.source_detection_table.item(row, 0)
            keyword_item = self.source_detection_table.item(row, 1)
            label = clean(label_item.text() if label_item else "")
            if not label:
                continue
            categories.append({
                "key": clean(label_item.data(Qt.ItemDataRole.UserRole) if label_item else ""),
                "label": label,
                "keywords": [part.strip() for part in clean(keyword_item.text() if keyword_item else "").split(",") if part.strip()],
                "built_in": bool(label_item.data(Qt.ItemDataRole.UserRole + 1)) if label_item else False,
            })
        save_source_detection_categories(categories)
        self._site_source_status_cache.clear()
        self._schema_validation_cache.clear()
        self.refresh_site_repository(force=True)
        self.statusBar().showMessage("Source recognition hints saved. Filenames remain unrestricted.", 5000)

    def _refresh_standard_reference_ui(self):
        if not hasattr(self, "settings_standard_label"):
            return
        try:
            info = current_standard_reference_info()
            if self.ui_language == LANG_ZH_CN:
                origin = ui_tr(info.origin, self.ui_language)
                self.settings_standard_label.setText(
                    f"当前：{origin} · {info.path.name}\n"
                    f"路径：{info.path}\n"
                    f"行数：{info.row_count} · 更新时间：{info.updated_at} · SHA256: {info.sha256[:16]}…"
                )
            else:
                self.settings_standard_label.setText(
                    f"Active: {info.origin} · {info.path.name}\n"
                    f"Path: {info.path}\n"
                    f"Rows: {info.row_count} · Updated: {info.updated_at} · SHA256: {info.sha256[:16]}…"
                )
            if hasattr(self, "settings_standard_combo"):
                previous_key = self.settings_standard_combo.currentData()
                self.settings_standard_combo.blockSignals(True)
                self.settings_standard_combo.clear()
                active_index = -1
                for ref in list_standard_references():
                    marker = "ACTIVE · " if ref.active else ""
                    label = f"{marker}{ref.origin} · {ref.path.name} · {ref.row_count} rows"
                    self.settings_standard_combo.addItem(label, ref.key)
                    idx = self.settings_standard_combo.count() - 1
                    self.settings_standard_combo.setItemData(
                        idx,
                        f"{ref.path}\nUpdated: {ref.updated_at}\nSHA256: {ref.sha256[:20]}…",
                        Qt.ToolTipRole,
                    )
                    if ref.active:
                        active_index = idx
                # Preserve a user's pending selection during an upload refresh;
                # otherwise show the current active reference.
                wanted = previous_key if previous_key else info.key
                wanted_index = self.settings_standard_combo.findData(wanted)
                if wanted_index >= 0:
                    self.settings_standard_combo.setCurrentIndex(wanted_index)
                elif active_index >= 0:
                    self.settings_standard_combo.setCurrentIndex(active_index)
                self.settings_standard_combo.blockSignals(False)
        except Exception as exc:
            self.settings_standard_label.setText(ui_tr(f"STANDARD unavailable: {type(exc).__name__}: {exc}", self.ui_language))

    def _audit_standard_change(self, previous, current, reason: str) -> None:
        if not self.store:
            return
        try:
            now = datetime.now().isoformat(timespec="seconds")
            self.store.db.execute(
                "INSERT INTO changes(rmu,field_name,old_value,new_value,reason,modified_by,modified_at) VALUES(?,?,?,?,?,?,?)",
                ("STANDARD", "standard_reference", f"{previous.origin}: {previous.path}", f"{current.origin}: {current.path}",
                 reason, self.user_name, now),
            )
            self.store.db.commit()
        except Exception:
            pass

    def update_standard_reference(self):
        initial = str(Path.home())
        try:
            current = standard_reference_path()
            if current.exists():
                initial = str(current.parent)
        except Exception:
            pass
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Upload STANDARD workbook(s)", initial, "Excel Workbook (*.xlsx *.xlsm)"
        )
        if not paths:
            return

        added = []
        skipped = []
        active_before_upload = standard_reference_path()
        active_content_replaced = False
        for raw in paths:
            source = Path(raw)
            overwrite = False
            while True:
                try:
                    info = add_standard_reference(source, self.user_name, overwrite=overwrite)
                    added.append(info)
                    try:
                        if overwrite and info.path.resolve() == active_before_upload.resolve():
                            active_content_replaced = True
                    except OSError:
                        pass
                    break
                except FileExistsError:
                    answer = QMessageBox.question(
                        self,
                        "STANDARD Already Exists",
                        f"A STANDARD workbook named '{source.name}' already exists in the library.\n\n"
                        "Replace that library file? The current file will be backed up first.\n"
                        "This does not change which STANDARD is active until you click Use Selected.",
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    )
                    if answer == QMessageBox.Cancel:
                        self._refresh_standard_reference_ui()
                        return
                    if answer == QMessageBox.No:
                        skipped.append(source.name)
                        break
                    overwrite = True
                except Exception as exc:
                    QMessageBox.critical(
                        self, "STANDARD Validation Failed",
                        f"{source.name} was not added.\n\n{type(exc).__name__}: {exc}",
                    )
                    skipped.append(source.name)
                    break

        self._refresh_standard_reference_ui()
        if active_content_replaced:
            self.db_smart_report = None
            self._db_smart_report_site = ""
            self._db_smart_ui_ready = False
            self._dirty_pages.add(3)
            if self.store:
                try:
                    self.store.config["validation_required_after_source_import"] = True
                    self.store.save_config()
                except Exception:
                    pass
        if added and hasattr(self, "settings_standard_combo"):
            # Highlight the last upload so the reviewer can explicitly activate it.
            idx = self.settings_standard_combo.findData(added[-1].key)
            if idx >= 0:
                self.settings_standard_combo.setCurrentIndex(idx)
        parts = []
        if added:
            parts.append("Uploaded: " + ", ".join(item.path.name for item in added))
        if skipped:
            parts.append("Skipped: " + ", ".join(skipped))
        parts.append("Active STANDARD was not changed. Choose a workbook and click Use Selected.")
        QMessageBox.information(self, "STANDARD Library", "\n\n".join(parts))

    def activate_selected_standard_reference(self):
        if not hasattr(self, "settings_standard_combo"):
            return
        key = self.settings_standard_combo.currentData()
        if not key:
            return
        try:
            previous = current_standard_reference_info()
            selected = next((ref for ref in list_standard_references() if ref.key == key), None)
            if selected is None:
                raise FileNotFoundError("The selected STANDARD workbook is no longer available.")
            if selected.active:
                self.statusBar().showMessage(ui_tr(f"STANDARD already active: {selected.path.name}", self.ui_language), 4000)
                return
            answer = QMessageBox.question(
                self,
                "Use Selected STANDARD",
                f"Use '{selected.path.name}' as the application-wide STANDARD?\n\n"
                "Signal Mapping Review and all subsequent Excel/PDF exports will use this workbook for every site.\n"
                "No site Review / Closed / Needs Action / Comments / Resolution data will be deleted.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            info = activate_standard_reference(str(key), self.user_name)
        except Exception as exc:
            QMessageBox.critical(self, "STANDARD Selection Failed", f"{type(exc).__name__}: {exc}")
            return
        self._audit_standard_change(previous, info, f"Application STANDARD selected manually: {info.path.name}")
        self._refresh_standard_reference_ui()
        if self.store:
            try:
                self.store.config["validation_required_after_source_import"] = True
                self.store.save_config()
            except Exception:
                pass
        self.db_smart_report = None
        self._db_smart_report_site = ""
        self._db_smart_ui_ready = False
        self._dirty_pages.add(3)
        self.statusBar().showMessage(ui_tr(f"Active STANDARD: {info.path.name}. Signal Mapping will recalculate from current selected sources.", self.ui_language), 6000)

    def restore_standard_reference(self):
        try:
            previous = current_standard_reference_info()
            if previous.origin == "Built-in":
                QMessageBox.information(self, "STANDARD Reference", "The bundled STANDARD table is already active.")
                return
            answer = QMessageBox.question(
                self, "Use Built-in STANDARD",
                "Select the bundled STANDARD reference? Uploaded STANDARD versions will remain in the library.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            info = restore_bundled_standard_reference()
        except Exception as exc:
            QMessageBox.critical(self, "STANDARD Reference", f"{type(exc).__name__}: {exc}")
            return
        self._audit_standard_change(previous, info, "Application STANDARD selected manually: built-in reference")
        self._refresh_standard_reference_ui()
        if self.store:
            try:
                self.store.config["validation_required_after_source_import"] = True
                self.store.save_config()
            except Exception:
                pass
        self.db_smart_report = None
        self._db_smart_report_site = ""
        self._db_smart_ui_ready = False
        self._dirty_pages.add(3)
        self.statusBar().showMessage(ui_tr(f"Built-in STANDARD selected: {info.path}", self.ui_language), 5000)

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

    def _position_busy_operation_popup(self) -> None:
        popup = getattr(self, "busy_operation_popup", None)
        stack = getattr(self, "stack", None)
        if popup is None or stack is None:
            return
        available = max(0, stack.width() - 32)
        popup.setFixedWidth(min(430, max(320, available)))
        popup.adjustSize()
        x = max(8, (stack.width() - popup.width()) // 2)
        y = max(18, (stack.height() - popup.height()) // 2)
        popup.move(x, y)
        popup.raise_()

    def _refresh_busy_operation_popup(self) -> None:
        popup = getattr(self, "busy_operation_popup", None)
        if popup is None:
            return
        operations = getattr(self, "_busy_popup_operations", {})
        if not operations:
            popup.hide()
            return
        _key, (title, detail, progress_value) = next(reversed(operations.items()))
        popup.set_message(title, detail, progress_value)
        self._position_busy_operation_popup()
        popup.show()
        popup.raise_()

    def _show_busy_operation(
        self, key: str, title: str, detail: str = "", progress_value: int | None = None
    ) -> None:
        key = clean(key) or "working"
        # Reinsert an existing key so the newest user action becomes the visible
        # message while older background tasks remain tracked underneath it.
        self._busy_popup_operations.pop(key, None)
        self._busy_popup_operations[key] = (clean(title) or "Loading...", clean(detail), progress_value)
        self._refresh_busy_operation_popup()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)

    def _update_busy_operation(
        self,
        key: str,
        *,
        title: str | None = None,
        detail: str | None = None,
        progress_value: int | None = None,
    ) -> None:
        if key not in self._busy_popup_operations:
            return
        old_title, old_detail, old_progress = self._busy_popup_operations[key]
        self._busy_popup_operations[key] = (
            clean(title) if title is not None else old_title,
            clean(detail) if detail is not None else old_detail,
            progress_value if progress_value is not None else old_progress,
        )
        self._refresh_busy_operation_popup()

    def _hide_busy_operation(self, key: str) -> None:
        self._busy_popup_operations.pop(clean(key), None)
        self._refresh_busy_operation_popup()

    def eventFilter(self, obj, event):
        """Coordinate spreadsheet selection and transient Signal Mapping highlights.

        Normal multi-cell review selections keep their existing persistent
        spreadsheet behaviour so toolbar actions can consume them.  The blue
        ADMS-implementation / Need-Action locator highlight is different: it is
        only a navigation aid.  The next ordinary mouse click clears that
        temporary blue row plus its navigation selection.  Set Status and Comment
        are exempt so they can still act on the row that was just located.
        """
        if obj is getattr(self, "stack", None) and event.type() in {QEvent.Type.Resize, QEvent.Type.Show}:
            QTimer.singleShot(0, self._position_busy_operation_popup)
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
            # Dialogs are created lazily throughout the application. Translate
            # each top-level window when it appears so Source Mapping, Resolution,
            # lifecycle and other operational dialogs follow the current setting.
            QTimer.singleShot(0, lambda w=obj: translate_widget_tree(w, self.ui_language))
        if event.type() == QEvent.Type.MouseButtonPress:
            if self._db_smart_navigation_highlight_active():
                keep_for_action = False
                if isinstance(obj, QWidget):
                    for action_widget in (
                        getattr(self, "db_smart_status_btn", None),
                        getattr(self, "db_smart_comment_btn", None),
                    ):
                        if action_widget is not None and self._widget_is_inside(obj, action_widget):
                            keep_for_action = True
                            break
                if not keep_for_action:
                    self._clear_db_smart_navigation_highlight(clear_selection=True)

            clicked_table = None
            if isinstance(obj, QWidget):
                for table in getattr(self, "_spreadsheet_tables", []):
                    if self._widget_is_inside(obj, table):
                        clicked_table = table
                        break
            if clicked_table is not None:
                self._clear_spreadsheet_selections(except_table=clicked_table)
        return super().eventFilter(obj, event)

    # ------------------------- background work -------------------------
    def _source_pipeline_busy(self) -> bool:
        return any(
            key in self._background_tasks
            for key in (
                "refresh-sources", "validation", "source-reload", "source-auto-refresh", "mapping-save",
                "module-signal-load", "module-rmu-load",
            )
        )

    def _set_work_progress(self, visible: bool, value: int = 0, text: str = "") -> None:
        """Legacy compatibility hook; operational progress is popup-only now."""
        return

    def _set_background_action_state(self) -> None:
        busy = bool(self._background_tasks)
        source_busy = self._source_pipeline_busy()
        if hasattr(self, "refresh_sources_btn"):
            self.refresh_sources_btn.setEnabled(not source_busy)
        if hasattr(self, "run_validation_btn"):
            self.run_validation_btn.setEnabled(not source_busy)
        if hasattr(self, "db_smart_refresh_btn"):
            self.db_smart_refresh_btn.setEnabled(not source_busy)
        if not busy and ui_tr(self.statusBar().currentMessage(), LANG_EN).startswith("Working ·"):
            self.statusBar().showMessage("Ready", 1500)

    def _start_background_task(
        self, key: str, label: str, fn, on_success, *, on_error=None, with_progress: bool = False
    ) -> bool:
        """Start a worker without ever blocking the GUI event loop."""
        if key in self._background_tasks:
            self.statusBar().showMessage(ui_tr(f"{label} is already running", self.ui_language), 2500)
            return False
        worker = BackgroundTask(fn, with_progress=with_progress)
        self._background_tasks[key] = worker
        self._set_background_action_state()
        self.statusBar().showMessage(ui_tr(f"Working · {label} …", self.ui_language))
        popup_key = f"task:{key}"
        show_popup = bool(with_progress and key != "source-auto-refresh")
        if show_popup:
            self._show_busy_operation(popup_key, label, "Preparing... Please wait.", progress_value=0)

        def progress_changed(value: int, stage: str):
            if key not in self._background_tasks:
                return
            stage_text = clean(stage) or label
            if show_popup:
                self._update_busy_operation(
                    popup_key,
                    title=label,
                    detail=f"{stage_text} · {int(value)}%",
                    progress_value=value,
                )
            self.statusBar().showMessage(ui_tr(f"Working · {stage_text} · {int(value)}%", self.ui_language))

        def finish(result):
            self._background_tasks.pop(key, None)
            self._set_background_action_state()
            if show_popup:
                self._hide_busy_operation(popup_key)
            try:
                on_success(result)
            except Exception:
                QMessageBox.critical(self, label, traceback.format_exc())

        def fail(details: str):
            self._background_tasks.pop(key, None)
            self._set_background_action_state()
            if show_popup:
                self._hide_busy_operation(popup_key)
            if on_error is not None:
                on_error(details)
                return
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.critical(self, label, last_line)

        if with_progress:
            worker.signals.progressed.connect(progress_changed)
        worker.signals.succeeded.connect(finish)
        worker.signals.failed.connect(fail)
        self.thread_pool.start(worker)
        return True

    def _start_process_background_task(
        self,
        key: str,
        label: str,
        job_name: str,
        args: tuple,
        on_success,
        *,
        on_error=None,
    ) -> bool:
        """Start a CPU-heavy review build without blocking the Qt event loop.

        There are two independent blocking risks on Windows: the calculation
        itself and ``multiprocessing.Process.start()`` while the spawned child is
        created.  v0.8.127 keeps *both* away from the GUI thread.  A small
        QThreadPool launcher performs process creation/startup; the child process
        then performs the expensive review calculation.  The GUI thread does
        nothing except animate the busy popup and poll a queue with non-blocking
        reads.
        """
        if key in self._background_tasks:
            self.statusBar().showMessage(ui_tr(f"{label} is already running", self.ui_language), 2500)
            return False

        poll_timer = QTimer(self)
        poll_timer.setInterval(40)
        popup_key = f"task:{key}"
        state = {
            "process": None,
            "queue": None,
            "timer": poll_timer,
            "launcher": None,
            "launched": False,
            "result_received": False,
            "finished": False,
            "exit_grace": 0,
        }
        self._background_tasks[key] = state
        self._set_background_action_state()
        self.statusBar().showMessage(ui_tr(f"Working · {label} …", self.ui_language))
        # The popup is shown before even spawning the process.  Its own timer is
        # now guaranteed to keep repainting while the launcher thread waits for
        # Windows/PyInstaller process startup.
        self._show_busy_operation(
            popup_key,
            label,
            "Starting background worker... Please wait.",
            progress_value=None,
        )

        def cleanup() -> None:
            if state.get("finished"):
                return
            state["finished"] = True
            poll_timer.stop()
            self._background_tasks.pop(key, None)
            self._set_background_action_state()
            self._hide_busy_operation(popup_key)
            process = state.get("process")
            message_queue = state.get("queue")
            if process is not None:
                try:
                    if process.is_alive():
                        process.join(timeout=0)
                    else:
                        process.join(timeout=0.05)
                except Exception:
                    pass
            if message_queue is not None:
                try:
                    message_queue.close()
                    message_queue.cancel_join_thread()
                except Exception:
                    pass

        def deliver_success(result) -> None:
            if state.get("finished"):
                return
            state["result_received"] = True
            cleanup()
            try:
                on_success(result)
            except Exception:
                QMessageBox.critical(self, label, traceback.format_exc())

        def deliver_error(details: str) -> None:
            if state.get("finished"):
                return
            cleanup()
            if on_error is not None:
                on_error(details)
                return
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.critical(self, label, last_line)

        def poll_messages_with_exit_guard() -> None:
            if state.get("finished") or not state.get("launched"):
                return
            process = state.get("process")
            message_queue = state.get("queue")
            if process is None or message_queue is None:
                return

            # Bound queue draining per tick.  An unbounded ``while get_nowait``
            # loop can itself starve repaint/timer events if a worker reports
            # progress rapidly.  Eight messages per 40 ms tick is ample while
            # preserving smooth GUI animation.
            got_terminal = False
            for _ in range(8):
                try:
                    message = message_queue.get_nowait()
                except queue.Empty:
                    break
                except Exception:
                    break
                if not message:
                    continue
                kind = message[0]
                if kind == "progress":
                    value = int(message[1])
                    stage = clean(message[2]) or label
                    self._update_busy_operation(
                        popup_key,
                        title=label,
                        detail=f"{stage} · {value}% · working in background",
                        progress_value=None,
                    )
                    self.statusBar().showMessage(ui_tr(f"Working · {stage} · {value}%", self.ui_language))
                elif kind == "success":
                    got_terminal = True
                    deliver_success(message[1])
                    return
                elif kind == "failed":
                    got_terminal = True
                    deliver_error(str(message[1]))
                    return
                elif kind == "done":
                    got_terminal = True

            if state.get("finished"):
                return
            try:
                alive = process.is_alive()
            except Exception:
                alive = False
            if alive:
                state["exit_grace"] = 0
                return
            state["exit_grace"] = int(state.get("exit_grace", 0)) + 1
            if int(state["exit_grace"]) >= 4:
                deliver_error(
                    f"{label} background process exited unexpectedly (code {process.exitcode})."
                )

        poll_timer.timeout.connect(poll_messages_with_exit_guard)

        # IMPORTANT: process.start() must not run here on the Qt GUI thread.
        # A QThreadPool launcher owns that potentially slow spawn step.
        launcher = BackgroundTask(lambda: _launch_review_process(job_name, tuple(args)))
        state["launcher"] = launcher

        def launched(payload) -> None:
            if state.get("finished"):
                # The view was cancelled while Windows was still spawning.
                try:
                    proc, mq = payload
                    if proc.is_alive():
                        proc.terminate()
                    mq.close()
                    mq.cancel_join_thread()
                except Exception:
                    pass
                return
            process, message_queue = payload
            state["process"] = process
            state["queue"] = message_queue
            state["launched"] = True
            state["launcher"] = None
            self._update_busy_operation(
                popup_key,
                title=label,
                detail="Background worker started · calculating...",
                progress_value=None,
            )
            poll_timer.start()

        def launch_failed(details: str) -> None:
            state["launcher"] = None
            deliver_error(details)

        launcher.signals.succeeded.connect(launched)
        launcher.signals.failed.connect(launch_failed)
        self.thread_pool.start(launcher)
        return True

    def _reopen_active_store_after_worker(self, site: SiteInfo) -> None:
        """Reload project.db/project.json after a worker committed changes."""
        if self.store:
            try:
                self.store.close()
            except Exception:
                pass
            self.store = None
        self.selected_site = site
        self._activate_site_workspace(site)

    # ------------------------- navigation -------------------------
    def set_page(self, index: int):
        """Switch modules; review pages show waiting feedback before any heavy preparation.

        Navigation must be cheap: QStackedWidget keeps every page alive.
        """
        if index != 2 and self._comparison_render_in_progress:
            self._cancel_comparison_render()
            self._dirty_pages.add(2)

        if self.stack.currentIndex() != index:
            self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

        if index in {2, 3}:
            title = "Loading RMU Data Review" if index == 2 else "Loading Signal Mapping Review"
            detail = "Preparing review data... Please wait."
            self._show_busy_operation("nav-review-load", title, detail)
            QTimer.singleShot(0, lambda idx=index: self._continue_review_navigation(idx))
            return
        self._refresh_page_if_dirty(index)

    def _continue_review_navigation(self, index: int) -> None:
        if self.stack.currentIndex() != index:
            self._hide_busy_operation("nav-review-load")
            return
        try:
            if index == 3 and self.db_smart_report is None:
                self._dirty_pages.add(3)
            if index == 2 and self.store and self.store.comparison_row_count() == 0:
                self._dirty_pages.add(2)
            if index == 2 and index in self._dirty_pages:
                self._set_comparison_loading(True)
            self._refresh_page_if_dirty(index)
        finally:
            self._hide_busy_operation("nav-review-load")

    def _mark_site_pages_dirty(self) -> None:
        # Site/source changes invalidate the in-memory Equipment Review session.
        # Ordinary reviewer edits use _dirty_pages.update(...) directly and keep
        # this session hot, so only true site/source invalidation clears it.
        self._comparison_dataset_ready = False
        self._comparison_row_cache.clear()
        self._comparison_entry_cache.clear()
        self._comparison_row_index_cache.clear()
        self._comparison_review_map_cache.clear()
        self._comparison_resolution_map_cache.clear()
        self._comparison_last_entries = []
        self._comparison_action_tracking_keys.clear()
        # Site Data Sources itself is refreshed immediately because the reviewer
        # is usually selecting a site from that page.  Everything else can wait
        # until its module is opened.
        self._dirty_pages.update({0, 2, 3, 4, 5, 6, 7})

    def _refresh_page_if_dirty(self, index: int) -> None:
        if index == 1:
            if hasattr(self, "site_list"):
                self._refresh_site_source_table()
            self._dirty_pages.discard(1)
            return
        if index not in self._dirty_pages:
            if index == 2:
                # Signal Mapping may have appended lifecycle events while RMU
                # Data Review itself remained clean. Refresh the lightweight
                # selected-RMU timeline every time this page is revisited.
                QTimer.singleShot(0, self.refresh_selected_rmu_lifecycle)
            if index == 3 and self.db_smart_report is not None:
                QTimer.singleShot(0, self._restore_db_smart_header)
            return
        try:
            if index == 0:
                self.refresh_dashboard()
            elif index == 2:
                if hasattr(self, "comparison_table"):
                    self._configure_comparison_headers()
                    self._populate_comparison_search_fields()
                # Cached project.db rows render immediately. A brand-new site or
                # fresh installation auto-builds the RMU review on first open.
                if self.store and self.store.comparison_row_count() == 0:
                    self._start_rmu_review_module_load()
                else:
                    self.refresh_comparison()
            elif index == 3:
                if hasattr(self, "db_smart_table"):
                    site_name = self.selected_site.name if self.selected_site else ""
                    if (
                        self.db_smart_report is None
                        or self._db_smart_report_site.casefold() != site_name.casefold()
                    ):
                        self._start_signal_mapping_module_load()
                    else:
                        # Preserve the established synchronous fast path when an
                        # in-memory report already exists but only the UI needs
                        # to be repainted.
                        self.refresh_db_smart_report(force=False, rescan=False)
                    if self.db_smart_report is not None:
                        self._show_db_smart_rmu_overview()
                    QTimer.singleShot(0, self._restore_db_smart_header)
            elif index == 4:
                self.refresh_changes()
            elif index == 5:
                self.refresh_versions()
            elif index == 6:
                self.refresh_site_history()
            elif index == 7:
                self.refresh_export_page()
        finally:
            self._dirty_pages.discard(index)

    def _start_signal_mapping_module_load(self) -> bool:
        """Auto-load Signal Mapping on first navigation with visible progress."""
        if "module-signal-load" in self._background_tasks:
            return True
        if not self.selected_site or not self.repository_root:
            self.db_smart_summary.setText("Select a site and configure its source Workspace first")
            return False
        # Site selection already activates the persistent workspace. Avoid a
        # redundant save/open on module navigation because SQLite busy waits
        # would run on the GUI thread and could freeze the just-shown animation.
        expected_folder = workspace_root() / re.sub(r"[^A-Za-z0-9._-]+", "_", self.selected_site.name)
        if not self.store or self.store.folder.resolve() != expected_folder.resolve():
            self._activate_site_workspace(self.selected_site)
        if not self.store:
            return False

        site_name = self.selected_site.name
        project_folder = str(self.store.folder)
        repository_root = str(self.repository_root)
        # Enter a neutral loading state.  The unavailable/failure EmptyState is
        # shown only after the worker confirms missing inputs or reports an
        # error; showing it while a healthy load is still running is misleading.
        self.db_smart_stack.setCurrentWidget(self.db_smart_loading)
        self.db_smart_source_label.setText("Auto-loading active Signal Mapping sources…")
        self.db_smart_sheet_label.setText("Mode: calculated")
        self.db_smart_meta_label.setText("Rows: loading…")
        self.db_smart_summary.setText("Loading Signal Mapping Review automatically…")

        def success(result: dict):
            result_site = result.get("site")
            if result_site is None or not self.selected_site or self.selected_site.name != site_name:
                return
            self._reopen_active_store_after_worker(result_site)
            report = result.get("report")
            if report is None:
                missing = list(result.get("missing") or [])
                missing_text = ", ".join(missing) if missing else "required Signal Mapping sources"
                self.db_smart_report = None
                self._db_smart_report_site = site_name
                self._db_smart_ui_ready = False
                self.db_smart_stack.setCurrentWidget(self.db_smart_empty)
                self.db_smart_source_label.setText(f"Missing: {missing_text}")
                self.db_smart_meta_label.setText("Rows: 0")
                self.db_smart_summary.setText(
                    f"Signal Mapping Review cannot load yet · missing {missing_text}. Configure it in Site Data Sources."
                )
                self._dirty_pages.add(3)
                return
            self.db_smart_report = report
            self._db_smart_report_site = site_name
            self._db_smart_ui_ready = False
            self._present_db_smart_report(report, 0)
            self._dirty_pages.discard(3)
            self.refresh_dashboard()
            self.statusBar().showMessage(
                f"Signal Mapping Review ready · {len(report.rows)} row(s)", 4000
            )

        def failed(details: str):
            self._dirty_pages.add(3)
            self.db_smart_report = None
            self._db_smart_ui_ready = False
            self.db_smart_stack.setCurrentWidget(self.db_smart_empty)
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            self.db_smart_source_label.setText("Signal Mapping auto-load failed")
            self.db_smart_meta_label.setText("Rows: 0")
            self.db_smart_summary.setText(ui_tr(f"Auto-load failed · {last_line}", self.ui_language))
            self.statusBar().showMessage(ui_tr(f"Signal Mapping auto-load failed · {last_line}", self.ui_language), 8000)

        return self._start_process_background_task(
            "module-signal-load",
            f"Loading {site_name} Signal Mapping Review",
            "module-signal-load",
            (project_folder, repository_root, site_name),
            success,
            on_error=failed,
        )

    def _start_rmu_review_module_load(self) -> bool:
        """Auto-build RMU review on first navigation when no cached rows exist."""
        if "module-rmu-load" in self._background_tasks:
            return True
        if not self.selected_site or not self.repository_root:
            self._set_comparison_loading(False)
            return False
        # Do not reopen/resave the same project.db on the GUI thread here.
        # The site-selection path already owns workspace activation.
        expected_folder = workspace_root() / re.sub(r"[^A-Za-z0-9._-]+", "_", self.selected_site.name)
        if not self.store or self.store.folder.resolve() != expected_folder.resolve():
            self._activate_site_workspace(self.selected_site)
        if not self.store:
            self._set_comparison_loading(False)
            return False
        site_name = self.selected_site.name
        project_folder = str(self.store.folder)
        repository_root = str(self.repository_root)
        self._set_comparison_loading(True, "Loading RMU Data Review automatically…")

        def success(result: dict):
            result_site = result.get("site")
            if result_site is None or not self.selected_site or self.selected_site.name != site_name:
                return
            self._reopen_active_store_after_worker(result_site)
            self._dirty_pages.discard(2)
            if int(result.get("row_count") or 0) <= 0:
                self._set_comparison_loading(False)
                self.comparison_summary.setText(
                    "No RMU Data Review rows could be built. Check Site Data Sources, then reopen this module."
                )
                self._dirty_pages.add(2)
                return
            if self.stack.currentIndex() == 2:
                self.refresh_comparison()
            else:
                self._dirty_pages.add(2)
            self.refresh_dashboard()

        def failed(details: str):
            self._set_comparison_loading(False)
            self._dirty_pages.add(2)
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            self.comparison_summary.setText(ui_tr(f"RMU Data Review auto-load failed · {last_line}", self.ui_language))
            self.statusBar().showMessage(ui_tr(f"RMU Data Review auto-load failed · {last_line}", self.ui_language), 8000)

        return self._start_process_background_task(
            "module-rmu-load",
            f"Loading {site_name} RMU Data Review",
            "module-rmu-load",
            (project_folder, repository_root, site_name),
            success,
            on_error=failed,
        )

    def _setup_state(self) -> dict:
        """Return lightweight startup configuration state without opening source files."""
        repository = self.repository_root
        source_ok = bool(repository and Path(repository).exists() and Path(repository).is_dir())
        project = project_data_root()
        project_ok = bool(project.exists() and project.is_dir())
        project_confirmed = bool(project_data_root_is_configured())
        missing = []
        if not source_ok:
            missing.append("Source Workspace")
        if not project_ok or not project_confirmed:
            missing.append("Project Data Storage")
        return {
            "source_ok": source_ok,
            "project_ok": project_ok,
            "project_confirmed": project_confirmed,
            "missing": missing,
        }

    def _refresh_setup_guidance(self) -> None:
        state = self._setup_state()
        missing = state["missing"]
        if not missing:
            message = "Setup complete. Source Workspace and Project Data Storage are configured and will be reused automatically on future launches."
        elif "Source Workspace" in missing and "Project Data Storage" in missing:
            message = "Choose the read-only Source Workspace and confirm the writable Project Data Storage location before starting site validation."
        elif "Source Workspace" in missing:
            message = "Source Workspace is not configured or is unavailable. Choose the folder that contains the site source files."
        else:
            message = f"Project Data Storage has not been confirmed. The app is currently using the safe default location: {project_data_root()}"
        display_message = ui_tr(message, self.ui_language)
        if hasattr(self, "setup_guidance_card"):
            self.setup_guidance_label.setText(display_message)
            self.setup_guidance_card.setVisible(bool(missing))
        if hasattr(self, "settings_setup_status"):
            self.settings_setup_status.setText(display_message)
        if hasattr(self, "settings_repo_label"):
            repo_text = str(self.repository_root) if self.repository_root else ui_tr("Not configured", self.ui_language)
            self.settings_repo_label.setText(repo_text)
        if hasattr(self, "settings_project_data_label"):
            suffix = "" if state["project_confirmed"] else (
                "  ·  使用默认位置（未确认）" if self.ui_language == LANG_ZH_CN else "  ·  using default (not confirmed)"
            )
            self.settings_project_data_label.setText(f"{project_data_root()}{suffix}")

    def open_setup_dialog(self) -> bool:
        """Open the two-path setup guide and persist both locations when accepted."""
        dialog = InitialSetupDialog(self.repository_root, project_data_root(), self)
        if dialog.exec() != QDialog.Accepted:
            self.settings.setValue("onboarding/initial_setup_seen_v1", True)
            self._refresh_setup_guidance()
            return False
        repository_root, project_root = dialog.selected_paths()
        if repository_root is None:
            return False

        old_repository = self.repository_root.resolve() if self.repository_root else None
        old_project = project_data_root().resolve()
        new_repository = Path(repository_root).resolve()
        new_project = Path(project_root).resolve()
        repository_changed = old_repository != new_repository
        project_changed = old_project != new_project

        # Close the active site store only when its persistent Project Data root
        # actually changes. Re-opening the guide and saving the same values must
        # not disturb the current review session.
        if project_changed and self.store:
            try:
                self.store.close()
            except Exception:
                pass
            self.store = None
        set_project_data_root(new_project)
        self.repository_root = new_repository
        save_repository_root(self.repository_root)
        self.settings.setValue("onboarding/initial_setup_seen_v1", True)

        if hasattr(self, "sidebar_workspace"):
            self.sidebar_workspace.setText(str(project_data_root()))
        if hasattr(self, "dash_project_path"):
            self.dash_project_path.setText(str(project_data_root()))
        self._refresh_setup_guidance()

        if repository_changed or project_changed:
            self.selected_site = None
            self.statusBar().showMessage(ui_tr("Setup saved · loading Source Workspace...", self.ui_language), 5000)
            self.refresh_site_repository(force=False, deep=False)
            self._mark_site_pages_dirty()
            self.refresh_dashboard()
        else:
            self.statusBar().showMessage(ui_tr("Setup confirmed", self.ui_language), 3500)
        return True

    def _maybe_show_initial_setup(self) -> None:
        if self._startup_setup_checked:
            return
        self._startup_setup_checked = True
        state = self._setup_state()
        self._refresh_setup_guidance()
        if not state["missing"]:
            return
        already_seen = self.settings.value("onboarding/initial_setup_seen_v1", False, type=bool)
        if not already_seen:
            self.open_setup_dialog()

    def _load_initial_workspace(self) -> None:
        """Fast post-show startup load.

        Only filenames/version families are inspected.  This is enough to show
        the site list and bind the last site without opening workbook contents.
        """
        if self._startup_repository_loaded:
            return
        self._startup_repository_loaded = True
        self._maybe_show_initial_setup()
        self._refresh_setup_guidance()
        if not self.repository_root:
            self.refresh_dashboard()
            self._dirty_pages.discard(0)
            return
        try:
            self.statusBar().showMessage(ui_tr("Loading workspace index...", self.ui_language))
            self.refresh_site_repository(force=False, deep=False)
        except Exception as exc:
            self.statusBar().showMessage(ui_tr(f"Workspace index warning: {type(exc).__name__}: {exc}", self.ui_language), 8000)
        finally:
            if self.selected_site:
                self.statusBar().showMessage(ui_tr(f"Ready · {self.selected_site.name}", self.ui_language), 3000)
                # Keep the last Workspace/Site/source selections for instant
                # startup, then verify the live files asynchronously. Only files
                # whose cheap metadata changed are re-read.
                QTimer.singleShot(250, self._check_live_source_changes)
            else:
                self.statusBar().showMessage("Ready", 3000)
            if not self._source_watch_timer.isActive():
                self._source_watch_timer.start()

    def _wire_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self.run_comparison)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.export_excel)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.set_page(2), self.search_edit.setFocus()))

    # ------------------------- site repository actions -------------------------
    @staticmethod
    def _site_metadata_signature(site: SiteInfo | None) -> tuple:
        """Cheap source signature used for UI cache invalidation.

        Deliberately uses path/size/mtime only. Full SHA256 work remains part of
        explicit source refresh/validation, not ordinary module navigation.
        """
        if site is None:
            return ()
        parts = []
        for key, path in sorted(site.sources.items()):
            try:
                p = Path(path)
                stat = p.stat()
                parts.append((key, str(p.resolve()), int(stat.st_size), int(stat.st_mtime_ns)))
            except OSError:
                parts.append((key, str(path), -1, -1))
        return tuple(parts)

    def _site_status_cache_key(self, site: SiteInfo, active_store: ProjectStore | None) -> tuple:
        stored = (active_store.config.get("repository_fingerprints", {}) if active_store else {}) or {}
        stored_sig = tuple(
            sorted(
                (key, clean(value.get("sha256")), str(value.get("size", "")), str(value.get("mtime_ns", "")))
                for key, value in stored.items() if isinstance(value, dict)
            )
        )
        manual_sig = ()
        selected_sig = ()
        if active_store:
            manual_sig = tuple(
                sorted(
                    (key, self._file_metadata_signature(active_store.source_path(key)))
                    for key in active_store.manual_source_overrides()
                    if active_store.source_path(key) is not None
                )
            )
            selected_sig = tuple(
                sorted(
                    (key, clean(record.get("file_name")), clean(record.get("selected_at")))
                    for key, record in active_store.source_file_selections().items()
                )
            )
        return self._site_metadata_signature(site) + (
            ("__stored__", stored_sig), ("__manual__", manual_sig), ("__selected_versions__", selected_sig)
        )

    @staticmethod
    def _file_metadata_signature(path: Path | None) -> tuple:
        if not path:
            return ()
        try:
            p = Path(path)
            stat = p.stat()
            return (str(p.resolve()), int(stat.st_size), int(stat.st_mtime_ns))
        except OSError:
            return (str(path), -1, -1)

    def choose_project_data_root(self):
        """Choose the persistent Project Data root used across application upgrades."""
        selected = QFileDialog.getExistingDirectory(
            self, "Select Project Data Folder", str(project_data_root())
        )
        if not selected:
            return
        target = Path(selected).resolve()
        current = project_data_root().resolve()
        if target == current:
            if not project_data_root_is_configured():
                confirm_project_data_root(current)
                self._refresh_setup_guidance()
                self.statusBar().showMessage(ui_tr(f"Project Data confirmed: {project_data_root()}", self.ui_language), 5000)
            return
        answer = QMessageBox.question(
            self, "Change Project Data",
            "Project Data contains the persistent records for every site, including Review, Closed, "
            "Needs Action, Comments, Resolution and Audit history.\n\n"
            f"Current: {current}\nNew: {target}\n\n"
            "The application will use the new folder from now on. Existing data is not deleted. Continue?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        if self.store:
            try:
                self.store.close()
            except Exception:
                pass
            self.store = None
        set_project_data_root(target)
        if hasattr(self, "settings_project_data_label"):
            self.settings_project_data_label.setText(str(project_data_root()))
        if hasattr(self, "sidebar_workspace"):
            self.sidebar_workspace.setText(str(project_data_root()))
        if hasattr(self, "dash_project_path"):
            self.dash_project_path.setText(str(project_data_root()))
        if self.selected_site:
            self._activate_site_workspace(self.selected_site)
        self.refresh_all(refresh_sources=False)
        self._refresh_setup_guidance()
        self.statusBar().showMessage(ui_tr(f"Project Data: {project_data_root()}", self.ui_language), 6000)

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
        self.refresh_site_repository(force=False, deep=False)
        self._refresh_setup_guidance()
        self.statusBar().showMessage(ui_tr(f"Source Workspace: {self.repository_root}", self.ui_language), 5000)

    def open_repository_root(self):
        if not self.repository_root or not self.repository_root.exists():
            QMessageBox.information(self, "Site Repository", "Choose a valid Workspace first.")
            return
        self._open_path(self.repository_root)

    def refresh_sources_and_reload(self):
        """Re-scan/re-read sources on the shared worker pool.

        Disk I/O, deep schema detection, snapshot copying and RMU calculation
        no longer run on the Qt GUI thread.  The page remains scrollable and the
        reviewer can continue reading while Refresh Sources is running.
        """
        if not self.repository_root:
            QMessageBox.information(self, "Refresh Sources", "Select a Workspace first.")
            return
        if not self.selected_site:
            QMessageBox.information(self, "Refresh Sources", "Select a site first.")
            return
        self._activate_site_workspace(self.selected_site)
        if not self.store:
            return
        site_name = self.selected_site.name
        project_folder = str(self.store.folder)
        repository_root = str(self.repository_root)

        def success(result: dict):
            result_site = result.get("site")
            if result_site is None:
                return
            if self.selected_site and self.selected_site.name == site_name:
                self._reopen_active_store_after_worker(result_site)
                self._site_source_status_cache.clear()
                self._schema_validation_cache.clear()
                self.db_smart_report = None
                self._db_smart_report_site = ""
                self._db_smart_ui_ready = False
                self._mark_site_pages_dirty()
                # Keep this lightweight: exact schema validation already ran in
                # the worker's deep scan and will be rendered when needed.
                self._refresh_site_source_table(validate_schema=False)
                if hasattr(self, "equipment_profile_combo"):
                    self._equipment_profile_source_sig = None
                    self._refresh_equipment_profile_options(force=True)
                self.refresh_dashboard()
                self._dirty_pages.discard(0)
                current_index = self.stack.currentIndex() if hasattr(self, "stack") else 1
                if current_index not in {0, 1}:
                    self._refresh_page_if_dirty(current_index)
            changed_keys = list(result.get("changed_keys") or [])
            changed_text = ", ".join(changed_keys) if changed_keys else "no content changes"
            self.statusBar().showMessage(ui_tr(f"Sources refreshed · {changed_text}", self.ui_language), 6000)

        def failed(details: str):
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.warning(self, "Refresh Sources", f"Source refresh failed:\n{last_line}")

        self._start_background_task(
            "refresh-sources", f"Refreshing {site_name} sources",
            lambda progress: _background_refresh_sources_job(
                project_folder, repository_root, site_name, progress
            ),
            success, on_error=failed, with_progress=True,
        )

    def refresh_site_repository(self, force: bool = True, *, deep: bool | None = None):
        if not hasattr(self, "site_list"):
            return
        if deep is None:
            deep = bool(force)
        if force:
            # Explicit Refresh Sources is the cache boundary. Ordinary module
            # navigation never performs file hashing or schema re-validation.
            self._site_source_status_cache.clear()
            self._schema_validation_cache.clear()
        selected_name = self.selected_site.name if self.selected_site else None
        if not selected_name and self.store:
            selected_name = self.store.config.get("repository_site")
        if not selected_name:
            selected_name = load_last_site() or None
        self.repository_sites = scan_repository(self.repository_root, deep=bool(deep)) if self.repository_root else []
        if hasattr(self, "repository_root_edit"):
            self.repository_root_edit.setText(str(self.repository_root) if self.repository_root else "")
        if hasattr(self, "repository_summary"):
            self.repository_summary.setText(
                f"{len(self.repository_sites)} 个站点 · 数据源数量按站点自由配置"
                if self.ui_language == LANG_ZH_CN else
                f"{len(self.repository_sites)} sites · source count is configurable per site"
            )
        if hasattr(self, "repository_last_scan"):
            self.repository_last_scan.setText(ui_tr("Last scan: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.ui_language))
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
            # Equipment Data Review uses a configurable source count.
            # The station list reports only whether tabular files are available
            # or a configurable review is already defined; no fixed-role count
            # or legacy missing-role list is rendered.
            # A site may organize inputs under arbitrary nested folders.
            # Never derive this status from the legacy root-only source-role
            # resolver; recursively inspect the actual site tree instead.
            has_tabular_files = site_has_tabular_files(site.path)
            current_site_configured = False
            if (
                self.store
                and self.store.config.get("repository_site", "").casefold() == site.name.casefold()
            ):
                current_config = get_equipment_comparison_config(self.store, bootstrap=False)
                current_site_configured = bool(current_config.get("sources"))
            status = "CONFIGURED" if current_site_configured else ("CONFIGURABLE" if has_tabular_files else "NO TABULAR FILES")
            display_status = ui_tr(status, self.ui_language)
            item = QListWidgetItem(f"{site.name}\n{display_status}")
            item.setData(Qt.ItemDataRole.UserRole, site.name)
            item.setForeground(QColor(COLORS["success"] if (current_site_configured or has_tabular_files) else COLORS["warning"]))
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
            self._active_site_signature = ()
            self._refresh_site_source_table()
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        site = next((x for x in self.repository_sites if x.name == name), None)
        if not site:
            return

        new_signature = self._site_metadata_signature(site)
        same_site = bool(
            self.selected_site
            and self.selected_site.name.casefold() == site.name.casefold()
            and self.store
            and self.store.config.get("repository_site", "").casefold() == site.name.casefold()
        )
        same_snapshot = same_site and self._active_site_signature == new_signature
        self.selected_site = site
        save_last_site(site.name)

        # Re-rendering the site list (for example after typing in the site search
        # box or merely opening Site Data Sources) used to reactivate the same
        # workspace and rebuild every review page. If neither site identity nor
        # cheap source metadata changed, keep the already loaded in-memory pages.
        if same_snapshot:
            self._refresh_site_source_table()
            return

        self._active_site_signature = new_signature
        # Bind the persistent site store immediately, but do not rebuild every
        # module's tables.  Repainting thousands of cells was the main reason
        # site switching felt frozen.  Pages are marked dirty and refreshed only
        # when the reviewer actually opens them.
        self._activate_site_workspace(site)
        self.db_smart_report = None
        self._db_smart_report_site = site.name
        self._db_smart_ui_ready = False
        self._mark_site_pages_dirty()
        self._refresh_site_source_table()
        current_index = self.stack.currentIndex() if hasattr(self, "stack") else 1
        if current_index != 1:
            self._refresh_page_if_dirty(current_index)

    def _refresh_site_source_table(self, *, validate_schema: bool = False):
        if not hasattr(self, "module_source_tables"):
            return
        for table in self.module_source_tables.values():
            table.setRowCount(0)

        site = self.selected_site
        if not site:
            self.site_detail_title.setText("Select a site")
            self.site_detail_path.setText("Choose a repository root, then select a detected site.")
            self.site_status_label.setText("—")
            if hasattr(self, "stack") and self.stack.count() > 1:
                translate_widget_tree(self.stack.widget(1), self.ui_language)
            return

        self.site_detail_title.setText(site.name)
        self.site_detail_path.setText(
            f"{site.path}\n{ui_tr('Site scope: ', self.ui_language)}{site.name}"
        )

        active_store = self.store if self.store and self.store.config.get("repository_site", "").casefold() == site.name.casefold() else None
        status_cache_key = self._site_status_cache_key(site, active_store)
        cached_status = self._site_source_status_cache.get(site.name.casefold())
        if cached_status and cached_status[0] == status_cache_key:
            statuses = cached_status[1]
        else:
            statuses = source_status(site, active_store, hash_contents=False)
            self._site_source_status_cache[site.name.casefold()] = (status_cache_key, statuses)

        effective_present = {key for key, info in statuses.items() if info.get("path")}
        if active_store:
            for signal_role in ("ioa", "adms_sld"):
                assigned = resolve_configurable_signal_assignment(active_store, signal_role)
                if assigned is not None and Path(assigned).exists():
                    effective_present.add(signal_role)
        required_keys = {definition.key for definition in SOURCE_DEFINITIONS if definition.required}
        pending_source_mappings = dict((active_store.config.get("pending_source_mappings", {}) or {}) if active_store else {})

        # v0.8.178: once this site has an explicit configurable Equipment Data
        # Review definition, the old SE/ZENON/ADMS equipment-role filenames are
        # no longer prerequisites for site readiness.  Signal Mapping remains
        # untouched and therefore continues to require only its own historical
        # site sources (for example IOA + ADMS SLD).
        comparison_config = get_equipment_comparison_config(active_store, bootstrap=False) if active_store else {"sources": []}
        configured_equipment_ready = True
        if comparison_config.get("sources"):
            signal_module = next((item for item in MODULE_SOURCE_GROUPS if item.key == "signal_mapping"), None)
            signal_required = {
                ref.source_type for ref in (signal_module.tables if signal_module else ())
                if ref.source_type != "standard_reference"
            }
            required_keys = required_keys & signal_required
            configured_status = configurable_comparison_status(active_store, comparison_config)
            enabled_configured_status = [
                item for item in configured_status
                if bool((item.get("source") or {}).get("enabled", True))
            ]
            configured_equipment_ready = (
                bool(enabled_configured_status)
                and bool(comparison_config.get("comparisons"))
                and all(clean(item.get("status")).upper() == "READY" for item in enabled_configured_status)
            )

        pending_required = required_keys & set(pending_source_mappings)
        effective_ready = required_keys.issubset(effective_present) and not pending_required and configured_equipment_ready
        self.site_status_label.setText(ui_tr("READY" if effective_ready else "PARTIAL", self.ui_language))
        self.site_status_label.setStyleSheet(
            f"font-weight:700;color:{COLORS['success'] if effective_ready else COLORS['warning']};"
        )

        status_color = {
            "CURRENT": COLORS["success"],
            "NEW": COLORS["info"],
            "UPDATED": COLORS["warning"],
            "MISSING": COLORS["danger"],
            "OPTIONAL": COLORS["muted"],
            "BUILT-IN": COLORS["info"],
            "USER OVERRIDE": COLORS["warning"],
            "MANUAL": COLORS["info"],
            "SELECTED": COLORS["info"],
        }

        for module in MODULE_SOURCE_GROUPS:
            table = self.module_source_tables[module.key]

            # v0.8.178: Equipment Data Review no longer exposes five fixed App
            # source roles. The table is generated from this site's own arbitrary
            # CSV/XLSX source configuration. Signal Mapping keeps its historical
            # source contract unchanged.
            if module.key == "rmu_review":
                config = get_equipment_comparison_config(active_store, bootstrap=False) if active_store else {"sources": [], "comparisons": []}
                configured_rows = configurable_comparison_status(active_store, config) if active_store and config.get("sources") else []
                if not configured_rows:
                    table.setRowCount(1)
                    name_item = QTableWidgetItem(ui_tr("Configurable Equipment Comparison", self.ui_language))
                    name_item.setData(Qt.ItemDataRole.UserRole, "equipment_configurable")
                    table.setItem(0, 0, name_item)
                    configure_btn = QPushButton(ui_tr("Configure Sources...", self.ui_language))
                    configure_btn.setObjectName("InlineSourceFile")
                    configure_btn.clicked.connect(self.open_equipment_comparison_config)
                    table.setCellWidget(0, 1, configure_btn)
                    table.setItem(0, 2, QTableWidgetItem(ui_tr("Any CSV / Excel", self.ui_language)))
                    table.setItem(0, 3, QTableWidgetItem(ui_tr("Add any number of files; each site has its own configuration", self.ui_language)))
                    table.setItem(0, 4, QTableWidgetItem(ui_tr("Choose each table's Key / Index and define any comparison fields. All source fields show by default.", self.ui_language)))
                    status_item = QTableWidgetItem(ui_tr("NOT CONFIGURED", self.ui_language))
                    status_item.setForeground(QColor(COLORS["warning"]))
                    table.setItem(0, 5, status_item)
                else:
                    table.setRowCount(len(configured_rows))
                    for row, info in enumerate(configured_rows):
                        source = info.get("source") or {}
                        path = info.get("path")
                        title = clean(source.get("title")) or (Path(path).stem if path else "Source")
                        columns = tuple(info.get("columns") or ())
                        key_id = clean(source.get("key_column"))
                        key_label = next((column.label for column in columns if column.id == key_id), ui_tr("Key not set", self.ui_language))
                        hidden = set(source.get("hidden_columns") or [])
                        shown_count = sum(column.id not in hidden for column in columns)
                        source_item = QTableWidgetItem(title)
                        source_item.setData(Qt.ItemDataRole.UserRole, source.get("id"))
                        table.setItem(row, 0, source_item)
                        configure_btn = QPushButton(Path(path).name if path else ui_tr("Configure Sources...", self.ui_language))
                        configure_btn.setObjectName("InlineSourceFile")
                        configure_btn.setToolTip(ui_tr("Open the site-local configurable comparison editor", self.ui_language))
                        configure_btn.clicked.connect(self.open_equipment_comparison_config)
                        table.setCellWidget(row, 1, configure_btn)
                        sheet_text = clean(source.get("sheet_name")) or ("CSV" if path and Path(path).suffix.lower() == ".csv" else "AUTO")
                        table.setItem(row, 2, QTableWidgetItem(sheet_text))
                        table.setItem(row, 3, QTableWidgetItem(str(path or "—")))
                        compare_count = int(info.get("compare_count") or 0)
                        detail = (
                            f"主键：{key_label} · 比较规则：{compare_count} · 显示字段：{shown_count}/{len(columns)}"
                            if self.ui_language == LANG_ZH_CN else
                            f"Key: {key_label} · Compare rules: {compare_count} · Shown: {shown_count}/{len(columns)} fields"
                        )
                        table.setItem(row, 4, QTableWidgetItem(detail))
                        status_text = clean(info.get("status")) or "READY"
                        status_item = QTableWidgetItem(ui_tr(status_text, self.ui_language))
                        status_item.setForeground(QColor(COLORS["success"] if status_text == "READY" else COLORS["warning"] if status_text != "MISSING" else COLORS["danger"]))
                        status_item.setToolTip(clean(info.get("error")))
                        table.setItem(row, 5, status_item)
                if table.rowCount() and table.currentRow() < 0:
                    table.setCurrentCell(0, 0)
                continue

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
                schema_tip = f"{ref.label} is non-tabular and has no field mapping."
                field_mapping = "—"
                schema = schema_for(source_type)
                if path and schema is not None:
                    try:
                        overrides = get_source_overrides(active_store, source_type)
                        preferred_sheet_key = active_store.source_sheet_name(source_type) if active_store and hasattr(active_store, "source_sheet_name") else ""
                        validation_key = (
                            source_type, self._file_metadata_signature(Path(path)),
                            preferred_sheet_key,
                            json.dumps(overrides or {}, ensure_ascii=False, sort_keys=True),
                        )
                        if validation_key in self._schema_validation_cache:
                            validation = self._schema_validation_cache[validation_key]
                        elif validate_schema:
                            sheet_name = ""
                            if Path(path).suffix.lower() in {".xlsx", ".xlsm"} and active_store and hasattr(active_store, "source_sheet_name"):
                                sheet_name = active_store.source_sheet_name(source_type)
                            validation = validate_source_file(source_type, path, overrides, sheet_name=sheet_name or None)
                            self._schema_validation_cache[validation_key] = validation
                        else:
                            validation = None

                        if validation is not None:
                            # Persist the real AUTO resolutions discovered from
                            # this physical header. Fast site switching can then
                            # show useful mappings without reopening the file.
                            set_resolved_source_mappings(
                                active_store, source_type,
                                {m.canonical_key: m.actual_column for m in validation.mappings if m.actual_column},
                            )

                        mapping_parts = module_field_mapping_lines(
                            module.key, source_type, active_store, validation
                        )
                        # Table/list content is intentionally language-neutral.
                        # Keep both the App-side display name and the physical
                        # source header exactly as configured so reviewers see
                        # the same field contract in English and Chinese UI.
                        display_mapping_parts = [str(mapping_part) for mapping_part in mapping_parts]
                        field_mapping = "  ·  ".join(display_mapping_parts) if display_mapping_parts else "—"

                        if validation is not None:
                            used_keys = set(ref.field_keys)
                            hidden_fields = get_hidden_source_fields(active_store, source_type) if active_store else set()
                            effective_errors = [e for e in validation.errors if e.canonical_key in used_keys]
                            effective_warnings = [
                                w for w in validation.warnings
                                if w.canonical_key in used_keys and w.canonical_key not in hidden_fields
                            ]
                            schema_text = (
                                f"ERROR ({len(effective_errors)})" if effective_errors else
                                f"WARNING ({len(effective_warnings)})" if effective_warnings else
                                "READY"
                            )
                            schema_tip = f"Fields used by {module.label}:\n" + ("\n".join(display_mapping_parts) if display_mapping_parts else ui_tr("None", self.ui_language))
                            available_unmapped = [clean(value) for value in validation.ignored_columns if clean(value)]
                            if available_unmapped:
                                schema_tip += "\n\nOther source fields available for mapping:\n" + "\n".join(available_unmapped)
                        else:
                            schema_text = "READY"
                            schema_tip = (
                                f"Fields used by {module.label}:\n" + ("\n".join(display_mapping_parts) if display_mapping_parts else ui_tr("None", self.ui_language)) +
                                "\n\nRefresh Sources or Map Fields to re-read the live file header."
                            )
                    except Exception as exc:
                        schema_text = "ERROR"
                        field_mapping = "Read error"
                        schema_tip = f"{type(exc).__name__}: {exc}"

                pending_mapping = dict(pending_source_mappings.get(source_type, {}) or {})
                if path and schema is not None and pending_mapping:
                    schema_text = "MAPPING REQUIRED"
                    headers = [clean(value) for value in (pending_mapping.get("headers") or []) if clean(value)]
                    header_preview = ", ".join(headers[:20])
                    if len(headers) > 20:
                        header_preview += ", ..."
                    schema_tip = (
                        "The replacement source is loaded, but required App Columns are not yet mapped to its physical fields. "
                        "Click Map Fields, unlock SYSTEM mappings when needed, map the new Source Fields, and Save before Validation."
                        + (f"\n\nDetected source fields:\n{header_preview}" if header_preview else "")
                    )
                if path and source_type != "standard_reference":
                    version_text = source_file_version_label(path)
                    if file_status == "SELECTED":
                        version_text += " · pinned"
                    elif file_status == "MANUAL":
                        version_text += " · manual"
                    else:
                        version_text += " · auto"
                elif source_type == "standard_reference" and path:
                    version_text = standard_reference_origin()
                else:
                    version_text = "—"

                if not path:
                    simple_status = "MISSING"
                elif schema_text == "MAPPING REQUIRED":
                    simple_status = "MAPPING REQUIRED"
                elif schema_text.startswith("ERROR"):
                    simple_status = "ERROR"
                elif schema_text.startswith("WARNING"):
                    simple_status = "WARNING"
                else:
                    simple_status = "READY"

                # Source File shows only the filename supplied/selected by the
                # reviewer. File Path separately shows that file's reviewer-
                # facing full location. Internal timestamped processing snapshots
                # are never presented as if they were input files.
                source_display = detected
                source_path_display = ""
                if path and source_type != "standard_reference":
                    source_display = source_user_visible_name(site, active_store, source_type, Path(path))
                    source_path_display = source_user_visible_path(site, active_store, source_type, Path(path))
                elif source_type == "standard_reference" and path:
                    source_display = Path(path).name
                    source_path_display = str(Path(path).resolve())
                sheet_display = "—"
                resolved_sheet = ""
                if path and source_type == "standard_reference":
                    sheet_display = "STANDARD"
                elif path and Path(path).suffix.lower() in {".xlsx", ".xlsm"}:
                    preferred_sheet = active_store.source_sheet_name(source_type) if active_store and hasattr(active_store, "source_sheet_name") else ""
                    try:
                        resolved_sheet = resolve_source_excel_sheet_name(source_type, Path(path), preferred_sheet or None)
                        sheet_display = (f"MANUAL → {resolved_sheet}" if preferred_sheet and resolved_sheet.casefold() == preferred_sheet.casefold() else f"AUTO → {resolved_sheet}")
                    except Exception:
                        sheet_display = "SHEET ERROR"

                display_sheet = sheet_display
                display_status = simple_status
                display_ref_label = ref.label
                values = [display_ref_label, source_display, display_sheet, source_path_display or "—", field_mapping, display_status]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if col == 0:
                        item.setData(Qt.ItemDataRole.UserRole, source_type)
                        font = item.font(); font.setBold(True); item.setFont(font)
                        fields_text = ", ".join(ref.field_keys) if ref.field_keys else "No direct table fields"
                        item.setToolTip(f"{ref.role}\nFields used by {module.label}: {fields_text}")
                    elif col == 1:
                        source_mode = (
                            "PINNED" if file_status == "SELECTED" else
                            "MANUAL" if file_status == "MANUAL" else
                            ("AUTO · LATEST VERSION" if path and has_explicit_source_version(Path(path)) else "AUTO · DETECTION RULE")
                        )
                        item.setToolTip(
                            (f"Source file: {source_display}\nMode: {source_mode}" if path
                             else f"No active file mapped for {ref.label}.") +
                            "\nClick this Source File cell to use AUTO, pin a specific V version, or browse another file. "
                            "AUTO prefers the highest parsable V version; if none exists it falls back to Source Detection Rules. "
                            "An explicit user choice always has priority."
                        )
                    elif col == 2:
                        if resolved_sheet:
                            item.setToolTip(
                                f"Excel sheet: {resolved_sheet}\n"
                                + ("Manual site-level sheet selection." if sheet_display.startswith("MANUAL") else "AUTO selected the first usable sheet in workbook order.")
                                + "\nClick the Sheet cell/button to change this site's sheet without changing global field mapping."
                            )
                        else:
                            item.setToolTip("CSV sources do not use worksheets." if path else "No active source")
                    elif col == 3:
                        item.setToolTip(source_path_display or "No active source path")
                    elif col == 4:
                        item.setToolTip(schema_tip + "\n\nDouble-click this row or click Map Fields to change mapping.")
                    elif col == 5:
                        color = (
                            COLORS["danger"] if simple_status in {"ERROR", "MISSING"} else
                            COLORS["warning"] if simple_status in {"WARNING", "MAPPING REQUIRED"} else COLORS["success"]
                        )
                        item.setForeground(QColor(color))
                        font = item.font(); font.setBold(True); item.setFont(font)
                    table.setItem(row, col, item)

                # File selection belongs to the App Table row itself. This replaces
                # the ambiguous footer Choose Active File / Import Source File
                # actions with one direct control that cannot target the wrong table.
                source_button = QPushButton(f"{source_display}  ▾")
                source_button.setObjectName("InlineSourceFile")
                source_button.setCursor(Qt.PointingHandCursor)
                source_button.setToolTip(
                    (f"Active source: {source_display}\n{source_path_display}" if path else f"No active source for {ref.label}")
                    + "\n\nClick to choose an existing version or browse another file for this App Table."
                )
                source_button.clicked.connect(
                    lambda _checked=False, st=source_type, label=ref.label: self.choose_source_file_for_table(st, label)
                )
                if source_type == "standard_reference":
                    source_button.setToolTip(
                        f"Application STANDARD: {source_display}\n{source_path_display}\n\nUse Update STANDARD on Signal Mapping Review to replace it."
                    )
                table.setCellWidget(row, 1, source_button)

                if path and source_type != "standard_reference" and Path(path).suffix.lower() in {".xlsx", ".xlsm"}:
                    sheet_button = QPushButton(f"{sheet_display}  ▾")
                    sheet_button.setObjectName("InlineSourceFile")
                    sheet_button.setCursor(Qt.PointingHandCursor)
                    sheet_button.setToolTip(
                        "Choose AUTO or one worksheet for this site's Excel source. "
                        "Sheet selection is site/file-level; App field mapping remains global by source type."
                    )
                    sheet_button.clicked.connect(
                        lambda _checked=False, st=source_type, label=ref.label: self.choose_source_sheet_for_table(st, label)
                    )
                    table.setCellWidget(row, 2, sheet_button)
            if table.rowCount() and table.currentRow() < 0:
                table.setCurrentCell(0, 0)

        if hasattr(self, "unmapped_file_combo"):
            self.unmapped_file_combo.clear()
            for unmapped in getattr(site, "unmapped_files", ()):
                self.unmapped_file_combo.addItem(unmapped.name, str(unmapped))
            count = self.unmapped_file_combo.count()
            self.unmapped_files_label.setText(ui_tr(f"Unmapped Files ({count})", self.ui_language))
            self.assign_unmapped_btn.setEnabled(count > 0)
            self.unmapped_file_combo.setEnabled(count > 0)
            if hasattr(self, "unmapped_card"):
                self.unmapped_card.setVisible(count > 0)
            if count == 0:
                self.unmapped_file_combo.addItem(ui_tr("No unmapped supported files", self.ui_language))

        if hasattr(self, "stack") and self.stack.count() > 1:
            translate_widget_tree(self.stack.widget(1), self.ui_language)

    def _live_source_origin_path(self, site: SiteInfo, source_type: str) -> Path | None:
        """Return the reviewer-facing live file, never the internal project copy."""
        if not self.store:
            return None
        selected = selected_repository_source_path(site, self.store, source_type)
        if selected is not None and selected.exists():
            return selected
        manual = (self.store.manual_source_overrides().get(source_type) or {})
        original_text = str(manual.get("original_path") or "").strip()
        if original_text:
            original = Path(original_text)
            if original.exists() and original.is_file():
                return original
        discovered = site.sources.get(source_type)
        if discovered and Path(discovered).exists():
            return Path(discovered)
        return None

    def _detect_live_source_changes(self) -> tuple[SiteInfo | None, list[str], tuple]:
        """Cheap change detection for the active site's live inputs.

        Configurable sources are direct file links. Their watcher compares the
        real file path/size/mtime (including AUTO-family path switches) and never
        compares or refreshes a workspace copy. Legacy projects retain the old
        snapshot-compatible watcher until they save a configurable source set.
        """
        if not self.repository_root or not self.selected_site or not self.store:
            return None, [], ()
        try:
            site = _load_repository_site(self.repository_root, self.selected_site.name, deep=False)
        except Exception:
            return None, [], ()

        configurable = get_equipment_comparison_config(self.store, bootstrap=False)
        if configurable.get("sources"):
            changed, direct_signature = configured_live_source_changes(self.store)
            signature = (site.name, "DIRECT", direct_signature, tuple(changed))
            return site, list(changed), signature

        baseline = dict(self.store.config.get("live_source_metadata", {}) or {})
        changed: list[str] = []
        signature_parts = []
        for definition in SOURCE_DEFINITIONS:
            key = definition.key
            live = self._live_source_origin_path(site, key)
            stored = self.store.source_path(key)
            if live is None:
                if stored is not None and not self.store.is_manual_source_override(key):
                    changed.append(key)
                    signature_parts.append((key, "MISSING", -1, -1))
                continue
            try:
                stat = live.stat()
                live_path = str(live.resolve())
                size = int(stat.st_size)
                mtime_ns = int(stat.st_mtime_ns)
            except OSError:
                continue
            signature_parts.append((key, live_path, size, mtime_ns))
            meta = baseline.get(key) if isinstance(baseline.get(key), dict) else None
            if meta:
                if (
                    str(meta.get("path") or "") != live_path
                    or int(meta.get("size") or -1) != size
                    or int(meta.get("mtime_ns") or -1) != mtime_ns
                ):
                    changed.append(key)
                continue
            if stored is None:
                changed.append(key)
                continue
            try:
                stored_stat = stored.stat()
                if int(stored_stat.st_size) != size or int(stored_stat.st_mtime_ns) != mtime_ns:
                    changed.append(key)
            except OSError:
                changed.append(key)
        signature = (site.name, tuple(signature_parts), tuple(sorted(changed)))
        return site, sorted(set(changed)), signature

    def _check_live_source_changes(self) -> None:
        """Auto-refresh live files that changed while the application is open."""
        if not self._startup_repository_loaded or self._source_pipeline_busy():
            return
        if QApplication.activeModalWidget() is not None or self._comparison_render_in_progress:
            return
        try:
            site, changed, signature = self._detect_live_source_changes()
        except Exception:
            return
        if site is None or not changed:
            return
        if signature == self._source_watch_last_trigger:
            return
        self._source_watch_last_trigger = signature
        self.statusBar().showMessage(
            "Source change detected · " + ", ".join(changed) + " · refreshing in background", 5000
        )
        configurable = get_equipment_comparison_config(self.store, bootstrap=False) if self.store else {}
        if configurable.get("sources"):
            self._reload_configurable_live_sources(
                changed, task_key="source-auto-refresh", quiet=True,
                label=f"Refreshing changed {site.name} live sources",
            )
        else:
            self._reload_live_sources(
                changed, task_key="source-auto-refresh", quiet=True,
                label=f"Refreshing changed {site.name} sources",
            )

    def _reload_configurable_live_sources(
        self, changed_keys, *, task_key: str = "source-auto-refresh", quiet: bool = False, label: str = ""
    ) -> bool:
        """Re-read configured files in place; never import/copy a source file."""
        keys = [clean(key) for key in changed_keys if clean(key)]
        if not keys or not self.selected_site or not self.repository_root:
            return False
        if self._source_pipeline_busy():
            if not quiet:
                self.statusBar().showMessage(
                    ui_tr("Source processing is already running. Please wait for it to finish.", self.ui_language), 4000
                )
            return False
        self._activate_site_workspace(self.selected_site)
        if not self.store:
            return False
        site_name = self.selected_site.name
        project_folder = str(self.store.folder)
        repository_root = str(self.repository_root)
        task_label = label or f"Refreshing {len(keys)} live source(s)"

        def success(result: dict):
            result_site = result.get("site")
            if result_site is None:
                return
            report = result.get("signal_report")
            if self.selected_site and self.selected_site.name == site_name:
                self._reopen_active_store_after_worker(result_site)
                self._active_site_signature = self._site_metadata_signature(result_site)
                self._site_source_status_cache.clear()
                self._schema_validation_cache.clear()
                if report is not None:
                    self.db_smart_report = report
                    self._db_smart_report_site = site_name
                    self._db_smart_ui_ready = False
                self._mark_site_pages_dirty()
                self._refresh_site_source_table(validate_schema=False)
                self.refresh_dashboard()
                self._dirty_pages.discard(0)
                current_index = self.stack.currentIndex() if hasattr(self, "stack") else 1
                if current_index in {2, 3}:
                    self._refresh_page_if_dirty(current_index)
                if current_index == 4:
                    self.refresh_changes()
            self._source_watch_last_trigger = ()
            changed_text = ", ".join(result.get("changed_keys") or keys)
            self.statusBar().showMessage(
                ui_tr(f"Live source refreshed · {changed_text} · Validation required", self.ui_language),
                7000,
            )

        def failed(details: str):
            self._source_watch_last_trigger = ()
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            if quiet:
                self.statusBar().showMessage(
                    ui_tr(f"Automatic live-source refresh failed · {last_line}", self.ui_language), 9000
                )
            else:
                QMessageBox.warning(self, "Live Source", f"Direct source reload failed:\n{last_line}")

        return self._start_background_task(
            task_key, task_label,
            lambda progress: _background_reload_configurable_live_sources_job(
                project_folder, repository_root, site_name, keys, progress
            ),
            success, on_error=failed, with_progress=True,
        )

    def _reload_live_sources(
        self, source_types, *, task_key: str = "source-reload", quiet: bool = False, label: str = "",
        open_mapping_on_required: bool = False,
    ) -> bool:
        """Re-read only requested sources and repaint only affected modules."""
        keys = [clean(key) for key in source_types if clean(key)]
        if not keys or not self.selected_site or not self.repository_root:
            return False
        if self._source_pipeline_busy():
            if not quiet:
                self.statusBar().showMessage(ui_tr("Source processing is already running. Please wait for it to finish.", self.ui_language), 4000)
            return False
        self._activate_site_workspace(self.selected_site)
        if not self.store:
            return False
        site_name = self.selected_site.name
        project_folder = str(self.store.folder)
        repository_root = str(self.repository_root)
        task_label = label or (f"Loading {keys[0]} source" if len(keys) == 1 else f"Loading {len(keys)} changed sources")

        def success(result: dict):
            result_site = result.get("site")
            if result_site is None:
                return
            report = result.get("signal_report")
            pending = dict(result.get("mapping_required") or {})
            if self.selected_site and self.selected_site.name == site_name:
                self._reopen_active_store_after_worker(result_site)
                self._active_site_signature = self._site_metadata_signature(result_site)
                self._site_source_status_cache.clear()
                self._schema_validation_cache.clear()
                if report is not None:
                    self.db_smart_report = report
                    self._db_smart_report_site = site_name
                    self._db_smart_ui_ready = False
                elif set(keys) & {"ioa", "adms_sld"} and not (set(pending) & {"ioa", "adms_sld"}):
                    self.db_smart_report = None
                    self._db_smart_report_site = ""
                    self._db_smart_ui_ready = False
                self._mark_site_pages_dirty()
                self._refresh_site_source_table(validate_schema=False)
                self.refresh_dashboard()
                self._dirty_pages.discard(0)
                current_index = self.stack.currentIndex() if hasattr(self, "stack") else 1
                if current_index in {2, 3}:
                    self._refresh_page_if_dirty(current_index)
                if current_index == 4:
                    self.refresh_changes()
            self._source_watch_last_trigger = ()
            changed_text = ", ".join(result.get("changed_keys") or keys)
            if pending:
                pending_text = ", ".join(pending)
                self.statusBar().showMessage(
                    f"Source loaded · {pending_text} · Map Fields required before Validation", 9000
                )
                if not quiet:
                    details = []
                    for source_key, info in pending.items():
                        headers = [clean(x) for x in (info.get("headers") or []) if clean(x)]
                        preview = ", ".join(headers[:12])
                        if len(headers) > 12:
                            preview += ", ..."
                        source_name = clean(info.get("source_name")) or source_key
                        details.append(f"{source_key}: {source_name}" + (f"\nDetected fields: {preview}" if preview else ""))
                    QMessageBox.information(
                        self, "Source Loaded · Mapping Required",
                        "The selected source file was loaded successfully, but its physical column names no longer satisfy the current App mapping.\n\n"
                        "This is not a source-file error. Remap the required App Columns to the new Source Fields, then Save and run Validation.\n\n"
                        + "\n\n".join(details)
                    )
                if open_mapping_on_required:
                    first_pending = next((key for key in keys if key in pending), next(iter(pending), ""))
                    if first_pending:
                        QTimer.singleShot(0, lambda st=first_pending: self._open_source_mapping_for_type(st))
            else:
                self.statusBar().showMessage(ui_tr(f"Source loaded · {changed_text} · Validation required", self.ui_language), 6000)

        def failed(details: str):
            self._source_watch_last_trigger = ()
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            if quiet:
                self.statusBar().showMessage(ui_tr(f"Automatic source refresh failed · {last_line}", self.ui_language), 8000)
            else:
                QMessageBox.warning(self, "Source File", f"Source reload failed:\n{last_line}")

        return self._start_background_task(
            task_key, task_label,
            lambda progress: _background_reload_live_sources_job(
                project_folder, repository_root, site_name, keys, progress
            ),
            success, on_error=failed, with_progress=True,
        )

    def choose_source_file_for_table(self, source_type: str, label: str = ""):
        """Choose AUTO latest published V version, pin one V version, or browse manually.

        Priority is explicit and stable: external/manual file > pinned repository
        version > AUTO latest published V version.  AUTO only considers physical
        filenames with a parsable V suffix (V1, V2, V2.1.0, ...).
        """
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Source File", "Select a site first.")
            return
        if self._source_pipeline_busy():
            self.statusBar().showMessage(ui_tr("Source processing is already running. Please wait for it to finish.", self.ui_language), 4000)
            return
        source_type = clean(source_type)
        label = clean(label) or source_type
        if source_type == "standard_reference":
            QMessageBox.information(
                self, "IOA STANDARD",
                "The application STANDARD reference is managed by Update STANDARD on Signal Mapping Review."
            )
            return

        candidates = list(source_version_candidates(self.selected_site.path, source_type) or [])
        auto_path = candidates[0] if candidates else self.selected_site.sources.get(source_type)
        auto_detection = self.selected_site.detections.get(source_type) if self.selected_site else None
        if auto_detection is not None and str(getattr(auto_detection, "method", "")).casefold() == "manual":
            auto_path = None
        labels: list[str] = []
        values: list[Path | str] = []

        if auto_path is not None and has_explicit_source_version(auto_path):
            labels.append(
                f"AUTO · Latest published version → {auto_path.name} · "
                f"{source_file_version_label(auto_path)}"
            )
        elif auto_path is not None:
            labels.append(f"AUTO · Detection rule fallback → {auto_path.name} · Unversioned")
        else:
            labels.append("AUTO · No source detected")
        values.append("__AUTO__")

        for candidate in candidates:
            try:
                modified = datetime.fromtimestamp(candidate.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                modified = "—"
            labels.append(
                f"PIN · {candidate.name} · {source_file_version_label(candidate)} · {modified}"
            )
            values.append(candidate)

        labels.append("Browse another file... · MANUAL highest priority")
        values.append("__BROWSE__")

        current_selection = self.store.source_file_selection(source_type)
        current_name = clean((current_selection or {}).get("file_name"))
        start_index = 0
        if current_name:
            for i, candidate in enumerate(values):
                if isinstance(candidate, Path) and candidate.name.casefold() == current_name.casefold():
                    start_index = i
                    break
        elif self.store.is_manual_source_override(source_type):
            # The exact external manual file is shown in the App Table row. The
            # picker intentionally starts on Browse because MANUAL is already
            # the active highest-priority mode.
            start_index = len(values) - 1

        selected_label, ok = QInputDialog.getItem(
            self, f"Source File · {label}",
            "Choose how this App Table resolves its physical source file.\n\n"
            "AUTO: use the highest semantic V version; if no published V exists, use the configured Source Detection Rules/base filename.\n"
            "PIN: use the exact V version you select, even when a newer version exists.\n"
            "MANUAL: browse any CSV/XLSX/XLSM filename; field mapping, not filename, defines the source role.",
            labels, start_index, False,
        )
        if not ok:
            return
        choice = values[labels.index(selected_label)]

        if choice == "__AUTO__":
            self.store.clear_manual_source_override(source_type)
            self.store.clear_source_file_selection(source_type, self.user_name)
            if auto_path is not None and has_explicit_source_version(auto_path):
                message = f"{label}: AUTO latest version → {auto_path.name}"
            elif auto_path is not None:
                message = f"{label}: AUTO detection-rule fallback → {auto_path.name}"
            else:
                message = f"{label}: AUTO enabled · no source currently detected"
        elif choice == "__BROWSE__":
            ext = "Supported tables (*.csv *.xlsx *.xlsm)"
            selected, _ = QFileDialog.getOpenFileName(
                self, f"Choose {label} Source File", str(self.selected_site.path), f"{ext};;CSV (*.csv);;Excel (*.xlsx *.xlsm);;All files (*.*)"
            )
            if not selected:
                return
            selected_path = Path(selected)
            # Explicit MANUAL selection is highest priority and may intentionally
            # use an unversioned/non-family physical file.
            self.store.clear_source_file_selection(source_type, self.user_name)
            self.store.mark_manual_source_override(source_type, selected_path)
            message = f"{label}: MANUAL file → {selected_path.name}"
        else:
            chosen = Path(choice)
            self.store.clear_manual_source_override(source_type)
            self.store.set_source_file_selection(source_type, chosen.name, self.user_name)
            message = f"{label}: PINNED version → {chosen.name}"

        self.store.config["validation_required_after_source_import"] = True
        self.store.save_config()
        self._site_source_status_cache.clear()
        self._schema_validation_cache.clear()
        self.statusBar().showMessage(message + " · reading selected source...", 4000)
        self._reload_live_sources(
            [source_type], task_key="source-reload", quiet=False,
            label=f"Loading {label} · {Path(self._live_source_origin_path(self.selected_site, source_type) or '').name or 'source'}",
            open_mapping_on_required=True,
        )

    def choose_source_sheet_for_table(self, source_type: str, label: str):
        """Choose a site-level Excel worksheet without changing global field mapping."""
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Source Sheet", "Select a site first.")
            return
        if self._source_pipeline_busy():
            self.statusBar().showMessage(ui_tr("Source processing is already running. Please wait for it to finish.", self.ui_language), 4000)
            return
        path = self._effective_site_source_path(source_type)
        if not path or Path(path).suffix.lower() not in {".xlsx", ".xlsm"}:
            QMessageBox.information(self, "Source Sheet", "The active source is not an Excel workbook.")
            return
        try:
            sheets = list(list_excel_sheets(Path(path)))
        except Exception as exc:
            QMessageBox.warning(self, "Source Sheet", f"Unable to read workbook sheets:\n{type(exc).__name__}: {exc}")
            return
        if not sheets:
            QMessageBox.warning(self, "Source Sheet", "The workbook contains no worksheets.")
            return
        preferred = self.store.source_sheet_name(source_type) if hasattr(self.store, "source_sheet_name") else ""
        auto_name = resolve_source_excel_sheet_name(source_type, Path(path), None)
        labels = [f"AUTO → {auto_name}"]
        values = [None]
        for info in sheets:
            marker = "usable" if info.usable else "review"
            labels.append(f"{info.name} · {info.rows} rows × {info.columns} cols · {marker}")
            values.append(info.name)
        start_index = 0
        if preferred:
            for idx, value in enumerate(values):
                if value and value.casefold() == preferred.casefold():
                    start_index = idx
                    break
        selected_label, ok = QInputDialog.getItem(
            self, "Source Sheet",
            f"{label}\n\nAUTO uses the source-preferred business sheet when available; otherwise it uses the first usable sheet in workbook order. "
            "A manual sheet selection applies only to this site/source file; global App-field mappings are unchanged.",
            labels, start_index, False,
        )
        if not ok:
            return
        chosen = values[labels.index(selected_label)]
        if chosen is None:
            self.store.clear_source_sheet_selection(source_type, self.user_name)
            message = f"{label}: Sheet AUTO → {auto_name}"
        else:
            self.store.set_source_sheet_selection(source_type, chosen, self.user_name)
            message = f"{label}: Sheet MANUAL → {chosen}"
        self.store.config["validation_required_after_source_import"] = True
        self.store.save_config()
        self._site_source_status_cache.clear()
        self._schema_validation_cache.clear()
        self.statusBar().showMessage(message + " · reading selected sheet...", 4000)
        self._reload_live_sources(
            [source_type], task_key="source-reload", quiet=False,
            label=f"Loading {label} · {Path(path).name}",
            open_mapping_on_required=True,
        )

    def select_active_source_file(self):
        """Choose AUTO latest or pin one exact published V version."""
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Choose Active File", "Select a site first.")
            return
        if self._source_pipeline_busy():
            self.statusBar().showMessage(ui_tr("Source processing is already running. Please wait for it to finish.", self.ui_language), 4000)
            return
        module, ref, _table = self._current_module_source_selection()
        if ref is None:
            QMessageBox.information(self, "Choose Active File", "Select an App Table first.")
            return
        source_type = ref.source_type
        if source_type == "standard_reference":
            QMessageBox.information(
                self, "Choose Active File",
                "The application STANDARD reference is managed with Update STANDARD / Restore Built-in, not site file selection.",
            )
            return

        candidates = list(source_version_candidates(self.selected_site.path, source_type) or [])
        auto_path = candidates[0] if candidates else self.selected_site.sources.get(source_type)
        auto_detection = self.selected_site.detections.get(source_type) if self.selected_site else None
        if auto_detection is not None and str(getattr(auto_detection, "method", "")).casefold() == "manual":
            auto_path = None
        labels = [
            (f"AUTO · Latest published version → {auto_path.name} · {source_file_version_label(auto_path)}"
             if auto_path is not None and has_explicit_source_version(auto_path) else
             f"AUTO · Detection rule fallback → {auto_path.name} · Unversioned"
             if auto_path is not None else "AUTO · No source detected")
        ]
        paths: list[Path | None] = [None]
        for candidate in candidates:
            try:
                modified = datetime.fromtimestamp(candidate.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                modified = "—"
            labels.append(f"PIN · {candidate.name} · {source_file_version_label(candidate)} · {modified}")
            paths.append(candidate)

        current_selection = self.store.source_file_selection(source_type)
        current_name = clean((current_selection or {}).get("file_name"))
        start_index = 0
        if current_name:
            for idx, candidate in enumerate(paths):
                if candidate and candidate.name.casefold() == current_name.casefold():
                    start_index = idx
                    break

        selected_label, ok = QInputDialog.getItem(
            self, "Choose Active File",
            f"{ref.label}\n\nAUTO uses the highest explicit V version first; if none exists it falls back to the configured Source Detection Rules. "
            "A pinned version always overrides AUTO until you return to AUTO.",
            labels, start_index, False,
        )
        if not ok:
            return
        selected_index = labels.index(selected_label)
        chosen = paths[selected_index]
        self.store.clear_manual_source_override(source_type)
        if chosen is None:
            self.store.clear_source_file_selection(source_type, self.user_name)
            message = (
                f"{ref.label}: AUTO latest version → {auto_path.name}"
                if auto_path is not None and has_explicit_source_version(auto_path) else
                f"{ref.label}: AUTO detection-rule fallback → {auto_path.name}"
                if auto_path is not None else
                f"{ref.label}: AUTO enabled · no source currently detected"
            )
        else:
            self.store.set_source_file_selection(source_type, chosen.name, self.user_name)
            message = f"{ref.label}: PINNED version → {chosen.name}"

        self.store.config["validation_required_after_source_import"] = True
        self.store.save_config()
        self.statusBar().showMessage(message + " · reading selected source...", 4000)
        self._reload_live_sources(
            [source_type], task_key="source-reload", quiet=False,
            label=f"Loading {ref.label}",
        )

    def assign_unmapped_source(self):
        if not self.selected_site or not hasattr(self, "unmapped_file_combo"):
            return
        raw_path = self.unmapped_file_combo.currentData()
        if not raw_path:
            return
        path = Path(str(raw_path))
        compatible = [
            definition for definition in SOURCE_DEFINITIONS
            if path.suffix.lower() in {".csv", ".xlsx", ".xlsm"}
        ]
        labels = [definition.label for definition in compatible]
        if not labels:
            return
        selected, ok = QInputDialog.getItem(self, "Assign Source", f"Assign {path.name} to:", labels, 0, False)
        if not ok:
            return
        definition = compatible[labels.index(selected)]
        save_manual_source_assignment(self.selected_site.path, definition.key, path)
        # Refresh filename discovery only; the selected file itself is read in
        # the background so assigning one source never blocks the GUI.
        self.refresh_site_repository(force=False, deep=False)
        self.statusBar().showMessage(ui_tr(f"Manual source mapping saved: {path.name} → {definition.label}", self.ui_language), 4000)
        self._reload_live_sources(
            [definition.key], task_key="source-reload", quiet=False,
            label=f"Loading {definition.label}",
            open_mapping_on_required=True,
        )

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"

    def _effective_site_source_path(self, source_type: str) -> Path | None:
        """Return the active source using persistent version pinning before auto discovery."""
        if self.selected_site and self.store:
            selected = selected_repository_source_path(self.selected_site, self.store, source_type)
            if selected is not None:
                return selected
        if self.store:
            manual = (self.store.manual_source_overrides().get(source_type) or {})
            original_text = clean(manual.get("original_path"))
            if original_text:
                original = Path(original_text)
                if original.exists() and original.is_file():
                    return original
            if self.store.is_manual_source_override(source_type):
                path = self.store.source_path(source_type)
                if path and path.exists():
                    return path
        if self.selected_site:
            path = self.selected_site.sources.get(source_type)
            if path and Path(path).exists():
                return Path(path)
        return self.store.source_path(source_type) if self.store else None

    def open_selected_site_folder(self):
        if not self.selected_site:
            QMessageBox.information(self, "Site Repository", "Select a site first.")
            return
        self._open_path(self.selected_site.path)

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

    def _open_source_mapping_for_type(self, source_type: str) -> None:
        """Open Map Fields directly for a staged source that needs remapping.

        This path is used immediately after a reviewer chooses a replacement
        file whose headers differ from the saved global mapping. It intentionally
        bypasses the currently selected table row so the exact affected source
        opens even if the UI selection changed while the background copy ran.
        """
        source_type = clean(source_type)
        if not source_type or not self.store:
            return
        path = standard_reference_path() if source_type == "standard_reference" else self._effective_site_source_path(source_type)
        if not path or not Path(path).exists():
            QMessageBox.information(self, "Source Mapping", "The selected source file is no longer available.")
            return
        schema = schema_for(source_type)
        if schema is None:
            QMessageBox.information(
                self, "Source Mapping",
                f"{source_label(source_type)} does not use a remappable CSV/XLSX column schema."
            )
            return
        try:
            before_custom_keys = {
                clean(item.get("field_key"))
                for item in (self.store.custom_source_fields(source_type) or [])
                if clean(item.get("field_key"))
            }
            dialog = SourceMappingDialog(source_type, Path(path), self.store, self.user_name, self)
        except Exception as exc:
            QMessageBox.critical(self, "Source Mapping", f"{type(exc).__name__}: {exc}")
            return
        if dialog.exec() != QDialog.Accepted:
            return
        # Visibility/display-name edits are presentation metadata and can update
        # the open Equipment Data Review header immediately; the authoritative
        # source-data reload continues in the background below.
        if hasattr(self, "comparison_table"):
            self._configure_comparison_headers()
        try:
            after_custom_keys = {
                clean(item.get("field_key"))
                for item in (self.store.custom_source_fields(source_type) or [])
                if clean(item.get("field_key"))
            }
            self._site_source_status_cache.clear()
            self._schema_validation_cache.clear()
            self._mark_site_pages_dirty()
            self._refresh_site_source_table(validate_schema=False)
            # Re-read the staged replacement only after the mapping is valid.
            self._reload_live_sources(
                [source_type], task_key="source-mapping-refresh", quiet=False,
                label=f"Applying {schema.label} field mapping",
                open_mapping_on_required=False,
            )
            if after_custom_keys != before_custom_keys:
                self.statusBar().showMessage("App column configuration updated globally.", 5000)
        except Exception as exc:
            QMessageBox.critical(self, "Source Mapping", f"{type(exc).__name__}: {exc}")

    def open_equipment_comparison_config(self, *_args):
        """Edit this site's arbitrary Equipment Data Review source contract."""
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Equipment Comparison", "Select a site first.")
            return
        try:
            dialog = ConfigurableEquipmentComparisonDialog(self.store, self.user_name, self)
        except Exception as exc:
            QMessageBox.critical(self, "Equipment Comparison", f"{type(exc).__name__}: {exc}")
            return
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            rows, _summary = build_equipment_source_view(self.store, "__ALL__")
            # Replace the persisted projection even when the new configuration
            # currently yields zero rows, so stale rows from the previous source
            # contract can never remain visible.
            self.store.save_comparison(rows)
            remember_configured_live_source_metadata(self.store)
            self._mark_site_pages_dirty()
            self._dirty_pages.add(2)
            self._refresh_site_source_table(validate_schema=False)
            if hasattr(self, "comparison_table"):
                self._refresh_equipment_profile_options(force=True)
                self._refresh_analysis_filter_options()
                self._configure_comparison_headers()
            if hasattr(self, "stack") and self.stack.currentIndex() == 2:
                self.refresh_comparison()
            self.refresh_dashboard()
            config = get_equipment_comparison_config(self.store, bootstrap=False)
            source_count = sum(bool(item.get("enabled", True)) for item in config.get("sources", []))
            comparison_count = len(config.get("comparisons", []))
            message = (
                f"设备对比已更新 · 已启用 {source_count} 个数据源 · {comparison_count} 个比较字段 · {len(rows)} 条索引记录"
                if self.ui_language == LANG_ZH_CN else
                f"Equipment comparison updated · {source_count} enabled source(s) · {comparison_count} comparison field(s) · {len(rows)} key row(s)"
            )
            self.statusBar().showMessage(message, 7000)
        except Exception as exc:
            QMessageBox.critical(self, "Equipment Comparison", f"Configuration was saved, but rebuilding the review failed:\n{type(exc).__name__}: {exc}")

    def open_source_mapping(self, *_args):
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Source Mapping", "Select a site first.")
            return
        module, ref, _table = self._current_module_source_selection()
        if module is not None and module.key == "rmu_review":
            self.open_equipment_comparison_config()
            return
        if ref is None:
            QMessageBox.information(self, "Source Mapping", "Select a table in the current module first.")
            return
        source_type = ref.source_type
        if source_type == "standard_reference":
            path = standard_reference_path()
        else:
            path = self._effective_site_source_path(source_type)
        if not path or not Path(path).exists():
            QMessageBox.information(
                self, "Source Mapping",
                f"{ref.label} is not currently mapped. Recommended name: {ref.expected_name}\n\n"
                "Click the Source File cell for this App Table to choose a version or browse another file."
            )
            return
        if schema_for(source_type) is None:
            QMessageBox.information(self, "Source Mapping", f"{ref.label} does not use a CSV/XLSX column schema.")
            return
        try:
            before_custom_keys = {
                clean(item.get("field_key"))
                for item in (self.store.custom_source_fields(source_type) or [])
                if clean(item.get("field_key"))
            }
            dialog = SourceMappingDialog(source_type, Path(path), self.store, self.user_name, self)
        except Exception as exc:
            QMessageBox.critical(self, "Source Mapping", f"{type(exc).__name__}: {exc}")
            return
        if dialog.exec() == QDialog.Accepted:
            # Apply Map Fields Show/Hide and App-label changes to the review
            # header immediately.  Data values are refreshed asynchronously.
            if hasattr(self, "comparison_table"):
                self._configure_comparison_headers()
            after_custom_keys = {
                clean(item.get("field_key"))
                for item in (self.store.custom_source_fields(source_type) or [])
                if clean(item.get("field_key"))
            }
            added_custom_keys = after_custom_keys - before_custom_keys
            if added_custom_keys:
                # A newly created App column must be visible on first appearance
                # even when this reviewer previously customized the grid.
                for field_key in added_custom_keys:
                    review_key = custom_review_column_key(source_type, field_key)
                    self.comparison_hidden_keys.discard(review_key)
                    self.comparison_visible_keys.add(review_key)
                save_review_hidden_columns(self.comparison_hidden_keys, "rmu_data_review")

            # Mapping persistence above is intentionally quick.  The live source
            # re-read plus RMU/Signal rebuild can be expensive, so never perform
            # it synchronously after the dialog closes.  A spawned process keeps
            # the Qt event loop free and the shared busy indicator moving from the
            # instant Save returns until the refreshed data is ready.
            self._apply_saved_source_mapping_async(source_type, ref.label)

    def _apply_saved_source_mapping_async(self, source_type: str, source_label: str) -> None:
        if not self.selected_site or not self.store or not self.repository_root:
            return
        if self._source_pipeline_busy():
            self.statusBar().showMessage(ui_tr("Source processing is already running. Please wait for it to finish.", self.ui_language), 4000)
            return

        site_name = self.selected_site.name
        project_folder = str(self.store.folder)
        repository_root = str(self.repository_root)
        source_label = clean(source_label) or clean(source_type) or "Source"
        task_label = f"Applying {source_label} field mapping"

        def success(result: dict):
            result_site = result.get("site")
            if result_site is None:
                return
            report = result.get("signal_report")
            if self.selected_site and self.selected_site.name == site_name:
                self._reopen_active_store_after_worker(result_site)
                self._active_site_signature = self._site_metadata_signature(result_site)
                self._site_source_status_cache.clear()
                self._schema_validation_cache.clear()
                if report is not None:
                    self.db_smart_report = report
                    self._db_smart_report_site = site_name
                    self._db_smart_ui_ready = False
                elif source_type in {"ioa", "adms_sld", "standard_reference"}:
                    self.db_smart_report = None
                    self._db_smart_report_site = ""
                    self._db_smart_ui_ready = False
                self._mark_site_pages_dirty()
                self._refresh_site_source_table(validate_schema=False)
                self.refresh_dashboard()
                self._dirty_pages.discard(0)
                current_index = self.stack.currentIndex() if hasattr(self, "stack") else 1
                if current_index in {2, 3}:
                    self._refresh_page_if_dirty(current_index)
                if current_index == 4:
                    self.refresh_changes()
            self.statusBar().showMessage(
                f"{source_label}: field mapping saved and affected data refreshed · global mapping active", 6000
            )

        def failed(details: str):
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.warning(
                self, "Mapping saved",
                f"The field mapping was saved, but affected data could not be refreshed immediately:\n{last_line}\n\n"
                "Your saved mapping and existing review data were not deleted. Run Validation after fixing the source file."
            )

        self._start_process_background_task(
            "mapping-save", task_label, "mapping-refresh",
            (project_folder, repository_root, site_name, source_type),
            success, on_error=failed,
        )

    def open_derived_table_builder(self):
        if not self.selected_site or not self.store:
            QMessageBox.information(self, "Derived Table Builder", "Select a site first.")
            return
        source_paths = {}
        for source_type in available_source_types():
            if source_type == "standard_reference":
                path = standard_reference_path()
                source_paths[source_type] = path if path.exists() else None
            else:
                source_paths[source_type] = self._effective_site_source_path(source_type)
        dialog = DerivedTableBuilderDialog(self.store, source_paths, self.user_name, self)
        dialog.exec()

    @staticmethod
    def _compatible_source_definitions(path: Path):
        suffix = Path(path).suffix.lower()
        keys = {definition.key for definition in SOURCE_DEFINITIONS} if suffix in {".csv", ".xlsx", ".xlsm"} else set()
        return [definition for definition in SOURCE_DEFINITIONS if definition.key in keys]

    def _choose_source_type_for_added_file(self, path: Path) -> str | None:
        """Detect one added file conservatively; ask only when detection is ambiguous."""
        compatible = self._compatible_source_definitions(path)
        if not compatible:
            QMessageBox.warning(self, "Unsupported Source", f"Unsupported source file type: {path.name}")
            return None
        ranked = rank_source_candidates(path)
        if len(compatible) == 1:
            return compatible[0].key
        if ranked:
            best = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0
            if best[1] >= 75 and best[1] - second_score >= 8:
                return best[0]

        score_map = {key: (score, detail) for key, score, detail in ranked}
        labels = []
        keys = []
        for definition in compatible:
            score, _detail = score_map.get(definition.key, (0, ""))
            suffix = f" · detected {score}%" if score else ""
            labels.append(f"{definition.label}{suffix}")
            keys.append(definition.key)
        selected, ok = QInputDialog.getItem(
            self, "Assign Source",
            f"The App cannot confidently identify {path.name}.\nChoose which source table it represents:",
            labels, 0, False,
        )
        if not ok:
            return None
        return keys[labels.index(selected)]

    def add_source_files(self):
        """Incrementally import one or many source files into the active App workspace.

        Each file is mapped independently. A reviewer may add one source now and
        another later; there is no all-at-once import requirement. Repository
        discovery remains read-only, while explicit imports become persistent
        workspace overrides for the selected site.
        """
        if not self.require_site():
            return
        initial = str(self.selected_site.path if self.selected_site else Path.home())
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Source File", initial,
            "Migration sources (*.csv *.xlsx *.xlsm);;CSV (*.csv);;Excel (*.xlsx *.xlsm);;All files (*.*)",
        )
        if not paths:
            return

        imported = []
        skipped = []
        failed = []
        for raw in paths:
            selected = Path(raw)
            source_type = self._choose_source_type_for_added_file(selected)
            if not source_type:
                skipped.append(selected.name)
                continue
            definition = next((item for item in SOURCE_DEFINITIONS if item.key == source_type), None)
            current = self.store.source_path(source_type) if self.store else None
            if current:
                try:
                    same_file = selected.resolve() == current.resolve()
                except OSError:
                    same_file = False
                if same_file:
                    skipped.append(selected.name)
                    continue
                answer = QMessageBox.question(
                    self, "Replace Source",
                    f"{definition.label if definition else source_type} already has an active file:\n{current.name}\n\nReplace it with {selected.name}?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    skipped.append(selected.name)
                    continue
            try:
                result = import_source(self.store, source_type, selected)
                self.store.mark_manual_source_override(source_type, selected)
                imported.append((source_type, result))
            except Exception as exc:
                failed.append(f"{selected.name}: {type(exc).__name__}: {exc}")

        if imported:
            self._site_source_status_cache.clear()
            self.store.config["validation_required_after_source_import"] = True
            self.store.save_config()
            changed_types = {key for key, _result in imported}
            if {"ioa", "adms_sld"} & changed_types:
                self.db_smart_report = None
                self._db_smart_ui_ready = False
            self.refresh_all(refresh_sources=False)
            self._render_site_list(preferred_name=self.selected_site.name if self.selected_site else None)
            self.statusBar().showMessage(
                f"Added {len(imported)} source file(s) · Run Validation when ready", 6000
            )

        lines = []
        if imported:
            lines.append("Imported and mapped:")
            for key, result in imported:
                definition = next((item for item in SOURCE_DEFINITIONS if item.key == key), None)
                lines.append(f"• {result.original_path.name} → {definition.label if definition else key}")
        if skipped:
            lines.append("\nSkipped: " + ", ".join(skipped))
        if failed:
            lines.append("\nFailed:\n" + "\n".join(failed))
        if lines:
            QMessageBox.information(self, "Import Source File", "\n".join(lines))

    def advanced_manual_import(self):
        """Backward-compatible command alias; the UI now uses incremental Add Source Files."""
        self.add_source_files()

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
        """Bind one repository site to its persistent Project Data workspace."""
        folder = workspace_root() / re.sub(r"[^A-Za-z0-9._-]+", "_", site.name)
        if not is_inside_workspace(folder):
            QMessageBox.critical(self, "Workspace restriction", f"Site project data must stay inside:\n{workspace_root()}")
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
        self.project_subtitle.setText(ui_tr(f"Migration Report · User: {self.user_name} · Site DB: project.db", self.ui_language))
        self.statusBar().showMessage(ui_tr(f"Site selected: {site.name}", self.ui_language), 5000)

    # ------------------------- comparison actions -------------------------
    def run_comparison(self):
        """Run full RMU + Signal validation outside the GUI thread."""
        if not self.selected_site:
            QMessageBox.warning(self, "Site required", "Select a site from Site Data Sources before running validation.")
            self.set_page(1)
            return
        if not self.repository_root:
            QMessageBox.warning(self, "Workspace required", "Select a Workspace before running validation.")
            return
        self._activate_site_workspace(self.selected_site)
        if not self.store:
            return

        site_name = self.selected_site.name
        project_folder = str(self.store.folder)
        repository_root = str(self.repository_root)

        def success(result: dict):
            result_site = result.get("site")
            if result_site is None:
                return
            report = result.get("signal_report")
            if self.selected_site and self.selected_site.name == site_name:
                self._reopen_active_store_after_worker(result_site)
                self._site_source_status_cache.clear()
                self._schema_validation_cache.clear()
                # Dashboard uses the persisted lightweight summary first so the
                # 5k+ signal rows are not reprocessed on the GUI thread. Keep
                # the already-built report for lazy Signal Mapping rendering.
                self.db_smart_report = None
                self._db_smart_report_site = ""
                self._db_smart_ui_ready = False
                self._mark_site_pages_dirty()
                self.refresh_dashboard()
                self._dirty_pages.discard(0)
                self.db_smart_report = report
                self._db_smart_report_site = site_name if report is not None else ""
                self._db_smart_ui_ready = False
                # Do not force-open RMU Data Review after Validation. Rebuilding
                # a large QTableWidget is a UI-only operation and should happen
                # only when the reviewer chooses that module.

            changed = ", ".join(result.get("changed_keys") or []) or "none"
            issue_fields = result.get("issue_fields") or {}
            issue_labels = result.get("issue_field_labels") or {}
            issue_order = list(result.get("issue_field_order") or [])
            if issue_order:
                ordered_issue_ids = issue_order + [key for key in issue_fields if key not in issue_order]
                breakdown = " · ".join(
                    f"{issue_labels.get(field_id) or field_id} {issue_fields.get(field_id, 0)}"
                    for field_id in ordered_issue_ids
                    if issue_fields.get(field_id, 0)
                ) or "No analysis mismatches"
            else:
                breakdown = " · ".join(
                    f"{name} {issue_fields.get(name, 0)}"
                    for name in ("NAME", "FEEDER", "SMART", "TYPE", "IP")
                    if issue_fields.get(name, 0)
                ) or "No analysis mismatches"
            report_obj = result.get("signal_report")
            if report_obj is not None:
                signal_text = (
                    f"\n\nSignal Mapping\nTotal: {len(report_obj.rows)}\nMatched: {result.get('signal_matched', 0)}\n"
                    f"Mismatched: {result.get('signal_mismatched', 0)}\nZENON Extra: {result.get('signal_zenon_extra', 0)}"
                )
            else:
                signal_text = "\n\nSignal Mapping\nUnavailable - check ZENON-ADMS IOA / ADMS SLD / STANDARD."
            QMessageBox.information(
                self, "Migration Validation complete",
                f"Validated site {site_name}.\nUpdated source files: {result.get('imported_count', 0)}"
                f"\nReloaded sources: {changed}\nSnapshot: {result.get('snapshot_dir', '')}\n\n"
                f"RMU Data Review\nTotal: {result.get('row_count', 0)}\nPass: {result.get('pass_count', 0)}\n"
                f"With Issues: {result.get('issue_count', 0)}\n{breakdown}{signal_text}",
            )
            self.statusBar().showMessage(ui_tr(f"Validation complete · {site_name}", self.ui_language), 6000)

        def failed(details: str):
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.critical(self, "Migration Validation failed", last_line)

        self._start_background_task(
            "validation", f"Validating {site_name}",
            lambda progress: _background_validation_job(
                project_folder, repository_root, site_name, progress
            ),
            success, on_error=failed, with_progress=True,
        )

    def _selected_comparison_rmus(self) -> list[str]:
        """Return unique RMUs represented by checked or selected review rows."""
        if not hasattr(self, "comparison_table"):
            return []
        rmu_col = next((i for i, (key, _label, _width) in enumerate(self._comparison_columns()) if key == "rmu"), -1)
        if rmu_col < 0:
            return []
        rows = sorted({index.row() for index in self.comparison_table.selectedIndexes()})
        if not rows and self.comparison_table.currentRow() >= 0:
            rows = [self.comparison_table.currentRow()]
        result = []
        for row in rows:
            item = self.comparison_table.item(row, rmu_col)
            review_key = clean(item.data(Qt.UserRole) if item else "") or clean(item.text() if item else "")
            if review_key and review_key not in result:
                result.append(review_key)
        return result

    def _comparison_row_by_rmu(self, rmu: str) -> dict | None:
        if not self.store:
            return None
        key = clean(rmu)
        cached = getattr(self, "_comparison_row_cache", {}).get(key)
        if cached is not None:
            return dict(cached)
        # Prefer the universal five-source row currently rendered. RMU still
        # uses its historical raw review key, while other classes use EQ::<TYPE>
        # namespaces, so no prior review history can collide or be lost.
        ctx = getattr(self, "_comparison_render_context", None) or {}
        for data in (ctx.get("rows") or []):
            if clean((data or {}).get("review_key") or (data or {}).get("rmu")) == key:
                return dict(data or {})
        profile = self._current_equipment_profile()
        try:
            rows, _summary = build_equipment_source_view(self.store, profile)
        except Exception:
            rows = []
        for data in rows:
            if clean(data.get("review_key") or data.get("rmu")) == key:
                return data
        # Legacy persisted RMU comparison rows remain a compatibility fallback
        # for old projects/reports, but are no longer the Equipment Review UI.
        direct = self.store.row_by_rmu(key)
        return direct or None

    @staticmethod
    def _equipment_display_name(review_key: str, data: dict | None = None) -> str:
        if data and clean((data or {}).get("rmu")):
            return clean((data or {}).get("rmu"))
        token = clean(review_key)
        if token.startswith("EQ::"):
            parts = token.split("::", 2)
            return parts[2] if len(parts) == 3 else token
        return token

    @staticmethod
    def _equipment_type_from_key(review_key: str, data: dict | None = None) -> str:
        if data and clean((data or {}).get("equipment_device_type")):
            return clean((data or {}).get("equipment_device_type")).upper()
        token = clean(review_key)
        if token.startswith("EQ::"):
            parts = token.split("::", 2)
            return parts[1].upper() if len(parts) >= 2 else "EQUIPMENT"
        return "RMU"

    def _refresh_comparison_resolution_progress_only(self) -> None:
        """Refresh Resolution counters entirely from the active in-memory session."""
        if not hasattr(self, "comparison_review_progress"):
            return
        entries = list(getattr(self, "_comparison_last_entries", []) or [])
        if not entries:
            return
        all_resolutions = getattr(self, "_comparison_resolution_map_cache", {}) or {}
        total_issue_decisions = resolved_issue_decisions = needs_action_decisions = 0
        for entry in entries:
            data = (entry or {}).get("data") or {}
            review_key = clean(data.get("review_key") or data.get("rmu"))
            state = (entry or {}).get("state") or analysis_review_state(data)
            saved = all_resolutions.get(review_key, {}) if isinstance(all_resolutions, dict) else {}
            for field in state.false_fields:
                total_issue_decisions += 1
                decision = clean((saved.get(field) or {}).get("decision_type")).upper()
                if decision:
                    resolved_issue_decisions += 1
                    if decision == "NEEDS_ACTION":
                        needs_action_decisions += 1
        resolution_pct = int(round(
            (resolved_issue_decisions / total_issue_decisions * 100.0) if total_issue_decisions else 100.0
        ))
        self.comparison_review_progress.setText(
            f"Resolution {resolved_issue_decisions} / {total_issue_decisions} issue decision(s) · {resolution_pct}% · "
            f"Unresolved {max(0, total_issue_decisions - resolved_issue_decisions)} · Needs Action {needs_action_decisions}"
        )

    def _refresh_comparison_resolution_row(self, rmu: str, *, refresh_progress: bool = True) -> None:
        """Patch one visible RMU after Review/Resolution/comment save without rebuilding all rows.

        A full refresh constructs thousands of QTableWidgetItem objects and was
        the main pause after Save Resolutions.  Analysis/source values do not
        change when a customer chooses a Resolution, so only Review, Resolution
        text and lightweight counters need repainting.
        """
        if not self.store or not hasattr(self, "comparison_table"):
            return
        data = self._comparison_row_by_rmu(rmu)
        if not data:
            return
        review_record = self.store.rmu_review_record(rmu)
        self._comparison_review_map_cache[clean(rmu)] = dict(review_record or {})
        review_status = rmu_review_display_status(data, review_record)
        state = analysis_review_state(data)
        if state.issue_count > 0:
            latest_resolution = self.store.rmu_resolution_map(rmu)
            self._comparison_resolution_map_cache[clean(rmu)] = dict(latest_resolution or {})
            summary = self.store.rmu_resolution_review_text(rmu)
        else:
            summary = clean(review_record.get("manual_comment"))
        entry = (getattr(self, "_comparison_entry_cache", {}) or {}).get(clean(rmu))
        if isinstance(entry, dict):
            entry["review_status"] = review_status
            entry["manual_review_comment"] = clean(review_record.get("manual_comment"))
            entry["resolution_summary"] = summary if state.issue_count > 0 else ""
            entry["resolution_display"] = summary

        columns = self._comparison_columns()
        rmu_col = next((i for i, (key, _label, _width) in enumerate(columns) if key == "rmu"), -1)
        comments_col = next((i for i, (key, _label, _width) in enumerate(columns) if key == "comments"), -1)
        target_row = int((getattr(self, "_comparison_row_index_cache", {}) or {}).get(clean(rmu), -1))
        if target_row < 0 and rmu_col >= 0:
            for row_index in range(self.comparison_table.rowCount()):
                item = self.comparison_table.item(row_index, rmu_col)
                item_key = clean(item.data(Qt.UserRole) if item else "") or clean(item.text() if item else "")
                if item_key == clean(rmu):
                    target_row = row_index
                    self._comparison_row_index_cache[clean(rmu)] = row_index
                    break
        if target_row < 0:
            if refresh_progress:
                self._refresh_comparison_resolution_progress_only()
            return

        # Filters are presentation-only in v0.8.196. Never remove physical rows
        # from the cached session; local filtering will hide/show this row.

        if comments_col >= 0:
            item = self.comparison_table.item(target_row, comments_col) or QTableWidgetItem()
            item.setText(summary)
            if state.issue_count > 0:
                tooltip = self.store.rmu_resolution_tooltip(rmu)
                tooltip += "\n\nDouble-click to resolve every active FALSE Analysis field."
            else:
                tooltip = (summary or "No optional manual Review comment recorded.") + (
                    "\n\nDouble-click to add a new Review comment. Previous comments are read-only and retained in history."
                )
            item.setToolTip(tooltip)
            font = item.font(); font.setBold(bool(summary)); item.setFont(font)
            self.comparison_table.setItem(target_row, comments_col, item)

        if state.issue_count > 0 and summary:
            height = min(104, 48 + 18 * max(0, min(state.issue_count, 3) - 1))
        else:
            height = 32
        self.comparison_table.setRowHeight(target_row, height)

        if hasattr(self, "comparison_locator") and target_row < self.comparison_locator.rowCount():
            self.comparison_locator.setRowHeight(target_row, height)
            label, review_fill, review_text = _review_visual(review_status)
            review_item = self.comparison_locator.item(target_row, 4) or QTableWidgetItem()
            review_item.setText(label)
            review_item.setBackground(review_fill)
            review_item.setForeground(review_text)
            review_item.setTextAlignment(Qt.AlignCenter)
            font = review_item.font(); font.setBold(True); review_item.setFont(font)
            review_item.setToolTip(
                f"{self._equipment_type_from_key(rmu, data)} {self._equipment_display_name(rmu, data)} · Analysis: {state.row_label} · Review: {review_status}" +
                (f" · Mismatch: {', '.join(state.false_fields)}" if state.false_fields else "")
            )
            self.comparison_locator.setItem(target_row, 4, review_item)

        if refresh_progress:
            self._refresh_comparison_resolution_progress_only()
        self._apply_comparison_filters_local()
        # Audit, history, report and dashboard are now stale, but there is no
        # reason to rebuild the currently visible RMU grid. They refresh lazily
        # when opened.
        self._dirty_pages.update({0, 4, 5, 6, 7})

    @staticmethod
    def _comparison_analysis_filter_match(entry: dict, analysis_filter: str) -> bool:
        analysis_filter = clean(analysis_filter) or "ALL ANALYSIS"
        if analysis_filter == "ALL ANALYSIS":
            return True
        data = (entry or {}).get("data") or {}
        state = (entry or {}).get("state") or analysis_review_state(data)
        false_keys = {clean(value).upper() for value in state.false_fields}
        if analysis_filter == "PASSED":
            return state.is_pass
        if analysis_filter == "ANY MISMATCH":
            return state.issue_count > 0
        if analysis_filter == "1 ISSUE":
            return state.issue_count == 1
        if analysis_filter == "2 ISSUES":
            return state.issue_count == 2
        if analysis_filter == "MULTIPLE ISSUES":
            return state.issue_count >= 3
        if analysis_filter == "CRITICAL":
            return state.is_critical
        if analysis_filter.startswith("RULE::"):
            return analysis_filter.split("::", 1)[1].upper() in false_keys
        if analysis_filter.endswith(" MISMATCH"):
            return analysis_filter.removesuffix(" MISMATCH") in false_keys
        return True

    def _apply_comparison_filters_local(self, *_args) -> None:
        """Apply search/review/analysis filters by hiding existing rows only.

        No source parse, SQLite map scan, worker process, QTableWidgetItem rebuild
        or Analysis recalculation is allowed on this hot interaction path.
        """
        if not getattr(self, "_comparison_dataset_ready", False):
            return
        if not hasattr(self, "comparison_table"):
            return
        entries = list(getattr(self, "_comparison_last_entries", []) or [])
        if len(entries) != self.comparison_table.rowCount():
            return
        term_cf = self.search_edit.text().strip().casefold() if hasattr(self, "search_edit") else ""
        search_field = (self.comparison_search_field.currentData() if hasattr(self, "comparison_search_field") else "*") or "*"
        review_filter = clean(self.rmu_review_filter_combo.currentData()) if hasattr(self, "rmu_review_filter_combo") else "ALL REVIEWS"
        analysis_filter = clean(self.analysis_combo.currentData()) if hasattr(self, "analysis_combo") else "ALL ANALYSIS"
        columns = tuple(self._comparison_columns())
        column_keys = [clean(item[0]) for item in columns if item]
        review_map = getattr(self, "_comparison_review_map_cache", {}) or {}
        visible_count = 0
        for row_index, entry in enumerate(entries):
            data = (entry or {}).get("data") or {}
            review_key = clean(data.get("review_key") or data.get("rmu"))
            review_status = rmu_review_display_status(data, review_map.get(review_key, {}))
            matches = review_filter in {"", "ALL REVIEWS"} or review_status == review_filter
            if matches:
                matches = self._comparison_analysis_filter_match(entry, analysis_filter)
            if matches and term_cf:
                review_text = clean((entry or {}).get("resolution_display"))
                if search_field == "comments":
                    searchable = review_text
                elif search_field and search_field != "*":
                    searchable = clean(data.get(search_field))
                else:
                    searchable = " | ".join(clean(data.get(key)) for key in column_keys) + " | " + review_text
                matches = term_cf in searchable.casefold()
            hidden = not matches
            if self.comparison_table.isRowHidden(row_index) != hidden:
                self.comparison_table.setRowHidden(row_index, hidden)
            if hasattr(self, "comparison_locator") and row_index < self.comparison_locator.rowCount():
                if self.comparison_locator.isRowHidden(row_index) != hidden:
                    self.comparison_locator.setRowHidden(row_index, hidden)
            if matches:
                visible_count += 1
        self._refresh_comparison_summary_only(shown_override=visible_count)

    def _refresh_comparison_summary_only(self, *, shown_override: int | None = None) -> None:
        """Refresh Equipment Review counters from cached states/maps only."""
        if not hasattr(self, "comparison_summary"):
            return
        entries = list(getattr(self, "_comparison_last_entries", []) or [])
        if not entries:
            return
        profile = self._current_equipment_profile()
        review_map = getattr(self, "_comparison_review_map_cache", {}) or {}
        review_counts = Counter()
        pass_rows = issue_rows = 0
        coverage_counts = Counter()
        for entry in entries:
            row = (entry or {}).get("data") or {}
            key = clean(row.get("review_key") or row.get("rmu"))
            review_counts[rmu_review_display_status(row, review_map.get(key, {}))] += 1
            state = (entry or {}).get("state") or analysis_review_state(row)
            pass_rows += int(bool(state.is_pass))
            issue_rows += int(state.issue_count > 0)
            coverage_counts[clean(row.get("equipment_source_count")) or "0/0"] += 1
        if shown_override is None:
            shown = sum(not self.comparison_table.isRowHidden(i) for i in range(self.comparison_table.rowCount()))
        else:
            shown = int(shown_override)
        coverage_text = " · ".join(f"{key} {value}" for key, value in sorted(coverage_counts.items(), reverse=True))
        label = "ALL EQUIPMENT" if profile == "__ALL__" else profile
        summary = (
            f"{label} · Total {len(entries)} · Shown {shown} · Pass {pass_rows} · With Issues {issue_rows} · "
            f"Unreviewed {review_counts.get('UNREVIEWED', 0)} · Closed {review_counts.get('CLOSED', 0)} · "
            f"Needs Action {review_counts.get('NEEDS ACTION', 0)} · Sources {coverage_text or 'No source coverage'}"
        )
        self.comparison_summary.setText(ui_tr(summary, self.ui_language))

    def open_rmu_resolution_dialog(self, rmu: str) -> None:
        if not self.store:
            return
        data = self._comparison_row_by_rmu(rmu)
        if not data:
            return
        state = analysis_review_state(data)
        if state.issue_count <= 0:
            QMessageBox.information(
                self, "Equipment Resolution",
                f"{self._equipment_type_from_key(rmu, data)} {self._equipment_display_name(rmu, data)} has no active Analysis mismatch. No Resolution decision is required."
            )
            return
        current = self.store.rmu_resolution_map(rmu)
        display_name = self._equipment_display_name(rmu, data)
        dialog = RMUResolutionDialog(display_name, data, current, self, equipment_type=self._equipment_type_from_key(rmu, data))
        if dialog.exec() != QDialog.Accepted:
            return
        decisions = dialog.decisions()
        # Compatibility note: the pre-v0.8.65 path called
        # self.store.set_rmu_resolution(...) once per issue on the GUI thread.
        # The worker now uses one batched transaction instead.
        project_folder = str(self.store.folder)
        site_name = self.selected_site.name if self.selected_site else ""
        task_key = f"resolution:{site_name}:{clean(rmu)}"

        def success(result: dict):
            # The reviewer may have switched sites while this tiny write was in
            # flight. The project was still saved correctly; only repaint when
            # the original site is still active.
            if self.selected_site and self.selected_site.name == site_name and self.store:
                self._refresh_comparison_resolution_row(rmu)
                self._select_comparison_rmu(rmu)
                self._schedule_comparison_lifecycle_refresh()
                # Site History can contain thousands of audit/lifecycle cells.
                # Mark it dirty and rebuild only when that page is opened.
                self._dirty_pages.update({0, 4, 5, 6, 7})
            self.statusBar().showMessage(
                f"{self._equipment_type_from_key(rmu, data)} {display_name} Resolution saved · Review: {result.get('review_status', '')} · {result.get('summary', '')}",
                7000,
            )

        def failed(details: str):
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.critical(self, "Save Equipment Resolution", last_line)

        self._start_background_task(
            task_key, f"Saving {self._equipment_type_from_key(rmu, data)} {display_name} Resolution",
            lambda: _background_resolution_save_job(project_folder, rmu, data, decisions, self.user_name),
            success, on_error=failed,
        )

    def edit_rmu_manual_review_comment(self, rmu: str, *, prompt_title: str = "Equipment Review Comments") -> bool:
        """Append a new optional human-review note without editing history in place.

        The previous v0.8.146 dialog opened with the latest text inside the
        editable box. Although the database retained history, a reviewer could
        understandably think they were editing the old record and accidentally
        clear/replace it. v0.8.147 separates immutable history from the new
        submission: prior notes are read-only, the new editor starts blank, and
        Continue from Latest is an explicit copy action.
        """
        if not self.store:
            return False
        data = self._comparison_row_by_rmu(rmu)
        if not data:
            return False
        state = analysis_review_state(data)
        if not state.has_result:
            QMessageBox.information(
                self, "Validation Required",
                f"{self._equipment_type_from_key(rmu, data)} {self._equipment_display_name(rmu, data)} does not yet have a complete automatic Analysis result. Run Validation before recording an optional manual Review comment."
            )
            return False
        if state.issue_count > 0:
            self.open_rmu_resolution_dialog(rmu)
            return False

        display_name = self._equipment_display_name(rmu, data)
        device_type = self._equipment_type_from_key(rmu, data)
        old_comment = self.store.rmu_manual_review_comment(rmu)
        history = [
            event for event in self.store.rmu_review_events(rmu)
            if not clean(event.get("analysis_field"))
            and clean(event.get("event_type")).upper() in {"COMMENT_RECORDED", "COMMENT_CLEARED"}
        ]
        dialog = RMUReviewCommentDialog(display_name, old_comment, history, self, equipment_type=device_type)
        dialog.setWindowTitle(prompt_title)
        if dialog.exec() != QDialog.Accepted:
            return False
        comment = dialog.comment()
        try:
            self.store.append_rmu_manual_review_comment(
                rmu, comment, self.user_name,
                reason=f"{device_type} manual Review comment added",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Add Equipment Review Comment", f"{type(exc).__name__}: {exc}")
            return False

        # A comment changes neither automatic Analysis nor Review counters.
        # Patch only the selected row and selected-equipment timeline; expensive
        # history/dashboard/report pages are refreshed lazily on navigation.
        self._refresh_comparison_resolution_row(rmu, refresh_progress=False)
        self._select_comparison_rmu(rmu)
        self._schedule_comparison_lifecycle_refresh()
        self._dirty_pages.update({0, 4, 5, 6, 7})
        total = len(history) + 1
        self.statusBar().showMessage(
            f"{device_type} {display_name} Review comment added · history {total} record(s) · previous comments retained", 6000
        )
        return True

    def _patch_cached_review_status(self, review_key: str, status: str) -> None:
        """Optimistically patch one visible review status without touching SQLite."""
        key = clean(review_key)
        if not key:
            return
        value = normalize_review_status(status)
        record = dict((getattr(self, "_comparison_review_map_cache", {}) or {}).get(key, {}))
        record.update({
            "rmu": key,
            "review_status": value,
            "reviewed_by": self.user_name or "User",
            "reviewed_at": datetime.now().isoformat(timespec="seconds"),
        })
        self._comparison_review_map_cache[key] = record
        entry = (getattr(self, "_comparison_entry_cache", {}) or {}).get(key)
        if isinstance(entry, dict):
            entry["review_status"] = value
        row_index = (getattr(self, "_comparison_row_index_cache", {}) or {}).get(key, -1)
        if row_index is None or row_index < 0:
            return
        if hasattr(self, "comparison_locator") and row_index < self.comparison_locator.rowCount():
            data = (entry or {}).get("data") if isinstance(entry, dict) else self._comparison_row_cache.get(key, {})
            data = data or {}
            state = (entry or {}).get("state") if isinstance(entry, dict) else None
            state = state or analysis_review_state(data)
            label, review_fill, review_text = _review_visual(value)
            item = self.comparison_locator.item(row_index, 4) or QTableWidgetItem()
            item.setText(label)
            item.setBackground(review_fill)
            item.setForeground(review_text)
            item.setTextAlignment(Qt.AlignCenter)
            font = item.font(); font.setBold(True); item.setFont(font)
            item.setToolTip(
                f"{self._equipment_type_from_key(key, data)} {self._equipment_display_name(key, data)} · "
                f"Analysis: {state.row_label} · Review: {value}"
                + (f" · Mismatch: {', '.join(state.false_fields)}" if state.false_fields else "")
            )
            self.comparison_locator.setItem(row_index, 4, item)

    def set_comparison_review_status(self, requested_status: str | None = None):
        """Set Equipment Review state optimistically, then persist in background."""
        if not self.store:
            return
        rmus = self._selected_comparison_rmus()
        if not rmus:
            QMessageBox.information(self, "Equipment Data Review", "Select one or more cells / equipment rows first.")
            return

        options = ["Unreviewed", "Closed", "Needs Action"]
        value_by_label = {"Unreviewed": "UNREVIEWED", "Closed": "CLOSED", "Needs Action": "NEEDS ACTION"}
        review_map = getattr(self, "_comparison_review_map_cache", {}) or {}
        if requested_status:
            value = normalize_review_status(requested_status)
            choice = next((label for label, code in value_by_label.items() if code == value), "Unreviewed")
        else:
            current_values = {
                rmu_review_display_status(self._comparison_row_cache.get(key, {}), review_map.get(key, {}))
                for key in rmus
            }
            current_value = next(iter(current_values)) if len(current_values) == 1 else "UNREVIEWED"
            current_label = next((label for label, code in value_by_label.items() if code == current_value), "Unreviewed")
            choice, ok = QInputDialog.getItem(
                self, "Set Equipment Review Status",
                f"{len(rmus)} equipment row(s) selected.\n\nChoose: Unreviewed, Closed or Needs Action.",
                options, options.index(current_label), False,
            )
            if not ok:
                return
            value = value_by_label[choice]

        reason_by_value = {
            "UNREVIEWED": "Equipment Data Review marked Unreviewed",
            "CLOSED": "Equipment Data Review marked Closed",
            "NEEDS ACTION": "Equipment Data Review marked Needs Action",
        }
        # UI first: all visible rows/counters update before any lifecycle/audit
        # SQLite writes. A worker transaction then durably saves the selection.
        for rmu in rmus:
            self._patch_cached_review_status(rmu, value)
            if value == "NEEDS ACTION":
                self._comparison_action_tracking_keys.add(clean(rmu))
        self._apply_comparison_filters_local()
        self._dirty_pages.update({0, 4, 5, 6, 7})
        if len(rmus) == 1:
            self._select_comparison_rmu(rmus[0])
        self.statusBar().showMessage(
            ui_tr(f"Equipment Review updated locally: {len(rmus)} row(s) → {choice} · saving…", self.ui_language), 2200
        )

        project_folder = str(self.store.folder)
        site_name = self.selected_site.name if self.selected_site else ""
        updates = [(key, value, reason_by_value[value]) for key in rmus]
        task_key = f"review-status:{site_name}"

        # If another status transaction is already running, queue/merge this
        # latest choice per equipment instead of blocking the GUI.
        pending = getattr(self, "_pending_review_status_updates", None)
        if pending is None:
            pending = {}
            self._pending_review_status_updates = pending
        for key, status, reason in updates:
            pending[key] = (status, reason)

        if task_key in self._background_tasks:
            return

        def flush_pending():
            if not self.store or (self.selected_site and self.selected_site.name != site_name):
                return
            queued = getattr(self, "_pending_review_status_updates", {}) or {}
            if not queued:
                return
            batch = [(key, val[0], val[1]) for key, val in queued.items()]
            self._pending_review_status_updates = {}

            def success(result: dict):
                self._dirty_pages.update({0, 4, 5, 6, 7})
                if len(batch) == 1:
                    self._schedule_comparison_lifecycle_refresh()
                self.statusBar().showMessage(
                    ui_tr(f"Equipment Review saved · {int((result or {}).get('count') or 0)} row(s)", self.ui_language), 2200
                )
                if getattr(self, "_pending_review_status_updates", None):
                    QTimer.singleShot(0, flush_pending)

            def failed(details: str):
                last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
                QMessageBox.critical(self, "Equipment Review", last_line)
                # Durable state is authoritative on failure; rebuild once only on
                # this exceptional path to reconcile the optimistic UI.
                self.refresh_comparison()

            self._start_background_task(
                task_key, "Saving Equipment Review Status",
                lambda: _background_review_status_batch_job(project_folder, batch, self.user_name),
                success, on_error=failed,
            )

        flush_pending()

    def edit_comparison_cell(self, row_index: int, column_index: int):
        if not self.store:
            return
        field, label, _ = self._comparison_columns()[column_index]
        rmu_col = next((i for i, (key, _label, _width) in enumerate(self._comparison_columns()) if key == "rmu"), -1)
        rmu_item = self.comparison_table.item(row_index, rmu_col) if rmu_col >= 0 else None
        value_item = self.comparison_table.item(row_index, column_index)
        if not rmu_item:
            return
        rmu = clean(rmu_item.data(Qt.UserRole)) or rmu_item.text()
        value = value_item.text() if value_item else ""
        analysis_fields = {
            key for key, _label, _width in self._comparison_columns()
            if key.startswith("analysis__") or key in {"analysis_name", "analysis_feeder", "analysis_smart", "analysis_type", "analysis_ip"}
        }
        if field == "comments":
            data = self._comparison_row_by_rmu(rmu)
            state = analysis_review_state(data or {})
            if state.issue_count > 0:
                self.open_rmu_resolution_dialog(rmu)
            elif state.has_result:
                self.edit_rmu_manual_review_comment(rmu)
            else:
                QMessageBox.information(
                    self, "Validation Required",
                    f"Equipment {self._equipment_display_name(rmu, data or {})} has no complete automatic Analysis result yet. Run Validation before recording Review/Resolution information."
                )
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
            QMessageBox.information(self, "Read-only field", f"{label} is generated as a protected key and cannot be edited here. Right-click this cell (or use Set Status) to change the row Human Review status.")
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
        self.statusBar().showMessage(ui_tr(f"Audit entry recorded for equipment {self._equipment_display_name(rmu, self._comparison_row_by_rmu(rmu) or {})}: {label}", self.ui_language), 5000)

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
        version_id = self.store.save_version(name.strip(), description.strip() or "Manual snapshot", self.user_name)
        self.store.create_site_revision(
            name.strip(), description.strip() or "Manual snapshot", self.user_name, version_id=version_id
        )
        self.refresh_versions()
        self.refresh_site_history()
        self.refresh_dashboard()
        QMessageBox.information(self, "Version saved", f"{name.strip()} has been saved in the site audit database.")

    def create_site_revision(self):
        if not self.require_site():
            return
        revisions = self.store.site_revisions()
        default = f"R{len(revisions) + 1:03d}"
        name, ok = QInputDialog.getText(self, "New Site Revision", "Revision name", text=default)
        if not ok or not name.strip():
            return
        description, ok = QInputDialog.getMultiLineText(
            self,
            "Revision Notes",
            "Describe the site work included in this revision.",
            "Site modification / issue closure checkpoint",
        )
        if not ok:
            return
        description = description.strip() or "Site modification / issue closure checkpoint"
        version_id = self.store.save_version(name.strip(), description, self.user_name)
        self.store.create_site_revision(name.strip(), description, self.user_name, version_id=version_id)
        self.refresh_versions()
        self.refresh_site_history()
        self.refresh_dashboard()
        self.statusBar().showMessage(ui_tr(f"Site revision created: {name.strip()}", self.ui_language), 5000)

    def add_site_issue_action(self):
        if not self.require_site():
            return
        dialog = IssueActionDialog(self.store.site_revisions(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.values()
        try:
            self.store.add_issue_action(created_by=self.user_name, **values)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", f"{type(exc).__name__}: {exc}")
            return
        self.refresh_site_history()
        self.refresh_dashboard()
        self.statusBar().showMessage("Issue / Action record saved in persistent Site History", 5000)

    def _selected_site_revision(self) -> dict | None:
        if not self.store:
            return None
        table = getattr(self, "site_revisions_table", None)
        if table is not None and table.currentRow() >= 0:
            item = table.item(table.currentRow(), 0)
            if item:
                try:
                    revision_id = int(item.text())
                except ValueError:
                    revision_id = -1
                for revision in self.store.site_revisions():
                    if int(revision.get("id") or -1) == revision_id:
                        return revision
        return self.store.latest_site_revision()

    def _confirm_review_draft_export(self, artifact_label: str) -> tuple[bool, bool]:
        """Allow historical review-draft export while protecting formal handover.

        Older deployed builds allowed reviewers to export while the project state
        was VALIDATION REQUIRED.  Later builds accidentally turned the validation
        marker into a hard export gate even though the Report Export page still
        stated that review-draft export was available.  Keep the warning, but let
        the reviewer explicitly continue with a clearly identified draft.
        """
        validation_pending = bool(self.store.config.get("validation_required_after_source_import", False)) if self.store else False
        delivery_state = clean(getattr(self, "project_delivery_state", ""))
        draft_required = validation_pending or delivery_state != "READY FOR EXPORT"
        if not draft_required:
            return True, False

        label = clean(artifact_label) or "report"
        if self.ui_language == LANG_ZH_CN:
            title = "导出审核草稿"
            if validation_pending:
                reason = (
                    "一个或多个当前 Excel/CSV 数据源，或当前 STANDARD 工作簿，在上次校验后发生了变化。\n\n"
                    "仍然可以导出审核草稿，但草稿使用的是当前项目数据库中最近一次已计算的审核结果；"
                    "在重新运行“校验”之前，它可能不会反映刚刚变更的数据源。"
                )
            else:
                reason = f"当前交付状态为：{delivery_state or '审核未完成'}。"
            message = (
                reason
                + "\n\n该文件仅用于内部审核/沟通，不应作为最终正式交付或签字依据。"
                + f"\n\n是否继续导出 {label} 审核草稿？"
            )
        else:
            title = "Export Review Draft"
            if validation_pending:
                reason = (
                    "One or more active Excel/CSV sources or the active STANDARD workbook changed after the last Validation.\n\n"
                    "You can still export a review draft, but it uses the most recently calculated review data currently stored in the project database. "
                    "Until Validation is run again, the draft may not reflect the newly changed source file(s)."
                )
            else:
                reason = f"Current delivery state: {delivery_state or 'Review incomplete'}."
            message = (
                reason
                + "\n\nThis file is for internal review/coordination only and must not be treated as the final formal handover or signed acceptance."
                + f"\n\nExport the {label} review draft now?"
            )

        answer = QMessageBox.question(
            self, title, message,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return answer == QMessageBox.Yes, True

    @staticmethod
    def _safe_export_filename(text: str) -> str:
        value = re.sub(r'[<>:"/\\|?*]+', '_', clean(text)).strip(' ._')
        return value or "MigrationReport"

    def _choose_export_target(self, caption: str, filename: str, file_filter: str, suffix: str) -> Path | None:
        """Require an explicit Save As decision for every formal export.

        A suggested filename is provided for convenience, but no file is written
        until the reviewer confirms a location in the native Save dialog.
        """
        suggested_root = Path.home()
        if self.selected_site and getattr(self.selected_site, "path", None):
            try:
                suggested_root = Path(self.selected_site.path)
            except Exception:
                pass
        selected, _ = QFileDialog.getSaveFileName(
            self, caption, str(suggested_root / filename), file_filter
        )
        if not selected:
            return None
        target = Path(selected)
        if target.suffix.lower() != suffix.lower():
            target = target.with_suffix(suffix)
        return target

    def export_signoff_pdf(self):
        if not self.require_site():
            return
        if self.store.comparison_row_count() <= 0:
            title = "无可导出的审核数据" if self.ui_language == LANG_ZH_CN else "No review data"
            message = (
                "当前项目还没有任何已计算的设备审核数据。至少需要先成功运行一次校验，然后才能导出 PDF。"
                if self.ui_language == LANG_ZH_CN
                else "The project does not contain any calculated equipment review data yet. Run Validation successfully at least once before exporting a PDF."
            )
            QMessageBox.warning(self, title, message)
            return
        proceed, review_draft = self._confirm_review_draft_export("PDF")
        if not proceed:
            return

        # Prepared By is a formal report field, not an inferred application value.
        # Require the exporter to type the name for every PDF so the printed report
        # explicitly records who prepared/exported this revision.
        while True:
            prepared_by, ok = QInputDialog.getText(
                self,
                "Prepared By",
                "Enter the name of the person preparing / exporting this report:",
            )
            if not ok:
                return
            prepared_by = clean(prepared_by)
            if prepared_by:
                break
            QMessageBox.warning(self, "Prepared By Required", "Enter a name before exporting the PDF report.")

        revision = self._selected_site_revision()
        site_name = self._safe_export_filename(
            self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name
        )
        revision_name = self._safe_export_filename(clean((revision or {}).get("revision_name")) or f"v{APP_VERSION}")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        draft_token = "_DRAFT" if review_draft else ""
        target_path = self._choose_export_target(
            "Choose Sign-off PDF Save Location",
            f"{site_name}_{revision_name}_Issue_Closure{draft_token}_{stamp}.pdf",
            "PDF Files (*.pdf)",
            ".pdf",
        )
        if target_path is None:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            target, snapshot = export_site_signoff_pdf(
                self.store,
                revision=revision,
                prepared_by=prepared_by,
                company="NARI",
                review_draft=review_draft,
                target_path=target_path,
            )
            self.store.record_signoff_report(
                revision_id=revision.get("id") if revision else None,
                path=target,
                snapshot=snapshot,
                created_by=self.user_name,
                report_type="SITE_SIGNOFF_DRAFT" if review_draft else "SITE_SIGNOFF",
            )
        except Exception as exc:
            QMessageBox.critical(self, "PDF export failed", f"{type(exc).__name__}: {exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh_site_history()
        self.refresh_export_page()
        generated_title = (
            "审核草稿 PDF 已生成"
            if review_draft and self.ui_language == LANG_ZH_CN
            else "Review Draft PDF generated"
            if review_draft
            else "签字 PDF 已生成"
            if self.ui_language == LANG_ZH_CN
            else "Sign-off PDF generated"
        )
        generated_message = (
            f"审核草稿 PDF 已保存：\n\n{target}\n\n该文件不是正式交付/签字版本。是否现在打开？"
            if review_draft and self.ui_language == LANG_ZH_CN
            else f"Review-draft PDF saved successfully:\n\n{target}\n\nThis is not the formal handover/signature version. Open the PDF now?"
            if review_draft
            else f"可打印签字 PDF 已保存：\n\n{target}\n\n是否现在打开？"
            if self.ui_language == LANG_ZH_CN
            else f"Printable sign-off PDF saved successfully:\n\n{target}\n\nOpen the PDF now?"
        )
        answer = QMessageBox.question(
            self,
            generated_title,
            generated_message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self._open_path(target)

    def _selected_signoff_report(self) -> dict | None:
        if not self.store or not hasattr(self, "site_reports_table"):
            return None
        row = self.site_reports_table.currentRow()
        if row < 0:
            return None
        item = self.site_reports_table.item(row, 0)
        if not item:
            return None
        try:
            report_id = int(item.text())
        except ValueError:
            return None
        return next((report for report in self.store.signoff_reports() if int(report.get("id") or -1) == report_id), None)

    def attach_signed_signoff_pdf(self):
        if not self.require_site():
            return
        report = self._selected_signoff_report()
        if not report:
            QMessageBox.information(self, "Select report", "Select a generated PDF record first.")
            return
        try:
            report_snapshot = json.loads(clean(report.get("snapshot_json")) or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            report_snapshot = {}
        if clean(report_snapshot.get("document_status")).upper() == "REVIEW DRAFT":
            if self.ui_language == LANG_ZH_CN:
                QMessageBox.warning(
                    self, "审核草稿不能作为正式签字版本",
                    "所选 PDF 是在校验/审核未完成时生成的 REVIEW DRAFT。\n\n"
                    "请先重新运行“校验”并完成需要的人工审核，然后重新生成正式签字 PDF。"
                )
            else:
                QMessageBox.warning(
                    self, "Review draft cannot be signed",
                    "The selected PDF was generated as a REVIEW DRAFT while Validation or Human Review was incomplete.\n\n"
                    "Run Validation, complete the required review, and generate a formal sign-off PDF before attaching a signed copy."
                )
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Attach Signed PDF",
            str(self.store.reports_dir),
            "PDF Files (*.pdf)",
        )
        if not selected:
            return
        try:
            target = self.store.attach_signed_report(int(report["id"]), Path(selected))
        except Exception as exc:
            QMessageBox.critical(self, "Attach failed", f"{type(exc).__name__}: {exc}")
            return
        self.refresh_site_history()
        QMessageBox.information(self, "Signed PDF attached", f"Signed copy saved to:\n\n{target}")

    def open_selected_signoff_pdf(self):
        report = self._selected_signoff_report()
        if not report:
            QMessageBox.information(self, "Select report", "Select a PDF record first.")
            return
        signed_path = clean(report.get("signed_file_path"))
        generated_path = clean(report.get("file_path"))
        path = Path(signed_path or generated_path)
        if not path.exists():
            QMessageBox.warning(self, "File not found", f"The recorded PDF is not available at:\n\n{path}")
            return
        self._open_path(path)

    def export_excel(self):
        if not self.require_site():
            return
        if self.store.comparison_row_count() <= 0:
            title = "无可导出的审核数据" if self.ui_language == LANG_ZH_CN else "No review data"
            message = (
                "当前项目还没有任何已计算的设备审核数据。至少需要先成功运行一次校验，然后才能导出 Excel。"
                if self.ui_language == LANG_ZH_CN
                else "The project does not contain any calculated equipment review data yet. Run Validation successfully at least once before exporting Excel."
            )
            QMessageBox.warning(self, title, message)
            return
        proceed, review_draft = self._confirm_review_draft_export("Excel")
        if not proceed:
            return
        site_name = self._safe_export_filename(
            self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name
        )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        draft_token = "-DRAFT" if review_draft else ""
        target_path = self._choose_export_target(
            "Choose Migration Report Save Location",
            f"{site_name}-REVIEW{draft_token}-{stamp}.xlsx",
            "Excel Workbook (*.xlsx)",
            ".xlsx",
        )
        if target_path is None:
            return
        project_folder = str(self.store.folder)

        def success(result):
            target = Path(str(result))
            # Formal Excel exports may live anywhere the reviewer chooses.
            # Persist the actual external target so Dashboard readiness does not
            # depend on scanning the legacy internal reports/ directory.
            self.store.config["last_migration_report_export_path"] = str(target)
            self.store.config["last_migration_report_export_at"] = datetime.now().isoformat(timespec="seconds")
            self.store.save_config()
            answer = QMessageBox.question(
                self,
                "Export complete",
                f"Report saved successfully:\n\n{target}\n\nOpen the report now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            self._dirty_pages.add(0)
            if answer == QMessageBox.Yes:
                self._open_path(target)

        def failed(details: str):
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            QMessageBox.critical(self, "Export failed", last_line)

        self._start_background_task(
            "excel-export",
            "Exporting Migration Report",
            lambda: _background_excel_export_job(project_folder, str(target_path)),
            success,
            on_error=failed,
        )

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
    def refresh_all(self, *, refresh_sources: bool = False):
        """Refresh application state without eagerly rebuilding hidden pages.

        The dashboard/top delivery status is kept current.  Heavy review/history
        grids are marked dirty and rendered on first navigation to that module.
        """
        if refresh_sources:
            self.refresh_import_page(force_scan=True)
        elif hasattr(self, "site_list"):
            self._refresh_site_source_table()
        self._dirty_pages.update({2, 3, 4, 5, 6, 7})
        self.refresh_dashboard()
        self._dirty_pages.discard(0)
        current_index = self.stack.currentIndex() if hasattr(self, "stack") else 0
        if current_index not in {0, 1}:
            self._refresh_page_if_dirty(current_index)

    def refresh_import_page(self, *, force_scan: bool = False):
        if not hasattr(self, "site_list"):
            return
        if force_scan or not self.repository_sites:
            self.refresh_site_repository(force=True)
        else:
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
        if selected.startswith("RULE::"):
            wanted = selected.split("::", 1)[1].upper()
            return wanted in {clean(value).upper() for value in false_keys}
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
        # column header already identifies NAME / FEEDER / SMART / TYPE / IP.
        return QColor("#F7D7D7") if value.upper() == "FALSE" else None

    def _capture_comparison_selection_keys(self) -> list[tuple[str, str]]:
        if not hasattr(self, "comparison_table"):
            return []
        rmu_col = next((i for i, (key, _label, _width) in enumerate(self._comparison_columns()) if key == "rmu"), -1)
        if rmu_col < 0:
            return []
        captured = []
        seen = set()
        for index in self.comparison_table.selectedIndexes():
            rmu_item = self.comparison_table.item(index.row(), rmu_col)
            if not rmu_item or index.column() >= len(self._comparison_columns()):
                continue
            pair = (clean(rmu_item.text()), self._comparison_columns()[index.column()][0])
            if pair[0] and pair not in seen:
                seen.add(pair)
                captured.append(pair)
        return captured

    def _restore_comparison_selection_keys(self, captured: list[tuple[str, str]]) -> None:
        if not captured or not hasattr(self, "comparison_table"):
            return
        rmu_col = next((i for i, (key, _label, _width) in enumerate(self._comparison_columns()) if key == "rmu"), -1)
        key_to_col = {key: i for i, (key, _label, _width) in enumerate(self._comparison_columns())}
        row_by_rmu = {}
        if rmu_col >= 0:
            for row in range(self.comparison_table.rowCount()):
                item = self.comparison_table.item(row, rmu_col)
                if item:
                    row_by_rmu[clean(item.text())] = row
        for rmu, key in captured:
            row = row_by_rmu.get(rmu)
            col = key_to_col.get(key)
            if row is None or col is None:
                continue
            item = self.comparison_table.item(row, col)
            if item:
                item.setSelected(True)

    def refresh_comparison(self):
        """Refresh RMU Data Review while keeping the busy marquee continuously alive.

        All whole-table SQLite/JSON reads, filtering and summary calculations
        run in a spawned background process.  The Qt GUI thread only captures
        current controls, receives the prepared payload, and paints one RMU row
        per timer turn.  This keeps the liveness marquee moving even on the
        first cached-page load and on slower Windows/PyInstaller machines.
        """
        if not hasattr(self, "comparison_table"):
            return

        # Coalesce repeated filter/search refreshes while one preparation job is
        # in flight.  The newest request is rerun immediately after the current
        # payload returns instead of starting competing processes against the
        # same project.db.
        if "rmu-render-prepare" in self._background_tasks:
            self._comparison_refresh_pending = True
            self._set_comparison_loading(True, "Updating RMU Data Review in background... Please wait.")
            return

        self._comparison_refresh_pending = False
        self._comparison_render_generation += 1
        generation = self._comparison_render_generation
        captured_selection = self._capture_comparison_selection_keys()

        self.comparison_table.setUpdatesEnabled(True)
        if hasattr(self, "comparison_locator"):
            self.comparison_locator.setUpdatesEnabled(True)
        self.comparison_table.setRowCount(0)
        if hasattr(self, "comparison_locator"):
            self.comparison_locator.setRowCount(0)

        if not self.store:
            self.comparison_summary.setText("No site selected")
            if hasattr(self, "comparison_review_progress"):
                self.comparison_review_progress.setText("Resolution 0 / 0 issue decisions · Human status is independent")
            self._comparison_render_context = None
            self._set_comparison_loading(False)
            self._hide_busy_operation("rmu-show-all")
            return

        self._refresh_equipment_profile_options()
        self._apply_equipment_profile_ui_mode()
        self._configure_comparison_headers()
        profile = self._current_equipment_profile()
        mode_label = "configured equipment review" if get_equipment_comparison_config(self.store, bootstrap=False).get("sources") else "legacy equipment review"
        self._set_comparison_loading(True, f"Loading {mode_label} in background... Please wait.")
        # Build the canonical dataset once. Search/review/analysis filters are
        # presentation-only and are applied locally by hiding rows, so changing
        # a filter never spawns a worker or reconstructs thousands of cells.
        term = ""
        search_field = "*"
        review_filter = "ALL REVIEWS"
        analysis_filter = "ALL ANALYSIS"
        columns = tuple(self._comparison_columns())
        project_folder = str(self.store.folder)

        def success(payload: dict):
            if generation != self._comparison_render_generation:
                self._comparison_refresh_pending = True
            if self.stack.currentIndex() != 2:
                self._dirty_pages.add(2)
                self._set_comparison_loading(False)
                return
            if self._comparison_refresh_pending:
                self._comparison_refresh_pending = False
                QTimer.singleShot(0, self.refresh_comparison)
                return

            shown = list(payload.get("shown") or [])
            rows = list(payload.get("rows") or [])
            self._comparison_last_rows = rows
            self._comparison_last_shown = shown
            review_map = dict(payload.get("review_map") or {})
            all_resolutions = dict(payload.get("all_resolutions") or {})
            self._comparison_last_entries = shown
            self._comparison_review_map_cache = review_map
            self._comparison_resolution_map_cache = all_resolutions
            self._comparison_action_tracking_keys = {clean(value) for value in (payload.get("action_tracking_keys") or []) if clean(value)}
            self._comparison_row_cache = {
                clean((row or {}).get("review_key") or (row or {}).get("rmu")): row
                for row in rows
                if clean((row or {}).get("review_key") or (row or {}).get("rmu"))
            }
            self._comparison_entry_cache = {
                clean(((entry or {}).get("data") or {}).get("review_key") or ((entry or {}).get("data") or {}).get("rmu")): entry
                for entry in shown
                if clean(((entry or {}).get("data") or {}).get("review_key") or ((entry or {}).get("data") or {}).get("rmu"))
            }
            self._comparison_dataset_ready = False
            mode = clean(payload.get("mode")) or "equipment_review"
            self.comparison_table.setRowCount(len(shown))
            if hasattr(self, "comparison_locator"):
                self.comparison_locator.setRowCount(len(shown))
            self.comparison_table.setUpdatesEnabled(False)
            if hasattr(self, "comparison_locator"):
                self.comparison_locator.setUpdatesEnabled(False)

            self._comparison_render_context = {
                "mode": mode,
                "profile": clean(payload.get("profile")) or profile,
                "generation": generation,
                "next_row": 0,
                "shown": shown,
                "rows": rows,
                "review_map": review_map,
                "all_resolutions": all_resolutions,
                "columns": list(columns),
                "captured_selection": captured_selection,
                "summary_text": clean(payload.get("summary_text")),
                "progress_text": clean(payload.get("progress_text")),
            }
            self._update_busy_operation(
                "rmu-render",
                detail=(f"Loading Equipment Data Review... 0 / {len(shown)} rows. Please wait." if shown else "Loading Equipment Data Review... Please wait."),
                progress_value=None,
            )
            QTimer.singleShot(0, lambda g=generation: self._render_comparison_batch(g))

        def failed(details: str):
            self._comparison_render_context = None
            self._set_comparison_loading(False)
            self._hide_busy_operation("rmu-show-all")
            last_line = next((line for line in reversed(details.strip().splitlines()) if line.strip()), details)
            self.comparison_summary.setText(ui_tr(f"Equipment Data Review load failed · {last_line}", self.ui_language))
            self.statusBar().showMessage(ui_tr(f"Equipment Data Review load failed · {last_line}", self.ui_language), 8000)

        started = self._start_process_background_task(
            "rmu-render-prepare",
            "Loading Equipment Data Review",
            "rmu-render-prepare",
            (project_folder, term, str(search_field), review_filter, analysis_filter, columns, profile),
            success,
            on_error=failed,
        )
        if not started:
            self._comparison_refresh_pending = True

    def _render_comparison_batch(self, generation: int) -> None:
        """Paint a bounded group of RMU rows, then yield back to Qt."""
        ctx = self._comparison_render_context
        if not ctx or generation != self._comparison_render_generation or ctx.get("generation") != generation:
            return
        if not hasattr(self, "stack") or self.stack.currentIndex() != 2:
            self._dirty_pages.add(2)
            self._cancel_comparison_render()
            return

        shown = ctx["shown"]
        columns = ctx["columns"]
        mode = clean(ctx.get("mode")) or "rmu"
        start = int(ctx.get("next_row", 0))
        total = len(shown)
        end = min(total, start + max(1, int(self._comparison_render_batch_size)))

        if mode == "equipment_sources_legacy":
            for r in range(start, end):
                entry = shown[r]
                data = entry.get("data") or {}
                # Customer-facing equipment review is intentionally neutral:
                # extractor quality/traceability remains internal and must not
                # tint rows or compete visually with formal review states.
                self.comparison_table.setRowHeight(r, 32)
                for c, (key, _label, _width) in enumerate(columns):
                    value = clean(data.get(key, ""))
                    item = QTableWidgetItem(value)
                    item.setBackground(QColor("#FFFFFF"))
                    if key == "equipment_source_count":
                        item.setTextAlignment(Qt.AlignCenter)
                        item.setToolTip(clean(data.get("equipment_source_presence_detail")) or value)
                        try:
                            present_text, total_text = value.split("/", 1)
                            present_count = int(present_text)
                            total_count = max(1, int(total_text))
                        except Exception:
                            present_count, total_count = 0, 1
                        if present_count >= total_count:
                            item.setBackground(QColor("#EAF7F0"))
                        elif present_count * 2 >= total_count:
                            item.setBackground(QColor("#FFF8D8"))
                        else:
                            item.setBackground(QColor("#FDECEC"))
                    elif key == "equipment_missing_sources":
                        item.setToolTip(clean(data.get("equipment_source_presence_detail")) or value or "All configured sources contain this key.")
                    else:
                        item.setToolTip(value)
                    if key in {"no", "rmu", "equipment_device_type", "equipment_source_count"}:
                        font = item.font(); font.setBold(True); item.setFont(font)
                    self.comparison_table.setItem(r, c, item)

            ctx["next_row"] = end
            self._update_busy_operation(
                "rmu-render",
                detail=(f"Loading Equipment Data Review... {end} / {total} rows. Please wait." if total else "Loading Equipment Data Review... Please wait."),
                progress_value=(int(round(end * 100 / total)) if total else None),
            )
            if end < total:
                QTimer.singleShot(0, lambda g=generation: self._render_comparison_batch(g))
                return
            self._finish_comparison_render(generation)
            return

        review_map = ctx["review_map"]
        all_resolutions = ctx["all_resolutions"]
        analysis_keys = {
            key for key, _label, _width in columns
            if key.startswith("analysis__") or key in {"analysis_name", "analysis_feeder", "analysis_smart", "analysis_type", "analysis_ip"}
        }
        neutral_review_keys = analysis_keys | {"remarks", "comments"}

        for r in range(start, end):
            entry = shown[r]
            data = entry["data"]
            tag = entry["review_status"]
            state = entry["state"]
            resolution_summary = entry["resolution_summary"]
            manual_review_comment = entry["manual_review_comment"]
            resolution_display = entry["resolution_display"]
            row_fill = self._analysis_row_fill(data)
            rmu = clean(data.get("rmu"))
            review_key = clean(data.get("review_key") or rmu)

            if state.issue_count > 0 and resolution_summary:
                self.comparison_table.setRowHeight(r, min(104, 48 + 18 * max(0, min(state.issue_count, 3) - 1)))
            # Normal rows already inherit the 32 px default section size; avoid
            # one resize operation (and mirrored resize signal) per business row.

            saved_resolution = all_resolutions.get(review_key, {}) if isinstance(all_resolutions, dict) else {}
            for c, (key, _label, _width) in enumerate(columns):
                value = resolution_display if key == "comments" else clean(data.get(key, ""))
                item = QTableWidgetItem(value)
                if key == "rmu":
                    item.setData(Qt.UserRole, review_key)
                item.setBackground(QColor("#FFFFFF") if key in neutral_review_keys else row_fill)
                if key in analysis_keys:
                    detail = clean(data.get(f"{key}__detail", "") or data.get(f"{key}_detail", ""))
                    item.setToolTip(detail or value)
                    analysis_fill = self._analysis_cell_fill(key, value)
                    if analysis_fill:
                        item.setBackground(analysis_fill)
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    if key == "comments":
                        if state.issue_count > 0:
                            lines = []
                            field_order = [clean(value).upper() for value in (data.get("analysis_field_order") or []) if clean(value)] or ["NAME", "FEEDER", "SMART", "TYPE", "IP"]
                            for field in field_order:
                                record = saved_resolution.get(field) or {}
                                if clean(record.get("decision_type")):
                                    lines.append(resolution_display_text(record))
                            tooltip = "\n\n".join(lines) or "No Resolution decisions recorded."
                            tooltip += "\n\nDouble-click to resolve every active FALSE Analysis field."
                        elif state.has_result:
                            tooltip = (
                                (manual_review_comment or "No optional manual Review comment recorded.")
                                + "\n\nDouble-click to add a new optional human Review comment. "
                                  "This does not change the automatic Pass result."
                            )
                        else:
                            tooltip = "Validation Required before Review/Resolution information can be recorded."
                        item.setToolTip(tooltip)
                    else:
                        # Most short source values are fully visible and do not
                        # need a duplicated tooltip string on every cell. Keep a
                        # tooltip only for values likely to be truncated.
                        if len(value) > 36 or "\n" in value:
                            item.setToolTip(value)
                if key in {"no", "rmu"}:
                    font = item.font(); font.setBold(True); item.setFont(font)
                if key == "comments" and value:
                    font = item.font(); font.setBold(True); item.setFont(font)
                if key in analysis_keys or key in {"rmu", "comments"}:
                    existing_tip = item.toolTip() or value
                    item.setToolTip((existing_tip + "\n\n" if existing_tip else "") + "Right-click any cell to set Unreviewed / Closed / Needs Action for this equipment row.")
                self.comparison_table.setItem(r, c, item)

            self._populate_comparison_locator_row(r, data, tag, review_map)

        ctx["next_row"] = end
        self._update_busy_operation(
            "rmu-render",
            detail=(
                f"Loading Equipment Data Review... {end} / {total} rows. Please wait."
                if total else "Loading Equipment Data Review... Please wait."
            ),
            progress_value=(int(round(end * 100 / total)) if total else None),
        )

        if end < total:
            QTimer.singleShot(0, lambda g=generation: self._render_comparison_batch(g))
            return
        self._finish_comparison_render(generation)

    def _finish_comparison_render(self, generation: int) -> None:
        ctx = self._comparison_render_context
        if not ctx or generation != self._comparison_render_generation or ctx.get("generation") != generation:
            return

        mode = clean(ctx.get("mode")) or "rmu"
        if mode in {"rmu", "equipment_review"}:
            self._sync_comparison_locator_geometry()
        self._apply_comparison_column_visibility()
        # v0.8.190: once all rows are available, automatically expand every
        # column that the reviewer has never manually resized.  Sampling uses
        # the full unfiltered data set, so widths stay stable while filters and
        # search terms change.
        self._auto_fit_comparison_columns(
            rows=list(ctx.get("rows") or []), shown=list(ctx.get("shown") or [])
        )
        self._restore_comparison_selection_keys(ctx.get("captured_selection") or [])
        self.comparison_table.setUpdatesEnabled(True)
        self.comparison_table.viewport().update()
        if hasattr(self, "comparison_locator"):
            self.comparison_locator.setUpdatesEnabled(True)
            if mode in {"rmu", "equipment_review"}:
                self.comparison_locator.verticalScrollBar().setValue(self.comparison_table.verticalScrollBar().value())
                self.comparison_locator.viewport().update()
        self.comparison_summary.setText(ctx.get("summary_text", ""))
        if hasattr(self, "comparison_review_progress"):
            self.comparison_review_progress.setText(ctx.get("progress_text", ""))

        shown_count = len(ctx.get("shown") or [])
        self._comparison_row_index_cache = {}
        for row_index, entry in enumerate(self._comparison_last_entries):
            data = (entry or {}).get("data") or {}
            key = clean(data.get("review_key") or data.get("rmu"))
            if key:
                self._comparison_row_index_cache[key] = row_index
        self._comparison_dataset_ready = True
        self._comparison_render_context = None
        # Apply whichever filters/search the reviewer currently selected while
        # the dataset was loading. This only toggles row visibility.
        self._apply_comparison_filters_local()
        self._set_comparison_loading(False)
        self._hide_busy_operation("rmu-show-all")
        if mode in {"rmu", "equipment_review"}:
            self._schedule_comparison_lifecycle_refresh()
        elif hasattr(self, "comparison_lifecycle_card"):
            self.comparison_lifecycle_card.setVisible(False)
        profile = self._current_equipment_profile()
        label = "all equipment" if profile == "__ALL__" else profile
        if hasattr(self, "stack") and self.stack.count() > 2:
            translate_widget_tree(self.stack.widget(2), self.ui_language)
        self.statusBar().showMessage(ui_tr(f"Equipment Data Review ready · {label} · {shown_count} row(s)", self.ui_language), 3000)

    def _select_comparison_rmu(self, rmu: str):
        """Restore a reviewed row without changing the horizontal viewport.

        The business RMU key lives in the main grid's Index/RMU column, which is
        far to the right of the Analysis/Remarks/Resolution review workspace.
        Selecting that key cell and calling ``scrollToItem`` used to make Qt
        horizontally pan to Index after every Resolution/comment save.  Locate
        the row by the key column, but keep the current left-edge visible column
        as the active cell and restore the horizontal scrollbar defensively.
        """
        if not hasattr(self, "comparison_table"):
            return
        table = self.comparison_table
        old_h = table.horizontalScrollBar().value()
        rmu_col = next((i for i, (key, _label, _width) in enumerate(self._comparison_columns()) if key == "rmu"), -1)
        if rmu_col < 0:
            return

        # Keep the active/current cell inside the user's current viewport.  This
        # lets scrollToItem adjust vertically without dragging the grid right to
        # the Index/RMU key column.
        visible_col = table.columnAt(0)
        if visible_col < 0 or table.isColumnHidden(visible_col):
            current_col = table.currentColumn()
            if current_col >= 0 and not table.isColumnHidden(current_col):
                visible_col = current_col
            else:
                visible_col = next((c for c in range(table.columnCount()) if not table.isColumnHidden(c)), 0)

        for row in range(table.rowCount()):
            key_item = table.item(row, rmu_col)
            item_key = clean(key_item.data(Qt.UserRole) if key_item else "") or clean(key_item.text() if key_item else "")
            if key_item and item_key == clean(rmu):
                active_item = table.item(row, visible_col) or key_item
                table.clear_spreadsheet_selection()
                active_item.setSelected(True)
                table.setCurrentItem(active_item)
                table.scrollToItem(active_item, QAbstractItemView.EnsureVisible)
                # Qt may perform one deferred ensure-visible pass after the
                # current index changes, so restore once synchronously and once
                # on the next event-loop turn.
                table.horizontalScrollBar().setValue(old_h)
                QTimer.singleShot(0, lambda value=old_h: table.horizontalScrollBar().setValue(value))
                break

    def refresh_changes(self):
        if not hasattr(self, "changes_table"):
            return
        changes = self.store.changes() if self.store else []
        if hasattr(self, "changes_stack"):
            self.changes_stack.setCurrentWidget(self.changes_table if changes else self.changes_empty)
        self.changes_table.setRowCount(len(changes))
        keys = ["id", "module", "record", "field", "original_value", "new_value", "reason", "modified_by", "modified_at"]
        for r, raw in enumerate(changes):
            data = present_audit_item(raw)
            for c, key in enumerate(keys):
                item = QTableWidgetItem(clean(data.get(key, "")))
                if key == "field":
                    internal = clean(data.get("internal_field"))
                    item.setToolTip(f"{item.text()}\nInternal field: {internal}" if internal else item.text())
                else:
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

    def _open_site_lifecycle_case(self, row: int, _column: int = 0) -> None:
        if not self.store or not hasattr(self, "site_lifecycle_table"):
            return
        item = self.site_lifecycle_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not data or len(data) != 2:
            return
        entity_type, entity_key = data
        IssueLifecycleDialog(self.store, entity_type, entity_key, self).exec()

    def refresh_site_history(self):
        if not hasattr(self, "site_revisions_table"):
            return

        if not self.store:
            self.site_history_site_label.setText("Site: —")
            self.site_history_revision_label.setText("Latest revision: —")
            self.site_history_issue_label.setText("Issue / Action items: 0")
            self.site_history_tracking_label.setText("Equipment Follow-up: Open 0 · Closed 0")
            self.site_history_lifecycle_label.setText("Lifecycle: Open 0 · Closed 0")
            self.site_history_audit_label.setText("Audit records: 0")
            self.site_history_report_label.setText("Sign-off PDFs: 0")
            self.site_revisions_table.setRowCount(0)
            self.site_issue_table.setRowCount(0)
            self.site_rmu_tracking_table.setRowCount(0)
            self.site_lifecycle_table.setRowCount(0)
            self.site_history_audit_table.setRowCount(0)
            self.site_reports_table.setRowCount(0)
            translate_widget_tree(self.site_history_page, self.ui_language)
            return

        site_name = (
            self.store.config.get("site_name")
            or self.store.config.get("repository_site")
            or self.store.folder.name
        )
        revisions = self.store.site_revisions()
        issues = self.store.issue_actions()
        changes = self.store.changes()
        reports = self.store.signoff_reports()
        tracking = (self.store.equipment_action_tracking() if hasattr(self.store, "equipment_action_tracking") else self.store.rmu_action_tracking())
        tracking_counts = (self.store.equipment_action_tracking_counts() if hasattr(self.store, "equipment_action_tracking_counts") else self.store.rmu_action_tracking_counts())
        lifecycle = self.store.issue_cases()
        lifecycle_counts = self.store.issue_lifecycle_counts()
        latest = revisions[0] if revisions else None

        self.site_history_site_label.setText(f"Site: {site_name}")
        self.site_history_revision_label.setText(
            f"Latest revision: {clean(latest.get('revision_name'))}" if latest else "Latest revision: —"
        )
        self.site_history_issue_label.setText(f"Issue / Action items: {len(issues)}")
        self.site_history_tracking_label.setText(
            f"Equipment Follow-up: Open {tracking_counts.get('OPEN', 0)} · Closed {tracking_counts.get('CLOSED', 0)}"
        )
        self.site_history_lifecycle_label.setText(
            f"Lifecycle: Open {lifecycle_counts.get('OPEN', 0)} · Closed {lifecycle_counts.get('CLOSED', 0)}"
        )
        self.site_history_audit_label.setText(f"Audit records: {len(changes)}")
        signed_count = sum(1 for report in reports if clean(report.get("report_status")).upper() == "SIGNED")
        self.site_history_report_label.setText(f"Sign-off PDFs: {len(reports)} · Signed: {signed_count}")

        versions_by_id = {int(v.get("id") or -1): v for v in self.store.versions()}
        self.site_revisions_table.setRowCount(len(revisions))
        for r, revision in enumerate(revisions):
            version = versions_by_id.get(int(revision.get("version_id") or -1), {})
            values = [
                revision.get("id"),
                revision.get("revision_name"),
                revision.get("description"),
                version.get("version_name") or (f"#{revision.get('version_id')}" if revision.get("version_id") else "—"),
                revision.get("created_by"),
                revision.get("created_at"),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(clean(value))
                item.setToolTip(item.text())
                self.site_revisions_table.setItem(r, c, item)

        self.site_issue_table.setRowCount(len(issues))
        for r, item_data in enumerate(issues):
            values = [
                item_data.get("id"),
                item_data.get("revision_name") or "Current",
                item_data.get("category"),
                item_data.get("equipment"),
                item_data.get("issue"),
                item_data.get("action_taken"),
                item_data.get("result"),
                item_data.get("comments"),
                item_data.get("created_by"),
                item_data.get("updated_at"),
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(clean(value))
                cell.setToolTip(cell.text())
                if c == 6:
                    status = clean(value).upper()
                    if status in {"PASS", "CLOSED"}:
                        cell.setBackground(QColor("#E8F5EE"))
                        cell.setForeground(QColor("#116A4D"))
                    elif status in {"OPEN", "NEEDS ACTION"}:
                        cell.setBackground(QColor("#FDECEC"))
                        cell.setForeground(QColor("#B42318"))
                self.site_issue_table.setItem(r, c, cell)

        self.site_lifecycle_table.setRowCount(len(lifecycle))
        for r, case in enumerate(lifecycle):
            entity_type = clean(case.get("entity_type")).upper()
            entity_key = clean(case.get("entity_key"))
            linked_row = self._comparison_row_by_rmu(entity_key) if entity_type == "RMU" else None
            display_entity_type = self._equipment_type_from_key(entity_key, linked_row or {}) if entity_type == "RMU" else entity_type
            display_equipment = self._equipment_display_name(entity_key, linked_row or {}) if entity_type == "RMU" else clean(case.get("rmu"))
            values = [
                f"#{int(case.get('case_no') or 0):03d}", display_entity_type, display_equipment,
                case.get("point_no"), case.get("signal_name"), case.get("status"), case.get("opened_at"),
                case.get("opened_by"), case.get("closed_at"), case.get("closed_by"),
                case.get("participant_count"), case.get("event_count"), case.get("last_event_at") or case.get("updated_at"),
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(clean(value)); cell.setToolTip(cell.text())
                if c == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, (clean(case.get("entity_type")), clean(case.get("entity_key"))))
                if c == 5:
                    status = clean(value).upper()
                    if status == "OPEN":
                        cell.setBackground(QColor("#FDECEC")); cell.setForeground(QColor("#B42318"))
                    elif status == "CLOSED":
                        cell.setBackground(QColor("#E8F5EE")); cell.setForeground(QColor("#116A4D"))
                    font = cell.font(); font.setBold(True); cell.setFont(font)
                self.site_lifecycle_table.setItem(r, c, cell)

        self.site_rmu_tracking_table.setRowCount(len(tracking))
        for r, data in enumerate(tracking):
            equipment_key = clean(data.get("equipment_key") or data.get("rmu"))
            row_data = self._comparison_row_by_rmu(equipment_key) or {}
            display_name = self._equipment_display_name(equipment_key, row_data)
            equipment_type = self._equipment_type_from_key(equipment_key, row_data)
            values = [
                display_name, equipment_type, data.get("tracking_status"),
                data.get("first_need_action_at"), data.get("last_need_action_at"), data.get("closed_at"),
                data.get("open_count"), data.get("opened_by"), data.get("closed_by"), data.get("last_reason"),
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(clean(value))
                cell.setToolTip(cell.text())
                if c == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, equipment_key)
                if c == 2:
                    status = clean(data.get("tracking_status")).upper()
                    if status == "OPEN":
                        cell.setBackground(QColor("#FDECEC"))
                        cell.setForeground(QColor("#B42318"))
                    elif status == "CLOSED":
                        cell.setBackground(QColor("#E8F5EE"))
                        cell.setForeground(QColor("#116A4D"))
                    font = cell.font(); font.setBold(True); cell.setFont(font)
                self.site_rmu_tracking_table.setItem(r, c, cell)

        self.site_history_audit_table.setRowCount(len(changes))
        audit_keys = ["id", "module", "record", "field", "original_value", "new_value", "reason", "modified_by", "modified_at"]
        for r, raw in enumerate(changes):
            data = present_audit_item(raw)
            for c, key in enumerate(audit_keys):
                cell = QTableWidgetItem(clean(data.get(key, "")))
                if key == "field":
                    internal = clean(data.get("internal_field"))
                    cell.setToolTip(f"{cell.text()}\nInternal field: {internal}" if internal else cell.text())
                else:
                    cell.setToolTip(cell.text())
                self.site_history_audit_table.setItem(r, c, cell)

        self.site_reports_table.setRowCount(len(reports))
        for r, report in enumerate(reports):
            values = [
                report.get("id"),
                report.get("revision_name") or "Current",
                report.get("report_status"),
                report.get("file_name"),
                report.get("created_by"),
                report.get("created_at"),
                report.get("signed_file_name"),
                report.get("signed_at"),
            ]
            for c, value in enumerate(values):
                cell = QTableWidgetItem(clean(value))
                if c == 3:
                    cell.setToolTip(clean(report.get("file_path")))
                elif c == 6:
                    cell.setToolTip(clean(report.get("signed_file_path")))
                else:
                    cell.setToolTip(cell.text())
                if c == 2:
                    status = clean(value).upper()
                    if status == "SIGNED":
                        cell.setBackground(QColor("#E8F5EE"))
                        cell.setForeground(QColor("#116A4D"))
                    else:
                        cell.setBackground(QColor("#EEF4F8"))
                        cell.setForeground(QColor("#3B5B73"))
                self.site_reports_table.setItem(r, c, cell)

        # Site-history counters are refreshed after the initial page-wide i18n
        # pass. Re-translate the page here so Chinese mode never regresses to
        # newly assigned English runtime summaries.
        translate_widget_tree(self.site_history_page, self.ui_language)

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
        return self.store.sync_db_smart_review_fingerprints(
                fingerprints, modified_by="SYSTEM",
                aliases=signal_review_alias_map(report),
                metadata={item.row_key: signal_review_metadata(report, item) for item in report.rows},
            )

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
        rmu_reviewed: int = 0, rmu_review_total: int = 0,
        signal_reviewed: int = 0, signal_review_total: int = 0,
    ) -> None:
        """Refresh delivery stage using business-record Human Review progress.

        Project Overview deliberately counts review *objects*, not low-level
        Resolution decisions: one affected equipment row is one equipment review object, and one
        mismatched signal is one Signal review object.  A multi-issue RMU counts
        as reviewed only after every active FALSE field has a Resolution decision.
        Per-field decision counts stay inside RMU Data Review where they are useful.
        Pass RMUs and matched signals do not inflate required Human Review progress.
        STANDARD-driven signal rows are TRUE/FALSE while ZENON extras are
        tracked separately and do not create a validation coverage-gap state.
        """
        processed = min(review_total, max(0, reviewed))
        unreviewed = max(0, review_total - processed)
        review_pct = int(round((processed / review_total * 100.0) if review_total else 100.0))
        review_complete = unreviewed == 0 and needs_action == 0
        validation_coverage_complete = validation_complete

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
            self.project_state_label.setText(ui_tr(f"STATUS · {display_state}", self.ui_language))
            if state in {"ACTION REQUIRED", "SOURCES INCOMPLETE", "VALIDATION INCOMPLETE"}:
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
            "done" if validation_coverage_complete else ("current" if sources_complete else "pending"),
        )
        self._set_workflow_badge(
            self.workflow_step_labels["review"],
            "done" if review_complete and validation_coverage_complete else ("current" if validation_complete and review_total else "pending"),
        )
        self._set_workflow_badge(
            self.workflow_step_labels["report"],
            "done" if (report_exported and review_complete and validation_coverage_complete) else ("current" if review_complete and validation_coverage_complete else "pending"),
        )

        if self.ui_language == LANG_ZH_CN:
            module_review = (
                f"人工审核 · 设备 {rmu_reviewed}/{rmu_review_total} · "
                f"信号 {signal_reviewed}/{signal_review_total}"
            )
            if not sources_complete:
                detail = "请完成当前站点已配置的设备审核数据源以及信号映射所需数据源。"
            elif not validation_complete:
                detail = "数据源已就绪。请运行校验以计算设备审核和信号映射结果。"
            elif needs_action:
                detail = f"{module_review} · {review_pct}% · {needs_action} 项需处理"
            elif review_complete and report_exported:
                detail = f"{module_review} · 审核已完成 · 当前迁移报告已是最新导出版本。"
            elif review_complete:
                detail = f"{module_review} · 审核已完成 · 迁移报告可以导出。"
            else:
                detail = f"{module_review} · {review_pct}% · 剩余 {unreviewed} 个审核对象"
        else:
            module_review = (
                f"Human Review · Equipment {rmu_reviewed}/{rmu_review_total} · "
                f"Signal {signal_reviewed}/{signal_review_total}"
            )
            if not sources_complete:
                detail = "Complete the configured Equipment Data Review sources and required Signal Mapping sources."
            elif not validation_complete:
                detail = "Sources are ready. Run Validation to calculate Equipment Data Review and Signal Mapping results."
            elif needs_action:
                detail = f"{module_review} · {review_pct}% · {needs_action} Needs Action"
            elif review_complete and report_exported:
                detail = f"{module_review} · Review complete · current Migration Report export is up to date."
            elif review_complete:
                detail = f"{module_review} · Review complete · Migration Report is ready for export."
            else:
                detail = f"{module_review} · {review_pct}% · {unreviewed} review object(s) remaining"
        self.workflow_detail.setText(detail)

    def refresh_dashboard(self):
        if not hasattr(self, "metric_rmu_total"):
            return
        self._refresh_setup_guidance()

        rmu_cards = (
            self.metric_rmu_total, self.metric_rmu_pass, self.metric_rmu_issues,
            self.metric_rmu_reviewed, self.metric_rmu_needs_action,
        )
        signal_cards = (
            self.metric_signal_total, self.metric_signal_matched, self.metric_signal_mismatched,
            self.metric_signal_zenon_extra, self.metric_signal_needs_action,
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
            self.dash_project_path.setText(str(project_data_root()))
            self.dash_last_version.setText("Latest version: —")
            self.dashboard_sources.clear()
            if hasattr(self, "dashboard_equipment_type_table"):
                self.dashboard_equipment_type_table.setRowCount(0)
            if hasattr(self, "dashboard_rmu_issues_button"):
                self.dashboard_rmu_issues_button.setText("Run Validation First")
                self.dashboard_rmu_issues_button.setEnabled(False)
            if hasattr(self, "dashboard_signal_mismatch_button"):
                self.dashboard_signal_mismatch_button.setText("Run Validation First")
                self.dashboard_signal_mismatch_button.setEnabled(False)
            self.project_title.setText("No site selected")
            self.project_subtitle.setText(ui_tr("Migration Report · Select a site to validate and review migration data", self.ui_language))
            self._update_delivery_workflow(
                sources_complete=False, validation_complete=False, review_total=0,
                reviewed=0, needs_action=0, report_exported=False,
                rmu_reviewed=0, rmu_review_total=0, signal_reviewed=0, signal_review_total=0,
            )
            return

        # RMU module: automated Analysis and human Review are independent.
        rows = self.store.rows()
        rmu_states = [analysis_review_state(row) for row in rows]
        rmu_pass = sum(state.is_pass for state in rmu_states)
        rmu_issues = sum(state.issue_count > 0 for state in rmu_states)
        rmu_no_analysis = sum(not state.has_result for state in rmu_states)
        # Project Overview counts affected RMUs, not their individual FALSE
        # fields.  The per-field Resolution decision count remains visible only
        # inside RMU Data Review.  One issue RMU is considered reviewed after
        # every active FALSE field has a saved decision (including Needs Action).
        rmu_total = len(rows)
        all_resolutions = self.store.rmu_resolution_map()
        rmu_review_total = rmu_issues
        rmu_reviewed = 0
        rmu_closed = 0
        rmu_required_needs = 0
        rmu_review_map = self.store.rmu_review_map()
        for row, state in zip(rows, rmu_states):
            if state.issue_count <= 0:
                continue
            rmu = clean(row.get("rmu"))
            review_record = rmu_review_map.get(rmu, {})
            visible_status = rmu_review_display_status(row, review_record)
            saved = all_resolutions.get(rmu, {}) if isinstance(all_resolutions, dict) else {}
            decisions = [clean((saved.get(field) or {}).get("decision_type")).upper() for field in state.false_fields]
            if visible_status in {"CLOSED", "NEEDS ACTION"}:
                rmu_reviewed += 1
            if visible_status == "CLOSED":
                rmu_closed += 1
            if visible_status == "NEEDS ACTION" or any(decision == "NEEDS_ACTION" for decision in decisions):
                rmu_required_needs += 1

        # Optional manual statuses on non-exception rows do not inflate the
        # required RMU denominator. Needs Action remains a project blocker.
        rmu_optional_needs = sum(
            1
            for row, state in zip(rows, rmu_states)
            if state.issue_count <= 0
            and (normalize_review_status(rmu_review_map.get(clean(row.get("rmu")), {}).get("review_status")) == "NEEDS ACTION")
        )
        rmu_needs = rmu_required_needs + rmu_optional_needs
        # Equipment Data Review uses one durable lifecycle register for every
        # equipment class. Historical DB/table names remain for compatibility,
        # but dashboard follow-up counts include every equipment Needs Action.
        equipment_tracking_rows = (
            self.store.equipment_action_tracking()
            if hasattr(self.store, "equipment_action_tracking")
            else self.store.rmu_action_tracking()
        )
        rmu_followup_open = sum(clean(item.get("tracking_status")).upper() == "OPEN" for item in equipment_tracking_rows)
        rmu_followup_closed = sum(clean(item.get("tracking_status")).upper() == "CLOSED" for item in equipment_tracking_rows)
        rmu_unreviewed = max(0, rmu_review_total - rmu_reviewed)
        rmu_review_pct = int(round((rmu_reviewed / rmu_review_total * 100.0) if rmu_review_total else 100.0))

        self.metric_rmu_total.set_value(rmu_total)
        self.metric_rmu_pass.set_value(rmu_pass)
        self.metric_rmu_issues.set_value(rmu_issues)
        self.metric_rmu_reviewed.set_value(f"{rmu_reviewed} / {rmu_review_total}")
        self.metric_rmu_needs_action.set_value(rmu_followup_open)
        self.dashboard_rmu_review_progress.setValue(rmu_review_pct)
        self.dashboard_rmu_review_progress.setFormat(f"{rmu_review_pct}%")
        self.dashboard_rmu_review_summary.setText(
            f"Equipment Review: {rmu_reviewed} / {rmu_review_total} · {rmu_review_pct}% · "
            f"Remaining {rmu_unreviewed} · Closed {rmu_closed} · Current Needs Action {rmu_needs} · "
            f"Follow-up Open {rmu_followup_open} / Closed {rmu_followup_closed}"
        )

        issue_counts = Counter(field for state in rmu_states for field in state.false_fields)
        issue_parts = [
            f"{name} {issue_counts[name]}"
            for name in ("NAME", "FEEDER", "SMART", "TYPE", "IP")
            if issue_counts[name]
        ]
        if rmu_no_analysis:
            issue_parts.append(f"NO ANALYSIS {rmu_no_analysis}")
        self.dashboard_rmu_issue_summary.setText(
            "Affected equipment by field: " + (" · ".join(issue_parts) if issue_parts else "None")
        )
        if hasattr(self, "dashboard_rmu_issues_button"):
            if not rmu_total:
                self.dashboard_rmu_issues_button.setText("Run Validation First")
                self.dashboard_rmu_issues_button.setEnabled(False)
                self.dashboard_rmu_issues_button.setToolTip("Run Validation before reviewing RMU issues.")
            elif rmu_issues:
                self.dashboard_rmu_issues_button.setText(ui_tr(f"Review Equipment Issues ({rmu_issues})", self.ui_language))
                self.dashboard_rmu_issues_button.setEnabled(True)
                self.dashboard_rmu_issues_button.setToolTip("Open Equipment Data Review filtered to ANY MISMATCH.")
            else:
                self.dashboard_rmu_issues_button.setText("No Equipment Issues")
                self.dashboard_rmu_issues_button.setEnabled(False)
                self.dashboard_rmu_issues_button.setToolTip("No equipment Analysis issues were found. Use the left navigation to open Equipment Data Review.")

        # Dynamic all-equipment review summary. Existing RMU keys remain plain
        # RMU names; non-RMU equipment uses EQ::<TYPE>::<NAME>, so historical
        # RMU comments/status/lifecycle survive upgrades unchanged.
        equipment_review_total_all = rmu_review_total
        equipment_reviewed_all = rmu_reviewed
        equipment_needs_all = rmu_needs
        try:
            equipment_rows, _equipment_source_summary = build_equipment_source_view(self.store, "__ALL__")
        except Exception:
            equipment_rows = []
        if hasattr(self, "dashboard_equipment_type_table"):
            by_type = {}
            for data in equipment_rows:
                device_type = clean(data.get("equipment_device_type")).upper() or "UNCLASSIFIED"
                bucket = by_type.setdefault(device_type, {
                    "total": 0, "pass": 0, "issues": 0, "unreviewed": 0,
                    "closed": 0, "needs": 0, "required": 0, "reviewed_required": 0,
                })
                bucket["total"] += 1
                state = analysis_review_state(data)
                if state.is_pass:
                    bucket["pass"] += 1
                if state.issue_count > 0:
                    bucket["issues"] += 1
                    bucket["required"] += 1
                review_key = clean(data.get("review_key") or data.get("rmu"))
                status = rmu_review_display_status(data, rmu_review_map.get(review_key, {}))
                if status == "UNREVIEWED":
                    bucket["unreviewed"] += 1
                elif status == "CLOSED":
                    bucket["closed"] += 1
                elif status == "NEEDS ACTION":
                    bucket["needs"] += 1
                if state.issue_count > 0 and status in {"CLOSED", "NEEDS ACTION"}:
                    bucket["reviewed_required"] += 1

            # Project workflow adds only non-RMU required review objects here;
            # RMU was already counted above using the legacy-preserving keys.
            for dtype, bucket in by_type.items():
                if dtype == "RMU":
                    continue
                equipment_review_total_all += int(bucket["required"])
                equipment_reviewed_all += int(bucket["reviewed_required"])
                equipment_needs_all += int(bucket["needs"])

            ordered = sorted(by_type.items(), key=lambda item: (-int(item[1]["total"]), item[0]))
            table = self.dashboard_equipment_type_table
            table.setRowCount(len(ordered))
            for row_index, (dtype, bucket) in enumerate(ordered):
                required = int(bucket["required"])
                reviewed_required = int(bucket["reviewed_required"])
                pct = int(round((reviewed_required / required * 100.0) if required else 100.0))
                values = [
                    dtype, bucket["total"], bucket["pass"], bucket["issues"],
                    bucket["unreviewed"], bucket["closed"], bucket["needs"], f"{reviewed_required}/{required} · {pct}%",
                ]
                for column_index, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if column_index == 0:
                        font = item.font(); font.setBold(True); item.setFont(font)
                    if column_index in {1, 2, 3, 4, 5, 6, 7}:
                        item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row_index, column_index, item)
                table.setRowHeight(row_index, 32)

            equipment_issue_total = sum(int(bucket["issues"]) for bucket in by_type.values())
            if hasattr(self, "dashboard_rmu_issues_button"):
                if not equipment_rows:
                    self.dashboard_rmu_issues_button.setText(ui_tr("Run Validation First", self.ui_language))
                    self.dashboard_rmu_issues_button.setEnabled(False)
                elif equipment_issue_total:
                    self.dashboard_rmu_issues_button.setText(
                        f"{ui_tr('Review Equipment Issues', self.ui_language)} ({equipment_issue_total})"
                    )
                    self.dashboard_rmu_issues_button.setEnabled(True)
                    self.dashboard_rmu_issues_button.setToolTip(
                        ui_tr("Open Equipment Data Review and show all equipment with automatic Analysis issues.", self.ui_language)
                    )
                else:
                    self.dashboard_rmu_issues_button.setText(ui_tr("No Equipment Issues", self.ui_language))
                    self.dashboard_rmu_issues_button.setEnabled(False)

        # Signal Mapping dashboard is intentionally cache-only.  Startup and
        # ordinary site switching must never open IOA/ADMS-SLD/STANDARD merely
        # to render Overview.  Run Validation and the Signal Mapping page are
        # the explicit parsing boundaries; until then we reuse the last persisted
        # validation summary plus any already-loaded in-memory report.
        signal_report = self.db_smart_report
        persisted_signal_summary = dict(self.store.config.get("signal_validation_summary", {}) or {})

        signal_total = signal_matched = signal_mismatched = signal_zenon_extra = 0
        signal_reviewed = signal_needs = signal_unreviewed = signal_review_total = 0
        if signal_report is None:
            signal_total = int(persisted_signal_summary.get("total") or 0)
            signal_matched = int(persisted_signal_summary.get("matched") or 0)
            signal_mismatched = int(persisted_signal_summary.get("mismatched") or 0)
            signal_zenon_extra = int(persisted_signal_summary.get("zenon_extra") or 0)
            saved_signal_reviews = self.store.db_smart_review_map()
            current_site_name = clean(self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name)
            signal_needs = sum(
                normalize_review_status((record or {}).get("review_status")) == "NEEDS ACTION"
                and (not clean((record or {}).get("site_name")) or clean((record or {}).get("site_name")).casefold() == current_site_name.casefold())
                for record in saved_signal_reviews.values()
            )
            signal_closed = sum(
                normalize_review_status((record or {}).get("review_status")) == "CLOSED"
                for record in saved_signal_reviews.values()
            )
            signal_review_total = signal_mismatched
            signal_reviewed = min(signal_closed, signal_review_total)
            signal_processed = min(signal_review_total, signal_closed + signal_needs)
            signal_unreviewed = max(0, signal_review_total - signal_processed)
            signal_review_pct = int(round((signal_processed / signal_review_total * 100.0) if signal_review_total else 100.0))
            rate = (signal_matched / signal_total * 100.0) if signal_total else 0.0
            self.metric_signal_total.set_value(signal_total)
            self.metric_signal_matched.set_value(signal_matched)
            self.metric_signal_mismatched.set_value(signal_mismatched)
            self.metric_signal_zenon_extra.set_value(signal_zenon_extra)
            self.metric_signal_needs_action.set_value(signal_needs)
            self.dashboard_signal_review_progress.setValue(signal_review_pct)
            self.dashboard_signal_review_progress.setFormat(f"{signal_review_pct}%")
            if signal_total:
                self.dashboard_signal_summary.setText(
                    f"ADMS Points {signal_total} · Matched {signal_matched} · Match rate {rate:.2f}% · ZENON Extra {signal_zenon_extra}"
                )
                self.dashboard_signal_review_summary.setText(
                    f"Signal Review: {signal_processed} / {signal_review_total} · {signal_review_pct}% · Remaining {signal_unreviewed} · Needs Action {signal_needs}"
                )
                if hasattr(self, "dashboard_signal_mismatch_button"):
                    if signal_mismatched:
                        self.dashboard_signal_mismatch_button.setText(ui_tr(f"Review Signal Mismatches ({signal_mismatched})", self.ui_language))
                        self.dashboard_signal_mismatch_button.setEnabled(True)
                        self.dashboard_signal_mismatch_button.setToolTip("Open Signal Mapping Review. The detailed table is loaded only when that module is opened.")
                    else:
                        self.dashboard_signal_mismatch_button.setText("No Signal Mismatches")
                        self.dashboard_signal_mismatch_button.setEnabled(False)
            else:
                for card in signal_cards:
                    card.set_value("0")
                self.dashboard_signal_summary.setText("No cached Signal Mapping validation · Run Validation")
                self.dashboard_signal_review_summary.setText("Review progress: 0 / 0 · 0%")
                self.dashboard_signal_review_progress.setValue(0)
                if hasattr(self, "dashboard_signal_mismatch_button"):
                    self.dashboard_signal_mismatch_button.setText("Run Validation First")
                    self.dashboard_signal_mismatch_button.setEnabled(False)
                    self.dashboard_signal_mismatch_button.setToolTip("Run Validation to calculate Signal Mapping results.")
        else:
            self._sync_signal_review_fingerprints(signal_report)
            value_index = {key: i for i, (key, _label, _width) in enumerate(signal_report.columns)}
            adms_indexes = [value_index.get(key) for key in ("adms_gss_fid", "adms_signal_name", "adms_dot_no")]
            signal_total = sum(
                any(i is not None and i < len(row.values) and clean(row.values[i]) for i in adms_indexes)
                for row in signal_report.rows
            )
            if signal_report.analysis_column is not None:
                for row in signal_report.rows:
                    result = clean(row.values[signal_report.analysis_column]).upper()
                    signal_matched += result == "TRUE"
                    signal_mismatched += result == "FALSE"
            signal_zenon_extra = sum(signal_row_is_zenon_only(row) for row in signal_report.rows)
            signal_review_map = self.store.db_smart_review_map()
            mismatch_keys = {
                row.row_key for row in signal_report.rows
                if signal_report.analysis_column is not None
                and clean(row.values[signal_report.analysis_column]).upper() == "FALSE"
            }
            signal_review_total = len(mismatch_keys)
            rows_by_key = {row.row_key: row for row in signal_report.rows}
            visible_by_key = {}
            for key, row in rows_by_key.items():
                review = signal_review_map.get(key, {})
                result = clean(row.values[signal_report.analysis_column]).upper() if signal_report.analysis_column is not None else ""
                visible_by_key[key] = signal_review_display_status(
                    result, review.get("review_status"),
                    explicit=review_record_is_explicit(review),
                    zenon_only=signal_row_is_zenon_only(row),
                )
            signal_review_counts = Counter(visible_by_key.get(key, "UNREVIEWED") for key in mismatch_keys)
            signal_closed = signal_review_counts["CLOSED"]
            signal_reviewed = signal_closed
            # Required Review progress counts current mismatches only. The Needs
            # Action metric/report count is the site's full persistent open set
            # at this moment, including older unresolved signal actions.
            current_site_name = clean(self.store.config.get("site_name") or self.store.config.get("repository_site") or self.store.folder.name)
            signal_needs = sum(
                normalize_review_status((record or {}).get("review_status")) == "NEEDS ACTION"
                and (not clean((record or {}).get("site_name")) or clean((record or {}).get("site_name")).casefold() == current_site_name.casefold())
                for record in signal_review_map.values()
            )
            signal_processed = signal_closed + signal_review_counts["NEEDS ACTION"]
            signal_unreviewed = max(0, signal_review_total - signal_processed)
            signal_review_pct = int(round((signal_processed / signal_review_total * 100.0) if signal_review_total else 100.0))
            rate = (signal_matched / signal_total * 100.0) if signal_total else 0.0

            self.metric_signal_total.set_value(signal_total)
            self.metric_signal_matched.set_value(signal_matched)
            self.metric_signal_mismatched.set_value(signal_mismatched)
            self.metric_signal_zenon_extra.set_value(signal_zenon_extra)
            self.metric_signal_needs_action.set_value(signal_needs)
            self.dashboard_signal_review_progress.setValue(signal_review_pct)
            self.dashboard_signal_review_progress.setFormat(f"{signal_review_pct}%")
            self.dashboard_signal_review_summary.setText(
                f"Signal Review: {signal_processed} / {signal_review_total} mismatches · {signal_review_pct}% · "
                f"Remaining {signal_unreviewed} · Closed {signal_closed} · Needs Action {signal_needs}"
            )
            self.dashboard_signal_summary.setText(
                f"ADMS Points {signal_total} · Matched {signal_matched} · Match rate {rate:.2f}% · ZENON Extra {signal_zenon_extra}"
            )
            if hasattr(self, "dashboard_signal_mismatch_button"):
                if signal_mismatched:
                    self.dashboard_signal_mismatch_button.setText(ui_tr(f"Review Signal Mismatches ({signal_mismatched})", self.ui_language))
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
        if self.ui_language == LANG_ZH_CN:
            self.dash_project_path.setText(
                (f"数据源仓库：{repository_path}\n" if repository_path else "") + f"项目数据：{self.store.folder}"
            )
        else:
            self.dash_project_path.setText(
                (f"Repository: {repository_path}\n" if repository_path else "") + f"Project Data: {self.store.folder}"
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
            selected_path = (
                selected_repository_source_path(site_for_sources, self.store, key)
                if site_for_sources is not None else None
            )
            live_path = site_for_sources.sources.get(key) if site_for_sources else None
            manual_path = self.store.source_path(key) if self.store.is_manual_source_override(key) else None
            selection = self.store.source_file_selection(key)
            if selected_path is not None and selection:
                path = selected_path
                origin = ui_tr("Selected Version", self.ui_language)
            elif manual_path:
                path = manual_path
                origin = ui_tr("Manual Import", self.ui_language)
            elif selected_path is not None:
                path = selected_path
                origin = ui_tr("Site Repository · Latest Version", self.ui_language)
            elif live_path:
                path = Path(live_path)
                origin = ui_tr("Site Repository", self.ui_language)
            else:
                path = self.store.source_path(key)
                origin = ui_tr("Workspace snapshot", self.ui_language) if path else ""
            item = QListWidgetItem(
                f"{ui_tr('READY' if path else 'MISSING', self.ui_language)}   {ui_tr(label, self.ui_language)}\n"
                f"{path.name if path else ui_tr('Not available', self.ui_language)}{f' · {origin}' if origin else ''}"
            )
            item.setIcon(app_icon("database"))
            item.setForeground(QColor(COLORS["success"] if path else COLORS["muted"]))
            self.dashboard_sources.addItem(item)
        standard_path = standard_reference_path()
        standard_item = QListWidgetItem(
            f"{ui_tr('READY' if standard_path.exists() else 'MISSING', self.ui_language)}   IOA STANDARD ({standard_reference_origin()})\n"
            f"{standard_path.name if standard_path.exists() else ui_tr('Reference not available', self.ui_language)}"
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
        effective_source_keys = set(repository_site.sources) if repository_site else set()
        effective_source_keys.update(
            key for key in self.store.manual_source_overrides()
            if self.store.source_path(key) is not None
        )
        # Existing workspace snapshots are also valid inputs when a repository
        # file is temporarily unavailable; explicit manual imports are shown
        # separately above but use the same validation engine.
        effective_source_keys.update(
            key for key, _meta in SOURCE_TYPES.items()
            if self.store.source_path(key) is not None
        )
        # Equipment Data Review is fully configurable and has no fixed source-count
        # requirement.  When a configurable contract exists, readiness depends on
        # the enabled configured sources + comparison rules, not on the historical
        # six repository roles.  Legacy projects keep their old fallback until they
        # explicitly save a configurable contract.
        comparison_config = get_equipment_comparison_config(self.store, bootstrap=False)
        if comparison_config.get("sources"):
            comparison_status = configurable_comparison_status(self.store, comparison_config)
            enabled_status = [
                item for item in comparison_status
                if bool((item.get("source") or {}).get("enabled", True))
            ]
            equipment_sources_ready = (
                bool(enabled_status)
                and bool(comparison_config.get("comparisons"))
                and all(clean(item.get("status")).upper() == "READY" for item in enabled_status)
            )
        else:
            legacy_equipment_required = {"se_list", "zenon_db", "zenon_sld", "adms_db", "adms_sld"}
            equipment_sources_ready = legacy_equipment_required.issubset(effective_source_keys)

        ioa_path = resolve_configurable_signal_assignment(self.store, "ioa") or self.store.source_path("ioa")
        signal_adms_path = resolve_configurable_signal_assignment(self.store, "adms_sld") or self.store.source_path("adms_sld")
        signal_sources_ready = bool(
            ioa_path and Path(ioa_path).exists()
            and signal_adms_path and Path(signal_adms_path).exists()
            and standard_path.exists()
        )
        sources_complete = equipment_sources_ready and signal_sources_ready
        validation_complete = (
            bool(rows)
            and (signal_report is not None or int(persisted_signal_summary.get("total") or 0) > 0)
            and not bool(self.store.config.get("validation_required_after_source_import", False))
        )
        # Project-level Human Review uses business objects so Dashboard totals
        # stay intuitive: one affected equipment item + one mismatched signal.
        # Per-field decisions remain an implementation/detail view inside Equipment Data Review
        # module and are deliberately not mixed into Overview progress.
        review_total = equipment_review_total_all + signal_review_total
        signal_required_needs = signal_review_counts["NEEDS ACTION"] if signal_report is not None else signal_needs
        signal_processed_total = signal_reviewed + signal_required_needs
        reviewed_total = equipment_reviewed_all + signal_processed_total
        needs_total = equipment_needs_all + signal_needs
        latest_state_ts = 0.0
        for table_name in ("comparison", "rmu_reviews", "rmu_resolutions", "db_smart_reviews"):
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
        else:
            try:
                cached_signal_ts = clean(persisted_signal_summary.get("updated_at"))
                if cached_signal_ts:
                    latest_state_ts = max(latest_state_ts, datetime.fromisoformat(cached_signal_ts).timestamp())
            except Exception:
                pass
        report_times = []
        # v0.8.186 formal exports are Save-As anywhere, so the delivery state
        # must follow the recorded external export rather than only the legacy
        # internal reports/ directory. Keep the directory scan for backward
        # compatibility with older projects.
        recorded_export_at = clean(self.store.config.get("last_migration_report_export_at"))
        recorded_export_path = clean(self.store.config.get("last_migration_report_export_path"))
        if recorded_export_at and recorded_export_path:
            try:
                external_path = Path(recorded_export_path)
                if external_path.exists():
                    report_times.append(datetime.fromisoformat(recorded_export_at).timestamp())
            except Exception:
                pass
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
            review_total=review_total,
            reviewed=reviewed_total, needs_action=needs_total, report_exported=report_exported,
            rmu_reviewed=rmu_reviewed, rmu_review_total=rmu_review_total,
            signal_reviewed=signal_processed_total, signal_review_total=signal_review_total,
        )
        if hasattr(self, "stack") and self.stack.count() > 0:
            translate_widget_tree(self.stack.widget(0), self.ui_language)

    def refresh_export_page(self):
        if not hasattr(self, "export_project_label"):
            return
        if not self.store:
            self.export_project_label.setText("Saudi ADMS Site: —")
            self.export_readiness_label.setText("Delivery status: select a site and run validation")
            self.export_readiness_label.setStyleSheet("")
            self.export_path_label.setText("Export location: choose a path when exporting")
            if hasattr(self, "export_signoff_status_label"):
                self.export_signoff_status_label.setText("Sign-off history: —")
        else:
            self.export_project_label.setText(ui_tr(f"Saudi ADMS Site: {self.store.config.get('site_name') or self.store.config.get('repository_site') or self.store.folder.name}", self.ui_language))
            state = getattr(self, "project_delivery_state", "—")
            if state == "READY FOR EXPORT":
                self.export_readiness_label.setText("Delivery status: Ready for formal Migration Report export")
                self.export_readiness_label.setStyleSheet(f"color:{COLORS['success']};font-weight:700;")
            else:
                self.export_readiness_label.setText(
                    f"Delivery status: {state} · Export is available as a review draft; complete Human Review before formal handover."
                )
                self.export_readiness_label.setStyleSheet(f"color:{COLORS['warning']};font-weight:650;")
            self.export_path_label.setText("Export location: choose a save path for every Excel/PDF export")
            if hasattr(self, "export_signoff_status_label"):
                reports = self.store.signoff_reports()
                signed = sum(1 for item in reports if clean(item.get("report_status")).upper() == "SIGNED")
                latest_revision = self.store.latest_site_revision()
                revision_text = clean(latest_revision.get("revision_name")) if latest_revision else "Current"
                self.export_signoff_status_label.setText(
                    f"Sign-off history: {len(reports)} generated · {signed} signed · latest revision {revision_text}"
                )

        # Export readiness/path/history labels are runtime-composed after the
        # page was built, so apply the current language after every refresh.
        translate_widget_tree(self.export_page, self.ui_language)

    def closeEvent(self, event):
        if self.store:
            try:
                self.store.db.close()
            except Exception:
                pass
        super().closeEvent(event)
