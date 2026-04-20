# Implementation Backlog v1

## 1. 目的

本書は、現在の要件・通信仕様・GUI 試作を前提に、
実装開始から v1 beta 相当までを進めるための具体バックログをまとめたものである。

対象は以下の 3 領域である。

- GUI application
- firmware
- end-to-end integration and validation

## 2. 実行方針

- 優先順位は `通信安定性 -> UI / UX -> 将来拡張性` とする
- GUI は `gui_prototype/` を実装ベースとして育てる
- firmware は top-level PlatformIO project を新 firmware の本体にする
- wired path を BLE より先に end-to-end 化する
- ただし firmware の measurement core と status model は wired / BLE 共通で先に作る

理由:

- wired は `10 ms` 必須要件があり、最も厳しい通信条件を早めに検証したい
- GUI / firmware の両方で、共通データモデルと共通 command 群を先に固めたほうが手戻りが少ない
- BLE は legacy compatibility を含むため、wired より実装分岐が多い

## 3. マイルストーン

### M0. Foundation Ready

- protocol constants が GUI / firmware の両側でコード化されている
- GUI 実装ベースと firmware 実装ベースが雛形から脱している
- テスト用 fixture と golden payload がある

### M1. GUI Shell Ready

- approved layout の GUI が mock backend で安定動作する
- recording, plot, warning の共通基盤が入っている
- mode switch と settings persistence が動く

### M2. Wired End-to-End

- wired firmware が binary framing で telemetry / status / capabilities / command ack を送受信できる
- GUI が `10 ms` telemetry を受信・描画・記録できる
- `Pump ON/OFF` と `Get Status` が end-to-end で動く

### M3. BLE End-to-End

- BLE firmware が v1 telemetry と extension service を提供する
- GUI が BLE 接続、telemetry 受信、status / capabilities 取得を行える
- legacy compatibility mode の最低限接続が確認できる

現在地:

- `COMPLETE` 相当
- local Mac 実機 probe により `180 s` session、recording finalize、manual reconnect、`sequence_gap_total=0`、reconnect recovery `3.43 s` を確認済み
- status path は追加 hardening を入れ、short probe で `Status events=7` まで確認済み

### M4. Beta Candidate

- 両モードで共通 CSV 記録が通る
- warning 表示と session log が揃う
- ローカル検証結果をもとに Windows packaging 準備へ移れる

現在地:

- `IN PROGRESS`
- next focus は `GUI-009 Packaging Preparation` と Windows smoke-ready な配布手順の整備

## 4. 推奨実行順

1. Cross-cutting foundation
2. GUI production skeleton
3. Firmware production skeleton
4. Wired transport on firmware
5. Wired adapter on GUI
6. Wired end-to-end validation
7. BLE transport on firmware
8. BLE adapter on GUI
9. BLE end-to-end validation
10. Hardening, packaging preparation, beta gate

## 5. Cross-Cutting Backlog

### 5.1 Current Cross-Cutting Progress

| Item | Status | Notes |
| :--- | :--- | :--- |
| `CORE-001` | `COMPLETE` | protocol constants は GUI / firmware の両側でコード定義済み |
| `CORE-002` | `COMPLETE` | `test/fixtures/protocol_golden_v1.json`、`tools/protocol_fixture_smoke.py`、`tools/firmware_fixture_verify.cpp` により shared golden fixture を導入済み |
| `CORE-003` | `COMPLETE` | `validation_checklist_v1.md` を継続更新し、GUI / firmware / integration の gate を管理中 |

### CORE-001. Protocol Constants Package

目的:

- `protocol_catalog_v1.md`
- `wired_transport_v1.md`
- `ble_transport_v1.md`

の内容を GUI / firmware のコード定数として同期する。

対象:

- protocol version
- command ids / opcodes
- status flag bits
- telemetry field bits
- event codes
- response / result codes

依存:

- なし

完了条件:

- GUI 側に protocol constants module がある
- firmware 側に protocol constants header がある
- 同じ定義値を両側から参照している

### CORE-002. Golden Fixture Set

目的:

- parser / encoder / CSV recording の回帰確認に使う固定 fixture を用意する

対象:

- BLE telemetry sample bytes
- BLE status snapshot bytes
- wired frame bytes
- expected normalized `TelemetrySample`
- expected CSV row

依存:

- `CORE-001`

完了条件:

- 少なくとも正常系 3 ケース、異常系 3 ケースの fixture がある
- GUI parser テストと firmware encode テストで同じ fixture を参照できる

現状メモ:

- shared fixture は `test/fixtures/protocol_golden_v1.json` に集約済み
- `tools/protocol_fixture_smoke.py` は GUI 側 BLE / wired decoder、CSV row formatting、invalid-case parser 動作を同じ fixture で検証する
- `tools/firmware_fixture_verify.cpp` は host-side C++ binary として firmware payload / frame encoder を同じ fixture に照合する
- current fixture set では正常系 9 ケース、異常系 4 ケース、CSV row 1 ケースをカバーする

### CORE-003. Validation Checklist Draft

目的:

- 実装完了判定を会話ベースではなくチェックリストで管理できるようにする

対象:

- launch
- connect / disconnect
- telemetry continuity
- command response
- recording
- warning display
- sample-period observation

依存:

- なし

完了条件:

- `M2`, `M3`, `M4` の gate 条件が文書化されている

## 6. GUI Backlog

### 6.1 Current GUI Progress

| Item | Status | Notes |
| :--- | :--- | :--- |
| `GUI-001` | `COMPLETE` | `gui_prototype/` は Python 3.12 上の実装ベースとして整理済み |
| `GUI-002` | `COMPLETE` | `AppUiState` と controller layer の基盤を導入済み |
| `GUI-003` | `COMPLETE` | `QSettings` による mode / plot / logging / window persistence を実装済み |
| `GUI-004` | `COMPLETE` | axis/viewbox interaction hook と time-based history retention により manual plot parity と plot history retention を回収済み |
| `GUI-005` | `COMPLETE` | 共通 CSV recording、partial file handling、configured recording directory を実装済み |
| `GUI-006` | `COMPLETE` | wired mode は real serial transport に加え、offscreen GUI session probe で connect / recording / `Pump ON/OFF` / CSV finalize まで確認済み |
| `GUI-007` | `PARTIAL` | `bleak` ベースの live BLE path は実装済みで、local Mac で scan / connect / capabilities / command request を確認済み。live reconnect continuity の追加確認が残る |
| `GUI-008` | `PARTIAL` | warning log と telemetry health monitor は実装済み。backend reconnect smoke で BLE event / status refresh 回帰をカバーしつつ、live continuity の追加確認が残る |
| `GUI-009` | `PENDING` | Windows packaging 準備は release 前に対応 |
| `GUI-010` | `COMPLETE` | user feedback integration と GUI parity hardening を回収済み。dark theme direction、settings mode switch flow、device auto-filter / preselect、manual plot parity、plot history retention を実装・確認 |

補足:

- GUI-only foundation step は実質完了とみなし、以後の GUI 作業は BLE transport と packaging に付随するものを中心とする
- 次の主戦場は firmware / BLE / end-to-end hardening である

### GUI-001. Promote Prototype to Production Skeleton

目的:

- `gui_prototype/` を「試作専用 UI」から「本番実装の基盤」へ引き上げる

作業:

- package structure を整理する
- mock backend と production adapter 境界を明示する
- app entry point, theme, dialogs, widgets の責務を固定する

依存:

- なし

完了条件:

- macOS + Python 3.12 で起動できる
- approved layout が維持されている
- mock backend を外しても main window 自体は壊れない

### GUI-002. Application State and Controller Layer

目的:

- UI event と adapter event を仲介する application layer を実装する

作業:

- `AppUiState`
- `ModeController`
- `ConnectionController`
- `RecordingController`
- `PlotController`
- `WarningController`

をコード化する。

依存:

- `GUI-001`

完了条件:

- main window が adapter 直結ではなく controller 経由で更新される
- mode switch, recording state, warnings を一元管理できる

### GUI-003. Settings Persistence

目的:

- mode, plot, logging の設定を保存 / 復元する

作業:

- settings store 実装
- `SettingsDialog` との接続
- 起動時 restore

依存:

- `GUI-002`

完了条件:

- mode 選択、plot preference、recording directory などが再起動後も保持される

### GUI-004. Plot and Scale Controller

目的:

- `example_gui` 相当の plot 操作性を production code として定着させる

作業:

- shared X-axis stacked plots
- auto / manual scale
- min / max direct input
- span preset
- reset view
- throttled refresh

依存:

- `GUI-002`

完了条件:

- manual scale が実用的に使える
- redraw が telemetry ingest を阻害しない
- dynamic text で column width が崩れない

### GUI-005. Recording Pipeline

目的:

- `recording_schema.md` に従った共通 CSV 記録を実装する

作業:

- file naming
- partial file handling
- CSV header metadata
- row append
- periodic flush

依存:

- `GUI-002`
- `CORE-002`

完了条件:

- mock sample でも actual adapter sample でも同じ schema で記録できる
- 強制終了時に partial file が残る

### GUI-006. Wired Adapter Integration

目的:

- `SerialSensorAdapter` を production adapter として実装する

作業:

- port discovery
- worker thread
- frame parser
- CRC validation
- `TelemetrySample` / `StatusSnapshot` / `DeviceCapabilities` への正規化

依存:

- `CORE-001`
- `CORE-002`
- `GUI-002`
- `FW-006`

完了条件:

- wired device へ connect / disconnect できる
- capabilities / status / telemetry / ack を処理できる
- parse error を warning として出せる

### GUI-007. BLE Adapter Integration

目的:

- `BleSensorAdapter` を production adapter として実装する

作業:

- scan / connect / disconnect
- legacy telemetry subscribe
- extension service discovery
- status / capabilities / event handling
- degraded mode fallback

依存:

- `CORE-001`
- `CORE-002`
- `GUI-002`
- `FW-007`

完了条件:

- BLE device へ connect / disconnect できる
- v1 extension service を使える
- extension service 不在時も telemetry-only degraded mode で動く

現状メモ:

- local Mac 上で `Scan -> Connect`、capabilities load、`Pump ON/OFF` request、manual `Get Status`、`Ping` は確認済み
- scan loop と connect loop の分離に伴う `Future attached to a different loop` は修正済み
- extension status / capabilities が使えない場合の degraded fallback はコード化済み
- disconnect 時の BLE notify / capabilities availability flags cleanup は実装済み
- `tools/ble_smoke.py` は reconnect cycles、`observe-duration`、telemetry continuity summary を扱える形に更新済み
- `tools/ble_backend_smoke.py` により fake client ベースの reconnect、event log、post-command status refresh 回帰を確認可能
- live disconnect / reconnect と telemetry continuity の追加実地確認が残る
- exec 環境では CoreBluetooth scan が CLI から安定しないため、live continuity の実地確認は `INT-004` の local GUI / hand-run path で扱う
- beta 扱いに向けた proposal は、`180 s` 以上の live session、session 中の `Pump ON/OFF` と `Get Status`、recording finalize、manual reconnect 1 回成功を最低線とする

### GUI-008. Warning and Session Log Hardening

目的:

- warning display only 方針を production quality にする

作業:

- warning severity 表示
- event log retention
- disconnect / sequence gap / parse error の整形
- UI banner / log table の調整

依存:

- `GUI-006`
- `GUI-007`

完了条件:

- 異常系を modal に頼らず追跡できる
- log pane で session 中の主要イベントを確認できる

現状メモ:

- warning log, telemetry health monitor, BLE backend reconnect smoke は実装済み
- GUI は disconnect 時に telemetry session summary を log 出力できるため、BLE manual continuity validation の観測補助として使える
- 残タスクは live BLE session の実地確認を通して、beta gate の許容値を確定すること

### GUI-009. Packaging Preparation

目的:

- release 前に Windows packaging へ移れる状態を作る

作業:

- dependency audit
- icons / metadata / version embedding
- PyInstaller spec の下準備
- relative resource path 整理

依存:

- `GUI-008`

完了条件:

- macOS local run と Windows packaging path の両方を意識した構成になっている
- PyInstaller 化に大きな阻害要因がない

現状メモ:

- `gui_prototype/zss_demokit_gui.spec` を追加し、`bleak.backends` と `pyqtgraph` を含む conservative な `onedir` packaging path を定義済み
- `gui_prototype/packaging_README.md` に local build smoke と Windows follow-up を整理済み
- macOS 上で `pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec` が成功し、`dist/zss_demokit_gui/` を生成できることを確認済み
- packaging metadata は `gui_prototype/src/app_metadata.py` に集約し、PyInstaller spec から Windows version resource を自動生成できる状態にした
- icon は `gui_prototype/assets/app_icon.*` に置かれた場合のみ自動で埋め込む optional path とした
- 初回 beta 方針は `onedir`, version `0.1.0-beta.1`, 配布名 `zss_demokit_gui_win64_beta1` とした
- geometric first-pass icon を `tools/generate_app_icon.py` で生成し、`app_icon.png` / `app_icon.ico` を asset 化済み
- 残タスクは final art direction の要否判断と Windows 実機 smoke の 2 点

### GUI-010. User Feedback Integration and UX Parity

目的:

- 実機 user test で見えた GUI の使い勝手差分を、次の hardening フェーズで計画的に回収する

作業:

- wired mode でも BLE mode と同じ manual plot interaction を保証する
- plot history の retention policy を見直し、数分で古い表示が消えないようにする
- `example_gui` に寄せた dark visual theme へ戻す
- `SettingsDialog` からの BLE / Wired mode switch を仕様どおり機能させる
- BLE device / serial port のフィルタリングと auto-preselect を導入する

依存:

- `GUI-003`
- `GUI-004`
- `GUI-006`
- `GUI-007`
- `GUI-008`

完了条件:

- BLE / Wired の両モードで manual pan / zoom / scale が同じ感覚で使える
- plot の古い履歴が数分で暗黙に消えない
- visual theme が `example_gui` の dark direction に整合する
- settings 経由の mode switch が launcher 以外の正式導線として動く
- intended device が connection UI で自動的に絞り込まれ、1 候補なら preselect される

## 7. Firmware Backlog

### FW-001. Replace Placeholder Firmware Skeleton

目的:

- top-level `src/main.cpp` の雛形を新 firmware の入口へ置き換える

作業:

- project-level source tree 作成
- board init
- serial monitor / logging init
- capability constants の定義

依存:

- なし

完了条件:

- root PlatformIO project が実装対象の firmware project として成立する
- placeholder code が消えている

### FW-002. Shared Measurement Core Extraction

目的:

- `resource/old_firmware` から再利用可能な sensor / pump / status 周辺を抽出する

作業:

- `ADCManager`
- `PumpManager`
- `StatusLED`

の再配置または再設計を行う。

依存:

- `FW-001`

完了条件:

- measurement, pump, led が transport 非依存で呼べる
- old_firmware 由来の board-specific 知識が局所化されている

現状メモ:

- top-level firmware は old_firmware 由来の board pin を `BoardConfig` へ移し、pump pin、I2C pin、ADC pin、sensor power enable pin を集約済み
- `AdcFrontend` は ADS1115 + internal ADC を使う実測 path 初版へ更新済み
- 現在の接続実機では external ADS1115 read が成立しておらず、zirconia / RTD は `NaN`、status flag には ADC / sensor fault が反映される
- `StatusLedController` はまだ simple GPIO placeholder のままで、WS2812B 向け再設計が残る

### FW-003. State Model and Payload Builder

目的:

- firmware 内部 state と protocol payload 構築を分ける

作業:

- `AppState`
- `StatusFlags`
- `TelemetryMeasurements`
- `StatusSnapshot`
- `CapabilitiesBuilder`

相当の構造体 / class を定義する。

依存:

- `CORE-001`
- `FW-002`

完了条件:

- telemetry / status / capabilities を 1 箇所で組み立てられる
- transport 実装は builder の結果だけ参照すればよい

### FW-004. Deterministic Sampling Scheduler

目的:

- old_firmware の `50 ms` ばらつき課題を解消するため、deadline-based scheduler を導入する

作業:

- `next_sample_deadline += period` 型の周期管理
- overrun detection
- sequence increment policy
- sample time observation hooks

依存:

- `FW-003`

完了条件:

- measurement 周期が `last = now` 型より安定している
- overrun を status flag / event に反映できる

### FW-005. Command Processor

目的:

- BLE / wired 共通の論理 command を 1 箇所で扱う

作業:

- `get_capabilities`
- `get_status`
- `set_pump_state`
- `ping`

の dispatcher 実装。

依存:

- `FW-003`

完了条件:

- transport layer は command id を command processor に渡すだけでよい
- pump state 変更と status 要求が共通処理で動く

### FW-006. Wired Binary Transport

目的:

- `wired_transport_v1.md` 準拠の serial binary framing を実装する

作業:

- frame encoder / decoder
- SOF resync
- CRC-16/CCITT-FALSE
- request / ack / telemetry / status / capabilities / event

依存:

- `CORE-001`
- `FW-003`
- `FW-005`

完了条件:

- host と `115200 8N1` で通信できる
- `10 ms` telemetry path が動く
- parse / execution error を error frame に変換できる

### FW-007. BLE v1 Transport and Legacy Compatibility

目的:

- `ble_transport_v1.md` 準拠の telemetry と extension service を実装する

作業:

- legacy telemetry characteristic
- legacy pump opcodes
- extension service
- status snapshot characteristic
- capabilities characteristic
- event characteristic

依存:

- `CORE-001`
- `FW-003`
- `FW-005`

完了条件:

- telemetry notify が動く
- `Get Status` と `Get Capabilities` が新 GUI から使える
- legacy `0x55` / `0xAA` が継続して使える

現状メモ:

- legacy service / characteristic と extension service の firmware 側実装は着手済み
- top-level firmware は BLE telemetry notify、legacy opcode queue、status / capabilities characteristic を持つ
- host-side live smoke は GUI adapter 実装または `tools/ble_smoke.py` による再確認待ち

### FW-008. Diagnostics and Event Emission

目的:

- warning display only 方針を支える event / diagnostic 出力を firmware 側に持たせる

作業:

- boot complete
- warning raised / cleared
- adc fault
- processing overrun
- optional diagnostic bits

依存:

- `FW-004`
- `FW-006`
- `FW-007`

完了条件:

- GUI が warning の起点を識別できる
- telemetry 以外の異常系イベントを transport へ載せられる

現状メモ:

- serial / BLE transport の両方で `event` publish path は実装済み
- firmware は `command_error`、`warning_raised / cleared`、`adc_fault_raised / cleared` を emit できる
- wired 実機 smoke では GUI warning log まで `command_error` と `warning_raised` が到達することを確認済み
- boot complete と richer diagnostic bits は今後の hardening 項目として残る

### FW-009. Board Bring-Up and Sanity Checks

目的:

- M5StampS3A 上で新 firmware の最低限動作を確認する

作業:

- sensor read sanity
- pump drive sanity
- BLE advertise sanity
- serial output sanity

依存:

- `FW-002`
- `FW-006`
- `FW-007`

現状メモ:

- M5StampS3A への build / upload は継続して成功
- wired transport は board pin 反映後も `Pump ON/OFF`、status、telemetry、event まで end-to-end で継続動作
- ADS1115 配線見直し後の実機では zirconia / RTD も finite 値を返し、status flags は fault なしで動作することを確認済み
- `tools/wired_timing_probe.py` により wired `10 ms` path の host-side inter-arrival と sequence gap を継続観測できる

完了条件:

- board 上で measurement / pump / transport の基本動作を確認できる

### FW-010. Timing and Soak Validation

目的:

- 周期安定性と長時間運用を確認する

作業:

- sample interval logging
- jitter / gap measurement
- continuous run test
- pump on/off repetition test

依存:

- `FW-004`
- `FW-009`

完了条件:

- BLE の周期ばらつきが観測できる
- wired `10 ms` path が継続運用で破綻しない
- overrun / fault が UI 側で見える形で再現確認できる

現状メモ:

- `tools/wired_timing_probe.py --samples 1200 --warmup 20` により initial timing probe を実施済み
- current run では `1200` samples、non-unit sequence gap `0`、host inter-arrival `mean=9.131 ms / p95=20.095 ms / max=20.320 ms` を観測
- host inter-arrival は USB / host buffering の影響を含むため、device-side cadence は sequence gap と併せて評価する
- `tools/wired_soak_probe.py --duration-s 30 --toggle-interval-s 2.5` により continuous run と pump repetition の初回実測を完了
- current soak run では `3001` telemetry samples、sequence gap `0`、`Pump ON/OFF` toggle `12` 回、telemetry 上の status flags は `[2, 3]` で安定した
- `tools/gui_wired_session_probe.py --duration-s 18 --toggle-interval-s 3` により offscreen GUI 経由の session-level stress 初回実測を完了
- current GUI session probe では `1909` telemetry samples、pump toggle request `5` 回、warning/error log `0`、final CSV `1740` rows、non-unit gap `0` を確認
- wired 側の次の深掘りは longer soak と GUI plot history / manual parity を含む session hardening、BLE 側の次の深掘りは live continuity / reconnect の長時間確認

## 8. Integration Backlog

### INT-001. Wired End-to-End Session

目的:

- GUI と wired firmware の最初の実接続を成立させる

依存:

- `GUI-006`
- `FW-006`

完了条件:

- connect
- capabilities
- status
- telemetry
- `Pump ON/OFF`
- recording

が 1 セッションで動く。

### INT-002. BLE End-to-End Session

目的:

- GUI と BLE firmware の最初の実接続を成立させる

依存:

- `GUI-007`
- `FW-007`

完了条件:

- scan / connect
- telemetry receive
- `Get Status`
- `Get Capabilities`
- `Pump ON/OFF`
- recording

が 1 セッションで動く。

### INT-003. Common Recording Verification

目的:

- BLE / wired の両方で記録フォーマットが共通に見えることを確認する

依存:

- `GUI-005`
- `INT-001`
- `INT-002`

完了条件:

- header metadata が両モードで揃う
- canonical fields が同一列で出る
- derived metric policy が記録される

### INT-004. BLE Live Continuity Manual Validation

目的:

- CoreBluetooth を使う live BLE continuity / reconnect を、local Mac の GUI 実行ベースで継続観測する

依存:

- `GUI-007`
- `GUI-008`
- `FW-007`

完了条件:

- `Scan -> Connect` 後に少なくとも数分の telemetry continuity を確認できる
- session 中に `Pump ON/OFF`、`Get Status`、recording を実行しても GUI warning log が不自然に荒れない
- manual disconnect / reconnect を 1 回以上実施し、capabilities / status / telemetry が再取得できる

現状メモ:

- basic `Scan -> Connect`、capabilities load、`Pump ON/OFF` request、manual `Get Status`、`Ping` は local Mac で確認済み
- current exec 環境では `BleakScanner.discover()` が無言終了するため、CLI automation ではなく GUI hand-run を正として継続確認する
- `tools/gui_ble_session_probe.py` を追加し、GUI と同じ `MainWindow + ConnectionController + RecordingController` 経路で `scan -> connect -> recording -> planned reconnect -> summary` を半自動で回せるようにした
- beta gate proposal:
  - `180 s` 以上の BLE live telemetry continuity を 1 session で確認する
  - session 中に `Pump ON/OFF`、`Get Status`、recording start/stop を各 1 回以上実施して成功する
  - manual disconnect / reconnect を同一 app run 内で 1 回以上実施し、capabilities / status / telemetry が `10 s` 以内に復帰する
  - planned reconnect を含む probe では `observed telemetry duration >= session duration - reconnect timeout budget` を目安とする
  - session summary 上で no unexpected disconnect、connected telemetry segment 内の `sequence_gap_total <= 5`、transient stall warning は多くても 1 回までを目安とする

### INT-005. Beta Gate

目的:

- beta candidate に進むための実装完了条件を満たす

依存:

- `INT-001`
- `INT-002`
- `INT-003`
- `GUI-008`
- `FW-010`

完了条件:

- 両 transport で接続・可視化・制御・記録が通る
- warning 表示が最低限機能する
- レイアウト退行がない
- Windows packaging 準備へ進める

## 9. 最初の着手セット

最初の着手セットは以下を推奨する。

1. `CORE-001`
2. `GUI-001`
3. `FW-001`
4. `FW-002`
5. `GUI-002`

理由:

- GUI と firmware を別々に前進させながら、後続の wired / BLE 実装で必要な基盤を先に固められる
- この順なら、次の会話からすぐに「どのタスクを実装するか」を選んで着手できる

## 10. 直近の確認ポイント

- wired 実機接続時の actual port behavior
- BLE extension service UUID の最終値
- flow sensor の正式換算式
- M5StampS3A 上での sampling / transport 競合の実測
