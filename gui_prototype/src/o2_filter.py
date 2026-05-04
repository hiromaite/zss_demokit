from __future__ import annotations

from collections import deque
from dataclasses import replace
import math

import numpy as np

from app_state import (
    O2_FILTER_PRESET_CUSTOM,
    O2_FILTER_PRESET_DEFAULT,
    O2_FILTER_PRESET_FAST,
    O2_FILTER_PRESET_QUIET,
    O2_FILTER_PRESETS,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN_7,
    O2_FILTER_TYPE_EMA_1,
    O2_FILTER_TYPE_EMA_2,
    O2_FILTER_TYPE_GAUSSIAN,
    O2_FILTER_TYPE_SAVGOL,
    O2_FILTER_TYPE_SAVGOL_7,
    O2_FILTER_TYPE_SAVGOL_9,
    O2_FILTER_TYPES,
    O2OutputFilterPreferences,
)


DEFAULT_SAMPLE_PERIOD_MS = 10.0
MIN_CENTERED_WINDOW_POINTS = 3
MAX_CENTERED_WINDOW_POINTS = 51
MAX_SAVGOL_POLYNOMIAL_ORDER = 5


def normalize_o2_filter_preferences(
    preferences: O2OutputFilterPreferences,
) -> O2OutputFilterPreferences:
    filter_type, legacy_window_points = _normalize_filter_type(preferences.filter_type)

    preset = _normalize_preset(preferences.preset)
    savgol_window_points = _normalize_window_points(
        legacy_window_points
        if preferences.filter_type in {O2_FILTER_TYPE_SAVGOL_7, O2_FILTER_TYPE_SAVGOL_9}
        else preferences.savgol_window_points
    )
    savgol_polynomial_order = _normalize_polynomial_order(
        preferences.savgol_polynomial_order,
        savgol_window_points,
    )
    centered_window_points = _normalize_window_points(
        7
        if preferences.filter_type == O2_FILTER_TYPE_CENTERED_GAUSSIAN_7
        else preferences.centered_gaussian_window_points
    )

    return O2OutputFilterPreferences(
        enabled=bool(preferences.enabled),
        filter_type=filter_type,
        preset=preset,
        savgol_window_points=savgol_window_points,
        savgol_polynomial_order=savgol_polynomial_order,
        centered_gaussian_window_points=centered_window_points,
        centered_gaussian_sigma_samples=_clamp(
            float(preferences.centered_gaussian_sigma_samples),
            0.5,
            12.0,
        ),
    )


def effective_o2_filter_preferences(
    preferences: O2OutputFilterPreferences,
) -> O2OutputFilterPreferences:
    normalized = normalize_o2_filter_preferences(preferences)
    if normalized.preset == O2_FILTER_PRESET_CUSTOM:
        return normalized

    if normalized.filter_type == O2_FILTER_TYPE_SAVGOL:
        settings_by_preset = {
            O2_FILTER_PRESET_FAST: (7, 2),
            O2_FILTER_PRESET_DEFAULT: (9, 2),
            O2_FILTER_PRESET_QUIET: (13, 2),
        }
        window_points, polynomial_order = settings_by_preset.get(
            normalized.preset,
            settings_by_preset[O2_FILTER_PRESET_DEFAULT],
        )
        return replace(
            normalized,
            savgol_window_points=window_points,
            savgol_polynomial_order=polynomial_order,
        )

    settings_by_preset = {
        O2_FILTER_PRESET_FAST: (7, 1.25),
        O2_FILTER_PRESET_DEFAULT: (9, 1.75),
        O2_FILTER_PRESET_QUIET: (13, 2.75),
    }
    window_points, sigma_samples = settings_by_preset.get(
        normalized.preset,
        settings_by_preset[O2_FILTER_PRESET_DEFAULT],
    )
    return replace(
        normalized,
        centered_gaussian_window_points=window_points,
        centered_gaussian_sigma_samples=sigma_samples,
    )


def describe_o2_filter(preferences: O2OutputFilterPreferences) -> str:
    effective = effective_o2_filter_preferences(preferences)
    if not effective.enabled:
        return "Raw"
    if effective.filter_type == O2_FILTER_TYPE_SAVGOL:
        return (
            f"{effective.filter_type} "
            f"{effective.savgol_window_points}-point order={effective.savgol_polynomial_order}"
        )
    return (
        f"{effective.filter_type} {effective.centered_gaussian_window_points}-point "
        f"sigma={effective.centered_gaussian_sigma_samples:g} samples"
    )


class O2OutputFilter:
    def __init__(self, preferences: O2OutputFilterPreferences | None = None) -> None:
        self._preferences = normalize_o2_filter_preferences(
            preferences or O2OutputFilterPreferences()
        )
        self._signature: tuple[object, ...] | None = None
        self._centered_history: deque[float] = deque()
        self._centered_weights: list[float] = []

    @property
    def preferences(self) -> O2OutputFilterPreferences:
        return self._preferences

    def set_preferences(self, preferences: O2OutputFilterPreferences) -> None:
        normalized = normalize_o2_filter_preferences(preferences)
        if normalized != self._preferences:
            self._preferences = normalized
            self.reset()

    def reset(self) -> None:
        self._signature = None
        self._centered_history.clear()
        self._centered_weights = []

    def apply(self, value: float, sample_period_ms: int | float | None) -> float:
        if value is None or not math.isfinite(value):
            return math.nan

        effective = effective_o2_filter_preferences(self._preferences)
        if not effective.enabled:
            return value

        period_ms = _normalize_sample_period_ms(sample_period_ms)
        self._configure(effective, period_ms)
        return self._apply_centered_fir(value)

    def apply_series(
        self,
        values: list[float] | tuple[float, ...],
        sample_period_ms: int | float | None,
    ) -> list[float]:
        self.reset()
        return [self.apply(value, sample_period_ms) for value in values]

    def _configure(
        self,
        effective: O2OutputFilterPreferences,
        sample_period_ms: float,
    ) -> None:
        signature = (
            effective.enabled,
            effective.filter_type,
            effective.savgol_window_points,
            effective.savgol_polynomial_order,
            effective.centered_gaussian_window_points,
            effective.centered_gaussian_sigma_samples,
            sample_period_ms,
        )
        if signature == self._signature:
            return

        self._signature = signature
        self._centered_history.clear()
        self._centered_weights = []

        if effective.filter_type == O2_FILTER_TYPE_SAVGOL:
            self._centered_weights = _savgol_weights(
                effective.savgol_window_points,
                effective.savgol_polynomial_order,
            )
        else:
            self._centered_weights = _centered_weights(effective)
        self._centered_history = deque(maxlen=len(self._centered_weights))

    def _apply_centered_fir(self, value: float) -> float:
        if not self._centered_weights:
            return value
        self._centered_history.append(value)
        if len(self._centered_history) < len(self._centered_weights):
            return value
        return sum(
            weight * sample
            for weight, sample in zip(self._centered_weights, self._centered_history)
        )


def _normalize_sample_period_ms(sample_period_ms: int | float | None) -> float:
    try:
        parsed = float(sample_period_ms)
    except (TypeError, ValueError):
        parsed = DEFAULT_SAMPLE_PERIOD_MS
    if not math.isfinite(parsed) or parsed <= 0.0:
        return DEFAULT_SAMPLE_PERIOD_MS
    return parsed


def _normalize_filter_type(filter_type: str) -> tuple[str, int | None]:
    if filter_type in O2_FILTER_TYPES:
        return filter_type, None
    if filter_type == O2_FILTER_TYPE_SAVGOL_7:
        return O2_FILTER_TYPE_SAVGOL, 7
    if filter_type == O2_FILTER_TYPE_SAVGOL_9:
        return O2_FILTER_TYPE_SAVGOL, 9
    if filter_type in {O2_FILTER_TYPE_GAUSSIAN, O2_FILTER_TYPE_CENTERED_GAUSSIAN_7}:
        return O2_FILTER_TYPE_CENTERED_GAUSSIAN, None
    if filter_type in {O2_FILTER_TYPE_EMA_1, O2_FILTER_TYPE_EMA_2}:
        return O2_FILTER_TYPE_SAVGOL, None
    return O2_FILTER_TYPE_SAVGOL, None


def _normalize_preset(preset: str) -> str:
    if preset == "Balanced":
        return O2_FILTER_PRESET_DEFAULT
    if preset in O2_FILTER_PRESETS:
        return preset
    return O2_FILTER_PRESET_DEFAULT


def _normalize_window_points(value: object) -> int:
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        parsed = 9
    parsed = int(_clamp(float(parsed), MIN_CENTERED_WINDOW_POINTS, MAX_CENTERED_WINDOW_POINTS))
    if parsed % 2 == 0:
        parsed += 1 if parsed < MAX_CENTERED_WINDOW_POINTS else -1
    return parsed


def _normalize_polynomial_order(value: object, window_points: int) -> int:
    max_order = min(MAX_SAVGOL_POLYNOMIAL_ORDER, window_points - 1)
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        parsed = 2
    return int(_clamp(float(parsed), 0.0, float(max_order)))


def _savgol_weights(window_points: int, polynomial_order: int) -> list[float]:
    half_window = window_points // 2
    positions = np.arange(-half_window, half_window + 1, dtype=float)
    design = np.vander(positions, N=polynomial_order + 1, increasing=True)
    weights = np.linalg.pinv(design)[0]
    return [float(weight) for weight in weights]


def _centered_weights(preferences: O2OutputFilterPreferences) -> list[float]:
    radius = preferences.centered_gaussian_window_points // 2
    sigma_samples = preferences.centered_gaussian_sigma_samples
    raw_weights = [
        math.exp(-0.5 * ((index - radius) / sigma_samples) ** 2)
        for index in range((radius * 2) + 1)
    ]
    total = sum(raw_weights) or 1.0
    return [weight / total for weight in raw_weights]


def _clamp(value: float, lower: float, upper: float) -> float:
    if not math.isfinite(value):
        return lower
    return max(lower, min(upper, value))
