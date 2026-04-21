#include "protocol/PayloadBuilders.h"

#include <math.h>

namespace zss::protocol {

TelemetryPayloadV1 buildTelemetryPayload(const app::AppState& app_state) {
    const auto& measurements = app_state.latestMeasurements();
    TelemetryPayloadV1 payload{};
    payload.sequence = app_state.latestSequence();
    payload.status_flags = app_state.statusFlags();
    payload.zirconia_output_voltage_v = measurements.zirconia_output_voltage_v;
    payload.heater_rtd_resistance_ohm = measurements.heater_rtd_resistance_ohm;
    payload.telemetry_field_bits = kTelemetryFieldBits;
    payload.differential_pressure_selected_pa = measurements.differential_pressure_selected_pa;
    if (app_state.hasDifferentialPressureSelectedPa()) {
        payload.differential_pressure_selected_pa = app_state.latestDifferentialPressureSelectedPa();
        payload.telemetry_field_bits |= kTelemetryFieldDifferentialPressureSelectedMask;
    } else if (isfinite(measurements.differential_pressure_selected_pa)) {
        payload.telemetry_field_bits |= kTelemetryFieldDifferentialPressureSelectedMask;
    }
    if (app_state.hasDifferentialPressureRawPa()) {
        payload.differential_pressure_low_range_pa =
            app_state.latestDifferentialPressureLowRangePa();
        payload.differential_pressure_high_range_pa =
            app_state.latestDifferentialPressureHighRangePa();
        payload.telemetry_field_bits |=
            kTelemetryFieldDifferentialPressureLowRangeMask |
            kTelemetryFieldDifferentialPressureHighRangeMask;
    }
    payload.nominal_sample_period_ms = app_state.nominalSamplePeriodMs();
    payload.diagnostic_bits = app_state.diagnosticBits();
    return payload;
}

StatusSnapshotPayloadV1 buildStatusSnapshotPayload(const app::AppState& app_state, uint8_t response_code) {
    const auto& measurements = app_state.latestMeasurements();
    StatusSnapshotPayloadV1 payload{};
    payload.response_code = response_code;
    payload.sequence = app_state.latestSequence();
    payload.status_flags = app_state.statusFlags();
    payload.nominal_sample_period_ms = app_state.nominalSamplePeriodMs();
    payload.zirconia_output_voltage_v = measurements.zirconia_output_voltage_v;
    payload.heater_rtd_resistance_ohm = measurements.heater_rtd_resistance_ohm;
    payload.telemetry_field_bits = kTelemetryFieldBits;
    payload.differential_pressure_selected_pa = measurements.differential_pressure_selected_pa;
    if (app_state.hasDifferentialPressureSelectedPa()) {
        payload.differential_pressure_selected_pa = app_state.latestDifferentialPressureSelectedPa();
        payload.telemetry_field_bits |= kTelemetryFieldDifferentialPressureSelectedMask;
    } else if (isfinite(measurements.differential_pressure_selected_pa)) {
        payload.telemetry_field_bits |= kTelemetryFieldDifferentialPressureSelectedMask;
    }
    if (app_state.hasDifferentialPressureRawPa()) {
        payload.differential_pressure_low_range_pa =
            app_state.latestDifferentialPressureLowRangePa();
        payload.differential_pressure_high_range_pa =
            app_state.latestDifferentialPressureHighRangePa();
        payload.telemetry_field_bits |=
            kTelemetryFieldDifferentialPressureLowRangeMask |
            kTelemetryFieldDifferentialPressureHighRangeMask;
    }
    return payload;
}

CapabilitiesPayloadV1 buildCapabilitiesPayload(const app::DeviceCapabilities& capabilities) {
    CapabilitiesPayloadV1 payload{};
    payload.device_type_code = static_cast<uint8_t>(capabilities.device_type_code);
    payload.transport_type_code = static_cast<uint8_t>(capabilities.transport_type_code);
    payload.firmware_version_major = capabilities.firmware_version_major;
    payload.firmware_version_minor = capabilities.firmware_version_minor;
    payload.firmware_version_patch = capabilities.firmware_version_patch;
    payload.supported_command_bits = capabilities.supported_command_bits;
    payload.telemetry_field_bits = capabilities.telemetry_field_bits;
    payload.nominal_sample_period_ms = capabilities.nominal_sample_period_ms;
    payload.status_flag_schema_version = capabilities.status_flag_schema_version;
    payload.max_payload_bytes = capabilities.max_payload_bytes;
    payload.feature_bits = capabilities.feature_bits;
    return payload;
}

EventPayloadV1 buildEventPayload(EventCode event_code, uint8_t severity, uint32_t sequence, uint32_t detail_u32) {
    EventPayloadV1 payload{};
    payload.event_code = static_cast<uint8_t>(event_code);
    payload.severity = severity;
    payload.sequence = sequence;
    payload.detail_u32 = detail_u32;
    return payload;
}

CommandAckPayloadV1 buildCommandAckPayload(
    CommandId command_id,
    ResultCode result_code,
    uint32_t detail_u32) {
    CommandAckPayloadV1 payload{};
    payload.command_id = static_cast<uint8_t>(command_id);
    payload.result_code = static_cast<uint8_t>(result_code);
    payload.detail_u32 = detail_u32;
    return payload;
}

}  // namespace zss::protocol
