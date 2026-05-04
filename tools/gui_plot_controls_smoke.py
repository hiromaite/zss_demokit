#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
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

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION
from gui_smoke_support import isolate_gui_settings
from main_window import MainWindow
from mock_backend import TelemetryPoint
from protocol_constants import BLE_MODE, TELEMETRY_FIELD_BITS, transport_type_for_mode
from qt_runtime import configure_qt_runtime


def _telemetry_point(sequence: int) -> TelemetryPoint:
    sample_index = sequence - 100
    return TelemetryPoint(
        sequence=sequence,
        host_received_at=datetime.now() + timedelta(milliseconds=10 * sample_index),
        nominal_sample_period_ms=10,
        status_flags=0,
        zirconia_output_voltage_v=0.72 + 0.001 * sample_index,
        heater_rtd_resistance_ohm=118.0 + sample_index,
        differential_pressure_selected_pa=0.5 + 0.1 * sample_index,
        device_sample_tick_us=10_000 * sample_index,
        telemetry_field_bits=TELEMETRY_FIELD_BITS,
    )


def _curve_sample_count(curve: object) -> int:
    x_values, _ = curve.getData()
    return 0 if x_values is None else len(x_values)


def _start_test_recording(window: MainWindow, base_dir: Path) -> None:
    window.recording_controller.start(
        base_dir=base_dir,
        gui_app_name=APP_NAME,
        gui_app_version=APP_VERSION,
        mode=BLE_MODE,
        transport_type=transport_type_for_mode(BLE_MODE),
        device_identifier="GasSensor-Proto",
        firmware_version="smoke",
        protocol_version="1.0",
        nominal_sample_period_ms="10",
        source_endpoint="BLE:GasSensor-Proto",
    )


def _exercise_plot_pause_and_visibility() -> None:
    window = MainWindow(BLE_MODE)
    tmpdir = tempfile.TemporaryDirectory(prefix="zss_plot_controls_")
    try:
        window._plot_refresh_timer.stop()  # noqa: SLF001 - deterministic offscreen smoke
        window.app_settings.o2.air_calibration_voltage_v = 0.72
        window.plot_controller.x_follow_enabled = False
        window.app_settings.plot.series_visibility = {
            "flow": True,
            "o2": True,
            "heater": True,
            "zirconia": True,
        }
        window._sync_series_visibility_checks()  # noqa: SLF001
        window._apply_series_visibility()  # noqa: SLF001
        _start_test_recording(window, Path(tmpdir.name))

        window._on_telemetry(_telemetry_point(100))  # noqa: SLF001
        window._refresh_plots()  # noqa: SLF001
        first_visible_count = _curve_sample_count(window.plot_curves["sensor"])
        if first_visible_count != 1:
            raise AssertionError(f"expected first plotted sample, got {first_visible_count}")

        window.plot_pause_button.setChecked(True)
        window._on_telemetry(_telemetry_point(101))  # noqa: SLF001
        window._refresh_plots()  # noqa: SLF001
        if len(window.plot_controller.time_values) != 2:
            raise AssertionError("plot buffer did not keep acquiring while paused")
        if window.recording_controller._pending_rows != 2:  # noqa: SLF001
            raise AssertionError("recording rows did not continue while plot was paused")
        paused_visible_count = _curve_sample_count(window.plot_curves["sensor"])
        if paused_visible_count != first_visible_count:
            raise AssertionError("plot curve changed while paused")

        window.plot_pause_button.setChecked(False)
        resumed_visible_count = _curve_sample_count(window.plot_curves["sensor"])
        if resumed_visible_count < 2:
            raise AssertionError("plot did not refresh to latest samples after resume")

        window.app_settings.plot.series_visibility["flow"] = False
        window._apply_series_visibility()  # noqa: SLF001
        if window.plot_curves["sensor"].isVisible():
            raise AssertionError("flow curve remained visible after disabling flow series")

        window.app_settings.plot.series_visibility["o2"] = False
        window._apply_series_visibility()  # noqa: SLF001
        if window.sensor_secondary_curve.isVisible():
            raise AssertionError("O2 curve remained visible after disabling O2 series")

        window.app_settings.plot.series_visibility["heater"] = False
        window.app_settings.plot.series_visibility["zirconia"] = False
        window._apply_series_visibility()  # noqa: SLF001
        if window.plot_curves["heater"].isVisible() or window.heater_secondary_curve.isVisible():
            raise AssertionError("heater plot series remained visible after disabling them")
    finally:
        if window.recording_controller.is_recording:
            window.recording_controller.stop()
        window.close()
        tmpdir.cleanup()


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    settings_dir = isolate_gui_settings("zss_plot_controls_smoke_")
    try:
        _exercise_plot_pause_and_visibility()
    finally:
        settings_dir.cleanup()
    print("gui_plot_controls_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
