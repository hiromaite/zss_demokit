#pragma once

#include <stddef.h>
#include <stdint.h>

namespace zss::protocol {

inline constexpr uint8_t kProtocolVersionMajor = 1;
inline constexpr uint8_t kProtocolVersionMinor = 0;
inline constexpr uint16_t kStatusFlagSchemaVersion = 2;
inline constexpr uint8_t kCapabilitySchemaVersion = 1;
inline constexpr const char kFirmwareVersionString[] = "0.1.0-skeleton";
inline constexpr const char kBleDeviceName[] = "GasSensor-Proto";
inline constexpr const char kBleControlServiceUuid[] = "0000180F-0000-1000-8000-00805F9B34FB";
inline constexpr const char kBlePumpControlCharacteristicUuid[] = "00002A19-0000-1000-8000-00805F9B34FB";
inline constexpr const char kBleMonitoringServiceUuid[] = "0000181A-0000-1000-8000-00805F9B34FB";
inline constexpr const char kBleSensorDataCharacteristicUuid[] = "00002A58-0000-1000-8000-00805F9B34FB";
inline constexpr const char kBleExtensionServiceUuid[] = "8B1F1000-5C4B-47C1-A742-9D6617B10000";
inline constexpr const char kBleStatusSnapshotCharacteristicUuid[] = "8B1F1001-5C4B-47C1-A742-9D6617B10001";
inline constexpr const char kBleCapabilitiesCharacteristicUuid[] = "8B1F1001-5C4B-47C1-A742-9D6617B10002";
inline constexpr const char kBleEventCharacteristicUuid[] = "8B1F1001-5C4B-47C1-A742-9D6617B10003";
inline constexpr uint8_t kWiredSof0 = 0xA5;
inline constexpr uint8_t kWiredSof1 = 0x5A;

inline constexpr const char kDeviceTypeName[] = "zirconia_sensor";
inline constexpr const char kBleTransportName[] = "ble";
inline constexpr const char kSerialTransportName[] = "serial";

enum class DeviceTypeCode : uint8_t {
    ZirconiaSensor = 1,
};

enum class TransportTypeCode : uint8_t {
    Ble = 1,
    Serial = 2,
};

enum class CommandId : uint8_t {
    GetCapabilities = 0x01,
    GetStatus = 0x02,
    SetPumpState = 0x03,
    Ping = 0x04,
    SetHeaterPowerState = 0x05,
};

enum class BleOpcode : uint8_t {
    SetPumpOn = 0x55,
    SetPumpOff = 0xAA,
    GetStatus = 0x30,
    GetCapabilities = 0x31,
    Ping = 0x32,
    SetHeaterPowerOn = 0x33,
    SetHeaterPowerOff = 0x34,
};

enum class WiredMessageType : uint8_t {
    TelemetrySample = 0x01,
    StatusSnapshot = 0x02,
    Capabilities = 0x03,
    CommandRequest = 0x10,
    CommandAck = 0x11,
    Event = 0x12,
    Error = 0x13,
    Ping = 0x14,
    Pong = 0x15,
    TimingDiagnostic = 0x16,
};

enum class ResultCode : uint8_t {
    Ok = 0,
    UnsupportedCommand = 1,
    InvalidArgument = 2,
    InvalidState = 3,
    Busy = 4,
    InternalError = 5,
};

enum class EventCode : uint8_t {
    BootComplete = 0x01,
    WarningRaised = 0x02,
    WarningCleared = 0x03,
    CommandError = 0x04,
    AdcFaultRaised = 0x05,
    AdcFaultCleared = 0x06,
};

inline constexpr uint32_t kStatusFlagPumpOnMask = 1u << 0;
inline constexpr uint32_t kStatusFlagTransportSessionActiveMask = 1u << 1;
inline constexpr uint32_t kStatusFlagAdcFaultMask = 1u << 2;
inline constexpr uint32_t kStatusFlagSamplingOverrunMask = 1u << 3;
inline constexpr uint32_t kStatusFlagSensorFaultMask = 1u << 4;
inline constexpr uint32_t kStatusFlagTelemetryRateWarningMask = 1u << 5;
inline constexpr uint32_t kStatusFlagCommandErrorLatchedMask = 1u << 6;
inline constexpr uint32_t kStatusFlagHeaterPowerOnMask = 1u << 7;

inline constexpr uint32_t kDiagnosticBitBootCompleteMask = 1u << 0;
inline constexpr uint32_t kDiagnosticBitMeasurementCoreReadyMask = 1u << 1;
inline constexpr uint32_t kDiagnosticBitExternalAdcReadyMask = 1u << 2;
inline constexpr uint32_t kDiagnosticBitBleTransportReadyMask = 1u << 3;
inline constexpr uint32_t kDiagnosticBitSerialTransportReadyMask = 1u << 4;
inline constexpr uint32_t kDiagnosticBitBleSessionObservedMask = 1u << 5;
inline constexpr uint32_t kDiagnosticBitSerialSessionObservedMask = 1u << 6;
inline constexpr uint32_t kDiagnosticBitTelemetryPublishedMask = 1u << 7;

inline constexpr uint16_t kSupportedCommandBits =
    (1u << 0) |
    (1u << 1) |
    (1u << 2) |
    (1u << 3) |
    (1u << 4);

inline constexpr uint16_t kTelemetryFieldBits =
    (1u << 0) |
    (1u << 1);
inline constexpr uint16_t kTelemetryFieldDifferentialPressureSelectedMask = 1u << 3;
inline constexpr uint16_t kTelemetryFieldDifferentialPressureLowRangeMask = 1u << 4;
inline constexpr uint16_t kTelemetryFieldDifferentialPressureHighRangeMask = 1u << 5;
inline constexpr uint16_t kTelemetryFieldZirconiaIpVoltageMask = 1u << 6;
inline constexpr uint16_t kTelemetryFieldInternalVoltageMask = 1u << 7;

inline constexpr uint32_t kBleFeatureBits =
    (1u << 0) |
    (1u << 1) |
    (1u << 2) |
    (1u << 3);

inline constexpr uint32_t kSerialFeatureBits =
    (1u << 0) |
    (1u << 1) |
    (1u << 2) |
    (1u << 3);

inline constexpr size_t kBleTelemetryPacketSize = 32;
inline constexpr size_t kBleStatusSnapshotPacketSize = 28;
inline constexpr size_t kBleCapabilitiesPacketSize = 24;
inline constexpr size_t kBleEventPacketSize = 12;
inline constexpr size_t kWiredHeaderSize = 16;
inline constexpr size_t kWiredTelemetryPayloadSize = 20;
inline constexpr size_t kWiredTelemetryPayloadExtendedSize = 28;
inline constexpr size_t kWiredTelemetryPayloadDiagnosticSize = 36;
inline constexpr size_t kWiredStatusSnapshotPayloadSize = 20;
inline constexpr size_t kWiredStatusSnapshotPayloadExtendedSize = 28;
inline constexpr size_t kWiredStatusSnapshotPayloadDiagnosticSize = 36;
inline constexpr size_t kWiredEventPayloadSize = 8;
inline constexpr size_t kWiredErrorPayloadSize = 8;
inline constexpr size_t kWiredCommandRequestPayloadSize = 16;
inline constexpr size_t kWiredCapabilitiesPayloadSize = 20;
inline constexpr size_t kWiredCommandAckPayloadSize = 8;
inline constexpr size_t kWiredTimingDiagnosticPayloadSize = 16;

inline constexpr float kDummyFlowRateGain = 1.0f;
inline constexpr float kDummyFlowRateOffset = 0.0f;

}  // namespace zss::protocol
