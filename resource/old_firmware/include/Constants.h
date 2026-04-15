#pragma once
#include <string>

// ピン定義
#define LED_PIN 21      // RGB LEDのピン
#define NUM_LEDS 1      // RGB LEDの数
#define INPUT_PIN 5     // 内部ADC入力ピン
#define FLOW_SENSOR_PIN 1 // Flow Sensor ADC input pin
#define ZSS_2CELL_PIN 3   // 2-Cell ZSS ADC input pin
#define OUTPUT_PIN 7    // ポンプ制御用出力ピン
#define I2C_SDA 13     // I2C SDAピン
#define I2C_SCL 15     // I2C SCLピン

// 時間関連の定数
#define UPDATE_INTERVAL_MS 50     // センサー更新間隔（ミリ秒）
#define PROCESSING_TIME_WARNING_MS 40 // 処理遅延の警告を出す閾値（ミリ秒）
#define STATUS_LED_UPDATE_INTERVAL_MS 50  // ステータスLED更新間隔（ミリ秒）
#define BLE_NOTIFY_INTERVAL_MS 1000 // BLE通知間隔（ミリ秒）

// ADC関連の定数
#define VOLTAGE_DIVIDER_RATIO 4.0  // 分圧比（4:1）
#define VOLTAGE_FORMAT "%.2f"      // 電圧表示フォーマット
#define MAX_RETRIES 3             // 再試行回数
#define INTERNAL_ADC_OVERSAMPLING_COUNT 16 // 内部ADCのオーバーサンプリング回数

// RTD抵抗値計算用定数
#define R_SERIES_RTD 11000.0f     // RTDと直列の抵抗値 (Ω)
#define V_SOURCE_RTD 5.0f         // RTD分圧回路の電源電圧 (V)

// BLE関連の定数
#define DEVICE_NAME "M5STAMP-MONITOR"
#define BLE_MANUFACTURER "M5STACK"

// BLEサービスとキャラクタリスティックのUUID
// Control Service: デバイス制御用
#define CONTROL_SERVICE_UUID        "0000180F-0000-1000-8000-00805F9B34FB"
#define PUMP_CONTROL_CHARACTERISTIC_UUID "00002A19-0000-1000-8000-00805F9B34FB" // ポンプ制御特性

// Monitoring Service: 電圧モニタリング用
#define MONITORING_SERVICE_UUID     "0000181A-0000-1000-8000-00805F9B34FB"
#define SENSOR_DATA_CHARACTERISTIC_UUID "00002A58-0000-1000-8000-00805F9B34FB" // センサーデータ特性

// エラーコード
enum class DeviceError {
    NONE = 0,
    INIT_FAILED,
    READ_ERROR,
    TIMEOUT,
    BLE_ERROR
};

// システム状態フラグ
enum SystemStateFlags : uint32_t {
    STATE_NONE            = 0,
    STATE_PUMP_ON         = (1 << 0), // ポンプが作動中
    STATE_BLE_CONNECTED   = (1 << 1), // BLEがクライアントと接続中
    STATE_FAULT_ADC       = (1 << 2), // 外部ADCとの通信に異常
    STATE_PROCESSING_OVERRUN = (1 << 3), // 処理時間が閾値を超過
};