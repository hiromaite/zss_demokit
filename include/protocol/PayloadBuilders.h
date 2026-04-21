#pragma once

#include <stdint.h>

#include "app/AppState.h"
#include "app/CapabilityBuilder.h"

namespace zss::protocol {

struct TelemetryPayloadV1 {
    uint8_t protocol_version_major = kProtocolVersionMajor;
    uint8_t protocol_version_minor = kProtocolVersionMinor;
    uint8_t telemetry_schema_version = 1;
    uint8_t header_flags = 0;
    uint32_t sequence = 0;
    uint32_t status_flags = 0;
    float zirconia_output_voltage_v = 0.0f;
    float heater_rtd_resistance_ohm = 0.0f;
    float differential_pressure_selected_pa = 0.0f;
    float differential_pressure_low_range_pa = 0.0f;
    float differential_pressure_high_range_pa = 0.0f;
    uint16_t nominal_sample_period_ms = 0;
    uint16_t telemetry_field_bits = kTelemetryFieldBits;
    uint32_t diagnostic_bits = 0;
};

struct StatusSnapshotPayloadV1 {
    uint8_t protocol_version_major = kProtocolVersionMajor;
    uint8_t protocol_version_minor = kProtocolVersionMinor;
    uint8_t status_snapshot_schema_version = 1;
    uint8_t response_code = 0;
    uint32_t sequence = 0;
    uint32_t status_flags = 0;
    uint16_t nominal_sample_period_ms = 0;
    uint16_t telemetry_field_bits = kTelemetryFieldBits;
    float zirconia_output_voltage_v = 0.0f;
    float heater_rtd_resistance_ohm = 0.0f;
    float differential_pressure_selected_pa = 0.0f;
    float differential_pressure_low_range_pa = 0.0f;
    float differential_pressure_high_range_pa = 0.0f;
};

struct CapabilitiesPayloadV1 {
    uint8_t protocol_version_major = kProtocolVersionMajor;
    uint8_t protocol_version_minor = kProtocolVersionMinor;
    uint8_t capability_schema_version = kCapabilitySchemaVersion;
    uint8_t device_type_code = static_cast<uint8_t>(DeviceTypeCode::ZirconiaSensor);
    uint8_t transport_type_code = static_cast<uint8_t>(TransportTypeCode::Ble);
    uint8_t firmware_version_major = 0;
    uint8_t firmware_version_minor = 1;
    uint8_t firmware_version_patch = 0;
    uint16_t supported_command_bits = kSupportedCommandBits;
    uint16_t telemetry_field_bits = kTelemetryFieldBits;
    uint16_t nominal_sample_period_ms = 0;
    uint16_t status_flag_schema_version = kStatusFlagSchemaVersion;
    uint16_t max_payload_bytes = 0;
    uint32_t feature_bits = 0;
};

struct EventPayloadV1 {
    uint8_t protocol_version_major = kProtocolVersionMajor;
    uint8_t protocol_version_minor = kProtocolVersionMinor;
    uint8_t event_code = 0;
    uint8_t severity = 0;
    uint32_t sequence = 0;
    uint32_t detail_u32 = 0;
};

struct CommandAckPayloadV1 {
    uint8_t command_id = 0;
    uint8_t result_code = 0;
    uint16_t reserved = 0;
    uint32_t detail_u32 = 0;
};

TelemetryPayloadV1 buildTelemetryPayload(const app::AppState& app_state);
StatusSnapshotPayloadV1 buildStatusSnapshotPayload(const app::AppState& app_state, uint8_t response_code = 0);
CapabilitiesPayloadV1 buildCapabilitiesPayload(const app::DeviceCapabilities& capabilities);
EventPayloadV1 buildEventPayload(EventCode event_code, uint8_t severity, uint32_t sequence, uint32_t detail_u32);
CommandAckPayloadV1 buildCommandAckPayload(
    CommandId command_id,
    ResultCode result_code,
    uint32_t detail_u32);

}  // namespace zss::protocol
