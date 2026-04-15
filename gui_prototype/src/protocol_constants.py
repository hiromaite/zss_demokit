from __future__ import annotations

BLE_MODE = "BLE"
WIRED_MODE = "Wired"

TRANSPORT_BLE = "ble"
TRANSPORT_SERIAL = "serial"
DEVICE_TYPE_ZIRCONIA_SENSOR = "zirconia_sensor"

PROTOCOL_VERSION_MAJOR = 1
PROTOCOL_VERSION_MINOR = 0
PROTOCOL_VERSION_TEXT = f"{PROTOCOL_VERSION_MAJOR}.{PROTOCOL_VERSION_MINOR}"
STATUS_FLAG_SCHEMA_VERSION = 1

WIRED_DEFAULT_BAUDRATE = 115200
WIRED_DEFAULT_LINE_SETTINGS = "8N1"

BLE_NOMINAL_SAMPLE_PERIOD_MS = 80
WIRED_NOMINAL_SAMPLE_PERIOD_MS = 10

FIRMWARE_VERSION_PLACEHOLDER = "prototype-ui"
DERIVED_METRIC_POLICY_ID = "dummy_linear_v1"

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

SUPPORTED_COMMANDS = (
    "get_capabilities",
    "get_status",
    "set_pump_state",
    "ping",
)
TELEMETRY_FIELDS = (
    "zirconia_output_voltage_v",
    "heater_rtd_resistance_ohm",
    "flow_sensor_voltage_v",
)

SUPPORTED_COMMAND_BITS = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3)
TELEMETRY_FIELD_BITS = (1 << 0) | (1 << 1) | (1 << 2)

BLE_OPCODE_SET_PUMP_ON = 0x55
BLE_OPCODE_SET_PUMP_OFF = 0xAA
BLE_OPCODE_GET_STATUS = 0x30
BLE_OPCODE_GET_CAPABILITIES = 0x31
BLE_OPCODE_PING = 0x32

WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE = 0x01
WIRED_MESSAGE_TYPE_STATUS_SNAPSHOT = 0x02
WIRED_MESSAGE_TYPE_CAPABILITIES = 0x03
WIRED_MESSAGE_TYPE_COMMAND_REQUEST = 0x10
WIRED_MESSAGE_TYPE_COMMAND_ACK = 0x11
WIRED_MESSAGE_TYPE_EVENT = 0x12
WIRED_MESSAGE_TYPE_ERROR = 0x13
WIRED_MESSAGE_TYPE_PING = 0x14
WIRED_MESSAGE_TYPE_PONG = 0x15
WIRED_COMMAND_ID_GET_CAPABILITIES = 0x01
WIRED_COMMAND_ID_GET_STATUS = 0x02
WIRED_COMMAND_ID_SET_PUMP_STATE = 0x03
WIRED_COMMAND_ID_PING = 0x04
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

FLOW_RATE_DUMMY_GAIN = 1.0
FLOW_RATE_DUMMY_OFFSET = 0.0


def nominal_sample_period_ms_for_mode(mode: str) -> int:
    return BLE_NOMINAL_SAMPLE_PERIOD_MS if mode == BLE_MODE else WIRED_NOMINAL_SAMPLE_PERIOD_MS


def transport_type_for_mode(mode: str) -> str:
    return TRANSPORT_BLE if mode == BLE_MODE else TRANSPORT_SERIAL


def build_status_flags(
    *,
    pump_on: bool,
    transport_session_active: bool,
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


def derive_flow_rate_lpm(flow_sensor_voltage_v: float) -> float:
    return max(0.0, FLOW_RATE_DUMMY_GAIN * flow_sensor_voltage_v + FLOW_RATE_DUMMY_OFFSET)


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
