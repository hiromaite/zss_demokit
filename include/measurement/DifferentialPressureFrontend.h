#pragma once

#include <Wire.h>

#include "measurement/Sdp8xxSensor.h"
#include "measurement/SensorData.h"

namespace zss::measurement {

class DifferentialPressureFrontend {
  public:
    explicit DifferentialPressureFrontend(TwoWire& wire = Wire);

    bool begin();
    DifferentialPressureMeasurements readMeasurements();
    bool isHealthy() const;
    bool lowRangeHealthy() const;
    bool highRangeHealthy() const;
    const char* lastError() const;
    const char* lowRangeLastError() const;
    const char* highRangeLastError() const;
    uint32_t lastTotalDurationUs() const;
    uint32_t lastLowRangeDurationUs() const;
    uint32_t lastHighRangeDurationUs() const;

  private:
    void updateSelectionPreference(const Sdp8xxReading& low_range_reading);
    void setError(const char* message);
    void clearError();

    Sdp8xxSensor low_range_sensor_;
    Sdp8xxSensor high_range_sensor_;
    bool initialized_ = false;
    bool prefer_low_range_ = true;
    uint32_t last_total_duration_us_ = 0;
    uint32_t last_low_range_duration_us_ = 0;
    uint32_t last_high_range_duration_us_ = 0;
    char last_error_[96] = {};
};

}  // namespace zss::measurement
