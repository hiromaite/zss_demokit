#include "app/CapabilityBuilder.h"

#include "board/BoardConfig.h"

namespace zss::app {

DeviceCapabilities CapabilityBuilder::build(
    transport::TransportKind transport_kind,
    uint16_t nominal_sample_period_ms,
    bool advertise_differential_pressure_selected,
    bool advertise_differential_pressure_low_range,
    bool advertise_differential_pressure_high_range,
    bool advertise_zirconia_ip_voltage,
    bool advertise_internal_voltage) {
    DeviceCapabilities capabilities{};
    capabilities.nominal_sample_period_ms = nominal_sample_period_ms;
    if (advertise_differential_pressure_selected) {
        capabilities.telemetry_field_bits |=
            protocol::kTelemetryFieldDifferentialPressureSelectedMask;
    }
    if (advertise_differential_pressure_low_range) {
        capabilities.telemetry_field_bits |=
            protocol::kTelemetryFieldDifferentialPressureLowRangeMask;
    }
    if (advertise_differential_pressure_high_range) {
        capabilities.telemetry_field_bits |=
            protocol::kTelemetryFieldDifferentialPressureHighRangeMask;
    }
    if (advertise_zirconia_ip_voltage) {
        capabilities.telemetry_field_bits |=
            protocol::kTelemetryFieldZirconiaIpVoltageMask;
    }
    if (advertise_internal_voltage) {
        capabilities.telemetry_field_bits |=
            protocol::kTelemetryFieldInternalVoltageMask;
    }

    if (transport_kind == transport::TransportKind::Serial) {
        capabilities.transport_type_code = protocol::TransportTypeCode::Serial;
        capabilities.max_payload_bytes = static_cast<uint16_t>(board::kSerialMaxPayloadBytes);
        capabilities.feature_bits = protocol::kSerialFeatureBits;
    } else {
        capabilities.transport_type_code = protocol::TransportTypeCode::Ble;
        capabilities.max_payload_bytes = static_cast<uint16_t>(protocol::kBleTelemetryBatchMaxPacketSize);
        capabilities.feature_bits = protocol::kBleFeatureBits;
        capabilities.telemetry_field_bits &=
            protocol::kBleV1SingleSampleTelemetryFieldBitsMask;
    }

    return capabilities;
}

}  // namespace zss::app
