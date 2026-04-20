#include "services/PumpController.h"

#include <Arduino.h>

#include "board/BoardConfig.h"

namespace zss::services {

PumpController::PumpController(int8_t output_pin)
    : output_pin_(output_pin) {}

void PumpController::begin() {
    if (output_pin_ >= 0) {
        pinMode(output_pin_, OUTPUT);
        analogWriteResolution(zss::board::kPumpPwmResolutionBits);
        analogWriteFrequency(zss::board::kPumpPwmFrequencyHz);
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

uint32_t PumpController::dutyValueForPercent(uint8_t duty_percent) const {
    const uint32_t max_duty = (1u << zss::board::kPumpPwmResolutionBits) - 1u;
    return static_cast<uint32_t>(
        (static_cast<uint64_t>(max_duty) * duty_percent) / 100u);
}

void PumpController::applyHardwareState() const {
    if (output_pin_ >= 0) {
        const uint8_t duty_percent = enabled_
                                         ? zss::board::kPumpPwmDutyOnPercent
                                         : zss::board::kPumpPwmDutyOffPercent;
        analogWrite(output_pin_, static_cast<int>(dutyValueForPercent(duty_percent)));
    }
}

}  // namespace zss::services
