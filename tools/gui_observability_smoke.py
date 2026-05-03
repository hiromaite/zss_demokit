#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime
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
from protocol_constants import (
    BLE_FEATURE_TELEMETRY_BATCH,
    BLE_MODE,
    TELEMETRY_FIELD_BITS,
    TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_HIGH_RANGE,
    TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_LOW_RANGE,
    TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED,
    TELEMETRY_FIELD_INTERNAL_VOLTAGE,
    TELEMETRY_FIELD_ZIRCONIA_IP_VOLTAGE,
    WIRED_MODE,
    transport_type_for_mode,
)
from qt_runtime import configure_qt_runtime


def _capabilities_payload(mode: str, *, telemetry_field_bits: int, feature_bits: int) -> dict[str, object]:
    return {
        "nominal_sample_period_ms": 10,
        "feature_bits": feature_bits,
        "telemetry_field_bits": telemetry_field_bits,
        "firmware_version": "0.1.0",
        "protocol_version": "1.0",
        "transport_type": transport_type_for_mode(mode),
    }


def _assert_contains(actual: str, expected: str, label: str) -> None:
    if expected not in actual:
        raise AssertionError(f"{label}: expected {expected!r} in {actual!r}")


def _exercise_ble_observability() -> None:
    window = MainWindow(BLE_MODE)
    try:
        selected_only_bits = TELEMETRY_FIELD_BITS | TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED
        window._on_capabilities_changed(  # noqa: SLF001 - smoke test for GUI state wiring
            _capabilities_payload(BLE_MODE, telemetry_field_bits=selected_only_bits, feature_bits=0)
        )
        _assert_contains(window.raw_sdp_availability_value.text(), "Selected DP only", "BLE legacy raw SDP")
        _assert_contains(window.service_voltage_availability_value.text(), "Not provided by BLE", "BLE service voltage")
        _assert_contains(window.ble_batch_availability_value.text(), "Not advertised", "BLE legacy batch")

        window._on_capabilities_changed(  # noqa: SLF001
            _capabilities_payload(
                BLE_MODE,
                telemetry_field_bits=selected_only_bits,
                feature_bits=BLE_FEATURE_TELEMETRY_BATCH,
            )
        )
        _assert_contains(window.ble_batch_availability_value.text(), "Supported", "BLE batch capability")

        batch_bits = (
            selected_only_bits
            | TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_LOW_RANGE
            | TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_HIGH_RANGE
        )
        window._on_telemetry(  # noqa: SLF001
            TelemetryPoint(
                sequence=1,
                host_received_at=datetime.now(),
                nominal_sample_period_ms=10,
                status_flags=0,
                zirconia_output_voltage_v=0.72,
                heater_rtd_resistance_ohm=120.0,
                differential_pressure_selected_pa=1.25,
                differential_pressure_low_range_pa=1.25,
                differential_pressure_high_range_pa=1.40,
                telemetry_field_bits=batch_bits,
            )
        )
        _assert_contains(window.raw_sdp_availability_value.text(), "Live via BLE batch", "BLE batch raw SDP")
        _assert_contains(window.metric_flow.detail_label.text(), "SDP811", "BLE flow detail")
    finally:
        window.close()


def _exercise_wired_observability() -> None:
    window = MainWindow(WIRED_MODE)
    try:
        diagnostic_bits = (
            TELEMETRY_FIELD_BITS
            | TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED
            | TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_LOW_RANGE
            | TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_HIGH_RANGE
            | TELEMETRY_FIELD_ZIRCONIA_IP_VOLTAGE
            | TELEMETRY_FIELD_INTERNAL_VOLTAGE
        )
        window._on_capabilities_changed(  # noqa: SLF001
            _capabilities_payload(WIRED_MODE, telemetry_field_bits=diagnostic_bits, feature_bits=0)
        )
        _assert_contains(window.raw_sdp_availability_value.text(), "Live", "Wired raw SDP")
        _assert_contains(window.service_voltage_availability_value.text(), "Live", "Wired service voltage")
        _assert_contains(window.ble_batch_availability_value.text(), "N/A", "Wired BLE batch label")
    finally:
        window.close()


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    _exercise_ble_observability()
    _exercise_wired_observability()
    print("gui_observability_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
