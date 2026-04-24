#pragma once

#include <math.h>
#include <stdint.h>

namespace zss::measurement {

struct SensorMeasurements {
    float zirconia_ip_voltage_v = NAN;
    float internal_voltage_v = NAN;
    float zirconia_output_voltage_v = NAN;
    float heater_rtd_resistance_ohm = NAN;
    float differential_pressure_selected_pa = NAN;
};

struct DifferentialPressureMeasurements {
    float low_range_differential_pressure_pa = NAN;
    float high_range_differential_pressure_pa = NAN;
    float selected_differential_pressure_pa = NAN;
    float low_range_temperature_c = NAN;
    float high_range_temperature_c = NAN;
    bool low_range_valid = false;
    bool high_range_valid = false;
    bool selected_from_low_range = false;
};

struct SampleSnapshot {
    uint32_t sequence = 0;
    uint32_t status_flags = 0;
    uint16_t nominal_sample_period_ms = 0;
    SensorMeasurements measurements{};
};

}  // namespace zss::measurement
