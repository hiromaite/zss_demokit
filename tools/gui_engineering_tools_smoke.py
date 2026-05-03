#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
for candidate in [str(GUI_ROOT), str(GUI_SRC)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION
from app_state import AppSettings
from dialogs import SettingsDialog
from protocol_constants import BLE_MODE
from qt_runtime import configure_qt_runtime


def _nav_labels(dialog: SettingsDialog) -> list[str]:
    return [dialog.nav.item(index).text() for index in range(dialog.nav.count())]


def _exercise_engineering_tools_navigation() -> None:
    dialog = SettingsDialog(
        AppSettings(last_mode=BLE_MODE),
        current_mode=BLE_MODE,
        connection_identifier="GasSensor-Proto",
        current_zirconia_voltage_v=0.72,
        flow_verification_available=True,
        flow_characterization_available=True,
    )
    try:
        labels = _nav_labels(dialog)
        if labels != ["General", "Plot", "Recording", "Device", "Engineering / Tools", "About"]:
            raise AssertionError(f"unexpected settings navigation labels: {labels}")

        dialog.nav.setCurrentRow(labels.index("Device"))
        if not dialog.o2_calibrate_button.isEnabled():
            raise AssertionError("operator-facing O2 calibration should remain on Device page")

        dialog.nav.setCurrentRow(labels.index("Engineering / Tools"))
        if not dialog.flow_verification_button.isEnabled():
            raise AssertionError("flow verification entry should be enabled for an expected connected device")
        if not dialog.flow_characterization_button.isEnabled():
            raise AssertionError("flow characterization entry should be enabled for an expected connected device")

        actions: list[str] = []
        dialog.device_action_requested.connect(actions.append)
        dialog.status_request_button.click()
        dialog.capabilities_request_button.click()
        dialog.ping_request_button.click()
        if actions != ["get_status", "get_capabilities", "ping"]:
            raise AssertionError(f"unexpected engineering diagnostics actions: {actions}")
    finally:
        dialog.close()


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    _exercise_engineering_tools_navigation()
    print("gui_engineering_tools_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
