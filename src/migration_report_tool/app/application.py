#!/usr/bin/env python3
"""NARI Saudi ADMS Migration Report application launcher."""
from __future__ import annotations

import ctypes
import multiprocessing
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from ..core import APP_NAME, APP_VERSION, resource_root
from ..utils.paths import bundled_standard_reference_path
from ..ui import APP_QSS, MainWindow
from ..ui.input_guards import install_selection_wheel_guard


def configure_windows_identity():
    """Give Windows a stable identity so taskbar grouping/icon caching stays consistent."""
    if os.name != "nt":
        return
    try:
        # Keep this stable across releases. A versioned AppUserModelID creates a
        # new Windows shell identity for every build and can leave taskbar icon
        # grouping/cache behavior inconsistent after an upgrade.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "NARI.SaudiADMS.MigrationReport"
        )
    except Exception:
        pass


def runtime_app_icon() -> QIcon:
    """Return a runtime-safe Qt icon. Prefer PNG; keep ICO for the EXE resource."""
    assets = resource_root() / "assets"
    # Qt's PNG path is reliable in frozen one-folder builds even when the ICO
    # image-format plugin is not available. PyInstaller still embeds logo.ico
    # into MigrationReportTool.exe for Explorer/shortcut display.
    for name in ("logo.png", "logo.ico"):
        path = assets / name
        if not path.exists():
            continue
        icon = QIcon(str(path))
        if not icon.isNull():
            return icon
    return QIcon()


def apply_native_windows_icon(window) -> None:
    """Force both native Windows window icons after the HWND has been created."""
    if os.name != "nt":
        return
    icon_path = resource_root() / "assets" / "logo.ico"
    if not icon_path.exists():
        return
    try:
        user32 = ctypes.windll.user32
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        # Explicit pointer-sized return type is important on 64-bit Windows;
        # ctypes otherwise assumes c_int and can truncate a native HICON.
        user32.LoadImageW.restype = ctypes.c_void_p
        hwnd = int(window.winId())
        small_icon = user32.LoadImageW(None, str(icon_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
        big_icon = user32.LoadImageW(None, str(icon_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
        if small_icon:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small_icon)
        if big_icon:
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big_icon)
    except Exception:
        # Qt's QIcon remains the fallback; icon setup must never block startup.
        pass


def main():
    # Required by PyInstaller/Windows when first-open RMU/Signal review work is
    # delegated to spawned child processes.  Calling this before QApplication
    # prevents a worker child from recursively launching the desktop UI.
    multiprocessing.freeze_support()

    # Build pipeline executes this mode against the packaged EXE. If PySide6
    # or application modules were not bundled, the process fails before here.
    if "--self-test" in sys.argv:
        required = [
            resource_root() / "assets" / "logo.ico",
            resource_root() / "assets" / "logo.png",
            bundled_standard_reference_path(),
            resource_root() / "icons" / "rmu.svg",
            resource_root() / "icons" / "signal.svg",
        ]
        return 0 if all(path.exists() for path in required) else 2

    configure_windows_identity()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("NARI")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    # Safety rule: wheel scrolling must never change a drop-down/spin selection.
    # Installed on QApplication so every current/future dialog is covered.
    install_selection_wheel_guard(app)

    icon = runtime_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)

    splash = None
    splash_path = resource_root() / "assets" / "splash.png"
    if splash_path.exists():
        pixmap = QPixmap(str(splash_path))
        if not pixmap.isNull():
            splash = QSplashScreen(pixmap)
            splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            splash.showMessage(
                "Loading Saudi ADMS migration workspace...",
                Qt.AlignLeft | Qt.AlignBottom,
                QColor("#D9E6F2"),
            )
            splash.show()
            app.processEvents()

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()
    # winId() is valid after show(); explicitly set WM_SETICON so the Windows
    # taskbar/Alt+Tab icon cannot fall back to the generic window glyph.
    QTimer.singleShot(0, lambda: apply_native_windows_icon(window))
    if splash:
        # The expensive repository load is deferred until after the main window
        # is visible, so keep the splash only long enough to hand off cleanly.
        QTimer.singleShot(80, lambda: splash.finish(window))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
