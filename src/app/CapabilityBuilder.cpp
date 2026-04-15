#include "app/CapabilityBuilder.h"

#include "board/BoardConfig.h"

namespace zss::app {

DeviceCapabilities CapabilityBuilder::build(
    transport::TransportKind transport_kind,
    uint16_t nominal_sample_period_ms) {
    DeviceCapabilities capabilities{};
    capabilities.nominal_sample_period_ms = nominal_sample_period_ms;

    if (transport_kind == transport::TransportKind::Serial) {
        capabilities.transport_type_code = protocol::TransportTypeCode::Serial;
        capabilities.max_payload_bytes = static_cast<uint16_t>(board::kSerialMaxPayloadBytes);
        capabilities.feature_bits = protocol::kSerialFeatureBits;
    } else {
        capabilities.transport_type_code = protocol::TransportTypeCode::Ble;
        capabilities.max_payload_bytes = static_cast<uint16_t>(protocol::kBleTelemetryPacketSize);
        capabilities.feature_bits = protocol::kBleFeatureBits;
    }

    return capabilities;
}

}  // namespace zss::app
