from __future__ import annotations

import re
import sys
from pathlib import Path


APP_ORGANIZATION = "zss-demokit"
APP_ID = "zss_demokit_gui"
APP_NAME = "ZSS Demo Kit"
APP_VERSION = "1.0.0"
APP_SUBTITLE = "Desktop GUI for BLE and Wired sensor workflows"

APP_EXECUTABLE_NAME = "zss_demokit_gui"
APP_DISTRIBUTION_NAME = "zss_demokit_gui_win64_1_0_0"
APP_COMPANY_NAME = "Hiromasa Ito, Niterra Co., Ltd."
APP_PRODUCT_NAME = APP_NAME
APP_FILE_DESCRIPTION = APP_SUBTITLE
APP_COPYRIGHT = "Copyright (c) 2026 ZSS Demo Kit contributors"

ICON_CANDIDATE_PATHS = (
    "gui_prototype/assets/app_icon.ico",
    "gui_prototype/assets/app_icon.icns",
    "gui_prototype/assets/app_icon.png",
)


def normalized_windows_version_parts(version_text: str) -> tuple[int, int, int, int]:
    numeric_parts = [int(part) for part in re.findall(r"\d+", version_text)]
    padded = (numeric_parts + [0, 0, 0, 0])[:4]
    return padded[0], padded[1], padded[2], padded[3]


def build_windows_version_file_text() -> str:
    major, minor, patch, build = normalized_windows_version_parts(APP_VERSION)
    dotted = f"{major}.{minor}.{patch}.{build}"
    original_filename = f"{APP_EXECUTABLE_NAME}.exe"
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', '{APP_COMPANY_NAME}'),
            StringStruct('FileDescription', '{APP_FILE_DESCRIPTION}'),
            StringStruct('FileVersion', '{dotted}'),
            StringStruct('InternalName', '{APP_EXECUTABLE_NAME}'),
            StringStruct('OriginalFilename', '{original_filename}'),
            StringStruct('ProductName', '{APP_PRODUCT_NAME}'),
            StringStruct('ProductVersion', '{dotted}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)"""


def write_windows_version_file(target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(build_windows_version_file_text(), encoding="utf-8")
    return target_path


def resolve_packaging_icon(project_root: Path) -> str | None:
    candidate_paths = ICON_CANDIDATE_PATHS
    if sys.platform.startswith("win"):
        candidate_paths = (
            "gui_prototype/assets/app_icon.ico",
            "gui_prototype/assets/app_icon.png",
            "gui_prototype/assets/app_icon.icns",
        )
    elif sys.platform == "darwin":
        candidate_paths = (
            "gui_prototype/assets/app_icon.png",
            "gui_prototype/assets/app_icon.icns",
            "gui_prototype/assets/app_icon.ico",
        )

    for relative_path in candidate_paths:
        candidate = project_root / relative_path
        if candidate.exists():
            return str(candidate)
    return None
