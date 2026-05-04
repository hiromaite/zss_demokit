from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QSettings

from app_state import (
    AppSettings,
    LoggingPreferences,
    O2CalibrationPreferences,
    O2OutputFilterPreferences,
    PlotPreferences,
    STARTUP_MODE_BLE,
    STARTUP_MODE_SELECTOR,
    STARTUP_MODES,
    WindowPreferences,
)
from o2_filter import normalize_o2_filter_preferences
from protocol_constants import BLE_MODE, O2_ZERO_REFERENCE_V
from recording_io import recording_directory


class SettingsStore:
    def __init__(self) -> None:
        settings_file = os.environ.get("ZSS_DEMOKIT_SETTINGS_FILE", "").strip()
        if settings_file:
            self._settings = QSettings(settings_file, QSettings.IniFormat)
        else:
            self._settings = QSettings("zss-demokit", "gui-prototype")

    def load(self) -> AppSettings:
        settings = AppSettings()
        settings.last_mode = str(self._settings.value("mode/last_mode", BLE_MODE))
        settings.startup_mode = self._normalize_startup_mode(
            str(self._settings.value("mode/startup_mode", STARTUP_MODE_SELECTOR))
        )
        selected_plot = self._normalize_selected_plot(
            str(self._settings.value("plot/selected_plot", settings.plot.selected_plot))
        )

        settings.plot = PlotPreferences(
            time_span=str(self._settings.value("plot/time_span", settings.plot.time_span)),
            axis_mode=str(self._settings.value("plot/axis_mode", settings.plot.axis_mode)),
            auto_scale=self._to_bool(self._settings.value("plot/auto_scale", settings.plot.auto_scale)),
            selected_plot=selected_plot,
            x_follow_enabled=self._to_bool(self._settings.value("plot/x_follow_enabled", settings.plot.x_follow_enabled)),
            series_visibility=self._load_series_visibility(settings.plot.series_visibility),
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

        zero_reference_voltage_v = self._to_float(
            self._settings.value("o2/zero_reference_voltage_v", O2_ZERO_REFERENCE_V),
            O2_ZERO_REFERENCE_V,
        )
        zero_reference_default_migrated = self._to_bool(
            self._settings.value("o2/zero_reference_default_migrated_to_2_55", False)
        )
        if (
            not zero_reference_default_migrated
            and self._is_legacy_default_o2_zero_reference(zero_reference_voltage_v)
        ):
            zero_reference_voltage_v = O2_ZERO_REFERENCE_V
        air_calibration_voltage_v = self._to_optional_float(
            self._settings.value("o2/air_calibration_voltage_v", "")
        )
        calibrated_at_iso = str(self._settings.value("o2/calibrated_at_iso", "")).strip()
        if air_calibration_voltage_v is not None and not calibrated_at_iso:
            air_calibration_voltage_v = None

        settings.o2 = O2CalibrationPreferences(
            zero_reference_voltage_v=zero_reference_voltage_v,
            ambient_reference_percent=self._to_float(
                self._settings.value("o2/ambient_reference_percent", 21.0),
                21.0,
            ),
            air_calibration_voltage_v=air_calibration_voltage_v,
            calibrated_at_iso=calibrated_at_iso,
            invert_polarity=self._to_bool(self._settings.value("o2/invert_polarity", False)),
        )
        settings.o2_filter = normalize_o2_filter_preferences(
            O2OutputFilterPreferences(
                enabled=self._to_bool(self._settings.value("o2_filter/enabled", True)),
                filter_type=str(
                    self._settings.value(
                        "o2_filter/filter_type",
                        settings.o2_filter.filter_type,
                    )
                ),
                preset=str(
                    self._settings.value(
                        "o2_filter/preset",
                        settings.o2_filter.preset,
                    )
                ),
                savgol_window_points=self._to_int(
                    self._settings.value(
                        "o2_filter/savgol_window_points",
                        settings.o2_filter.savgol_window_points,
                    ),
                    settings.o2_filter.savgol_window_points,
                ),
                savgol_polynomial_order=self._to_int(
                    self._settings.value(
                        "o2_filter/savgol_polynomial_order",
                        settings.o2_filter.savgol_polynomial_order,
                    ),
                    settings.o2_filter.savgol_polynomial_order,
                ),
                centered_gaussian_window_points=self._to_int(
                    self._settings.value(
                        "o2_filter/centered_gaussian_window_points",
                        settings.o2_filter.centered_gaussian_window_points,
                    ),
                    settings.o2_filter.centered_gaussian_window_points,
                ),
                centered_gaussian_sigma_samples=self._to_float(
                    self._settings.value(
                        "o2_filter/centered_gaussian_sigma_samples",
                        settings.o2_filter.centered_gaussian_sigma_samples,
                    ),
                    settings.o2_filter.centered_gaussian_sigma_samples,
                ),
            )
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
        self._settings.setValue(
            "mode/startup_mode",
            self._normalize_startup_mode(settings.startup_mode),
        )
        self._settings.setValue("plot/time_span", settings.plot.time_span)
        self._settings.setValue("plot/axis_mode", settings.plot.axis_mode)
        self._settings.setValue("plot/auto_scale", settings.plot.auto_scale)
        self._settings.setValue("plot/selected_plot", settings.plot.selected_plot)
        self._settings.setValue("plot/x_follow_enabled", settings.plot.x_follow_enabled)
        self._settings.setValue(
            "plot/series_visibility",
            json.dumps(self._normalize_series_visibility(settings.plot.series_visibility)),
        )
        self._settings.setValue("plot/manual_y_ranges", json.dumps(self._normalize_ranges(settings.plot.manual_y_ranges)))
        self._settings.setValue("logging/recording_directory", settings.logging.recording_directory)
        self._settings.setValue(
            "logging/partial_recovery_notice_enabled",
            settings.logging.partial_recovery_notice_enabled,
        )
        self._settings.setValue("o2/zero_reference_voltage_v", settings.o2.zero_reference_voltage_v)
        self._settings.setValue("o2/zero_reference_default_migrated_to_2_55", True)
        self._settings.setValue("o2/ambient_reference_percent", settings.o2.ambient_reference_percent)
        self._settings.setValue(
            "o2/air_calibration_voltage_v",
            "" if settings.o2.air_calibration_voltage_v is None else settings.o2.air_calibration_voltage_v,
        )
        self._settings.setValue("o2/calibrated_at_iso", settings.o2.calibrated_at_iso)
        self._settings.setValue("o2/invert_polarity", settings.o2.invert_polarity)
        o2_filter = normalize_o2_filter_preferences(settings.o2_filter)
        self._settings.setValue("o2_filter/enabled", o2_filter.enabled)
        self._settings.setValue("o2_filter/filter_type", o2_filter.filter_type)
        self._settings.setValue("o2_filter/preset", o2_filter.preset)
        self._settings.setValue("o2_filter/savgol_window_points", o2_filter.savgol_window_points)
        self._settings.setValue("o2_filter/savgol_polynomial_order", o2_filter.savgol_polynomial_order)
        self._settings.setValue(
            "o2_filter/centered_gaussian_window_points",
            o2_filter.centered_gaussian_window_points,
        )
        self._settings.setValue(
            "o2_filter/centered_gaussian_sigma_samples",
            o2_filter.centered_gaussian_sigma_samples,
        )
        for legacy_key in (
            "o2_filter/ema_cutoff_hz",
            "o2_filter/gaussian_sigma_ms",
            "o2_filter/gaussian_tail_sigma",
        ):
            self._settings.remove(legacy_key)
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
    def _to_int(value: object, default: int) -> int:
        try:
            return int(round(float(value)))
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

    @staticmethod
    def _normalize_startup_mode(value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {STARTUP_MODE_BLE, "ble_mode", "ble startup", "open_ble"}:
            return STARTUP_MODE_BLE
        if normalized in STARTUP_MODES:
            return normalized
        return STARTUP_MODE_SELECTOR

    @staticmethod
    def _is_legacy_default_o2_zero_reference(value: float) -> bool:
        # Earlier beta builds used either 0.0 V or 2.5 V as a default anchor.
        # Treat exact legacy defaults as defaults, not as user-specific calibration.
        return abs(value - 0.0) < 1e-9 or abs(value - 2.5) < 1e-9

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

    def _load_series_visibility(self, defaults: dict[str, bool]) -> dict[str, bool]:
        visibility = dict(defaults)
        raw = self._settings.value("plot/series_visibility", "")
        if not raw:
            return visibility
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return visibility
        if not isinstance(parsed, dict):
            return visibility
        for key in visibility:
            if key in parsed:
                visibility[key] = self._to_bool(parsed[key])
        return visibility

    @staticmethod
    def _normalize_series_visibility(visibility: dict[str, bool]) -> dict[str, bool]:
        return {
            "flow": bool(visibility.get("flow", True)),
            "o2": bool(visibility.get("o2", True)),
            "heater": bool(visibility.get("heater", True)),
            "zirconia": bool(visibility.get("zirconia", True)),
        }

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
        if plot_label in {"Zirconia", "Flow", "Sensor / Flow", "Flow / O2"}:
            return "Flow / O2"
        if plot_label in {"Heater", "Zirconia / Heater"}:
            return "Zirconia / Heater"
        return "Flow / O2"
