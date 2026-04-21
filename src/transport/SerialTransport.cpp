#include "transport/SerialTransport.h"

#include <Arduino.h>

#include <string.h>

#include "services/Logger.h"

namespace zss::transport {

namespace {

uint16_t readU16Le(const uint8_t* data) {
    return static_cast<uint16_t>(data[0]) |
           (static_cast<uint16_t>(data[1]) << 8);
}

uint32_t readU32Le(const uint8_t* data) {
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
}

void writeU16Le(uint8_t* out, uint16_t value) {
    out[0] = static_cast<uint8_t>(value & 0xFFu);
    out[1] = static_cast<uint8_t>((value >> 8) & 0xFFu);
}

void writeU32Le(uint8_t* out, uint32_t value) {
    out[0] = static_cast<uint8_t>(value & 0xFFu);
    out[1] = static_cast<uint8_t>((value >> 8) & 0xFFu);
    out[2] = static_cast<uint8_t>((value >> 16) & 0xFFu);
    out[3] = static_cast<uint8_t>((value >> 24) & 0xFFu);
}

void writeFloat32Le(uint8_t* out, float value) {
    uint32_t raw = 0;
    memcpy(&raw, &value, sizeof(raw));
    writeU32Le(out, raw);
}

}  // namespace

bool SerialTransport::begin() {
    return true;
}

void SerialTransport::update() {
    while (Serial.available() > 0) {
        const int next_byte = Serial.read();
        if (next_byte < 0) {
            break;
        }
        appendReceivedByte(static_cast<uint8_t>(next_byte));
    }

    consumeRxBuffer();
}

bool SerialTransport::isConnected() const {
    return session_active_;
}

bool SerialTransport::takePendingCommand(app::CommandRequest& request, uint32_t& request_id) {
    if (!has_pending_command_) {
        return false;
    }
    request = pending_command_;
    request_id = pending_request_id_;
    has_pending_command_ = false;
    pending_request_id_ = 0;
    return true;
}

void SerialTransport::publishTelemetry(const protocol::TelemetryPayloadV1& payload) {
    if (!session_active_) {
        return;
    }

    const bool has_raw_channels =
        (payload.telemetry_field_bits &
         (protocol::kTelemetryFieldDifferentialPressureLowRangeMask |
          protocol::kTelemetryFieldDifferentialPressureHighRangeMask)) != 0u;
    const size_t payload_size =
        has_raw_channels
            ? protocol::kWiredTelemetryPayloadExtendedSize
            : protocol::kWiredTelemetryPayloadSize;
    uint8_t encoded_payload[protocol::kWiredTelemetryPayloadExtendedSize]{};
    writeU32Le(encoded_payload + 0, payload.status_flags);
    writeU16Le(encoded_payload + 4, payload.nominal_sample_period_ms);
    writeU16Le(encoded_payload + 6, payload.telemetry_field_bits);
    writeFloat32Le(encoded_payload + 8, payload.zirconia_output_voltage_v);
    writeFloat32Le(encoded_payload + 12, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(encoded_payload + 16, payload.differential_pressure_selected_pa);
    if (has_raw_channels) {
        writeFloat32Le(encoded_payload + 20, payload.differential_pressure_low_range_pa);
        writeFloat32Le(encoded_payload + 24, payload.differential_pressure_high_range_pa);
    }

    writeFrame(
        protocol::WiredMessageType::TelemetrySample,
        payload.sequence,
        0,
        encoded_payload,
        payload_size);
    published_telemetry_count_ += 1u;
}

void SerialTransport::publishStatusSnapshot(const protocol::StatusSnapshotPayloadV1& payload, uint32_t request_id) {
    if (!session_active_) {
        return;
    }

    const bool has_raw_channels =
        (payload.telemetry_field_bits &
         (protocol::kTelemetryFieldDifferentialPressureLowRangeMask |
          protocol::kTelemetryFieldDifferentialPressureHighRangeMask)) != 0u;
    const size_t payload_size =
        has_raw_channels
            ? protocol::kWiredStatusSnapshotPayloadExtendedSize
            : protocol::kWiredStatusSnapshotPayloadSize;
    uint8_t encoded_payload[protocol::kWiredStatusSnapshotPayloadExtendedSize]{};
    writeU32Le(encoded_payload + 0, payload.status_flags);
    writeU16Le(encoded_payload + 4, payload.nominal_sample_period_ms);
    writeU16Le(encoded_payload + 6, payload.telemetry_field_bits);
    writeFloat32Le(encoded_payload + 8, payload.zirconia_output_voltage_v);
    writeFloat32Le(encoded_payload + 12, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(encoded_payload + 16, payload.differential_pressure_selected_pa);
    if (has_raw_channels) {
        writeFloat32Le(encoded_payload + 20, payload.differential_pressure_low_range_pa);
        writeFloat32Le(encoded_payload + 24, payload.differential_pressure_high_range_pa);
    }

    writeFrame(
        protocol::WiredMessageType::StatusSnapshot,
        payload.sequence,
        request_id,
        encoded_payload,
        payload_size);
}

void SerialTransport::publishCapabilities(const protocol::CapabilitiesPayloadV1& payload, uint32_t request_id) {
    if (!session_active_) {
        return;
    }

    uint8_t encoded_payload[protocol::kWiredCapabilitiesPayloadSize]{};
    encoded_payload[0] = payload.capability_schema_version;
    encoded_payload[1] = payload.device_type_code;
    encoded_payload[2] = payload.transport_type_code;
    encoded_payload[3] = payload.firmware_version_major;
    encoded_payload[4] = payload.firmware_version_minor;
    encoded_payload[5] = payload.firmware_version_patch;
    writeU16Le(encoded_payload + 6, payload.supported_command_bits);
    writeU16Le(encoded_payload + 8, payload.telemetry_field_bits);
    writeU16Le(encoded_payload + 10, payload.nominal_sample_period_ms);
    writeU16Le(encoded_payload + 12, payload.status_flag_schema_version);
    writeU16Le(encoded_payload + 14, payload.max_payload_bytes);
    writeU32Le(encoded_payload + 16, payload.feature_bits);

    writeFrame(
        protocol::WiredMessageType::Capabilities,
        0,
        request_id,
        encoded_payload,
        sizeof(encoded_payload));
}

void SerialTransport::publishEvent(const protocol::EventPayloadV1& payload, uint32_t request_id) {
    if (!session_active_) {
        return;
    }

    uint8_t encoded_payload[protocol::kWiredEventPayloadSize]{};
    encoded_payload[0] = payload.event_code;
    encoded_payload[1] = payload.severity;
    writeU16Le(encoded_payload + 2, 0u);
    writeU32Le(encoded_payload + 4, payload.detail_u32);

    writeFrame(
        protocol::WiredMessageType::Event,
        payload.sequence,
        request_id,
        encoded_payload,
        sizeof(encoded_payload));
}

void SerialTransport::publishCommandAck(const protocol::CommandAckPayloadV1& payload, uint32_t request_id) {
    if (!session_active_) {
        return;
    }

    uint8_t encoded_payload[protocol::kWiredCommandAckPayloadSize]{};
    encoded_payload[0] = payload.command_id;
    encoded_payload[1] = payload.result_code;
    writeU16Le(encoded_payload + 2, payload.reserved);
    writeU32Le(encoded_payload + 4, payload.detail_u32);

    writeFrame(
        protocol::WiredMessageType::CommandAck,
        0,
        request_id,
        encoded_payload,
        sizeof(encoded_payload));
}

void SerialTransport::silenceTextLoggerIfNeeded() {
    if (logger_silenced_) {
        return;
    }
    logger_silenced_ = true;
    services::Logger::setEnabled(false);
}

void SerialTransport::appendReceivedByte(uint8_t byte) {
    if (rx_size_ >= sizeof(rx_buffer_)) {
        discardBytes(1);
    }
    rx_buffer_[rx_size_] = byte;
    rx_size_ += 1;
}

void SerialTransport::consumeRxBuffer() {
    while (tryDecodeFrame()) {
    }
}

bool SerialTransport::tryDecodeFrame() {
    while (rx_size_ >= 2) {
        if (rx_buffer_[0] == protocol::kWiredSof0 && rx_buffer_[1] == protocol::kWiredSof1) {
            break;
        }
        discardBytes(1);
    }

    if (rx_size_ < protocol::kWiredHeaderSize + 2) {
        return false;
    }

    const uint16_t payload_length = readU16Le(rx_buffer_ + 6);
    if (payload_length > board::kSerialMaxPayloadBytes) {
        discardBytes(1);
        return true;
    }

    const size_t total_frame_size = protocol::kWiredHeaderSize + payload_length + 2;
    if (rx_size_ < total_frame_size) {
        return false;
    }

    const uint16_t expected_crc = computeCrcCcittFalse(rx_buffer_ + 2, 14 + payload_length);
    const uint16_t received_crc = readU16Le(rx_buffer_ + total_frame_size - 2);
    if (expected_crc != received_crc) {
        discardBytes(1);
        return true;
    }

    const auto message_type = static_cast<protocol::WiredMessageType>(rx_buffer_[4]);
    const uint32_t request_id = readU32Le(rx_buffer_ + 12);
    const uint8_t* payload = rx_buffer_ + protocol::kWiredHeaderSize;

    if (!has_pending_command_) {
        if (message_type == protocol::WiredMessageType::CommandRequest &&
            payload_length == protocol::kWiredCommandRequestPayloadSize) {
            const auto command_id = static_cast<protocol::CommandId>(payload[0]);
            pending_command_.command_id = command_id;
            pending_command_.arg0_u32 = readU32Le(payload + 4);
            pending_command_.source_transport = TransportKind::Serial;
            pending_request_id_ = request_id;
            has_pending_command_ = true;
            markSessionActive();
        } else if (message_type == protocol::WiredMessageType::Ping && payload_length == 0) {
            pending_command_.command_id = protocol::CommandId::Ping;
            pending_command_.arg0_u32 = 0;
            pending_command_.source_transport = TransportKind::Serial;
            pending_request_id_ = request_id;
            has_pending_command_ = true;
            markSessionActive();
        }
    }

    discardBytes(total_frame_size);
    return true;
}

void SerialTransport::discardBytes(size_t count) {
    if (count >= rx_size_) {
        rx_size_ = 0;
        return;
    }

    memmove(rx_buffer_, rx_buffer_ + count, rx_size_ - count);
    rx_size_ -= count;
}

void SerialTransport::markSessionActive() {
    session_active_ = true;
    silenceTextLoggerIfNeeded();
}

void SerialTransport::writeFrame(
    protocol::WiredMessageType message_type,
    uint32_t sequence,
    uint32_t request_id,
    const uint8_t* payload,
    size_t payload_length) {
    uint8_t frame[protocol::kWiredHeaderSize + board::kSerialMaxPayloadBytes + 2]{};

    frame[0] = protocol::kWiredSof0;
    frame[1] = protocol::kWiredSof1;
    frame[2] = protocol::kProtocolVersionMajor;
    frame[3] = protocol::kProtocolVersionMinor;
    frame[4] = static_cast<uint8_t>(message_type);
    frame[5] = 0;
    writeU16Le(frame + 6, static_cast<uint16_t>(payload_length));
    writeU32Le(frame + 8, sequence);
    writeU32Le(frame + 12, request_id);

    if (payload_length > 0) {
        memcpy(frame + protocol::kWiredHeaderSize, payload, payload_length);
    }

    const uint16_t crc = computeCrcCcittFalse(frame + 2, 14 + payload_length);
    writeU16Le(frame + protocol::kWiredHeaderSize + payload_length, crc);

    const size_t total_frame_size = protocol::kWiredHeaderSize + payload_length + 2;
    Serial.write(frame, total_frame_size);
}

uint16_t SerialTransport::computeCrcCcittFalse(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFFu;
    for (size_t i = 0; i < length; ++i) {
        crc ^= static_cast<uint16_t>(data[i]) << 8;
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

}  // namespace zss::transport
