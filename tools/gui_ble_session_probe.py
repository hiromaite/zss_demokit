from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

if "--offscreen" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
for candidate in [str(PROJECT_ROOT), str(GUI_ROOT), str(GUI_SRC)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION
from main_window import MainWindow
from protocol_constants import BLE_MODE
from qt_runtime import configure_qt_runtime


@dataclass
class ProbeThresholds:
    min_observed_duration_s: float
    max_sequence_gap_total: int
    max_stall_warnings: int
    reconnect_timeout_s: float


@dataclass
class ProbeSummary:
    scanned_devices: int
    selected_device_label: str
    connect_count: int
    disconnect_count: int
    connected_segment_count: int
    capabilities_events: int
    status_events: int
    telemetry_count: int
    total_observed_duration_s: float
    sequence_gap_total: int
    max_sequence_gap: int
    sequence_reset_count: int
    warning_count: int
    error_count: int
    stall_warning_count: int
    pump_command_requests: int
    pump_on_status_seen: bool
    pump_off_status_seen: bool
    status_requests: int
    ping_requests: int
    reconnect_performed: bool
    reconnect_recovered: bool
    reconnect_recovery_s: float | None
    recording_sessions_completed: int
    csv_rows: int
    csv_non_unit_gaps: int
    final_recording_path: Path | None


class AggregateTelemetryStats:
    def __init__(self) -> None:
        self.telemetry_count = 0
        self.total_observed_duration_s = 0.0
        self.sequence_gap_total = 0
        self.max_sequence_gap = 0
        self.sequence_reset_count = 0
        self.connected_segment_count = 0
        self._last_sequence: int | None = None
        self._segment_start_monotonic: float | None = None
        self._last_telemetry_monotonic: float | None = None

    def on_connection_changed(self, connected: bool) -> None:
        if connected:
            self._last_sequence = None
            return
        self.close_segment()
        self._last_sequence = None

    def on_telemetry(self, sequence: int) -> None:
        now = time.monotonic()
        if self._segment_start_monotonic is None:
            self._segment_start_monotonic = now
            self.connected_segment_count += 1
        if self._last_sequence is not None:
            if sequence > self._last_sequence + 1:
                gap = sequence - self._last_sequence - 1
                self.sequence_gap_total += gap
                self.max_sequence_gap = max(self.max_sequence_gap, gap)
            elif sequence <= self._last_sequence:
                self.sequence_reset_count += 1
        self.telemetry_count += 1
        self._last_sequence = sequence
        self._last_telemetry_monotonic = now

    def close_segment(self) -> None:
        if self._segment_start_monotonic is not None and self._last_telemetry_monotonic is not None:
            duration = self._last_telemetry_monotonic - self._segment_start_monotonic
            self.total_observed_duration_s += max(0.0, duration)
        self._segment_start_monotonic = None
        self._last_telemetry_monotonic = None


class FakeBleakScanner:
    @staticmethod
    async def discover(timeout: float = 6.0):
        del timeout

        class _FakeDevice:
            def __init__(self, name: str, address: str) -> None:
                self.name = name
                self.address = address

        return [
            _FakeDevice("M5STAMP-MONITOR", "FAKE-UUID-001"),
            _FakeDevice("IGNORED-NODE", "FAKE-UUID-999"),
        ]


class GuiBleSessionProbe(QObject):
    def __init__(
        self,
        *,
        window: MainWindow,
        selected_prefix: str,
        exact_label: str,
        scan_timeout_s: float,
        connect_timeout_s: float,
        duration_s: float,
        recording_duration_s: float,
        reconnect_at_s: float,
        thresholds: ProbeThresholds,
        original_recording_directory: str,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.selected_prefix = selected_prefix
        self.exact_label = exact_label
        self.scan_timeout_s = scan_timeout_s
        self.connect_timeout_s = connect_timeout_s
        self.duration_s = duration_s
        self.recording_duration_s = recording_duration_s
        self.reconnect_at_s = reconnect_at_s
        self.thresholds = thresholds
        self.original_recording_directory = original_recording_directory

        self.scanned_devices = 0
        self.selected_device_label = ""
        self.connect_count = 0
        self.disconnect_count = 0
        self.capabilities_events = 0
        self.status_events = 0
        self.warning_count = 0
        self.error_count = 0
        self.stall_warning_count = 0
        self.pump_command_requests = 0
        self.pump_on_status_seen = False
        self.pump_off_status_seen = False
        self.status_requests = 0
        self.ping_requests = 0
        self.reconnect_performed = False
        self.reconnect_recovered = False
        self.reconnect_recovery_s: float | None = None
        self.recording_sessions_completed = 0
        self.final_recording_path: Path | None = None
        self.csv_rows = 0
        self.csv_non_unit_gaps = 0
        self._telemetry_stats = AggregateTelemetryStats()
        self._finished = False
        self._failure_message: str | None = None
        self._telemetry_seen_in_current_connection = False
        self._planned_disconnect_pending = False
        self._recording_started = False
        self._session_schedule_started = False
        self._reconnect_disconnect_at_monotonic: float | None = None
        self._timers: list[QTimer] = []

        self._scan_timeout_timer = QTimer(self)
        self._scan_timeout_timer.setSingleShot(True)
        self._scan_timeout_timer.timeout.connect(self._on_scan_timeout)

        self._connect_timeout_timer = QTimer(self)
        self._connect_timeout_timer.setSingleShot(True)
        self._connect_timeout_timer.timeout.connect(self._on_connect_timeout)

        self._reconnect_timeout_timer = QTimer(self)
        self._reconnect_timeout_timer.setSingleShot(True)
        self._reconnect_timeout_timer.timeout.connect(self._on_reconnect_timeout)

        self.window.connection_controller.connection_changed.connect(self._on_connection_changed)
        self.window.connection_controller.capabilities_changed.connect(self._on_capabilities_changed)
        self.window.connection_controller.status_changed.connect(self._on_status_changed)
        self.window.connection_controller.telemetry_received.connect(self._on_telemetry)
        self.window.connection_controller.log_generated.connect(self._on_log)
        self.window.connection_controller.ble_devices_discovered.connect(self._on_ble_devices_discovered)

    @property
    def result(self) -> ProbeSummary | None:
        if self._finished and self._failure_message is None:
            return ProbeSummary(
                scanned_devices=self.scanned_devices,
                selected_device_label=self.selected_device_label,
                connect_count=self.connect_count,
                disconnect_count=self.disconnect_count,
                connected_segment_count=self._telemetry_stats.connected_segment_count,
                capabilities_events=self.capabilities_events,
                status_events=self.status_events,
                telemetry_count=self._telemetry_stats.telemetry_count,
                total_observed_duration_s=self._telemetry_stats.total_observed_duration_s,
                sequence_gap_total=self._telemetry_stats.sequence_gap_total,
                max_sequence_gap=self._telemetry_stats.max_sequence_gap,
                sequence_reset_count=self._telemetry_stats.sequence_reset_count,
                warning_count=self.warning_count,
                error_count=self.error_count,
                stall_warning_count=self.stall_warning_count,
                pump_command_requests=self.pump_command_requests,
                pump_on_status_seen=self.pump_on_status_seen,
                pump_off_status_seen=self.pump_off_status_seen,
                status_requests=self.status_requests,
                ping_requests=self.ping_requests,
                reconnect_performed=self.reconnect_performed,
                reconnect_recovered=self.reconnect_recovered,
                reconnect_recovery_s=self.reconnect_recovery_s,
                recording_sessions_completed=self.recording_sessions_completed,
                csv_rows=self.csv_rows,
                csv_non_unit_gaps=self.csv_non_unit_gaps,
                final_recording_path=self.final_recording_path,
            )
        return None

    @property
    def failure_message(self) -> str | None:
        return self._failure_message

    def start(self) -> None:
        self.window.show()
        self.window.ble_device_selector.clear()
        self._append_info("Starting BLE GUI session probe.")
        self.window.connection_controller.scan_ble_devices()
        self._scan_timeout_timer.start(max(1000, int(self.scan_timeout_s * 1000)))

    def _on_scan_timeout(self) -> None:
        if self._finished:
            return
        if self.selected_device_label:
            return
        self._abort("BLE scan did not yield a matching device within the timeout window.")

    def _on_connect_timeout(self) -> None:
        if self._finished:
            return
        self._abort("BLE telemetry did not start within the expected timeout window.")

    def _on_reconnect_timeout(self) -> None:
        if self._finished:
            return
        self._abort("BLE reconnect did not recover within the expected timeout window.")

    def _on_ble_devices_discovered(self, devices: list[str]) -> None:
        if self._finished:
            return
        self.scanned_devices = len(devices)
        if self.selected_device_label:
            return
        selected = self._select_device_label(devices)
        if not selected:
            return
        self.selected_device_label = selected
        self._scan_timeout_timer.stop()
        self._append_info(f"Selected BLE device: {selected}")
        self.window.connection_controller.connect_device(selected)

    def _on_connection_changed(self, connected: bool, identifier: str) -> None:
        if self._finished:
            return

        self._telemetry_stats.on_connection_changed(connected)
        if connected:
            self.connect_count += 1
            self._telemetry_seen_in_current_connection = False
            self._connect_timeout_timer.start(max(1000, int(self.connect_timeout_s * 1000)))
            if self._reconnect_disconnect_at_monotonic is not None and not self.reconnect_recovered:
                self.reconnect_recovered = True
                self.reconnect_recovery_s = time.monotonic() - self._reconnect_disconnect_at_monotonic
                self._reconnect_timeout_timer.stop()
                self._schedule_post_reconnect_actions()
            return

        self.disconnect_count += 1
        self._connect_timeout_timer.stop()
        if self._planned_disconnect_pending and not self.reconnect_performed:
            self._planned_disconnect_pending = False
            self.reconnect_performed = True
            self._reconnect_disconnect_at_monotonic = time.monotonic()
            self._reconnect_timeout_timer.start(max(1000, int(self.thresholds.reconnect_timeout_s * 1000)))
            self._schedule_once(1200, self._reconnect_device)
            return
        if not self._finished and self.connect_count > 0:
            self._abort(f"Unexpected BLE disconnect from {identifier}.")

    def _on_capabilities_changed(self, _payload: dict[str, object]) -> None:
        self.capabilities_events += 1

    def _on_status_changed(self, payload: dict[str, object]) -> None:
        self.status_events += 1
        pump_state = str(payload.get("pump_state", "") or "")
        if pump_state == "ON":
            self.pump_on_status_seen = True
        elif pump_state == "OFF":
            self.pump_off_status_seen = True

    def _on_telemetry(self, point: object) -> None:
        if self._finished:
            return
        sequence = int(getattr(point, "sequence"))
        self._telemetry_stats.on_telemetry(sequence)
        if not self._telemetry_seen_in_current_connection:
            self._telemetry_seen_in_current_connection = True
            self._connect_timeout_timer.stop()
            if not self._recording_started:
                self._schedule_once(1200, self._start_recording)
            elif self.reconnect_recovered:
                self._append_info("Telemetry recovered after reconnect.")

    def _on_log(self, severity: str, message: str) -> None:
        if self._finished:
            return
        if severity == "warn":
            self.warning_count += 1
        elif severity == "error":
            self.error_count += 1
        if "Telemetry stream appears stalled." in message:
            self.stall_warning_count += 1
        if severity == "error" and "Recording could not be started" not in message:
            self._abort(f"GUI probe observed error log: {message}")

    def _start_recording(self) -> None:
        if self._finished or self._recording_started:
            return
        if not self.window.connection_controller.is_connected():
            self._abort("BLE probe could not establish a connection before recording.")
            return
        self.window._start_recording()
        if not self.window.recording_controller.is_recording:
            self._abort("BLE probe failed to enter recording state.")
            return
        self._recording_started = True
        if not self._session_schedule_started:
            self._session_schedule_started = True
            self._schedule_session_actions()

    def _schedule_session_actions(self) -> None:
        recording_ms = max(1000, int(self.recording_duration_s * 1000))
        reconnect_ms = max(recording_ms + 1000, int(self.reconnect_at_s * 1000))
        total_ms = max(reconnect_ms + 2000, int(self.duration_s * 1000))

        self._schedule_once(max(300, int(recording_ms * 0.20)), self._request_status)
        self._schedule_once(max(600, int(recording_ms * 0.35)), lambda: self._set_pump_state(True))
        self._schedule_once(max(900, int(recording_ms * 0.50)), self._request_status)
        self._schedule_once(max(1200, int(recording_ms * 0.70)), lambda: self._set_pump_state(False))
        self._schedule_once(max(1500, int(recording_ms * 0.85)), self._ping)
        self._schedule_once(recording_ms, self._stop_recording)
        self._schedule_once(reconnect_ms, self._trigger_planned_reconnect)
        self._schedule_once(total_ms, self._finish_probe)

    def _schedule_post_reconnect_actions(self) -> None:
        reconnect_phase_ms = max(4000, int((self.duration_s - self.reconnect_at_s) * 1000))
        self._schedule_once(max(400, int(reconnect_phase_ms * 0.15)), self._request_status)
        self._schedule_once(max(800, int(reconnect_phase_ms * 0.35)), lambda: self._set_pump_state(True))
        self._schedule_once(max(1200, int(reconnect_phase_ms * 0.55)), lambda: self._set_pump_state(False))
        self._schedule_once(max(1600, int(reconnect_phase_ms * 0.75)), self._ping)

    def _set_pump_state(self, enabled: bool) -> None:
        if self._finished or not self.window.connection_controller.is_connected():
            return
        self.window.connection_controller.set_pump_state(enabled)
        self.pump_command_requests += 1

    def _request_status(self) -> None:
        if self._finished or not self.window.connection_controller.is_connected():
            return
        self.window.connection_controller.request_status()
        self.status_requests += 1

    def _ping(self) -> None:
        if self._finished or not self.window.connection_controller.is_connected():
            return
        self.window.connection_controller.ping()
        self.ping_requests += 1

    def _stop_recording(self) -> None:
        if self._finished or not self.window.recording_controller.is_recording:
            return
        self.window._stop_recording()
        final_path_raw = self.window.ui_state.recording.current_file
        if final_path_raw:
            final_path = Path(final_path_raw)
            if final_path.exists():
                self.recording_sessions_completed += 1
                self.final_recording_path = final_path
                self.csv_rows, self.csv_non_unit_gaps = _analyze_recording_csv(final_path)

    def _trigger_planned_reconnect(self) -> None:
        if self._finished or self.reconnect_performed:
            return
        if self.window.recording_controller.is_recording:
            self._stop_recording()
        if not self.window.connection_controller.is_connected():
            self._abort("BLE probe could not initiate the planned reconnect because the device is not connected.")
            return
        self._planned_disconnect_pending = True
        self.window.connection_controller.disconnect_device()

    def _reconnect_device(self) -> None:
        if self._finished:
            return
        if not self.selected_device_label:
            self._abort("BLE probe lost the selected device label before reconnect.")
            return
        self.window.connection_controller.connect_device(self.selected_device_label)

    def _finish_probe(self) -> None:
        if self._finished:
            return
        self._stop_recording()
        self._telemetry_stats.close_segment()

        summary = self.result or ProbeSummary(
            scanned_devices=self.scanned_devices,
            selected_device_label=self.selected_device_label,
            connect_count=self.connect_count,
            disconnect_count=self.disconnect_count,
            connected_segment_count=self._telemetry_stats.connected_segment_count,
            capabilities_events=self.capabilities_events,
            status_events=self.status_events,
            telemetry_count=self._telemetry_stats.telemetry_count,
            total_observed_duration_s=self._telemetry_stats.total_observed_duration_s,
            sequence_gap_total=self._telemetry_stats.sequence_gap_total,
            max_sequence_gap=self._telemetry_stats.max_sequence_gap,
            sequence_reset_count=self._telemetry_stats.sequence_reset_count,
            warning_count=self.warning_count,
            error_count=self.error_count,
            stall_warning_count=self.stall_warning_count,
            pump_command_requests=self.pump_command_requests,
            pump_on_status_seen=self.pump_on_status_seen,
            pump_off_status_seen=self.pump_off_status_seen,
            status_requests=self.status_requests,
            ping_requests=self.ping_requests,
            reconnect_performed=self.reconnect_performed,
            reconnect_recovered=self.reconnect_recovered,
            reconnect_recovery_s=self.reconnect_recovery_s,
            recording_sessions_completed=self.recording_sessions_completed,
            csv_rows=self.csv_rows,
            csv_non_unit_gaps=self.csv_non_unit_gaps,
            final_recording_path=self.final_recording_path,
        )

        failures: list[str] = []
        if summary.total_observed_duration_s < self.thresholds.min_observed_duration_s:
            failures.append(
                f"observed BLE telemetry duration {summary.total_observed_duration_s:0.1f}s "
                f"is below {self.thresholds.min_observed_duration_s:0.1f}s"
            )
        if summary.recording_sessions_completed < 1 or summary.final_recording_path is None:
            failures.append("recording was not finalized successfully")
        if summary.pump_command_requests < 2:
            failures.append("pump ON/OFF commands were not both exercised")
        if not summary.pump_on_status_seen:
            failures.append("pump ON status was not observed")
        if not summary.pump_off_status_seen:
            failures.append("pump OFF status was not observed")
        if summary.status_requests < 1:
            failures.append("status request was not exercised")
        if summary.ping_requests < 1:
            failures.append("ping was not exercised")
        if not summary.reconnect_performed:
            failures.append("planned reconnect was not performed")
        if not summary.reconnect_recovered:
            failures.append("reconnect did not recover capabilities/status/telemetry")
        if summary.reconnect_recovery_s is not None and summary.reconnect_recovery_s > self.thresholds.reconnect_timeout_s:
            failures.append(
                f"reconnect recovery {summary.reconnect_recovery_s:0.2f}s exceeded "
                f"{self.thresholds.reconnect_timeout_s:0.2f}s"
            )
        if summary.sequence_gap_total > self.thresholds.max_sequence_gap_total:
            failures.append(
                f"sequence_gap_total={summary.sequence_gap_total} exceeded "
                f"{self.thresholds.max_sequence_gap_total}"
            )
        if summary.stall_warning_count > self.thresholds.max_stall_warnings:
            failures.append(
                f"stall_warning_count={summary.stall_warning_count} exceeded "
                f"{self.thresholds.max_stall_warnings}"
            )
        if summary.sequence_reset_count > 0:
            failures.append(f"sequence_reset_count={summary.sequence_reset_count} should be 0")
        if summary.error_count > 0:
            failures.append(f"error_count={summary.error_count} should be 0")

        if failures:
            self._abort("; ".join(failures))
            return

        self._cleanup_and_quit()

    def _cleanup_and_quit(self) -> None:
        self._finished = True
        self._scan_timeout_timer.stop()
        self._connect_timeout_timer.stop()
        self._reconnect_timeout_timer.stop()
        self.window.app_settings.logging.recording_directory = self.original_recording_directory
        if self.window.connection_controller.is_connected():
            self.window.connection_controller.disconnect_device()
        QTimer.singleShot(400, QApplication.instance().quit)

    def _abort(self, message: str) -> None:
        if self._finished:
            return
        self._failure_message = message
        self._cleanup_and_quit()

    def _schedule_once(self, delay_ms: int, callback) -> None:
        timer = QTimer(self)
        timer.setSingleShot(True)

        def _run() -> None:
            if timer in self._timers:
                self._timers.remove(timer)
            if self._finished:
                return
            callback()

        timer.timeout.connect(_run)
        self._timers.append(timer)
        timer.start(max(0, delay_ms))

    def _select_device_label(self, devices: list[str]) -> str:
        if not devices:
            return ""
        if self.exact_label:
            for label in devices:
                if label == self.exact_label:
                    return label
        if self.selected_prefix:
            for label in devices:
                if label.startswith(self.selected_prefix):
                    return label
        return devices[0]

    def _append_info(self, message: str) -> None:
        self.window._append_log("info", message)


def _analyze_recording_csv(path: Path) -> tuple[int, int]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        content_lines = [line for line in handle if not line.startswith("#")]
    reader = csv.DictReader(content_lines)
    rows.extend(reader)
    non_unit_gaps = sum(1 for row in rows if int(row["sequence_gap"]) > 0)
    return len(rows), non_unit_gaps


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a GUI-level BLE continuity / reconnect probe.")
    parser.add_argument("--device-prefix", default="M5STAMP-MONITOR", help="Preferred BLE device label prefix")
    parser.add_argument("--device-label", default="", help="Optional exact BLE device label to connect")
    parser.add_argument("--scan-timeout-s", type=float, default=12.0, help="BLE scan timeout")
    parser.add_argument("--connect-timeout-s", type=float, default=12.0, help="Telemetry start timeout after connect")
    parser.add_argument("--duration-s", type=float, default=180.0, help="Total probe duration")
    parser.add_argument(
        "--recording-duration-s",
        type=float,
        default=45.0,
        help="Recording duration before planned reconnect",
    )
    parser.add_argument(
        "--reconnect-at-s",
        type=float,
        default=60.0,
        help="When to trigger the planned disconnect / reconnect",
    )
    parser.add_argument(
        "--reconnect-timeout-s",
        type=float,
        default=10.0,
        help="Maximum allowed reconnect recovery duration",
    )
    parser.add_argument(
        "--min-observed-duration-s",
        type=float,
        default=0.0,
        help="Minimum total connected BLE telemetry observation time required for success. When omitted, duration minus reconnect timeout is used.",
    )
    parser.add_argument(
        "--max-sequence-gap-total",
        type=int,
        default=5,
        help="Maximum allowed total sequence gap across the probe",
    )
    parser.add_argument(
        "--max-stall-warnings",
        type=int,
        default=1,
        help="Maximum allowed telemetry stall warnings",
    )
    parser.add_argument(
        "--recording-dir",
        default="",
        help="Optional directory for generated CSV files. A temporary directory is used when omitted.",
    )
    parser.add_argument(
        "--use-fake-live",
        action="store_true",
        help="Run against a fake BLE scanner/client for probe logic smoke testing.",
    )
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Run Qt in offscreen mode. Useful for automated smoke tests.",
    )
    args = parser.parse_args()
    if args.recording_duration_s >= args.reconnect_at_s:
        parser.error("--recording-duration-s must be smaller than --reconnect-at-s")
    if args.reconnect_at_s >= args.duration_s:
        parser.error("--reconnect-at-s must be smaller than --duration-s")
    return args


def main() -> int:
    args = _parse_args()
    configure_qt_runtime()

    min_observed_duration_s = args.min_observed_duration_s
    if min_observed_duration_s <= 0.0:
        min_observed_duration_s = max(0.0, args.duration_s - args.reconnect_timeout_s)

    recording_dir = Path(args.recording_dir) if args.recording_dir else None
    if recording_dir is None:
        recording_dir = Path(tempfile.mkdtemp(prefix="zss_gui_ble_probe_"))
    recording_dir.mkdir(parents=True, exist_ok=True)

    backend_patch: tuple[object, object] | None = None
    if args.use_fake_live:
        import mock_backend as backend_module
        from ble_backend_smoke import FakeBleakClient

        backend_patch = (backend_module.BleakClient, backend_module.BleakScanner)
        backend_module.BleakClient = FakeBleakClient
        backend_module.BleakScanner = FakeBleakScanner

    try:
        app = QApplication(sys.argv)
        app.setOrganizationName(APP_ORGANIZATION)
        app.setApplicationName(APP_ID)
        app.setApplicationDisplayName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)

        window = MainWindow(BLE_MODE)
        original_recording_directory = window.app_settings.logging.recording_directory
        window.app_settings.logging.recording_directory = str(recording_dir)

        thresholds = ProbeThresholds(
            min_observed_duration_s=min_observed_duration_s,
            max_sequence_gap_total=args.max_sequence_gap_total,
            max_stall_warnings=args.max_stall_warnings,
            reconnect_timeout_s=args.reconnect_timeout_s,
        )
        probe = GuiBleSessionProbe(
            window=window,
            selected_prefix=args.device_prefix,
            exact_label=args.device_label,
            scan_timeout_s=args.scan_timeout_s,
            connect_timeout_s=args.connect_timeout_s,
            duration_s=args.duration_s,
            recording_duration_s=args.recording_duration_s,
            reconnect_at_s=args.reconnect_at_s,
            thresholds=thresholds,
            original_recording_directory=original_recording_directory,
        )
        QTimer.singleShot(0, probe.start)
        app.exec()

        if probe.failure_message is not None:
            print(f"gui_ble_session_probe_failed: {probe.failure_message}")
            print(f"recording_dir={recording_dir}")
            return 1

        summary = probe.result
        if summary is None:
            print("gui_ble_session_probe_failed: no result produced")
            print(f"recording_dir={recording_dir}")
            return 1

        print(f"Scanned devices: {summary.scanned_devices}")
        print(f"Selected device: {summary.selected_device_label}")
        print(f"Connect count: {summary.connect_count}")
        print(f"Disconnect count: {summary.disconnect_count}")
        print(f"Connected telemetry segments: {summary.connected_segment_count}")
        print(f"Capabilities events: {summary.capabilities_events}")
        print(f"Status events: {summary.status_events}")
        print(f"Telemetry samples observed: {summary.telemetry_count}")
        print(f"Observed BLE telemetry duration: {summary.total_observed_duration_s:0.2f} s")
        print(f"Sequence gap total: {summary.sequence_gap_total}")
        print(f"Max sequence gap: {summary.max_sequence_gap}")
        print(f"Sequence reset count: {summary.sequence_reset_count}")
        print(f"Warning logs observed: {summary.warning_count}")
        print(f"Error logs observed: {summary.error_count}")
        print(f"Stall warnings observed: {summary.stall_warning_count}")
        print(f"Pump command requests: {summary.pump_command_requests}")
        print(f"Pump ON status seen: {summary.pump_on_status_seen}")
        print(f"Pump OFF status seen: {summary.pump_off_status_seen}")
        print(f"Status requests: {summary.status_requests}")
        print(f"Ping requests: {summary.ping_requests}")
        print(f"Reconnect performed: {summary.reconnect_performed}")
        print(f"Reconnect recovered: {summary.reconnect_recovered}")
        print(f"Reconnect recovery s: {summary.reconnect_recovery_s}")
        print(f"Recording sessions completed: {summary.recording_sessions_completed}")
        print(f"CSV rows written: {summary.csv_rows}")
        print(f"CSV non-unit gaps: {summary.csv_non_unit_gaps}")
        print(f"Final recording: {summary.final_recording_path}")
        print(f"recording_dir={recording_dir}")
        print("gui_ble_session_probe_ok")
        return 0
    finally:
        if backend_patch is not None:
            import mock_backend as backend_module

            backend_module.BleakClient, backend_module.BleakScanner = backend_patch

if __name__ == "__main__":
    raise SystemExit(main())
