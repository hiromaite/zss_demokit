from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from protocol_constants import BLE_MODE

O2_FILTER_TYPE_SAVGOL = "Savitzky-Golay"
O2_FILTER_TYPE_CENTERED_GAUSSIAN = "Centered Gaussian"
O2_FILTER_TYPES = (
    O2_FILTER_TYPE_SAVGOL,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
)
# Legacy labels are kept only so existing QSettings values can migrate cleanly.
O2_FILTER_TYPE_EMA_1 = "EMA 1-pole"
O2_FILTER_TYPE_EMA_2 = "EMA 2-pole"
O2_FILTER_TYPE_GAUSSIAN = "One-sided Gaussian"
O2_FILTER_TYPE_SAVGOL_7 = "Savitzky-Golay 7-point"
O2_FILTER_TYPE_SAVGOL_9 = "Savitzky-Golay 9-point"
O2_FILTER_TYPE_CENTERED_GAUSSIAN_7 = "Centered Gaussian 7-point"

O2_FILTER_PRESET_FAST = "Fast"
O2_FILTER_PRESET_DEFAULT = "Default"
O2_FILTER_PRESET_QUIET = "Quiet"
O2_FILTER_PRESET_CUSTOM = "Custom"
O2_FILTER_PRESETS = (
    O2_FILTER_PRESET_FAST,
    O2_FILTER_PRESET_DEFAULT,
    O2_FILTER_PRESET_QUIET,
    O2_FILTER_PRESET_CUSTOM,
)
O2_FILTER_PRESET_BALANCED = O2_FILTER_PRESET_DEFAULT


@dataclass
class PlotPreferences:
    time_span: str = "2 min"
    axis_mode: str = "Relative"
    auto_scale: bool = True
    selected_plot: str = "Flow / O2"
    x_follow_enabled: bool = True
    series_visibility: dict[str, bool] = field(
        default_factory=lambda: {
            "flow": True,
            "o2": True,
            "heater": True,
            "zirconia": True,
        }
    )
    manual_y_ranges: dict[str, tuple[float, float]] = field(default_factory=dict)


@dataclass
class LoggingPreferences:
    recording_directory: str = ""
    partial_recovery_notice_enabled: bool = True


@dataclass
class O2CalibrationPreferences:
    zero_reference_voltage_v: float = 0.0
    ambient_reference_percent: float = 21.0
    air_calibration_voltage_v: float | None = None
    calibrated_at_iso: str = ""
    invert_polarity: bool = False


@dataclass
class O2OutputFilterPreferences:
    enabled: bool = True
    filter_type: str = O2_FILTER_TYPE_SAVGOL
    preset: str = O2_FILTER_PRESET_DEFAULT
    savgol_window_points: int = 9
    savgol_polynomial_order: int = 2
    centered_gaussian_window_points: int = 9
    centered_gaussian_sigma_samples: float = 1.75


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
    o2_filter: O2OutputFilterPreferences = field(default_factory=O2OutputFilterPreferences)
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
