#include "services/StatusLedController.h"

#include <Arduino.h>

#include "protocol/ProtocolConstants.h"

namespace zss::services {

StatusLedController::StatusLedController(int8_t output_pin)
    : output_pin_(output_pin) {}

void StatusLedController::begin() {
    if (output_pin_ >= 0) {
        pinMode(output_pin_, OUTPUT);
        digitalWrite(output_pin_, LOW);
    }
}

void StatusLedController::updateStatus(uint32_t status_flags) {
    last_status_flags_ = status_flags;
    if (output_pin_ < 0) {
        return;
    }

    const bool fault_active =
        (status_flags & zss::protocol::kStatusFlagAdcFaultMask) != 0u ||
        (status_flags & zss::protocol::kStatusFlagSensorFaultMask) != 0u ||
        (status_flags & zss::protocol::kStatusFlagSamplingOverrunMask) != 0u;

    digitalWrite(output_pin_, fault_active ? HIGH : LOW);
}

}  // namespace zss::services
