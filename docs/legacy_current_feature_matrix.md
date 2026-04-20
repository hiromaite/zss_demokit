# Legacy vs Current Feature Matrix

## 1. 目的

本書は、旧資産と現行実装の差分を、機能項目単位で比較するための一覧である。

対象:

- 旧 firmware: `resource/old_firmware/`
- 現行 firmware: top-level PlatformIO project (`src/`, `include/`)
- 旧 PC app: `resource/old_gui/ble_test.html`
- 参考 PC app: `resource/example_gui/`
- 現行 PC app: `gui_prototype/`

比較時の見方:

- `Yes`: 機能が概ね実装されている
- `Partial`: 一部のみ実装、または導線 / 表示 / 挙動が限定的
- `No`: 現時点では未実装
- `Alternative`: 同じ課題を別の設計で解いている
- `N/A`: 比較対象のデバイスや運用前提が異なるため、そのまま同等比較しにくい

注記:

- 旧 GUI の `serial` 機能は browser の Web Serial と行ベース受信を前提としており、現行 wired path の binary framing とは設計が異なる
- 現行システムは、後方互換よりも transport 共通化と安定性を優先しているため、旧 packet schema や旧 UI そのものは意図的に引き継いでいない箇所がある

## 2. Firmware Comparison

| Feature | Old Firmware | Current Firmware | Notes |
| :--- | :--- | :--- | :--- |
| Target board | Yes | Yes | どちらも M5StampS3 系を前提 |
| BLE advertise name `M5STAMP-MONITOR` | Yes | Yes | 現行も同じ advertise name を維持 |
| BLE legacy control service / pump characteristic UUID | Yes | Yes | 旧 UUID を維持 |
| BLE legacy pump opcodes `0x55` / `0xAA` | Yes | Yes | 旧 GUI 系の最低限操作互換を維持 |
| BLE monitoring characteristic for telemetry notify | Yes | Yes | characteristic は維持。ただし payload schema は別物 |
| 旧 BLE telemetry payload schema そのまま互換 | Yes | No | 現行は `sequence` / `status_flags` / `diagnostic_bits` を含む新 schema |
| BLE status snapshot read / notify | No | Yes | 現行は extension service で追加 |
| BLE capabilities read | No | Yes | 現行は extension service で追加 |
| BLE event notify | No | Yes | `boot_complete`, `warning`, `adc_fault`, `command_error` 等 |
| Wired transport | No | Yes | 現行は `115200 8N1` の binary framing を実装 |
| 共通 command processor (BLE / wired 共有) | No | Yes | 現行は transport 非依存 command path |
| Pump control via BLE | Yes | Yes | どちらも状態ベース制御 |
| Pump control via physical on-device button | Yes | Partial | 現行 firmware に local button controller を再導入済み。実機 operator validation は残る |
| Internal ADC measurement: internal voltage | Yes | No | 現行 canonical telemetry には未搭載 |
| Internal ADC measurement: flow sensor voltage | Yes | Yes | 現行は flow raw を GUI 側で差圧 / 流量へ変換 |
| Internal ADC measurement: ZSS 2-cell raw voltage | Yes | No | 現行では未搭載 |
| External ADC measurement: Zirconia Ip voltage | Yes | Partial | 現行 firmware で ADS1115 ch0 読み取りを復活。現在は LED 制御向け local measurement |
| External ADC measurement: Heater RTD resistance | Yes | Yes | 継続搭載 |
| External ADC measurement: Zirconia output voltage | Yes | Yes | 継続搭載 |
| ADS1115 初期化失敗時の fault 化 | Yes | Yes | どちらも fault 状態を持つ |
| ADS1115 再試行 / recovery | Yes | Yes | 現行も periodic recovery を持つ |
| Sampling cadence control | Partial | Yes | 旧は `UPDATE_INTERVAL_MS` ベース。現行は deadline-based |
| Sampling overrun detection | Yes | Yes | 現行の方が明示的で status/event に反映しやすい |
| BLE / wired で cadence 切替 | No | Yes | 現行は BLE `80 ms`, wired `10 ms`, idle default を切替 |
| Structured status flags | Yes | Yes | 現行のほうが bit 数と意味が拡張されている |
| Command error latch | No | Yes | 現行で追加 |
| Transport session active flag | BLE only equivalent | Yes | 現行は transport session active bit を持つ |
| Boot complete event | No | Yes | 現行で追加 |
| Warning raised / cleared event | No | Yes | 現行で追加 |
| ADC fault raised / cleared event | No | Yes | 現行で追加 |
| Telemetry diagnostic bits | No | Yes | 現行で boot / ADC / transport readiness 等を埋め始めた |
| Serial structured logging | Yes | Yes | 旧は color-coded logger、現行も logger を継続 |
| Capability preview log at boot | No | Yes | 現行で追加 |
| Rich WS2812 status LED behavior | Yes | Partial | 現行 firmware に WS2812 state machine を再導入済み。priority / pattern の実機確認は残る |
| Voltage-target aware LED behavior | Yes | Partial | 現行 firmware に `zirconia_ip_voltage_v` ベースの target logic を実装済み。GUI / protocol 載せは未対応 |
| BLE advertising / connected LED patterns | Yes | Partial | 現行 firmware に advertising / connected pattern を再導入済み。実機目視確認は残る |
| Sensor power enable control | Yes | Yes | 現行も board config に集約 |
| Legacy-first single-transport architecture | Yes | No | 現行は BLE / wired 共通コア設計へ移行 |

## 3. PC App Comparison

| Feature | Old PC App | Current PC App | Notes |
| :--- | :--- | :--- | :--- |
| App form factor | Browser single HTML/JS | Desktop PySide6 app | 現行はローカル実行 / packaging 前提 |
| Windows packaging | No | Yes | PyInstaller `onedir` と Windows smoke 実施済み |
| BLE connect | Yes | Yes | どちらも接続可能 |
| BLE candidate scan list | Partial | Yes | 旧は browser device picker 依存。現行はアプリ内 scan + filter |
| BLE device auto-filter / preselect | No | Yes | 現行で追加 |
| Wired connect | Yes | Yes | 旧は Web Serial、現行は PySerial + binary protocol |
| Wired transport model | Generic line-based text | Structured binary protocol | 同じ課題への別解 |
| 単一アプリで BLE / wired を扱う | Partial | Yes | 旧は 1 HTML 内に混在、現行は mode-aware desktop app |
| Launcher / splash with mode select | No | Yes | 現行で追加 |
| Runtime mode switch | No | Yes | 現行は Settings から切替 |
| Settings persistence | Partial | Yes | 旧は `localStorage` を calibration points に使用。現行は `QSettings` |
| Recording pipeline | Alternative | Yes | 旧は chart export CSV。現行は session recording / partial / finalize |
| Partial file recovery | No | Yes | 現行で追加 |
| Common CSV schema for BLE / wired | No | Yes | 現行で追加 |
| CSV header metadata | No | Yes | 現行で追加 |
| Warning / event log pane | No | Yes | 現行で追加 |
| Session summary on disconnect | No | Yes | 現行で追加 |
| Device status panel | Yes | Yes | 現行は collapsible |
| Device status collapsible | No | Yes | 現行で追加 |
| Firmware / protocol / sample period visible | Partial | Yes | 現行 status / settings に統合 |
| Pump control button | Yes | Yes | 現行は Start/Stop toggle |
| `Get Status` action | No explicit action | Yes | 現行は settings 内 device actions |
| `Get Capabilities` action | No | Yes | 現行で追加 |
| `Ping` action | No | Yes | 現行で追加 |
| Manual disconnect / reconnect validation path | No | Yes | 現行は BLE session probe / GUI hardening まで実施 |
| Real-time value: Internal Voltage | Yes | No | 現行 UI には未表示 |
| Real-time value: Zirconia Ip Voltage | Yes | No | 現行 UI には未表示 |
| Real-time value: Heater RTD Resistance | Yes | Yes | 表示あり |
| Real-time value: Zirconia Output Voltage | Yes | Yes | 表示あり |
| Real-time value: Flow Rate | Yes | Yes | 現行は placeholder flow formula |
| Real-time value: O2 Concentration (1-cell) | Yes | No | 現行未搭載 |
| Real-time value: O2 Concentration (2-cell) | Yes | No | 現行未搭載 |
| ZSS 2-cell calibration table | Yes | No | 現行未搭載 |
| Editable calibration persistence | Yes | No | 旧は `localStorage` |
| Zero-point calibration command | Yes | No | 旧 serial path の独自 command。現行 protocol 未定義 |
| Flow inversion toggle | Yes | No | 旧 serial path の独自 command。現行 protocol 未定義 |
| Pause graph | Yes | No | 現行は未搭載 |
| Export currently plotted data to CSV | Yes | Alternative | 現行は plot export ではなく session recording を提供 |
| Time span presets | Yes | Yes | 現行も span preset あり |
| Reset zoom / reset view | Yes | Yes | 現行も reset view あり |
| Manual pan / zoom by plot interaction | Yes | Yes | 現行は pyqtgraph で parity 改善済み |
| Manual numeric Y-range input | No | No | 現行では一度試作したが削除済み |
| Dataset legend visibility toggle | Yes | No | 現行は固定 2 plot 構成で legend-based hide/show は未搭載 |
| Multi-axis plotting | Yes | Yes | 旧は single chart multi-axis、現行は combined sensor/flow + heater plot |
| Plot history retention | Yes | Yes | 旧は downsample、現行は time-based retention + span-aware rendering |
| Relative time axis | Yes | Yes | 両方対応 |
| Clock time axis | No | Yes | 現行で追加 |
| Collapsible side panels | Yes | Partial | 旧は複数 panel collapsible、現行は device status などを整理 |
| Professional desktop-style settings UI | No | Yes | 現行で追加 |
| Recording directory configuration | No | Yes | 現行で追加 |
| Warning-oriented continuity monitoring | No | Yes | 現行で delayed start / stalled stream を log に反映 |
| Windows packaged app smoke validated | No | Yes | 現行で実施済み |

## 4. Example GUI vs Current PC App (Abstract GUI Function Comparison)

この節では、`resource/example_gui/` と現行 GUI を、「対象デバイス固有の意味」ではなく、
desktop GUI / visualizer / logger / device console として見たときの抽象機能で比較する。

| Feature | Example GUI | Current PC App | Notes |
| :--- | :--- | :--- | :--- |
| Desktop PySide6 application | Yes | Yes | どちらも desktop native 実装 |
| Dedicated entrypoint for packaging | Yes | Yes | `main.py` を持つ |
| Splash / startup presentation | Yes | Yes | どちらも splash / launcher 的導線あり |
| Single main window with control pane + plot pane | Yes | Yes | UI 構造は近い |
| Asynchronous transport worker / adapter separation | Yes | Yes | `SerialWorker` vs `DeviceAdapter` / backend |
| Serial port scan / connect / disconnect | Yes | Yes | どちらも対応 |
| BLE connect path | No | Yes | 現行 GUI で追加 |
| Single app handling multiple transport modes | No | Yes | 現行 GUI は BLE / wired mode を持つ |
| Candidate filtering / auto-preselect for intended device | Partial | Yes | example_gui は port refresh 主体。現行は filter / preselect を持つ |
| Runtime mode switch | N/A | Yes | example_gui は single-mode serial app |
| Local settings persistence | Yes | Yes | example_gui は JSON files、現行は `QSettings` |
| Partial recording detection at startup | Yes | Yes | どちらも `.partial.csv` を検出 |
| Session recording to CSV during live run | Yes | Yes | どちらも live logging 対応 |
| Finalize `.partial.csv` to `.csv` on stop | Yes | Yes | どちらも対応 |
| CSV header metadata | Yes | Yes | どちらもメタデータ行あり |
| Event / status / capabilities ingest path | Yes | Yes | example_gui は line family、現行は BLE/wired protocol |
| Log pane for runtime messages | Yes | Yes | どちらも operator 向け log view を持つ |
| Session summary on disconnect | No | Yes | 現行 GUI で追加 |
| Plot time span presets | Yes | Yes | どちらも span preset を持つ |
| Relative / Clock time axis | Yes | Yes | どちらも対応 |
| Manual pan / zoom / reset on plots | Yes | Yes | どちらも plot interaction 重視 |
| Adjustable splitter between plot regions | Yes | Yes | どちらも vertical splitter を持つ |
| Plot redraw throttling / downsampling | Yes | Yes | どちらも重さ対策あり |
| Partial recovery dialog / review flow | No | Yes | example_gui は startup notice 中心。現行は review dialog あり |
| Recording directory configurability | Partial | Yes | example_gui は既定 `data/` 前提。現行は settings から変更可 |
| Windows packaging intent | Partial | Yes | example_gui は packaging 想定 README あり、現行は smoke 済み |
| Windows packaged app smoke validated | Partial | Yes | example_gui は packaging 想定のみで、実 smoke 記録は同梱されていない |
| Device status panel | Partial | Yes | example_gui は status label 中心、現行は panel 化 |
| Warning-oriented telemetry continuity monitoring | No | Yes | 現行 GUI で追加 |
| Live command actions from GUI | Yes | Yes | example_gui は `GET_CAPS`, `GET_PROFILE`, profile reset 等。現行は pump / status / caps / ping |
| Device-specific preset management | Yes | No | example_gui の heater profile preset に相当する現行機能は未導入 |
| Device-specific advanced configuration dialog | Yes | Partial | example_gui は profile / stability dialogs、現行は general settings 中心 |
| Segment markers / labeled recording regions | Yes | No | example_gui の exposure segment 相当機能は未搭載 |
| Segment overlay bands on plot | Yes | No | example_gui 特有の解析支援 UI |
| Stability analyzer / stability lamp UI | Yes | No | example_gui 特有の解析支援 UI |
| Sleep prevention while connected / recording | Yes | No | example_gui は Windows sleep prevention を持つ |
| Recording-active visual emphasis | Yes | Partial | example_gui は glow effect、現行は Start/Stop toggle 表示中心 |

## 5. Same Problem, Different Solution

| Topic | Old Approach | Current Approach | Interpretation |
| :--- | :--- | :--- | :--- |
| CSV 保存 | その時点の chart data を手動 export | session recording を partial/final CSV として自動保存 | 現行の方が運用向け |
| Wired input | browser Web Serial で CSV-like line を読む | desktop app から binary framed protocol を読む | 現行の方が protocol 拡張に向く |
| 設定保存 | calibration table を `localStorage` 保存 | app-wide settings を `QSettings` で保存 | 現行の方が対象範囲が広い |
| グラフ負荷対策 | old data の downsample | span-aware redraw + downsampling + pyqtgraph | 現行の方が高頻度向け |
| 接続 UX | BLE browser picker / serial browser picker | app 内 scan, filter, preselect, settings-based mode switch | 現行の方が専用機らしい |
| エラー確認 | status panel と console 依存 | warning/event log + session summary + firmware events | 現行の方が追跡しやすい |

## 6. Major Gaps If Legacy Parity Is Desired

現時点で、旧資産にあって現行実装にまだ無い、もしくは明確に別解へ置き換わっている代表項目は以下である。

- firmware / GUI 共通
  - `Internal Voltage`
  - `Zirconia Ip Voltage`
  - `ZSS 2-cell raw value`
- GUI / operator feature
  - `O2 concentration (1-cell / 2-cell)` の表示
  - `ZSS 2-cell calibration table`
  - `Zero-point calibration`
  - `Flow invert`
  - `Pause graph`
  - dataset ごとの legend hide/show
- firmware / local device behavior
  - physical button による pump toggle
  - 旧 firmware 相当の rich WS2812 status LED state machine
- compatibility
  - 旧 GUI が前提としていた BLE payload schema 互換

## 7. Recommended Interpretation for Next Planning

次の計画検討では、旧機能を以下の 3 つに分けて扱うのがよい。

1. `そのまま戻したい機能`
- 例: `Internal Voltage` 表示、`Zirconia Ip Voltage` 表示、physical button、rich status LED

2. `同じ課題は新方式で解けているので戻さなくてよい機能`
- 例: chart export CSV -> session recording
- 例: Web Serial generic line parser -> structured wired binary transport

3. `ユーザー価値は高いが protocol / UI の再設計が必要な機能`
- 例: `Zero-point calibration`
- 例: `Flow invert`
- 例: `ZSS 2-cell calibration / O2 conversion`

この分類で backlog に戻すと、旧資産の見落としを減らしつつ、現在の設計方針も壊しにくい。
