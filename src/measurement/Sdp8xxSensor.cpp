#include "measurement/Sdp8xxSensor.h"

#include <Arduino.h>

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

namespace zss::measurement {
namespace {

constexpr uint16_t kStartContinuousDifferentialPressureAverageTillReadCommand = 0x3615;
constexpr uint16_t kStopContinuousMeasurementCommand = 0x3FF9;
constexpr uint16_t kReadProductIdentifierCommandPart1 = 0x367C;
constexpr uint16_t kReadProductIdentifierCommandPart2 = 0xE102;
constexpr uint8_t kFullSampleReadLengthBytes = 9;
constexpr uint8_t kPressureSampleReadLengthBytes = 3;
constexpr uint8_t kProductAndSerialReadLengthBytes = 18;
constexpr uint16_t kSensorWarmupDelayMs = 20;
constexpr uint16_t kSensorStopToIdleDelayUs = 700;
constexpr float kTemperatureScaleFactor = 200.0f;

}  // namespace

Sdp8xxSensor::Sdp8xxSensor(
    TwoWire& wire,
    uint8_t address,
    uint32_t expected_product_prefix,
    const char* label)
    : wire_(wire),
      address_(address),
      expected_product_prefix_(expected_product_prefix),
      label_(label != nullptr ? label : "") {}

bool Sdp8xxSensor::begin() {
    healthy_ = false;

    if (!probe()) {
        char message[96];
        snprintf(message, sizeof(message), "%s probe failed", label_);
        setError(message);
        return false;
    }

    stopContinuousMeasurement();
    delayMicroseconds(kSensorStopToIdleDelayUs);

    uint32_t product_number = 0u;
    uint64_t serial_number = 0u;
    if (!readProductAndSerial(product_number, serial_number)) {
        return false;
    }

    if (expected_product_prefix_ != 0u &&
        (product_number & 0xFFFFFF00u) != expected_product_prefix_) {
        char message[96];
        snprintf(
            message,
            sizeof(message),
            "%s unexpected product 0x%08" PRIX32,
            label_,
            product_number);
        setError(message);
        return false;
    }

    product_number_ = product_number;
    serial_number_ = serial_number;

    if (!startContinuousMeasurement()) {
        return false;
    }

    delay(kSensorWarmupDelayMs);

    Sdp8xxReading reading{};
    if (!readFullSample(reading)) {
        return false;
    }

    healthy_ = true;
    clearError();
    return true;
}

bool Sdp8xxSensor::readSample(Sdp8xxReading& reading) {
    if (scale_factor_pa_ > 0.0f) {
        return readPressureSample(reading);
    }
    return readFullSample(reading);
}

bool Sdp8xxSensor::readFullSample(Sdp8xxReading& reading) {
    uint8_t buffer[kFullSampleReadLengthBytes] = {};
    if (!readWords(kFullSampleReadLengthBytes, buffer)) {
        return false;
    }

    for (uint8_t offset = 0; offset < kFullSampleReadLengthBytes; offset += 3) {
        if (!validateWordCrc(&buffer[offset])) {
            char message[96];
            snprintf(message, sizeof(message), "%s CRC mismatch", label_);
            setError(message);
            healthy_ = false;
            return false;
        }
    }

    const int16_t raw_pressure =
        static_cast<int16_t>((static_cast<uint16_t>(buffer[0]) << 8u) | buffer[1]);
    const int16_t raw_temperature =
        static_cast<int16_t>((static_cast<uint16_t>(buffer[3]) << 8u) | buffer[4]);
    const uint16_t scale_factor =
        static_cast<uint16_t>((static_cast<uint16_t>(buffer[6]) << 8u) | buffer[7]);

    if (scale_factor == 0u) {
        char message[96];
        snprintf(message, sizeof(message), "%s returned zero scale", label_);
        setError(message);
        healthy_ = false;
        return false;
    }

    scale_factor_pa_ = static_cast<float>(scale_factor);
    latest_temperature_c_ = static_cast<float>(raw_temperature) / kTemperatureScaleFactor;

    reading.scale_factor_pa = scale_factor_pa_;
    reading.differential_pressure_pa = static_cast<float>(raw_pressure) / reading.scale_factor_pa;
    reading.temperature_c = latest_temperature_c_;
    reading.valid = isfinite(reading.differential_pressure_pa) && isfinite(reading.temperature_c);

    healthy_ = reading.valid;
    if (healthy_) {
        clearError();
    } else {
        char message[96];
        snprintf(message, sizeof(message), "%s sample invalid", label_);
        setError(message);
    }
    return healthy_;
}

bool Sdp8xxSensor::readPressureSample(Sdp8xxReading& reading) {
    if (scale_factor_pa_ <= 0.0f) {
        char message[96];
        snprintf(message, sizeof(message), "%s scale not initialized", label_);
        setError(message);
        healthy_ = false;
        return false;
    }

    uint8_t buffer[kPressureSampleReadLengthBytes] = {};
    if (!readWords(kPressureSampleReadLengthBytes, buffer)) {
        return false;
    }

    if (!validateWordCrc(buffer)) {
        char message[96];
        snprintf(message, sizeof(message), "%s pressure CRC mismatch", label_);
        setError(message);
        healthy_ = false;
        return false;
    }

    const int16_t raw_pressure =
        static_cast<int16_t>((static_cast<uint16_t>(buffer[0]) << 8u) | buffer[1]);

    reading.scale_factor_pa = scale_factor_pa_;
    reading.differential_pressure_pa = static_cast<float>(raw_pressure) / reading.scale_factor_pa;
    reading.temperature_c = latest_temperature_c_;
    reading.valid = isfinite(reading.differential_pressure_pa);

    healthy_ = reading.valid;
    if (healthy_) {
        clearError();
    } else {
        char message[96];
        snprintf(message, sizeof(message), "%s pressure sample invalid", label_);
        setError(message);
    }
    return healthy_;
}

bool Sdp8xxSensor::readProductAndSerial(uint32_t& product_number_out, uint64_t& serial_number_out) {
    product_number_out = 0u;
    serial_number_out = 0u;

    if (!writeCommand(kReadProductIdentifierCommandPart1) ||
        !writeCommand(kReadProductIdentifierCommandPart2)) {
        return false;
    }

    uint8_t buffer[kProductAndSerialReadLengthBytes] = {};
    if (!readWords(kProductAndSerialReadLengthBytes, buffer)) {
        return false;
    }

    for (uint8_t offset = 0; offset < kProductAndSerialReadLengthBytes; offset += 3) {
        if (!validateWordCrc(&buffer[offset])) {
            char message[96];
            snprintf(message, sizeof(message), "%s product CRC mismatch", label_);
            setError(message);
            return false;
        }
    }

    product_number_out =
        (static_cast<uint32_t>(buffer[0]) << 24u) |
        (static_cast<uint32_t>(buffer[1]) << 16u) |
        (static_cast<uint32_t>(buffer[3]) << 8u) |
        static_cast<uint32_t>(buffer[4]);

    serial_number_out =
        (static_cast<uint64_t>(buffer[6]) << 56u) |
        (static_cast<uint64_t>(buffer[7]) << 48u) |
        (static_cast<uint64_t>(buffer[9]) << 40u) |
        (static_cast<uint64_t>(buffer[10]) << 32u) |
        (static_cast<uint64_t>(buffer[12]) << 24u) |
        (static_cast<uint64_t>(buffer[13]) << 16u) |
        (static_cast<uint64_t>(buffer[15]) << 8u) |
        static_cast<uint64_t>(buffer[16]);

    clearError();
    return true;
}

bool Sdp8xxSensor::isHealthy() const {
    return healthy_;
}

uint8_t Sdp8xxSensor::address() const {
    return address_;
}

uint32_t Sdp8xxSensor::productNumber() const {
    return product_number_;
}

uint64_t Sdp8xxSensor::serialNumber() const {
    return serial_number_;
}

const char* Sdp8xxSensor::label() const {
    return label_;
}

const char* Sdp8xxSensor::lastError() const {
    return last_error_;
}

bool Sdp8xxSensor::probe() {
    wire_.beginTransmission(address_);
    return wire_.endTransmission() == 0;
}

bool Sdp8xxSensor::writeCommand(uint16_t command) {
    wire_.beginTransmission(address_);
    wire_.write(static_cast<uint8_t>((command >> 8u) & 0xFFu));
    wire_.write(static_cast<uint8_t>(command & 0xFFu));
    if (wire_.endTransmission() != 0) {
        char message[96];
        snprintf(message, sizeof(message), "%s command 0x%04X failed", label_, command);
        setError(message);
        healthy_ = false;
        return false;
    }
    return true;
}

bool Sdp8xxSensor::startContinuousMeasurement() {
    if (!writeCommand(kStartContinuousDifferentialPressureAverageTillReadCommand)) {
        return false;
    }
    clearError();
    return true;
}

bool Sdp8xxSensor::stopContinuousMeasurement() {
    if (!writeCommand(kStopContinuousMeasurementCommand)) {
        return false;
    }
    return true;
}

bool Sdp8xxSensor::readWords(uint8_t byte_count, uint8_t* buffer) {
    const size_t actual = wire_.requestFrom(address_, static_cast<size_t>(byte_count), true);
    if (actual != byte_count) {
        char message[96];
        snprintf(
            message,
            sizeof(message),
            "%s short read %u/%u",
            label_,
            static_cast<unsigned int>(actual),
            static_cast<unsigned int>(byte_count));
        setError(message);
        healthy_ = false;
        return false;
    }

    for (uint8_t index = 0; index < byte_count; ++index) {
        if (!wire_.available()) {
            char message[96];
            snprintf(message, sizeof(message), "%s read underrun", label_);
            setError(message);
            healthy_ = false;
            return false;
        }
        buffer[index] = static_cast<uint8_t>(wire_.read());
    }

    return true;
}

bool Sdp8xxSensor::validateWordCrc(const uint8_t* data) const {
    return computeCrc(data, 2u) == data[2];
}

uint8_t Sdp8xxSensor::computeCrc(const uint8_t* data, size_t length) const {
    uint8_t crc = 0xFFu;
    for (size_t index = 0; index < length; ++index) {
        crc ^= data[index];
        for (uint8_t bit = 0; bit < 8u; ++bit) {
            if ((crc & 0x80u) != 0u) {
                crc = static_cast<uint8_t>((crc << 1u) ^ 0x31u);
            } else {
                crc <<= 1u;
            }
        }
    }
    return crc;
}

void Sdp8xxSensor::setError(const char* message) {
    strncpy(last_error_, message, sizeof(last_error_) - 1u);
    last_error_[sizeof(last_error_) - 1u] = '\0';
}

void Sdp8xxSensor::clearError() {
    last_error_[0] = '\0';
}

}  // namespace zss::measurement
