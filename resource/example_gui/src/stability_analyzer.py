from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence


STABILITY_STATE_UNKNOWN = "unknown"
STABILITY_STATE_STABLE = "stable"
STABILITY_STATE_UNSTABLE = "unstable"


@dataclass(frozen=True)
class StabilityConfig:
    history_window_seconds: float = 10 * 60.0
    recent_window_seconds: float = 30.0
    ratio_threshold: float = 0.05
    required_channel_count: int = 10
    epsilon: float = 1e-9


@dataclass(frozen=True)
class TraceStability:
    state: str
    history_span: float
    recent_span: float
    ratio: float
    sample_count: int
    history_sample_count: int
    recent_sample_count: int


@dataclass(frozen=True)
class StabilitySnapshot:
    channels: List[TraceStability]
    stable_count: int
    unstable_count: int
    unknown_count: int
    required_channel_count: int
    overall_stable: bool

    @classmethod
    def empty(cls, channel_count: int, required_channel_count: int) -> "StabilitySnapshot":
        channels = [
            TraceStability(
                state=STABILITY_STATE_UNKNOWN,
                history_span=0.0,
                recent_span=0.0,
                ratio=0.0,
                sample_count=0,
                history_sample_count=0,
                recent_sample_count=0,
            )
            for _ in range(channel_count)
        ]
        return cls(
            channels=channels,
            stable_count=0,
            unstable_count=0,
            unknown_count=channel_count,
            required_channel_count=required_channel_count,
            overall_stable=False,
        )


def _span(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return max(values) - min(values)


def _window_values(time_values: Sequence[float], series_values: Sequence[float], cutoff: float) -> List[float]:
    if not time_values or not series_values:
        return []
    return [value for timestamp, value in zip(time_values, series_values) if timestamp >= cutoff]


def analyze_trace_stability(
    time_values: Sequence[float],
    series_values: Sequence[float],
    config: StabilityConfig,
) -> TraceStability:
    if not time_values or not series_values or len(time_values) != len(series_values):
        return TraceStability(
            state=STABILITY_STATE_UNKNOWN,
            history_span=0.0,
            recent_span=0.0,
            ratio=0.0,
            sample_count=len(series_values),
            history_sample_count=0,
            recent_sample_count=0,
        )

    latest_time = time_values[-1]
    history_values = _window_values(time_values, series_values, latest_time - config.history_window_seconds)
    recent_values = _window_values(time_values, series_values, latest_time - config.recent_window_seconds)

    if len(history_values) < 2 or len(recent_values) < 2:
        return TraceStability(
            state=STABILITY_STATE_UNKNOWN,
            history_span=_span(history_values),
            recent_span=_span(recent_values),
            ratio=0.0,
            sample_count=len(series_values),
            history_sample_count=len(history_values),
            recent_sample_count=len(recent_values),
        )

    history_span = _span(history_values)
    recent_span = _span(recent_values)

    if history_span <= config.epsilon:
        ratio = 0.0 if recent_span <= config.epsilon else float("inf")
    else:
        ratio = recent_span / history_span

    state = STABILITY_STATE_STABLE if ratio <= config.ratio_threshold else STABILITY_STATE_UNSTABLE
    return TraceStability(
        state=state,
        history_span=history_span,
        recent_span=recent_span,
        ratio=ratio,
        sample_count=len(series_values),
        history_sample_count=len(history_values),
        recent_sample_count=len(recent_values),
    )


def analyze_gas_stability(
    gas_traces: Sequence[Dict[str, List[float]]],
    config: StabilityConfig,
) -> StabilitySnapshot:
    channel_results = [
        analyze_trace_stability(trace.get("time", []), trace.get("value", []), config)
        for trace in gas_traces
    ]
    stable_count = sum(1 for channel in channel_results if channel.state == STABILITY_STATE_STABLE)
    unstable_count = sum(1 for channel in channel_results if channel.state == STABILITY_STATE_UNSTABLE)
    unknown_count = sum(1 for channel in channel_results if channel.state == STABILITY_STATE_UNKNOWN)
    required_channel_count = min(config.required_channel_count, len(channel_results))
    overall_stable = stable_count >= required_channel_count and unknown_count == 0
    return StabilitySnapshot(
        channels=channel_results,
        stable_count=stable_count,
        unstable_count=unstable_count,
        unknown_count=unknown_count,
        required_channel_count=required_channel_count,
        overall_stable=overall_stable,
    )
