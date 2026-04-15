# Validation Checklist v1

## 1. 目的

本書は、現時点の実装段階で実施可能な検証項目を整理し、
実施結果を残すためのチェックリストである。

対象段階:

- GUI prototype + protocol constants 導入後
- firmware skeleton + top-level PlatformIO project 置換後
- wired transport は firmware / host 側で smoke test 可能な段階
- BLE transport は firmware 側に最小実装が入り、host 側 smoke は準備済み

## 2. ステータス定義

- `PASS`: 期待どおりに確認できた
- `FAIL`: 実施したが期待どおりではなかった
- `BLOCKED`: 環境や未実装のため現時点では確認不能
- `TODO`: まだ未実施

## 3. 現段階での検証方針

- 最優先は「土台が壊れていないこと」の確認とする
- GUI は import / 起動 / 画面生成の smoke test を中心に確認する
- firmware は build / upload / boot / serial log / scheduler の smoke test を中心に確認する
- wired は実機 serial path で end-to-end smoke を進める
- BLE は firmware transport の build / boot / advertise までは進め、GUI adapter 実装までは integration を `BLOCKED` とする

## 4. GUI Checklist

| ID | Item | Expected Result | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `GUI-VAL-001` | Python compile check | `gui_prototype/` が compile できる | `PASS` | `python3.12 -m compileall gui_prototype` 実施済み |
| `GUI-VAL-002` | Offscreen launcher smoke | `LauncherWindow` が生成できる | `PASS` | Qt offscreen で生成確認済み |
| `GUI-VAL-003` | Offscreen main window smoke | `MainWindow(BLE)` が生成できる | `PASS` | Qt offscreen で生成確認済み |
| `GUI-VAL-004` | Protocol constants wiring | UI / mock backend が共通 constants を参照して動く | `PASS` | `protocol_constants.py` 導入後の compile / smoke を通過 |
| `GUI-VAL-005` | Layout regression smoke | compact launcher / no top bar / stable column width 方針が維持される | `PASS` | 既存の承認済みレイアウトに対し constants 導入後も起動回帰なし |
| `GUI-VAL-006` | Wired backend smoke | `Wired` モード backend が実機 serial transport と接続できる | `PASS` | `MockBackend(Wired)` による `capabilities / status / telemetry` 受信 smoke を通過 |
| `GUI-VAL-007` | Recording pipeline smoke | `Start/Stop Recording` が partial/final CSV を正しく扱う | `PASS` | BLE mock / Wired 実機の両方で header + data rows + finalize を確認 |
| `GUI-VAL-008` | Settings persistence smoke | plot / logging / window settings が再起動後も保持される | `PASS` | offscreen smoke で `QSettings` の save / load を確認 |
| `GUI-VAL-009` | Partial recovery dialog smoke | configured recording directory に対して partial 検出が動く | `PASS` | launcher / dialog の両方で configured directory を参照することを確認 |
| `GUI-VAL-010` | Controller boundary smoke | `MainWindow` が connection / plot / recording / warning controller と協調して動く | `PASS` | offscreen smoke と wired connect smoke で controller 経由の更新を確認 |
| `GUI-VAL-011` | BLE window startup smoke | `MainWindow(BLE)` が auto-scan なしで安定起動する | `PASS` | offscreen smoke で `Scan` button 起点へ整理後も起動確認 |
| `GUI-VAL-012` | Telemetry health monitor smoke | delayed start / stalled stream が warning log 条件として検出できる | `PASS` | `TelemetryHealthMonitor` の direct smoke で waiting / stalled / recovered を確認 |
| `GUI-VAL-013` | BLE backend reconnect smoke | BLE backend が reconnect / event log / post-command status refresh を維持する | `PASS` | `tools/ble_backend_smoke.py` で fake client による connect / disconnect / reconnect / `Pump ON/OFF` / `Ping` を確認 |
| `GUI-VAL-014` | Wired manual plot parity | wired mode でも BLE mode と同じ manual pan / zoom / scale が使える | `PASS` | axis/viewbox manual interaction hook を追加し、helper smoke で `x_follow` 解除と manual Y range 化を確認 |
| `GUI-VAL-015` | Plot history retention | 数分以上の session でも古い plot data が暗黙に消えない | `PASS` | `PlotController` を time-based history retention へ変更し、helper smoke で `1800 s / 180000 points` retention を確認 |
| `GUI-VAL-016` | Settings mode switch flow | `SettingsDialog` から BLE / Wired mode switch を実行できる | `PASS` | helper smoke で `Save and Switch` 表示と mode switch 後の `Mode switched to Wired.` log を確認 |
| `GUI-VAL-017` | Device filtering and preselect | intended device / port が自動的に絞り込まれ、候補が 1 つなら preselect される | `PASS` | backend filter/preselect logic を追加し、`M5STAMP-MONITOR*` と `usbmodem/usbserial` 候補が優先されることを helper smoke で確認 |
| `GUI-VAL-018` | Visual theme parity | GUI theme が `example_gui` の dark direction に整合する | `PASS` | stylesheet を dark blue/slate direction へ更新し、theme 変更後も GUI session probe が継続動作することを確認 |
| `GUI-VAL-019` | Wired GUI session probe | offscreen GUI 経由で wired connect / recording / pump toggle / CSV finalize が継続する | `PASS` | `tools/gui_wired_session_probe.py --duration-s 18 --toggle-interval-s 3` で `1909` telemetry、CSV `1740` rows、non-unit gap `0` を確認 |

## 5. Firmware Checklist

| ID | Item | Expected Result | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `FW-VAL-001` | PlatformIO build | `pio run` が成功する | `PASS` | local `.venv_pio` 上の `pio run` で成功 |
| `FW-VAL-002` | PlatformIO upload | 実機へ upload できる | `PASS` | `/dev/cu.usbmodem5101` へ upload 成功 |
| `FW-VAL-003` | Boot log | serial monitor に boot log が出る | `PASS` | monitor 再接続後に boot 相当の初期ログを確認 |
| `FW-VAL-004` | Capability preview log | BLE / serial capability preview が出る | `PASS` | boot log で `BLE caps: period=80 ms max_payload=32` と `Serial caps: period=10 ms max_payload=64` を確認 |
| `FW-VAL-009` | BLE advertise boot sanity | BLE stack 初期化後も boot / loop が継続する | `PASS` | serial log で BLE advertising 初期化後も summary log 継続を確認 |
| `FW-VAL-005` | Sampling summary log | summary log が一定周期で出る | `PASS` | 約 1 秒周期で `Sample` log を観測 |
| `FW-VAL-006` | Sequence monotonicity | `seq` が単調増加する | `PASS` | `seq=10, 23, 35, ...` と単調増加を確認 |
| `FW-VAL-007` | Scheduler alive | sample log が継続出力される | `PASS` | 数十秒継続して summary log を観測 |
| `FW-VAL-008` | Crash-free idle run | 数秒間クラッシュしない | `PASS` | upload 後の idle run でクラッシュなし |
| `FW-VAL-010` | ADC fault reflection | external ADC が取れない場合でも fault flag と telemetry が破綻せず維持される | `PASS` | current hardware では zirconia / RTD が `NaN` だが、ADC / sensor fault flag を立てつつ wired transport と command path は継続動作 |
| `FW-VAL-011` | ADS1115 live measurement sanity | ADS1115 配線後に zirconia / RTD が finite 値で読める | `PASS` | `wired_serial_smoke` で zirconia / RTD が `NaN` ではなく finite 値を返し、status flags も fault なしを確認 |
| `FW-VAL-012` | Wired timing probe | wired `10 ms` path を sequence gap と host inter-arrival で観測できる | `PASS` | `tools/wired_timing_probe.py --samples 1200 --warmup 20` で `1200` samples、gap `0`、host inter-arrival `mean=9.131 ms / p95=20.095 ms / max=20.320 ms` を確認 |
| `FW-VAL-013` | Wired soak probe | `30 s` continuous run と periodic `Pump ON/OFF` repetition が破綻せず継続する | `PASS` | `tools/wired_soak_probe.py --duration-s 30 --toggle-interval-s 2.5` で `3001` telemetry samples、gap `0`、toggle `12` 回、status flags `[2, 3]` を確認 |

## 6. Integration Checklist

| ID | Item | Expected Result | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `INT-VAL-001` | BLE scan / connect | GUI から BLE 接続できる | `PASS` | user の local Mac 実機確認で `Scan -> Connect -> capabilities load` を確認 |
| `INT-VAL-002` | wired connect | GUI から serial 接続できる | `PASS` | `MockBackend(Wired)` の実機 smoke で `/dev/cu.usbmodem5101` 接続を確認 |
| `INT-VAL-003` | Pump ON/OFF end-to-end | GUI command が実機動作へ届く | `PASS` | `tools/wired_serial_smoke.py` で `SetPumpState` と status flag 反映を確認 |
| `INT-VAL-004` | Get Status end-to-end | GUI で status snapshot を取得できる | `PASS` | wired backend smoke と host smoke の両方で `status_snapshot` を確認 |
| `INT-VAL-005` | Shared CSV recording | 実データを共通 schema で保存できる | `PASS` | BLE mock と wired 実機の両方で `.partial.csv -> .csv` finalize と schema header を確認 |
| `INT-VAL-006` | Wired 10 ms transport validation | `10 ms` path を end-to-end 検証できる | `PASS` | `wired_serial_smoke` と wired backend smoke で `nominal_sample_period_ms=10` を確認 |
| `INT-VAL-007` | BLE 50-100 ms validation | BLE telemetry 周期を検証できる | `TODO` | live telemetry continuity / period observation は追加確認待ち。`tools/ble_smoke.py` は reconnect cycles、`--observe-duration`、inter-arrival summary を出力可能だが、この exec 環境では CoreBluetooth discover が無言終了するため live CLI 実測は保留 |
| `INT-VAL-008` | Wired event propagation | firmware event が GUI warning log に届く | `PASS` | `command_error` と `warning_raised` を wired 実機 + GUI backend smoke で確認 |

## 7. 実施ログ

### 2026-04-08

- `python3.12 -m compileall gui_prototype` を実施し、GUI prototype の compile を確認
- Qt offscreen で `LauncherWindow` と `MainWindow(BLE)` の生成を確認
- local `.venv_pio` を作成し、PlatformIO を導入
- `pio run` により top-level firmware の build 成功を確認
- `pio run -t upload --upload-port /dev/cu.usbmodem5101` により M5StampS3 への upload 成功を確認
- `pio device monitor --port /dev/cu.usbmodem5101 --baud 115200` により runtime log を観測
- summary log はおおむね 1 秒周期で出力され、`seq` は単調増加、`overruns=0` を維持
- boot / capability preview は monitor reconnect 直後に観測。reconnect 窓のため先頭行の一部が欠ける場合あり
- `tools/wired_serial_smoke.py --port /dev/cu.usbmodem5101 --baudrate 115200` を実施し、`capabilities / status / telemetry / Pump ON/OFF` の wired end-to-end を確認
- serial capabilities の `max_payload_bytes` は実装値に合わせて `64` を広告するよう修正し、再 upload 後の smoke で確認
- `.venv_gui_prototype` 上で `MockBackend(Wired)` の backend smoke を実施し、GUI prototype から実機 serial transport を扱えることを確認
- GUI recording pipeline を実装し、offscreen smoke により BLE mock / wired 実機の両方で `Start Recording -> data rows -> Stop Recording -> final CSV` を確認

### 2026-04-14

- `python3.12 -m compileall gui_prototype/src gui_prototype/main.py` を実施し、settings / controller 分離後も compile を確認
- offscreen smoke で `LauncherWindow` が persisted window size と partial recovery notice flag を正しく読むことを確認
- offscreen smoke で `MainWindow` の plot defaults、recording directory、manual plot preferences が `QSettings` に保存 / 復元されることを確認
- `ConnectionController` 導入後の offscreen wired smoke を実施し、controller 経由でも `/dev/cu.usbmodem5101` から telemetry を継続受信できることを確認
- BLE mock recording smoke を実施し、configured recording directory に `.partial.csv -> .csv` finalize されることを確認
- top-level firmware に BLE transport の最小実装を追加し、legacy UUID と extension service を同時に advertise する構成へ更新
- `pio run` と `pio run -t upload --upload-port /dev/cu.usbmodem5101` を再実施し、BLE transport 追加後も build / upload 成功を確認
- serial log で BLE advertising 初期化後も boot と sampling summary が継続することを確認
- `tools/ble_smoke.py` を追加したが、この exec 環境では CoreBluetooth ベースの scan が即時終了してしまい、host-side live BLE smoke は未完了
- GUI 側に `bleak` ベースの live BLE path を追加し、BLE mode は manual `Scan` button 起点で device discovery を行う構成へ更新
- offscreen smoke で `MainWindow(BLE)` が auto-scan を走らせずに安定起動することを確認
- offscreen wired regression smoke で BLE adapter 追加後も wired path が継続動作することを確認

### 2026-04-15

- firmware scheduler を見直し、late sample 時は missed interval を数えつつ cadence を立て直す構成へ更新
- firmware に `command_error`、`warning_raised / cleared`、`adc_fault_raised / cleared` の event emission を追加
- serial transport に wired `event` frame publish を追加し、GUI 側にも wired event decode / warning log 反映を追加
- `python3.12 -m compileall gui_prototype/src tools/wired_serial_smoke.py` を再実施し、GUI 側 compile を確認
- `pio run` と `pio run -t upload --upload-port /dev/cu.usbmodem5101` を再実施し、event/scheduler 追加後も build / upload 成功を確認
- `tools/wired_serial_smoke.py --port /dev/cu.usbmodem5101 --baudrate 115200` を再実施し、unsupported command に対する `command_error` event 受信まで確認
- offscreen GUI backend smoke で wired 実機から `Wired event command_error` と `Wired event warning_raised` が warning log へ届くことを確認
- user の local Mac 実機確認で `M5STAMP-MONITOR` への BLE `Scan -> Connect`、capabilities load、`Pump ON/OFF` request、manual `Get Status`、`Ping` を確認
- BLE scan results は stable identifier を保持する方式へ修正し、`Future attached to a different loop` 問題を解消
- BLE live path に post-command status refresh、status direct-read fallback、capabilities degraded fallback を追加
- GUI に telemetry health monitor を追加し、初回 sample 遅延 / stalled stream / recovery を warning log 条件として扱うよう更新
- `TelemetryHealthMonitor` の direct smoke で `waiting`, `stalled`, `recovered` の各ログ条件を確認
- BLE disconnect cleanup の direct smoke で notify / capabilities availability flags が reset されることを確認
- `tools/ble_smoke.py` を reconnect cycles / telemetry continuity summary 対応へ更新し、CLI からも BLE live validation を繰り返し実施できるようにした
- `tools/ble_backend_smoke.py` を実施し、fake client ベースで BLE reconnect、event log、`Pump ON/OFF` 後の status update、telemetry monotonicity を確認
- `BoardConfig` に old_firmware 由来の pin mapping を反映し、`AdcFrontend` を ADS1115 + internal ADC の実測 path 初版へ更新
- `pio run`、`pio run -t upload --upload-port /dev/cu.usbmodem4101`、`tools/wired_serial_smoke.py --port /dev/cu.usbmodem4101 --baudrate 115200` を再実施し、board bring-up 後も wired transport が継続動作することを確認
- current hardware では external ADS1115 read が成立せず、`zirconia_output_voltage_v` / `heater_rtd_resistance_ohm` は `NaN`、status flags は ADC / sensor fault を示した
- `tools/wired_serial_smoke.py` は USB reopen 直後でも安定するよう初期待ちを延長し、target event code を追う形に強化
- ADS1115 配線見直し後に `pio run` と `tools/wired_serial_smoke.py --port /dev/cu.usbmodem4101 --baudrate 115200` を再実施し、zirconia / RTD が finite 値で取れることを確認
- `tools/wired_timing_probe.py --port /dev/cu.usbmodem4101 --baudrate 115200 --samples 1200 --warmup 20` を実施し、non-unit sequence gap `0` と host inter-arrival summary を取得
- timing probe の status flags `66` は直前の unsupported command smoke により `command_error_latched` が残った状態であり、probe 自体は transport continuity を正常に観測できた
- user feedback として、serial mode の manual plot parity、plot history retention、dark theme 回帰、settings mode switch、device auto-filter/preselect を次フェーズの GUI hardening 対象として記録
- `pio run -t upload --upload-port /dev/cu.usbmodem4101` で clean state に戻した後、`tools/wired_soak_probe.py --port /dev/cu.usbmodem4101 --baudrate 115200 --duration-s 30 --toggle-interval-s 2.5` を実施
- current soak run では `3001` telemetry samples、sequence `575 -> 3575`、non-unit gap `0`、telemetry 上の pump states `[False, True]`、status flags `[2, 3]`、pump toggle `12` 回を確認
- soak 中の host inter-arrival summary は `mean=9.996 ms / p95=20.083 ms / max=20.748 ms` で、host buffering を含みつつも continuity は維持された
- `tools/gui_wired_session_probe.py --port /dev/cu.usbmodem4101 --duration-s 18 --toggle-interval-s 3` を実施し、offscreen GUI 経由で wired connect、recording start/stop、`Pump ON/OFF` request、CSV finalize まで継続することを確認
- current GUI session probe では `1909` telemetry samples、pump toggle request `5` 回、warning/error log `0`、final CSV `1740` rows、non-unit gap `0` を確認
- `tools/ble_smoke.py` に `--observe-duration` を追加し、BLE continuity を reconnect cycle ごとに数秒以上観測できるよう更新
- helper smoke により BLE candidate filter と wired port filter の優先順位ロジックを確認し、`M5STAMP-MONITOR*` と `usbmodem/usbserial` が preselect 対象になることを確認
- exec 環境からの `BleakScanner.discover()` は `before discover` 出力後に無言終了するため、BLE live CLI continuity の実測は引き続きローカル GUI / 手元実行ベースで進める
- plot interaction helper smoke により bottom axis manual interaction 後の `x_follow=False`、left axis interaction 後の manual Y range 化を確認
- plot history helper smoke により `10 ms` 相当入力で `1800 s` の time-based retention と `180000` retained points を確認
- `tools/gui_wired_session_probe.py --port /dev/cu.usbmodem4101 --duration-s 10 --toggle-interval-s 2.5` を再実施し、manual/history 修正後も offscreen GUI wired session が継続動作することを確認
- settings dialog helper smoke により mode page の OK label が `Save Settings` / `Save and Switch` へ切り替わり、mode switch 後に connection stack と log が追従することを確認
- dark theme への stylesheet 更新後に `tools/gui_wired_session_probe.py --port /dev/cu.usbmodem4101 --duration-s 8 --toggle-interval-s 2.5` を再実施し、GUI wired session が継続動作することを確認
- graph performance feedback を受けて描画設定を再確認し、`antialias=True` が有効だったことを確認
- `pg.setConfigOptions(antialias=False)` へ変更し、あわせて `render_data()` を span-aware / downsample 対応へ更新して full-history `setData()` の負荷を削減
- helper smoke で `30 s=1501 points`, `2 min=3001 points`, `10 min=5455 points`, `All=7827 points` まで描画点数が抑制されることを確認
- 軽量化後に `tools/gui_wired_session_probe.py --port /dev/cu.usbmodem4101 --duration-s 8 --toggle-interval-s 2.5` を再実施し、GUI wired session が継続動作することを確認

## 8. 更新ルール

- 実施後は `Status` を更新し、必要なら `Notes` に観測内容を残す
- `BLOCKED` の項目は、実装が入ったタイミングで `TODO` に戻す
- `FAIL` が出た場合は、再現条件と修正対象ファイルを追記する
