#pragma once

#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include "Constants.h"

struct SensorData {
    float internalVoltage;
    float zirconiaIpVoltage;
    float heaterRtdResistance;
    float zirconiaOutputVoltage;
    uint32_t systemState;
    uint32_t updateInterval; // ファームウェアが意図する更新間隔(ms)
    float flowSensorVoltage; // Flow Sensor Voltage
    float zss2CellValue;     // 2-Cell ZSS Value
    SensorData() : internalVoltage(0), zirconiaIpVoltage(0), heaterRtdResistance(0), zirconiaOutputVoltage(0), systemState(0), updateInterval(0), flowSensorVoltage(0), zss2CellValue(0) {}
};

class BLEManager; // BLECallback内でポインタとして使用するため前方宣言

// BLEコールバッククラスの定義
class BLECallback : public BLEServerCallbacks, public BLECharacteristicCallbacks {
private:
    BLEManager* _manager;

public:
    BLECallback(BLEManager* manager) : _manager(manager) {}

    void onConnect(BLEServer* pServer) override;
    void onDisconnect(BLEServer* pServer) override;
    void onWrite(BLECharacteristic* pCharacteristic) override;
};

class BLEManager {
public:
    using PumpControlCallback = std::function<void(uint8_t)>;
    using ConnectionStatusCallback = std::function<void(bool)>;
    
    BLEManager();
    bool begin();
    void update();
    void setPumpControlCallback(PumpControlCallback callback);
    void setConnectionStatusCallback(ConnectionStatusCallback callback);
    void updateSensorData(const SensorData& data);
    bool isConnected() const;
    const char* getLastError() const { return lastErrorMsg; }

private:
    BLEServer* server;
    BLEService* controlService;
    BLEService* monitoringService;
    BLECharacteristic* toggleCharacteristic;
    BLECharacteristic* voltageCharacteristic;
    BLECallback* bleCallback;
    PumpControlCallback onPumpControl;
    ConnectionStatusCallback onConnectionStatus;
    bool deviceConnected;
    uint32_t lastNotify;
    uint32_t lastWriteTime;  // 追加: 最後のWrite操作の時刻
    char lastErrorMsg[64];
    
    void setError(const char* msg);
    friend class BLECallback;
};