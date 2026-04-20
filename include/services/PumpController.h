#pragma once

#include <stdint.h>

namespace zss::services {

class PumpController {
  public:
    explicit PumpController(int8_t output_pin);

    void begin();
    void setEnabled(bool enabled);
    void toggle();
    bool isEnabled() const;

  private:
    uint32_t dutyValueForPercent(uint8_t duty_percent) const;
    void applyHardwareState() const;

    int8_t output_pin_;
    bool enabled_ = false;
};

}  // namespace zss::services
