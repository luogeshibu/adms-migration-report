#!/usr/bin/env python3
"""NARI Saudi ADMS Migration Report application launcher."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from ..core import APP_NAME, APP_VERSION, resource_root
from ..utils.paths import bundled_standard_reference_path
from ..ui import APP_QSS, MainWindow


def configure_windows_identity():
    """Give Windows a stable application identity even when started via pythonw.exe."""
    if os.name != "nt":
        return
    try:
        app_id = f"NARI.SaudiADMS.MigrationReport.{APP_VERSION}"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def main():
    # Build pipeline executes this mode against the packaged EXE. If PySide6
    # or application modules were not bundled, the process fails before here.
    if "--self-test" in sys.argv:
        required = [
            resource_root() / "assets" / "logo.ico",
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

    icon_path = resource_root() / "assets" / "logo.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

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
    window.show()
    if splash:
        QTimer.singleShot(650, lambda: splash.finish(window))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
