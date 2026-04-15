#pragma once

#include <M5Unified.h>
#include <FastLED.h>
#include "Constants.h"

// LEDの表示状態を定義
enum class LEDState {
    INITIALIZING,
    RAINBOW,
    ERROR,
    BLE_ADVERTISING,
    BLE_CONNECTED,
    VOLTAGE_LOW,
    VOLTAGE_HIGH,
    VOLTAGE_GRADIENT,
    VOLTAGE_TARGET_NOTIFY,
    VOLTAGE_TARGET_STABLE,
    PROCESSING_OVERRUN,
};

class StatusLED {
public:
    StatusLED();
    void begin();
    void setData(bool bleConnected, bool adcFault, bool processingOverrun, float vipVoltage);
    void update();

private:
    CRGB leds[NUM_LEDS];
    LEDState currentState;
    uint8_t gHue;
    unsigned long _lastUpdateTime;
    unsigned long _lastFlashTime;
    uint8_t _flashCount;
    bool _isVoltageStable;
    bool _isNotifyingTarget;
    float _currentVipVoltage;
    bool _bleConnected;
    bool _adcFault;
    bool _processingOverrun;
    unsigned long _timeEnteredStableRange;

    void _displaySolidColor(CRGB color);
    void _displayBlinkingColor(CRGB color, unsigned long onTime, unsigned long offTime);
    void _displayVoltageGradient(float vipVoltage);
    void _displayTwoShortFlashes(CRGB color, unsigned long cycleTime);
    void _displayBreathingColor(CRGB color, unsigned long cycleTime);
    bool _displayThreeGreenFlashes();
};
