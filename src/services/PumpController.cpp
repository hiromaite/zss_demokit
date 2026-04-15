#include "services/PumpController.h"

#include <Arduino.h>

namespace zss::services {

PumpController::PumpController(int8_t output_pin)
    : output_pin_(output_pin) {}

void PumpController::begin() {
    if (output_pin_ >= 0) {
        pinMode(output_pin_, OUTPUT);
    }
    applyHardwareState();
}

void PumpController::setEnabled(bool enabled) {
    enabled_ = enabled;
    applyHardwareState();
}

void PumpController::toggle() {
    setEnabled(!enabled_);
}

bool PumpController::isEnabled() const {
    return enabled_;
}

void PumpController::applyHardwareState() const {
    if (output_pin_ >= 0) {
        digitalWrite(output_pin_, enabled_ ? HIGH : LOW);
    }
}

}  // namespace zss::services
