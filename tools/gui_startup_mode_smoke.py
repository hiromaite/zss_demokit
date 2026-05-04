#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
for candidate in [str(GUI_ROOT), str(GUI_SRC)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from PySide6.QtWidgets import QApplication  # noqa: E402

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION  # noqa: E402
from app_state import STARTUP_MODE_BLE, STARTUP_MODE_SELECTOR  # noqa: E402
from dialogs import SettingsDialog  # noqa: E402
from gui_smoke_support import isolate_gui_settings  # noqa: E402
from launcher_window import LauncherWindow  # noqa: E402
from main import create_startup_window  # noqa: E402
from main_window import MainWindow  # noqa: E402
from protocol_constants import BLE_MODE  # noqa: E402
from qt_runtime import configure_qt_runtime  # noqa: E402
from settings_store import SettingsStore  # noqa: E402


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    settings_dir = isolate_gui_settings("zss_startup_mode_smoke_")
    try:
        store = SettingsStore()
        settings = store.load()
        if settings.startup_mode != STARTUP_MODE_SELECTOR:
            raise AssertionError(f"default startup mode was not selector: {settings.startup_mode}")

        launcher = create_startup_window()
        try:
            if not isinstance(launcher, LauncherWindow):
                raise AssertionError(f"default startup did not create launcher: {type(launcher)!r}")
        finally:
            launcher.close()

        settings.startup_mode = STARTUP_MODE_BLE
        store.save(settings)
        ble_window = create_startup_window()
        try:
            if not isinstance(ble_window, MainWindow):
                raise AssertionError(f"BLE startup did not create MainWindow: {type(ble_window)!r}")
            if ble_window.mode != BLE_MODE:
                raise AssertionError(f"BLE startup opened wrong mode: {ble_window.mode}")
        finally:
            ble_window.close()

        dialog = SettingsDialog(
            store.load(),
            current_mode=BLE_MODE,
            connection_identifier="GasSensor-Proto",
            flow_verification_available=False,
            flow_characterization_available=False,
        )
        try:
            if dialog.selected_startup_mode != STARTUP_MODE_BLE:
                raise AssertionError("settings dialog did not reflect BLE startup mode")
            dialog.startup_mode_combo.setCurrentIndex(
                dialog.startup_mode_combo.findData(STARTUP_MODE_SELECTOR)
            )
            if dialog.selected_startup_mode != STARTUP_MODE_SELECTOR:
                raise AssertionError("settings dialog did not expose selector startup mode")
        finally:
            dialog.close()
    finally:
        settings_dir.cleanup()

    print("gui_startup_mode_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
