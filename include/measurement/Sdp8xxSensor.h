#pragma once

#include <stddef.h>
#include <stdint.h>

#include <Wire.h>

namespace zss::measurement {

struct Sdp8xxReading {
    float differential_pressure_pa = 0.0f;
    float temperature_c = 0.0f;
    float scale_factor_pa = 0.0f;
    bool valid = false;
};

class Sdp8xxSensor {
  public:
    Sdp8xxSensor(TwoWire& wire, uint8_t address, uint32_t expected_product_prefix, const char* label);

    bool begin();
    bool readSample(Sdp8xxReading& reading);
    bool readProductAndSerial(uint32_t& product_number_out, uint64_t& serial_number_out);
    bool isHealthy() const;
    uint8_t address() const;
    uint32_t productNumber() const;
    uint64_t serialNumber() const;
    const char* label() const;
    const char* lastError() const;

  private:
    bool probe();
    bool writeCommand(uint16_t command);
    bool startContinuousMeasurement();
    bool stopContinuousMeasurement();
    bool readFullSample(Sdp8xxReading& reading);
    bool readPressureSample(Sdp8xxReading& reading);
    bool readWords(uint8_t byte_count, uint8_t* buffer);
    bool validateWordCrc(const uint8_t* data) const;
    uint8_t computeCrc(const uint8_t* data, size_t length) const;
    void setError(const char* message);
    void clearError();

    TwoWire& wire_;
    uint8_t address_ = 0u;
    uint32_t expected_product_prefix_ = 0u;
    const char* label_ = "";
    bool healthy_ = false;
    uint32_t product_number_ = 0u;
    uint64_t serial_number_ = 0u;
    float scale_factor_pa_ = 0.0f;
    float latest_temperature_c_ = 0.0f;
    char last_error_[96] = {};
};

}  // namespace zss::measurement
