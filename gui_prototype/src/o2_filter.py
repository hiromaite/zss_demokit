from __future__ import annotations

from collections import deque
from dataclasses import replace
import math

from app_state import (
    O2_FILTER_PRESET_BALANCED,
    O2_FILTER_PRESET_CUSTOM,
    O2_FILTER_PRESET_FAST,
    O2_FILTER_PRESET_QUIET,
    O2_FILTER_PRESETS,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_EMA_1,
    O2_FILTER_TYPE_EMA_2,
    O2_FILTER_TYPE_GAUSSIAN,
    O2_FILTER_TYPE_SAVGOL_7,
    O2_FILTER_TYPE_SAVGOL_9,
    O2_FILTER_TYPES,
    O2OutputFilterPreferences,
)


DEFAULT_SAMPLE_PERIOD_MS = 10.0
MAX_GAUSSIAN_TAPS = 256
SAVGOL_7_POINT_QUADRATIC_WEIGHTS = (
    -2.0 / 21.0,
    3.0 / 21.0,
    6.0 / 21.0,
    7.0 / 21.0,
    6.0 / 21.0,
    3.0 / 21.0,
    -2.0 / 21.0,
)
SAVGOL_9_POINT_QUADRATIC_WEIGHTS = (
    -21.0 / 231.0,
    14.0 / 231.0,
    39.0 / 231.0,
    54.0 / 231.0,
    59.0 / 231.0,
    54.0 / 231.0,
    39.0 / 231.0,
    14.0 / 231.0,
    -21.0 / 231.0,
)
CENTERED_FILTER_TYPES = {
    O2_FILTER_TYPE_SAVGOL_7,
    O2_FILTER_TYPE_SAVGOL_9,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
}


def normalize_o2_filter_preferences(
    preferences: O2OutputFilterPreferences,
) -> O2OutputFilterPreferences:
    filter_type = preferences.filter_type
    if filter_type not in O2_FILTER_TYPES:
        filter_type = O2_FILTER_TYPE_GAUSSIAN

    preset = preferences.preset
    if preset not in O2_FILTER_PRESETS:
        preset = O2_FILTER_PRESET_BALANCED

    return O2OutputFilterPreferences(
        enabled=bool(preferences.enabled),
        filter_type=filter_type,
        preset=preset,
        ema_cutoff_hz=_clamp(float(preferences.ema_cutoff_hz), 0.1, 25.0),
        gaussian_sigma_ms=_clamp(float(preferences.gaussian_sigma_ms), 1.0, 1000.0),
        gaussian_tail_sigma=_clamp(float(preferences.gaussian_tail_sigma), 1.0, 6.0),
        centered_gaussian_sigma_samples=_clamp(
            float(preferences.centered_gaussian_sigma_samples),
            1.0,
            1.5,
        ),
    )


def effective_o2_filter_preferences(
    preferences: O2OutputFilterPreferences,
) -> O2OutputFilterPreferences:
    normalized = normalize_o2_filter_preferences(preferences)
    if normalized.preset == O2_FILTER_PRESET_CUSTOM:
        return normalized

    if normalized.filter_type == O2_FILTER_TYPE_GAUSSIAN:
        sigma_by_preset = {
            O2_FILTER_PRESET_FAST: 20.0,
            O2_FILTER_PRESET_BALANCED: 30.0,
            O2_FILTER_PRESET_QUIET: 40.0,
        }
        return replace(
            normalized,
            gaussian_sigma_ms=sigma_by_preset.get(normalized.preset, 30.0),
            gaussian_tail_sigma=3.0,
        )

    if normalized.filter_type == O2_FILTER_TYPE_CENTERED_GAUSSIAN:
        sigma_by_preset = {
            O2_FILTER_PRESET_FAST: 1.0,
            O2_FILTER_PRESET_BALANCED: 1.25,
            O2_FILTER_PRESET_QUIET: 1.5,
        }
        return replace(
            normalized,
            centered_gaussian_sigma_samples=sigma_by_preset.get(normalized.preset, 1.25),
        )

    cutoff_by_preset = {
        O2_FILTER_PRESET_FAST: 10.0,
        O2_FILTER_PRESET_BALANCED: 7.0,
        O2_FILTER_PRESET_QUIET: 5.0,
    }
    return replace(
        normalized,
        ema_cutoff_hz=cutoff_by_preset.get(normalized.preset, 7.0),
    )


def describe_o2_filter(preferences: O2OutputFilterPreferences) -> str:
    effective = effective_o2_filter_preferences(preferences)
    if not effective.enabled:
        return "Raw"
    if effective.filter_type == O2_FILTER_TYPE_GAUSSIAN:
        return (
            f"{effective.filter_type} "
            f"sigma={effective.gaussian_sigma_ms:g}ms tail={effective.gaussian_tail_sigma:g}sigma"
        )
    if effective.filter_type == O2_FILTER_TYPE_CENTERED_GAUSSIAN:
        return (
            f"{effective.filter_type} "
            f"sigma={effective.centered_gaussian_sigma_samples:g} samples"
        )
    if effective.filter_type == O2_FILTER_TYPE_SAVGOL_7:
        return "Savitzky-Golay 7-point, quadratic"
    if effective.filter_type == O2_FILTER_TYPE_SAVGOL_9:
        return "Savitzky-Golay 9-point, quadratic"
    return f"{effective.filter_type} cutoff={effective.ema_cutoff_hz:g}Hz"


class O2OutputFilter:
    def __init__(self, preferences: O2OutputFilterPreferences | None = None) -> None:
        self._preferences = normalize_o2_filter_preferences(
            preferences or O2OutputFilterPreferences()
        )
        self._signature: tuple[object, ...] | None = None
        self._ema_values: list[float | None] = []
        self._gaussian_history: deque[float] = deque()
        self._gaussian_weights: list[float] = []
        self._centered_history: deque[float] = deque()
        self._centered_weights: list[float] = []
        self._alpha = 1.0

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
        self._ema_values = []
        self._gaussian_history.clear()
        self._gaussian_weights = []
        self._centered_history.clear()
        self._centered_weights = []
        self._alpha = 1.0

    def apply(self, value: float, sample_period_ms: int | float | None) -> float:
        if value is None or not math.isfinite(value):
            return math.nan

        effective = effective_o2_filter_preferences(self._preferences)
        if not effective.enabled:
            return value

        period_ms = _normalize_sample_period_ms(sample_period_ms)
        self._configure(effective, period_ms)
        if effective.filter_type in {O2_FILTER_TYPE_EMA_1, O2_FILTER_TYPE_EMA_2}:
            return self._apply_ema(value, _ema_stages(effective.filter_type))
        if effective.filter_type in CENTERED_FILTER_TYPES:
            return self._apply_centered_fir(value)
        return self._apply_gaussian(value)

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
            effective.ema_cutoff_hz,
            effective.gaussian_sigma_ms,
            effective.gaussian_tail_sigma,
            effective.centered_gaussian_sigma_samples,
            sample_period_ms,
        )
        if signature == self._signature:
            return

        self._signature = signature
        self._ema_values = []
        self._gaussian_history.clear()
        self._gaussian_weights = []
        self._centered_history.clear()
        self._centered_weights = []

        if effective.filter_type in {O2_FILTER_TYPE_EMA_1, O2_FILTER_TYPE_EMA_2}:
            sample_rate_hz = 1000.0 / sample_period_ms
            cutoff_hz = min(effective.ema_cutoff_hz, sample_rate_hz * 0.45)
            dt_s = sample_period_ms / 1000.0
            self._alpha = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz * dt_s)
            self._ema_values = [None] * _ema_stages(effective.filter_type)
            return

        if effective.filter_type in CENTERED_FILTER_TYPES:
            self._centered_weights = _centered_weights(effective)
            self._centered_history = deque(maxlen=len(self._centered_weights))
            return

        tap_count = int(
            math.ceil(
                (effective.gaussian_sigma_ms * effective.gaussian_tail_sigma)
                / sample_period_ms
            )
        ) + 1
        tap_count = max(1, min(MAX_GAUSSIAN_TAPS, tap_count))
        raw_weights = [
            math.exp(-0.5 * ((index * sample_period_ms) / effective.gaussian_sigma_ms) ** 2)
            for index in range(tap_count)
        ]
        total = sum(raw_weights) or 1.0
        self._gaussian_weights = [weight / total for weight in raw_weights]
        self._gaussian_history = deque(maxlen=len(self._gaussian_weights))

    def _apply_ema(self, value: float, stages: int) -> float:
        output = value
        for index in range(stages):
            previous = self._ema_values[index]
            if previous is None or not math.isfinite(previous):
                current = output
            else:
                current = previous + self._alpha * (output - previous)
            self._ema_values[index] = current
            output = current
        return output

    def _apply_gaussian(self, value: float) -> float:
        if not self._gaussian_weights:
            return value
        self._gaussian_history.appendleft(value)
        weighted_sum = 0.0
        weight_sum = 0.0
        for weight, sample in zip(self._gaussian_weights, self._gaussian_history):
            weighted_sum += weight * sample
            weight_sum += weight
        return weighted_sum / weight_sum if weight_sum > 0.0 else value

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


def _ema_stages(filter_type: str) -> int:
    return 2 if filter_type == O2_FILTER_TYPE_EMA_2 else 1


def _centered_weights(preferences: O2OutputFilterPreferences) -> list[float]:
    if preferences.filter_type == O2_FILTER_TYPE_SAVGOL_7:
        return list(SAVGOL_7_POINT_QUADRATIC_WEIGHTS)
    if preferences.filter_type == O2_FILTER_TYPE_SAVGOL_9:
        return list(SAVGOL_9_POINT_QUADRATIC_WEIGHTS)

    radius = 3
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
