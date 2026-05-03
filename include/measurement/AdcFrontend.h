#pragma once

#include <Adafruit_ADS1X15.h>

#include "measurement/SensorData.h"

namespace zss::measurement {

class AdcFrontend {
  public:
    bool begin();
    SensorMeasurements readMeasurements();
    SensorMeasurements readScheduledMeasurements(uint8_t auxiliary_channel);
    bool isHealthy() const;
    bool lastReadSucceeded() const;
    bool externalAdcAvailable() const;
    const char* lastError() const;
    uint32_t lastTotalDurationUs() const;
    uint32_t lastChannelDurationUs(uint8_t channel) const;

  private:
    bool initializeExternalAdc();
    void readInternalVoltageIfEnabled(SensorMeasurements& measurements);
    bool tryReadAdsChannelVoltage(uint8_t channel, float& voltage_out);
    bool tryReadLegacySensorSet(SensorMeasurements& measurements);
    void setError(const char* message);
    void clearError();

    Adafruit_ADS1115 ads_;
    bool initialized_ = false;
    bool external_adc_available_ = false;
    bool last_read_succeeded_ = false;
    uint32_t last_recovery_attempt_ms_ = 0;
    uint32_t last_total_duration_us_ = 0;
    uint32_t last_channel_duration_us_[4] = {};
    SensorMeasurements latest_measurements_{};
    char last_error_[96] = {};
};

}  // namespace zss::measurement
