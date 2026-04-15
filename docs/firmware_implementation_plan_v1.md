# Firmware Implementation Plan v1

## 1. 目的

本書は、新 firmware を top-level PlatformIO project 上で実装するための
モジュール分割案と実装順の詳細をまとめる。

前提:

- board target は `m5stack-stamps3`
- framework は Arduino
- BLE / wired は同一 measurement core を共有する
- v1 では通信安定性を最優先とする

## 2. 現状

- top-level `src/main.cpp` はまだ PlatformIO 雛形
- 実用ロジックは `resource/old_firmware/` に残っている
- old_firmware は 1 ループ集中で、周期管理が `last = now` 型になっている

## 3. 設計原則

- measurement, command handling, transport を分離する
- protocol payload の組み立ては transport 実装から切り離す
- sampling scheduler は deadline-based にする
- BLE と wired は transport 層のみ差し替える
- board-specific pin / peripheral 設定は 1 箇所に集約する

## 4. 推奨ソース構成

```text
include/
  app/
    AppState.h
    CommandProcessor.h
    CapabilityBuilder.h
    StatusFlags.h
  board/
    BoardConfig.h
  measurement/
    MeasurementCore.h
    SensorData.h
    AdcFrontend.h
  services/
    PumpController.h
    StatusLedController.h
    Logger.h
  transport/
    BleTransport.h
    SerialTransport.h
    TransportTypes.h
  protocol/
    ProtocolConstants.h
    PayloadBuilders.h

src/
  main.cpp
  app/
    AppState.cpp
    CommandProcessor.cpp
    CapabilityBuilder.cpp
  measurement/
    MeasurementCore.cpp
    AdcFrontend.cpp
  services/
    PumpController.cpp
    StatusLedController.cpp
    Logger.cpp
  transport/
    BleTransport.cpp
    SerialTransport.cpp
  protocol/
    PayloadBuilders.cpp
```

補足:

- `ADCManager` 相当の実装は `measurement/` に寄せる
- `PumpManager`, `StatusLED`, `Logger` は `services/` に寄せる
- `BLEManager` の責務は `transport/BleTransport.*` と `protocol/PayloadBuilders.*` に分割する

## 5. ランタイムモデル

### 5.1 setup

1. board config initialize
2. logger initialize
3. pump initialize
4. ADC / sensor frontend initialize
5. app state initialize
6. transport initialize
7. status LED initialize

### 5.2 main loop

推奨順:

1. pump / button / local input service
2. BLE transport service
3. serial transport service
4. command queue service
5. measurement scheduler check
6. if due:
   - acquire measurements
   - update app state
   - build telemetry snapshot
   - publish telemetry to enabled transports
7. status LED service
8. low-rate diagnostics / log flush

### 5.3 Scheduling Rule

- `next_sample_deadline_ms += nominal_period_ms` を基本とする
- `now_ms > next_sample_deadline_ms + tolerance_ms` を overrun とみなす
- overrun は status flag と event に反映する
- sample publish は measurement 完了後に行う

## 6. App State の責務

`AppState` が保持するもの:

- pump state
- transport connection state
- latest measurements
- latest status flags
- sequence counter
- nominal sample period
- diagnostics counters
- firmware version

`AppState` が保持しないもの:

- transport-specific handle
- raw receive buffer
- GUI-derived value

## 7. Command Processor の責務

入力:

- logical command id
- optional argument
- source transport

処理対象:

- `get_capabilities`
- `get_status`
- `set_pump_state`
- `ping`

出力:

- command result
- optional response payload trigger
- event generation

## 8. Measurement Core の責務

`MeasurementCore` は以下を担当する。

- ADC read sequence
- sensor fault detection
- measurement normalization
- latest measurement caching

入力:

- board services
- sample period configuration

出力:

- canonical measurements
- fault / warning signals

## 9. Transport Layer の責務

### 9.1 `BleTransport`

- advertise
- service / characteristic setup
- notify dispatch
- command write decode
- connection state callback

### 9.2 `SerialTransport`

- serial port read / write
- frame assembly
- CRC check
- request dispatch
- response / telemetry encode

## 10. Payload Builder の責務

`PayloadBuilders` は以下を担当する。

- telemetry packet build
- status snapshot build
- capabilities payload build
- event payload build
- wired ack / error payload build

方針:

- transport は payload builder の戻り値をそのまま搬送する
- float / integer packing の規則はここに集約する

## 11. old_firmware からの移植方針

### 11.1 再利用候補

- sensor read 手順
- pump drive 手順
- state flag の意味
- status LED の基本挙動

### 11.2 そのまま持ち込まないもの

- main loop 一極集中の責務配置
- `lastADCUpdate = millis()` 型の周期管理
- BLE 専用に埋め込まれた payload 組み立て

## 12. 実装順

1. `BoardConfig`, `Logger`, `PumpController`
2. `AdcFrontend`, `MeasurementCore`
3. `AppState`, `StatusFlags`, `CapabilityBuilder`
4. `CommandProcessor`
5. `PayloadBuilders`
6. `SerialTransport`
7. `BleTransport`
8. `StatusLedController`
9. sample-period diagnostics

## 13. 最低限の実機確認項目

- boot して fault なく初期化できる
- pump on / off がローカルでも remote command でも動く
- ADC read が連続取得できる
- wired で capabilities / status / telemetry を返せる
- BLE で telemetry notify を返せる
- sequence が単調増加する
- overrun を観測・表示できる

## 14. 未確定事項

- wired 側の transport 実装を USB CDC 前提にするか、UART bridge も考慮するか
- BLE extension service UUID の最終値
- sampling jitter の許容範囲
