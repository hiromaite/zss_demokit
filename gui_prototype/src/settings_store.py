from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QSettings

from app_state import AppSettings, LoggingPreferences, O2CalibrationPreferences, PlotPreferences, WindowPreferences
from protocol_constants import BLE_MODE
from recording_io import recording_directory


class SettingsStore:
    def __init__(self) -> None:
        self._settings = QSettings("zss-demokit", "gui-prototype")

    def load(self) -> AppSettings:
        settings = AppSettings()
        settings.last_mode = str(self._settings.value("mode/last_mode", BLE_MODE))
        selected_plot = self._normalize_selected_plot(
            str(self._settings.value("plot/selected_plot", settings.plot.selected_plot))
        )

        settings.plot = PlotPreferences(
            time_span=str(self._settings.value("plot/time_span", settings.plot.time_span)),
            axis_mode=str(self._settings.value("plot/axis_mode", settings.plot.axis_mode)),
            auto_scale=self._to_bool(self._settings.value("plot/auto_scale", settings.plot.auto_scale)),
            selected_plot=selected_plot,
            x_follow_enabled=self._to_bool(self._settings.value("plot/x_follow_enabled", settings.plot.x_follow_enabled)),
            manual_y_ranges=self._load_manual_ranges(),
        )

        default_recording_directory = str(recording_directory())
        settings.logging = LoggingPreferences(
            recording_directory=str(
                self._settings.value("logging/recording_directory", default_recording_directory)
            ),
            partial_recovery_notice_enabled=self._to_bool(
                self._settings.value("logging/partial_recovery_notice_enabled", True)
            ),
        )

        settings.o2 = O2CalibrationPreferences(
            zero_reference_voltage_v=self._to_float(
                self._settings.value("o2/zero_reference_voltage_v", 2.5),
                2.5,
            ),
            ambient_reference_percent=self._to_float(
                self._settings.value("o2/ambient_reference_percent", 21.0),
                21.0,
            ),
            air_calibration_voltage_v=self._to_optional_float(
                self._settings.value("o2/air_calibration_voltage_v", "")
            ),
            calibrated_at_iso=str(self._settings.value("o2/calibrated_at_iso", "")),
            invert_polarity=self._to_bool(self._settings.value("o2/invert_polarity", False)),
        )

        settings.windows = WindowPreferences(
            main_window_width=int(self._settings.value("windows/main_window_width", settings.windows.main_window_width)),
            main_window_height=int(self._settings.value("windows/main_window_height", settings.windows.main_window_height)),
            launcher_window_width=int(
                self._settings.value("windows/launcher_window_width", settings.windows.launcher_window_width)
            ),
            launcher_window_height=int(
                self._settings.value("windows/launcher_window_height", settings.windows.launcher_window_height)
            ),
        )
        return settings

    def save(self, settings: AppSettings) -> None:
        self._settings.setValue("mode/last_mode", settings.last_mode)
        self._settings.setValue("plot/time_span", settings.plot.time_span)
        self._settings.setValue("plot/axis_mode", settings.plot.axis_mode)
        self._settings.setValue("plot/auto_scale", settings.plot.auto_scale)
        self._settings.setValue("plot/selected_plot", settings.plot.selected_plot)
        self._settings.setValue("plot/x_follow_enabled", settings.plot.x_follow_enabled)
        self._settings.setValue("plot/manual_y_ranges", json.dumps(self._normalize_ranges(settings.plot.manual_y_ranges)))
        self._settings.setValue("logging/recording_directory", settings.logging.recording_directory)
        self._settings.setValue(
            "logging/partial_recovery_notice_enabled",
            settings.logging.partial_recovery_notice_enabled,
        )
        self._settings.setValue("o2/zero_reference_voltage_v", settings.o2.zero_reference_voltage_v)
        self._settings.setValue("o2/ambient_reference_percent", settings.o2.ambient_reference_percent)
        self._settings.setValue(
            "o2/air_calibration_voltage_v",
            "" if settings.o2.air_calibration_voltage_v is None else settings.o2.air_calibration_voltage_v,
        )
        self._settings.setValue("o2/calibrated_at_iso", settings.o2.calibrated_at_iso)
        self._settings.setValue("o2/invert_polarity", settings.o2.invert_polarity)
        self._settings.setValue("windows/main_window_width", settings.windows.main_window_width)
        self._settings.setValue("windows/main_window_height", settings.windows.main_window_height)
        self._settings.setValue("windows/launcher_window_width", settings.windows.launcher_window_width)
        self._settings.setValue("windows/launcher_window_height", settings.windows.launcher_window_height)
        self._settings.sync()

    def recording_directory_path(self, settings: AppSettings) -> Path:
        raw_value = settings.logging.recording_directory.strip()
        return Path(raw_value) if raw_value else recording_directory()

    @staticmethod
    def _to_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def _to_float(value: object, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_optional_float(value: object) -> float | None:
        if value in {"", None}:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _load_manual_ranges(self) -> dict[str, tuple[float, float]]:
        raw = self._settings.value("plot/manual_y_ranges", "")
        if not raw:
            return {}
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}

        manual_ranges: dict[str, tuple[float, float]] = {}
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if isinstance(value, list) and len(value) == 2:
                    try:
                        normalized_key = self._normalize_plot_key(str(key))
                        manual_ranges[normalized_key] = (float(value[0]), float(value[1]))
                    except (TypeError, ValueError):
                        continue
        return manual_ranges

    @staticmethod
    def _normalize_ranges(ranges: dict[str, tuple[float, float]]) -> dict[str, list[float]]:
        normalized: dict[str, list[float]] = {}
        for key, value in ranges.items():
            normalized[key] = [float(value[0]), float(value[1])]
        return normalized

    @staticmethod
    def _normalize_plot_key(plot_key: str) -> str:
        if plot_key in {"zirconia", "flow", "sensor"}:
            return "sensor"
        if plot_key == "heater":
            return "heater"
        return plot_key

    @staticmethod
    def _normalize_selected_plot(plot_label: str) -> str:
        if plot_label in {"Zirconia", "Flow", "Sensor / Flow"}:
            return "Sensor / Flow"
        if plot_label == "Heater":
            return "Heater"
        return "Sensor / Flow"
