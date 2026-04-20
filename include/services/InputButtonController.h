#pragma once

#include <stdint.h>

namespace zss::services {

class InputButtonController {
  public:
    explicit InputButtonController(int8_t input_pin);

    void begin(uint32_t now_ms);
    void poll(uint32_t now_ms);
    bool takeToggleRequest();

  private:
    int8_t input_pin_;
    bool last_raw_level_high_ = true;
    bool debounced_level_high_ = true;
    bool toggle_request_pending_ = false;
    uint32_t last_transition_ms_ = 0;
    uint32_t arm_after_ms_ = 0;
};

}  // namespace zss::services
