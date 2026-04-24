from __future__ import annotations

import math
import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TextIO

from PySide6.QtCore import QObject, Signal

from mock_backend import TelemetryPoint
from protocol_constants import (
    BLE_MODE,
    DERIVED_METRIC_POLICY_ID,
    STATUS_FLAG_HEATER_POWER_ON,
    STATUS_FLAG_PUMP_ON,
    derive_flow_rate_lpm_from_selected_differential_pressure_pa,
    format_status_flags,
    infer_differential_pressure_selected_source,
)
from recording_io import create_recording_paths, write_csv_header


@dataclass(frozen=True)
class LogEntry:
    timestamp: datetime
    severity: str
    message: str


class WarningController:
    def __init__(self, max_entries: int = 500) -> None:
        self._entries: deque[LogEntry] = deque(maxlen=max_entries)
        self.warning_count = 0

    def append(self, severity: str, message: str) -> LogEntry:
        entry = LogEntry(timestamp=datetime.now(), severity=severity, message=message)
        self._entries.append(entry)
        if severity in {"warn", "error"}:
            self.warning_count += 1
        return entry

    def entries(self) -> list[LogEntry]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()
        self.warning_count = 0


class ConnectionController(QObject):
    connection_changed = Signal(bool, str)
    status_changed = Signal(object)
    capabilities_changed = Signal(object)
    telemetry_received = Signal(object)
    log_generated = Signal(str, str)
    ble_devices_discovered = Signal(list)
    ports_discovered = Signal(list)

    def __init__(self, backend: QObject, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._bind_backend()

    @property
    def backend(self) -> QObject:
        return self._backend

    def _bind_backend(self) -> None:
        self._backend.connection_changed.connect(self.connection_changed)
        self._backend.status_changed.connect(self.status_changed)
        self._backend.capabilities_changed.connect(self.capabilities_changed)
        self._backend.telemetry_generated.connect(self.telemetry_received)
        self._backend.log_generated.connect(self.log_generated)
        self._backend.ble_devices_discovered.connect(self.ble_devices_discovered)
        self._backend.ports_discovered.connect(self.ports_discovered)

    def is_connected(self) -> bool:
        return bool(self._backend.is_connected())

    def current_mode(self) -> str:
        return str(self._backend.mode)

    def set_mode(self, mode: str) -> None:
        self._backend.set_mode(mode)

    def scan_ble_devices(self) -> None:
        self._backend.scan_ble_devices()

    def refresh_ports(self) -> None:
        self._backend.refresh_ports()

    def connect_device(self, identifier: str) -> None:
        self._backend.connect_device(identifier)

    def disconnect_device(self) -> None:
        self._backend.disconnect_device()

    def set_pump_state(self, on: bool) -> None:
        self._backend.set_pump_state(on)

    def set_heater_power_state(self, on: bool) -> None:
        self._backend.set_heater_power_state(on)

    def request_status(self) -> None:
        self._backend.request_status()

    def request_capabilities(self) -> None:
        self._backend.request_capabilities()

    def ping(self) -> None:
        self._backend.ping()


class PlotController:
    def __init__(self, history_window_s: float = 1800.0) -> None:
        self.history_window_s = history_window_s
        self.time_values: deque[float] = deque()
        self.zirconia_values: deque[float] = deque()
        self.heater_values: deque[float] = deque()
        self.differential_pressure_selected_values: deque[float] = deque()
        self.flow_rate_values: deque[float] = deque()
        self.last_sequence: int | None = None
        self.plot_sequence_origin: int | None = None
        self.sequence_gap_total = 0
        self.x_follow_enabled = True
        self.manual_y_ranges: dict[str, tuple[float, float]] = {}

    def append_sample(self, point: TelemetryPoint) -> dict[str, object]:
        if self.plot_sequence_origin is None:
            self.plot_sequence_origin = point.sequence

        elapsed = ((point.sequence - self.plot_sequence_origin) * point.nominal_sample_period_ms) / 1000.0
        differential_pressure_selected_pa = point.differential_pressure_selected_pa
        flow_rate = derive_flow_rate_lpm_from_selected_differential_pressure_pa(
            differential_pressure_selected_pa,
        )

        self.time_values.append(elapsed)
        self.zirconia_values.append(point.zirconia_output_voltage_v)
        self.heater_values.append(point.heater_rtd_resistance_ohm)
        self.differential_pressure_selected_values.append(
            differential_pressure_selected_pa if differential_pressure_selected_pa is not None else math.nan
        )
        self.flow_rate_values.append(flow_rate)
        self._trim_history(elapsed)

        sequence_gap = 0
        if self.last_sequence is not None and point.sequence != self.last_sequence + 1:
            sequence_gap = max(0, point.sequence - self.last_sequence - 1)
            self.sequence_gap_total += sequence_gap
        self.last_sequence = point.sequence

        return {
            "elapsed_seconds": elapsed,
            "flow_rate_lpm": flow_rate,
            "sequence_gap": sequence_gap,
            "sequence_gap_total": self.sequence_gap_total,
        }

    def clear(self) -> None:
        self.time_values.clear()
        self.zirconia_values.clear()
        self.heater_values.clear()
        self.differential_pressure_selected_values.clear()
        self.flow_rate_values.clear()
        self.last_sequence = None
        self.plot_sequence_origin = None
        self.sequence_gap_total = 0
        self.x_follow_enabled = True

    def history_duration_s(self) -> float:
        if len(self.time_values) < 2:
            return 0.0
        return self.time_values[-1] - self.time_values[0]

    def metric_snapshot(self) -> dict[str, float]:
        if not self.time_values:
            return {}
        return {
            "zirconia_output_voltage_v": self.zirconia_values[-1],
            "heater_rtd_resistance_ohm": self.heater_values[-1],
            "flow_rate_lpm": self.flow_rate_values[-1],
        }

    def render_data(self, time_span: str) -> dict[str, object]:
        if not self.time_values:
            return {
                "x_values": [],
                "series": {"zirconia": [], "heater": [], "flow": []},
                "xmin": 0.0,
                "xmax": 0.0,
            }

        span_map = {"30 s": 30.0, "2 min": 120.0, "10 min": 600.0}
        max_render_points = {"30 s": 3000, "2 min": 4000, "10 min": 6000, "All": 8000}
        span = span_map.get(time_span)
        x_latest = self.time_values[-1]
        if span is None:
            xmin = self.time_values[0]
            xmax = x_latest
            x_values, zirconia_values, heater_values, flow_values = self._extract_visible_series()
        else:
            xmax = x_latest
            xmin = max(0.0, xmax - span)
            x_values, zirconia_values, heater_values, flow_values = self._extract_visible_series(cutoff=xmin)

        x_values, zirconia_values, heater_values, flow_values = self._downsample_series(
            x_values,
            zirconia_values,
            heater_values,
            flow_values,
            max_points=max_render_points.get(time_span, 8000),
        )

        return {
            "x_values": x_values,
            "series": {
                "zirconia": zirconia_values,
                "heater": heater_values,
                "flow": flow_values,
            },
            "xmin": xmin,
            "xmax": xmax,
        }

    def set_manual_y_range(self, plot_key: str, y_min: float, y_max: float) -> None:
        self.manual_y_ranges[plot_key] = (y_min, y_max)

    def manual_y_range_for(self, plot_key: str) -> tuple[float, float] | None:
        return self.manual_y_ranges.get(plot_key)

    def _trim_history(self, latest_elapsed: float) -> None:
        cutoff = latest_elapsed - self.history_window_s
        if cutoff <= 0:
            return
        while self.time_values and self.time_values[0] < cutoff:
            self.time_values.popleft()
            self.zirconia_values.popleft()
            self.heater_values.popleft()
            self.differential_pressure_selected_values.popleft()
            self.flow_rate_values.popleft()

    def _extract_visible_series(
        self,
        *,
        cutoff: float | None = None,
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        if cutoff is None:
            return (
                list(self.time_values),
                list(self.zirconia_values),
                list(self.heater_values),
                list(self.flow_rate_values),
            )

        x_values_reversed: list[float] = []
        zirconia_reversed: list[float] = []
        heater_reversed: list[float] = []
        flow_reversed: list[float] = []
        for elapsed, zirconia, heater, flow in zip(
            reversed(self.time_values),
            reversed(self.zirconia_values),
            reversed(self.heater_values),
            reversed(self.flow_rate_values),
        ):
            if elapsed < cutoff:
                break
            x_values_reversed.append(elapsed)
            zirconia_reversed.append(zirconia)
            heater_reversed.append(heater)
            flow_reversed.append(flow)

        x_values_reversed.reverse()
        zirconia_reversed.reverse()
        heater_reversed.reverse()
        flow_reversed.reverse()
        return x_values_reversed, zirconia_reversed, heater_reversed, flow_reversed

    @staticmethod
    def _downsample_series(
        x_values: list[float],
        zirconia_values: list[float],
        heater_values: list[float],
        flow_values: list[float],
        *,
        max_points: int,
    ) -> tuple[list[float], list[float], list[float], list[float]]:
        if len(x_values) <= max_points:
            return x_values, zirconia_values, heater_values, flow_values

        step = max(1, math.ceil(len(x_values) / max_points))
        x_values = x_values[::step]
        zirconia_values = zirconia_values[::step]
        heater_values = heater_values[::step]
        flow_values = flow_values[::step]
        return x_values, zirconia_values, heater_values, flow_values


class TelemetryHealthMonitor:
    def __init__(self, mode: str, nominal_sample_period_ms: int | None = None) -> None:
        self.mode = mode
        self.nominal_sample_period_ms = nominal_sample_period_ms or (80 if mode == BLE_MODE else 10)
        self.reset()

    def reset(self) -> None:
        self.connected = False
        self.identifier = "Disconnected"
        self.connected_at: datetime | None = None
        self.last_telemetry_at: datetime | None = None
        self.last_sequence: int | None = None
        self.waiting_warning_emitted = False
        self.stall_warning_emitted = False

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.nominal_sample_period_ms = 80 if mode == BLE_MODE else 10
        self.reset()

    def update_nominal_sample_period(self, nominal_sample_period_ms: int | str) -> None:
        try:
            parsed = int(nominal_sample_period_ms)
        except (TypeError, ValueError):
            return
        if parsed > 0:
            self.nominal_sample_period_ms = parsed

    def on_connection_changed(self, connected: bool, identifier: str) -> list[tuple[str, str]]:
        if connected:
            self.connected = True
            self.identifier = identifier
            self.connected_at = datetime.now()
            self.last_telemetry_at = None
            self.last_sequence = None
            self.waiting_warning_emitted = False
            self.stall_warning_emitted = False
            return []

        had_stall = self.stall_warning_emitted
        self.reset()
        logs: list[tuple[str, str]] = []
        if had_stall:
            logs.append(("info", "Telemetry monitoring reset after disconnect."))
        return logs

    def on_telemetry(self, point: TelemetryPoint) -> list[tuple[str, str]]:
        logs: list[tuple[str, str]] = []
        if self.stall_warning_emitted:
            logs.append(("info", "Telemetry stream recovered."))
            self.stall_warning_emitted = False

        if self.last_sequence is not None and point.sequence > self.last_sequence + 1:
            gap = point.sequence - self.last_sequence - 1
            logs.append(("warn", f"Telemetry sequence gap observed: {gap} sample(s) missing."))

        self.last_telemetry_at = point.host_received_at
        self.last_sequence = point.sequence
        self.waiting_warning_emitted = True
        return logs

    def poll(self, now: datetime | None = None) -> list[tuple[str, str]]:
        if not self.connected:
            return []

        now = now or datetime.now()
        logs: list[tuple[str, str]] = []

        if self.last_telemetry_at is None and self.connected_at is not None:
            if not self.waiting_warning_emitted and now - self.connected_at >= self._first_sample_timeout():
                self.waiting_warning_emitted = True
                logs.append(("warn", "Telemetry has not started within the expected time window."))
            return logs

        if self.last_telemetry_at is not None and not self.stall_warning_emitted:
            if now - self.last_telemetry_at >= self._stall_timeout():
                self.stall_warning_emitted = True
                logs.append(("warn", "Telemetry stream appears stalled."))

        return logs

    def _first_sample_timeout(self) -> timedelta:
        seconds = max(2.0, (self.nominal_sample_period_ms * 20) / 1000.0)
        return timedelta(seconds=seconds)

    def _stall_timeout(self) -> timedelta:
        seconds = max(0.75, (self.nominal_sample_period_ms * 12) / 1000.0)
        return timedelta(seconds=seconds)


class TelemetrySessionStats:
    def __init__(self, mode: str, nominal_sample_period_ms: int | None = None) -> None:
        self.mode = mode
        self.nominal_sample_period_ms = nominal_sample_period_ms or (80 if mode == BLE_MODE else 10)
        self.reset()

    def reset(self) -> None:
        self.connected = False
        self.identifier = "Disconnected"
        self.connected_at: datetime | None = None
        self.first_telemetry_at: datetime | None = None
        self.last_telemetry_at: datetime | None = None
        self.first_sequence: int | None = None
        self.last_sequence: int | None = None
        self.sample_count = 0
        self.sequence_gap_total = 0
        self.max_sequence_gap = 0
        self.inter_arrival_count = 0
        self.inter_arrival_total_ms = 0.0
        self.max_inter_arrival_ms = 0.0

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.nominal_sample_period_ms = 80 if mode == BLE_MODE else 10
        self.reset()

    def update_nominal_sample_period(self, nominal_sample_period_ms: int | str) -> None:
        try:
            parsed = int(nominal_sample_period_ms)
        except (TypeError, ValueError):
            return
        if parsed > 0:
            self.nominal_sample_period_ms = parsed

    def on_connection_changed(self, connected: bool, identifier: str) -> list[tuple[str, str]]:
        if connected:
            self.reset()
            self.connected = True
            self.identifier = identifier
            self.connected_at = datetime.now()
            return []

        logs: list[tuple[str, str]] = []
        if self.sample_count > 0:
            logs.append(("info", self.summary_message()))
        self.reset()
        return logs

    def on_telemetry(self, point: TelemetryPoint) -> None:
        if self.sample_count == 0:
            self.first_telemetry_at = point.host_received_at
            self.first_sequence = point.sequence
        elif self.last_telemetry_at is not None:
            inter_arrival_ms = (point.host_received_at - self.last_telemetry_at).total_seconds() * 1000.0
            self.inter_arrival_count += 1
            self.inter_arrival_total_ms += inter_arrival_ms
            self.max_inter_arrival_ms = max(self.max_inter_arrival_ms, inter_arrival_ms)

        if self.last_sequence is not None and point.sequence > self.last_sequence + 1:
            gap = point.sequence - self.last_sequence - 1
            self.sequence_gap_total += gap
            self.max_sequence_gap = max(self.max_sequence_gap, gap)

        self.sample_count += 1
        self.last_sequence = point.sequence
        self.last_telemetry_at = point.host_received_at

    def duration_s(self) -> float:
        if self.first_telemetry_at is None or self.last_telemetry_at is None:
            return 0.0
        return max(0.0, (self.last_telemetry_at - self.first_telemetry_at).total_seconds())

    def mean_inter_arrival_ms(self) -> float:
        if self.inter_arrival_count <= 0:
            return 0.0
        return self.inter_arrival_total_ms / self.inter_arrival_count

    def summary_message(self) -> str:
        duration_s = self.duration_s()
        mean_inter_arrival_ms = self.mean_inter_arrival_ms()
        first_sequence = self.first_sequence if self.first_sequence is not None else 0
        last_sequence = self.last_sequence if self.last_sequence is not None else 0
        return (
            "Telemetry session summary: "
            f"samples={self.sample_count}, "
            f"duration={duration_s:0.1f}s, "
            f"seq={first_sequence}->{last_sequence}, "
            f"gap_total={self.sequence_gap_total}, "
            f"max_gap={self.max_sequence_gap}, "
            f"mean_inter_arrival_ms={mean_inter_arrival_ms:0.3f}, "
            f"max_inter_arrival_ms={self.max_inter_arrival_ms:0.3f}"
        )


class RecordingController:
    def __init__(self) -> None:
        self._recording_file: TextIO | None = None
        self._csv_writer: csv.writer | None = None
        self._pending_rows = 0
        self._last_sequence: int | None = None
        self._last_received_at: datetime | None = None
        self._last_device_sample_tick_us: int | None = None
        self.session_id = ""
        self.started_at: datetime | None = None
        self.recording_path: Path | None = None
        self.partial_path: Path | None = None
        self.is_recording = False

    def start(
        self,
        *,
        base_dir: Path,
        gui_app_name: str,
        gui_app_version: str,
        mode: str,
        transport_type: str,
        device_identifier: str,
        firmware_version: str,
        protocol_version: str,
        nominal_sample_period_ms: str,
        source_endpoint: str,
    ) -> None:
        base_dir.mkdir(parents=True, exist_ok=True)
        started_at = datetime.now()
        paths = create_recording_paths(base_dir, started_at)
        session_id = started_at.strftime("%Y%m%d_%H%M%S_run01")
        file_obj = paths.partial_path.open("w", newline="", encoding="utf-8")
        write_csv_header(
            file_obj,
            exported_at=started_at,
            gui_app_name=gui_app_name,
            gui_app_version=gui_app_version,
            session_id=session_id,
            mode=mode,
            transport_type=transport_type,
            device_type="zirconia_sensor",
            device_identifier=device_identifier,
            firmware_version=firmware_version,
            protocol_version=protocol_version,
            nominal_sample_period_ms=nominal_sample_period_ms,
            derived_metric_policy=DERIVED_METRIC_POLICY_ID,
            source_endpoint=source_endpoint,
        )
        self._recording_file = file_obj
        self._csv_writer = csv.writer(file_obj)
        self._pending_rows = 0
        self._last_sequence = None
        self._last_received_at = None
        self._last_device_sample_tick_us = None
        self.session_id = session_id
        self.started_at = started_at
        self.recording_path = paths.recording_path
        self.partial_path = paths.partial_path
        self.is_recording = True

    def append_row(
        self,
        *,
        point: TelemetryPoint,
        mode: str,
        transport_type: str,
    ) -> float:
        if self._csv_writer is None:
            return derive_flow_rate_lpm_from_selected_differential_pressure_pa(
                point.differential_pressure_selected_pa,
            )

        flow_rate_lpm = derive_flow_rate_lpm_from_selected_differential_pressure_pa(
            point.differential_pressure_selected_pa,
        )
        differential_pressure_selected_source = infer_differential_pressure_selected_source(
            point.differential_pressure_selected_pa,
            point.differential_pressure_low_range_pa,
            point.differential_pressure_high_range_pa,
        )
        host_received_at = point.host_received_at.astimezone()
        host_received_unix_ms = int(point.host_received_at.timestamp() * 1000)
        if self._last_sequence is None:
            sequence_gap = 0
        else:
            sequence_gap = max(0, point.sequence - self._last_sequence - 1)

        host_inter_arrival_ms = ""
        if self._last_received_at is not None:
            host_inter_arrival_ms = f"{(point.host_received_at - self._last_received_at).total_seconds() * 1000.0:.3f}"

        device_inter_arrival_ms = ""
        if (
            point.device_sample_tick_us is not None and
            self._last_device_sample_tick_us is not None
        ):
            delta_us = (point.device_sample_tick_us - self._last_device_sample_tick_us) & 0xFFFFFFFF
            device_inter_arrival_ms = f"{(delta_us / 1000.0):.3f}"

        inter_arrival_ms = device_inter_arrival_ms or host_inter_arrival_ms

        row = [
            host_received_at.isoformat(timespec="milliseconds"),
            str(host_received_unix_ms),
            mode,
            transport_type,
            str(point.sequence),
            str(sequence_gap),
            inter_arrival_ms,
            host_inter_arrival_ms,
            device_inter_arrival_ms,
            str(point.device_sample_tick_us) if point.device_sample_tick_us is not None else "",
            str(point.nominal_sample_period_ms),
            format_status_flags(point.status_flags),
            str(1 if (point.status_flags & STATUS_FLAG_PUMP_ON) != 0 else 0),
            str(1 if (point.status_flags & STATUS_FLAG_HEATER_POWER_ON) != 0 else 0),
            f"{point.zirconia_output_voltage_v:.6f}",
            f"{point.heater_rtd_resistance_ohm:.6f}",
            (
                f"{point.zirconia_ip_voltage_v:.6f}"
                if point.zirconia_ip_voltage_v is not None
                else ""
            ),
            (
                f"{point.internal_voltage_v:.6f}"
                if point.internal_voltage_v is not None
                else ""
            ),
            (
                f"{point.differential_pressure_selected_pa:.6f}"
                if point.differential_pressure_selected_pa is not None
                else ""
            ),
            differential_pressure_selected_source,
            (
                f"{point.differential_pressure_low_range_pa:.6f}"
                if point.differential_pressure_low_range_pa is not None
                else ""
            ),
            (
                f"{point.differential_pressure_high_range_pa:.6f}"
                if point.differential_pressure_high_range_pa is not None
                else ""
            ),
            f"{flow_rate_lpm:.6f}",
        ]
        self._csv_writer.writerow(row)
        self._pending_rows += 1
        self._last_sequence = point.sequence
        self._last_received_at = point.host_received_at
        self._last_device_sample_tick_us = point.device_sample_tick_us
        return flow_rate_lpm

    def should_flush(self, row_threshold: int) -> bool:
        return self._pending_rows >= row_threshold

    def flush(self) -> None:
        if self._recording_file is None or self._pending_rows <= 0:
            return
        self._recording_file.flush()
        self._pending_rows = 0

    def stop(self) -> Path | None:
        self.flush()
        final_path = self.recording_path
        partial_path = self.partial_path
        if self._recording_file is not None:
            self._recording_file.close()

        if partial_path is not None and final_path is not None:
            partial_path.replace(final_path)

        self._recording_file = None
        self._csv_writer = None
        self._pending_rows = 0
        self._last_sequence = None
        self._last_received_at = None
        self.started_at = None
        self.partial_path = None
        self.recording_path = None
        self.is_recording = False
        return final_path

    def abort(self) -> None:
        self.flush()
        if self._recording_file is not None:
            self._recording_file.close()
        self._recording_file = None
        self._csv_writer = None
        self._pending_rows = 0
        self._last_sequence = None
        self._last_received_at = None
        self.started_at = None
        self.partial_path = None
        self.recording_path = None
        self.is_recording = False
