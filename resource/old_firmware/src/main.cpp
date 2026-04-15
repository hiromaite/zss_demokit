#include <Arduino.h>
#include <M5Unified.h>
#include "PumpManager.h"
#include "ADCManager.h"
#include "BLEManager.h"
#include "StatusLED.h"
#include "Constants.h"
#include "Logger.h"
#include <Wire.h>

// --- グローバル変数 ---
uint32_t g_system_state = STATE_NONE;
volatile bool g_button_pressed_flag = false;
volatile unsigned long g_last_interrupt_time = 0;
volatile uint8_t g_pump_command = 0;

// --- デバイスのインスタンス化 ---
PumpManager pump(OUTPUT_PIN);
ADCManager adc(INPUT_PIN, FLOW_SENSOR_PIN, ZSS_2CELL_PIN);
BLEManager ble;
StatusLED statusLed;

// --- 割り込み処理関数 (ISR) ---
void IRAM_ATTR handle_button_interrupt() {
    unsigned long interrupt_time = millis();
    if (interrupt_time - g_last_interrupt_time > 200) {
        g_button_pressed_flag = true;
        g_last_interrupt_time = interrupt_time;
    }
}

// --- BLEコールバック関数 ---
void handlePumpControl(uint8_t command) {
    if (command == 0x55 || command == 0xAA) {
        g_pump_command = command;
    }
}

void handleConnectionStatus(bool connected) {
    if (connected) {
        g_system_state |= STATE_BLE_CONNECTED;
    } else {
        g_system_state &= ~STATE_BLE_CONNECTED;
    }
}

// --- メイン処理 ---
void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);

    pinMode(38, OUTPUT);
    digitalWrite(38, HIGH);

    statusLed.begin();
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(400000); // Set I2C clock to 400kHz
    Wire.setTimeOut(10);
    pump.begin();
    
    if (!adc.begin()) {
        Logger::log(LogLevel::ERROR, "ADC", "Initialization failed: %s", adc.getLastError());
        g_system_state |= STATE_FAULT_ADC;
    }
    
    if (!ble.begin()) {
        Logger::log(LogLevel::ERROR, "BLE", "Initialization failed: %s", ble.getLastError());
    }
    
    statusLed.setData(ble.isConnected(), (g_system_state & STATE_FAULT_ADC), (g_system_state & STATE_PROCESSING_OVERRUN), NAN);

    ble.setPumpControlCallback(handlePumpControl);
    ble.setConnectionStatusCallback(handleConnectionStatus);

    attachInterrupt(digitalPinToInterrupt(0), handle_button_interrupt, FALLING);
    
    Logger::log(LogLevel::INFO, "Main", "Setup complete. Starting monitoring...");
}

void loop() {
    M5.update();
    statusLed.update();
    ble.update();

    // Handle pump control commands from BLE
    if (g_pump_command != 0) {
        if (g_pump_command == 0x55) {
            pump.start();
            g_system_state |= STATE_PUMP_ON;
            Logger::log(LogLevel::INFO, "Main", "Pump started via BLE command.");
        } else if (g_pump_command == 0xAA) {
            pump.stop();
            g_system_state &= ~STATE_PUMP_ON;
            Logger::log(LogLevel::INFO, "Main", "Pump stopped via BLE command.");
        }
        g_pump_command = 0; // Reset the flag
    }

    if (g_button_pressed_flag) {
        g_button_pressed_flag = false;
        Logger::log(LogLevel::INFO, "Main", "Button interrupt processed.");
        if (pump.isOn()) {
            pump.stop();
            g_system_state &= ~STATE_PUMP_ON;
        } else {
            pump.start();
            g_system_state |= STATE_PUMP_ON;
        }
        return;
    }

    static uint32_t lastADCUpdate = 0;
    if (millis() - lastADCUpdate >= UPDATE_INTERVAL_MS) {
        uint32_t startTime = millis(); // 処理時間計測開始

        SensorData sensorData;
        sensorData.updateInterval = UPDATE_INTERVAL_MS; // 更新間隔をセット

        sensorData.internalVoltage = adc.readInternalVoltage();
        sensorData.flowSensorVoltage = adc.readFlowSensorVoltage();
        sensorData.zss2CellValue = adc.readZss2CellValue();

        if (g_system_state & STATE_FAULT_ADC) {
            Logger::log(LogLevel::WARN, "ADC", "External ADC is in FAULT state. Attempting to recover...");
            if (adc.begin()) {
                Logger::log(LogLevel::INFO, "ADC", "External ADC recovered!");
                g_system_state &= ~STATE_FAULT_ADC;
            }
            sensorData.zirconiaIpVoltage = NAN;
            sensorData.heaterRtdResistance = NAN;
            sensorData.zirconiaOutputVoltage = NAN;
        } else {
            sensorData.zirconiaIpVoltage = adc.readZirconiaIpVoltage();
            sensorData.heaterRtdResistance = adc.readHeaterRtdResistance();
            sensorData.zirconiaOutputVoltage = adc.readZirconiaOutputVoltage();

            if (isnan(sensorData.zirconiaIpVoltage) || isnan(sensorData.heaterRtdResistance) || isnan(sensorData.zirconiaOutputVoltage)) {
                Logger::log(LogLevel::ERROR, "ADC", "Read error: %s. Entering FAULT state.", adc.getLastError());
                g_system_state |= STATE_FAULT_ADC;
            } else {
                char log_buf[128];
                snprintf(log_buf, sizeof(log_buf), 
                    "Int:%.2fV, Ip:%.3fV, RTD:%.1fOhm, Vout:%.3fV {State=0x%02X}",
                    sensorData.internalVoltage, sensorData.zirconiaIpVoltage, 
                    sensorData.heaterRtdResistance, sensorData.zirconiaOutputVoltage, g_system_state);
                Logger::log(LogLevel::INFO, "Sensor", log_buf);
            }
        }
        
        sensorData.systemState = g_system_state;
        ble.updateSensorData(sensorData);

        // 処理時間計測とフラグ設定
        uint32_t processingTime = millis() - startTime;
        if (processingTime > PROCESSING_TIME_WARNING_MS) {
            g_system_state |= STATE_PROCESSING_OVERRUN;
        } else {
            g_system_state &= ~STATE_PROCESSING_OVERRUN;
        }

        statusLed.setData(ble.isConnected(), (g_system_state & STATE_FAULT_ADC), (g_system_state & STATE_PROCESSING_OVERRUN), sensorData.zirconiaIpVoltage);
        lastADCUpdate = millis();
    }
}