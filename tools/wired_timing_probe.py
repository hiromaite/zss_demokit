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
)
from wired_protocol import (  # noqa: E402
    WiredFrame,
    WiredFrameBuffer,
    build_command_frame,
    decode_capabilities,
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

        while len(sequences) < args.warmup + args.samples:
            frame = session.read_matching_frame(
                message_type=WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
                timeout_s=4.0,
            )
            host_timestamps.append(time.monotonic())
            sample = decode_telemetry_sample(frame)
            sequences.append(int(sample["sequence"]))
            status_flags.append(int(sample["status_flags"]))

    host_timestamps = host_timestamps[args.warmup:]
    sequences = sequences[args.warmup:]
    status_flags = status_flags[args.warmup:]

    inter_arrival_ms = [
        (host_timestamps[index] - host_timestamps[index - 1]) * 1000.0
        for index in range(1, len(host_timestamps))
    ]
    sequence_gaps = [
        sequences[index] - sequences[index - 1]
        for index in range(1, len(sequences))
    ]
    gap_count = sum(1 for gap in sequence_gaps if gap != 1)
    summaries = summarize_intervals(inter_arrival_ms)

    print("Capabilities:", capabilities)
    print(f"Collected telemetry samples: {len(sequences)}")
    print(f"Nominal sample period (reported): {capabilities['nominal_sample_period_ms']} ms")
    print(f"Sequence first/last: {sequences[0]} -> {sequences[-1]}")
    print(f"Non-unit sequence gaps: {gap_count}")
    print(f"Observed status flags: {sorted(set(status_flags))}")
    if summaries:
        print(
            "Host inter-arrival ms: "
            f"mean={summaries['mean_ms']:.3f} "
            f"stdev={summaries['stdev_ms']:.3f} "
            f"min={summaries['min_ms']:.3f} "
            f"p95={summaries['p95_ms']:.3f} "
            f"max={summaries['max_ms']:.3f}"
        )
    print("wired_timing_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
