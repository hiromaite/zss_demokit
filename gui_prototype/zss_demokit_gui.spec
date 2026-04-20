# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve().parent
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
sys.path.insert(0, str(GUI_SRC))

from app_metadata import (
    APP_DISTRIBUTION_NAME,
    APP_EXECUTABLE_NAME,
    resolve_packaging_icon,
    write_windows_version_file,
)

datas = []
datas += collect_data_files("pyqtgraph")
icon_png = PROJECT_ROOT / "gui_prototype" / "assets" / "app_icon.png"
if icon_png.exists():
    datas.append((str(icon_png), "gui_prototype/assets"))

hiddenimports = []
hiddenimports += collect_submodules("bleak.backends")
hiddenimports += [
    "serial.tools.list_ports",
]

build_root = PROJECT_ROOT / "build" / "pyinstaller"
packaging_icon = resolve_packaging_icon(PROJECT_ROOT)
windows_version_file = None
if sys.platform.startswith("win"):
    windows_version_file = str(write_windows_version_file(build_root / "version_info.txt"))

analysis = Analysis(
    [str(GUI_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT), str(GUI_ROOT), str(GUI_SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe_kwargs = {}
if packaging_icon is not None:
    exe_kwargs["icon"] = packaging_icon
if windows_version_file is not None:
    exe_kwargs["version"] = windows_version_file

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=APP_EXECUTABLE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    **exe_kwargs,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_DISTRIBUTION_NAME,
)
