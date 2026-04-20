# Feature Extension Plan v1

## 1. 目的

本書は、beta 到達後の次フェーズとして追加実装したい機能について、

- 実装のまとまり
- 実装方法
- PoC の切り方
- 実装の順番
- protocol / GUI / firmware への影響

を整理し、次の開発を迷いなく進めるための計画書である。

今回対象とする機能は以下の 2 群である。

### 1.1 旧資産や参考アプリに寄せたい機能

- `Pump control via physical on-device button`
- `Voltage-target aware LED behavior`
- `BLE advertising / connected LED patterns`
- `Recording-active visual emphasis`

### 1.2 新規に設計したい機能

- `Real-time value: O2 Concentration (1-cell)`
- `Real-time value: Flow Rate` using `Sensirion SDP811-500Pa-D` and `SDP810-125Pa`

## 2. 実行方針

今回の追加機能は、難易度と影響範囲の差が大きい。
そのため、以下の方針で進める。

1. まず `protocol 変更なしで回収できる機能` を先に実装する
2. 次に `GUI 側だけで成立する派生値` を実装する
3. 最後に `measurement model / protocol に影響する機能` を PoC 付きで導入する

この順にする理由:

- 物理ボタン、LED、recording emphasis は低リスクで operator 価値が高い
- `O2 Concentration (1-cell)` は既存の `zirconia_output_voltage_v` から派生でき、比較的独立して進めやすい
- dual-range differential pressure flow は hardware / firmware / protocol / GUI 全部に波及するため、最後に分離して扱うべき

## 3. 推奨実装順

推奨順序は以下とする。

1. `Bundle A`: Firmware UX parity
2. `Bundle B`: GUI recording emphasis
3. `Bundle C`: O2 1-cell display and calibration
4. `Bundle D`: Dual-SDP differential pressure PoC
5. `Bundle E`: Flow algorithm integration and telemetry expansion
6. `Bundle F`: End-to-end hardening and operator validation

## 4. Bundle A: Firmware UX Parity

### 対象

- `Pump control via physical on-device button`
- `Voltage-target aware LED behavior`
- `BLE advertising / connected LED patterns`

### 実装方針

#### A-1. Physical on-device button

旧 firmware は device button interrupt により pump をトグルしていた。
現行 firmware でも、これを `local command source` として復活させる。

推奨実装:

- `InputButtonController` を追加する
- debounce は interrupt か poll-based どちらでもよいが、現行構造では `poll in loop` のほうが安全
- button event は `CommandProcessor` に直接 bypass せず、`CommandRequest{source=Local}` として統一経路へ流す
- boot 直後の誤反応を避けるため、`post-boot arm delay` を設ける

理由:

- pump state の single source of truth を壊さない
- BLE / wired / local button の command path を共通化できる
- 状態遷移 event / status flag / log をそのまま再利用できる

注意:

- M5StampS3 の button / boot strap pin を使う場合、`power-on held` 時の挙動には注意が必要
- runtime toggle と boot mode selection は切り分ける

#### A-2. WS2812 status LED state machine

現行の `StatusLedController` は fault 時の simple GPIO placeholder であり、
旧 firmware の WS2812B state machine は未移植である。

推奨実装:

- `StatusLedController` を `WS2812StatusLedController` へ再設計する
- `FastLED` もしくは `Adafruit_NeoPixel` を使用する
- board pin は既存の `kStatusLedDataPin=21` を使う
- state machine は `status_flags`, `BLE connection state`, `zirconia_ip_voltage_v`, `recording active` を入力として決める

初期 state priority 案:

1. `ADC / sensor fault`
2. `sampling overrun`
3. `recording active emphasis`
4. `voltage-target notify / stable`
5. `BLE connected`
6. `BLE advertising`
7. idle / off

#### A-3. Voltage-target aware LED behavior

旧 firmware では `zirconiaIpVoltage` を見て LED 色や通知を変えていた。
これは operator feedback として復元価値が高い。

推奨実装:

- ADS1115 channel 0 の `zirconia_ip_voltage_v` 読み取りを復活する
- まずは `LED local use only` として導入する
- GUI 表示や protocol 載せは次の段階で判断する

推奨 target policy:

- low: `< 0.80 V`
- approaching / gradient: `0.80 to 0.92 V`
- target band: `0.89 to 0.91 V`
- high: `> 0.92 V`
- stable notification: target band 継続 `>= 3 s`

この帯域は旧 firmware 実装をそのまま初期値として採用し、後で定数化する。

### PoC

PoC は 2 段階に分ける。

#### PoC-A1. Button and LED skeleton

- local button で `Pump ON/OFF` が切り替わる
- BLE advertising / connected の pattern が復元される
- system fault 時に LED priority が正しく上書きされる

#### PoC-A2. Voltage-target behavior

- `zirconia_ip_voltage_v` が finite で取れる
- target band 近傍で LED gradient / notify / stable が遷移する
- BLE state / fault state / voltage state の priority 衝突が破綻しない

### 受け入れ条件

- local button, BLE command, wired command のいずれでも pump state が一貫する
- LED は advertising / connected / fault / target-state を operator に区別可能な形で示す
- sampling cadence や BLE / wired transport 安定性を壊さない

## 5. Bundle B: GUI Recording Emphasis

### 対象

- `Recording-active visual emphasis`

### 実装方針

これは firmware や protocol に触らず、GUI だけで回収する。

推奨実装:

- `Recording` group に subtle glow, border tint, or header accent を追加する
- `Start Recording` / `Stop Recording` toggle の active state をさらに強調する
- `warning log` とは別に、recording active が glance で分かる視覚要素にする

参考:

- `example_gui` は `recording group glow` を使っていた
- 現行 GUI は button state は分かるが、panel 全体の state cue は弱い

### PoC

- offscreen screenshot / local run で active / inactive の視認差を確認する
- dark theme とぶつからないことを確認する

### 受け入れ条件

- operator が 1 秒以内に recording active / inactive を判別できる
- narrow window でも layout を崩さない

## 6. Bundle C: O2 1-Cell Display and Calibration

### 対象

- `Real-time value: O2 Concentration (1-cell)`
- ambient-air calibration workflow

### 基本方針

この値は GUI derived metric として実装する。
device 側の canonical measurement は引き続き `zirconia_output_voltage_v` とする。

理由:

- v1 現行 telemetry で必要な raw value はすでに届いている
- calibration state を GUI 側で保持すれば、firmware 変更なしで導入可能
- 現場で calibration をやり直しやすい

### 推奨モデル

ユーザー要求を初期方針として、`0 % O2` の固定基準を `2.5 V` とし、
`21 % O2` の基準を ambient-air calibration で取得する。

定義:

- `v_zero_ref = 2.5`
- `v_air_cal = calibrated zirconia_output_voltage_v in ambient air`
- `o2_air_ref = 21.0`

推奨一次式:

```text
normalized = (v_zero_ref - v_measured) / (v_zero_ref - v_air_cal)
o2_percent = clamp(normalized * 21.0, 0.0, 100.0)
```

補足:

- これは `v_measured` が小さくなるほど O2% が増える前提の式である
- 実機で極性が逆なら、`invert_polarity` を設けて反転できるようにする

### GUI 仕様

最低限必要な UI:

- `O2 Concentration (1-cell)` の numeric display
- `Calibrate to Ambient Air (21%)` button
- `Reset O2 Calibration` action
- calibration state の表示
  - calibrated / not calibrated
  - `v_air_cal`
  - calibrated timestamp

保存先:

- `QSettings`

### PoC

#### PoC-C1. Formula and persistence

- calibration button 押下時に現在の `zirconia_output_voltage_v` を保存する
- app 再起動後も calibration state が残る
- derived O2 value が表示に反映される

#### PoC-C2. Sanity validation

- ambient air で calibration 直後に `21 %` 近傍になる
- clamp, NaN handling, uncalibrated state が破綻しない

### 受け入れ条件

- 未 calibration 時に misleading な値を出さない
- calibration 後に ambient air で `21 %` 近傍を示す
- formula, anchor, calibration timestamp が operator から追跡できる

## 7. Bundle D: Dual-SDP Differential Pressure PoC

### 対象

- `SDP811-500Pa-D`
- `SDP810-125Pa`

### 事実ベースの前提

Sensirion の SDP8xx digital datasheet によると:

- `SDP810-125Pa` は tube connection, bidirectional `±125 Pa`, I2C address `0x25`
- `SDP811-500Pa` は tube connection, bidirectional `±500 Pa`, I2C address `0x26`
- continuous mode differential-pressure update rate は typ. `2000 Hz`
- I2C は `400 kHz to 1 MHz`

このため、両センサを同一 I2C bus に同居させる前提は妥当である。

### 実装方針

`AdcFrontend` に直接混ぜず、`DifferentialPressureFrontend` を別コンポーネントとして追加する。

推奨責務:

- `Sdp8xxSensor` driver
  - start continuous measurement
  - read differential pressure
  - CRC validation
  - soft reset / reinit / health
- `DifferentialPressureFrontend`
  - low-range sensor (`±125 Pa`) read
  - high-range sensor (`±500 Pa`) read
  - selected differential pressure
  - health bits
  - smoothing / hysteresis / blending

### PoC

#### PoC-D1. Bus and readout sanity

- 両センサが同一 bus で probe できる
- address collision がない
- continuous mode read が安定する
- CRC error / timeout recovery が動く

#### PoC-D2. Bench logging

- no-flow, low-flow, medium-flow, higher-flow の各点で
  - `dp_125_pa`
  - `dp_500_pa`
  - health
  - read latency

を serial log に出す

#### PoC-D3. Selector-only algorithm

まずは blend せず、hysteresis 付き selector で動かす。

推奨 selector:

- default は `±125 Pa` を優先
- `abs(dp_125) <= 100 Pa` なら `125 Pa` sensor を使う
- `abs(dp_125) >= 110 Pa` なら `500 Pa` sensor へ切替
- `90 to 110 Pa` は hysteresis band とする
- 片側 fault 時は healthy sensor に fallback

### 受け入れ条件

- no-flow で両センサとも大きく暴れない
- range handoff で選択がチャタリングしない
- I2C bus error が起きても recovery 可能

## 8. Bundle E: Flow Algorithm Integration and Telemetry Expansion

### 対象

- `Real-time value: Flow Rate`
- dual-range differential pressure based measurement

### 重要判断

この bundle は、初めて `measurement model` と `protocol` を広げる可能性がある。

推奨判断:

- `Bundle D` までは firmware local log と debug path で進める
- `Bundle E` で初めて GUI integration と protocol extension を入れる

### 推奨 canonical measurement

現行の `flow_sensor_voltage_v` は、旧アナログ前段に由来する placeholder である。
dual-SDP 化後は、canonical measurement を差圧ベースへ移す方が自然である。

推奨追加項目:

- `differential_pressure_low_range_pa`
- `differential_pressure_high_range_pa`
- `differential_pressure_selected_pa`
- `flow_sensor_selector_state`

ただし、常時 transport に全部載せるかは別途判断する。

現実的な段階案:

1. GUI 表示に必要な最小値として `differential_pressure_selected_pa` だけ transport に追加
2. debug build か status snapshot で raw low/high pressure を読めるようにする
3. flow rate は GUI derived metric のまま維持する

### 推奨 flow placeholder

最終的なオリフィス係数は後続の gas line 実測で決める。
そのため、この段階では `signed sqrt law` を placeholder とする。

```text
flow_rate_lpm =
    sign(differential_pressure_selected_pa) *
    k_flow_gain *
    sqrt(max(0.0, abs(differential_pressure_selected_pa) - dp_offset_pa))
```

初期 placeholder:

- `k_flow_gain = 1.0`
- `dp_offset_pa = 0.0`

### 相補利用アルゴリズムの推奨形

最終推奨は `selector + optional blend` の 2 段階である。

#### Step 1: robust selector

- low range を主役にする
- high range を over-range safety net にする
- hysteresis で handoff の不安定化を避ける

#### Step 2: overlap blend

PoC で必要性が確認できたら、overlap band だけ weighted blend を入れる。

例:

```text
if abs(dp_125) <= 90:
    dp_selected = dp_125
elif abs(dp_125) >= 110:
    dp_selected = dp_500
else:
    w = (abs(dp_125) - 90) / 20
    dp_selected = (1 - w) * dp_125 + w * dp_500
```

これは range handoff で plot の段差を減らすための後段改善であり、
最初から必須にしない。

### 受け入れ条件

- low-flow 域で `±125 Pa` センサの分解能メリットが出る
- high-flow 域で `±500 Pa` センサへ安全に移れる
- GUI 側の flow rate は selected differential pressure から一貫して計算できる

## 9. まとめて実装すべき単位

### Group 1: Low-risk parity restore

- local pump button
- BLE advertising / connected LED
- voltage-target LED
- recording-active visual emphasis

理由:

- operator 価値が高い
- protocol を壊さない
- regression 切り分けが簡単

### Group 2: GUI-derived oxygen metric

- O2 1-cell display
- ambient-air calibration
- calibration persistence / reset

理由:

- 既存 telemetry だけで進められる
- GUI 内で閉じる

### Group 3: New flow sensing platform

- dual SDP frontend
- selector algorithm
- telemetry extension
- flow GUI integration

理由:

- 最も複雑で、PoC と production integration を分けるべき

## 10. 推奨スケジュール感

### Step 1

`Bundle A + Bundle B`

期待成果:

- parity restore の quick win
- operator feedback 改善

現状:

- `Bundle A` は初期コード実装まで着手済み
- 具体的には `local button controller`, `ADS1115 ch0 zirconia_ip_voltage_v`, `WS2812 LED state machine` を firmware に追加済み
- build / upload / wired regression smoke は通過済み
- 残る確認は、physical button と LED pattern の実機 operator validation

### Step 2

`Bundle C`

期待成果:

- O2 1-cell の value-added display
- calibration UX の先行整備

### Step 3

`Bundle D`

期待成果:

- dual-SDP hardware / firmware feasibility
- selector threshold の bench data

### Step 4

`Bundle E`

期待成果:

- actual flow feature integration
- protocol / GUI extension

## 11. 現時点の重要判断

### 11.1 すぐ実装してよいもの

- local pump button
- LED pattern parity
- recording emphasis
- O2 1-cell calibration UI

### 11.2 PoC を挟むべきもの

- dual-SDP flow frontend
- differential pressure based flow algorithm
- telemetry extension for extra measurement fields

### 11.3 追加で決めなくてよいもの

- 最終オリフィス係数
- 最終 flow calibration procedure
- O2 1-cell の factory coefficient

これらは実測フェーズで決める前提でよい。
