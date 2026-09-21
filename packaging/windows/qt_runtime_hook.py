"""Keep frozen PySide6 loads inside the packaged Qt directory on Windows."""

from __future__ import annotations

import os
import sys
from pathlib import Path


_DLL_DIRECTORY_HANDLES = []

if sys.platform.startswith("win") and getattr(sys, "frozen", False):
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    qt_directory = bundle_root / "PySide6"
    shiboken_directory = bundle_root / "shiboken6"

    if qt_directory.is_dir() or shiboken_directory.is_dir():
        # Keep the handles alive for the lifetime of the process. Windows
        # removes an AddDllDirectory entry when its handle is closed.
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            for directory in (qt_directory, shiboken_directory, bundle_root):
                if not directory.is_dir():
                    continue
                try:
                    _DLL_DIRECTORY_HANDLES.append(add_dll_directory(str(directory)))
                except OSError:
                    pass

        current_path = os.environ.get("PATH", "")
        path_entries = [
            str(directory)
            for directory in (qt_directory, shiboken_directory, bundle_root)
            if directory.is_dir()
        ]
        if current_path:
            path_entries.append(current_path)
        os.environ["PATH"] = os.pathsep.join(path_entries)
