# Protocol Catalog v1 Draft

## 1. 目的

本書は、新システム v1 における protocol 上の名前と意味を固定するための一覧である。

この文書は、以下の項目を対象とする。

- canonical field names
- status flag bits
- command names
- BLE command opcode draft
- capability keys

## 2. 基本方針

- BLE / Wired で同じ意味の値は同じ field 名を使う
- transport が異なっても、GUI 内部では同じ logical command を使う
- 記録ファイルも本書の canonical field 名に従う
- 表示寄りの derived value は GUI 側で計算する

## 3. Canonical Identifiers

### 3.1 GUI Mode Values

| Field | Allowed Values | Notes |
| :--- | :--- | :--- |
| `mode` | `BLE`, `Wired` | GUI 上の動作モード |

### 3.2 Transport Values

| Field | Allowed Values | Notes |
| :--- | :--- | :--- |
| `transport_type` | `ble`, `serial` | 通信手段の分類 |

### 3.3 Device Type Values

| Field | Allowed Values | Notes |
| :--- | :--- | :--- |
| `device_type` | `zirconia_sensor` | v1 では両 transport 共通の機能ファミリとして扱う |

### 3.4 Wire Enum Encodings

論理モデルでは文字列を使うが、binary transport 上では以下の `uint8` code を使う。

#### Device Type Codes

| Code | Logical Value |
| :--- | :--- |
| `1` | `zirconia_sensor` |
| `2..255` | `reserved` |

#### Transport Type Codes

| Code | Logical Value |
| :--- | :--- |
| `1` | `ble` |
| `2` | `serial` |
| `3..255` | `reserved` |

## 4. Canonical Measurement Fields

### 4.1 Device-to-GUI Measurements

| Field Name | Type | Unit | Required in v1 | Description |
| :--- | :--- | :--- | :--- | :--- |
| `zirconia_output_voltage_v` | `float32` | `V` | Yes | Zirconia output voltage |
| `heater_rtd_resistance_ohm` | `float32` | `Ohm` | Yes | Heater RTD resistance |
| `differential_pressure_selected_pa` | `float32` | `Pa` | Yes | Canonical differential pressure selected by device-side selector |
| `differential_pressure_low_range_pa` | `float32` | `Pa` | Optional | Raw low-range differential pressure (`SDP810`) for diagnostics |
| `differential_pressure_high_range_pa` | `float32` | `Pa` | Optional | Raw high-range differential pressure (`SDP811`) for diagnostics |

### 4.2 GUI-Derived Display Fields

| Field Name | Type | Unit | Required in v1 | Description |
| :--- | :--- | :--- | :--- | :--- |
| `flow_rate_lpm` | `float32` | `L/min` | Yes | GUI-derived flow rate for display and recording |

方針:

- `flow_rate_lpm` は GUI 側で計算する
- device は canonical measurement として `differential_pressure_selected_pa` を送る
- raw 2ch は diagnostic measurement として transport ごとに optional とする
- v1 実装では placeholder として `dummy_selected_dp_orifice_v1` を使う

v1 placeholder formula:

```text
flow_rate_lpm = sign(differential_pressure_selected_pa) * (1.0 * sqrt(abs(differential_pressure_selected_pa)) + 0.0)
```

補足:

- raw voltage から差圧への dummy coefficient は `100.0 Pa/V`, `0.0 Pa`
- オリフィス流量換算の dummy coefficient は `1.0 L/min/sqrt(Pa)`, `0.0 L/min`
- 呼気/吸気の両方向を表現できるよう、placeholder の段階から flow rate は signed value とする
- 実流量構成に基づく正式換算式は将来バージョンで置き換える

## 5. Telemetry Sample Shape

v1 の `TelemetrySample` は以下の logical fields を持つことを想定する。

```text
TelemetrySample
  device_type
  transport_type
  sequence
  host_received_at
  nominal_sample_period_ms
  status_flags
  measurements:
    zirconia_output_voltage_v
    heater_rtd_resistance_ohm
    differential_pressure_selected_pa
    differential_pressure_low_range_pa?
    differential_pressure_high_range_pa?
  derived_values:
    flow_rate_lpm
```

## 6. Status Flag Bit Assignment

v1 では `status_flags` を `uint32` として扱う。

| Bit | Name | Meaning | v1 Use |
| :--- | :--- | :--- | :--- |
| `0` | `pump_on` | Pump output is active | Required |
| `1` | `transport_session_active` | Host session / transport is active | Optional, legacy-friendly |
| `2` | `adc_fault` | ADC-related fault is latched | Required |
| `3` | `sampling_overrun` | Sampling or main loop overrun detected | Required |
| `4` | `sensor_fault` | Sensor read result is invalid or faulted | Recommended |
| `5` | `telemetry_rate_warning` | Telemetry timing is outside nominal expectations | Recommended |
| `6` | `command_error_latched` | A command-level error has occurred and is latched | Optional |
| `7..31` | `reserved` | Reserved for future use | Reserved |

補足:

- Bit `0` と Bit `2` は old firmware の意味と整合しやすい
- Bit `3` は old firmware の `processing overrun` を一般化した位置づけとする

## 7. Logical Commands

### 7.1 Required in v1

| Logical Command | Request Payload | Success Result | Notes |
| :--- | :--- | :--- | :--- |
| `get_capabilities` | none | `capabilities` message | 接続直後に実行する |
| `get_status` | none | `status_snapshot` message | 画面更新、診断に使用する |
| `set_pump_state` | `state=on|off` | ack or refreshed status | `Pump ON/OFF` の共通表現 |

### 7.2 Recommended in v1

| Logical Command | Request Payload | Success Result | Notes |
| :--- | :--- | :--- | :--- |
| `ping` | none | `pong` event or response | transport の基本疎通確認 |

## 8. BLE Command Opcode Draft

BLE では既存の pump control command を維持しつつ、追加 command を拡張する案を採用候補とする。

| Opcode | Logical Command | Notes |
| :--- | :--- | :--- |
| `0x55` | `set_pump_state(on)` | Existing legacy-compatible opcode |
| `0xAA` | `set_pump_state(off)` | Existing legacy-compatible opcode |
| `0x30` | `get_status` | New v1 opcode draft |
| `0x31` | `get_capabilities` | New v1 opcode draft |
| `0x32` | `ping` | New v1 opcode draft |

方針:

- 既存の `0x55` / `0xAA` は維持する
- `0x30` 以降を追加 command 用の draft range とする
- 今後 multi-byte command envelope が必要になった場合でも、v1 では単純な opcode 方式を優先する

## 9. Required Capability Keys

この節は GUI 内で扱う logical capability model を表す。
binary transport 上では、一部の項目が code / bit field に符号化される。

`get_capabilities` の応答では、最低限以下のキーを扱えるようにする。

| Key | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `protocol_version_major` | `uint8` | Yes | Major version |
| `protocol_version_minor` | `uint8` | Yes | Minor version |
| `device_type` | `string` | Yes | `zirconia_sensor` |
| `transport_type` | `string` | Yes | `ble` or `serial` |
| `firmware_version` | `string` | Yes | Firmware version string |
| `nominal_sample_period_ms` | `uint16` | Yes | Expected sample period |
| `supported_commands` | `string[]` | Yes | Logical command names |
| `telemetry_fields` | `string[]` | Yes | Canonical field names sent by device |
| `status_flag_schema_version` | `uint16` | Yes | Status flag definition version |

### 9.1 Recommended Capability Keys

| Key | Type | Description |
| :--- | :--- | :--- |
| `device_name` | `string` | BLE advertisement name or serial-side device name |
| `max_payload_bytes` | `uint16` | For transport sizing |
| `warning_flag_schema_version` | `string` | If warning flags are added later |
| `device_serial` | `string` | Manufacturing / tracking identifier |

## 9.2 Capability Bit Maps

### Supported Command Bits

| Bit | Command |
| :--- | :--- |
| `0` | `get_capabilities` |
| `1` | `get_status` |
| `2` | `set_pump_state` |
| `3` | `ping` |
| `4..15` | `reserved` |

### Telemetry Field Bits

| Bit | Field |
| :--- | :--- |
| `0` | `zirconia_output_voltage_v` |
| `1` | `heater_rtd_resistance_ohm` |
| `3` | `differential_pressure_selected_pa` |
| `4` | `differential_pressure_low_range_pa` |
| `5` | `differential_pressure_high_range_pa` |
| `2, 6..15` | `reserved` |

### 9.3 Logical-to-Wire Mapping Notes

| Logical Capability Key | Wire Encoding Example |
| :--- | :--- |
| `device_type` | `device_type_code` (`uint8`) |
| `transport_type` | `transport_type_code` (`uint8`) |
| `supported_commands` | `supported_command_bits` (`uint16`) |
| `telemetry_fields` | `telemetry_field_bits` (`uint16`) |
| `status_flag_schema_version` | `status_flag_schema_version` (`uint16`) |

## 10. Transport Presence Matrix

| Logical Item | BLE | Wired | Notes |
| :--- | :--- | :--- | :--- |
| `zirconia_output_voltage_v` | Required | Required | Common display item |
| `heater_rtd_resistance_ohm` | Required | Required | Common display item |
| `differential_pressure_selected_pa` | Required | Required | GUI computes flow rate from this canonical field |
| `differential_pressure_low_range_pa` | Optional / usually omitted | Optional | Diagnostic field; typically available on wired only |
| `differential_pressure_high_range_pa` | Optional / usually omitted | Optional | Diagnostic field; typically available on wired only |
| `flow_rate_lpm` | GUI-derived | GUI-derived | Not canonical transport field |
| `get_capabilities` | Required | Required | Common logical command |
| `get_status` | Required | Required | Common logical command |
| `set_pump_state` | Required | Required | Common logical command |

## 11. Open Questions

- `transport_session_active` を bit `1` に残すか、完全に reserved にするか
- BLE の `get_status` / `get_capabilities` 応答 carrier を extension characteristic に固定するか、別 fallback を残すか

## 12. TODO

- [ ] BLE の response carrier policy を確定する
