#include <stdint.h>

#include <cstring>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>

#include "app/AppState.h"
#include "app/CapabilityBuilder.h"
#include "measurement/SensorData.h"
#include "protocol/PayloadBuilders.h"
#include "transport/TransportTypes.h"

namespace {

using zss::app::AppState;
using zss::app::CapabilityBuilder;
using zss::app::DeviceCapabilities;
using zss::measurement::SensorMeasurements;
using zss::protocol::CapabilitiesPayloadV1;
using zss::protocol::CommandAckPayloadV1;
using zss::protocol::EventPayloadV1;
using zss::protocol::StatusSnapshotPayloadV1;
using zss::protocol::TelemetryPayloadV1;

static_assert(sizeof(CapabilitiesPayloadV1) == zss::protocol::kBleCapabilitiesPacketSize);
static_assert(sizeof(EventPayloadV1) == zss::protocol::kBleEventPacketSize);
static_assert(sizeof(CommandAckPayloadV1) == zss::protocol::kWiredCommandAckPayloadSize);

void writeU16Le(std::vector<uint8_t>& out, size_t offset, uint16_t value) {
    out[offset + 0] = static_cast<uint8_t>(value & 0xFFu);
    out[offset + 1] = static_cast<uint8_t>((value >> 8) & 0xFFu);
}

void writeU32Le(std::vector<uint8_t>& out, size_t offset, uint32_t value) {
    out[offset + 0] = static_cast<uint8_t>(value & 0xFFu);
    out[offset + 1] = static_cast<uint8_t>((value >> 8) & 0xFFu);
    out[offset + 2] = static_cast<uint8_t>((value >> 16) & 0xFFu);
    out[offset + 3] = static_cast<uint8_t>((value >> 24) & 0xFFu);
}

void writeFloat32Le(std::vector<uint8_t>& out, size_t offset, float value) {
    uint32_t raw = 0;
    std::memcpy(&raw, &value, sizeof(raw));
    writeU32Le(out, offset, raw);
}

uint16_t computeCrcCcittFalse(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFFu;
    for (size_t index = 0; index < length; ++index) {
        crc ^= static_cast<uint16_t>(data[index]) << 8;
        for (uint8_t bit = 0; bit < 8; ++bit) {
            if ((crc & 0x8000u) != 0u) {
                crc = static_cast<uint16_t>((crc << 1) ^ 0x1021u);
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

SensorMeasurements makeMeasurements(float zirconia, float heater, float selected_differential_pressure_pa) {
    SensorMeasurements measurements{};
    measurements.zirconia_output_voltage_v = zirconia;
    measurements.heater_rtd_resistance_ohm = heater;
    measurements.differential_pressure_selected_pa = selected_differential_pressure_pa;
    return measurements;
}

AppState makeState(
    uint16_t nominal_sample_period_ms,
    uint32_t sequence,
    const SensorMeasurements& measurements,
    bool transport_session_active,
    bool pump_on) {
    AppState state(nominal_sample_period_ms);
    state.setTransportSessionActive(transport_session_active);
    state.setPumpOn(pump_on);
    state.updateMeasurements(sequence, measurements);
    return state;
}

std::vector<uint8_t> encodeWiredTelemetryPayload(const TelemetryPayloadV1& payload) {
    const bool has_raw_channels =
        (payload.telemetry_field_bits &
         (zss::protocol::kTelemetryFieldDifferentialPressureLowRangeMask |
          zss::protocol::kTelemetryFieldDifferentialPressureHighRangeMask)) != 0u;
    const size_t payload_size =
        has_raw_channels
            ? zss::protocol::kWiredTelemetryPayloadExtendedSize
            : zss::protocol::kWiredTelemetryPayloadSize;
    std::vector<uint8_t> out(payload_size, 0);
    writeU32Le(out, 0, payload.status_flags);
    writeU16Le(out, 4, payload.nominal_sample_period_ms);
    writeU16Le(out, 6, payload.telemetry_field_bits);
    writeFloat32Le(out, 8, payload.zirconia_output_voltage_v);
    writeFloat32Le(out, 12, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(out, 16, payload.differential_pressure_selected_pa);
    if (has_raw_channels) {
        writeFloat32Le(out, 20, payload.differential_pressure_low_range_pa);
        writeFloat32Le(out, 24, payload.differential_pressure_high_range_pa);
    }
    return out;
}

std::vector<uint8_t> encodeWiredStatusPayload(const StatusSnapshotPayloadV1& payload) {
    const bool has_raw_channels =
        (payload.telemetry_field_bits &
         (zss::protocol::kTelemetryFieldDifferentialPressureLowRangeMask |
          zss::protocol::kTelemetryFieldDifferentialPressureHighRangeMask)) != 0u;
    const size_t payload_size =
        has_raw_channels
            ? zss::protocol::kWiredStatusSnapshotPayloadExtendedSize
            : zss::protocol::kWiredStatusSnapshotPayloadSize;
    std::vector<uint8_t> out(payload_size, 0);
    writeU32Le(out, 0, payload.status_flags);
    writeU16Le(out, 4, payload.nominal_sample_period_ms);
    writeU16Le(out, 6, payload.telemetry_field_bits);
    writeFloat32Le(out, 8, payload.zirconia_output_voltage_v);
    writeFloat32Le(out, 12, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(out, 16, payload.differential_pressure_selected_pa);
    if (has_raw_channels) {
        writeFloat32Le(out, 20, payload.differential_pressure_low_range_pa);
        writeFloat32Le(out, 24, payload.differential_pressure_high_range_pa);
    }
    return out;
}

std::vector<uint8_t> encodeBleTelemetryPayload(const TelemetryPayloadV1& payload) {
    std::vector<uint8_t> out(zss::protocol::kBleTelemetryPacketSize, 0);
    out[0] = payload.protocol_version_major;
    out[1] = payload.protocol_version_minor;
    out[2] = payload.telemetry_schema_version;
    out[3] = payload.header_flags;
    writeU32Le(out, 4, payload.sequence);
    writeU32Le(out, 8, payload.status_flags);
    writeFloat32Le(out, 12, payload.zirconia_output_voltage_v);
    writeFloat32Le(out, 16, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(out, 20, payload.differential_pressure_selected_pa);
    writeU16Le(out, 24, payload.nominal_sample_period_ms);
    writeU16Le(out, 26, payload.telemetry_field_bits);
    writeU32Le(out, 28, payload.diagnostic_bits);
    return out;
}

std::vector<uint8_t> encodeBleStatusPayload(const StatusSnapshotPayloadV1& payload) {
    std::vector<uint8_t> out(zss::protocol::kBleStatusSnapshotPacketSize, 0);
    out[0] = payload.protocol_version_major;
    out[1] = payload.protocol_version_minor;
    out[2] = payload.status_snapshot_schema_version;
    out[3] = payload.response_code;
    writeU32Le(out, 4, payload.sequence);
    writeU32Le(out, 8, payload.status_flags);
    writeU16Le(out, 12, payload.nominal_sample_period_ms);
    writeU16Le(out, 14, payload.telemetry_field_bits);
    writeFloat32Le(out, 16, payload.zirconia_output_voltage_v);
    writeFloat32Le(out, 20, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(out, 24, payload.differential_pressure_selected_pa);
    return out;
}

std::vector<uint8_t> encodeWiredCapabilitiesPayload(const CapabilitiesPayloadV1& payload) {
    std::vector<uint8_t> out(zss::protocol::kWiredCapabilitiesPayloadSize, 0);
    out[0] = payload.capability_schema_version;
    out[1] = payload.device_type_code;
    out[2] = payload.transport_type_code;
    out[3] = payload.firmware_version_major;
    out[4] = payload.firmware_version_minor;
    out[5] = payload.firmware_version_patch;
    writeU16Le(out, 6, payload.supported_command_bits);
    writeU16Le(out, 8, payload.telemetry_field_bits);
    writeU16Le(out, 10, payload.nominal_sample_period_ms);
    writeU16Le(out, 12, payload.status_flag_schema_version);
    writeU16Le(out, 14, payload.max_payload_bytes);
    writeU32Le(out, 16, payload.feature_bits);
    return out;
}

std::vector<uint8_t> encodeWiredEventPayload(const EventPayloadV1& payload) {
    std::vector<uint8_t> out(zss::protocol::kWiredEventPayloadSize, 0);
    out[0] = payload.event_code;
    out[1] = payload.severity;
    writeU16Le(out, 2, 0u);
    writeU32Le(out, 4, payload.detail_u32);
    return out;
}

std::vector<uint8_t> encodeWiredCommandAckPayload(const CommandAckPayloadV1& payload) {
    std::vector<uint8_t> out(zss::protocol::kWiredCommandAckPayloadSize, 0);
    out[0] = payload.command_id;
    out[1] = payload.result_code;
    writeU16Le(out, 2, payload.reserved);
    writeU32Le(out, 4, payload.detail_u32);
    return out;
}

std::vector<uint8_t> buildWiredFrame(
    zss::protocol::WiredMessageType message_type,
    uint32_t sequence,
    uint32_t request_id,
    const std::vector<uint8_t>& payload) {
    std::vector<uint8_t> frame(zss::protocol::kWiredHeaderSize + payload.size() + 2, 0);
    frame[0] = zss::protocol::kWiredSof0;
    frame[1] = zss::protocol::kWiredSof1;
    frame[2] = zss::protocol::kProtocolVersionMajor;
    frame[3] = zss::protocol::kProtocolVersionMinor;
    frame[4] = static_cast<uint8_t>(message_type);
    frame[5] = 0;
    writeU16Le(frame, 6, static_cast<uint16_t>(payload.size()));
    writeU32Le(frame, 8, sequence);
    writeU32Le(frame, 12, request_id);
    if (!payload.empty()) {
        std::memcpy(frame.data() + zss::protocol::kWiredHeaderSize, payload.data(), payload.size());
    }
    const uint16_t crc = computeCrcCcittFalse(frame.data() + 2, 14 + payload.size());
    writeU16Le(frame, zss::protocol::kWiredHeaderSize + payload.size(), crc);
    return frame;
}

std::string toHex(const std::vector<uint8_t>& bytes) {
    std::ostringstream stream;
    stream << std::hex << std::setfill('0');
    for (uint8_t byte : bytes) {
        stream << std::setw(2) << static_cast<int>(byte);
    }
    return stream.str();
}

std::vector<uint8_t> buildFixture(const std::string& case_id) {
    using zss::protocol::CommandId;
    using zss::protocol::EventCode;
    using zss::protocol::ResultCode;
    using zss::protocol::WiredMessageType;

    if (case_id == "ble_telemetry_nominal") {
        auto state = makeState(80, 4660, makeMeasurements(0.625f, 120.5f, 1.25f), true, true);
        return encodeBleTelemetryPayload(zss::protocol::buildTelemetryPayload(state));
    }

    if (case_id == "ble_status_fault") {
        auto state = makeState(80, 4661, makeMeasurements(0.145f, 98.75f, 0.42f), true, false);
        state.setStatusFlag(zss::protocol::kStatusFlagAdcFaultMask, true);
        state.setStatusFlag(zss::protocol::kStatusFlagSensorFaultMask, true);
        return encodeBleStatusPayload(zss::protocol::buildStatusSnapshotPayload(state));
    }

    if (case_id == "ble_capabilities_ble") {
        DeviceCapabilities capabilities = CapabilityBuilder::build(zss::transport::TransportKind::Ble, 80);
        const auto payload = zss::protocol::buildCapabilitiesPayload(capabilities);
        std::vector<uint8_t> out(sizeof(payload), 0);
        std::memcpy(out.data(), &payload, sizeof(payload));
        return out;
    }

    if (case_id == "ble_event_command_error") {
        const auto payload =
            zss::protocol::buildEventPayload(EventCode::CommandError, 2, 4662, 0x99u);
        std::vector<uint8_t> out(sizeof(payload), 0);
        std::memcpy(out.data(), &payload, sizeof(payload));
        return out;
    }

    if (case_id == "wired_telemetry_serial_nominal") {
        auto state = makeState(10, 8738, makeMeasurements(0.7125f, 119.25f, 1.5f), true, true);
        const auto payload = zss::protocol::buildTelemetryPayload(state);
        return buildWiredFrame(
            WiredMessageType::TelemetrySample,
            payload.sequence,
            0u,
            encodeWiredTelemetryPayload(payload));
    }

    if (case_id == "wired_status_serial_fault") {
        auto state = makeState(10, 8739, makeMeasurements(0.1825f, 97.25f, 0.33f), true, false);
        state.setStatusFlag(zss::protocol::kStatusFlagAdcFaultMask, true);
        state.setStatusFlag(zss::protocol::kStatusFlagSensorFaultMask, true);
        state.setStatusFlag(zss::protocol::kStatusFlagCommandErrorLatchedMask, true);
        const auto payload = zss::protocol::buildStatusSnapshotPayload(state);
        return buildWiredFrame(
            WiredMessageType::StatusSnapshot,
            payload.sequence,
            7u,
            encodeWiredStatusPayload(payload));
    }

    if (case_id == "wired_capabilities_serial") {
        DeviceCapabilities capabilities = CapabilityBuilder::build(zss::transport::TransportKind::Serial, 10);
        const auto payload = zss::protocol::buildCapabilitiesPayload(capabilities);
        return buildWiredFrame(
            WiredMessageType::Capabilities,
            0u,
            8u,
            encodeWiredCapabilitiesPayload(payload));
    }

    if (case_id == "wired_event_command_error") {
        const auto payload = zss::protocol::buildEventPayload(EventCode::CommandError, 2, 8740, 0x99u);
        return buildWiredFrame(
            WiredMessageType::Event,
            payload.sequence,
            9u,
            encodeWiredEventPayload(payload));
    }

    if (case_id == "wired_ack_set_pump_ok") {
        const auto payload = zss::protocol::buildCommandAckPayload(CommandId::SetPumpState, ResultCode::Ok, 1u);
        return buildWiredFrame(
            WiredMessageType::CommandAck,
            0u,
            10u,
            encodeWiredCommandAckPayload(payload));
    }

    throw std::runtime_error("unknown fixture case: " + case_id);
}

}  // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: firmware_fixture_verify <case-id>\n";
        return 2;
    }

    try {
        std::cout << toHex(buildFixture(argv[1])) << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }

    return 0;
}
