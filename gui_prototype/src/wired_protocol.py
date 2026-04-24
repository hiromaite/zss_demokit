from __future__ import annotations

import struct
from dataclasses import dataclass

from protocol_constants import (
    DEVICE_TYPE_CODE_ZIRCONIA_SENSOR,
    EVENT_CODE_ADC_FAULT_CLEARED,
    EVENT_CODE_ADC_FAULT_RAISED,
    EVENT_CODE_BOOT_COMPLETE,
    EVENT_CODE_COMMAND_ERROR,
    EVENT_CODE_WARNING_CLEARED,
    EVENT_CODE_WARNING_RAISED,
    PROTOCOL_VERSION_TEXT,
    STATUS_FLAG_HEATER_POWER_ON,
    STATUS_FLAG_PUMP_ON,
    SUPPORTED_COMMANDS,
    TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_HIGH_RANGE,
    TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_LOW_RANGE,
    TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED,
    TELEMETRY_FIELD_INTERNAL_VOLTAGE,
    TELEMETRY_FIELD_ZIRCONIA_IP_VOLTAGE,
    TELEMETRY_FIELDS,
    TRANSPORT_BLE,
    TRANSPORT_SERIAL,
    TRANSPORT_TYPE_CODE_BLE,
    TRANSPORT_TYPE_CODE_SERIAL,
    WIRED_COMMAND_ID_GET_CAPABILITIES,
    WIRED_COMMAND_ID_GET_STATUS,
    WIRED_COMMAND_ID_PING,
    WIRED_COMMAND_ID_SET_HEATER_POWER_STATE,
    WIRED_COMMAND_ID_SET_PUMP_STATE,
    WIRED_HEADER_SIZE,
    WIRED_MAX_PAYLOAD_BYTES,
    WIRED_MESSAGE_TYPE_CAPABILITIES,
    WIRED_MESSAGE_TYPE_COMMAND_ACK,
    WIRED_MESSAGE_TYPE_COMMAND_REQUEST,
    WIRED_MESSAGE_TYPE_EVENT,
    WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT,
    WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
    WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC,
    WIRED_SOF0,
    WIRED_SOF1,
    result_code_to_text,
)


@dataclass(slots=True)
class WiredFrame:
    version_major: int
    version_minor: int
    message_type: int
    sequence: int
    request_id: int
    payload: bytes


class WiredFrameBuffer:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def clear(self) -> None:
        self._buffer.clear()

    def push(self, chunk: bytes) -> list[WiredFrame]:
        if chunk:
            self._buffer.extend(chunk)

        frames: list[WiredFrame] = []
        while True:
            while len(self._buffer) >= 2:
                if self._buffer[0] == WIRED_SOF0 and self._buffer[1] == WIRED_SOF1:
                    break
                del self._buffer[0]

            if len(self._buffer) < WIRED_HEADER_SIZE + 2:
                return frames

            payload_length = struct.unpack_from("<H", self._buffer, 6)[0]
            if payload_length > WIRED_MAX_PAYLOAD_BYTES:
                del self._buffer[0]
                continue

            total_size = WIRED_HEADER_SIZE + payload_length + 2
            if len(self._buffer) < total_size:
                return frames

            frame_bytes = bytes(self._buffer[:total_size])
            del self._buffer[:total_size]

            expected_crc = crc16_ccitt_false(frame_bytes[2:-2])
            received_crc = struct.unpack_from("<H", frame_bytes, total_size - 2)[0]
            if expected_crc != received_crc:
                continue

            _, _, version_major, version_minor, message_type, _, _, sequence, request_id = struct.unpack_from(
                "<BBBBBBHII",
                frame_bytes,
                0,
            )
            payload = frame_bytes[WIRED_HEADER_SIZE:-2]
            frames.append(
                WiredFrame(
                    version_major=version_major,
                    version_minor=version_minor,
                    message_type=message_type,
                    sequence=sequence,
                    request_id=request_id,
                    payload=payload,
                )
            )


def crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_command_frame(command_id: int, request_id: int, arg0_u32: int = 0, options: int = 0) -> bytes:
    payload = struct.pack("<BBHIII", command_id, options, 0, arg0_u32, 0, 0)
    header = struct.pack(
        "<BBBBBBHII",
        WIRED_SOF0,
        WIRED_SOF1,
        1,
        0,
        WIRED_MESSAGE_TYPE_COMMAND_REQUEST,
        0,
        len(payload),
        0,
        request_id,
    )
    crc = crc16_ccitt_false(header[2:] + payload)
    return header + payload + struct.pack("<H", crc)


def build_protocol_version_text(frame: WiredFrame) -> str:
    return f"{frame.version_major}.{frame.version_minor}"


def decode_command_ack(frame: WiredFrame) -> dict[str, int | str]:
    command_id, result_code, _, detail_u32 = struct.unpack("<BBHI", frame.payload)
    return {
        "command_id": command_id,
        "result_code": result_code,
        "result_text": result_code_to_text(result_code),
        "detail_u32": detail_u32,
    }


def decode_capabilities(frame: WiredFrame) -> dict[str, object]:
    values = struct.unpack("<BBBBBBHHHHHI", frame.payload)
    transport_code = int(values[2])
    transport_type = TRANSPORT_SERIAL if transport_code == TRANSPORT_TYPE_CODE_SERIAL else TRANSPORT_BLE
    device_type = "unknown"
    if int(values[1]) == DEVICE_TYPE_CODE_ZIRCONIA_SENSOR:
        device_type = "zirconia_sensor"

    supported_commands = []
    supported_bits = int(values[6])
    if supported_bits & (1 << 0):
        supported_commands.append(SUPPORTED_COMMANDS[0])
    if supported_bits & (1 << 1):
        supported_commands.append(SUPPORTED_COMMANDS[1])
    if supported_bits & (1 << 2):
        supported_commands.append(SUPPORTED_COMMANDS[2])
    if supported_bits & (1 << 3):
        supported_commands.append(SUPPORTED_COMMANDS[3])
    if supported_bits & (1 << 4):
        supported_commands.append(SUPPORTED_COMMANDS[4])

    telemetry_fields = []
    telemetry_bits = int(values[7])
    if telemetry_bits & (1 << 0):
        telemetry_fields.append(TELEMETRY_FIELDS[0])
    if telemetry_bits & (1 << 1):
        telemetry_fields.append(TELEMETRY_FIELDS[1])
    if telemetry_bits & TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED:
        telemetry_fields.append(TELEMETRY_FIELDS[2])
    if telemetry_bits & TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_LOW_RANGE:
        telemetry_fields.append(TELEMETRY_FIELDS[3])
    if telemetry_bits & TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_HIGH_RANGE:
        telemetry_fields.append(TELEMETRY_FIELDS[4])
    if telemetry_bits & TELEMETRY_FIELD_ZIRCONIA_IP_VOLTAGE:
        telemetry_fields.append(TELEMETRY_FIELDS[5])
    if telemetry_bits & TELEMETRY_FIELD_INTERNAL_VOLTAGE:
        telemetry_fields.append(TELEMETRY_FIELDS[6])

    return {
        "protocol_version": build_protocol_version_text(frame),
        "capability_schema_version": int(values[0]),
        "device_type_code": int(values[1]),
        "device_type": device_type,
        "transport_type_code": transport_code,
        "transport_type": transport_type,
        "firmware_version": f"{int(values[3])}.{int(values[4])}.{int(values[5])}",
        "supported_command_bits": supported_bits,
        "supported_commands": supported_commands,
        "telemetry_field_bits": telemetry_bits,
        "telemetry_fields": telemetry_fields,
        "nominal_sample_period_ms": int(values[8]),
        "status_flag_schema_version": int(values[9]),
        "max_payload_bytes": int(values[10]),
        "feature_bits": int(values[11]),
    }


def decode_status_snapshot(frame: WiredFrame) -> dict[str, object]:
    if len(frame.payload) == 20:
        status_flags, nominal_sample_period_ms, telemetry_field_bits, zirconia, heater, flow_raw = struct.unpack(
            "<IHHfff",
            frame.payload,
        )
        low_range_raw = None
        high_range_raw = None
        zirconia_ip_voltage_v = None
        internal_voltage_v = None
    elif len(frame.payload) == 28:
        status_flags, nominal_sample_period_ms, telemetry_field_bits, zirconia, heater, flow_raw, low_range_raw, high_range_raw = struct.unpack(
            "<IHHfffff",
            frame.payload,
        )
        zirconia_ip_voltage_v = None
        internal_voltage_v = None
    elif len(frame.payload) == 36:
        (
            status_flags,
            nominal_sample_period_ms,
            telemetry_field_bits,
            zirconia,
            heater,
            flow_raw,
            low_range_raw,
            high_range_raw,
            zirconia_ip_voltage_v,
            internal_voltage_v,
        ) = struct.unpack("<IHHfffffff", frame.payload)
    else:
        raise ValueError(f"Expected 20-byte, 28-byte, or 36-byte wired status payload, got {len(frame.payload)} bytes")
    differential_pressure_selected_pa = None
    if telemetry_field_bits & TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED:
        differential_pressure_selected_pa = flow_raw
    if (telemetry_field_bits & TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_LOW_RANGE) == 0:
        low_range_raw = None
    if (telemetry_field_bits & TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_HIGH_RANGE) == 0:
        high_range_raw = None
    if (telemetry_field_bits & TELEMETRY_FIELD_ZIRCONIA_IP_VOLTAGE) == 0:
        zirconia_ip_voltage_v = None
    if (telemetry_field_bits & TELEMETRY_FIELD_INTERNAL_VOLTAGE) == 0:
        internal_voltage_v = None
    return {
        "protocol_version": build_protocol_version_text(frame),
        "status_flags": status_flags,
        "nominal_sample_period_ms": nominal_sample_period_ms,
        "telemetry_field_bits": telemetry_field_bits,
        "zirconia_output_voltage_v": zirconia,
        "heater_rtd_resistance_ohm": heater,
        "differential_pressure_selected_pa": differential_pressure_selected_pa,
        "differential_pressure_low_range_pa": low_range_raw,
        "differential_pressure_high_range_pa": high_range_raw,
        "zirconia_ip_voltage_v": zirconia_ip_voltage_v,
        "internal_voltage_v": internal_voltage_v,
        "pump_on": (status_flags & STATUS_FLAG_PUMP_ON) != 0,
        "heater_power_on": (status_flags & STATUS_FLAG_HEATER_POWER_ON) != 0,
    }


def decode_telemetry_sample(frame: WiredFrame) -> dict[str, object]:
    values = decode_status_snapshot(frame)
    values["sequence"] = frame.sequence
    return values


def decode_event(frame: WiredFrame) -> dict[str, int | str]:
    event_code, severity_code, _, detail_u32 = struct.unpack("<BBHI", frame.payload)
    event_labels = {
        EVENT_CODE_BOOT_COMPLETE: "boot_complete",
        EVENT_CODE_WARNING_RAISED: "warning_raised",
        EVENT_CODE_WARNING_CLEARED: "warning_cleared",
        EVENT_CODE_COMMAND_ERROR: "command_error",
        EVENT_CODE_ADC_FAULT_RAISED: "adc_fault_raised",
        EVENT_CODE_ADC_FAULT_CLEARED: "adc_fault_cleared",
    }
    severity_labels = {
        0: "info",
        1: "warn",
        2: "error",
    }
    return {
        "event_code": event_code,
        "event_name": event_labels.get(event_code, f"unknown_{event_code}"),
        "severity_code": severity_code,
        "severity": severity_labels.get(severity_code, "info"),
        "detail_u32": detail_u32,
        "sequence": frame.sequence,
    }


def decode_timing_diagnostic(frame: WiredFrame) -> dict[str, int]:
    (sample_tick_us,) = struct.unpack("<I", frame.payload)
    return {
        "sequence": frame.sequence,
        "sample_tick_us": sample_tick_us,
    }


def command_name_from_id(command_id: int) -> str:
    labels = {
        WIRED_COMMAND_ID_GET_CAPABILITIES: "get_capabilities",
        WIRED_COMMAND_ID_GET_STATUS: "get_status",
        WIRED_COMMAND_ID_SET_PUMP_STATE: "set_pump_state",
        WIRED_COMMAND_ID_PING: "ping",
        WIRED_COMMAND_ID_SET_HEATER_POWER_STATE: "set_heater_power_state",
    }
    return labels.get(command_id, f"unknown_{command_id}")


def message_name_from_type(message_type: int) -> str:
    labels = {
        WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE: "telemetry_sample",
        WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT: "status_snapshot",
        WIRED_MESSAGE_TYPE_CAPABILITIES: "capabilities",
        WIRED_MESSAGE_TYPE_COMMAND_ACK: "command_ack",
        WIRED_MESSAGE_TYPE_EVENT: "event",
        WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC: "timing_diagnostic",
    }
    return labels.get(message_type, f"unknown_{message_type}")
