from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections import deque
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui_prototype" / "src"))

from protocol_constants import (  # noqa: E402
    WIRED_COMMAND_ID_GET_CAPABILITIES,
    WIRED_MESSAGE_TYPE_CAPABILITIES,
    WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
    WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC,
)
from wired_protocol import (  # noqa: E402
    WiredFrame,
    WiredFrameBuffer,
    build_command_frame,
    decode_capabilities,
    decode_timing_diagnostic,
    decode_telemetry_sample,
)


class SerialProtocolSession:
    def __init__(self, ser: serial.Serial) -> None:
        self._serial = ser
        self._frame_buffer = WiredFrameBuffer()
        self._pending_frames: deque[WiredFrame] = deque()

    def _pump_frames(self) -> None:
        waiting = max(1, int(getattr(self._serial, "in_waiting", 0)))
        chunk = self._serial.read(waiting)
        if chunk:
            self._pending_frames.extend(self._frame_buffer.push(chunk))

    def read_matching_frame(
        self,
        *,
        message_type: int,
        request_id: int | None = None,
        timeout_s: float = 3.0,
    ) -> WiredFrame:
        deadline = time.monotonic() + timeout_s
        skipped: deque[WiredFrame] = deque()

        while time.monotonic() < deadline:
            while self._pending_frames:
                frame = self._pending_frames.popleft()
                if frame.message_type == message_type and (request_id is None or frame.request_id == request_id):
                    while skipped:
                        self._pending_frames.appendleft(skipped.pop())
                    return frame
                skipped.append(frame)

            self._pump_frames()
            time.sleep(0.001)

        while skipped:
            self._pending_frames.appendleft(skipped.pop())
        raise TimeoutError(
            f"Timed out waiting for message_type=0x{message_type:02X}"
            + (f" request_id={request_id}" if request_id is not None else "")
        )

    def read_next_frame(self, *, timeout_s: float = 3.0) -> WiredFrame:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._pending_frames:
                return self._pending_frames.popleft()

            self._pump_frames()
            time.sleep(0.001)

        raise TimeoutError("Timed out waiting for next wired frame")


def summarize_intervals(intervals_ms: list[float]) -> dict[str, float]:
    if not intervals_ms:
        return {}
    ordered = sorted(intervals_ms)
    index_95 = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * 0.95))))
    return {
        "mean_ms": statistics.fmean(intervals_ms),
        "stdev_ms": statistics.pstdev(intervals_ms) if len(intervals_ms) > 1 else 0.0,
        "min_ms": ordered[0],
        "p95_ms": ordered[index_95],
        "max_ms": ordered[-1],
    }


def summarize_jitter_us(intervals_ms: list[float], nominal_period_ms: float) -> dict[str, float]:
    if not intervals_ms:
        return {}
    jitter_us = [(interval - nominal_period_ms) * 1000.0 for interval in intervals_ms]
    abs_jitter_us = [abs(value) for value in jitter_us]
    ordered_abs = sorted(abs_jitter_us)
    index_95 = min(len(ordered_abs) - 1, max(0, int(round((len(ordered_abs) - 1) * 0.95))))
    return {
        "mean_jitter_us": statistics.fmean(jitter_us),
        "stdev_jitter_us": statistics.pstdev(jitter_us) if len(jitter_us) > 1 else 0.0,
        "min_jitter_us": min(jitter_us),
        "max_jitter_us": max(jitter_us),
        "mean_abs_jitter_us": statistics.fmean(abs_jitter_us),
        "p95_abs_jitter_us": ordered_abs[index_95],
        "max_abs_jitter_us": ordered_abs[-1],
    }


def format_interval_summary(label: str, summary: dict[str, float]) -> str:
    if not summary:
        return f"{label}: no intervals"
    return (
        f"{label}: "
        f"mean={summary['mean_ms']:.3f} "
        f"stdev={summary['stdev_ms']:.3f} "
        f"min={summary['min_ms']:.3f} "
        f"p95={summary['p95_ms']:.3f} "
        f"max={summary['max_ms']:.3f}"
    )


def format_jitter_summary(label: str, summary: dict[str, float]) -> str:
    if not summary:
        return f"{label}: no jitter data"
    return (
        f"{label}: "
        f"mean={summary['mean_jitter_us']:.1f} "
        f"stdev={summary['stdev_jitter_us']:.1f} "
        f"min={summary['min_jitter_us']:.1f} "
        f"max={summary['max_jitter_us']:.1f} "
        f"mean_abs={summary['mean_abs_jitter_us']:.1f} "
        f"p95_abs={summary['p95_abs_jitter_us']:.1f} "
        f"max_abs={summary['max_abs_jitter_us']:.1f}"
    )


def tick_delta_us(previous_tick: int, current_tick: int) -> int:
    return (current_tick - previous_tick) & 0xFFFFFFFF


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--samples", type=int, default=1200)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.05) as ser:
        session = SerialProtocolSession(ser)
        time.sleep(1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        ser.write(build_command_frame(WIRED_COMMAND_ID_GET_CAPABILITIES, request_id=1))
        capabilities_frame = session.read_matching_frame(
            message_type=WIRED_MESSAGE_TYPE_CAPABILITIES,
            request_id=1,
            timeout_s=4.0,
        )
        capabilities = decode_capabilities(capabilities_frame)

        host_timestamps: list[float] = []
        sequences: list[int] = []
        status_flags: list[int] = []
        device_ticks_by_sequence: dict[int, int] = {}

        while len(sequences) < args.warmup + args.samples:
            frame = session.read_next_frame(timeout_s=4.0)
            if frame.message_type == WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC:
                timing = decode_timing_diagnostic(frame)
                device_ticks_by_sequence[int(timing["sequence"])] = int(timing["sample_tick_us"])
                continue
            if frame.message_type != WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE:
                continue

            host_timestamps.append(time.monotonic())
            sample = decode_telemetry_sample(frame)
            sequences.append(int(sample["sequence"]))
            status_flags.append(int(sample["status_flags"]))

        drain_deadline = time.monotonic() + 0.25
        while time.monotonic() < drain_deadline:
            try:
                frame = session.read_next_frame(timeout_s=0.02)
            except TimeoutError:
                continue
            if frame.message_type == WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC:
                timing = decode_timing_diagnostic(frame)
                device_ticks_by_sequence[int(timing["sequence"])] = int(timing["sample_tick_us"])

    host_timestamps = host_timestamps[args.warmup:]
    sequences = sequences[args.warmup:]
    status_flags = status_flags[args.warmup:]
    nominal_period_ms = float(capabilities["nominal_sample_period_ms"])

    inter_arrival_ms = [
        (host_timestamps[index] - host_timestamps[index - 1]) * 1000.0
        for index in range(1, len(host_timestamps))
    ]
    device_inter_arrival_ms: list[float] = []
    matched_device_ticks = 0
    for previous_sequence, current_sequence in zip(sequences, sequences[1:]):
        previous_tick = device_ticks_by_sequence.get(previous_sequence)
        current_tick = device_ticks_by_sequence.get(current_sequence)
        if previous_tick is None or current_tick is None:
            continue
        if current_sequence != previous_sequence + 1:
            continue
        matched_device_ticks += 1
        device_inter_arrival_ms.append(tick_delta_us(previous_tick, current_tick) / 1000.0)

    sequence_gaps = [
        sequences[index] - sequences[index - 1]
        for index in range(1, len(sequences))
    ]
    gap_count = sum(1 for gap in sequence_gaps if gap != 1)
    host_summary = summarize_intervals(inter_arrival_ms)
    device_summary = summarize_intervals(device_inter_arrival_ms)
    device_jitter_summary = summarize_jitter_us(device_inter_arrival_ms, nominal_period_ms)

    print("Capabilities:", capabilities)
    print(f"Collected telemetry samples: {len(sequences)}")
    print(f"Nominal sample period (reported): {capabilities['nominal_sample_period_ms']} ms")
    print(f"Sequence first/last: {sequences[0]} -> {sequences[-1]}")
    print(f"Non-unit sequence gaps: {gap_count}")
    print(f"Observed status flags: {sorted(set(status_flags))}")
    print(f"Timing diagnostics matched: {matched_device_ticks}/{max(0, len(sequences) - 1)} interval(s)")
    print(format_interval_summary("Host read/decode inter-arrival ms", host_summary))
    print(format_interval_summary("Device sample interval ms", device_summary))
    print(format_jitter_summary("Device sample jitter us", device_jitter_summary))
    print("Note: host read/decode intervals include USB/OS buffering and probe loop batching; use device sample interval for firmware cadence.")
    print("wired_timing_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
