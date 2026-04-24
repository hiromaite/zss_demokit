#include "services/StatusLedController.h"

#include <Arduino.h>
#include <FastLED.h>

#include <math.h>

#include "board/BoardConfig.h"
#include "protocol/ProtocolConstants.h"

namespace zss::services {

namespace {

constexpr uint8_t kLedCount = 1;
constexpr uint16_t kBootSolidMs = 700;
constexpr float kVoltageLowThresholdV = 0.80f;
constexpr float kVoltageHighThresholdV = 0.92f;
constexpr float kVoltageTargetBandMinV = 0.89f;
constexpr float kVoltageTargetBandMaxV = 0.91f;
constexpr uint32_t kVoltageStableHoldMs = 3000;

CRGB g_leds[kLedCount];

uint8_t clampToByte(float value) {
    if (value <= 0.0f) {
        return 0u;
    }
    if (value >= 255.0f) {
        return 255u;
    }
    return static_cast<uint8_t>(value);
}

}  // namespace

StatusLedController::StatusLedController(int8_t data_pin)
    : data_pin_(data_pin) {}

void StatusLedController::begin() {
    if (data_pin_ != zss::board::kStatusLedDataPin) {
        return;
    }

    if (zss::board::kStatusLedPowerEnablePin >= 0) {
        pinMode(zss::board::kStatusLedPowerEnablePin, OUTPUT);
        digitalWrite(zss::board::kStatusLedPowerEnablePin, HIGH);
        delay(5);
    }

    FastLED.addLeds<WS2812B, zss::board::kStatusLedDataPin, GRB>(g_leds, kLedCount);
    FastLED.setBrightness(zss::board::kStatusLedBrightness);
    showSolidRgb(0, 0, 0);
    boot_started_ms_ = millis();
    state_entered_ms_ = boot_started_ms_;
    animation_anchor_ms_ = boot_started_ms_;
    initialized_ = true;
}

void StatusLedController::setContext(const StatusLedContext& context) {
    context_ = context;
}

void StatusLedController::tick(uint32_t now_ms) {
    if (!initialized_) {
        return;
    }

    const auto next_state = selectState(now_ms);
    applyStateTransition(next_state, now_ms);
    renderState(now_ms);
    FastLED.show();
}

void StatusLedController::applyStateTransition(LedState next_state, uint32_t now_ms) {
    if (next_state == current_state_) {
        return;
    }

    current_state_ = next_state;
    state_entered_ms_ = now_ms;
    animation_anchor_ms_ = now_ms;
    notify_completed_flashes_ = 0;
}

StatusLedController::LedState StatusLedController::selectState(uint32_t now_ms) const {
    if (now_ms - boot_started_ms_ < kBootSolidMs) {
        return LedState::Boot;
    }

    const bool adc_fault =
        (context_.status_flags & zss::protocol::kStatusFlagAdcFaultMask) != 0u ||
        (context_.status_flags & zss::protocol::kStatusFlagSensorFaultMask) != 0u;
    if (adc_fault) {
        return LedState::Error;
    }

    const bool overrun =
        (context_.status_flags & zss::protocol::kStatusFlagSamplingOverrunMask) != 0u ||
        (context_.status_flags & zss::protocol::kStatusFlagTelemetryRateWarningMask) != 0u;
    if (overrun) {
        return LedState::SamplingOverrun;
    }

    if (context_.recording_active) {
        return LedState::RecordingActive;
    }

    if (context_.measurement_ready && isfinite(context_.zirconia_ip_voltage_v)) {
        const float vip = context_.zirconia_ip_voltage_v;
        if (vip < kVoltageLowThresholdV) {
            return LedState::VoltageLow;
        }
        if (vip > kVoltageHighThresholdV) {
            return LedState::VoltageHigh;
        }
        if (isVoltageTargetBand(vip) &&
            stable_band_entered_ms_ != 0 &&
            now_ms - stable_band_entered_ms_ >= kVoltageStableHoldMs) {
            if (current_state_ == LedState::VoltageTargetNotify &&
                notify_completed_flashes_ < 3u) {
                return LedState::VoltageTargetNotify;
            }
            if (current_state_ != LedState::VoltageTargetStable &&
                current_state_ != LedState::VoltageTargetNotify) {
                return LedState::VoltageTargetNotify;
            }
            return LedState::VoltageTargetStable;
        }
        return LedState::VoltageGradient;
    }

    if (context_.ble_connected) {
        return LedState::BleConnected;
    }
    if (context_.ble_ready) {
        return LedState::BleAdvertising;
    }
    return LedState::Idle;
}

void StatusLedController::renderState(uint32_t now_ms) {
    const bool measurement_in_target_band =
        context_.measurement_ready &&
        isfinite(context_.zirconia_ip_voltage_v) &&
        isVoltageTargetBand(context_.zirconia_ip_voltage_v);

    if (measurement_in_target_band) {
        if (stable_band_entered_ms_ == 0) {
            stable_band_entered_ms_ = now_ms;
        }
    } else {
        stable_band_entered_ms_ = 0;
    }

    switch (current_state_) {
        case LedState::Boot:
            showSolidRgb(255, 255, 255);
            break;
        case LedState::Error:
            showBlinkRgb(now_ms, 255, 0, 0, 500, 500);
            break;
        case LedState::SamplingOverrun:
            showBlinkRgb(now_ms, 160, 0, 255, 200, 200);
            break;
        case LedState::RecordingActive:
            showBreathingRgb(now_ms, 255, 48, 48, 1200);
            break;
        case LedState::VoltageLow:
            showBlinkRgb(now_ms, 255, 255, 0, 500, 500);
            break;
        case LedState::VoltageHigh:
            showBlinkRgb(now_ms, 255, 128, 0, 500, 500);
            break;
        case LedState::VoltageGradient:
            showVoltageGradient(context_.zirconia_ip_voltage_v);
            break;
        case LedState::VoltageTargetNotify:
            if (!renderThreeGreenFlashes(now_ms)) {
                current_state_ = LedState::VoltageTargetStable;
                state_entered_ms_ = now_ms;
                animation_anchor_ms_ = now_ms;
            }
            break;
        case LedState::VoltageTargetStable:
            if (context_.ble_connected) {
                showBreathingRgb(now_ms, 0, 80, 255, 2000);
            } else {
                showTwoShortFlashes(now_ms, 0, 80, 255, 2000);
            }
            break;
        case LedState::BleConnected:
            showBreathingRgb(now_ms, 0, 80, 255, 1800);
            break;
        case LedState::BleAdvertising:
            showTwoShortFlashes(now_ms, 0, 80, 255, 2000);
            break;
        case LedState::Idle:
        default:
            showSolidRgb(0, 0, 0);
            break;
    }
}

void StatusLedController::showSolidRgb(uint8_t red, uint8_t green, uint8_t blue) {
    g_leds[0] = CRGB(red, green, blue);
}

void StatusLedController::showBlinkRgb(
    uint32_t now_ms,
    uint8_t red,
    uint8_t green,
    uint8_t blue,
    uint16_t on_ms,
    uint16_t off_ms) {
    const uint32_t phase_ms = (now_ms - animation_anchor_ms_) % (on_ms + off_ms);
    if (phase_ms < on_ms) {
        showSolidRgb(red, green, blue);
    } else {
        showSolidRgb(0, 0, 0);
    }
}

void StatusLedController::showVoltageGradient(float zirconia_ip_voltage_v) {
    uint8_t hue = 42u;
    if (zirconia_ip_voltage_v <= kVoltageTargetBandMinV) {
        hue = static_cast<uint8_t>(
            map(static_cast<long>(zirconia_ip_voltage_v * 1000.0f), 800L, 890L, 42L, 85L));
    } else {
        hue = static_cast<uint8_t>(
            map(static_cast<long>(zirconia_ip_voltage_v * 1000.0f), 890L, 920L, 85L, 21L));
    }
    g_leds[0] = CHSV(hue, 255, 255);
}

void StatusLedController::showTwoShortFlashes(
    uint32_t now_ms,
    uint8_t red,
    uint8_t green,
    uint8_t blue,
    uint16_t cycle_ms) {
    const uint32_t phase_ms = (now_ms - animation_anchor_ms_) % cycle_ms;
    const bool active =
        phase_ms < 100u ||
        (phase_ms >= 200u && phase_ms < 300u);
    if (active) {
        showSolidRgb(red, green, blue);
    } else {
        showSolidRgb(0, 0, 0);
    }
}

void StatusLedController::showBreathingRgb(
    uint32_t now_ms,
    uint8_t red,
    uint8_t green,
    uint8_t blue,
    uint16_t cycle_ms) {
    constexpr float kPi = 3.1415926535f;
    const uint32_t phase_ms = (now_ms - animation_anchor_ms_) % cycle_ms;
    const float phase = static_cast<float>(phase_ms) * (kPi / static_cast<float>(cycle_ms));
    const float scale = (sinf(phase) * 0.5f) + 0.5f;
    showSolidRgb(
        clampToByte(scale * static_cast<float>(red)),
        clampToByte(scale * static_cast<float>(green)),
        clampToByte(scale * static_cast<float>(blue)));
}

bool StatusLedController::renderThreeGreenFlashes(uint32_t now_ms) {
    const uint32_t phase_ms = now_ms - animation_anchor_ms_;
    const uint32_t window_ms = phase_ms % 300u;
    const bool light_on = window_ms < 150u;
    if (!light_on && window_ms >= 150u && window_ms < 300u) {
        const uint8_t completed = static_cast<uint8_t>(phase_ms / 300u);
        notify_completed_flashes_ = completed > 3u ? 3u : completed;
    }

    if (notify_completed_flashes_ >= 3u) {
        showSolidRgb(0, 0, 0);
        return false;
    }

    if (light_on) {
        showSolidRgb(0, 255, 0);
    } else {
        showSolidRgb(0, 0, 0);
    }
    return true;
}

bool StatusLedController::isVoltageTargetBand(float zirconia_ip_voltage_v) const {
    return zirconia_ip_voltage_v >= kVoltageTargetBandMinV &&
           zirconia_ip_voltage_v <= kVoltageTargetBandMaxV;
}

}  // namespace zss::services
