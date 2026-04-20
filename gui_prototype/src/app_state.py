from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from protocol_constants import BLE_MODE


@dataclass
class PlotPreferences:
    time_span: str = "2 min"
    axis_mode: str = "Relative"
    auto_scale: bool = True
    selected_plot: str = "Sensor / Flow"
    x_follow_enabled: bool = True
    manual_y_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class LoggingPreferences:
    recording_directory: str = ""
    partial_recovery_notice_enabled: bool = True


@dataclass
class O2CalibrationPreferences:
    zero_reference_voltage_v: float = 2.5
    ambient_reference_percent: float = 21.0
    air_calibration_voltage_v: float | None = None
    calibrated_at_iso: str = ""
    invert_polarity: bool = False


@dataclass
class WindowPreferences:
    main_window_width: int = 1480
    main_window_height: int = 940
    launcher_window_width: int = 880
    launcher_window_height: int = 600


@dataclass
class AppSettings:
    last_mode: str = BLE_MODE
    plot: PlotPreferences = field(default_factory=PlotPreferences)
    logging: LoggingPreferences = field(default_factory=LoggingPreferences)
    o2: O2CalibrationPreferences = field(default_factory=O2CalibrationPreferences)
    windows: WindowPreferences = field(default_factory=WindowPreferences)


@dataclass
class ConnectionState:
    phase: str = "disconnected"
    identifier: str = "Disconnected"


@dataclass
class RecordingState:
    phase: str = "idle"
    session_id: str = ""
    current_file: str = ""
    started_at: datetime | None = None


@dataclass
class SessionMetadata:
    firmware_version: str = "--"
    protocol_version: str = "--"
    nominal_sample_period_ms: str = "--"
    device_type: str = "zirconia_sensor"
    transport_type: str = ""


@dataclass
class AppUiState:
    mode: str = BLE_MODE
    connection: ConnectionState = field(default_factory=ConnectionState)
    recording: RecordingState = field(default_factory=RecordingState)
    session_metadata: SessionMetadata = field(default_factory=SessionMetadata)
