#pragma once

#include <M5Unified.h>

class PumpManager {
public:
    PumpManager(uint8_t outputPin);
    void begin();
    void start();
    void stop();
    bool isOn() const;

private:
    uint8_t _outputPin;
    bool _isOn;
};
