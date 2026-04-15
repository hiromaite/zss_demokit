#include "BLEManager.h"
#include <BLE2902.h>
#include "Logger.h"

// 比較用のUUIDオブジェクトを静的に定義
static BLEUUID pumpControlUUID(PUMP_CONTROL_CHARACTERISTIC_UUID);

// --- BLECallback Method Implementations ---
void BLECallback::onConnect(BLEServer* pServer) {
    _manager->deviceConnected = true;
    if (_manager->onConnectionStatus) {
        _manager->onConnectionStatus(true);
    }
    Logger::log(LogLevel::INFO, "BLE", "Client connected");
}

void BLECallback::onDisconnect(BLEServer* pServer) {
    _manager->deviceConnected = false;
    if (_manager->onConnectionStatus) {
        _manager->onConnectionStatus(false);
    }
    Logger::log(LogLevel::INFO, "BLE", "Client disconnected, restarting advertising...");
    pServer->startAdvertising();
}

void BLECallback::onWrite(BLECharacteristic* pCharacteristic) {
    if (!pCharacteristic->getUUID().equals(pumpControlUUID)) {
        return;
    }

    uint8_t* value = pCharacteristic->getData();
    size_t length = pCharacteristic->getLength();

    if (value && length > 0 && _manager->onPumpControl) {
        // ここはBLEタスク内で実行されるため、スタックオーバーフローを避けるためM5.Logを直接使用
        M5.Log.printf("BLE: Pump control write: 0x%02X\n", value[0]);
        _manager->onPumpControl(value[0]);
    }
}

// --- BLEManager Method Implementations ---
BLEManager::BLEManager() 
    : server(nullptr), controlService(nullptr), monitoringService(nullptr),
      toggleCharacteristic(nullptr), voltageCharacteristic(nullptr),
      bleCallback(nullptr), deviceConnected(false), lastNotify(0) {
    lastErrorMsg[0] = '\0';
}

bool BLEManager::begin() {
    Logger::log(LogLevel::INFO, "BLE", "Initializing...");
    
    BLEDevice::init(DEVICE_NAME);
    server = BLEDevice::createServer();
    if (!server) {
        setError("Failed to create BLE server");
        return false;
    }
    
    bleCallback = new BLECallback(this);
    server->setCallbacks(bleCallback);
    
    controlService = server->createService(CONTROL_SERVICE_UUID);
    if (!controlService) {
        setError("Failed to create Control service");
        return false;
    }
    
    toggleCharacteristic = controlService->createCharacteristic(
        PUMP_CONTROL_CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    toggleCharacteristic->setCallbacks(bleCallback);
    
    monitoringService = server->createService(MONITORING_SERVICE_UUID);
    if (!monitoringService) {
        setError("Failed to create Monitoring service");
        return false;
    }
    
    voltageCharacteristic = monitoringService->createCharacteristic(
        SENSOR_DATA_CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_NOTIFY
    );
    voltageCharacteristic->addDescriptor(new BLE2902());
    
    controlService->start();
    monitoringService->start();
    
    BLEAdvertising* advertising = server->getAdvertising();
    advertising->addServiceUUID(CONTROL_SERVICE_UUID);
    advertising->addServiceUUID(MONITORING_SERVICE_UUID);
    advertising->start();
    
    return true;
}

void BLEManager::update() {}

void BLEManager::setPumpControlCallback(PumpControlCallback callback) {
    onPumpControl = callback;
}

void BLEManager::setConnectionStatusCallback(ConnectionStatusCallback callback) {
    onConnectionStatus = callback;
}

void BLEManager::updateSensorData(const SensorData& data) {
    if (deviceConnected && voltageCharacteristic) {
        uint8_t packet[32]; // Expanded packet size to 32 bytes
        memcpy(packet, &data.internalVoltage, 4);
        memcpy(packet + 4, &data.zirconiaIpVoltage, 4);
        memcpy(packet + 8, &data.heaterRtdResistance, 4);
        memcpy(packet + 12, &data.zirconiaOutputVoltage, 4);
        memcpy(packet + 16, &data.systemState, 4);
        memcpy(packet + 20, &data.updateInterval, 4);
        memcpy(packet + 24, &data.flowSensorVoltage, 4);
        memcpy(packet + 28, &data.zss2CellValue, 4);

        voltageCharacteristic->setValue(packet, sizeof(packet));
        voltageCharacteristic->notify();
    }
}

bool BLEManager::isConnected() const {
    return deviceConnected;
}

void BLEManager::setError(const char* msg) {
    strncpy(lastErrorMsg, msg, sizeof(lastErrorMsg) - 1);
    lastErrorMsg[sizeof(lastErrorMsg) - 1] = '\0';
}
