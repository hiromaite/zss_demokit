#include "ADCManager.h"
#include "Logger.h"

ADCManager::ADCManager(uint8_t internalPin, uint8_t flowSensorPin, uint8_t zss2CellPin)
    : _internalADCPin(internalPin), _flowSensorPin(flowSensorPin), _zss2CellPin(zss2CellPin), _externalADCAvailable(false) {
    _lastErrorMsg[0] = '\0';
}

bool ADCManager::begin() {
    if (!_ads.begin()) {
        setError("ADS1115 initialization failed");
        _externalADCAvailable = false;
        return false;
    }
    
    _ads.setGain(GAIN_ONE);
    _ads.setDataRate(RATE_ADS1115_860SPS); // Set data rate to 860SPS
    _externalADCAvailable = true;
    return true;
}

float ADCManager::readInternalVoltage() {
    long sum_voltage_mV = 0;
    for (int i = 0; i < INTERNAL_ADC_OVERSAMPLING_COUNT; ++i) {
        sum_voltage_mV += analogReadMilliVolts(_internalADCPin);
        // delay(1); // Removed to improve performance
    }
    float raw_voltage = (sum_voltage_mV / (float)INTERNAL_ADC_OVERSAMPLING_COUNT) / 1000.0f;
    return convertToActualVoltage(raw_voltage);
}

float ADCManager::readADS1115Channel(uint8_t channel) {
    if (!_externalADCAvailable) {
        setError("External ADC not initialized");
        return NAN;
    }
    
    for (int retry = 0; retry < MAX_RETRIES; retry++) {
        int16_t ads_raw = _ads.readADC_SingleEnded(channel);
        if (ads_raw != -1) {
            return _ads.computeVolts(ads_raw);
        }
        delay(10);
    }
    
    setError("Failed to read from external ADC");
    _externalADCAvailable = false;
    return NAN;
}

float ADCManager::readZirconiaIpVoltage() {
    float raw_voltage = readADS1115Channel(0);
    if (isnan(raw_voltage)) return NAN;
    return raw_voltage;
}

float ADCManager::readHeaterRtdResistance() {
    float measured_voltage = readADS1115Channel(1);
    if (isnan(measured_voltage)) return NAN;
    if (V_SOURCE_RTD - measured_voltage == 0) return NAN;
    return (measured_voltage * R_SERIES_RTD) / (V_SOURCE_RTD - measured_voltage);
}

float ADCManager::readZirconiaOutputVoltage() {
    float raw_voltage = readADS1115Channel(2);
    if (isnan(raw_voltage)) return NAN;
    return raw_voltage;
}

float ADCManager::readFlowSensorVoltage() {
    long sum_voltage_mV = 0;
    for (int i = 0; i < INTERNAL_ADC_OVERSAMPLING_COUNT; ++i) {
        sum_voltage_mV += analogReadMilliVolts(_flowSensorPin);
    }
    float raw_voltage = (sum_voltage_mV / (float)INTERNAL_ADC_OVERSAMPLING_COUNT) / 1000.0f;
    return convertToActualVoltage(raw_voltage);
}

float ADCManager::readZss2CellValue() {
    long sum_voltage_mV = 0;
    for (int i = 0; i < INTERNAL_ADC_OVERSAMPLING_COUNT; ++i) {
        sum_voltage_mV += analogReadMilliVolts(_zss2CellPin);
    }
    float raw_voltage = (sum_voltage_mV / (float)INTERNAL_ADC_OVERSAMPLING_COUNT) / 1000.0f;
    return convertToActualVoltage(raw_voltage);
}

void ADCManager::setError(const char* msg) {
    strncpy(_lastErrorMsg, msg, sizeof(_lastErrorMsg) - 1);
    _lastErrorMsg[sizeof(_lastErrorMsg) - 1] = '\0';
    Logger::log(LogLevel::ERROR, "ADC", msg);
}

float ADCManager::convertToActualVoltage(float measured_voltage) const {
    return measured_voltage * VOLTAGE_DIVIDER_RATIO;
}