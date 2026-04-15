#include "PumpManager.h"
#include "Logger.h"

PumpManager::PumpManager(uint8_t outputPin)
    : _outputPin(outputPin), _isOn(false) {
}

void PumpManager::begin() {
    pinMode(_outputPin, OUTPUT);
    digitalWrite(_outputPin, LOW);
    _isOn = false;
}

void PumpManager::start() {
    digitalWrite(_outputPin, HIGH);
    _isOn = true;
}

void PumpManager::stop() {
    digitalWrite(_outputPin, LOW);
    _isOn = false;
}

bool PumpManager::isOn() const {
    return _isOn;
}