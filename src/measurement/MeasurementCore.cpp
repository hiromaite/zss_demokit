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
        latest_acquisition_timing_ = {};
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

    const auto measurements = adc_frontend_.readMeasurements();
    latest_acquisition_timing_.adc_total_duration_us = adc_frontend_.lastTotalDurationUs();
    latest_acquisition_timing_.differential_pressure_total_duration_us =
        differential_pressure_available_ ? differential_pressure_frontend_.lastTotalDurationUs() : 0u;
    latest_acquisition_timing_.ads_ch0_duration_us = adc_frontend_.lastChannelDurationUs(0);
    latest_acquisition_timing_.ads_ch1_duration_us = adc_frontend_.lastChannelDurationUs(1);
    latest_acquisition_timing_.ads_ch2_duration_us = adc_frontend_.lastChannelDurationUs(2);
    latest_acquisition_timing_.sdp_low_range_duration_us =
        differential_pressure_available_ ? differential_pressure_frontend_.lastLowRangeDurationUs() : 0u;
    latest_acquisition_timing_.sdp_high_range_duration_us =
        differential_pressure_available_ ? differential_pressure_frontend_.lastHighRangeDurationUs() : 0u;
    return measurements;
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

const AcquisitionTiming& MeasurementCore::latestAcquisitionTiming() const {
    return latest_acquisition_timing_;
}

}  // namespace zss::measurement
