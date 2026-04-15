#pragma once

#include <stdint.h>

#include "protocol/ProtocolConstants.h"
#include "transport/TransportTypes.h"

namespace zss::app {

struct DeviceCapabilities {
    uint8_t protocol_version_major = protocol::kProtocolVersionMajor;
    uint8_t protocol_version_minor = protocol::kProtocolVersionMinor;
    protocol::DeviceTypeCode device_type_code = protocol::DeviceTypeCode::ZirconiaSensor;
    protocol::TransportTypeCode transport_type_code = protocol::TransportTypeCode::Ble;
    uint8_t firmware_version_major = 0;
    uint8_t firmware_version_minor = 1;
    uint8_t firmware_version_patch = 0;
    uint16_t supported_command_bits = protocol::kSupportedCommandBits;
    uint16_t telemetry_field_bits = protocol::kTelemetryFieldBits;
    uint16_t nominal_sample_period_ms = 0;
    uint16_t status_flag_schema_version = protocol::kStatusFlagSchemaVersion;
    uint16_t max_payload_bytes = 0;
    uint32_t feature_bits = 0;
};

class CapabilityBuilder {
  public:
    static DeviceCapabilities build(
        transport::TransportKind transport_kind,
        uint16_t nominal_sample_period_ms);
};

}  // namespace zss::app
