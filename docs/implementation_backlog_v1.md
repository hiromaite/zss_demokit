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

- `COMPLETE` 相当
- Windows 11 Pro 上で packaging と packaged app 実行を確認し、`Wired` / `BLE` の両モードで blocking issue なしを確認済み
- current focus は feature extension bundle の継続実装であり、現在は `EXT-006` end-to-end validation / operator hardening を進めている

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
| `GUI-007` | `COMPLETE` | `bleak` ベースの live BLE path は local Mac 実機 probe で continuity / reconnect / recording まで確認済み |
| `GUI-008` | `COMPLETE` | warning log、telemetry health monitor、BLE status fallback、session summary log を含む hardening を完了 |
| `GUI-009` | `COMPLETE` | Windows packaging 準備と Windows 11 Pro packaged app smoke を完了 |
| `GUI-010` | `COMPLETE` | user feedback integration と GUI parity hardening を回収済み。dark theme direction、settings mode switch flow、device auto-filter / preselect、manual plot parity、plot history retention、compact layout refinement を実装・確認 |

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
- GUI 側 BLE control write は `write with response` を使う方針へ更新し、firmware 側 control characteristic も `WRITE | WRITE_NR` を受けるよう harden した
- `tools/gui_ble_session_probe.py` は `Pump ON/OFF request 数` に加えて、実際の `pump_state ON/OFF` status 観測も pass 条件に含めるよう更新した
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
- beta2 packaging 方針は `onedir`, version `0.1.0-beta.2`, 配布名 `zss_demokit_gui_win64_beta2` とした
- geometric first-pass icon を `tools/generate_app_icon.py` で生成し、`app_icon.png` / `app_icon.ico` を asset 化済み
- Windows 11 Pro 上で packaging と packaged app 実行を確認し、`Wired` / `BLE` 両モードの smoke が通過
- 2026-05-03 release-readiness slice として、既存 `v0.1.0-beta.2` tag との衝突を避けるため
  next distribution candidate を `0.1.0-beta.3` / `zss_demokit_gui_win64_beta3` とし、
  `docs/release_notes_beta3.md` と
  `tools/release_readiness_check.py` を追加し、metadata / icon / PyInstaller spec /
  release docs の整合を packaging 前に確認できるようにした
- 残タスクは final art direction の要否判断、installer / signing / updater policy の最終化

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
- `boot_complete` event は emit 済みで、`detail_u32` には diagnostic bits を載せる方針へ更新した
- telemetry payload の `diagnostic_bits` には boot / measurement core / external ADC / transport ready / session observed / telemetry published の bit を載せる実装を追加した
- 次の hardening は diagnostic bits を host-side visibility や実機 monitor 観測へつなぐこと

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

## 11. Post-Beta Extension Backlog

beta 到達後の次フェーズでは、以下の順で bundle 単位に進めることを推奨する。

### 11.1 Priority Order

1. `EXT-001` Firmware UX parity `COMPLETE`
2. `EXT-002` GUI recording emphasis `COMPLETE`
3. `EXT-003` O2 1-cell display and calibration `COMPLETE`
4. `EXT-004` Dual-SDP differential pressure PoC `COMPLETE`
5. `EXT-005` Flow telemetry integration `COMPLETE`
6. `EXT-006` End-to-end validation and operator hardening `IN_PROGRESS`
7. `EXT-007` System usability and engineering-tools hardening `PLANNED`

### EXT-001. Firmware UX Parity

目的:

- 旧 firmware にあった operator-facing parity を、現行 architecture を壊さずに回収する

対象:

- local physical button pump toggle
- BLE advertising / connected LED pattern
- voltage-target aware LED behavior
- ADS1115 channel 0 based `zirconia_ip_voltage_v` local readback

推奨依存:

- 現行 `CommandProcessor`
- 現行 `StatusLedController`
- 現行 `AdcFrontend`

完了条件:

- local button, BLE, wired のどの command source でも pump state が一貫する
- LED が advertising / connected / fault / voltage-target state を区別して示す
- `zirconia_ip_voltage_v` に基づく target band 判定が動く

現状メモ:

- initial code path は実装済み
- `InputButtonController` を追加し、local button event を `CommandProcessor` へ `Local` source command として流す構成にした
- `AdcFrontend` は ADS1115 ch0 の `zirconia_ip_voltage_v` 読み取りを復活済み
- `StatusLedController` は WS2812 state machine に置き換え、fault / overrun / BLE advertising / BLE connected / voltage-target behavior を持つ
- KNF `NMP03 KPDC-B3` 向けに `PumpController` を PWM 出力へ更新し、`20 kHz`, `10-bit`, `OFF=0 %`, `ON=50 %` の duty policy を採用した
- PWM 化後の `pio run`、upload、`tools/protocol_fixture_smoke.py`、`tools/wired_serial_smoke.py --port /dev/cu.usbmodem3101 --baudrate 115200` は通過済み
- command path 上は `pump_on` status の遷移と command error handling まで継続動作を確認済み
- Bundle close-out 中に BLE 実機 pump control、mode switch、settings dialog crash fix まで含めて operator feedback を回収した
- EXT-001 は完了扱いとし、以後の residual 調整は regression fix として扱う

### EXT-002. GUI Recording Emphasis

目的:

- recording active を GUI 上で glanceable にする

対象:

- recording group glow / accent
- active / inactive state の視認性改善

完了条件:

- narrow layout を壊さず recording active が一目で分かる

検証方針:

- offscreen GUI smoke で active / inactive の visual state 遷移を確認する
- local 実行で narrow window 時の panel 強調が layout を崩さないことを確認する

現状メモ:

- `Recording` panel に専用 accent state を追加した
- `REC ACTIVE` badge と session detail text により active / inactive を glanceable にした
- recording toggle button に専用 visual treatment を追加した
- `python3.12 -m compileall gui_prototype/src/main_window.py gui_prototype/src/theme.py` を実施済み
- `./.venv_gui_prototype/bin/python` による offscreen `recording_emphasis_smoke_ok` を確認済み
- EXT-002 は完了扱いとし、以後の調整は GUI polish / regression fix として扱う

### EXT-003. O2 1-Cell Display and Calibration

目的:

- `zirconia_output_voltage_v` を元に `O2 Concentration (1-cell)` を GUI 派生値として追加する

対象:

- O2 numeric display
- ambient-air calibration button
- calibration reset
- calibration persistence

推奨式:

```text
normalized = (v_zero_ref - v_measured) / (v_zero_ref - v_air_cal)
o2_percent = clamp(normalized * 21.0, 0.0, 100.0)
```

補足:

- `v_zero_ref` は GUI の Device settings で調整可能にし、prototype wiring / analog frontend の0%基準に合わせる

現状メモ:

- GUI first pass は実装済み
- `O2 Concentration (1-cell)` metric card を追加した
- `Settings > Device` に ambient-air calibration / reset action を追加した
- calibration anchor と timestamp は `QSettings` に永続化される
- `python3.12 -m compileall gui_prototype/src/app_state.py gui_prototype/src/settings_store.py gui_prototype/src/protocol_constants.py gui_prototype/src/dialogs.py gui_prototype/src/main_window.py` を実施済み
- `./.venv_gui_prototype/bin/python` による offscreen `o2_bundle_c_smoke_ok` を確認済み
- essential function の operator validation は完了済み
- 現時点では polarity reverse は不要と判断し、EXT-003 は close 扱いとする

完了条件:

- calibration 後に ambient air で `21 %` 近傍を示す
- uncalibrated 状態が UI で明示される

### EXT-004. Dual-SDP Differential Pressure PoC

目的:

- `SDP811-500Pa-D` と `SDP810-125Pa` の dual-range differential pressure sensing を実機で成立させる

対象:

- I2C coexistence
- continuous read
- CRC validation
- selector / hysteresis

完了条件:

- low/high sensor が同一 bus で安定読取りできる
- no-flow / low-flow / higher-flow で両系列ログが取れる
- selector の threshold 候補を決められる

現状メモ:

- `Sdp8xxSensor` driver を追加し、continuous differential-pressure mode、CRC validation、product identifier read、temperature / scale factor decode を持たせた
- `DifferentialPressureFrontend` を追加し、`SDP810-125Pa` / `SDP811-500Pa` の dual-sensor readout と hysteresis-based selector の土台を実装した
- board constants に I2C address、product prefix、selector threshold を追加した
- `MeasurementCore` に differential pressure frontend を観測専用で接続し、firmware summary log に `DpSel`, `Dp125`, `Dp500` を出すところまで進めた
- current slice では transport payload へはまだ統合していない
- `pio run` と `/dev/cu.usbmodem3101` への upload は通過済みで、boot / summary log 上で dual-SDP frontend の観測が成立している
- `tools/sdp_serial_probe.py --port /dev/cu.usbmodem3101 --duration-s 8` により no-flow baseline を取得し、`DpSel mean=-0.0514 Pa`, `Dp125 mean=-0.0514 Pa`, `Dp500 mean=-0.0586 Pa`, selector は low-range `7/7` を確認した
- 追加の実機観測で low-flow / medium-flow / high-flow / return-to-no-flow を取得し、selector activity と return-side hysteresis を確認した
- current decision として EXT-004 は close 扱いにし、以後は EXT-005 の transport / GUI integration に進む

### EXT-005. Flow Telemetry Integration

目的:

- dual-SDP PoC の結果を flow feature として GUI / firmware に統合する

対象:

- `differential_pressure_selected_pa` 導入
- flow placeholder 式を differential pressure ベースへ更新
- 必要なら telemetry v2 を追加

完了条件:

- GUI flow rate が selected differential pressure を元に計算される
- handoff 時に plot が破綻しない

現状メモ:

- GUI 側は `TelemetryPoint.differential_pressure_selected_pa` を optional field として受け取れるよう更新済み
- `PlotController` と `RecordingController` は `selected differential pressure` のみを使って flow rate を算出する
- firmware transport では packet size を広げず、`telemetry_field_bits bit3` を使って既存 `flow_sensor_voltage_v` slot を `differential_pressure_selected_pa` として再解釈する互換拡張を採用した
- BLE / wired decoder は bit3 を見て `differential_pressure_selected_pa` を復元する
- raw `SDP810 / SDP811` は diagnostic field として CSV にも保存し、BLE では batch schema v2で取得できる場合に保存、legacy/unavailable 時は空欄とする
- `./.venv_pio/bin/pio run`、`python3.12 -m compileall gui_prototype/src/protocol_constants.py gui_prototype/src/ble_protocol.py gui_prototype/src/wired_protocol.py gui_prototype/src/mock_backend.py gui_prototype/src/controllers.py`、`python3.12 tools/protocol_fixture_smoke.py` は通過済み
- `/dev/cu.usbmodem3101` への upload 後、`python3.12 tools/wired_serial_smoke.py --port /dev/cu.usbmodem3101 --baudrate 115200` により `telemetry_field_bits=15` と finite `differential_pressure_selected_pa` を live wired で確認済み
- `python3.12 tools/gui_wired_session_probe.py --port /dev/cu.usbmodem3101 --duration-s 8 --toggle-interval-s 2.5` も `gui_wired_session_probe_ok` で通過済み
- current decision として EXT-005 は close 扱いにし、以後の BLE-side operator confirmation は EXT-006 の validation task に含める
- plan adjustment として、flow calibration / selector tuning は hardware 完成後へ defer し、現段階では dummy flow law を維持する
- hardware bring-up を支援するため、next step では wired GUI に `SDP811` / `SDP810` raw value を一時表示し、transport / UI 上で差圧の各 channel を観察しやすくする

### EXT-006. End-to-End Validation and Operator Hardening

目的:

- parity restore と新規値表示を operator-ready な水準まで固める

対象:

- local button + GUI + BLE / wired coexistence
- LED state priority
- O2 calibration workflow
- dual-SDP flow display
- BLE / wired の operator-facing flow validation
- long-run recording / plot behavior under mixed UI states

現状メモ:

- Bundle F の最初の operator tool として `tools/wired_flow_probe.py` を追加した
- probe は transport-level の `selected differential pressure` と `derived flow rate` を集計し、
  no-flow / low-flow / medium-flow / high-flow を同じ観測軸で比較できる
- no-flow baseline は `python3.12 tools/wired_flow_probe.py --port /dev/cu.usbmodem4101 --duration-s 4` で通過済みで、
  `telemetry_field_bits=63`、finite `selected differential pressure`、finite `SDP810 / SDP811 raw` を確認した
- final calibration / selector tuning は hardware 完成後に行う前提へ変更した
- hardware bring-up 支援として、GUI の flow card detail に `SDP811` / `SDP810` raw value を live 表示できるようにした
- selected differential pressure の source (`SDP810` / `SDP811`) を GUI detail と CSV から追えるよう更新した
- service visibility の first slice として、wired-first diagnostics に `zirconia_ip_voltage_v` / `internal_voltage_v` の optional field を追加し、GUI `Device Status` と CSV へ配線した
- current board config では `internal_voltage_v` path は disabled のため live value unavailable を想定し、GUI / CSV は空欄・`--` で扱う
- signed flow placeholder を採用し、呼気/吸気の両方向を持つ前提で表示・記録する
- `Flow Verification` の実装方針として、`Settings > Device` から guided verification wizard を起動する設計を採用する
- guided verification は `Zero Check`, `Exhalation Low`, `Inhalation Low`, `Exhalation Medium`, `Inhalation Medium`, `Exhalation High`, `Inhalation High`, `Review` の 9-step flow を想定する
- v1 verification は soft advisory ベースとし、strict gate による workflow block は採用しない
- `FlowVerificationController`, `VerificationSession`, `VerificationStrokeResult`, `ZeroCheckResult` を中核にする設計方針を採用する
- 詳細設計は `flow_verification_plan_v1.md` を参照する
- first implementation slice として、controller / dialog / JSON persistence / settings entry をコード化した
- follow-up slice として、`Show Latest Details` button と latest saved session details dialog を追加し、saved JSON record の operator review 導線を実装した
- non-hardware polish slice として、`Show History` button、recent session preview、review guidance message を追加し、PoC session の比較と振り返りをしやすくした
- current slice では offscreen smoke により controller-driven capture path、settings entry、dialog skeleton、latest details dialog、history dialog を確認済みである
- hardware 完成後の low / medium / high flow sweep は、まず開発用 `Flow Characterization (PoC)` wizard で raw `SDP810 / SDP811 / selected` を保存し、
  センサー極性と `SDP810` abs pressure の handoff review band (`90-110 Pa`) を判断する入力データを作る
- `Flow Characterization (PoC)` は `Zero Baseline`, `Small Exhale`, `Small Inhale`, `Maximum Exhale`, `Maximum Inhale` を手動 capture し、
  JSON metadata と sample-level CSV を保存する方針にする
- 2026-05-03 の実機 characterization で current hardware の `SDP811` high-range は `SDP810` low-range と逆極性であることを確認したため、board config に pressure polarity 係数を置き、firmware 側で high-range pressure を canonical telemetry へ格納する時点で反転する
- 補正後の実機 run では small flow は `SDP810` selected、maximum flow は `SDP810` abs 約 `111 Pa` で `SDP811` へ切替、約 `95-99 Pa` で `SDP810` へ復帰し、`Low/high sign consistency: consistent` を確認した
- next step は得られた raw response と rough scale estimate をもとに、formal flow calibration と selector threshold tuning の別フェーズへ移行することである

完了条件:

- 実機で一連の operator workflow が破綻しない
- warning / event / UI state が互いに矛盾しない

### EXT-007. System Usability and Engineering-Tools Hardening

目的:

- beta2 相当までに増えた operator 機能、engineering diagnostics、verification / characterization workflow を整理し、
  現場で迷いにくい GUI と regression に強い system にする

参照:

- `system_usability_review_v1.md`

推奨優先順:

1. pump / heater interlock を regression checklist として固定する
2. diagnostic bits / optional diagnostic fields を GUI 上で operator-readable label として見せる
3. plot pause / freeze と series visibility toggle を追加する
4. Settings 内の device tools を `Operator settings` と `Engineering / Tools` に分ける
5. Windows / low-resolution visual validation を checklist 化する
6. recording latest summary、open folder、quick review など post-run UX を追加する
7. verification / characterization history comparison を強化する
8. `main_window.py` / `dialogs.py` の module split を進める

完了条件:

- operator が通常測定に必要な操作だけを短い導線で実行できる
- engineering diagnostics は隠れすぎず、通常操作画面を圧迫しない
- BLE / Wired で availability が違う optional fields が誤解なく表示される
- Windows / low-resolution 環境で layout overlap や意図しない scroll が再発しない

現状メモ:

- 2026-04-30 の system usability review では、現時点の blocking issue は見つかっていない
- flow の最終 calibration / selector tuning は hardware completion 待ちであり、EXT-007 では UX と regression hardening を先行する
- firmware の pump / heater safety interlock は実装済みだが、今後の regression protection として明示的に追跡する
- 2026-05-02 の追加課題群は `active_development_bundles_v1.md` に bundle / branch 単位で整理し、実機確認ができない期間でも進められる作業から分岐開発する
- 2026-05-03 first slice として、`tools/command_processor_smoke.py` で pump / heater interlock を host-side regression に固定し、
  Device Status に raw SDP / service voltage / BLE batch availability label を追加した
- 2026-05-03 second slice として、Plot Toolbar に `Pause Plot` と series visibility toggle を追加し、
  acquisition / recording を継続したまま operator が plot 表示だけを freeze / 整理できるようにした。次は Settings の Engineering / Tools 整理か Windows / low-resolution visual validation が候補
- 2026-05-03 third slice として、Settings nav に `Engineering / Tools` を追加し、routine operator setting と engineering workflow を分離した。
  `Device` は connection summary / O2 calibration に寄せ、Flow Verification / Characterization / on-demand diagnostics は tools page から起動する
- 2026-05-03 fourth slice として、`tools/gui_layout_smoke.py` を追加し、tall desktop / default / Windows common / compact HD / narrow lab sizes で
  horizontal scroll、metric cards row、metric / toolbar compact height、plot splitter minimum height / tall-window growth / resize response を offscreen regression として固定した
- 2026-05-03 fifth slice として、Recording panel に latest CSV summary、`Open Folder`、`Copy CSV Path` を追加した。
  recording stop 後に rows / duration / sequence range / gap / size をすぐ確認でき、CSV の保存先へ短い導線で移動できる
- 2026-05-03 sixth slice として、Warning / Event Log に severity filter、text search、visible copy、CSV export を追加した。
  user report や debug session の切り出しを軽くし、`tools/gui_log_history_smoke.py` で filter / copy / export を固定した
- 2026-05-03 seventh slice として、Flow Verification / Flow Characterization history comparison を追加した。
  Verification は mean / max volume error、out-of-target / skipped、source switch の変化を比較し、Characterization は capture completion、polarity、low/high consistency、selected peak、rough gain の変化を比較する。
  どちらも history summary CSV export を持ち、hardware 完成後の調整判断材料を蓄積しやすくした
- 2026-05-03 eighth slice として、GUI module split を進め、flow history dialogs、
  event log panel、generic UI helpers、plot interaction helpers、dialog helpers を分離した
- 2026-05-03 release-readiness slice として、beta3 release notes と release readiness
  metadata / document smoke を追加した。既存 `v0.1.0-beta.2` tag は維持し、次の配布は
  `0.1.0-beta.3` として扱う。installer / signing / updater は formal release 前の
  separate decision として残す

直近 bundle:

| Bundle | Status | Notes |
| :--- | :--- | :--- |
| `A` Diagnostics | `PLANNED` | pump noise / timing jitter の観測基盤 |
| `B` Windows serial handshake | `PLANNED` | COM open と protocol handshake を分離 |
| `C` Connection UX | `PLANNED` | auto-connect, scan/connect state, device label |
| `D` Plot / performance | `PLANNED` | fixed range, manual secondary axis, smooth follow, UI throttle |
| `E` Sampling architecture | `PLANNED` | RTOS task split and BLE batch design / PoC |
