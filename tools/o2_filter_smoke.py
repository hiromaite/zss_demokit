#!/usr/bin/env python3
from __future__ import annotations

import math
import random
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_SRC = REPO_ROOT / "gui_prototype" / "src"
sys.path.insert(0, str(GUI_SRC))

from app_state import (  # noqa: E402
    O2_FILTER_PRESET_CUSTOM,
    O2_FILTER_PRESET_DEFAULT,
    O2_FILTER_PRESET_FAST,
    O2_FILTER_PRESET_QUIET,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_SAVGOL,
    O2OutputFilterPreferences,
)
from o2_filter import O2OutputFilter, describe_o2_filter  # noqa: E402
from protocol_constants import derive_o2_concentration_percent  # noqa: E402


def main() -> int:
    _assert_o2_voltage_conversion_uses_configured_zero_anchor()
    _assert_disabled_filter_is_identity()
    _assert_supported_filter_presets_reduce_pump_ripple()
    _assert_savgol_preserves_quadratic_with_delay()
    _assert_centered_gaussian_custom_reduces_ripple()
    print("o2_filter_smoke_ok")
    return 0


def _assert_o2_voltage_conversion_uses_configured_zero_anchor() -> None:
    legacy_value = derive_o2_concentration_percent(
        0.64,
        air_calibration_voltage_v=0.64,
        zero_reference_voltage_v=0.0,
    )
    if legacy_value is None or abs(legacy_value - 21.0) > 1e-9:
        raise AssertionError(f"legacy 0 V zero anchor did not map ambient to 21%: {legacy_value}")

    shifted_zero_value = derive_o2_concentration_percent(
        0.64,
        air_calibration_voltage_v=0.64,
        zero_reference_voltage_v=2.55,
    )
    if shifted_zero_value is None or abs(shifted_zero_value - 21.0) > 1e-9:
        raise AssertionError(f"2.55 V zero anchor did not map ambient to 21%: {shifted_zero_value}")

    clamped_value = derive_o2_concentration_percent(
        2.6,
        air_calibration_voltage_v=0.64,
        zero_reference_voltage_v=2.55,
    )
    if clamped_value != 0.0:
        raise AssertionError(f"above-zero-reference voltage should clamp to 0%: {clamped_value}")


def _assert_disabled_filter_is_identity() -> None:
    preferences = O2OutputFilterPreferences(enabled=False)
    output_filter = O2OutputFilter(preferences)
    values = [0.61, 0.62, 0.63, 0.64]
    filtered = output_filter.apply_series(values, 10)
    if filtered != values:
        raise AssertionError(f"disabled filter changed values: {filtered}")


def _assert_supported_filter_presets_reduce_pump_ripple() -> None:
    random.seed(42)
    sample_period_ms = 10
    raw_values: list[float] = []
    baseline: list[float] = []
    for index in range(500):
        t_s = index * sample_period_ms / 1000.0
        slow = 0.64 + 0.02 * (1.0 - math.exp(-max(0.0, t_s - 1.0) / 0.08))
        ripple = 0.006 * math.sin(2.0 * math.pi * 18.0 * t_s)
        noise = random.uniform(-0.0015, 0.0015)
        baseline.append(slow)
        raw_values.append(slow + ripple + noise)

    stable_slice = slice(250, 500)
    raw_rms = _rms_residual(raw_values[stable_slice], baseline[stable_slice])
    for filter_type in (O2_FILTER_TYPE_SAVGOL, O2_FILTER_TYPE_CENTERED_GAUSSIAN):
        fast_preferences = O2OutputFilterPreferences(
            enabled=True,
            filter_type=filter_type,
            preset=O2_FILTER_PRESET_FAST,
        )
        quiet_preferences = O2OutputFilterPreferences(
            enabled=True,
            filter_type=filter_type,
            preset=O2_FILTER_PRESET_QUIET,
        )
        fast_filtered = O2OutputFilter(fast_preferences).apply_series(raw_values, sample_period_ms)
        quiet_filtered = O2OutputFilter(quiet_preferences).apply_series(raw_values, sample_period_ms)
        fast_rms = _rms_residual(fast_filtered[stable_slice], baseline[stable_slice])
        quiet_rms = _rms_residual(quiet_filtered[stable_slice], baseline[stable_slice])
        if fast_rms >= raw_rms:
            raise AssertionError(
                f"{describe_o2_filter(fast_preferences)} did not reduce ripple: "
                f"raw={raw_rms:0.6f}, filtered={fast_rms:0.6f}"
            )
        if quiet_rms >= fast_rms:
            raise AssertionError(
                f"{describe_o2_filter(quiet_preferences)} was not quieter than fast preset: "
                f"fast={fast_rms:0.6f}, quiet={quiet_rms:0.6f}"
            )

    default_description = describe_o2_filter(
        O2OutputFilterPreferences(
            enabled=True,
            filter_type=O2_FILTER_TYPE_SAVGOL,
            preset=O2_FILTER_PRESET_DEFAULT,
        )
    )
    if "9-point" not in default_description:
        raise AssertionError(
            f"Savitzky-Golay default preset did not report 9-point settings: {default_description}"
        )


def _assert_savgol_preserves_quadratic_with_delay() -> None:
    for window_points in (7, 9, 13, 15):
        half_window = window_points // 2
        values = [float(index * index) for index in range(40)]
        filtered = O2OutputFilter(
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_SAVGOL,
                preset=O2_FILTER_PRESET_CUSTOM,
                savgol_window_points=window_points,
                savgol_polynomial_order=2,
            )
        ).apply_series(values, 10)
        first_full_index = window_points - 1
        expected_center = float((first_full_index - half_window) ** 2)
        if abs(filtered[first_full_index] - expected_center) > 1e-8:
            raise AssertionError(
                f"Savitzky-Golay {window_points}-point did not preserve quadratic center: "
                f"{filtered[first_full_index]} != {expected_center}"
            )


def _assert_centered_gaussian_custom_reduces_ripple() -> None:
    sample_period_ms = 10
    raw_values = [
        0.64 + 0.006 * math.sin(2.0 * math.pi * 18.0 * index * sample_period_ms / 1000.0)
        for index in range(500)
    ]
    filtered = O2OutputFilter(
        O2OutputFilterPreferences(
            enabled=True,
            filter_type=O2_FILTER_TYPE_CENTERED_GAUSSIAN,
            preset=O2_FILTER_PRESET_CUSTOM,
            centered_gaussian_window_points=13,
            centered_gaussian_sigma_samples=2.75,
        )
    ).apply_series(raw_values, sample_period_ms)
    raw_rms = _rms_residual(raw_values[100:], [0.64] * 400)
    filtered_rms = _rms_residual(filtered[100:], [0.64] * 400)
    if filtered_rms >= raw_rms * 0.75:
        raise AssertionError(
            f"centered Gaussian did not reduce ripple enough: raw={raw_rms:0.6f}, filtered={filtered_rms:0.6f}"
        )


def _first_crossing_ms(
    values: list[float],
    level: float,
    *,
    offset_samples: int,
    sample_period_ms: float = 10.0,
) -> float | None:
    previous = values[offset_samples - 1]
    for index in range(offset_samples, len(values)):
        current = values[index]
        if current >= level:
            if current == previous:
                return (index - offset_samples) * sample_period_ms
            fraction = (level - previous) / (current - previous)
            return ((index - 1 + fraction) - offset_samples) * sample_period_ms
        previous = current
    return None


def _rms_residual(values: list[float], baseline: list[float]) -> float:
    residuals = [value - expected for value, expected in zip(values, baseline)]
    return math.sqrt(sum(value * value for value in residuals) / len(residuals))


if __name__ == "__main__":
    raise SystemExit(main())
