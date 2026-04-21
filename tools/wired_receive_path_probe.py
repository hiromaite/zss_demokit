from __future__ import annotations

import argparse
import queue
import statistics
import sys
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass
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


@dataclass(slots=True)
class ChunkRecord:
    received_at: float
    payload: bytes


@dataclass(slots=True)
class ParsedFrame:
    frame: WiredFrame
    chunk_received_at: float
    handled_at: float
    frames_in_same_chunk: int


class SerialReaderThread(threading.Thread):
    def __init__(self, ser: serial.Serial, out_queue: queue.SimpleQueue[ChunkRecord], stop_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self._serial = ser
        self._out_queue = out_queue
        self._stop_event = stop_event

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                waiting = max(1, int(getattr(self._serial, "in_waiting", 0)))
                chunk = self._serial.read(waiting)
            except Exception:
                return
            if not chunk:
                continue
            self._out_queue.put(
                ChunkRecord(
                    received_at=time.monotonic(),
                    payload=chunk,
                )
            )


class PollProcessorThread(threading.Thread):
    def __init__(
        self,
        in_queue: queue.SimpleQueue[ChunkRecord],
        out_queue: queue.SimpleQueue[ParsedFrame],
        stop_event: threading.Event,
        poll_interval_ms: float,
    ) -> None:
        super().__init__(daemon=True)
        self._in_queue = in_queue
        self._out_queue = out_queue
        self._stop_event = stop_event
        self._poll_interval_s = poll_interval_ms / 1000.0
        self._frame_buffer = WiredFrameBuffer()

    def run(self) -> None:
        while not self._stop_event.is_set():
            drained: list[ChunkRecord] = []
            while True:
                try:
                    drained.append(self._in_queue.get_nowait())
                except queue.Empty:
                    break

            if drained:
                handled_at = time.monotonic()
                for record in drained:
                    frames = self._frame_buffer.push(record.payload)
                    frame_count = len(frames)
                    for frame in frames:
                        self._out_queue.put(
                            ParsedFrame(
                                frame=frame,
                                chunk_received_at=record.received_at,
                                handled_at=handled_at,
                                frames_in_same_chunk=frame_count,
                            )
                        )

            time.sleep(self._poll_interval_s)


class ReceivePathSession:
    def __init__(self, ser: serial.Serial, poll_interval_ms: float) -> None:
        self._serial = ser
        self._poll_interval_s = poll_interval_ms / 1000.0
        self._chunk_queue: queue.SimpleQueue[ChunkRecord] = queue.SimpleQueue()
        self._frame_queue: queue.SimpleQueue[ParsedFrame] = queue.SimpleQueue()
        self._stop_event = threading.Event()
        self._reader = SerialReaderThread(ser, self._chunk_queue, self._stop_event)
        self._pending_frames: deque[ParsedFrame] = deque()
        self._processor = PollProcessorThread(
            self._chunk_queue,
            self._frame_queue,
            self._stop_event,
            poll_interval_ms=poll_interval_ms,
        )

    def start(self) -> None:
        self._reader.start()
        self._processor.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._reader.join(timeout=0.5)
        self._processor.join(timeout=0.5)

    def read_matching_frame(
        self,
        *,
        message_type: int,
        request_id: int | None = None,
        timeout_s: float = 4.0,
    ) -> ParsedFrame:
        deadline = time.monotonic() + timeout_s
        skipped: deque[ParsedFrame] = deque()

        while time.monotonic() < deadline:
            while self._pending_frames:
                item = self._pending_frames.popleft()
                frame = item.frame
                if frame.message_type == message_type and (request_id is None or frame.request_id == request_id):
                    while skipped:
                        self._pending_frames.appendleft(skipped.pop())
                    return item
                skipped.append(item)

            try:
                self._pending_frames.append(self._frame_queue.get(timeout=self._poll_interval_s))
            except queue.Empty:
                pass

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
        description="Compare serial read timestamp jitter against GUI-like poll handling jitter on wired telemetry."
    )
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--samples", type=int, default=1200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--poll-interval-ms", type=float, default=5.0)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.02) as ser:
        session = ReceivePathSession(ser, poll_interval_ms=args.poll_interval_ms)
        session.start()
        try:
            time.sleep(1.5)
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            ser.write(build_command_frame(WIRED_COMMAND_ID_GET_CAPABILITIES, request_id=1))
            capabilities_frame = session.read_matching_frame(
                message_type=WIRED_MESSAGE_TYPE_CAPABILITIES,
                request_id=1,
                timeout_s=4.0,
            )
            capabilities = decode_capabilities(capabilities_frame.frame)

            chunk_received_timestamps: list[float] = []
            handled_timestamps: list[float] = []
            handling_delay_ms: list[float] = []
            sequences: list[int] = []
            frames_per_chunk_samples: list[int] = []

            while len(sequences) < args.warmup + args.samples:
                item = session.read_matching_frame(
                    message_type=WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
                    timeout_s=4.0,
                )
                payload = decode_telemetry_sample(item.frame)
                chunk_received_timestamps.append(item.chunk_received_at)
                handled_timestamps.append(item.handled_at)
                handling_delay_ms.append((item.handled_at - item.chunk_received_at) * 1000.0)
                sequences.append(int(payload["sequence"]))
                frames_per_chunk_samples.append(item.frames_in_same_chunk)
        finally:
            session.stop()

    chunk_received_timestamps = chunk_received_timestamps[args.warmup:]
    handled_timestamps = handled_timestamps[args.warmup:]
    handling_delay_ms = handling_delay_ms[args.warmup:]
    sequences = sequences[args.warmup:]
    frames_per_chunk_samples = frames_per_chunk_samples[args.warmup:]

    receive_intervals_ms = [
        (chunk_received_timestamps[index] - chunk_received_timestamps[index - 1]) * 1000.0
        for index in range(1, len(chunk_received_timestamps))
    ]
    handled_intervals_ms = [
        (handled_timestamps[index] - handled_timestamps[index - 1]) * 1000.0
        for index in range(1, len(handled_timestamps))
    ]
    sequence_gaps = [
        sequences[index] - sequences[index - 1]
        for index in range(1, len(sequences))
    ]
    non_unit_gap_total = sum(max(0, gap - 1) for gap in sequence_gaps)
    same_receive_timestamp_pairs = sum(
        1
        for index in range(1, len(chunk_received_timestamps))
        if chunk_received_timestamps[index] == chunk_received_timestamps[index - 1]
    )
    same_handled_timestamp_pairs = sum(
        1
        for index in range(1, len(handled_timestamps))
        if handled_timestamps[index] == handled_timestamps[index - 1]
    )
    batch_histogram = Counter(frames_per_chunk_samples)

    print("Capabilities:", capabilities)
    print(f"Collected telemetry samples: {len(sequences)}")
    print(f"Sequence first/last: {sequences[0]} -> {sequences[-1]}")
    print(f"Non-unit sequence gap total: {non_unit_gap_total}")

    receive_summary = summarize(receive_intervals_ms)
    if receive_summary:
        print(
            "Reader-side receive inter-arrival ms: "
            f"mean={receive_summary['mean']:.3f} "
            f"stdev={receive_summary['stdev']:.3f} "
            f"min={receive_summary['min']:.3f} "
            f"p95={receive_summary['p95']:.3f} "
            f"max={receive_summary['max']:.3f}"
        )

    handled_summary = summarize(handled_intervals_ms)
    if handled_summary:
        print(
            "Poll-handled inter-arrival ms: "
            f"mean={handled_summary['mean']:.3f} "
            f"stdev={handled_summary['stdev']:.3f} "
            f"min={handled_summary['min']:.3f} "
            f"p95={handled_summary['p95']:.3f} "
            f"max={handled_summary['max']:.3f}"
        )

    delay_summary = summarize(handling_delay_ms)
    if delay_summary:
        print(
            "Handling delay ms (handled_at - chunk_received_at): "
            f"mean={delay_summary['mean']:.3f} "
            f"stdev={delay_summary['stdev']:.3f} "
            f"min={delay_summary['min']:.3f} "
            f"p95={delay_summary['p95']:.3f} "
            f"max={delay_summary['max']:.3f}"
        )

    print(f"Samples decoded from multi-frame chunks: {sum(1 for count in frames_per_chunk_samples if count > 1)}/{len(frames_per_chunk_samples)}")
    print(f"Consecutive samples sharing identical reader timestamp: {same_receive_timestamp_pairs}")
    print(f"Consecutive samples sharing identical handled timestamp: {same_handled_timestamp_pairs}")
    print("Frames-per-chunk histogram:")
    for frame_count in sorted(batch_histogram):
        print(f"  {frame_count}: {batch_histogram[frame_count]}")

    print("wired_receive_path_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
