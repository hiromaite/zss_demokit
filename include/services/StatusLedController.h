#pragma once

#include <stdint.h>

namespace zss::services {

struct StatusLedContext {
    uint32_t status_flags = 0;
    bool ble_ready = false;
    bool ble_connected = false;
    bool recording_active = false;
    bool measurement_ready = false;
    float zirconia_ip_voltage_v = 0.0f;
};

class StatusLedController {
  public:
    explicit StatusLedController(int8_t data_pin);

    void begin();
    void setContext(const StatusLedContext& context);
    void tick(uint32_t now_ms);

  private:
    enum class LedState : uint8_t {
        Boot,
        Error,
        SamplingOverrun,
        RecordingActive,
        VoltageLow,
        VoltageHigh,
        VoltageGradient,
        VoltageTargetNotify,
        VoltageTargetStable,
        BleConnected,
        BleAdvertising,
        Idle,
    };

    void applyStateTransition(LedState next_state, uint32_t now_ms);
    LedState selectState(uint32_t now_ms) const;
    void renderState(uint32_t now_ms);
    void showSolidRgb(uint8_t red, uint8_t green, uint8_t blue);
    void showBlinkRgb(uint32_t now_ms, uint8_t red, uint8_t green, uint8_t blue, uint16_t on_ms, uint16_t off_ms);
    void showVoltageGradient(float zirconia_ip_voltage_v);
    void showTwoShortFlashes(uint32_t now_ms, uint8_t red, uint8_t green, uint8_t blue, uint16_t cycle_ms);
    void showBreathingRgb(uint32_t now_ms, uint8_t red, uint8_t green, uint8_t blue, uint16_t cycle_ms);
    bool renderThreeGreenFlashes(uint32_t now_ms);
    bool isVoltageTargetBand(float zirconia_ip_voltage_v) const;

    int8_t data_pin_;
    StatusLedContext context_{};
    LedState current_state_ = LedState::Boot;
    uint32_t boot_started_ms_ = 0;
    uint32_t state_entered_ms_ = 0;
    uint32_t stable_band_entered_ms_ = 0;
    uint32_t animation_anchor_ms_ = 0;
    uint8_t notify_completed_flashes_ = 0;
    bool initialized_ = false;
};

}  // namespace zss::services
