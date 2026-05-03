#pragma once

#include <stddef.h>
#include <stdint.h>

namespace zss::board {

inline constexpr int8_t kPumpOutputPin = 7;
inline constexpr int8_t kStatusLedPin = -1;
inline constexpr int8_t kStatusLedDataPin = 21;
// Stamp-S3A-derived hardware gates the onboard RGB LED power on GPIO38.
inline constexpr int8_t kStatusLedPowerEnablePin = 38;
inline constexpr int8_t kHeaterPowerEnablePin = 5;
inline constexpr int8_t kPumpToggleButtonPin = 0;
// GPIO5 is reserved for heater enable, so the legacy internal ADC path stays disabled.
inline constexpr int8_t kLegacyInputAdcPin = -1;
inline constexpr int8_t kZss2CellAdcPin = 3;
inline constexpr int8_t kI2cSdaPin = 13;
inline constexpr int8_t kI2cSclPin = 15;

inline constexpr unsigned long kSerialMonitorBaudRate = 115200;
inline constexpr uint16_t kBleNominalSamplePeriodMs = 10;
inline constexpr uint16_t kWiredNominalSamplePeriodMs = 10;
inline constexpr uint16_t kDefaultNominalSamplePeriodMs = kWiredNominalSamplePeriodMs;
inline constexpr uint16_t kBleSingleTelemetryNotifyIntervalMs = 80;
inline constexpr uint16_t kBleTelemetryBatchNotifyIntervalMs = 50;
inline constexpr uint16_t kBlePreferredMtuBytes = 185;
inline constexpr uint32_t kSamplingOverrunToleranceMs = 4;
inline constexpr uint32_t kSummaryLogIntervalMs = 1000;
inline constexpr size_t kSerialRxBufferSize = 512;
inline constexpr size_t kSerialTxBufferSize = 4096;
inline constexpr uint32_t kSerialTxTimeoutMs = 0;
inline constexpr uint16_t kSerialMaxPayloadBytes = 64;
inline constexpr size_t kSampleFrameRingCapacity = 128;
inline constexpr uint32_t kI2cClockHz = 400000;
inline constexpr uint16_t kI2cTimeoutMs = 10;
inline constexpr uint8_t kSdp810125PaI2cAddress = 0x25;
inline constexpr uint8_t kSdp811500PaI2cAddress = 0x26;
inline constexpr uint32_t kSdp810125PaProductPrefix = 0x03020B00u;
inline constexpr uint32_t kSdp811500PaProductPrefix = 0x03020D00u;
inline constexpr float kSdpSelectorReturnToLowPa = 100.0f;
inline constexpr float kSdpSelectorSwitchToHighPa = 110.0f;
inline constexpr uint8_t kInternalAdcOversamplingCount = 16;
inline constexpr uint8_t kStatusLedBrightness = 50;
inline constexpr uint16_t kButtonDebounceMs = 30;
inline constexpr uint16_t kButtonArmDelayMs = 500;
inline constexpr uint32_t kPumpPwmFrequencyHz = 20000;
inline constexpr uint8_t kPumpPwmResolutionBits = 10;
inline constexpr uint8_t kPumpPwmDutyOffPercent = 0;
inline constexpr uint8_t kPumpPwmDutyOnPercent = 50;
inline constexpr float kVoltageDividerRatio = 4.0f;
inline constexpr float kRtdSeriesResistanceOhm = 11000.0f;
inline constexpr float kRtdSourceVoltageV = 5.0f;
inline constexpr uint32_t kAdcRecoveryIntervalMs = 1000;

}  // namespace zss::board
