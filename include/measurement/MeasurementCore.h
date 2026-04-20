#pragma once

#include "measurement/AdcFrontend.h"

namespace zss::measurement {

class MeasurementCore {
  public:
    explicit MeasurementCore(AdcFrontend& adc_frontend);

    bool begin();
    SensorMeasurements acquire();
    bool isHealthy() const;
    bool lastReadSucceeded() const;
    bool externalAdcAvailable() const;
    const char* lastError() const;

  private:
    AdcFrontend& adc_frontend_;
    bool initialized_ = false;
};

}  // namespace zss::measurement
