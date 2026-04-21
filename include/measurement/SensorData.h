#pragma once

#include <stdint.h>

namespace zss::measurement {

struct SensorMeasurements {
    float zirconia_ip_voltage_v = 0.0f;
    float zirconia_output_voltage_v = 0.0f;
    float heater_rtd_resistance_ohm = 0.0f;
    float differential_pressure_selected_pa = 0.0f;
};

struct DifferentialPressureMeasurements {
    float low_range_differential_pressure_pa = 0.0f;
    float high_range_differential_pressure_pa = 0.0f;
    float selected_differential_pressure_pa = 0.0f;
    float low_range_temperature_c = 0.0f;
    float high_range_temperature_c = 0.0f;
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
