from __future__ import annotations

import argparse
import sys
import time
from collections import deque
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui_prototype" / "src"))

from protocol_constants import (  # noqa: E402
    EVENT_CODE_COMMAND_ERROR,
    RESULT_CODE_INVALID_STATE,
    RESULT_CODE_OK,
    RESULT_CODE_UNSUPPORTED_COMMAND,
    STATUS_FLAG_HEATER_POWER_ON,
    WIRED_COMMAND_ID_GET_CAPABILITIES,
    WIRED_COMMAND_ID_GET_STATUS,
    WIRED_COMMAND_ID_SET_HEATER_POWER_STATE,
    WIRED_COMMAND_ID_SET_PUMP_STATE,
    WIRED_MESSAGE_TYPE_CAPABILITIES,
    WIRED_MESSAGE_TYPE_COMMAND_ACK,
    WIRED_MESSAGE_TYPE_EVENT,
    WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT,
    WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
)
from wired_protocol import (  # noqa: E402
    WiredFrame,
    WiredFrameBuffer,
    build_command_frame,
    decode_capabilities,
    decode_command_ack,
    decode_event,
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

    def read_matching_frame(self, *, message_type: int, request_id: int | None = None, timeout_s: float = 3.0) -> WiredFrame:
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
            time.sleep(0.01)

        while skipped:
            self._pending_frames.appendleft(skipped.pop())
        raise TimeoutError(
            f"Timed out waiting for message_type=0x{message_type:02X}"
            + (f" request_id={request_id}" if request_id is not None else "")
        )


def expect_ack(
    session: SerialProtocolSession,
    request_id: int,
    command_id: int,
    *,
    expected_result_code: int = RESULT_CODE_OK,
) -> dict[str, int | str]:
    frame = session.read_matching_frame(
        message_type=WIRED_MESSAGE_TYPE_COMMAND_ACK,
        request_id=request_id,
        timeout_s=4.0,
    )
    ack = decode_command_ack(frame)
    if int(ack["command_id"]) != command_id:
        raise AssertionError(f"ACK command mismatch: {ack['command_id']} != {command_id}")
    if int(ack["result_code"]) != expected_result_code:
        raise AssertionError(f"ACK result_code={ack['result_code']} detail={ack['detail_u32']}")
    return ack


def expect_capabilities(session: SerialProtocolSession, request_id: int) -> dict[str, object]:
    frame = session.read_matching_frame(
        message_type=WIRED_MESSAGE_TYPE_CAPABILITIES,
        request_id=request_id,
        timeout_s=4.0,
    )
    return decode_capabilities(frame)


def expect_status(session: SerialProtocolSession, request_id: int) -> dict[str, object]:
    frame = session.read_matching_frame(
        message_type=WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT,
        request_id=request_id,
        timeout_s=4.0,
    )
    return decode_status_snapshot(frame)


def expect_telemetry(session: SerialProtocolSession, count: int) -> list[dict[str, object]]:
    collected: list[dict[str, object]] = []
    while len(collected) < count:
        frame = session.read_matching_frame(
            message_type=WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
            timeout_s=2.0,
        )
        collected.append(decode_telemetry_sample(frame))
    return collected


def expect_event(
    session: SerialProtocolSession,
    *,
    timeout_s: float = 3.0,
    expected_event_code: int | None = None,
) -> dict[str, int | str]:
    deadline = time.monotonic() + timeout_s
    observed: list[dict[str, int | str]] = []

    while time.monotonic() < deadline:
        remaining = max(0.1, deadline - time.monotonic())
        frame = session.read_matching_frame(
            message_type=WIRED_MESSAGE_TYPE_EVENT,
            timeout_s=remaining,
        )
        event = decode_event(frame)
        if expected_event_code is None or int(event["event_code"]) == expected_event_code:
            return event
        observed.append(event)

    raise TimeoutError(
        f"Timed out waiting for event_code={expected_event_code}; observed={observed}"
    )


def assert_monotonic_sequences(samples: list[dict[str, object]]) -> None:
    sequences = [int(sample["sequence"]) for sample in samples]
    if sequences != sorted(sequences):
        raise AssertionError(f"Telemetry sequences are not monotonic: {sequences}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.05) as ser:
        session = SerialProtocolSession(ser)
        time.sleep(1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        ser.write(build_command_frame(WIRED_COMMAND_ID_GET_CAPABILITIES, request_id=1))
        expect_ack(session, request_id=1, command_id=WIRED_COMMAND_ID_GET_CAPABILITIES)
        capabilities = expect_capabilities(session, request_id=1)
        print("Capabilities:", capabilities)
        if int(capabilities["nominal_sample_period_ms"]) != 10:
            raise AssertionError(f"Expected nominal_sample_period_ms=10, got {capabilities['nominal_sample_period_ms']}")
        if int(capabilities["transport_type_code"]) != 2:
            raise AssertionError(f"Expected transport_type_code=2, got {capabilities['transport_type_code']}")

        ser.write(build_command_frame(WIRED_COMMAND_ID_GET_STATUS, request_id=2))
        expect_ack(session, request_id=2, command_id=WIRED_COMMAND_ID_GET_STATUS)
        status = expect_status(session, request_id=2)
        print("Initial status:", status)

        ser.write(build_command_frame(WIRED_COMMAND_ID_SET_PUMP_STATE, request_id=3, arg0_u32=0))
        expect_ack(session, request_id=3, command_id=WIRED_COMMAND_ID_SET_PUMP_STATE)
        baseline_status = expect_status(session, request_id=3)
        print("Baseline OFF status:", baseline_status)
        if (int(baseline_status["status_flags"]) & 0x01) != 0:
            raise AssertionError("Baseline reset did not clear pump status flag bit 0")
        if (int(baseline_status["status_flags"]) & STATUS_FLAG_HEATER_POWER_ON) != 0:
            raise AssertionError("Baseline reset did not clear heater status flag bit 7")

        ser.write(build_command_frame(WIRED_COMMAND_ID_SET_HEATER_POWER_STATE, request_id=4, arg0_u32=1))
        bad_heater_ack = expect_ack(
            session,
            request_id=4,
            command_id=WIRED_COMMAND_ID_SET_HEATER_POWER_STATE,
            expected_result_code=RESULT_CODE_INVALID_STATE,
        )
        print("Heater ON while pump OFF ACK:", bad_heater_ack)
        heater_rejected_status = expect_status(session, request_id=4)
        print("Heater rejected status:", heater_rejected_status)
        if (int(heater_rejected_status["status_flags"]) & STATUS_FLAG_HEATER_POWER_ON) != 0:
            raise AssertionError("Heater ON while pump OFF should not set the heater status flag")
        heater_rejected_event = expect_event(
            session,
            timeout_s=4.0,
            expected_event_code=EVENT_CODE_COMMAND_ERROR,
        )
        print("Heater rejected event:", heater_rejected_event)

        ser.write(build_command_frame(WIRED_COMMAND_ID_SET_PUMP_STATE, request_id=5, arg0_u32=1))
        expect_ack(session, request_id=5, command_id=WIRED_COMMAND_ID_SET_PUMP_STATE)
        status_on = expect_status(session, request_id=5)
        print("Pump ON status:", status_on)
        if (int(status_on["status_flags"]) & 0x01) == 0:
            raise AssertionError("Pump ON did not set status flag bit 0")

        ser.write(build_command_frame(WIRED_COMMAND_ID_SET_HEATER_POWER_STATE, request_id=6, arg0_u32=1))
        expect_ack(session, request_id=6, command_id=WIRED_COMMAND_ID_SET_HEATER_POWER_STATE)
        heater_on_status = expect_status(session, request_id=6)
        print("Heater ON status:", heater_on_status)
        if (int(heater_on_status["status_flags"]) & STATUS_FLAG_HEATER_POWER_ON) == 0:
            raise AssertionError("Heater ON did not set status flag bit 7")

        session._pending_frames.clear()
        ser.reset_input_buffer()
        time.sleep(0.05)
        telemetry = expect_telemetry(session, count=5)
        print("Telemetry samples:", telemetry)
        assert_monotonic_sequences(telemetry)
        if any(int(sample["nominal_sample_period_ms"]) != 10 for sample in telemetry):
            raise AssertionError("Telemetry did not report nominal_sample_period_ms=10")
        if not any((int(sample["status_flags"]) & STATUS_FLAG_HEATER_POWER_ON) != 0 for sample in telemetry):
            raise AssertionError("Telemetry did not report heater ON state after enabling the heater")

        ser.write(build_command_frame(WIRED_COMMAND_ID_SET_PUMP_STATE, request_id=7, arg0_u32=0))
        expect_ack(session, request_id=7, command_id=WIRED_COMMAND_ID_SET_PUMP_STATE)
        status_off = expect_status(session, request_id=7)
        print("Pump OFF status:", status_off)
        if (int(status_off["status_flags"]) & 0x01) != 0:
            raise AssertionError("Pump OFF did not clear status flag bit 0")
        if (int(status_off["status_flags"]) & STATUS_FLAG_HEATER_POWER_ON) != 0:
            raise AssertionError("Pump OFF did not clear heater status flag bit 7")

        ser.write(build_command_frame(0x99, request_id=8))
        bad_ack = expect_ack(
            session,
            request_id=8,
            command_id=0x99,
            expected_result_code=RESULT_CODE_UNSUPPORTED_COMMAND,
        )
        print("Unsupported command ACK:", bad_ack)
        command_error_event = expect_event(
            session,
            timeout_s=4.0,
            expected_event_code=EVENT_CODE_COMMAND_ERROR,
        )
        print("Command error event:", command_error_event)
        if int(command_error_event["event_code"]) != EVENT_CODE_COMMAND_ERROR:
            raise AssertionError(
                f"Expected command_error event, got {command_error_event['event_name']}"
            )

    print("wired_serial_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
