from __future__ import annotations

import struct

from protocol_constants import (
    DEVICE_TYPE_CODE_ZIRCONIA_SENSOR,
    EVENT_CODE_ADC_FAULT_CLEARED,
    EVENT_CODE_ADC_FAULT_RAISED,
    EVENT_CODE_BOOT_COMPLETE,
    EVENT_CODE_COMMAND_ERROR,
    EVENT_CODE_WARNING_CLEARED,
    EVENT_CODE_WARNING_RAISED,
    STATUS_FLAG_PUMP_ON,
    SUPPORTED_COMMANDS,
    TELEMETRY_FIELDS,
    TRANSPORT_BLE,
    TRANSPORT_TYPE_CODE_BLE,
)


def decode_ble_telemetry_packet(data: bytes) -> dict[str, object]:
    if len(data) != 32:
        raise ValueError(f"Expected 32-byte BLE telemetry packet, got {len(data)} bytes")

    return {
        "protocol_version": f"{data[0]}.{data[1]}",
        "telemetry_schema_version": data[2],
        "header_flags": data[3],
        "sequence": struct.unpack_from("<I", data, 4)[0],
        "status_flags": struct.unpack_from("<I", data, 8)[0],
        "zirconia_output_voltage_v": struct.unpack_from("<f", data, 12)[0],
        "heater_rtd_resistance_ohm": struct.unpack_from("<f", data, 16)[0],
        "flow_sensor_voltage_v": struct.unpack_from("<f", data, 20)[0],
        "nominal_sample_period_ms": struct.unpack_from("<H", data, 24)[0],
        "telemetry_field_bits": struct.unpack_from("<H", data, 26)[0],
        "diagnostic_bits": struct.unpack_from("<I", data, 28)[0],
        "pump_on": (struct.unpack_from("<I", data, 8)[0] & STATUS_FLAG_PUMP_ON) != 0,
    }


def decode_ble_status_snapshot(data: bytes) -> dict[str, object]:
    if len(data) != 28:
        raise ValueError(f"Expected 28-byte BLE status packet, got {len(data)} bytes")

    status_flags = struct.unpack_from("<I", data, 8)[0]
    return {
        "protocol_version": f"{data[0]}.{data[1]}",
        "status_snapshot_schema_version": data[2],
        "response_code": data[3],
        "sequence": struct.unpack_from("<I", data, 4)[0],
        "status_flags": status_flags,
        "status_flags_hex": f"0x{status_flags:08X}",
        "nominal_sample_period_ms": struct.unpack_from("<H", data, 12)[0],
        "telemetry_field_bits": struct.unpack_from("<H", data, 14)[0],
        "zirconia_output_voltage_v": struct.unpack_from("<f", data, 16)[0],
        "heater_rtd_resistance_ohm": struct.unpack_from("<f", data, 20)[0],
        "flow_sensor_voltage_v": struct.unpack_from("<f", data, 24)[0],
        "pump_on": (status_flags & STATUS_FLAG_PUMP_ON) != 0,
    }


def decode_ble_capabilities_packet(data: bytes) -> dict[str, object]:
    if len(data) != 24:
        raise ValueError(f"Expected 24-byte BLE capabilities packet, got {len(data)} bytes")

    device_type_code = data[3]
    transport_type_code = data[4]
    supported_command_bits = struct.unpack_from("<H", data, 8)[0]
    telemetry_field_bits = struct.unpack_from("<H", data, 10)[0]

    supported_commands = []
    if supported_command_bits & (1 << 0):
        supported_commands.append(SUPPORTED_COMMANDS[0])
    if supported_command_bits & (1 << 1):
        supported_commands.append(SUPPORTED_COMMANDS[1])
    if supported_command_bits & (1 << 2):
        supported_commands.append(SUPPORTED_COMMANDS[2])
    if supported_command_bits & (1 << 3):
        supported_commands.append(SUPPORTED_COMMANDS[3])

    telemetry_fields = []
    if telemetry_field_bits & (1 << 0):
        telemetry_fields.append(TELEMETRY_FIELDS[0])
    if telemetry_field_bits & (1 << 1):
        telemetry_fields.append(TELEMETRY_FIELDS[1])
    if telemetry_field_bits & (1 << 2):
        telemetry_fields.append(TELEMETRY_FIELDS[2])

    device_type = "unknown"
    if device_type_code == DEVICE_TYPE_CODE_ZIRCONIA_SENSOR:
        device_type = "zirconia_sensor"

    transport_type = "unknown"
    if transport_type_code == TRANSPORT_TYPE_CODE_BLE:
        transport_type = TRANSPORT_BLE

    return {
        "protocol_version": f"{data[0]}.{data[1]}",
        "capability_schema_version": data[2],
        "device_type_code": device_type_code,
        "device_type": device_type,
        "transport_type_code": transport_type_code,
        "transport_type": transport_type,
        "firmware_version": f"{data[5]}.{data[6]}.{data[7]}",
        "supported_command_bits": supported_command_bits,
        "supported_commands": supported_commands,
        "telemetry_field_bits": telemetry_field_bits,
        "telemetry_fields": telemetry_fields,
        "nominal_sample_period_ms": struct.unpack_from("<H", data, 12)[0],
        "status_flag_schema_version": struct.unpack_from("<H", data, 14)[0],
        "max_payload_bytes": struct.unpack_from("<H", data, 16)[0],
        "feature_bits": struct.unpack_from("<I", data, 20)[0],
    }


def decode_ble_event_packet(data: bytes) -> dict[str, object]:
    if len(data) != 12:
        raise ValueError(f"Expected 12-byte BLE event packet, got {len(data)} bytes")

    event_code = data[2]
    severity_code = data[3]
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
        "protocol_version": f"{data[0]}.{data[1]}",
        "event_code": event_code,
        "event_name": event_labels.get(event_code, f"unknown_{event_code}"),
        "severity": severity_labels.get(severity_code, "info"),
        "sequence": struct.unpack_from("<I", data, 4)[0],
        "detail_u32": struct.unpack_from("<I", data, 8)[0],
    }
