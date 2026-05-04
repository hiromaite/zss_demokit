#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from dataclasses import asdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_SRC = REPO_ROOT / "gui_prototype" / "src"
sys.path.insert(0, str(GUI_SRC))

from app_state import (  # noqa: E402
    O2_FILTER_PRESET_BALANCED,
    O2_FILTER_PRESET_CUSTOM,
    O2_FILTER_PRESET_FAST,
    O2_FILTER_PRESET_QUIET,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_EMA_1,
    O2_FILTER_TYPE_EMA_2,
    O2_FILTER_TYPE_GAUSSIAN,
    O2_FILTER_TYPE_SAVGOL_7,
    O2_FILTER_TYPE_SAVGOL_9,
    O2OutputFilterPreferences,
)
from o2_filter import O2OutputFilter, describe_o2_filter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare O2 output filter candidates against a recorded 10 ms CSV session.",
    )
    parser.add_argument("recording_csv", type=Path)
    parser.add_argument("--start-s", type=float, default=None, help="Start of analysis window")
    parser.add_argument("--end-s", type=float, default=None, help="End of analysis window")
    parser.add_argument("--step-at-s", type=float, default=None, help="Optional step start time for 10-90 analysis")
    parser.add_argument("--pre-window-s", type=float, default=0.25)
    parser.add_argument("--post-window-s", type=float, default=0.50)
    parser.add_argument("--write-sidecar", action="store_true", help="Write .o2_filter_analysis.csv/.json next to input")
    args = parser.parse_args()

    samples = load_recording(args.recording_csv)
    if not samples:
        print(f"No finite zirconia samples found in {args.recording_csv}", file=sys.stderr)
        return 2

    rows = compare_candidates(
        samples,
        start_s=args.start_s,
        end_s=args.end_s,
        step_at_s=args.step_at_s,
        pre_window_s=args.pre_window_s,
        post_window_s=args.post_window_s,
    )
    print_summary(rows)
    if args.write_sidecar:
        write_sidecars(args.recording_csv, rows)
    return 0


def load_recording(path: Path) -> list[dict[str, float]]:
    samples: list[dict[str, float]] = []
    first_sequence: int | None = None
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(line for line in handle if line.strip() and not line.startswith("#"))
        for index, row in enumerate(reader):
            value = _to_float(row.get("zirconia_output_voltage_v"))
            if value is None:
                continue
            nominal_ms = _to_float(row.get("nominal_sample_period_ms")) or 10.0
            elapsed_s = _to_float(row.get("device_elapsed_s"))
            if elapsed_s is None:
                sequence = _to_int(row.get("sequence"))
                if sequence is not None:
                    if first_sequence is None:
                        first_sequence = sequence
                    elapsed_s = ((sequence - first_sequence) * nominal_ms) / 1000.0
                else:
                    elapsed_s = (index * nominal_ms) / 1000.0
            samples.append(
                {
                    "elapsed_s": elapsed_s,
                    "zirconia_output_voltage_v": value,
                    "nominal_sample_period_ms": nominal_ms,
                    "pump_state": float(_to_int(row.get("pump_state")) or 0),
                }
            )
    return samples


def compare_candidates(
    samples: list[dict[str, float]],
    *,
    start_s: float | None,
    end_s: float | None,
    step_at_s: float | None,
    pre_window_s: float,
    post_window_s: float,
) -> list[dict[str, object]]:
    raw_values = [sample["zirconia_output_voltage_v"] for sample in samples]
    nominal_ms = statistics.median(sample["nominal_sample_period_ms"] for sample in samples)
    candidates = candidate_preferences()
    raw_segment = _window_values(samples, raw_values, start_s, end_s)
    raw_rms = _rms(raw_segment)

    rows: list[dict[str, object]] = []
    for name, preferences in candidates:
        filtered = O2OutputFilter(preferences).apply_series(raw_values, nominal_ms)
        segment = _window_values(samples, filtered, start_s, end_s)
        rms = _rms(segment)
        step_metrics = (
            _step_metrics(samples, filtered, step_at_s, pre_window_s, post_window_s)
            if step_at_s is not None
            else {}
        )
        rows.append(
            {
                "candidate": name,
                "description": describe_o2_filter(preferences),
                "settings": asdict(preferences),
                "sample_period_ms": nominal_ms,
                "rms_v": rms,
                "rms_reduction_db_vs_raw": _db(raw_rms, rms),
                **step_metrics,
            }
        )
    return rows


def candidate_preferences() -> list[tuple[str, O2OutputFilterPreferences]]:
    return [
        ("Raw", O2OutputFilterPreferences(enabled=False)),
        (
            "EMA 1-pole Fast 10Hz",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_EMA_1,
                preset=O2_FILTER_PRESET_FAST,
            ),
        ),
        (
            "EMA 2-pole Balanced 7Hz",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_EMA_2,
                preset=O2_FILTER_PRESET_BALANCED,
            ),
        ),
        (
            "Gaussian Fast sigma20",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_GAUSSIAN,
                preset=O2_FILTER_PRESET_CUSTOM,
                gaussian_sigma_ms=20.0,
            ),
        ),
        (
            "Gaussian Balanced sigma30",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_GAUSSIAN,
                preset=O2_FILTER_PRESET_BALANCED,
            ),
        ),
        (
            "Gaussian Quiet sigma40",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_GAUSSIAN,
                preset=O2_FILTER_PRESET_QUIET,
            ),
        ),
        (
            "Savitzky-Golay 7-point quadratic",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_SAVGOL_7,
                preset=O2_FILTER_PRESET_CUSTOM,
            ),
        ),
        (
            "Savitzky-Golay 9-point quadratic",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_SAVGOL_9,
                preset=O2_FILTER_PRESET_CUSTOM,
            ),
        ),
        (
            "Centered Gaussian 7-point sigma1.0",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_CENTERED_GAUSSIAN,
                preset=O2_FILTER_PRESET_CUSTOM,
                centered_gaussian_sigma_samples=1.0,
            ),
        ),
        (
            "Centered Gaussian 7-point sigma1.25",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_CENTERED_GAUSSIAN,
                preset=O2_FILTER_PRESET_CUSTOM,
                centered_gaussian_sigma_samples=1.25,
            ),
        ),
        (
            "Centered Gaussian 7-point sigma1.5",
            O2OutputFilterPreferences(
                enabled=True,
                filter_type=O2_FILTER_TYPE_CENTERED_GAUSSIAN,
                preset=O2_FILTER_PRESET_CUSTOM,
                centered_gaussian_sigma_samples=1.5,
            ),
        ),
    ]


def print_summary(rows: list[dict[str, object]]) -> None:
    for row in rows:
        response = row.get("t10_90_ms")
        response_text = "--" if response is None else f"{float(response):0.1f} ms"
        print(
            f"{row['candidate']}: rms={float(row['rms_v']):0.6f} V, "
            f"reduction={float(row['rms_reduction_db_vs_raw']):+0.2f} dB, "
            f"t10-90={response_text}"
        )


def write_sidecars(recording_csv: Path, rows: list[dict[str, object]]) -> None:
    csv_path = recording_csv.with_suffix(".o2_filter_analysis.csv")
    json_path = recording_csv.with_suffix(".o2_filter_analysis.json")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "candidate",
            "description",
            "sample_period_ms",
            "rms_v",
            "rms_reduction_db_vs_raw",
            "t50_delay_ms",
            "t10_90_ms",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump({"candidates": rows}, handle, indent=2)
    print(f"Sidecars written: {csv_path}, {json_path}")


def _window_values(
    samples: list[dict[str, float]],
    values: list[float],
    start_s: float | None,
    end_s: float | None,
) -> list[float]:
    selected = [
        value
        for sample, value in zip(samples, values)
        if (start_s is None or sample["elapsed_s"] >= start_s)
        and (end_s is None or sample["elapsed_s"] <= end_s)
        and math.isfinite(value)
    ]
    return selected or [value for value in values if math.isfinite(value)]


def _step_metrics(
    samples: list[dict[str, float]],
    values: list[float],
    step_at_s: float,
    pre_window_s: float,
    post_window_s: float,
) -> dict[str, float | None]:
    pre_values = [
        value
        for sample, value in zip(samples, values)
        if step_at_s - pre_window_s <= sample["elapsed_s"] < step_at_s
    ]
    post_values = [
        value
        for sample, value in zip(samples, values)
        if step_at_s + post_window_s <= sample["elapsed_s"] <= step_at_s + post_window_s * 1.5
    ]
    if not pre_values or not post_values:
        return {"t50_delay_ms": None, "t10_90_ms": None}

    start = statistics.median(pre_values)
    end = statistics.median(post_values)
    amplitude = end - start
    if abs(amplitude) < 1e-9:
        return {"t50_delay_ms": None, "t10_90_ms": None}

    t10 = _crossing_time(samples, values, step_at_s, start + amplitude * 0.1, amplitude)
    t50 = _crossing_time(samples, values, step_at_s, start + amplitude * 0.5, amplitude)
    t90 = _crossing_time(samples, values, step_at_s, start + amplitude * 0.9, amplitude)
    t10_90_ms = None if t10 is None or t90 is None else (t90 - t10) * 1000.0
    t50_delay_ms = None if t50 is None else (t50 - step_at_s) * 1000.0
    return {"t50_delay_ms": t50_delay_ms, "t10_90_ms": t10_90_ms}


def _crossing_time(
    samples: list[dict[str, float]],
    values: list[float],
    step_at_s: float,
    level: float,
    amplitude: float,
) -> float | None:
    previous_time: float | None = None
    previous_value: float | None = None
    rising = amplitude > 0.0
    for sample, value in zip(samples, values):
        elapsed_s = sample["elapsed_s"]
        if elapsed_s < step_at_s:
            previous_time = elapsed_s
            previous_value = value
            continue
        crossed = value >= level if rising else value <= level
        if crossed:
            if previous_time is None or previous_value is None or value == previous_value:
                return elapsed_s
            fraction = (level - previous_value) / (value - previous_value)
            return previous_time + (elapsed_s - previous_time) * fraction
        previous_time = elapsed_s
        previous_value = value
    return None


def _rms(values: list[float]) -> float:
    if not values:
        return math.nan
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _db(raw_rms: float, filtered_rms: float) -> float:
    if raw_rms <= 0.0 or filtered_rms <= 0.0:
        return 0.0
    return 20.0 * math.log10(filtered_rms / raw_rms)


def _to_float(value: object) -> float | None:
    if value in {"", None}:
        return None
    try:
        parsed = float(str(value))
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _to_int(value: object) -> int | None:
    if value in {"", None}:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
