#pragma once

#include <Arduino.h>
#include <Adafruit_ADS1X15.h>
#include "Constants.h"

class ADCManager {
public:
    ADCManager(uint8_t internalPin, uint8_t gpio1Pin, uint8_t gpio3Pin);
    bool begin();
    float readInternalVoltage();
    float readZirconiaIpVoltage();
    float readHeaterRtdResistance();
    float readZirconiaOutputVoltage();
    float readFlowSensorVoltage();
    float readZss2CellValue();
    bool isExternalADCAvailable() const { return _externalADCAvailable; }
    const char* getLastError() const { return _lastErrorMsg; }

private:
    Adafruit_ADS1115 _ads;
    uint8_t _internalADCPin;
    uint8_t _flowSensorPin;
    uint8_t _zss2CellPin;
    char _lastErrorMsg[64];
    bool _externalADCAvailable;
    
    void setError(const char* msg);
    float convertToActualVoltage(float measured_voltage) const;
    float readADS1115Channel(uint8_t channel);
};