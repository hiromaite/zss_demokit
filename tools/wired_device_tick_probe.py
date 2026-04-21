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


class SerialDiagnosticSession:
    def __init__(self, ser: serial.Serial) -> None:
        self._serial = ser
        self._frame_buffer = WiredFrameBuffer()
        self._pending_frames: deque[tuple[WiredFrame, float, int]] = deque()

    def _pump_frames(self) -> None:
        waiting = max(1, int(getattr(self._serial, "in_waiting", 0)))
        chunk = self._serial.read(waiting)
        if not chunk:
            return

        received_at = time.monotonic()
        frames = self._frame_buffer.push(chunk)
        frame_count = len(frames)
        for frame in frames:
            self._pending_frames.append((frame, received_at, frame_count))

    def read_next_frame(self, timeout_s: float = 4.0) -> tuple[WiredFrame, float, int]:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._pending_frames:
                return self._pending_frames.popleft()
            self._pump_frames()
            time.sleep(0.0005)
        raise TimeoutError("Timed out waiting for next wired frame")

    def read_matching_frame(
        self,
        *,
        message_type: int,
        request_id: int | None = None,
        timeout_s: float = 4.0,
    ) -> tuple[WiredFrame, float, int]:
        deadline = time.monotonic() + timeout_s
        skipped: deque[tuple[WiredFrame, float, int]] = deque()

        while time.monotonic() < deadline:
            while self._pending_frames:
                item = self._pending_frames.popleft()
                frame = item[0]
                if frame.message_type == message_type and (request_id is None or frame.request_id == request_id):
                    while skipped:
                        self._pending_frames.appendleft(skipped.pop())
                    return item
                skipped.append(item)
            self._pump_frames()
            time.sleep(0.0005)

        while skipped:
            self._pending_frames.appendleft(skipped.pop())
        raise TimeoutError(
            f"Timed out waiting for message_type=0x{message_type:02X}"
            + (f" request_id={request_id}" if request_id is not None else "")
        )


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * 0.95))))
    return {
        "mean": statistics.fmean(values),
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": ordered[0],
        "p95": ordered[p95_index],
        "max": ordered[-1],
    }


def delta_u32(newer: int, older: int) -> int:
    return (newer - older) & 0xFFFFFFFF


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare device-side sample tick cadence against host-side receive timing on wired telemetry."
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--samples", type=int, default=1200)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.05) as ser:
        session = SerialDiagnosticSession(ser)
        time.sleep(1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        ser.write(build_command_frame(WIRED_COMMAND_ID_GET_CAPABILITIES, request_id=1))
        capabilities_frame, _, _ = session.read_matching_frame(
            message_type=WIRED_MESSAGE_TYPE_CAPABILITIES,
            request_id=1,
            timeout_s=4.0,
        )
        capabilities = decode_capabilities(capabilities_frame)

        telemetry_by_sequence: dict[int, tuple[float, dict[str, object]]] = {}
        timing_by_sequence: dict[int, int] = {}

        paired_sequences: list[int] = []
        paired_receive_times: list[float] = []
        paired_sample_ticks_us: list[int] = []

        target_pairs = args.warmup + args.samples
        while len(paired_sequences) < target_pairs:
            frame, received_at, _ = session.read_next_frame(timeout_s=4.0)

            if frame.message_type == WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE:
                telemetry_by_sequence[frame.sequence] = (received_at, decode_telemetry_sample(frame))
            elif frame.message_type == WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC:
                payload = decode_timing_diagnostic(frame)
                timing_by_sequence[frame.sequence] = int(payload["sample_tick_us"])
            else:
                continue

            if frame.sequence in telemetry_by_sequence and frame.sequence in timing_by_sequence:
                telemetry_received_at, _ = telemetry_by_sequence.pop(frame.sequence)
                sample_tick_us = timing_by_sequence.pop(frame.sequence)
                paired_sequences.append(frame.sequence)
                paired_receive_times.append(telemetry_received_at)
                paired_sample_ticks_us.append(sample_tick_us)

        paired_sequences = paired_sequences[args.warmup:]
        paired_receive_times = paired_receive_times[args.warmup:]
        paired_sample_ticks_us = paired_sample_ticks_us[args.warmup:]

    host_intervals_ms = [
        (paired_receive_times[index] - paired_receive_times[index - 1]) * 1000.0
        for index in range(1, len(paired_receive_times))
    ]
    device_intervals_ms = [
        delta_u32(paired_sample_ticks_us[index], paired_sample_ticks_us[index - 1]) / 1000.0
        for index in range(1, len(paired_sample_ticks_us))
    ]
    sequence_gaps = [
        paired_sequences[index] - paired_sequences[index - 1]
        for index in range(1, len(paired_sequences))
    ]
    non_unit_gap_total = sum(max(0, gap - 1) for gap in sequence_gaps)

    host_summary = summarize(host_intervals_ms)
    device_summary = summarize(device_intervals_ms)
    device_minus_host_ms = [
        device_intervals_ms[index] - host_intervals_ms[index]
        for index in range(min(len(device_intervals_ms), len(host_intervals_ms)))
    ]
    diff_summary = summarize(device_minus_host_ms)

    print("Capabilities:", capabilities)
    print(f"Collected paired telemetry/timing samples: {len(paired_sequences)}")
    print(f"Sequence first/last: {paired_sequences[0]} -> {paired_sequences[-1]}")
    print(f"Non-unit sequence gap total: {non_unit_gap_total}")
    if host_summary:
        print(
            "Host receive inter-arrival ms: "
            f"mean={host_summary['mean']:.3f} "
            f"stdev={host_summary['stdev']:.3f} "
            f"min={host_summary['min']:.3f} "
            f"p95={host_summary['p95']:.3f} "
            f"max={host_summary['max']:.3f}"
        )
    if device_summary:
        print(
            "Device sample tick interval ms: "
            f"mean={device_summary['mean']:.3f} "
            f"stdev={device_summary['stdev']:.3f} "
            f"min={device_summary['min']:.3f} "
            f"p95={device_summary['p95']:.3f} "
            f"max={device_summary['max']:.3f}"
        )
    if diff_summary:
        print(
            "Device minus host interval ms: "
            f"mean={diff_summary['mean']:.3f} "
            f"stdev={diff_summary['stdev']:.3f} "
            f"min={diff_summary['min']:.3f} "
            f"p95={diff_summary['p95']:.3f} "
            f"max={diff_summary['max']:.3f}"
        )

    print("wired_device_tick_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
