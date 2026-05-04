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
    O2_FILTER_PRESET_BALANCED,
    O2_FILTER_PRESET_CUSTOM,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_EMA_2,
    O2_FILTER_TYPE_GAUSSIAN,
    O2_FILTER_TYPE_SAVGOL_7,
    O2_FILTER_TYPE_SAVGOL_9,
    O2OutputFilterPreferences,
)
from o2_filter import O2OutputFilter, describe_o2_filter  # noqa: E402


def main() -> int:
    _assert_disabled_filter_is_identity()
    _assert_gaussian_default_response()
    _assert_ema_reduces_pump_ripple()
    _assert_savgol_preserves_quadratic_with_delay()
    _assert_centered_gaussian_reduces_ripple()
    print("o2_filter_smoke_ok")
    return 0


def _assert_disabled_filter_is_identity() -> None:
    preferences = O2OutputFilterPreferences(enabled=False)
    output_filter = O2OutputFilter(preferences)
    values = [0.61, 0.62, 0.63, 0.64]
    filtered = output_filter.apply_series(values, 10)
    if filtered != values:
        raise AssertionError(f"disabled filter changed values: {filtered}")


def _assert_gaussian_default_response() -> None:
    preferences = O2OutputFilterPreferences(
        enabled=True,
        filter_type=O2_FILTER_TYPE_GAUSSIAN,
        preset=O2_FILTER_PRESET_BALANCED,
    )
    output_filter = O2OutputFilter(preferences)
    step = [0.0] * 20 + [1.0] * 80
    filtered = output_filter.apply_series(step, 10)
    t10_ms = _first_crossing_ms(filtered, 0.1, offset_samples=20)
    t90_ms = _first_crossing_ms(filtered, 0.9, offset_samples=20)
    if t10_ms is None or t90_ms is None:
        raise AssertionError("default Gaussian filter did not cross 10/90%")
    response_ms = t90_ms - t10_ms
    if response_ms > 135.0:
        raise AssertionError(
            f"default Gaussian response too slow: {response_ms:0.1f} ms ({describe_o2_filter(preferences)})"
        )


def _assert_ema_reduces_pump_ripple() -> None:
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

    preferences = O2OutputFilterPreferences(
        enabled=True,
        filter_type=O2_FILTER_TYPE_EMA_2,
        preset=O2_FILTER_PRESET_CUSTOM,
        ema_cutoff_hz=7.0,
    )
    filtered = O2OutputFilter(preferences).apply_series(raw_values, sample_period_ms)
    stable_slice = slice(250, 500)
    raw_rms = _rms_residual(raw_values[stable_slice], baseline[stable_slice])
    filtered_rms = _rms_residual(filtered[stable_slice], baseline[stable_slice])
    if filtered_rms >= raw_rms * 0.65:
        raise AssertionError(
            f"EMA filter did not reduce ripple enough: raw={raw_rms:0.6f}, filtered={filtered_rms:0.6f}"
        )


def _assert_savgol_preserves_quadratic_with_delay() -> None:
    for filter_type, half_window in (
        (O2_FILTER_TYPE_SAVGOL_7, 3),
        (O2_FILTER_TYPE_SAVGOL_9, 4),
    ):
        values = [float(index * index) for index in range(20)]
        filtered = O2OutputFilter(
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=filter_type,
                preset=O2_FILTER_PRESET_CUSTOM,
            )
        ).apply_series(values, 10)
        first_full_index = (half_window * 2)
        expected_center = float((first_full_index - half_window) ** 2)
        if abs(filtered[first_full_index] - expected_center) > 1e-9:
            raise AssertionError(
                f"{filter_type} did not preserve quadratic center: "
                f"{filtered[first_full_index]} != {expected_center}"
            )


def _assert_centered_gaussian_reduces_ripple() -> None:
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
            centered_gaussian_sigma_samples=1.25,
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
