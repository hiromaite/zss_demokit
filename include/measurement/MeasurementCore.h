#pragma once

#include "measurement/AdcFrontend.h"
#include "measurement/DifferentialPressureFrontend.h"

namespace zss::measurement {

class MeasurementCore {
  public:
    MeasurementCore(
        AdcFrontend& adc_frontend,
        DifferentialPressureFrontend& differential_pressure_frontend);

    bool begin();
    SensorMeasurements acquire();
    bool isHealthy() const;
    bool lastReadSucceeded() const;
    bool externalAdcAvailable() const;
    bool differentialPressureAvailable() const;
    bool differentialPressureHealthy() const;
    const char* lastError() const;
    const char* differentialPressureLastError() const;
    const DifferentialPressureMeasurements& latestDifferentialPressureMeasurements() const;

  private:
    AdcFrontend& adc_frontend_;
    DifferentialPressureFrontend& differential_pressure_frontend_;
    bool initialized_ = false;
    bool differential_pressure_available_ = false;
    DifferentialPressureMeasurements latest_differential_pressure_measurements_{};
};

}  // namespace zss::measurement
