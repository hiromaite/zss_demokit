from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PySide6 import __file__ as PYSIDE6_FILE
from PySide6.QtCore import QCoreApplication, QLibraryInfo


def bundled_base_path() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parents[1]


def resolve_runtime_asset(relative_path: str) -> Path:
    return bundled_base_path() / relative_path


def configure_qt_runtime() -> None:
    plugins_dir: Optional[Path] = None
    qt_lib_dir: Optional[Path] = None

    try:
        plugin_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        if plugin_path:
            candidate = Path(plugin_path)
            if candidate.is_dir():
                plugins_dir = candidate
        library_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.LibrariesPath)
        if library_path:
            candidate = Path(library_path)
            if candidate.is_dir():
                qt_lib_dir = candidate
    except Exception:
        pass

    if plugins_dir is None or qt_lib_dir is None:
        pyside_dir = Path(PYSIDE6_FILE).resolve().parent
        plugin_candidates = [
            pyside_dir / "plugins",
            pyside_dir / "Qt" / "plugins",
        ]
        qt_lib_candidates = [
            pyside_dir / "Qt" / "lib",
            pyside_dir / "lib",
            pyside_dir,
        ]
        if plugins_dir is None:
            plugins_dir = next((path for path in plugin_candidates if path.is_dir()), plugin_candidates[-1])
        if qt_lib_dir is None:
            qt_lib_dir = next((path for path in qt_lib_candidates if path.is_dir()), qt_lib_candidates[-1])

    if not os.environ.get("QT_PLUGIN_PATH"):
        os.environ["QT_PLUGIN_PATH"] = str(plugins_dir)
    platform_plugins_dir = plugins_dir / "platforms"
    if not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platform_plugins_dir)
    if sys.platform == "darwin":
        if not os.environ.get("DYLD_FRAMEWORK_PATH"):
            os.environ["DYLD_FRAMEWORK_PATH"] = str(qt_lib_dir)
        if not os.environ.get("DYLD_LIBRARY_PATH"):
            os.environ["DYLD_LIBRARY_PATH"] = str(qt_lib_dir)
    elif sys.platform.startswith("linux"):
        if not os.environ.get("LD_LIBRARY_PATH"):
            os.environ["LD_LIBRARY_PATH"] = str(qt_lib_dir)

    QCoreApplication.setLibraryPaths([str(plugins_dir)])
