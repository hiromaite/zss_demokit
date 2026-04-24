from __future__ import annotations

import math

BLE_MODE = "BLE"
WIRED_MODE = "Wired"

TRANSPORT_BLE = "ble"
TRANSPORT_SERIAL = "serial"
DEVICE_TYPE_ZIRCONIA_SENSOR = "zirconia_sensor"

PROTOCOL_VERSION_MAJOR = 1
PROTOCOL_VERSION_MINOR = 0
PROTOCOL_VERSION_TEXT = f"{PROTOCOL_VERSION_MAJOR}.{PROTOCOL_VERSION_MINOR}"
STATUS_FLAG_SCHEMA_VERSION = 2

WIRED_DEFAULT_BAUDRATE = 115200
WIRED_DEFAULT_LINE_SETTINGS = "8N1"

BLE_NOMINAL_SAMPLE_PERIOD_MS = 80
WIRED_NOMINAL_SAMPLE_PERIOD_MS = 10

FIRMWARE_VERSION_PLACEHOLDER = "prototype-ui"
DERIVED_METRIC_POLICY_ID = "dummy_selected_dp_orifice_v1"

DEVICE_TYPE_CODE_ZIRCONIA_SENSOR = 1
TRANSPORT_TYPE_CODE_BLE = 1
TRANSPORT_TYPE_CODE_SERIAL = 2

STATUS_FLAG_PUMP_ON = 1 << 0
STATUS_FLAG_TRANSPORT_SESSION_ACTIVE = 1 << 1
STATUS_FLAG_ADC_FAULT = 1 << 2
STATUS_FLAG_SAMPLING_OVERRUN = 1 << 3
STATUS_FLAG_SENSOR_FAULT = 1 << 4
STATUS_FLAG_TELEMETRY_RATE_WARNING = 1 << 5
STATUS_FLAG_COMMAND_ERROR_LATCHED = 1 << 6
STATUS_FLAG_HEATER_POWER_ON = 1 << 7

DIAGNOSTIC_BIT_BOOT_COMPLETE = 1 << 0
DIAGNOSTIC_BIT_MEASUREMENT_CORE_READY = 1 << 1
DIAGNOSTIC_BIT_EXTERNAL_ADC_READY = 1 << 2
DIAGNOSTIC_BIT_BLE_TRANSPORT_READY = 1 << 3
DIAGNOSTIC_BIT_SERIAL_TRANSPORT_READY = 1 << 4
DIAGNOSTIC_BIT_BLE_SESSION_OBSERVED = 1 << 5
DIAGNOSTIC_BIT_SERIAL_SESSION_OBSERVED = 1 << 6
DIAGNOSTIC_BIT_TELEMETRY_PUBLISHED = 1 << 7

SUPPORTED_COMMANDS = (
    "get_capabilities",
    "get_status",
    "set_pump_state",
    "ping",
    "set_heater_power_state",
)
TELEMETRY_FIELDS = (
    "zirconia_output_voltage_v",
    "heater_rtd_resistance_ohm",
    "differential_pressure_selected_pa",
    "differential_pressure_low_range_pa",
    "differential_pressure_high_range_pa",
    "zirconia_ip_voltage_v",
    "internal_voltage_v",
)

SUPPORTED_COMMAND_BITS = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)
TELEMETRY_FIELD_BITS = (1 << 0) | (1 << 1)
TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED = 1 << 3
TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_LOW_RANGE = 1 << 4
TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_HIGH_RANGE = 1 << 5
TELEMETRY_FIELD_ZIRCONIA_IP_VOLTAGE = 1 << 6
TELEMETRY_FIELD_INTERNAL_VOLTAGE = 1 << 7

BLE_OPCODE_SET_PUMP_ON = 0x55
BLE_OPCODE_SET_PUMP_OFF = 0xAA
BLE_OPCODE_GET_STATUS = 0x30
BLE_OPCODE_GET_CAPABILITIES = 0x31
BLE_OPCODE_PING = 0x32
BLE_OPCODE_SET_HEATER_ON = 0x33
BLE_OPCODE_SET_HEATER_OFF = 0x34

WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE = 0x01
WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT = 0x02
WIRED_MESSAGE_TYPE_CAPABILITIES = 0x03
WIRED_MESSAGE_TYPE_COMMAND_REQUEST = 0x10
WIRED_MESSAGE_TYPE_COMMAND_ACK = 0x11
WIRED_MESSAGE_TYPE_EVENT = 0x12
WIRED_MESSAGE_TYPE_ERROR = 0x13
WIRED_MESSAGE_TYPE_PING = 0x14
WIRED_MESSAGE_TYPE_PONG = 0x15
WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC = 0x16
WIRED_COMMAND_ID_GET_CAPABILITIES = 0x01
WIRED_COMMAND_ID_GET_STATUS = 0x02
WIRED_COMMAND_ID_SET_PUMP_STATE = 0x03
WIRED_COMMAND_ID_PING = 0x04
WIRED_COMMAND_ID_SET_HEATER_POWER_STATE = 0x05
WIRED_SOF0 = 0xA5
WIRED_SOF1 = 0x5A
WIRED_HEADER_SIZE = 16
WIRED_MAX_PAYLOAD_BYTES = 64

RESULT_CODE_OK = 0
RESULT_CODE_UNSUPPORTED_COMMAND = 1
RESULT_CODE_INVALID_ARGUMENT = 2
RESULT_CODE_INVALID_STATE = 3
RESULT_CODE_BUSY = 4
RESULT_CODE_INTERNAL_ERROR = 5

EVENT_CODE_BOOT_COMPLETE = 0x01
EVENT_CODE_WARNING_RAISED = 0x02
EVENT_CODE_WARNING_CLEARED = 0x03
EVENT_CODE_COMMAND_ERROR = 0x04
EVENT_CODE_ADC_FAULT_RAISED = 0x05
EVENT_CODE_ADC_FAULT_CLEARED = 0x06

ORIFICE_FLOW_DUMMY_GAIN_LPM_PER_SQRT_PA = 1.0
ORIFICE_FLOW_DUMMY_OFFSET_LPM = 0.0
O2_ZERO_REFERENCE_V = 2.5
O2_AMBIENT_REFERENCE_PERCENT = 21.0


def nominal_sample_period_ms_for_mode(mode: str) -> int:
    return BLE_NOMINAL_SAMPLE_PERIOD_MS if mode == BLE_MODE else WIRED_NOMINAL_SAMPLE_PERIOD_MS


def transport_type_for_mode(mode: str) -> str:
    return TRANSPORT_BLE if mode == BLE_MODE else TRANSPORT_SERIAL


def build_status_flags(
    *,
    pump_on: bool,
    transport_session_active: bool,
    heater_power_on: bool = False,
    adc_fault: bool = False,
    sampling_overrun: bool = False,
    sensor_fault: bool = False,
    telemetry_rate_warning: bool = False,
    command_error_latched: bool = False,
) -> int:
    status_flags = 0
    if pump_on:
        status_flags |= STATUS_FLAG_PUMP_ON
    if transport_session_active:
        status_flags |= STATUS_FLAG_TRANSPORT_SESSION_ACTIVE
    if heater_power_on:
        status_flags |= STATUS_FLAG_HEATER_POWER_ON
    if adc_fault:
        status_flags |= STATUS_FLAG_ADC_FAULT
    if sampling_overrun:
        status_flags |= STATUS_FLAG_SAMPLING_OVERRUN
    if sensor_fault:
        status_flags |= STATUS_FLAG_SENSOR_FAULT
    if telemetry_rate_warning:
        status_flags |= STATUS_FLAG_TELEMETRY_RATE_WARNING
    if command_error_latched:
        status_flags |= STATUS_FLAG_COMMAND_ERROR_LATCHED
    return status_flags


def format_status_flags(status_flags: int) -> str:
    return f"0x{status_flags:08X}"


def derive_flow_rate_lpm_from_differential_pressure_pa(
    differential_pressure_selected_pa: float | None,
) -> float:
    if differential_pressure_selected_pa is None or not math.isfinite(differential_pressure_selected_pa):
        return 0.0

    magnitude_lpm = (
        ORIFICE_FLOW_DUMMY_GAIN_LPM_PER_SQRT_PA * math.sqrt(abs(differential_pressure_selected_pa))
        + ORIFICE_FLOW_DUMMY_OFFSET_LPM
    )
    if differential_pressure_selected_pa < 0.0:
        return -magnitude_lpm
    return magnitude_lpm


def derive_flow_rate_lpm_from_selected_differential_pressure_pa(
    differential_pressure_selected_pa: float | None,
) -> float:
    return derive_flow_rate_lpm_from_differential_pressure_pa(differential_pressure_selected_pa)


def infer_differential_pressure_selected_source(
    differential_pressure_selected_pa: float | None,
    differential_pressure_low_range_pa: float | None,
    differential_pressure_high_range_pa: float | None,
    *,
    tolerance_pa: float = 1e-4,
) -> str:
    if (
        differential_pressure_selected_pa is None
        or not math.isfinite(differential_pressure_selected_pa)
    ):
        return ""

    matches_low = (
        differential_pressure_low_range_pa is not None
        and math.isfinite(differential_pressure_low_range_pa)
        and abs(differential_pressure_selected_pa - differential_pressure_low_range_pa) <= tolerance_pa
    )
    matches_high = (
        differential_pressure_high_range_pa is not None
        and math.isfinite(differential_pressure_high_range_pa)
        and abs(differential_pressure_selected_pa - differential_pressure_high_range_pa) <= tolerance_pa
    )

    if matches_low and not matches_high:
        return "SDP810"
    if matches_high and not matches_low:
        return "SDP811"
    if matches_low and matches_high:
        return "BOTH"
    return ""


def derive_o2_concentration_percent(
    zirconia_output_voltage_v: float,
    *,
    air_calibration_voltage_v: float | None,
    zero_reference_voltage_v: float = O2_ZERO_REFERENCE_V,
    ambient_reference_percent: float = O2_AMBIENT_REFERENCE_PERCENT,
    invert_polarity: bool = False,
) -> float | None:
    if air_calibration_voltage_v is None:
        return None
    if not math.isfinite(zirconia_output_voltage_v) or not math.isfinite(air_calibration_voltage_v):
        return None

    denominator = zero_reference_voltage_v - air_calibration_voltage_v
    if abs(denominator) < 1e-9:
        return None

    normalized = (zero_reference_voltage_v - zirconia_output_voltage_v) / denominator
    if invert_polarity:
        normalized *= -1.0
    return max(0.0, min(100.0, normalized * ambient_reference_percent))


def result_code_to_text(result_code: int) -> str:
    labels = {
        RESULT_CODE_OK: "ok",
        RESULT_CODE_UNSUPPORTED_COMMAND: "unsupported_command",
        RESULT_CODE_INVALID_ARGUMENT: "invalid_argument",
        RESULT_CODE_INVALID_STATE: "invalid_state",
        RESULT_CODE_BUSY: "busy",
        RESULT_CODE_INTERNAL_ERROR: "internal_error",
    }
    return labels.get(result_code, f"unknown_{result_code}")
