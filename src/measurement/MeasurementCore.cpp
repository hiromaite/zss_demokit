#include "measurement/MeasurementCore.h"

#include <math.h>

namespace zss::measurement {

MeasurementCore::MeasurementCore(
    AdcFrontend& adc_frontend,
    DifferentialPressureFrontend& differential_pressure_frontend)
    : adc_frontend_(adc_frontend),
      differential_pressure_frontend_(differential_pressure_frontend) {}

bool MeasurementCore::begin() {
    initialized_ = adc_frontend_.begin();
    differential_pressure_available_ = differential_pressure_frontend_.begin();
    return initialized_;
}

SensorMeasurements MeasurementCore::acquire() {
    if (!initialized_) {
        return {};
    }

    if (differential_pressure_available_) {
        latest_differential_pressure_measurements_ =
            differential_pressure_frontend_.readMeasurements();
    } else {
        latest_differential_pressure_measurements_ = {};
        latest_differential_pressure_measurements_.low_range_differential_pressure_pa = NAN;
        latest_differential_pressure_measurements_.high_range_differential_pressure_pa = NAN;
        latest_differential_pressure_measurements_.selected_differential_pressure_pa = NAN;
        latest_differential_pressure_measurements_.low_range_temperature_c = NAN;
        latest_differential_pressure_measurements_.high_range_temperature_c = NAN;
    }

    return adc_frontend_.readMeasurements();
}

bool MeasurementCore::isHealthy() const {
    return adc_frontend_.isHealthy();
}

bool MeasurementCore::lastReadSucceeded() const {
    return adc_frontend_.lastReadSucceeded();
}

bool MeasurementCore::externalAdcAvailable() const {
    return adc_frontend_.externalAdcAvailable();
}

bool MeasurementCore::differentialPressureAvailable() const {
    return differential_pressure_available_;
}

bool MeasurementCore::differentialPressureHealthy() const {
    return differential_pressure_available_ &&
           differential_pressure_frontend_.isHealthy();
}

const char* MeasurementCore::lastError() const {
    return adc_frontend_.lastError();
}

const char* MeasurementCore::differentialPressureLastError() const {
    return differential_pressure_frontend_.lastError();
}

const DifferentialPressureMeasurements& MeasurementCore::latestDifferentialPressureMeasurements() const {
    return latest_differential_pressure_measurements_;
}

}  // namespace zss::measurement
