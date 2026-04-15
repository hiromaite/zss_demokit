#pragma once

#include <stdint.h>

namespace zss::services {

class StatusLedController {
  public:
    explicit StatusLedController(int8_t output_pin);

    void begin();
    void updateStatus(uint32_t status_flags);

  private:
    int8_t output_pin_;
    uint32_t last_status_flags_ = 0;
};

}  // namespace zss::services
