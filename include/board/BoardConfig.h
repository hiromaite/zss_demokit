#pragma once

#include <stddef.h>
#include <stdint.h>

namespace zss::board {

inline constexpr int8_t kPumpOutputPin = 7;
inline constexpr int8_t kStatusLedPin = -1;
inline constexpr int8_t kStatusLedDataPin = 21;
inline constexpr int8_t kFlowSensorAdcPin = 1;
inline constexpr int8_t kLegacyInputAdcPin = 5;
inline constexpr int8_t kZss2CellAdcPin = 3;
inline constexpr int8_t kI2cSdaPin = 13;
inline constexpr int8_t kI2cSclPin = 15;
inline constexpr int8_t kSensorPowerEnablePin = 38;

inline constexpr unsigned long kSerialMonitorBaudRate = 115200;
inline constexpr uint16_t kBleNominalSamplePeriodMs = 80;
inline constexpr uint16_t kWiredNominalSamplePeriodMs = 10;
inline constexpr uint16_t kDefaultNominalSamplePeriodMs = kWiredNominalSamplePeriodMs;
inline constexpr uint32_t kSamplingOverrunToleranceMs = 4;
inline constexpr uint32_t kSummaryLogIntervalMs = 1000;
inline constexpr size_t kSerialRxBufferSize = 512;
inline constexpr uint16_t kSerialMaxPayloadBytes = 64;
inline constexpr uint32_t kI2cClockHz = 400000;
inline constexpr uint16_t kI2cTimeoutMs = 10;
inline constexpr uint8_t kInternalAdcOversamplingCount = 16;
inline constexpr float kVoltageDividerRatio = 4.0f;
inline constexpr float kRtdSeriesResistanceOhm = 11000.0f;
inline constexpr float kRtdSourceVoltageV = 5.0f;
inline constexpr uint32_t kAdcRecoveryIntervalMs = 1000;

}  // namespace zss::board
