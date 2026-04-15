# Communication Protocol Draft

## 1. 目的

本書は、新システムの通信仕様を検討するための初期ドラフトである。

この文書では、以下の 2 つを分けて考える。

- 共通の論理メッセージ
- transport ごとの具体的な符号化と搬送方式

補助文書:

- canonical field / command 一覧: `protocol_catalog_v1.md`
- 記録ファイルスキーマ: `recording_schema.md`
- BLE transport 詳細: `ble_transport_v1.md`
- wired transport 詳細: `wired_transport_v1.md`

## 2. 背景

既存資産では、通信方式が分断されている。

- BLE 系
  - `old_firmware` が GATT notify / write を用いる
  - telemetry は固定長バイナリ
- wired 系
  - `example_gui` はシリアルの行ベースプロトコルを扱う
  - `[csv]`, `[profile]`, `[status]`, `[event]`, `[caps]` などのプレフィクスを持つ

このままでは GUI 内部で device-specific 分岐が増えやすいため、新システムでは
「共通の論理モデル」と「transport 別 encoding」を分離する。

## 3. 設計原則

- GUI 内部では transport 非依存のメッセージモデルを使う
- BLE と wired は同じ意味の情報をできるだけ同じ名前で扱う
- high-rate telemetry と control / event / capability を同一手法に無理に統一しない
- versioning を前提にする
- 記録時刻は GUI 受信時刻を基準とする
- 欠落検知のために sequence 番号を持たせる
- エラー検出と異常可視化を考慮する
- BLE の既存識別子は可能な限り維持する
- 表示寄りの derived values は GUI 側で計算することを基本とする

## 4. 推奨方針

### 4.1 推奨案

「論理メッセージは共通化し、transport ごとに最適な encoding を採用する」を
推奨案とする。

理由:

- BLE は MTU と notify の性質上、コンパクトなバイナリが有利
- wired は `10 ms` の必須要件があるため、telemetry は軽量で安定な framing を優先すべき
- GUI 側は adapter で吸収できる

### 4.2 採用しない方がよい案

- すべてを BLE 向け固定長バイナリに寄せる
  - 開発・デバッグ効率が落ちやすい
- すべてを verbose なテキストに寄せる
  - BLE での効率が悪くなりやすい

## 5. 共通論理メッセージ案

### 5.1 Message Types

- `hello`
- `capabilities`
- `status_snapshot`
- `telemetry_sample`
- `telemetry_batch`
- `command_request`
- `command_response`
- `event`
- `error`
- `heartbeat`

### 5.2 共通フィールド案

最低限、以下のフィールドを検討対象とする。

| Field | Purpose |
| :--- | :--- |
| `protocol_version` | プロトコル互換性の識別 |
| `device_type` | `zirconia_sensor` などの機能ファミリ識別 |
| `transport_type` | `ble` / `serial` などの transport 識別 |
| `device_id` | 個体識別 |
| `firmware_version` | firmware 識別 |
| `session_id` | GUI セッション識別 |
| `sequence` | 欠落や順序乱れの検出 |
| `host_received_at` | GUI 側受信時刻 |
| `status_flags` | 状態ビット群 |
| `nominal_sample_period_ms` | 想定サンプリング周期 |

### 5.3 TelemetrySample の論理モデル案

```text
TelemetrySample
  device_type
  transport_type
  sequence
  host_received_at
  nominal_sample_period_ms
  status_flags
  measurements{}
  derived_values[]
```

補足:

- `measurements{}` は device から受け取る canonical measurement を表す
- `derived_values[]` は GUI 側で算出した表示 / 解析向けの補助値を表す
- デバイスごとの差分は capability で補足する

## 6. メッセージカテゴリ別の方針

### 6.1 Capability / Handshake

目的:

- 接続直後にデバイス種別、プロトコル版、チャンネル数、対応コマンドを把握する

含めたい内容:

- protocol version
- firmware version
- device type
- supported commands
- telemetry channel definitions
- nominal sample period
- optional features
- transport specific constraints

### 6.2 Telemetry

目的:

- 連続した計測データを欠落検知可能な形で運ぶ

含めたい内容:

- sequence
- nominal / measured sample period
- status flags
- canonical measurement values

v1 の主要 measurement 候補:

- `zirconia_output_voltage_v`
- `heater_rtd_resistance_ohm`
- `flow_sensor_voltage_v`

v1 の主要 derived value:

- `flow_rate_lpm`

詳細は `protocol_catalog_v1.md` を参照する。

### 6.3 Command / Response

目的:

- ポンプ制御
- 状態取得
- capability 取得
- 接続確認

方針:

- wired では request / response の対応関係を追うために `request_id` を持たせる
- BLE v1 の legacy-compatible opcode path では `request_id` を持たず、response carrier で補う
- 成功 / 失敗 / validation error を明確に返す

v1 必須 command 候補:

- `get_capabilities`
- `get_status`
- `set_pump_state`
- `ping`

詳細は `protocol_catalog_v1.md` を参照する。

### 6.4 Event / Error

目的:

- 状態変化と異常を GUI に伝える

例:

- connected
- disconnected
- adc_fault
- sensor_fault
- transport_error
- warning

## 7. BLE プロトコル案

### 7.1 位置づけ

BLE は低から中頻度の telemetry を安定して運ぶ transport とする。

v1 方針:

- 可能な限り既存の device name と UUID を維持する
- 詳細 packet layout と extension service 方針は `ble_transport_v1.md` を参照する

### 7.2 GATT 構成案

優先案:

- 既存の `CONTROL_SERVICE_UUID` を維持する
- 既存の `MONITORING_SERVICE_UUID` を維持する
- 既存の pump control characteristic を維持する
- 既存の sensor telemetry characteristic を維持する

拡張方針:

- 既存 characteristic だけで不足する場合は、新しい optional characteristic を追加する
- 既存 UUID を全面変更するのは、互換性よりも構造上のメリットが大きい場合に限定する

### 7.3 Telemetry encoding 案

推奨:

- BLE telemetry は固定長または versioned binary packet を使う

最低限含めたい項目:

- `protocol_version`
- `telemetry_schema_version`
- `sequence`
- `status_flags`
- `zirconia_output_voltage_v`
- `heater_rtd_resistance_ohm`
- `flow_sensor_voltage_v`

備考:

- 現行 old_firmware は 32 byte notify を送っている
- 新仕様では将来拡張に備え、version / flags / sequence を明示的に先頭へ持たせたい
- GUI 側で `host_received_at` を付与し、`flow_rate_lpm` を計算する

### 7.4 BLE command encoding 案

候補:

- 小さい enum ベース binary command
- UTF-8 text command

初期推奨:

- 既存 characteristic を維持する観点から、小さい binary command を第一候補とする
- telemetry ほど高頻度ではないため、可読性重視も選択肢に入る

### 7.5 BLE で追加したい観測項目

- `sequence`
- `adc_fault`
- `ble_connected`
- device-defined status flags
- optional diagnostic counter

これにより、old_firmware の「50 ms のばらつき」を host 側で観測しやすくする。

## 8. wired プロトコル案

### 8.1 位置づけ

wired は高頻度サンプルを扱う transport とする。

### 8.2 初期方針

初期開発では、`10 ms` の必須要件を優先し、以下を採用候補とする。

- 方式 A: framed binary telemetry + compact command / response
- 方式 B: binary telemetry + text command / response
- 方式 C: 行ベーステキストプロトコル

現時点の推奨:

- telemetry は binary を第一候補とする
- `example_gui` の行ベース設計は control plane やログ可読性の参考として扱う
- 完全な行ベーステキストは、性能実測で十分と示せた場合のみ採用候補とする
- 詳細 frame layout と request/response flow は `wired_transport_v1.md` を参照する
- v1 default serial setting は `115200 baud`, `8N1` とする

### 8.3 Wired telemetry framing 案

推奨イメージ:

```text
SOF | version | message_type | length | sequence | status_flags | payload | checksum
```

payload の v1 候補:

- `zirconia_output_voltage_v`
- `heater_rtd_resistance_ohm`
- `flow_sensor_voltage_v`

### 8.4 テキスト系 fallback 案

開発用または control plane 用の候補:

```text
[caps] protocol_version=1
[caps] device_type=zirconia_sensor
[caps] transport_type=serial
[status] pong=1
[telemetry] seq=123,zirconia_output_voltage_v=...,heater_rtd_resistance_ohm=...,flow_sensor_voltage_v=...
```

または:

```text
{"type":"telemetry","seq":123,"channels":{"zirconia_output_voltage_v":0.64,"heater_rtd_resistance_ohm":123.4,"flow_sensor_voltage_v":1.25}}
```

比較観点:

- prefix 付き key-value / CSV
  - 実装が軽い
  - 既存参考資産を流用しやすい
- JSON Lines
  - 拡張しやすい
  - 文字量が増えやすい

### 8.5 wired で重視すること

- 高頻度でも parse コストが重すぎないこと
- 欠落や乱れを追跡できること
- capability / command / error が扱いやすいこと
- ログ保存形式と相性がよいこと
- `10 ms` の必須要件を崩さないこと

## 9. GUI 内部への正規化

GUI 内部では、BLE と wired の受信内容を以下のように共通化する。

```text
Raw Transport Frame
  -> Transport Decoder
  -> Device Adapter
  -> Common Domain Message
  -> App State
  -> Plot / Recording / Log
```

重要:

- GUI の記録層は raw frame ではなく、原則として共通化後の論理データを保存する
- 必要であれば debug 用に raw payload も別列として残す
- `host_received_at` は adapter が付与する
- `flow_rate_lpm` のような表示寄りの derived value は GUI 側で計算する
- 主記録ファイルのスキーマは `recording_schema.md` を参照する

## 10. versioning 方針案

- `protocol_version_major`
- `protocol_version_minor`

基本方針:

- major が異なる場合は非互換とみなす
- minor が異なる場合は後方互換を基本とする
- GUI は capability handshake で protocol version を必ず確認する

## 11. エラー処理方針案

- command ごとに success / failure を返す
- validation error は人間が読める形で返す
- telemetry の連番欠落は GUI 側で警告にできるようにする
- transport disconnect は event と UI の両方で明確化する
- v1 の異常時動作は警告表示を基本とし、自動再接続は必須にしない

## 12. このフェーズで具体化した項目

- BLE telemetry packet の先頭レイアウト
- wired telemetry の binary framing
- capability の必須キー一覧
- command 名の一覧
- status flag のビット定義

## 13. Open Questions

- BLE extension service の UUID を最終的にどう固定するか
- BLE の response carrier policy を extension characteristic 固定にするか
- raw payload をどこまで記録ファイルに残すか

## 14. TODO

- [ ] BLE の response carrier policy を確定する
- [ ] raw payload の debug 保存方針を確定する
