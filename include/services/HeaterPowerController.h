#pragma once

#include <stdint.h>

namespace zss::services {

class HeaterPowerController {
  public:
    explicit HeaterPowerController(int8_t output_pin);

    void begin();
    void setEnabled(bool enabled);
    bool isEnabled() const;

  private:
    void applyHardwareState() const;

    int8_t output_pin_;
    bool enabled_ = false;
};

}  // namespace zss::services
