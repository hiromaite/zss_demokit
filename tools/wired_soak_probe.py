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
    RESULT_CODE_OK,
    WIRED_COMMAND_ID_GET_CAPABILITIES,
    WIRED_COMMAND_ID_GET_STATUS,
    WIRED_COMMAND_ID_SET_PUMP_STATE,
    WIRED_MESSAGE_TYPE_CAPABILITIES,
    WIRED_MESSAGE_TYPE_COMMAND_ACK,
    WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT,
    WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
)
from wired_protocol import (  # noqa: E402
    WiredFrame,
    WiredFrameBuffer,
    build_command_frame,
    decode_capabilities,
    decode_command_ack,
    decode_status_snapshot,
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


def expect_ack(session: SerialProtocolSession, request_id: int, command_id: int) -> dict[str, int | str]:
    frame = session.read_matching_frame(
        message_type=WIRED_MESSAGE_TYPE_COMMAND_ACK,
        request_id=request_id,
        timeout_s=4.0,
    )
    ack = decode_command_ack(frame)
    if int(ack["command_id"]) != command_id:
        raise AssertionError(f"ACK command mismatch: {ack['command_id']} != {command_id}")
    if int(ack["result_code"]) != RESULT_CODE_OK:
        raise AssertionError(f"ACK result_code={ack['result_code']} detail={ack['detail_u32']}")
    return ack


def expect_status(session: SerialProtocolSession, request_id: int) -> dict[str, object]:
    frame = session.read_matching_frame(
        message_type=WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT,
        request_id=request_id,
        timeout_s=4.0,
    )
    return decode_status_snapshot(frame)


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


def request_capabilities(session: SerialProtocolSession, ser: serial.Serial, request_id: int) -> dict[str, object]:
    ser.write(build_command_frame(WIRED_COMMAND_ID_GET_CAPABILITIES, request_id=request_id))
    expect_ack(session, request_id, WIRED_COMMAND_ID_GET_CAPABILITIES)
    frame = session.read_matching_frame(
        message_type=WIRED_MESSAGE_TYPE_CAPABILITIES,
        request_id=request_id,
        timeout_s=4.0,
    )
    return decode_capabilities(frame)


def request_status(session: SerialProtocolSession, ser: serial.Serial, request_id: int) -> dict[str, object]:
    ser.write(build_command_frame(WIRED_COMMAND_ID_GET_STATUS, request_id=request_id))
    expect_ack(session, request_id, WIRED_COMMAND_ID_GET_STATUS)
    return expect_status(session, request_id)


def set_pump_state(
    session: SerialProtocolSession,
    ser: serial.Serial,
    request_id: int,
    enabled: bool,
) -> dict[str, object]:
    ser.write(
        build_command_frame(
            WIRED_COMMAND_ID_SET_PUMP_STATE,
            request_id=request_id,
            arg0_u32=1 if enabled else 0,
        )
    )
    expect_ack(session, request_id, WIRED_COMMAND_ID_SET_PUMP_STATE)
    status = expect_status(session, request_id)
    if bool(status["pump_on"]) != enabled:
        raise AssertionError(f"Pump state mismatch after command: expected {enabled}, got {status}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--duration-s", type=float, default=30.0)
    parser.add_argument("--toggle-interval-s", type=float, default=2.5)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.05) as ser:
        session = SerialProtocolSession(ser)
        time.sleep(1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        request_id = 1
        capabilities = request_capabilities(session, ser, request_id)
        request_id += 1
        status = request_status(session, ser, request_id)
        request_id += 1

        if bool(status["pump_on"]):
            status = set_pump_state(session, ser, request_id, False)
            request_id += 1

        host_timestamps: list[float] = []
        sequences: list[int] = []
        status_flags: list[int] = []
        pump_states: list[bool] = []
        toggle_results: list[tuple[float, bool]] = []

        start_monotonic = time.monotonic()
        deadline = start_monotonic + args.duration_s
        next_toggle = start_monotonic + args.toggle_interval_s
        target_pump_state = True

        while time.monotonic() < deadline:
            frame = session.read_matching_frame(
                message_type=WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
                timeout_s=4.0,
            )
            host_now = time.monotonic()
            sample = decode_telemetry_sample(frame)
            host_timestamps.append(host_now)
            sequences.append(int(sample["sequence"]))
            status_flags.append(int(sample["status_flags"]))
            pump_states.append(bool(sample["pump_on"]))

            while host_now >= next_toggle and next_toggle <= deadline:
                status = set_pump_state(session, ser, request_id, target_pump_state)
                toggle_results.append((host_now - start_monotonic, bool(status["pump_on"])))
                target_pump_state = not target_pump_state
                request_id += 1
                next_toggle += args.toggle_interval_s

        if toggle_results and toggle_results[-1][1]:
            set_pump_state(session, ser, request_id, False)

    inter_arrival_ms = [
        (host_timestamps[index] - host_timestamps[index - 1]) * 1000.0
        for index in range(1, len(host_timestamps))
    ]
    sequence_gaps = [
        sequences[index] - sequences[index - 1]
        for index in range(1, len(sequences))
    ]
    gap_count = sum(1 for gap in sequence_gaps if gap != 1)
    interval_summary = summarize_intervals(inter_arrival_ms)

    if gap_count != 0:
        raise AssertionError(f"Non-unit sequence gaps detected: {gap_count}")

    print("Capabilities:", capabilities)
    print(f"Duration seconds: {args.duration_s:.1f}")
    print(f"Telemetry samples collected: {len(sequences)}")
    print(f"Sequence first/last: {sequences[0]} -> {sequences[-1]}")
    print(f"Observed status flags: {sorted(set(status_flags))}")
    print(f"Observed pump states in telemetry: {sorted(set(pump_states))}")
    print(f"Pump toggles confirmed: {len(toggle_results)}")
    if interval_summary:
        print(
            "Host inter-arrival ms: "
            f"mean={interval_summary['mean_ms']:.3f} "
            f"stdev={interval_summary['stdev_ms']:.3f} "
            f"min={interval_summary['min_ms']:.3f} "
            f"p95={interval_summary['p95_ms']:.3f} "
            f"max={interval_summary['max_ms']:.3f}"
        )
    print("wired_soak_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
