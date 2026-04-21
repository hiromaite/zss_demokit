# Validation Checklist v1

## 1. 目的

本書は、現時点の実装段階で実施可能な検証項目を整理し、
実施結果を残すためのチェックリストである。

対象段階:

- GUI prototype + protocol constants 導入後
- firmware skeleton + top-level PlatformIO project 置換後
- wired transport は firmware / host 側で smoke test 可能な段階
- BLE transport と GUI adapter は実装済みで、basic live connect は確認済み
- ただし BLE live continuity / reconnect の長時間観測は local Mac GUI 実行ベースで継続する段階

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
- BLE は basic live connect までは実施済みとし、continuity / reconnect は GUI hand-run と backend smoke を組み合わせて追う

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
| `GUI-VAL-020` | PyInstaller packaging smoke | PyInstaller spec から GUI bundle を生成できる | `PASS` | `pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec` で GUI bundle を生成し、offscreen short launch が成立することを確認。version metadata scaffold、beta naming、icon asset 追加後も再通過 |
| `GUI-VAL-021` | Windows packaged GUI smoke | Windows packaged app が起動し、基本操作が成立する | `PASS` | user による Windows 11 Pro 実機確認で packaging 成功、packaged app 起動成功、blocking issue なしを確認 |

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
| `FW-VAL-014` | Diagnostic payload wiring build smoke | diagnostic bits 追加後も firmware build と shared regression が壊れない | `PASS` | `pio run` と `tools/protocol_fixture_smoke.py` により AppState / payload builder の diagnostic wiring 後も build/regression が継続することを確認 |
| `FW-VAL-015` | Bundle A regression smoke | physical button / ADS1115 ch0 / WS2812 parity 追加後も wired path が退行しない | `PASS` | `pio run`, upload, `tools/wired_serial_smoke.py --port /dev/cu.usbmodem3101 --baudrate 115200` を実施し、capabilities / status / telemetry / `Pump ON/OFF` / command error event が継続動作することを確認 |
| `FW-VAL-016` | Differential pressure telemetry publication | dual-SDP selected differential pressure が transport payload に反映される | `PASS` | `pio run`, upload, `tools/sdp_serial_probe.py --port /dev/cu.usbmodem3101 --duration-s 6`, `tools/wired_serial_smoke.py --port /dev/cu.usbmodem3101 --baudrate 115200` により `telemetry_field_bits=15` と finite `differential_pressure_selected_pa` を確認 |

## 6. Integration Checklist

| ID | Item | Expected Result | Status | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `INT-VAL-001` | BLE scan / connect | GUI から BLE 接続できる | `PASS` | user の local Mac 実機確認で `Scan -> Connect -> capabilities load` を確認 |
| `INT-VAL-002` | wired connect | GUI から serial 接続できる | `PASS` | `MockBackend(Wired)` の実機 smoke で `/dev/cu.usbmodem5101` 接続を確認 |
| `INT-VAL-003` | Pump ON/OFF end-to-end | GUI command が実機動作へ届く | `PASS` | `tools/wired_serial_smoke.py` で `SetPumpState` と status flag 反映を確認 |
| `INT-VAL-004` | Get Status end-to-end | GUI で status snapshot を取得できる | `PASS` | wired backend smoke と host smoke の両方で `status_snapshot` を確認 |
| `INT-VAL-005` | Shared CSV recording | 実データを共通 schema で保存できる | `PASS` | BLE mock と wired 実機の両方で `.partial.csv -> .csv` finalize と schema header を確認 |
| `INT-VAL-006` | Wired 10 ms transport validation | `10 ms` path を end-to-end 検証できる | `PASS` | `wired_serial_smoke` と wired backend smoke で `nominal_sample_period_ms=10` を確認 |
| `INT-VAL-007` | BLE 50-100 ms validation | BLE telemetry 周期を検証できる | `PASS` | local Mac 実機 probe で `2221` samples / `177.54 s` を観測し、実効 inter-arrival は約 `79.97 ms`、target range 内を確認 |
| `INT-VAL-008` | Wired event propagation | firmware event が GUI warning log に届く | `PASS` | `command_error` と `warning_raised` を wired 実機 + GUI backend smoke で確認 |
| `INT-VAL-009` | Golden fixture regression smoke | shared fixture で GUI parser / firmware encoder / CSV row を回帰確認できる | `PASS` | `tools/protocol_fixture_smoke.py` と `tools/firmware_fixture_verify.cpp` により正常系 9 ケース、異常系 4 ケース、CSV row 1 ケースを確認 |
| `INT-VAL-010` | BLE GUI continuity manual validation | local Mac GUI 実行で BLE continuity / reconnect を継続確認できる | `PASS` | `tools/gui_ble_session_probe.py --duration-s 180 --recording-duration-s 45 --reconnect-at-s 60` で `Connect count=2`, `Connected telemetry segments=2`, `sequence_gap_total=0`, `Reconnect recovered=True`, `recovery=3.42 s`, `Recording sessions completed=1`, `gui_ble_session_probe_ok` を確認 |
| `INT-VAL-011` | BLE GUI session probe logic smoke | GUI-level BLE probe の段取りと gate 判定が fake live backend で回る | `PASS` | `tools/gui_ble_session_probe.py --use-fake-live --offscreen --duration-s 12 --recording-duration-s 4 --reconnect-at-s 6 --min-observed-duration-s 6 --connect-timeout-s 6` で `scan -> connect -> recording -> reconnect -> summary` を確認 |
| `INT-VAL-012` | Windows packaged end-to-end smoke | Windows packaged app で `Wired` / `BLE` の両モードが blocking issue なく動く | `PASS` | user による Windows 11 Pro 実機確認で serial / BLE の両方に問題なしを確認 |
| `INT-VAL-013` | GUI wired flow integration | GUI が selected differential pressure を含む wired session を継続処理できる | `PASS` | `tools/gui_wired_session_probe.py --port /dev/cu.usbmodem3101 --duration-s 8 --toggle-interval-s 2.5` で `967` telemetry, warning/error `0`, CSV `799` rows, `gui_wired_session_probe_ok` を確認 |
| `INT-VAL-014` | Wired flow probe baseline | wired transport 上で selected differential pressure と derived flow rate を集計できる | `PASS` | `tools/wired_flow_probe.py --port /dev/cu.usbmodem4101 --duration-s 4` で `telemetry_field_bits=63`, advertised differential pressure, finite `selected / SDP810 / SDP811` no-flow baseline を確認 |
| `INT-VAL-015` | Wired flow operator sweep | low / medium / high flow で transport-level flow probe が handoff を観測できる | `TODO` | `tools/wired_flow_probe.py` を用いた user-operated flow sweep を次回実施 |
| `GUI-VAL-022` | Flow card raw SDP visibility | wired differential pressure raw values が flow metric card に表示される | `PASS` | offscreen live connection で `flow_detail=SDP811: -0.05 Pa / SDP810: -0.05 Pa`, `detail_visible=True` を確認 |

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
- `test/fixtures/protocol_golden_v1.json` を追加し、shared golden fixture による parser / encoder / CSV row 回帰基盤を導入
- `tools/protocol_fixture_smoke.py` を実施し、GUI 側 BLE / wired decoder、invalid-case parser、CSV row formatting、firmware-side C++ encoder の全ケース照合が通ることを確認
- current fixture smoke では正常系 9 ケース、異常系 4 ケース、CSV row 1 ケースが `PASS` となり、`protocol_fixture_smoke_ok` を確認
- `flow_rate_lpm` の placeholder policy を `dummy_selected_dp_orifice_v1` へ更新し、`selected differential pressure -> signed flow_rate_lpm` の換算へ置き換えた
- 2026-04-21 の再計測では `tools/wired_timing_probe.py --port /dev/cu.usbmodem4101 --samples 1200 --warmup 20` により
  `mean=10.007 ms / stdev=6.521 ms / min=0.003 ms / p95=20.728 ms / max=21.160 ms`, `sequence gap=0` を確認し、
  CSV / host probe の大きな jitter は device cadence だけでなく host receive jitter を強く含むという current hypothesis を記録した
- 続けて `tools/wired_batch_probe.py --port /dev/cu.usbmodem4101 --samples 1200 --warmup 20` を実施し、
  `513 / 1200` sample が multi-frame chunk から decode され、`304` 件の consecutive sample が同一 receive timestamp を共有することを確認した
- current evidence は、CSV / host probe 上の大きな jitter の主因が host-side polling / buffering / batching にある可能性をさらに強める
- `tools/wired_receive_path_probe.py` により reader-side receive timestamp と poll-handled timestamp を比較し、
  `5 ms` poll では handling delay `mean=3.063 ms / p95=5.730 ms`,
  `1 ms` poll では `mean=0.657 ms / p95=1.180 ms`,
  `10 ms` poll では `mean=5.983 ms / p95=11.583 ms` を確認した
- current evidence は、GUI poll cadence が handled timestamp jitter を増やす一方で、
  broad な receive distribution 自体は reader-side serial chunking / host buffering に起因する可能性が高いことを示す
- debug-only `TimingDiagnostic` frame を追加した firmware を upload し、
  `tools/wired_device_tick_probe.py --port /dev/cu.usbmodem4101 --samples 1200 --warmup 20` により
  device-side cadence `mean=10.001 ms / stdev=1.204 ms / min=8.378 ms / p95=10.932 ms / max=10.962 ms` を確認した
- 同 probe では host receive inter-arrival `mean=10.001 ms / stdev=1.217 ms / p95=11.031 ms` と device cadence が近く、
  `device minus host interval` も `stdev=0.081 ms` に収まることを確認した
- `gui_prototype` の wired backend は debug timing diagnostic を受け取れるよう更新し、
  `RecordingController` は `inter_arrival_ms` を device cadence 優先にしつつ
  `host_inter_arrival_ms`, `device_inter_arrival_ms`, `device_sample_tick_us` を CSV へ記録するよう更新した
- wired backend の `host_received_at` は `frame decode 後` ではなく `serial chunk read 直後` を採るよう更新し、
  host-side timing semantics を current transport boundary に近づけた
- `tools/gui_wired_session_probe.py --port /dev/cu.usbmodem4101 --duration-s 6 --toggle-interval-s 2.5` により、
  debug timing support 追加後も offscreen GUI wired session が継続動作することを確認した
- `python3.12 -m compileall gui_prototype/src tools/protocol_fixture_smoke.py` を再実施し、derived metric policy と session summary 追加後も compile を確認
- `tools/protocol_fixture_smoke.py` を再実施し、差圧ベース placeholder へ更新後も shared fixture regression が維持されることを確認
- direct helper smoke により `TelemetrySessionStats` が disconnect 時に summary log を生成し、sample count / gap total を含むことを確認
- `tools/gui_ble_session_probe.py` を追加し、GUI-level BLE continuity / reconnect の半自動 probe を導入
- `python3.12 -m compileall tools/gui_ble_session_probe.py` を実施し、新 probe の compile を確認
- `tools/gui_ble_session_probe.py --use-fake-live --offscreen --duration-s 12 --recording-duration-s 4 --reconnect-at-s 6 --min-observed-duration-s 6 --connect-timeout-s 6` を実施し、fake live backend 上で `recording finalize`, `planned reconnect`, `summary verdict` が通ることを確認
- BLE 実機 probe の結果を受け、planned reconnect を含む場合の観測時間基準を `session duration - reconnect timeout budget` に調整した
- firmware 側は active transport に応じて sampling cadence を `wired=10 ms` / `BLE=80 ms` へ動的切替するよう更新し、BLE packet 上の `nominal_sample_period_ms` も payload と一致させた
- GUI 側は live BLE disconnect を background task で二重に閉じないよう更新し、shutdown 時の pending task warning を解消する方針に変更した
- local Mac 実機で `tools/gui_ble_session_probe.py --duration-s 180 --recording-duration-s 45 --reconnect-at-s 60` を実施し、`sequence_gap_total=0`, `Reconnect recovered=True`, `recovery=3.42 s`, `Recording sessions completed=1`, `gui_ble_session_probe_ok` を確認
- probe 後の follow-up として BLE status fallback を harden し、short probe `--duration-s 40 --recording-duration-s 12 --reconnect-at-s 20 --min-observed-duration-s 25` で `Status events=7`, `sequence_gap_total=0`, `gui_ble_session_probe_ok` を確認
- BLE status direct-read fallback を Qt timer ではなく BLE asyncio loop 側で遅延実行する形へ変更し、probe / backend smoke から `QObject::startTimer` warning を除去した
- `pyinstaller>=6,<7` を `.venv_gui_prototype` へ導入し、`pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec` により `dist/zss_demokit_gui/` を生成できることを確認
- packaged binary `dist/zss_demokit_gui/zss_demokit_gui` を `QT_QPA_PLATFORM=offscreen` で短時間起動し、bundle が即時クラッシュせず立ち上がることを確認
- packaging metadata scaffold を追加した後も `pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec` を再実施し、build と packaged offscreen short launch が継続して成立することを確認
- beta2 naming `zss_demokit_gui_win64_beta2`, version `0.1.0-beta.2`, publisher metadata, generated icon asset を反映した後も packaging smoke が継続して成立することを確認
- user により Windows 11 Pro 上で packaging を実施し、packaged app の起動と `Wired` / `BLE` の両モード実行に問題がないことを確認

### 2026-04-20

- post-beta hardening として、GUI compact layout の最終調整を実施し、left column の縦スクロール化、BLE selector の dropdown 化、不要な plot toolbar 第二行の削除、Start/Stop トグル表記への整理を行った
- `python3.12 -m compileall gui_prototype/main.py gui_prototype/src tools/gui_ble_session_probe.py tools/gui_wired_session_probe.py` を実施し、GUI の current source state が compile 可能であることを確認した
- helper smoke により `Settings` 経由の mode switch、`Relative / Clock` 軸表示、compact layout 後の fake live BLE session probe が継続動作することを確認した
- left column の横スクロール問題を再現し、content width を viewport width に同期する修正を加えた後に `viewport_width == content_width` と `ScrollBarAlwaysOff` を確認した
- firmware 側の diagnostics hardening として `diagnostic_bits` を AppState / telemetry payload に配線し、`boot_complete` event の `detail_u32` に diagnostic bits を載せるよう更新した
- `python3.12 -m compileall gui_prototype/src tools/protocol_fixture_smoke.py`、`./.venv_gui_prototype/bin/python3.12 tools/protocol_fixture_smoke.py`、`./.venv_pio/bin/pio run` を実施し、diagnostic wiring 後も GUI compile、shared protocol regression、firmware build が継続して成立することを確認した
- Bundle A の初期実装として `InputButtonController`、ADS1115 ch0 `zirconia_ip_voltage_v` 読み取り、WS2812 `StatusLedController` state machine を追加した
- `./.venv_pio/bin/pio run`、`./.venv_pio/bin/pio run -t upload --upload-port /dev/cu.usbmodem3101`、`source .venv_gui_prototype/bin/activate && python3.12 tools/protocol_fixture_smoke.py`、`source .venv_gui_prototype/bin/activate && python3.12 tools/wired_serial_smoke.py --port /dev/cu.usbmodem3101 --baudrate 115200` を実施し、Bundle A 追加後も build / upload / shared regression / wired transport が継続して成立することを確認した
- KNF `NMP03 KPDC-B3` への切替に合わせて `PumpController` を PWM 駆動へ更新し、`20 kHz`, `10-bit`, `OFF=0 %`, `ON=50 %` を firmware へ反映した
- PWM 化後は `./.venv_pio/bin/pio run` と `source .venv_gui_prototype/bin/activate && python3.12 tools/protocol_fixture_smoke.py` を再実施し、build と shared protocol regression の継続成立を確認した
- デバイス再接続後に `./.venv_pio/bin/pio run -t upload --upload-port /dev/cu.usbmodem3101` と `source .venv_gui_prototype/bin/activate && python3.12 tools/wired_serial_smoke.py --port /dev/cu.usbmodem3101 --baudrate 115200` を再実施し、PWM 化後も upload / capabilities / status / telemetry / `Pump ON/OFF` / command error handling が継続動作することを確認した
- BLE control write を `response=True` に変更し、firmware 側 control characteristic を `WRITE | WRITE_NR` に更新した
- `source .venv_gui_prototype/bin/activate && python3.12 tools/ble_backend_smoke.py`、`source .venv_gui_prototype/bin/activate && python3.12 tools/gui_ble_session_probe.py --use-fake-live --offscreen --duration-s 12 --recording-duration-s 4 --reconnect-at-s 6 --min-observed-duration-s 6 --connect-timeout-s 6` を実施し、`Pump ON status seen=True`, `Pump OFF status seen=True` を含めて BLE command path の fake live 回帰が通ることを確認した
- settings dialog の `Accepted` 判定例外を修正し、offscreen smoke で「設定更新」と「BLE/Wired mode switch」の両経路が通ることを確認した
- BLE / wired の接続 UI を `Disconnect` 表示と mode switch 前 disconnect に統一し、offscreen smoke で接続中 controls の enable/disable と mode switch sequencing を確認した
- user feedback により Bundle A 完了を確認したため、次フェーズは `EXT-002` GUI recording emphasis に移行する
- `Recording` panel に active accent / badge / detail text を追加し、`python3.12 -m compileall gui_prototype/src/main_window.py gui_prototype/src/theme.py` を実施した
- `./.venv_gui_prototype/bin/python` による offscreen smoke で `recording_emphasis_smoke_ok` を確認し、`Idle -> REC ACTIVE -> Idle` の visual state 遷移が成立することを確認した
- Bundle C first pass として `O2 Concentration (1-cell)` card、ambient-air calibration / reset action、`QSettings` persistence を追加した
- `python3.12 -m compileall gui_prototype/src/app_state.py gui_prototype/src/settings_store.py gui_prototype/src/protocol_constants.py gui_prototype/src/dialogs.py gui_prototype/src/main_window.py` を実施し、GUI 変更後も compile 可能であることを確認した
- `./.venv_gui_prototype/bin/python` による offscreen smoke で `o2_bundle_c_smoke_ok` を確認し、calibration staging、settings persistence、`21.0 %` 表示、uncalibrated 時の `Calibrate` 表示が成立することを確認した
- user により Bundle C の essential function validation が完了し、ambient-air calibration workflow を現行 bundle close 条件として受け入れた
- Bundle D の current slice として `Sdp8xxSensor` / `DifferentialPressureFrontend` を追加し、`MeasurementCore` と summary log への観測専用統合後も `./.venv_pio/bin/pio run` が成功することを確認した
- `/dev/cu.usbmodem3101` へ upload 後の serial summary log で `DpSel`, `Dp125`, `Dp500` が finite 値で継続出力されることを確認した
- `source .venv_gui_prototype/bin/activate && python3.12 tools/sdp_serial_probe.py --port /dev/cu.usbmodem3101 --duration-s 8` を実施し、no-flow baseline として `DpSel mean=-0.0514 Pa`, `Dp125 mean=-0.0514 Pa`, `Dp500 mean=-0.0586 Pa`, selector low `7/7` を確認した
- 同 probe により low-flow, medium-flow, high-flow, return-to-no-flow を観測し、selector high-side activity と low-side return を確認した
- Bundle E の事前整備として、GUI は optional `differential_pressure_selected_pa` を受け取れるよう更新し、field がある場合はそれを優先して flow rate を算出する fallback-safe path を導入した
- `python3.12 -m compileall gui_prototype/src/protocol_constants.py gui_prototype/src/mock_backend.py gui_prototype/src/controllers.py` と `source .venv_gui_prototype/bin/activate && python3.12 tools/protocol_fixture_smoke.py` を実施し、GUI regression がないことを確認した
- right column scroll 対応後の plot height / vertical splitter 挙動は数回調整したが、この時点では local macOS の見た目を accept とし、Windows / 別解像度環境での follow-up visual validation 項目として扱う
- flow telemetry integration として `telemetry_field_bits bit3` による selected differential pressure 拡張を導入し、既存 payload サイズを維持したまま wired / BLE decoder を更新した
- `./.venv_pio/bin/pio run`、`python3.12 -m compileall gui_prototype/src/protocol_constants.py gui_prototype/src/ble_protocol.py gui_prototype/src/wired_protocol.py gui_prototype/src/mock_backend.py gui_prototype/src/controllers.py`、`python3.12 tools/protocol_fixture_smoke.py` を実施し、transport / GUI regression がないことを確認した
- `/dev/cu.usbmodem3101` へ upload 後、`python3.12 tools/sdp_serial_probe.py --port /dev/cu.usbmodem3101 --duration-s 6` により no-flow baseline `DpSel mean=-0.0671 Pa` を確認した
- `python3.12 tools/wired_serial_smoke.py --port /dev/cu.usbmodem3101 --baudrate 115200` により `telemetry_field_bits=15`, finite `differential_pressure_selected_pa`, `Pump ON/OFF`, command error event を live wired で確認した
- `python3.12 tools/gui_wired_session_probe.py --port /dev/cu.usbmodem3101 --duration-s 8 --toggle-interval-s 2.5` により GUI wiring 後も wired session が継続し、`967` telemetry, warning/error `0`, CSV `799` rows, `gui_wired_session_probe_ok` を確認した
- `python3.12 tools/wired_flow_probe.py --port /dev/cu.usbmodem3101 --duration-s 6` を実施し、no-flow baseline として `telemetry_field_bits=15`, advertised differential pressure, `DpSel mean=-0.0591 Pa`, `Non-unit sequence gap total=0` を確認した

## 8. 更新ルール

- 実施後は `Status` を更新し、必要なら `Notes` に観測内容を残す
- `BLOCKED` の項目は、実装が入ったタイミングで `TODO` に戻す
- `FAIL` が出た場合は、再現条件と修正対象ファイルを追記する
