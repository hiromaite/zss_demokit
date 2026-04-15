#pragma once

#include <Adafruit_ADS1X15.h>

#include "measurement/SensorData.h"

namespace zss::measurement {

class AdcFrontend {
  public:
    bool begin();
    SensorMeasurements readMeasurements();
    bool isHealthy() const;
    bool lastReadSucceeded() const;
    const char* lastError() const;

  private:
    bool initializeExternalAdc();
    float readOversampledInternalVoltage(int8_t pin) const;
    bool tryReadAdsChannelVoltage(uint8_t channel, float& voltage_out);
    float convertToActualVoltage(float measured_voltage) const;
    void setError(const char* message);
    void clearError();

    Adafruit_ADS1115 ads_;
    bool initialized_ = false;
    bool external_adc_available_ = false;
    bool last_read_succeeded_ = false;
    uint32_t last_recovery_attempt_ms_ = 0;
    char last_error_[96] = {};
};

}  // namespace zss::measurement
