#include "measurement/DifferentialPressureFrontend.h"

#include <Arduino.h>

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
    low_range_available_ = low_ok;
    high_range_available_ = high_ok;
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
    const uint32_t read_started_us = micros();
    last_low_range_duration_us_ = 0;
    last_high_range_duration_us_ = 0;
    DifferentialPressureMeasurements measurements{
        .low_range_differential_pressure_pa = NAN,
        .high_range_differential_pressure_pa = NAN,
        .selected_differential_pressure_pa = NAN,
        .low_range_temperature_c = NAN,
        .high_range_temperature_c = NAN,
    };

    if (!initialized_) {
        setError("DifferentialPressureFrontend not initialized");
        last_total_duration_us_ = micros() - read_started_us;
        return measurements;
    }

    Sdp8xxReading low_range_reading{};
    Sdp8xxReading high_range_reading{};
    bool low_ok = false;
    bool high_ok = false;
    if (low_range_available_) {
        const uint32_t low_range_started_us = micros();
        low_ok = low_range_sensor_.readSample(low_range_reading);
        last_low_range_duration_us_ = micros() - low_range_started_us;
        if (!low_ok) {
            low_range_available_ = false;
        }
    }
    if (high_range_available_) {
        const uint32_t high_range_started_us = micros();
        high_ok = high_range_sensor_.readSample(high_range_reading);
        last_high_range_duration_us_ = micros() - high_range_started_us;
        if (!high_ok) {
            high_range_available_ = false;
        }
    }

    measurements.low_range_valid = low_ok && low_range_reading.valid;
    measurements.high_range_valid = high_ok && high_range_reading.valid;

    if (measurements.low_range_valid) {
        measurements.low_range_differential_pressure_pa =
            low_range_reading.differential_pressure_pa *
            zss::board::kSdp810125PaPressurePolarity;
        measurements.low_range_temperature_c = low_range_reading.temperature_c;
    }

    if (measurements.high_range_valid) {
        measurements.high_range_differential_pressure_pa =
            high_range_reading.differential_pressure_pa *
            zss::board::kSdp811500PaPressurePolarity;
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
        last_total_duration_us_ = micros() - read_started_us;
        return measurements;
    }

    measurements.selected_differential_pressure_pa =
        measurements.selected_from_low_range
            ? measurements.low_range_differential_pressure_pa
            : measurements.high_range_differential_pressure_pa;

    clearError();
    last_total_duration_us_ = micros() - read_started_us;
    latest_measurements_ = measurements;
    return measurements;
}

DifferentialPressureMeasurements DifferentialPressureFrontend::readScheduledMeasurements(bool read_low_range) {
    const uint32_t read_started_us = micros();
    last_low_range_duration_us_ = 0;
    last_high_range_duration_us_ = 0;

    if (!initialized_) {
        setError("DifferentialPressureFrontend not initialized");
        latest_measurements_ = {};
        last_total_duration_us_ = micros() - read_started_us;
        return latest_measurements_;
    }

    if (read_low_range && low_range_available_) {
        Sdp8xxReading low_range_reading{};
        const uint32_t low_range_started_us = micros();
        const bool low_ok = low_range_sensor_.readSample(low_range_reading);
        last_low_range_duration_us_ = micros() - low_range_started_us;
        latest_measurements_.low_range_valid = low_ok && low_range_reading.valid;
        if (latest_measurements_.low_range_valid) {
            latest_measurements_.low_range_differential_pressure_pa =
                low_range_reading.differential_pressure_pa *
                zss::board::kSdp810125PaPressurePolarity;
            latest_measurements_.low_range_temperature_c = low_range_reading.temperature_c;
            updateSelectionPreference(low_range_reading);
        } else {
            low_range_available_ = false;
            latest_measurements_.low_range_differential_pressure_pa = NAN;
            latest_measurements_.low_range_temperature_c = NAN;
        }
    } else if (!low_range_available_) {
        latest_measurements_.low_range_valid = false;
        latest_measurements_.low_range_differential_pressure_pa = NAN;
        latest_measurements_.low_range_temperature_c = NAN;
    }

    if (high_range_available_) {
        Sdp8xxReading high_range_reading{};
        const uint32_t high_range_started_us = micros();
        const bool high_ok = high_range_sensor_.readSample(high_range_reading);
        last_high_range_duration_us_ = micros() - high_range_started_us;
        latest_measurements_.high_range_valid = high_ok && high_range_reading.valid;
        if (latest_measurements_.high_range_valid) {
            latest_measurements_.high_range_differential_pressure_pa =
                high_range_reading.differential_pressure_pa *
                zss::board::kSdp811500PaPressurePolarity;
            latest_measurements_.high_range_temperature_c = high_range_reading.temperature_c;
        } else {
            high_range_available_ = false;
            latest_measurements_.high_range_differential_pressure_pa = NAN;
            latest_measurements_.high_range_temperature_c = NAN;
        }
    } else {
        latest_measurements_.high_range_valid = false;
        latest_measurements_.high_range_differential_pressure_pa = NAN;
        latest_measurements_.high_range_temperature_c = NAN;
    }

    updateSelectedFromCachedMeasurements();
    if (!latest_measurements_.low_range_valid && !latest_measurements_.high_range_valid) {
        setError("No valid cached SDP8xx differential pressure sample");
    } else {
        clearError();
    }
    last_total_duration_us_ = micros() - read_started_us;
    return latest_measurements_;
}

bool DifferentialPressureFrontend::isHealthy() const {
    return low_range_sensor_.isHealthy() || high_range_sensor_.isHealthy();
}

bool DifferentialPressureFrontend::lowRangeAvailable() const {
    return low_range_available_;
}

bool DifferentialPressureFrontend::highRangeAvailable() const {
    return high_range_available_;
}

bool DifferentialPressureFrontend::rawChannelsAvailable() const {
    return low_range_available_ && high_range_available_;
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

uint32_t DifferentialPressureFrontend::lastTotalDurationUs() const {
    return last_total_duration_us_;
}

uint32_t DifferentialPressureFrontend::lastLowRangeDurationUs() const {
    return last_low_range_duration_us_;
}

uint32_t DifferentialPressureFrontend::lastHighRangeDurationUs() const {
    return last_high_range_duration_us_;
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

void DifferentialPressureFrontend::updateSelectedFromCachedMeasurements() {
    if (latest_measurements_.low_range_valid && latest_measurements_.high_range_valid) {
        latest_measurements_.selected_from_low_range = prefer_low_range_;
    } else if (latest_measurements_.low_range_valid) {
        prefer_low_range_ = true;
        latest_measurements_.selected_from_low_range = true;
    } else if (latest_measurements_.high_range_valid) {
        prefer_low_range_ = false;
        latest_measurements_.selected_from_low_range = false;
    } else {
        latest_measurements_.selected_differential_pressure_pa = NAN;
        latest_measurements_.selected_from_low_range = false;
        return;
    }

    latest_measurements_.selected_differential_pressure_pa =
        latest_measurements_.selected_from_low_range
            ? latest_measurements_.low_range_differential_pressure_pa
            : latest_measurements_.high_range_differential_pressure_pa;
}

void DifferentialPressureFrontend::setError(const char* message) {
    strncpy(last_error_, message, sizeof(last_error_) - 1u);
    last_error_[sizeof(last_error_) - 1u] = '\0';
}

void DifferentialPressureFrontend::clearError() {
    last_error_[0] = '\0';
}

}  // namespace zss::measurement
