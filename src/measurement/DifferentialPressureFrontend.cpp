#include "measurement/DifferentialPressureFrontend.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "board/BoardConfig.h"

namespace zss::measurement {

DifferentialPressureFrontend::DifferentialPressureFrontend(TwoWire& wire)
    : low_range_sensor_(
          wire,
          zss::board::kSdp810125PaI2cAddress,
          zss::board::kSdp810125PaProductPrefix,
          "SDP810-125Pa"),
      high_range_sensor_(
          wire,
          zss::board::kSdp811500PaI2cAddress,
          zss::board::kSdp811500PaProductPrefix,
          "SDP811-500Pa") {}

bool DifferentialPressureFrontend::begin() {
    const bool low_ok = low_range_sensor_.begin();
    const bool high_ok = high_range_sensor_.begin();
    initialized_ = low_ok || high_ok;
    prefer_low_range_ = low_ok;

    if (!initialized_) {
        setError("No SDP8xx differential pressure sensor initialized");
        return false;
    }

    if (!low_ok || !high_ok) {
        setError("Only one SDP8xx differential pressure sensor initialized");
    } else {
        clearError();
    }
    return true;
}

DifferentialPressureMeasurements DifferentialPressureFrontend::readMeasurements() {
    DifferentialPressureMeasurements measurements{
        .low_range_differential_pressure_pa = NAN,
        .high_range_differential_pressure_pa = NAN,
        .selected_differential_pressure_pa = NAN,
        .low_range_temperature_c = NAN,
        .high_range_temperature_c = NAN,
    };

    if (!initialized_) {
        setError("DifferentialPressureFrontend not initialized");
        return measurements;
    }

    Sdp8xxReading low_range_reading{};
    Sdp8xxReading high_range_reading{};
    const bool low_ok = low_range_sensor_.readSample(low_range_reading);
    const bool high_ok = high_range_sensor_.readSample(high_range_reading);

    measurements.low_range_valid = low_ok && low_range_reading.valid;
    measurements.high_range_valid = high_ok && high_range_reading.valid;

    if (measurements.low_range_valid) {
        measurements.low_range_differential_pressure_pa =
            low_range_reading.differential_pressure_pa;
        measurements.low_range_temperature_c = low_range_reading.temperature_c;
    }

    if (measurements.high_range_valid) {
        measurements.high_range_differential_pressure_pa =
            high_range_reading.differential_pressure_pa;
        measurements.high_range_temperature_c = high_range_reading.temperature_c;
    }

    if (measurements.low_range_valid) {
        updateSelectionPreference(low_range_reading);
    }

    if (measurements.low_range_valid && measurements.high_range_valid) {
        measurements.selected_from_low_range = prefer_low_range_;
    } else if (measurements.low_range_valid) {
        prefer_low_range_ = true;
        measurements.selected_from_low_range = true;
    } else if (measurements.high_range_valid) {
        prefer_low_range_ = false;
        measurements.selected_from_low_range = false;
    } else {
        setError("No valid SDP8xx differential pressure sample");
        return measurements;
    }

    measurements.selected_differential_pressure_pa =
        measurements.selected_from_low_range
            ? measurements.low_range_differential_pressure_pa
            : measurements.high_range_differential_pressure_pa;

    clearError();
    return measurements;
}

bool DifferentialPressureFrontend::isHealthy() const {
    return low_range_sensor_.isHealthy() || high_range_sensor_.isHealthy();
}

bool DifferentialPressureFrontend::lowRangeHealthy() const {
    return low_range_sensor_.isHealthy();
}

bool DifferentialPressureFrontend::highRangeHealthy() const {
    return high_range_sensor_.isHealthy();
}

const char* DifferentialPressureFrontend::lastError() const {
    return last_error_;
}

const char* DifferentialPressureFrontend::lowRangeLastError() const {
    return low_range_sensor_.lastError();
}

const char* DifferentialPressureFrontend::highRangeLastError() const {
    return high_range_sensor_.lastError();
}

void DifferentialPressureFrontend::updateSelectionPreference(
    const Sdp8xxReading& low_range_reading) {
    const float absolute_low_range_pa = fabsf(low_range_reading.differential_pressure_pa);
    if (prefer_low_range_) {
        if (absolute_low_range_pa >= zss::board::kSdpSelectorSwitchToHighPa) {
            prefer_low_range_ = false;
        }
        return;
    }

    if (absolute_low_range_pa <= zss::board::kSdpSelectorReturnToLowPa) {
        prefer_low_range_ = true;
    }
}

void DifferentialPressureFrontend::setError(const char* message) {
    strncpy(last_error_, message, sizeof(last_error_) - 1u);
    last_error_[sizeof(last_error_) - 1u] = '\0';
}

void DifferentialPressureFrontend::clearError() {
    last_error_[0] = '\0';
}

}  // namespace zss::measurement
