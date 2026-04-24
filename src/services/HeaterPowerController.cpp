#include "services/HeaterPowerController.h"

#include <Arduino.h>

namespace zss::services {

HeaterPowerController::HeaterPowerController(int8_t output_pin)
    : output_pin_(output_pin) {}

void HeaterPowerController::begin() {
    if (output_pin_ >= 0) {
        pinMode(output_pin_, OUTPUT);
    }
    enabled_ = false;
    applyHardwareState();
}

void HeaterPowerController::setEnabled(bool enabled) {
    enabled_ = enabled;
    applyHardwareState();
}

bool HeaterPowerController::isEnabled() const {
    return enabled_;
}

void HeaterPowerController::applyHardwareState() const {
    if (output_pin_ >= 0) {
        digitalWrite(output_pin_, enabled_ ? HIGH : LOW);
    }
}

}  // namespace zss::services
