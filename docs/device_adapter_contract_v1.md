# DeviceAdapter Contract v1

## 1. 目的

本書は、新 GUI における `DeviceAdapter` の責務、公開 API、signals、
threading 境界を固定するための実装契約である。

## 2. 役割

`DeviceAdapter` は transport 差分を吸収し、GUI 上位層へ
transport-independent な domain model を渡す。

責務:

- connect / disconnect の管理
- transport frame の decode
- protocol-specific response の解釈
- `TelemetrySample`, `StatusSnapshot`, `DeviceCapabilities` への正規化
- command の encode / dispatch

責務外:

- plot 描画
- CSV 書き込み
- `flow_rate_lpm` の計算
- mode switch UX

## 3. 共通実装方針

- PySide6 ベースの GUI に合わせ、adapter は `QObject`-style signals を公開する
- transport I/O と frame parsing は UI thread 外で処理する
- adapter は canonical measurements のみを emit する
- adapter は受信直後の `host_received_at` を `TelemetrySample` に付与する
- GUI service は derived metrics のみを付与する

## 4. Connection Parameter Models

### 4.1 BLE

```python
@dataclass
class BleConnectionParams:
    device_identifier: str
    device_address: str | None = None
```

### 4.2 Wired

```python
@dataclass
class SerialConnectionParams:
    port_name: str
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    read_timeout_s: float = 0.10
    write_timeout_s: float = 0.10
```

補足:

- v1 では `baudrate=115200` を default かつ通常 UI では固定とする
- GUI 契約上、wired device は `Windows COM port` として扱う

## 5. Adapter Lifecycle State

```text
disconnected
  -> connecting
  -> connected
  -> disconnecting
  -> disconnected

connected
  -> error
  -> disconnecting
```

方針:

- `open()` は non-blocking に開始し、結果は signal で返す
- `close()` は repeated call に耐える
- adapter は reopen 前に必ず worker を clean shutdown する

## 6. Domain Payloads

### 6.1 DeviceCapabilities

```python
@dataclass
class DeviceCapabilities:
    protocol_version_major: int
    protocol_version_minor: int
    device_type: str
    transport_type: str
    firmware_version: str
    nominal_sample_period_ms: int
    supported_commands: list[str]
    telemetry_fields: list[str]
    status_flag_schema_version: int
    max_payload_bytes: int | None = None
```

### 6.2 StatusSnapshot

```python
@dataclass
class StatusSnapshot:
    sequence: int
    status_flags: int
    zirconia_output_voltage_v: float
    heater_rtd_resistance_ohm: float
    flow_sensor_voltage_v: float
```

### 6.3 TelemetrySample

```python
@dataclass
class TelemetrySample:
    device_type: str
    transport_type: str
    sequence: int
    host_received_at: datetime
    nominal_sample_period_ms: int
    status_flags: int
    zirconia_output_voltage_v: float
    heater_rtd_resistance_ohm: float
    flow_sensor_voltage_v: float
```

### 6.4 DeviceEvent

```python
@dataclass
class DeviceEvent:
    severity: str
    code: str
    message: str
    sequence: int | None = None
    detail_u32: int | None = None
```

### 6.5 CommandResult

```python
@dataclass
class CommandResult:
    command_name: str
    success: bool
    detail: str = ""
```

## 7. Public Signals

```python
class DeviceAdapterBase(QObject):
    connection_state_changed = Signal(object)
    capabilities_received = Signal(object)
    status_snapshot_received = Signal(object)
    telemetry_received = Signal(object)
    event_received = Signal(object)
    command_result_received = Signal(object)
    warning_raised = Signal(object)
    fatal_error = Signal(str)
```

Signal payload policy:

- payload は dataclass instance を基本とする
- high-rate path は `telemetry_received` のみとする
- `warning_raised` は non-fatal issue に使う
- unrecoverable issue は `fatal_error` を使う

## 8. Public Methods

```python
class DeviceAdapter(Protocol):
    def open(self, params: object) -> None: ...
    def close(self) -> None: ...
    def is_connected(self) -> bool: ...
    def request_capabilities(self) -> None: ...
    def request_status(self) -> None: ...
    def set_pump_state(self, on: bool) -> None: ...
    def ping(self) -> None: ...
```

呼び出し規約:

- すべて UI thread から呼べること
- adapter method は同期 block しないこと
- response は signal で返すこと

## 9. Threading Contract

### 9.1 Common Rules

- transport read loop は dedicated worker で動かす
- frame assembly / protocol decode も worker 側で行う
- GUI thread へは normalized dataclass を送る
- disk I/O と plot redraw は adapter に持たせない

### 9.2 BLE Adapter

- service discovery と characteristic subscribe は BLE worker に閉じ込める
- notify payload の decode 後に `telemetry_received` を emit する
- status / capabilities / event characteristic を個別に扱う

### 9.3 Serial Adapter

- byte stream を ring buffer 的に蓄積する
- SOF search, payload extraction, CRC validation を worker で完結させる
- valid frame のみ上位へ送る

## 10. Mode-Specific Mapping

### 10.1 `BleSensorAdapter`

- control write: `PUMP_CONTROL_CHARACTERISTIC_UUID`
- telemetry carrier: `SENSOR_DATA_CHARACTERISTIC_UUID`
- status carrier: `STATUS_SNAPSHOT_CHARACTERISTIC_UUID`
- capabilities carrier: `CAPABILITIES_CHARACTERISTIC_UUID`
- event carrier: `EVENT_CHARACTERISTIC_UUID`

### 10.2 `SerialSensorAdapter`

- transport: byte-stream serial over COM port
- default serial parameters: `115200`, `8N1`, no flow control
- frame format: `wired_transport_v1.md`
- startup sequence:
  1. open port
  2. `request_capabilities()`
  3. `request_status()`
  4. accept periodic telemetry

## 11. Derived Metric Boundary

adapter は `flow_rate_lpm` を計算しない。

GUI 側 service が以下を使って計算する。

```text
differential_pressure_pa = 100.0 * flow_sensor_voltage_v + 0.0
flow_rate_lpm = sign(differential_pressure_pa) * (1.0 * sqrt(abs(differential_pressure_pa)) + 0.0)
```

policy id:

- `dummy_orifice_dp_v1`

理由:

- transport payload を canonical raw measurement 中心に保つため
- 将来、正式な差圧変換係数とオリフィス係数へ差し替えやすくするため

## 12. Error and Warning Policy

- CRC fail や parse fail は serial adapter 内で warning 化できる
- sequence gap は adapter または upper service が warning 化できる
- disconnect は `connection_state_changed` と `warning_raised` の両方で可視化してよい
- v1 では adapter が自動再接続しない

## 13. Controller Responsibilities Around the Adapter

`ConnectionController`:

- active adapter instance の所有
- open / close 呼び出し
- signal の購読
- mode switch 時の adapter 破棄

`RecordingController`:

- normalized `TelemetrySample` の保存
- `flow_rate_lpm` 付与後の row write

`PlotController`:

- sample buffering
- render throttling
- plot state と scale state の保持

## 14. 推奨初期実装順

1. `DeviceAdapterBase` を定義する
2. `SerialSensorAdapter` を先に実装する
3. fake transport で controller 配線を確認する
4. `BleSensorAdapter` を追加する
5. warning / diagnostics を整える

## 15. Open Questions

- `telemetry_received` の payload を dataclass のまま維持するか、より軽量な immutable wrapper にするか
- raw payload debug dump を adapter が担当するか、transport helper に分離するか
