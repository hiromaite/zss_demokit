from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_SRC = PROJECT_ROOT / "gui_prototype" / "src"
EXPECTED_VERSION = "0.1.0-beta.3"
EXPECTED_DISTRIBUTION = "zss_demokit_gui_win64_beta3"

sys.path.insert(0, str(GUI_SRC))

from app_metadata import (  # noqa: E402
    APP_COMPANY_NAME,
    APP_DISTRIBUTION_NAME,
    APP_EXECUTABLE_NAME,
    APP_NAME,
    APP_VERSION,
    resolve_packaging_icon,
)


def _contains(path: Path, text: str) -> bool:
    return text in path.read_text(encoding="utf-8")


def main() -> int:
    checks: list[tuple[bool, str, str]] = []

    checks.append((APP_NAME == "ZSS Demo Kit", "app name", APP_NAME))
    checks.append((APP_EXECUTABLE_NAME == "zss_demokit_gui", "executable name", APP_EXECUTABLE_NAME))
    checks.append((APP_VERSION == EXPECTED_VERSION, "app version", APP_VERSION))
    checks.append((APP_DISTRIBUTION_NAME == EXPECTED_DISTRIBUTION, "distribution name", APP_DISTRIBUTION_NAME))
    checks.append((bool(APP_COMPANY_NAME), "company metadata", APP_COMPANY_NAME))

    spec_path = PROJECT_ROOT / "gui_prototype" / "zss_demokit_gui.spec"
    checks.append((spec_path.exists(), "PyInstaller spec exists", str(spec_path.relative_to(PROJECT_ROOT))))
    if spec_path.exists():
        spec_text = spec_path.read_text(encoding="utf-8")
        checks.append(("APP_DISTRIBUTION_NAME" in spec_text, "spec uses metadata distribution name", "APP_DISTRIBUTION_NAME"))
        checks.append(("bleak.backends" in spec_text, "spec collects BLE backends", "bleak.backends"))
        checks.append(("serial.tools.list_ports" in spec_text, "spec includes serial port helper", "serial.tools.list_ports"))
        checks.append(("console=False" in spec_text, "spec uses windowed app mode", "console=False"))

    icon_path = resolve_packaging_icon(PROJECT_ROOT)
    checks.append((icon_path is not None, "packaging icon resolved", icon_path or "--"))
    checks.append(((PROJECT_ROOT / "gui_prototype" / "assets" / "app_icon.png").exists(), "PNG icon exists", "gui_prototype/assets/app_icon.png"))
    checks.append(((PROJECT_ROOT / "gui_prototype" / "assets" / "app_icon.ico").exists(), "ICO icon exists", "gui_prototype/assets/app_icon.ico"))

    required_docs = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "gui_prototype" / "packaging_README.md",
        PROJECT_ROOT / "docs" / "distribution_plan_v1.md",
        PROJECT_ROOT / "docs" / "windows_beta_smoke_checklist_v1.md",
        PROJECT_ROOT / "docs" / "release_notes_beta3.md",
    ]
    for doc_path in required_docs:
        relative = str(doc_path.relative_to(PROJECT_ROOT))
        checks.append((doc_path.exists(), f"{relative} exists", relative))
        if doc_path.exists():
            checks.append((_contains(doc_path, EXPECTED_VERSION), f"{relative} mentions version", EXPECTED_VERSION))
            checks.append((_contains(doc_path, EXPECTED_DISTRIBUTION), f"{relative} mentions distribution", EXPECTED_DISTRIBUTION))

    failed = False
    for ok, label, detail in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status} {label}: {detail}")
        failed = failed or not ok

    if failed:
        print("release_readiness_check_failed")
        return 1

    print("release_readiness_check_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
