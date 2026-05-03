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
from main_window import MainWindow
from mock_backend import TelemetryPoint
from protocol_constants import BLE_MODE, TELEMETRY_FIELD_BITS, transport_type_for_mode
from qt_runtime import configure_qt_runtime


def _telemetry_point(sequence: int) -> TelemetryPoint:
    sample_index = sequence - 200
    return TelemetryPoint(
        sequence=sequence,
        host_received_at=datetime.now() + timedelta(milliseconds=10 * sample_index),
        nominal_sample_period_ms=10,
        status_flags=0,
        zirconia_output_voltage_v=0.72 + 0.001 * sample_index,
        heater_rtd_resistance_ohm=118.0 + sample_index,
        differential_pressure_selected_pa=0.5 + 0.1 * sample_index,
        differential_pressure_low_range_pa=0.5 + 0.1 * sample_index,
        differential_pressure_high_range_pa=0.6 + 0.1 * sample_index,
        device_sample_tick_us=1_000_000 + 10_000 * sample_index,
        telemetry_field_bits=TELEMETRY_FIELD_BITS,
    )


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
    window._sync_recording_controls()  # noqa: SLF001 - GUI smoke for panel state


def _exercise_recording_review() -> None:
    window = MainWindow(BLE_MODE)
    tmpdir = tempfile.TemporaryDirectory(prefix="zss_recording_review_")
    try:
        window._plot_refresh_timer.stop()  # noqa: SLF001
        window._telemetry_health_timer.stop()  # noqa: SLF001
        _start_test_recording(window, Path(tmpdir.name))
        if window.open_recording_folder_button.isEnabled() or window.copy_recording_path_button.isEnabled():
            raise AssertionError("review actions should stay disabled during recording")

        for sequence in range(200, 205):
            window._on_telemetry(_telemetry_point(sequence))  # noqa: SLF001

        window._stop_recording()  # noqa: SLF001
        summary = window._latest_recording_summary  # noqa: SLF001
        if summary is None:
            raise AssertionError("latest recording summary was not created")
        if summary.row_count != 5:
            raise AssertionError(f"unexpected row count: {summary.row_count}")
        if summary.sequence_first != 200 or summary.sequence_last != 204:
            raise AssertionError(f"unexpected sequence range: {summary.sequence_first}->{summary.sequence_last}")
        if summary.sequence_gap_total != 0:
            raise AssertionError(f"unexpected sequence gaps: {summary.sequence_gap_total}")
        if summary.device_duration_s != 0.04:
            raise AssertionError(f"unexpected device duration: {summary.device_duration_s}")
        if not summary.path.exists() or summary.path.suffix != ".csv":
            raise AssertionError(f"final CSV was not created: {summary.path}")
        if summary.path.with_suffix(".partial.csv").exists():
            raise AssertionError("partial CSV remained after finalization")
        if not window.open_recording_folder_button.isEnabled() or not window.copy_recording_path_button.isEnabled():
            raise AssertionError("review actions were not enabled after finalization")
        if "Rows: 5" not in window.latest_recording_summary_value.text():
            raise AssertionError(f"summary label did not include row count: {window.latest_recording_summary_value.text()}")

        window._copy_latest_recording_path()  # noqa: SLF001
        if QApplication.clipboard().text() != str(summary.path):
            raise AssertionError("latest CSV path was not copied to clipboard")
    finally:
        if window.recording_controller.is_recording:
            window.recording_controller.abort()
        window.close()
        tmpdir.cleanup()


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    _exercise_recording_review()
    print("gui_recording_review_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
