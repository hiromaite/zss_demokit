#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
for candidate in [str(GUI_ROOT), str(GUI_SRC)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION  # noqa: E402
from app_state import (  # noqa: E402
    O2_FILTER_PRESET_CUSTOM,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_EMA_2,
    O2_FILTER_TYPE_GAUSSIAN,
    O2OutputFilterPreferences,
)
from dialogs import SettingsDialog  # noqa: E402
from main_window import MainWindow  # noqa: E402
from mock_backend import TelemetryPoint  # noqa: E402
from protocol_constants import BLE_MODE, TELEMETRY_FIELD_BITS  # noqa: E402
from qt_runtime import configure_qt_runtime  # noqa: E402


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    _exercise_o2_filter_controls()
    print("gui_o2_filter_smoke_ok")
    return 0


def _exercise_o2_filter_controls() -> None:
    window = MainWindow(BLE_MODE)
    try:
        window._plot_refresh_timer.stop()  # noqa: SLF001 - deterministic smoke
        window.app_settings.o2.air_calibration_voltage_v = 0.70
        window.app_settings.o2_filter = O2OutputFilterPreferences(
            enabled=True,
            filter_type=O2_FILTER_TYPE_GAUSSIAN,
        )
        window.o2_output_filter.set_preferences(window.app_settings.o2_filter)

        window._on_telemetry(_telemetry_point(100, 0.70))  # noqa: SLF001
        window._on_telemetry(_telemetry_point(101, 0.90))  # noqa: SLF001
        raw_latest = window.plot_controller.zirconia_values[-1]
        filtered_latest = window.plot_controller.o2_zirconia_values[-1]
        if raw_latest != 0.90:
            raise AssertionError(f"raw zirconia plot value changed: {raw_latest}")
        if not (0.70 < filtered_latest < raw_latest):
            raise AssertionError(f"Gaussian filter did not smooth step: {filtered_latest}")

        dialog = SettingsDialog(
            window.app_settings,
            current_mode=BLE_MODE,
            connection_identifier="GasSensor-Proto",
            current_zirconia_voltage_v=raw_latest,
            flow_verification_available=False,
            flow_characterization_available=False,
            parent=window,
        )
        try:
            dialog.o2_filter_enabled_check.setChecked(False)
            dialog.o2_filter_type_combo.setCurrentText(O2_FILTER_TYPE_EMA_2)
            dialog.o2_filter_preset_combo.setCurrentText(O2_FILTER_PRESET_CUSTOM)
            dialog.o2_filter_ema_cutoff_spin.setValue(7.5)
            dialog.o2_filter_type_combo.setCurrentText(O2_FILTER_TYPE_CENTERED_GAUSSIAN)
            dialog.o2_filter_centered_gaussian_sigma_spin.setValue(1.35)
            selected = dialog.selected_o2_filter_preferences
            if selected.enabled:
                raise AssertionError("dialog did not expose disabled O2 filter state")
            if (
                selected.filter_type != O2_FILTER_TYPE_CENTERED_GAUSSIAN
                or abs(selected.centered_gaussian_sigma_samples - 1.35) > 1e-9
            ):
                raise AssertionError(f"dialog did not expose custom centered Gaussian settings: {selected}")
            window._apply_dialog_settings(dialog)  # noqa: SLF001
        finally:
            dialog.close()

        window._on_telemetry(_telemetry_point(102, 0.82))  # noqa: SLF001
        if window.plot_controller.o2_zirconia_values[-1] != 0.82:
            raise AssertionError("disabled O2 filter did not pass raw voltage through")
    finally:
        window.close()


def _telemetry_point(sequence: int, zirconia_output_voltage_v: float) -> TelemetryPoint:
    return TelemetryPoint(
        sequence=sequence,
        host_received_at=datetime.now() + timedelta(milliseconds=(sequence - 100) * 10),
        nominal_sample_period_ms=10,
        status_flags=0,
        zirconia_output_voltage_v=zirconia_output_voltage_v,
        heater_rtd_resistance_ohm=120.0,
        differential_pressure_selected_pa=0.0,
        device_sample_tick_us=(sequence - 100) * 10_000,
        telemetry_field_bits=TELEMETRY_FIELD_BITS,
    )


if __name__ == "__main__":
    raise SystemExit(main())
