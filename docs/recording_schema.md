# Recording Schema Draft

## 1. 目的

本書は、BLE / Wired の両モードで共通に使う記録ファイルスキーマのドラフトである。

v1 では、解析しやすさと通信安定性の観測しやすさを優先する。

## 2. 基本方針

- 主記録ファイルは telemetry 中心の CSV とする
- BLE / Wired で同じ列構成を使う
- 記録時刻は GUI 受信時刻を基準とする
- device の raw/canonical measurement と GUI-derived value を同じ行に保存する
- 通信安定性の観測のため、`sequence_gap` と timing 関連列を保存する
- partial file を許容し、異常終了時の復旧性を確保する

## 3. ファイル種別

### 3.1 Final Session File

命名例:

```text
session_20260408_153000.csv
```

用途:

- 正常終了したセッションの正式記録

### 3.2 Partial Session File

命名例:

```text
session_20260408_153000.partial.csv
```

用途:

- GUI が正常終了しなかった場合の暫定ファイル
- 次回起動時に検出対象とする

## 4. ファイル構造

### 4.1 Header Section

- 先頭の metadata は `# key=value` 形式で保存する
- metadata 行の後に CSV header row を置く

例:

```text
# file_format=zss_demokit_session_csv_v1
# exported_at_iso=2026-04-08T15:30:00+09:00
# gui_app_name=ZSS Demo Kit
# gui_app_version=0.1.0
# session_id=20260408_153000_run01
# mode=BLE
# transport_type=ble
# device_type=zirconia_sensor
# device_identifier=M5STAMP-MONITOR
# firmware_version=1.0.0
# protocol_version=1.0
# nominal_sample_period_ms=50
# derived_metric_policy=dummy_selected_dp_orifice_v1
# source_endpoint=BLE:M5STAMP-MONITOR
# notes=
host_received_at_iso,host_received_at_unix_ms,mode,transport_type,sequence,sequence_gap,inter_arrival_ms,host_inter_arrival_ms,device_inter_arrival_ms,device_sample_tick_us,nominal_sample_period_ms,status_flags_hex,pump_state,heater_power_state,zirconia_output_voltage_v,heater_rtd_resistance_ohm,zirconia_ip_voltage_v,internal_voltage_v,differential_pressure_selected_pa,differential_pressure_selected_source,differential_pressure_low_range_pa,differential_pressure_high_range_pa,flow_rate_lpm
```

## 5. Required Header Metadata Keys

| Key | Required | Description |
| :--- | :--- | :--- |
| `file_format` | Yes | Always `zss_demokit_session_csv_v1` |
| `exported_at_iso` | Yes | File creation timestamp |
| `gui_app_name` | Yes | GUI app display name |
| `gui_app_version` | Yes | GUI app version |
| `session_id` | Yes | Session identifier |
| `mode` | Yes | `BLE` or `Wired` |
| `transport_type` | Yes | `ble` or `serial` |
| `device_type` | Yes | `zirconia_sensor` |
| `device_identifier` | Yes | BLE device name or serial-side device identifier |
| `firmware_version` | Recommended | Firmware version if known |
| `protocol_version` | Recommended | Protocol version if known |
| `nominal_sample_period_ms` | Recommended | Target sample period |
| `source_endpoint` | Recommended | `BLE:<name>` or `COM<n>` など |
| `derived_metric_policy` | Recommended | Example: `dummy_selected_dp_orifice_v1` |
| `notes` | Optional | Free text |

## 6. CSV Columns

### 6.1 Column Order

```text
host_received_at_iso
host_received_at_unix_ms
mode
transport_type
sequence
sequence_gap
inter_arrival_ms
host_inter_arrival_ms
device_inter_arrival_ms
device_sample_tick_us
nominal_sample_period_ms
status_flags_hex
pump_state
heater_power_state
zirconia_output_voltage_v
heater_rtd_resistance_ohm
zirconia_ip_voltage_v
internal_voltage_v
differential_pressure_selected_pa
differential_pressure_selected_source
differential_pressure_low_range_pa
differential_pressure_high_range_pa
flow_rate_lpm
```

### 6.2 Column Definitions

| Column | Type | Unit | Required | Description |
| :--- | :--- | :--- | :--- | :--- |
| `host_received_at_iso` | `string` | ISO8601 | Yes | GUI receive timestamp in ISO format |
| `host_received_at_unix_ms` | `int64` | ms | Yes | GUI receive timestamp in Unix milliseconds |
| `mode` | `string` | - | Yes | `BLE` or `Wired` |
| `transport_type` | `string` | - | Yes | `ble` or `serial` |
| `sequence` | `uint32` | - | Recommended | Device sequence number |
| `sequence_gap` | `uint32` | samples | Yes | Missing sample count since previous row; `0` if contiguous |
| `inter_arrival_ms` | `float32` | ms | Yes | Preferred interval value; use `device_inter_arrival_ms` when available, otherwise `host_inter_arrival_ms` |
| `host_inter_arrival_ms` | `float32` | ms | Optional | Difference from previous row host receive time |
| `device_inter_arrival_ms` | `float32` | ms | Optional | Difference from previous row device sample tick; blank when unavailable |
| `device_sample_tick_us` | `uint32` | us | Optional | Device-side sample start tick captured for timing diagnostics; blank when unavailable |
| `nominal_sample_period_ms` | `uint16` | ms | Recommended | Expected sample period |
| `status_flags_hex` | `string` | hex | Yes | Status flags as zero-padded hex |
| `pump_state` | `uint8` | - | Yes | `1` when pump on, otherwise `0` |
| `heater_power_state` | `uint8` | - | Yes | `1` when heater power on, otherwise `0` |
| `zirconia_output_voltage_v` | `float32` | V | Yes | Canonical measurement |
| `heater_rtd_resistance_ohm` | `float32` | Ohm | Yes | Canonical measurement |
| `zirconia_ip_voltage_v` | `float32` | V | Optional | Service / engineering diagnostic measurement; blank when unavailable |
| `internal_voltage_v` | `float32` | V | Optional | Service / engineering diagnostic measurement; blank when unavailable |
| `differential_pressure_selected_pa` | `float32` | Pa | Yes | Canonical differential pressure selected by device |
| `differential_pressure_selected_source` | `string` | - | Optional | Which differential pressure sensor contributed the selected value, e.g. `SDP810` / `SDP811` |
| `differential_pressure_low_range_pa` | `float32` | Pa | Optional | Raw low-range differential pressure; blank when unavailable |
| `differential_pressure_high_range_pa` | `float32` | Pa | Optional | Raw high-range differential pressure; blank when unavailable |
| `flow_rate_lpm` | `float32` | L/min | Yes | GUI-derived value |

## 7. Interpretation Rules

### 7.1 `sequence_gap`

- 初回行は `0`
- `current_sequence == previous_sequence + 1` のとき `0`
- それ以外は `max(0, current_sequence - previous_sequence - 1)` を記録する
- sequence が未提供の場合は `0` を記録し、別途 capability で未対応を示す

### 7.2 `inter_arrival_ms`

- 初回行は空欄または `0`
- `device_inter_arrival_ms` が利用可能な場合は、その値を `inter_arrival_ms` に記録する
- `device_inter_arrival_ms` が利用できない場合は、`host_inter_arrival_ms` を `inter_arrival_ms` に記録する

### 7.3 `host_inter_arrival_ms`

- 初回行は空欄
- 2 行目以降は `host_received_at_unix_ms` の差分を記録する

### 7.4 `device_inter_arrival_ms`

- 初回行は空欄
- `device_sample_tick_us` が利用可能な場合のみ記録する
- 2 行目以降は device-side sample tick の差分を ms に変換して記録する

### 7.5 `device_sample_tick_us`

- wired など device-side timing diagnostic を提供する transport でのみ値を持つ
- BLE など未対応 transport では空欄としてよい

### 7.6 `pump_state`

- `status_flags` の bit `0` から導出する
- `1` は ON、`0` は OFF

### 7.7 Numeric Missing Values

- v1 の core measurement は基本空欄にしない
- 取得不能時は空欄ではなく warning を伴う fallback 値使用を避け、可能ならその行を記録しないか fault 状態で扱う
- raw diagnostic field (`differential_pressure_low_range_pa`, `differential_pressure_high_range_pa`) は transport に存在しない場合のみ空欄としてよい
- service diagnostic field (`zirconia_ip_voltage_v`, `internal_voltage_v`) は transport / board config に存在しない場合のみ空欄としてよい
- timing diagnostic field (`device_inter_arrival_ms`, `device_sample_tick_us`) は transport に存在しない場合のみ空欄としてよい
- `differential_pressure_selected_source` は raw diagnostic field が存在しない transport では空欄としてよい

### 7.8 `flow_rate_lpm`

- v1 では placeholder として `dummy_selected_dp_orifice_v1` を使う
- formula は以下の placeholder とする

```text
flow_rate_lpm = sign(differential_pressure_selected_pa) * (1.0 * sqrt(abs(differential_pressure_selected_pa)) + 0.0)
```

- metadata に `derived_metric_policy=dummy_selected_dp_orifice_v1` を残すことを推奨する
- flow rate は signed value として記録し、後続の calibration で呼気/吸気方向を維持する

## 8. Example Rows

```csv
2026-04-08T15:30:00.100+09:00,1775639400100,BLE,ble,100,0,,,,50,0x00000001,1,0,0.640,123.4,,,1.250,,,,11.180340
2026-04-08T15:30:00.150+09:00,1775639400150,BLE,ble,101,0,50.0,50.0,,,50,0x00000001,1,0,0.642,123.5,,,1.252,,,,11.189281
2026-04-08T15:30:00.260+09:00,1775639400260,Wired,serial,103,1,50.0,110.0,50.0,5541200,50,0x00000021,1,0,0.641,123.6,0.913,,1.255,SDP810,1.240,1.270,11.202678
```

解釈:

- 3 行目は `sequence_gap=1` のため 1 サンプル欠落を示す
- 3 行目は host 側では `110.0 ms` 遅れて見えているが、device 側では `50.0 ms` cadence が維持されている例である

## 9. v1 Scope Decisions

- 主記録ファイルは telemetry 中心とする
- command log や event log を同じ CSV に混在させない
- 必要であれば将来 `events_*.csv` などの sidecar file を追加する

## 10. Implementation Notes

- `example_gui` の partial file 運用を参考にする
- GUI は row write と flush を分離し、高頻度受信時も受信処理を詰まらせない
- finalization 時に `.partial.csv` を `.csv` へ rename する

## 11. Open Questions

- fault row を「記録する」か「破棄する」か
- raw payload の debug 保存を sidecar file にするか、完全に持たないか

## 12. TODO

- [ ] `status_flags_hex` の表示フォーマット桁数を固定する
- [ ] sidecar event log が必要かを判断する
