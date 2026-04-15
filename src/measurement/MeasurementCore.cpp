#include "measurement/MeasurementCore.h"

namespace zss::measurement {

MeasurementCore::MeasurementCore(AdcFrontend& adc_frontend)
    : adc_frontend_(adc_frontend) {}

bool MeasurementCore::begin() {
    initialized_ = adc_frontend_.begin();
    return initialized_;
}

SensorMeasurements MeasurementCore::acquire() {
    if (!initialized_) {
        return {};
    }
    return adc_frontend_.readMeasurements();
}

bool MeasurementCore::isHealthy() const {
    return adc_frontend_.isHealthy();
}

bool MeasurementCore::lastReadSucceeded() const {
    return adc_frontend_.lastReadSucceeded();
}

const char* MeasurementCore::lastError() const {
    return adc_frontend_.lastError();
}

}  // namespace zss::measurement
