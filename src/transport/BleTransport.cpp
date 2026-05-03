#include "transport/BleTransport.h"

#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>

#include <math.h>
#include <string.h>

#include "board/BoardConfig.h"
#include "protocol/ProtocolConstants.h"
#include "transport/TransportTypes.h"

namespace zss::transport {

namespace {

BLEServer* g_server = nullptr;
BLEService* g_control_service = nullptr;
BLEService* g_monitoring_service = nullptr;
BLEService* g_extension_service = nullptr;
BLECharacteristic* g_control_characteristic = nullptr;
BLECharacteristic* g_telemetry_characteristic = nullptr;
BLECharacteristic* g_status_characteristic = nullptr;
BLECharacteristic* g_capabilities_characteristic = nullptr;
BLECharacteristic* g_event_characteristic = nullptr;
BLECharacteristic* g_telemetry_batch_characteristic = nullptr;
BleTransport* g_transport_instance = nullptr;

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

uint16_t bleV1SingleSampleTelemetryFieldBits(uint16_t telemetry_field_bits) {
    return telemetry_field_bits & protocol::kBleV1SingleSampleTelemetryFieldBitsMask;
}

uint16_t bleTelemetryBatchFieldBits(const app::SampleFrame* frames, size_t count) {
    uint16_t field_bits = 0u;
    for (size_t index = 0u; index < count; ++index) {
        field_bits |= frames[index].telemetry.telemetry_field_bits;
    }
    return field_bits & protocol::kBleTelemetryBatchFieldBitsMask;
}

float optionalBatchFloat(uint16_t sample_field_bits, uint16_t field_mask, float value) {
    return (sample_field_bits & field_mask) != 0u ? value : NAN;
}

class BleServerCallbacks final : public BLEServerCallbacks {
  public:
    void onConnect(BLEServer*) override {
        if (g_transport_instance != nullptr) {
            g_transport_instance->update();
        }
    }

    void onDisconnect(BLEServer* server) override {
        if (g_transport_instance != nullptr) {
            g_transport_instance->update();
        }
        if (server != nullptr) {
            server->startAdvertising();
        }
    }
};

class ControlCharacteristicCallbacks final : public BLECharacteristicCallbacks {
  public:
    void onWrite(BLECharacteristic* characteristic) override {
        if (g_transport_instance == nullptr || characteristic == nullptr) {
            return;
        }

        const uint8_t* value = characteristic->getData();
        const size_t length = characteristic->getLength();
        if (value == nullptr || length == 0) {
            return;
        }

        g_transport_instance->queueOpcode(value[0]);
    }
};

BleServerCallbacks g_server_callbacks;
ControlCharacteristicCallbacks g_control_callbacks;

}  // namespace

bool BleTransport::begin() {
    if (g_server != nullptr) {
        return true;
    }

    g_transport_instance = this;
    BLEDevice::init(protocol::kBleDeviceName);
    BLEDevice::setMTU(board::kBlePreferredMtuBytes);

    g_server = BLEDevice::createServer();
    if (g_server == nullptr) {
        return false;
    }
    g_server->setCallbacks(&g_server_callbacks);

    g_control_service = g_server->createService(protocol::kBleControlServiceUuid);
    g_monitoring_service = g_server->createService(protocol::kBleMonitoringServiceUuid);
    g_extension_service = g_server->createService(protocol::kBleExtensionServiceUuid);
    if (g_control_service == nullptr || g_monitoring_service == nullptr || g_extension_service == nullptr) {
        return false;
    }

    g_control_characteristic = g_control_service->createCharacteristic(
        protocol::kBlePumpControlCharacteristicUuid,
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
    g_telemetry_characteristic = g_monitoring_service->createCharacteristic(
        protocol::kBleSensorDataCharacteristicUuid,
        BLECharacteristic::PROPERTY_NOTIFY);
    g_status_characteristic = g_extension_service->createCharacteristic(
        protocol::kBleStatusSnapshotCharacteristicUuid,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
    g_capabilities_characteristic = g_extension_service->createCharacteristic(
        protocol::kBleCapabilitiesCharacteristicUuid,
        BLECharacteristic::PROPERTY_READ);
    g_event_characteristic = g_extension_service->createCharacteristic(
        protocol::kBleEventCharacteristicUuid,
        BLECharacteristic::PROPERTY_NOTIFY);
    g_telemetry_batch_characteristic = g_extension_service->createCharacteristic(
        protocol::kBleTelemetryBatchCharacteristicUuid,
        BLECharacteristic::PROPERTY_NOTIFY);

    if (g_control_characteristic == nullptr ||
        g_telemetry_characteristic == nullptr ||
        g_status_characteristic == nullptr ||
        g_capabilities_characteristic == nullptr ||
        g_event_characteristic == nullptr ||
        g_telemetry_batch_characteristic == nullptr) {
        return false;
    }

    g_control_characteristic->setCallbacks(&g_control_callbacks);
    g_telemetry_characteristic->addDescriptor(new BLE2902());
    g_status_characteristic->addDescriptor(new BLE2902());
    g_event_characteristic->addDescriptor(new BLE2902());
    g_telemetry_batch_characteristic->addDescriptor(new BLE2902());

    g_control_service->start();
    g_monitoring_service->start();
    g_extension_service->start();

    BLEAdvertising* advertising = g_server->getAdvertising();
    if (advertising == nullptr) {
        return false;
    }
    advertising->addServiceUUID(protocol::kBleControlServiceUuid);
    advertising->addServiceUUID(protocol::kBleMonitoringServiceUuid);
    advertising->addServiceUUID(protocol::kBleExtensionServiceUuid);
    advertising->start();
    return true;
}

void BleTransport::update() {
    if (g_server == nullptr) {
        connected_ = false;
        return;
    }

    connected_ = g_server->getConnectedCount() > 0;
}

bool BleTransport::isConnected() const {
    return connected_;
}

bool BleTransport::takePendingCommand(app::CommandRequest& request, uint32_t& request_id) {
    if (!has_pending_command_) {
        return false;
    }

    request = pending_command_;
    request_id = pending_request_id_;
    has_pending_command_ = false;
    pending_request_id_ = 0;
    return true;
}

bool BleTransport::queueOpcode(uint8_t opcode) {
    if (has_pending_command_) {
        return false;
    }

    app::CommandRequest request{};
    request.source_transport = TransportKind::Ble;

    switch (static_cast<protocol::BleOpcode>(opcode)) {
        case protocol::BleOpcode::SetPumpOn:
            request.command_id = protocol::CommandId::SetPumpState;
            request.arg0_u32 = 1u;
            break;

        case protocol::BleOpcode::SetPumpOff:
            request.command_id = protocol::CommandId::SetPumpState;
            request.arg0_u32 = 0u;
            break;

        case protocol::BleOpcode::GetStatus:
            request.command_id = protocol::CommandId::GetStatus;
            break;

        case protocol::BleOpcode::GetCapabilities:
            request.command_id = protocol::CommandId::GetCapabilities;
            break;

        case protocol::BleOpcode::Ping:
            request.command_id = protocol::CommandId::Ping;
            break;

        case protocol::BleOpcode::SetHeaterPowerOn:
            request.command_id = protocol::CommandId::SetHeaterPowerState;
            request.arg0_u32 = 1u;
            break;

        case protocol::BleOpcode::SetHeaterPowerOff:
            request.command_id = protocol::CommandId::SetHeaterPowerState;
            request.arg0_u32 = 0u;
            break;

        default:
            return false;
    }

    pending_command_ = request;
    pending_request_id_ = next_request_id_;
    next_request_id_ += 1u;
    has_pending_command_ = true;
    return true;
}

void BleTransport::publishTelemetry(const protocol::TelemetryPayloadV1& payload) {
    if (!connected_ || g_telemetry_characteristic == nullptr) {
        return;
    }

    const uint32_t now_ms = millis();
    if (last_single_telemetry_notify_ms_ != 0u &&
        now_ms - last_single_telemetry_notify_ms_ < board::kBleSingleTelemetryNotifyIntervalMs) {
        return;
    }
    last_single_telemetry_notify_ms_ = now_ms;

    uint8_t encoded_payload[protocol::kBleTelemetryPacketSize]{};
    encoded_payload[0] = payload.protocol_version_major;
    encoded_payload[1] = payload.protocol_version_minor;
    encoded_payload[2] = payload.telemetry_schema_version;
    encoded_payload[3] = payload.header_flags;
    writeU32Le(encoded_payload + 4, payload.sequence);
    writeU32Le(encoded_payload + 8, payload.status_flags);
    writeFloat32Le(encoded_payload + 12, payload.zirconia_output_voltage_v);
    writeFloat32Le(encoded_payload + 16, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(encoded_payload + 20, payload.differential_pressure_selected_pa);
    writeU16Le(encoded_payload + 24, payload.nominal_sample_period_ms);
    writeU16Le(
        encoded_payload + 26,
        bleV1SingleSampleTelemetryFieldBits(payload.telemetry_field_bits));
    writeU32Le(encoded_payload + 28, payload.diagnostic_bits);

    g_telemetry_characteristic->setValue(encoded_payload, sizeof(encoded_payload));
    g_telemetry_characteristic->notify();
    published_telemetry_count_ += 1u;
}

bool BleTransport::publishTelemetryBatch(const app::SampleFrame* frames, size_t count) {
    if (!connected_ || g_telemetry_batch_characteristic == nullptr || frames == nullptr || count == 0u) {
        return false;
    }
    if (count > protocol::kBleTelemetryBatchMaxSamples) {
        count = protocol::kBleTelemetryBatchMaxSamples;
    }

    uint8_t encoded_payload[protocol::kBleTelemetryBatchMaxPacketSize]{};
    const auto& first = frames[0].telemetry;
    const uint32_t first_sample_tick_us = frames[0].sample_tick_us;
    const uint16_t field_bits =
        bleTelemetryBatchFieldBits(frames, count);
    encoded_payload[0] = first.protocol_version_major;
    encoded_payload[1] = first.protocol_version_minor;
    encoded_payload[2] = 2u;
    encoded_payload[3] = static_cast<uint8_t>(count);
    writeU32Le(encoded_payload + 4, first.sequence);
    writeU32Le(encoded_payload + 8, first_sample_tick_us);
    writeU16Le(encoded_payload + 12, first.nominal_sample_period_ms);
    writeU16Le(encoded_payload + 14, field_bits);

    for (size_t index = 0u; index < count; ++index) {
        const auto& frame = frames[index];
        const auto& telemetry = frame.telemetry;
        uint8_t* sample = encoded_payload +
            protocol::kBleTelemetryBatchHeaderSize +
            (index * protocol::kBleTelemetryBatchSampleSize);
        writeU32Le(sample + 0, frame.sample_tick_us - first_sample_tick_us);
        writeU32Le(sample + 4, telemetry.status_flags);
        writeFloat32Le(sample + 8, telemetry.zirconia_output_voltage_v);
        writeFloat32Le(sample + 12, telemetry.heater_rtd_resistance_ohm);
        writeFloat32Le(
            sample + 16,
            optionalBatchFloat(
                telemetry.telemetry_field_bits,
                protocol::kTelemetryFieldDifferentialPressureSelectedMask,
                telemetry.differential_pressure_selected_pa));
        writeFloat32Le(
            sample + 20,
            optionalBatchFloat(
                telemetry.telemetry_field_bits,
                protocol::kTelemetryFieldDifferentialPressureLowRangeMask,
                telemetry.differential_pressure_low_range_pa));
        writeFloat32Le(
            sample + 24,
            optionalBatchFloat(
                telemetry.telemetry_field_bits,
                protocol::kTelemetryFieldDifferentialPressureHighRangeMask,
                telemetry.differential_pressure_high_range_pa));
    }

    const size_t packet_size =
        protocol::kBleTelemetryBatchHeaderSize +
        (count * protocol::kBleTelemetryBatchSampleSize);
    g_telemetry_batch_characteristic->setValue(encoded_payload, packet_size);
    g_telemetry_batch_characteristic->notify();
    published_batch_count_ += 1u;
    return true;
}

void BleTransport::publishStatusSnapshot(const protocol::StatusSnapshotPayloadV1& payload) {
    if (g_status_characteristic == nullptr) {
        return;
    }

    uint8_t encoded_payload[protocol::kBleStatusSnapshotPacketSize]{};
    encoded_payload[0] = payload.protocol_version_major;
    encoded_payload[1] = payload.protocol_version_minor;
    encoded_payload[2] = payload.status_snapshot_schema_version;
    encoded_payload[3] = payload.response_code;
    writeU32Le(encoded_payload + 4, payload.sequence);
    writeU32Le(encoded_payload + 8, payload.status_flags);
    writeU16Le(encoded_payload + 12, payload.nominal_sample_period_ms);
    writeU16Le(
        encoded_payload + 14,
        bleV1SingleSampleTelemetryFieldBits(payload.telemetry_field_bits));
    writeFloat32Le(encoded_payload + 16, payload.zirconia_output_voltage_v);
    writeFloat32Le(encoded_payload + 20, payload.heater_rtd_resistance_ohm);
    writeFloat32Le(encoded_payload + 24, payload.differential_pressure_selected_pa);

    g_status_characteristic->setValue(encoded_payload, sizeof(encoded_payload));
    if (connected_) {
        g_status_characteristic->notify();
    }
}

void BleTransport::publishCapabilities(const protocol::CapabilitiesPayloadV1& payload) {
    if (g_capabilities_characteristic == nullptr) {
        return;
    }

    uint8_t encoded_payload[protocol::kBleCapabilitiesPacketSize]{};
    encoded_payload[0] = payload.protocol_version_major;
    encoded_payload[1] = payload.protocol_version_minor;
    encoded_payload[2] = payload.capability_schema_version;
    encoded_payload[3] = payload.device_type_code;
    encoded_payload[4] = payload.transport_type_code;
    encoded_payload[5] = payload.firmware_version_major;
    encoded_payload[6] = payload.firmware_version_minor;
    encoded_payload[7] = payload.firmware_version_patch;
    writeU16Le(encoded_payload + 8, payload.supported_command_bits);
    writeU16Le(encoded_payload + 10, payload.telemetry_field_bits);
    writeU16Le(encoded_payload + 12, payload.nominal_sample_period_ms);
    writeU16Le(encoded_payload + 14, payload.status_flag_schema_version);
    writeU16Le(encoded_payload + 16, payload.max_payload_bytes);
    writeU16Le(encoded_payload + 18, 0u);
    writeU32Le(encoded_payload + 20, payload.feature_bits);

    g_capabilities_characteristic->setValue(encoded_payload, sizeof(encoded_payload));
}

void BleTransport::publishEvent(const protocol::EventPayloadV1& payload) {
    if (!connected_ || g_event_characteristic == nullptr) {
        return;
    }

    uint8_t encoded_payload[protocol::kBleEventPacketSize]{};
    encoded_payload[0] = payload.protocol_version_major;
    encoded_payload[1] = payload.protocol_version_minor;
    encoded_payload[2] = payload.event_code;
    encoded_payload[3] = payload.severity;
    writeU32Le(encoded_payload + 4, payload.sequence);
    writeU32Le(encoded_payload + 8, payload.detail_u32);

    g_event_characteristic->setValue(encoded_payload, sizeof(encoded_payload));
    g_event_characteristic->notify();
}

}  // namespace zss::transport
