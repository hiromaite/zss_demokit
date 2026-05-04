#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
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
    O2_FILTER_PRESET_DEFAULT,
    O2_FILTER_PRESET_QUIET,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_SAVGOL,
    O2_FILTER_TYPES,
    O2OutputFilterPreferences,
)
from dialogs import SettingsDialog  # noqa: E402
from gui_smoke_support import isolate_gui_settings  # noqa: E402
from main_window import MainWindow  # noqa: E402
from mock_backend import TelemetryPoint  # noqa: E402
from protocol_constants import BLE_MODE, TELEMETRY_FIELD_BITS  # noqa: E402
from qt_runtime import configure_qt_runtime  # noqa: E402
from settings_store import SettingsStore  # noqa: E402


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    settings_dir = isolate_gui_settings("zss_o2_filter_smoke_")
    try:
        _exercise_o2_settings_migration()
        _exercise_o2_clamp_diagnostics()
        _exercise_o2_filter_controls()
    finally:
        settings_dir.cleanup()
    print("gui_o2_filter_smoke_ok")
    return 0


def _exercise_o2_settings_migration() -> None:
    settings_path = os.environ["ZSS_DEMOKIT_SETTINGS_FILE"]
    raw_settings = QSettings(settings_path, QSettings.IniFormat)
    raw_settings.setValue("o2/air_calibration_voltage_v", 0.70)
    raw_settings.setValue("o2/calibrated_at_iso", "")
    raw_settings.setValue("o2/zero_reference_voltage_v", 2.5)
    raw_settings.setValue("o2_filter/filter_type", "EMA 2-pole")
    raw_settings.setValue("o2_filter/preset", "Balanced")
    raw_settings.sync()

    loaded = SettingsStore().load()
    if loaded.o2.air_calibration_voltage_v is not None:
        raise AssertionError("unversioned O2 calibration anchor was not ignored on load")
    if loaded.o2.zero_reference_voltage_v != 0.0:
        raise AssertionError("legacy O2 zero reference was not migrated to 0 V default")
    if loaded.o2_filter.filter_type not in O2_FILTER_TYPES:
        raise AssertionError(f"legacy O2 filter type was not migrated: {loaded.o2_filter}")
    if loaded.o2_filter.preset != O2_FILTER_PRESET_DEFAULT:
        raise AssertionError(f"legacy Balanced preset was not migrated: {loaded.o2_filter}")


def _exercise_o2_clamp_diagnostics() -> None:
    window = MainWindow(BLE_MODE)
    try:
        window._plot_refresh_timer.stop()  # noqa: SLF001 - deterministic smoke
        window.app_settings.o2.air_calibration_voltage_v = 0.70
        window.app_settings.o2.zero_reference_voltage_v = 2.5
        window.app_settings.o2_filter = O2OutputFilterPreferences(enabled=False)
        window.o2_output_filter.set_preferences(window.app_settings.o2_filter)
        window._on_telemetry(_telemetry_point(100, 2.60))  # noqa: SLF001
        window._refresh_plots()  # noqa: SLF001

        _x_data, y_data = window.sensor_secondary_curve.getData()
        if y_data is None or float(y_data[-1]) != 0.0:
            raise AssertionError("clamped O2 plot did not reproduce expected 0% condition")
        detail = window.metric_o2.detail_label.text()
        if "clamped to 0%" not in detail or "Input 2.600 V" not in detail:
            raise AssertionError(f"O2 clamp diagnostic detail was not shown: {detail}")
    finally:
        window.close()


def _exercise_o2_filter_controls() -> None:
    window = MainWindow(BLE_MODE)
    try:
        window._plot_refresh_timer.stop()  # noqa: SLF001 - deterministic smoke
        window.app_settings.o2.air_calibration_voltage_v = 0.70
        window.app_settings.o2.zero_reference_voltage_v = 0.0
        window.app_settings.o2_filter = O2OutputFilterPreferences(
            enabled=True,
            filter_type=O2_FILTER_TYPE_CENTERED_GAUSSIAN,
        )
        window.o2_output_filter.set_preferences(window.app_settings.o2_filter)

        for sequence, voltage in enumerate(
            [0.70, 0.70, 0.70, 0.70, 0.90, 0.90, 0.90, 0.90, 0.90],
            start=100,
        ):
            window._on_telemetry(_telemetry_point(sequence, voltage))  # noqa: SLF001
        raw_latest = window.plot_controller.zirconia_values[-1]
        filtered_latest = window.plot_controller.o2_zirconia_values[-1]
        if raw_latest != 0.90:
            raise AssertionError(f"raw zirconia plot value changed: {raw_latest}")
        if not (0.70 < filtered_latest < raw_latest):
            raise AssertionError(f"centered Gaussian filter did not smooth step: {filtered_latest}")
        window._refresh_plots()  # noqa: SLF001
        x_data, y_data = window.sensor_secondary_curve.getData()
        if x_data is None or y_data is None or len(y_data) != len(window.plot_controller.time_values):
            raise AssertionError("O2 plot curve did not receive filtered O2 data")
        if float(y_data[-1]) <= 21.0:
            raise AssertionError(f"O2 plot curve did not use filtered voltage conversion: {float(y_data[-1])}")

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
            dialog.o2_zero_reference_spin.setValue(0.05)
            dialog.o2_filter_enabled_check.setChecked(False)
            if not dialog.o2_filter_type_combo.isEnabled():
                raise AssertionError("disabled O2 filter blocked filter type editing")
            if [
                dialog.o2_filter_type_combo.itemText(index)
                for index in range(dialog.o2_filter_type_combo.count())
            ] != list(O2_FILTER_TYPES):
                raise AssertionError("O2 filter type list was not limited to supported filters")
            dialog.o2_filter_type_combo.setCurrentText(O2_FILTER_TYPE_SAVGOL)
            dialog.o2_filter_preset_combo.setCurrentText(O2_FILTER_PRESET_DEFAULT)
            if dialog.o2_filter_savgol_window_spin.value() != 9:
                raise AssertionError("Savitzky-Golay default preset did not update custom fields")
            if dialog.o2_filter_savgol_window_spin.isEnabled():
                raise AssertionError("Savitzky-Golay preset field should be read-only until Custom")
            dialog.o2_filter_preset_combo.setCurrentText(O2_FILTER_PRESET_CUSTOM)
            if not dialog.o2_filter_savgol_window_spin.isEnabled():
                raise AssertionError("Savitzky-Golay custom window control was not editable")
            dialog.o2_filter_savgol_window_spin.setValue(15)
            dialog.o2_filter_savgol_order_spin.setValue(3)
            dialog.o2_filter_type_combo.setCurrentText(O2_FILTER_TYPE_CENTERED_GAUSSIAN)
            dialog.o2_filter_preset_combo.setCurrentText(O2_FILTER_PRESET_QUIET)
            if (
                dialog.o2_filter_centered_gaussian_window_spin.value() != 13
                or abs(dialog.o2_filter_centered_gaussian_sigma_spin.value() - 2.75) > 1e-9
            ):
                raise AssertionError("centered Gaussian quiet preset did not update custom fields")
            if dialog.o2_filter_centered_gaussian_sigma_spin.isEnabled():
                raise AssertionError("centered Gaussian preset field should be read-only until Custom")
            dialog.o2_filter_preset_combo.setCurrentText(O2_FILTER_PRESET_CUSTOM)
            if not dialog.o2_filter_centered_gaussian_sigma_spin.isEnabled():
                raise AssertionError("centered Gaussian sigma control was not editable")
            dialog.o2_filter_centered_gaussian_window_spin.setValue(17)
            dialog.o2_filter_centered_gaussian_sigma_spin.setValue(3.25)
            selected = dialog.selected_o2_filter_preferences
            if selected.enabled:
                raise AssertionError("dialog did not expose disabled O2 filter state")
            if abs(dialog.selected_o2_zero_reference_voltage_v - 0.05) > 1e-9:
                raise AssertionError("dialog did not expose custom O2 zero reference voltage")
            if (
                selected.filter_type != O2_FILTER_TYPE_CENTERED_GAUSSIAN
                or selected.centered_gaussian_window_points != 17
                or abs(selected.centered_gaussian_sigma_samples - 3.25) > 1e-9
            ):
                raise AssertionError(f"dialog did not expose custom centered Gaussian settings: {selected}")
            window._apply_dialog_settings(dialog)  # noqa: SLF001
        finally:
            dialog.close()

        window._on_telemetry(_telemetry_point(109, 0.82))  # noqa: SLF001
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
