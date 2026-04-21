from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections import Counter, deque
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


class SerialBatchSession:
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

    def read_matching_frame(
        self,
        *,
        message_type: int,
        request_id: int | None = None,
        timeout_s: float = 3.0,
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Investigate host-side batching and receive jitter on the wired telemetry path."
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--samples", type=int, default=1200)
    parser.add_argument("--warmup", type=int, default=20)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.05) as ser:
        session = SerialBatchSession(ser)
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

        received_timestamps: list[float] = []
        sequences: list[int] = []
        frames_per_chunk_samples: list[int] = []

        while len(sequences) < args.warmup + args.samples:
            frame, received_at, frames_in_same_chunk = session.read_matching_frame(
                message_type=WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
                timeout_s=4.0,
            )
            payload = decode_telemetry_sample(frame)
            received_timestamps.append(received_at)
            sequences.append(int(payload["sequence"]))
            frames_per_chunk_samples.append(frames_in_same_chunk)

    received_timestamps = received_timestamps[args.warmup:]
    sequences = sequences[args.warmup:]
    frames_per_chunk_samples = frames_per_chunk_samples[args.warmup:]

    telemetry_intervals_ms = [
        (received_timestamps[index] - received_timestamps[index - 1]) * 1000.0
        for index in range(1, len(received_timestamps))
    ]
    sequence_gaps = [
        sequences[index] - sequences[index - 1]
        for index in range(1, len(sequences))
    ]
    non_unit_gap_total = sum(max(0, gap - 1) for gap in sequence_gaps)
    multi_frame_samples = sum(1 for count in frames_per_chunk_samples if count > 1)
    same_timestamp_pairs = sum(
        1
        for index in range(1, len(received_timestamps))
        if received_timestamps[index] == received_timestamps[index - 1]
    )
    batch_histogram = Counter(frames_per_chunk_samples)

    print("Capabilities:", capabilities)
    print(f"Collected telemetry samples: {len(sequences)}")
    print(f"Sequence first/last: {sequences[0]} -> {sequences[-1]}")
    print(f"Non-unit sequence gap total: {non_unit_gap_total}")

    interval_summary = summarize(telemetry_intervals_ms)
    if interval_summary:
        print(
            "Telemetry receive inter-arrival ms: "
            f"mean={interval_summary['mean']:.3f} "
            f"stdev={interval_summary['stdev']:.3f} "
            f"min={interval_summary['min']:.3f} "
            f"p95={interval_summary['p95']:.3f} "
            f"max={interval_summary['max']:.3f}"
        )

    print(f"Samples decoded from multi-frame chunks: {multi_frame_samples}/{len(frames_per_chunk_samples)}")
    print(f"Consecutive samples sharing identical receive timestamp: {same_timestamp_pairs}")
    print("Frames-per-chunk histogram:")
    for frame_count in sorted(batch_histogram):
        print(f"  {frame_count}: {batch_histogram[frame_count]}")

    print("wired_batch_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
