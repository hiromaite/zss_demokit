#include "measurement/AdcFrontend.h"

#include <Arduino.h>
#include <Wire.h>

#include <math.h>
#include <string.h>

#include "board/BoardConfig.h"
#include "services/Logger.h"

namespace zss::measurement {

bool AdcFrontend::begin() {
    if (zss::board::kSensorPowerEnablePin >= 0) {
        pinMode(zss::board::kSensorPowerEnablePin, OUTPUT);
        digitalWrite(zss::board::kSensorPowerEnablePin, HIGH);
        delay(5);
    }

    Wire.begin(zss::board::kI2cSdaPin, zss::board::kI2cSclPin);
    Wire.setClock(zss::board::kI2cClockHz);
    Wire.setTimeOut(zss::board::kI2cTimeoutMs);

    analogReadResolution(12);
    if (zss::board::kFlowSensorAdcPin >= 0) {
        analogSetPinAttenuation(zss::board::kFlowSensorAdcPin, ADC_11db);
    }
    if (zss::board::kLegacyInputAdcPin >= 0) {
        analogSetPinAttenuation(zss::board::kLegacyInputAdcPin, ADC_11db);
    }
    if (zss::board::kZss2CellAdcPin >= 0) {
        analogSetPinAttenuation(zss::board::kZss2CellAdcPin, ADC_11db);
    }

    initialized_ = true;
    external_adc_available_ = initializeExternalAdc();
    last_read_succeeded_ = external_adc_available_;
    return initialized_;
}

SensorMeasurements AdcFrontend::readMeasurements() {
    if (!initialized_) {
        last_read_succeeded_ = false;
        return {
            .zirconia_output_voltage_v = NAN,
            .heater_rtd_resistance_ohm = NAN,
            .flow_sensor_voltage_v = NAN,
        };
    }

    SensorMeasurements measurements{
        .zirconia_output_voltage_v = NAN,
        .heater_rtd_resistance_ohm = NAN,
        .flow_sensor_voltage_v = readOversampledInternalVoltage(zss::board::kFlowSensorAdcPin),
    };

    if (!external_adc_available_) {
        const uint32_t now_ms = millis();
        if (now_ms - last_recovery_attempt_ms_ >= zss::board::kAdcRecoveryIntervalMs) {
            last_recovery_attempt_ms_ = now_ms;
            external_adc_available_ = initializeExternalAdc();
        }
    }

    float heater_rtd_voltage = NAN;
    if (external_adc_available_) {
        const bool zirconia_ok = tryReadAdsChannelVoltage(2, measurements.zirconia_output_voltage_v);
        const bool heater_ok = tryReadAdsChannelVoltage(1, heater_rtd_voltage);
        if (!zirconia_ok || !heater_ok) {
            external_adc_available_ = false;
        }
    }

    if (isfinite(heater_rtd_voltage)) {
        const float denominator = zss::board::kRtdSourceVoltageV - heater_rtd_voltage;
        if (fabsf(denominator) > 1.0e-6f) {
            measurements.heater_rtd_resistance_ohm =
                (heater_rtd_voltage * zss::board::kRtdSeriesResistanceOhm) / denominator;
        }
    }

    last_read_succeeded_ =
        external_adc_available_ &&
        isfinite(measurements.zirconia_output_voltage_v) &&
        isfinite(measurements.heater_rtd_resistance_ohm) &&
        isfinite(measurements.flow_sensor_voltage_v);
    return measurements;
}

bool AdcFrontend::isHealthy() const {
    return external_adc_available_;
}

bool AdcFrontend::lastReadSucceeded() const {
    return last_read_succeeded_;
}

bool AdcFrontend::externalAdcAvailable() const {
    return external_adc_available_;
}

const char* AdcFrontend::lastError() const {
    return last_error_;
}

bool AdcFrontend::initializeExternalAdc() {
    Wire.beginTransmission(0x48);
    if (Wire.endTransmission() != 0) {
        setError("ADS1115 probe failed");
        return false;
    }

    if (!ads_.begin(0x48, &Wire)) {
        setError("ADS1115 initialization failed");
        return false;
    }

    ads_.setGain(GAIN_ONE);
    ads_.setDataRate(RATE_ADS1115_860SPS);
    clearError();
    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "ADC",
        "ADS1115 initialized on SDA=%d SCL=%d",
        zss::board::kI2cSdaPin,
        zss::board::kI2cSclPin);
    return true;
}

float AdcFrontend::readOversampledInternalVoltage(int8_t pin) const {
    if (pin < 0) {
        return NAN;
    }

    uint32_t sum_millivolts = 0;
    for (uint8_t i = 0; i < zss::board::kInternalAdcOversamplingCount; ++i) {
        sum_millivolts += static_cast<uint32_t>(analogReadMilliVolts(pin));
    }

    const float average_voltage = static_cast<float>(sum_millivolts) /
                                  static_cast<float>(zss::board::kInternalAdcOversamplingCount) /
                                  1000.0f;
    return convertToActualVoltage(average_voltage);
}

bool AdcFrontend::tryReadAdsChannelVoltage(uint8_t channel, float& voltage_out) {
    if (!external_adc_available_) {
        setError("External ADC not initialized");
        voltage_out = NAN;
        return false;
    }

    for (uint8_t attempt = 0; attempt < 3; ++attempt) {
        const int16_t raw = ads_.readADC_SingleEnded(channel);
        if (raw >= 0) {
            voltage_out = ads_.computeVolts(raw);
            clearError();
            return true;
        }
        delay(2);
    }

    setError("Failed to read ADS1115 channel");
    voltage_out = NAN;
    return false;
}

float AdcFrontend::convertToActualVoltage(float measured_voltage) const {
    return measured_voltage * zss::board::kVoltageDividerRatio;
}

void AdcFrontend::setError(const char* message) {
    strncpy(last_error_, message, sizeof(last_error_) - 1);
    last_error_[sizeof(last_error_) - 1] = '\0';
}

void AdcFrontend::clearError() {
    last_error_[0] = '\0';
}

}  // namespace zss::measurement
