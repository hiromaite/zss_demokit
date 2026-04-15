#include "StatusLED.h"
#include <math.h>

StatusLED::StatusLED() : currentState(LEDState::INITIALIZING), gHue(0),
    _lastUpdateTime(0), _lastFlashTime(0), _flashCount(0),
    _isVoltageStable(false), _isNotifyingTarget(false),
    _currentVipVoltage(0.0f), _bleConnected(false), _adcFault(false), _processingOverrun(false), _timeEnteredStableRange(0) {
}

void StatusLED::begin() {
    FastLED.addLeds<WS2812B, LED_PIN, GRB>(leds, NUM_LEDS);
    FastLED.setBrightness(50);
}

void StatusLED::setData(bool bleConnected, bool adcFault, bool processingOverrun, float vipVoltage) {
    _bleConnected = bleConnected;
    _adcFault = adcFault;
    _processingOverrun = processingOverrun;
    if (!isnan(vipVoltage)) {
        _currentVipVoltage = vipVoltage;
    }

    unsigned long currentTime = millis();
    LEDState nextState = currentState;

    // --- Handle stable range timing ---
    bool isCurrentlyInRange = (!isnan(vipVoltage) && vipVoltage >= 0.89f && vipVoltage <= 0.91f);

    if (isCurrentlyInRange) {
        if (_timeEnteredStableRange == 0) {
            _timeEnteredStableRange = currentTime;
        }
    }
    else {
        _timeEnteredStableRange = 0;
        _isVoltageStable = false;
    }

    // --- P1: Hard Error (Highest Priority) ---
    if (_adcFault) {
        nextState = LEDState::ERROR;
    }
    // --- P2: Processing Overrun ---
    else if (_processingOverrun) {
        nextState = LEDState::PROCESSING_OVERRUN;
    }
    // --- P3: Voltage-based states ---
    else if (!isnan(vipVoltage)) {
        if (isCurrentlyInRange && !_isVoltageStable && _timeEnteredStableRange != 0 && (currentTime - _timeEnteredStableRange >= 3000)) {
            nextState = LEDState::VOLTAGE_TARGET_NOTIFY;
        } else if (_isVoltageStable) {
            nextState = LEDState::VOLTAGE_TARGET_STABLE;
        } else if (vipVoltage <= 0.8f) {
            nextState = LEDState::VOLTAGE_LOW;
        } else if (vipVoltage >= 0.92f) {
            nextState = LEDState::VOLTAGE_HIGH;
        } else {
            nextState = LEDState::VOLTAGE_GRADIENT;
        }
    }

    // --- State Transition Logic ---
    if (nextState != currentState) {
        currentState = nextState;
        _lastFlashTime = 0;
        _flashCount = 0;
        _isNotifyingTarget = false;
    }
}

void StatusLED::update() {
    unsigned long currentTime = millis();

    // --- Display Logic for each state ---
    switch (currentState) {
        case LEDState::INITIALIZING:
            _displaySolidColor(CRGB::White);
            break;
        case LEDState::ERROR:
            _displayBlinkingColor(CRGB::Red, 500, 500);
            break;
        case LEDState::PROCESSING_OVERRUN:
            _displayBlinkingColor(CRGB::Purple, 200, 200);
            break;
        case LEDState::VOLTAGE_LOW:
            _displayBlinkingColor(CRGB::Yellow, 500, 500);
            break;
        case LEDState::VOLTAGE_HIGH:
            _displayBlinkingColor(CRGB::Orange, 500, 500);
            break;
        case LEDState::VOLTAGE_GRADIENT:
            _displayVoltageGradient(_currentVipVoltage);
            break;
        case LEDState::VOLTAGE_TARGET_NOTIFY:
            if (!_displayThreeGreenFlashes()) {
                currentState = LEDState::VOLTAGE_TARGET_STABLE;
                _isVoltageStable = true;
            }
            break;
        case LEDState::VOLTAGE_TARGET_STABLE:
            if (_bleConnected) {
                _displayBreathingColor(CRGB::Blue, 2000);
            } else {
                _displayTwoShortFlashes(CRGB::Blue, 2000);
            }
            break;
        default:
            _displaySolidColor(CRGB::Black);
            break;
    }

    FastLED.show();
    _lastUpdateTime = currentTime;
}

// Helper function to display a solid color
void StatusLED::_displaySolidColor(CRGB color) {
    leds[0] = color;
}

// Helper function for blinking color
void StatusLED::_displayBlinkingColor(CRGB color, unsigned long onTime, unsigned long offTime) {
    unsigned long currentTime = millis();
    if (currentTime - _lastFlashTime >= (leds[0] == CRGB::Black ? offTime : onTime)) {
        _lastFlashTime = currentTime;
        leds[0] = (leds[0] == CRGB::Black) ? color : CRGB::Black;
    }
}

// Helper function for voltage gradient
void StatusLED::_displayVoltageGradient(float vipVoltage) {
    // Map Vip voltage (0.8V to 0.92V) to hue (Yellow to Orange, Green at 0.9V)
    // Range: 0.8V (Yellow) --- 0.89V (Yellow-Green) --- 0.9V (Green) --- 0.91V (Green-Orange) --- 0.92V (Orange)
    // Hue mapping: Yellow (42) -> Green (85) -> Orange (21)
    // This is a simplified mapping, can be refined.
    uint8_t hue;
    if (vipVoltage <= 0.89f) { // Yellow to Green
        // Map 0.8f-0.89f to Hue 42-85
        hue = map(vipVoltage * 1000, 800, 890, 42, 85);
    } else { // Green to Orange
        // Map 0.89f-0.92f to Hue 85-21 (decreasing hue) - Note: FastLED hue wraps around
        hue = map(vipVoltage * 1000, 890, 920, 85, 21);
    }
    leds[0] = CHSV(hue, 255, 255);
}

// Helper function for two short flashes (e.g., BLE advertising)
void StatusLED::_displayTwoShortFlashes(CRGB color, unsigned long cycleTime) {
    unsigned long currentTime = millis();
    unsigned long elapsed = currentTime - _lastFlashTime;

    if (elapsed < 100) { // First flash ON
        leds[0] = color;
    } else if (elapsed < 200) { // First flash OFF
        leds[0] = CRGB::Black;
    } else if (elapsed < 300) { // Second flash ON
        leds[0] = color;
    } else if (elapsed < 400) { // Second flash OFF
        leds[0] = CRGB::Black;
    } else if (elapsed >= cycleTime) { // Reset cycle
        _lastFlashTime = currentTime;
    } else { // Stay off for the rest of the cycle
        leds[0] = CRGB::Black;
    }
}

// Helper function for breathing color (e.g., BLE connected)
void StatusLED::_displayBreathingColor(CRGB color, unsigned long cycleTime) {
    unsigned long currentTime = millis();
    unsigned long elapsed = currentTime - _lastFlashTime;
    if (elapsed >= cycleTime) {
        _lastFlashTime = currentTime;
        elapsed = 0;
    }

    // Calculate brightness using a sine wave for breathing effect
    // Note: PI is not defined by default in Arduino, need to include <math.h> or define it.
    // For now, using a constant approximation.
    float PI_APPROX = 3.1415926535f;
    uint8_t brightness = (sin(elapsed * (PI_APPROX / cycleTime)) * 127) + 128;
    leds[0] = color;
    leds[0].nscale8(brightness);
}

// Helper function for three green flashes (target achieved notification)
// Returns true if animation is running, false if finished.
bool StatusLED::_displayThreeGreenFlashes() {
    unsigned long currentTime = millis();
    if (!_isNotifyingTarget) { // Start notification
        _isNotifyingTarget = true;
        _flashCount = 0;
        _lastFlashTime = currentTime;
        leds[0] = CRGB::Green; // Start with first flash
        return true;
    }

    if (_flashCount < 3) {
        if (currentTime - _lastFlashTime >= 150) { // 150ms on, 150ms off
            _lastFlashTime = currentTime;
            if (leds[0] == CRGB::Green) {
                leds[0] = CRGB::Black;
                _flashCount++;
            } else {
                leds[0] = CRGB::Green;
            }
        }
        return true; // Animation is running
    }
    
    // Animation finished
    _isNotifyingTarget = false;
    leds[0] = CRGB::Black;
    return false;
}
