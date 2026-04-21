# GUI Implementation Spec v1

## 1. 目的

本書は、新 GUI の画面構成、状態遷移、主要操作、描画更新方針を
実装開始できる粒度まで具体化するための仕様書である。

## 2. 実装原則

- UI 文言は英語を使う
- `example_gui` の professional で落ち着いた雰囲気を踏襲する
- visual theme は `example_gui` に寄せた dark palette を基本とし、light direction は v1 最終形の前提にしない
- 通信安定性を最優先し、描画更新は受信処理よりも下位優先にする
- BLE / Wired の差分は接続パネルと adapter に閉じ込める
- record / plot / warning は mode 非依存の共通 UI とする

## 3. 画面一覧

| Screen / Dialog | Purpose | Notes |
| :--- | :--- | :--- |
| `LauncherWindow` | 起動時の mode 選択 | `BLE mode` / `Wired mode` の 2 択。過度に大きくしない compact launcher とする |
| `MainWindow` | 計測、記録、可視化の主画面 | mode に応じて接続パネルが変化 |
| `SettingsDialog` | mode、plot、logging、advanced の設定 | 起動後の mode change を含む |
| `ModeSwitchDialog` | mode change 前の確認 | 接続中 / recording 中の中断確認 |
| `PartialRecoveryDialog` | partial file の検出通知 | `example_gui` 系の復旧 UX を踏襲 |

## 4. 起動と mode 切替

### 4.1 Launcher Flow

1. アプリ起動
2. `LauncherWindow` を表示
3. `BLE mode` または `Wired mode` を選択
4. `MainWindow` を選択 mode で初期化

### 4.2 Mode Switch Flow

1. User opens `SettingsDialog`
2. User selects another mode
3. If connected, GUI prompts for disconnect confirmation
4. If recording, GUI prompts for recording stop confirmation
5. GUI closes active adapter cleanly
6. GUI clears mode-specific transient state
7. GUI rebinds `MainWindow` to the new mode

方針:

- mode switch は silent に行わない
- active session がある場合は必ず確認ダイアログを出す
- mode switch 後は `Disconnected` state から再開する
- `SettingsDialog` の mode selector は display-only にせず、この flow を実際に起動できる正式導線とする

## 5. Main Window 情報設計

### 5.1 Window Frame

- v1 では dedicated top bar を置かない
- app title、mode、connection、recording を top-level strip に重複配置しない
- 状態表示は左カラムの `Connection` / `Device Status` と右側の warning log に集約する
- `Settings` 導線は left control column 内に統合する

### 5.2 Left Control Column

上から順に以下を置く。

1. `Connection`
2. `Device Status`
3. `Controls`
4. `Recording`

補足:

- `Settings` button は `Connection` セクション内の utility row に配置する
- BLE / Wired で panel の骨格は揃え、device-specific input のみ差し替える

### 5.3 Right Content Area

- Summary cards for the 3 primary displayed values
- Synchronized stacked plots
  - `Zirconia Output Voltage`
  - `Heater RTD Resistance`
  - `Flow Rate`
- Plot toolbar
  - time span selector
  - auto/manual scale toggle
  - reset view
  - relative / clock axis switch
- Event / warning log pane

### 5.4 Geometry and Resize Policy

- left / right の主要カラム幅は、dynamic text length に引きずられて変化しない
- 実装上は fixed ratio もしくは content-independent な width policy を採用する
- recording path や status text のような長い文字列は、panel width を押し広げずに elide もしくは wrap で扱う
- main window は縦方向の情報密度を優先し、冗長な header 領域を作らない

## 6. Mode-Specific Connection Panel

### 6.1 BLE Mode

表示項目:

- device scan button
- discovered device list
- connect / disconnect button
- `Settings` button
- connection state label
- protocol / capability summary

主要操作:

- scan
- connect
- disconnect
- request status

補足:

- BLE scan は startup 時の automatic behavior にせず、user が `Scan` button で明示的に開始する
- v1 GUI は `bleak` ベースの live BLE path を持ち、host 側 BLE 環境が使えない場合のみ mock fallback を許容する
- BLE live path では scan 結果の stable identifier を保持し、connect 時に loop-crossing object を持ち回らない
- BLE `SetPumpState` 実行後は短い delay を置いて `GetStatus` を自動実行し、status pane の更新確認を早める
- status notify が使えない場合は status characteristic の direct read へ退避する
- capabilities read が使えない場合は telemetry-first degraded capabilities を emit して session を継続する
- telemetry health monitor を GUI 側に持ち、初回 sample 遅延と stream stall を warning log へ出す
- scan 結果は target device name を優先して絞り込み、候補が 1 台だけなら auto-select する

### 6.2 Wired Mode

表示項目:

- COM port selector
- refresh ports button
- connect / disconnect button
- `Settings` button
- fixed serial setting label: `115200 baud / 8N1`
- connection state label
- protocol / capability summary

主要操作:

- refresh port list
- connect
- disconnect
- request status

補足:

- v1 では baudrate を通常 UI から変更しない
- 高頻度受信時の事故を避けるため、advanced override は v1 対象外とする
- serial port list は intended device を優先表示し、1 候補だけなら auto-select する
- settings の mode page は current mode と switch outcome を明示し、mode change がある場合は save action を `Save and Switch` と表示する

## 7. Device Status and Controls

### 7.1 Device Status Section

- pump state
- transport state
- latest status flags
- nominal sample period
- firmware version
- protocol version

### 7.2 Control Section

- `Pump ON`
- `Pump OFF`
- `Get Status`
- `Get Capabilities`
- optional `Ping`

方針:

- destructive ではないが装置挙動に影響する操作として、button 状態を明確にする
- command 実行中は短時間 disabled にして二重送信を避ける

## 8. Recording UX

- `Start Recording`
- `Stop Recording`
- current file path
- session id
- recording elapsed time
- partial recovery notification at startup

実装方針:

- record write は受信処理と分離する
- partial file は session 開始時に作成し、正常終了時に rename する
- recording directory は settings で変更可能とし、次回起動時に restore する
- partial recovery detection は recording directory を見て startup 時に実施する
- `derived_metric_policy` を metadata に残す
- 長い file path は panel 幅を変えずに省略表示できるようにする

## 9. Plot UX

### 9.1 表示方針

- 3 指標は stacked plots で同期スクロールする
- 各 plot は独立した Y-axis scale state を持つ
- X-axis は shared timeline とする

### 9.2 操作方針

- auto scale / manual scale を明示的に切り替える
- manual scale 時は min / max を直接入力できる
- time span presets を持つ
- drag zoom, pan, reset をサポートする
- user が drag / wheel により X-axis を手動操作した場合、auto follow は解除される
- auto follow は `Reset View` または time span selector の変更で再有効化する
- user が Y-axis を手動操作した場合、その plot の Y-axis は manual state とみなす
- manual plot interaction の挙動は BLE / Wired で一致させる
- axis drag / wheel と plot viewport drag / wheel の両方を manual interaction として扱う

### 9.3 描画更新方針

- telemetry ingest は every sample
- recording は every sample
- plot refresh は timer-driven
- v1 の初期 target は `150 ms` refresh interval とする
- plot 用の X-axis は host receive timestamp ではなく `sequence + nominal sample period` ベースの shared timeline を使う
- visible time span の変更は viewport 操作とし、session 中の古い plot data を数分で暗黙に破棄しない
- memory guard のために pruning が必要な場合は、selected time span より短くならない explicit policy とする
- current prototype では explicit history retention window を `1800 s` とし、少なくとも数分単位の session では古い data を失わない

補足:

- wired 10 ms 入力でも毎サンプル描画は行わない
- render throttling により通信安定性を優先する
- 見た目上の波形ノイズを避けるため、plot 側では clip-to-view / downsampling を有効化する

## 10. Warning UX

- v1 の異常時動作は warning display only
- modal error ではなく non-blocking warning banner / log を基本とする
- warning severity は `info`, `warn`, `error` の 3 段階
- disconnect や sequence gap は UI で視認できるようにする
- disconnect 時には telemetry session summary を log に残し、manual BLE continuity validation の補助に使えるようにする

## 11. GUI State Model

```text
AppUiState
  mode
  connection
  recording
  capabilities
  latest_status
  latest_sample
  plot_view
  warnings
  session_metadata
```

### 11.1 Connection State

- `disconnected`
- `connecting`
- `connected`
- `disconnecting`
- `error`

### 11.2 Recording State

- `idle`
- `starting`
- `recording`
- `stopping`
- `error`

### 11.3 Persisted Settings

- `QSettings` を用いて local-only persistence を行う
- restore 対象は `last_mode`, `time_span`, `axis_mode`, `auto_scale`, `selected_plot`,
  `x_follow_enabled`, per-plot manual Y range, recording directory, partial recovery notice flag,
  launcher size, main window size とする
- launcher は configured recording directory を使って partial file の有無を確認する

### 11.4 Controller Layer

- `ConnectionController` が adapter / backend の接続、command dispatch、signal relay を担当する
- `PlotController` が sample buffer, shared X-axis timeline, manual Y range を担当する
- `RecordingController` が CSV session lifecycle, append, periodic flush, finalize を担当する
- `WarningController` が severity 付き log entry retention を担当する
- `MainWindow` は widget composition と user interaction orchestration に集中し、
  transport-specific details を controller 層へ直接委譲する

## 12. Derived Metric Policy

`flow_rate_lpm` は GUI 側で計算する。

v1 では placeholder として以下を採用する。

```text
flow_rate_lpm = sign(differential_pressure_selected_pa) * (1.0 * sqrt(abs(differential_pressure_selected_pa)) + 0.0)
```

metadata:

- `derived_metric_policy = dummy_selected_dp_orifice_v1`

補足:

- v1 では `selected differential pressure` を canonical transport field として持つ
- raw `SDP810 / SDP811` は diagnostics として optional に扱う
- 正式な差圧変換係数とオリフィス係数は、流量計とガスラインを使った後続評価で更新する

## 13. 推奨モジュール分割

```text
src/
  main.py
  app_controller.py
  app_state.py
  mode_controller.py
  connection_controller.py
  recording_controller.py
  plot_controller.py
  warning_controller.py
  adapters/
    device_adapter_base.py
    ble_sensor_adapter.py
    serial_sensor_adapter.py
  transport/
    ble_transport.py
    serial_transport.py
  ui/
    launcher_window.py
    main_window.py
    dialogs/
      settings_dialog.py
      mode_switch_dialog.py
      partial_recovery_dialog.py
    widgets/
      connection_panel.py
      status_panel.py
      control_panel.py
      recording_panel.py
      plot_area.py
      warning_log_panel.py
  services/
    derived_metrics.py
    recording_io.py
    settings_store.py
```

## 14. 実装順の推奨

1. `LauncherWindow` と `MainWindow` の骨組みを作る
2. `AppUiState` と controller 群を作る
3. `DeviceAdapter` 契約に従って `SerialSensorAdapter` を先行実装する
4. plot / recording の共通配線を作る
5. `BleSensorAdapter` を追加する
6. warning 表示と mode switch flow を仕上げる

## 15. Prototype Feedback Reflection

- local PySide6 prototype で compact launcher と top bar を持たない main layout を確認済み
- left control column と right content area は、dynamic text に依存せず安定した幅を保つ方針で確定
- local prototype / smoke test は macOS 上の Python 3.12 環境で行い、Windows packaging は release フェーズで扱う
- approved layout に加えて、manual plot UX、local settings persistence、configured recording directory、
  partial recovery detection、wired real transport まで GUI 側の基盤実装を完了済み

## 16. Open Questions

- Plot widget の exact visual treatment を `example_gui` からどこまで忠実に踏襲するか
- raw payload の debug 表示を GUI に出すか、file 保存のみに留めるか
