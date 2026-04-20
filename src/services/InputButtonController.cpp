#include "services/InputButtonController.h"

#include <Arduino.h>

#include "board/BoardConfig.h"

namespace zss::services {

InputButtonController::InputButtonController(int8_t input_pin)
    : input_pin_(input_pin) {}

void InputButtonController::begin(uint32_t now_ms) {
    if (input_pin_ < 0) {
        return;
    }

    pinMode(input_pin_, INPUT_PULLUP);
    const bool level_high = digitalRead(input_pin_) != LOW;
    last_raw_level_high_ = level_high;
    debounced_level_high_ = level_high;
    last_transition_ms_ = now_ms;
    arm_after_ms_ = now_ms + zss::board::kButtonArmDelayMs;
    toggle_request_pending_ = false;
}

void InputButtonController::poll(uint32_t now_ms) {
    if (input_pin_ < 0) {
        return;
    }

    const bool raw_level_high = digitalRead(input_pin_) != LOW;
    if (raw_level_high != last_raw_level_high_) {
        last_raw_level_high_ = raw_level_high;
        last_transition_ms_ = now_ms;
    }

    if (raw_level_high == debounced_level_high_) {
        return;
    }

    if (now_ms - last_transition_ms_ < zss::board::kButtonDebounceMs) {
        return;
    }

    const bool previous_level_high = debounced_level_high_;
    debounced_level_high_ = raw_level_high;

    if (now_ms < arm_after_ms_) {
        return;
    }

    const bool falling_edge = previous_level_high && !debounced_level_high_;
    if (falling_edge) {
        toggle_request_pending_ = true;
    }
}

bool InputButtonController::takeToggleRequest() {
    const bool pending = toggle_request_pending_;
    toggle_request_pending_ = false;
    return pending;
}

}  // namespace zss::services
