# Flow Verification Plan v1

## 1. 目的

本書は、`zss_demokit` における flow system の `verification` 機能を、
実装に着手できる粒度まで具体化するための設計メモである。

本機能は、差圧ベース flow measurement path の実用性を確認し、
hardware PoC、device tuning、将来の校正作業へつなげることを目的とする。

本書は現時点では `flow calibration` ではなく、
`flow verification` を主題とする。

## 2. 背景と規格参照方針

flow verification の考え方は、以下をベースにする。

- `ATS/ERS 2019 Standardization of Spirometry`
- `ISO 26782 Respiratory therapy equipment — Spirometers intended for the measurement of forced expiratory manoeuvres in humans`

設計判断:

- v1 では `3 L syringe` を使った guided verification workflow を採用する
- low / medium / high の複数 speed band を確認する
- 受け入れ基準の基本線は `3.000 L ± 3 %` とする
- ただし v1 は PoC / design validation を主目的とするため、hard gate にはしない

## 3. 用語整理

### 3.1 Verification

- 現在の measurement path が使える状態かを確認するための guided check
- operator による step-based workflow を持つ
- result は `Pass / Pass with advisory / Out of target / Incomplete` で扱う

### 3.2 Calibration

- 差圧から流量への変換係数や model を更新する行為
- dual-SDP の selector tuning や gain fitting を含む
- hardware 完成後の後続フェーズで扱う

判断:

- v1 では `Flow Verification` を実装対象とする
- `Flow Model Calibration` は future advanced feature として分離する

## 4. v1 の基本方針

- `Settings > Device > Flow Verification` を正式導線にする
- verification 本体は `Flow Verification Dialog` として modal wizard で実装する
- exhalation / inhalation の両方向を v1 から対象にする
- exhalation を primary 判定対象、inhalation を extended check として扱う
- ただし v1 は strict gate にしない
- retry は推奨に留め、pass しなくても operator は次へ進める
- dual-SDP 固有の value は `diagnostic visibility` として見えるようにする

## 5. UI 導線

### 5.1 Settings 内の配置

`Settings > Device` に以下の flow verification card を置く。

- `Start Guided Verification`
- `Last result`
- `Last completed at`
- `Last criterion version`
- `Show latest details`

補足:

- `Settings` には入口と latest summary だけを置く
- 実作業は `Flow Verification Dialog` で行う

### 5.2 Dialog の構成

Dialog は以下の 3 領域を持つ。

- top header
  - title
  - subtitle
  - progress (`Step x of y`)
  - section badge (`Zero Check`, `Exhalation`, `Inhalation`, `Review`)
- center content
  - step 固有の instruction / live metrics / result view
- bottom action row
  - `Back`
  - `Retry`
  - `Accept and continue`
  - `Skip`
  - `Cancel`
  - `Save Verification` (`Review` 時のみ)

## 6. Step 構成

v1 の guided verification は以下の step を持つ。

1. `Overview`
2. `Zero Check`
3. `Exhalation Low`
4. `Inhalation Low`
5. `Exhalation Medium`
6. `Inhalation Medium`
7. `Exhalation High`
8. `Inhalation High`
9. `Review`

補足:

- exhalation / inhalation を両方入れる
- operator の自然な操作順に合わせ、各 speed band で `吐く -> 吸う` を交互に進める
- progress 上は `Step 1 of 9` 形式を想定する

## 7. 各 Step の operator 体験

### 7.1 Overview

役割:

- verification の目的説明
- 3 L syringe 使用の案内
- filter / flow path を実運用条件に合わせる注意
- 本 workflow は PoC 向けであり、out-of-target でも continuation 可能であることの説明

主ボタン:

- `Start Verification`

### 7.2 Zero Check

役割:

- no-flow 時の stability を確認する
- zero drift の大きさを advisory として表示する

表示項目:

- current flow
- selected source
- `SDP810 raw`
- `SDP811 raw`
- stability badge
- advisory text

許可する操作:

- `Retry`
- `Accept and continue`
- `Skip`

### 7.3 Stroke Step

各 stroke step は以下を共通とする。

表示項目:

- instruction text
- live flow
- integrated volume
- selected source
- `SDP810 raw`
- `SDP811 raw`
- capture status
  - `Waiting for motion`
  - `Capturing`
  - `Captured`
- captured result
  - recovered volume
  - error %
  - peak flow
  - stroke duration
  - advisory text

操作:

- `Retry`
- `Accept and continue`
- `Skip`

### 7.4 Review

役割:

- 6 stroke + zero check の結果を一覧表示する
- operator note を残す
- session を保存する

表示項目:

- zero check summary
- exhalation summary
- inhalation summary
- 6-row result table
- overall summary
- operator note

## 8. Speed Band の扱い

v1 では speed band を自動分類しない。
step 自体が band を定義する。

### 8.1 Exhalation

- `Low`: `Push the 3 L syringe slowly and smoothly.`
- `Medium`: `Move the 3 L syringe at a moderate, steady speed.`
- `High`: `Move the 3 L syringe quickly in one smooth stroke.`

### 8.2 Inhalation

- `Low`: `Pull the 3 L syringe slowly and smoothly.`
- `Medium`: `Pull the 3 L syringe at a moderate, steady speed.`
- `High`: `Pull the 3 L syringe quickly in one smooth stroke.`

判断:

- v1 は operator instruction based banding とする
- internal では peak flow や duration を記録するが、band 判定の主役にはしない

## 9. 判定思想

### 9.1 Strict gate を採用しない

v1 の目的は PoC / design validation である。
このため、verification result は operator guidance として扱い、
workflow の進行を hard block しない。

### 9.2 Stroke-level status

各 step は以下の result status を持つ。

- `pass`
- `advisory`
- `out_of_target`
- `incomplete`
- `skipped`

### 9.3 Section-level status

- `pass`
- `pass_with_advisory`
- `out_of_target`
- `incomplete`

### 9.4 Overall status

- `pass`
- `pass_with_advisory`
- `fail`
- `incomplete`

### 9.5 Primary / Extended 判定

- exhalation は primary verification
- inhalation は extended verification

推奨 aggregate logic:

- exhalation 3 条件 pass, inhalation 3 条件 pass
  - `pass`
- exhalation pass, inhalation に advisory / out_of_target がある
  - `pass_with_advisory`
- exhalation に out_of_target がある
  - `fail`
- skip や capture 不成立がある
  - `incomplete`

補足:

- 実装上はこの aggregate logic を function として切り出し、将来差し替え可能にする

## 10. 閾値と advisory の扱い

v1 では exact threshold の最終化を急がず、調整しやすい定数群として持つ。

想定定数:

- `start_threshold_lpm`
- `stop_threshold_lpm`
- `minimum_duration_ms`
- `settle_duration_ms`
- `minimum_integrated_volume_l`
- `capture_timeout_ms`
- `zero_stability_window_ms`
- `zero_stability_threshold_lpm`

表示方針:

- strict fail ではなく `Retry recommended` を主に使う
- operator は `Accept and continue` を選べる
- `Skip` も許可する

## 11. 内部状態モデル

### 11.1 Session State

- `idle`
- `overview`
- `zero_check`
- `exhalation_low`
- `exhalation_medium`
- `exhalation_high`
- `inhalation_low`
- `inhalation_medium`
- `inhalation_high`
- `review`
- `completed`
- `cancelled`

### 11.2 Capture State

- `not_armed`
- `armed`
- `capturing`
- `captured`
- `accepted`
- `skipped`

### 11.3 Zero Check State

- `settling`
- `evaluated`
- `accepted`
- `skipped`

## 12. イベントモデル

### 12.1 Session-level events

- `start_verification`
- `next_step`
- `previous_step`
- `cancel_verification`
- `save_verification`

### 12.2 Capture-level events

- `arm_capture`
- `motion_detected`
- `capture_completed`
- `retry_step`
- `accept_step`
- `skip_step`

### 12.3 Measurement-derived events

- `zero_stable`
- `zero_unstable`
- `stroke_timeout`
- `capture_invalid`
- `capture_valid`

## 13. Stroke Capture Algorithm v1

v1 は `threshold + settle window` ベースの semi-automatic capture を採用する。

### 13.1 開始条件

- exhalation step: `flow_rate_lpm > start_threshold_lpm`
- inhalation step: `flow_rate_lpm < -start_threshold_lpm`

### 13.2 capturing 中の処理

- sample を capture buffer に保持する
- `integrated_volume` を flow と sample interval から積分する
- `peak_flow` を更新する
- selected source history を蓄積する
- source change があれば `source_switch_count` を増やす

### 13.3 終了条件

- `abs(flow_rate_lpm) < stop_threshold_lpm` が `settle_duration_ms` 続く
- かつ `minimum_duration_ms` を満たす
- かつ `minimum_integrated_volume_l` を満たす

### 13.4 invalid capture

- timeout
- duration too short
- integrated volume too small
- expected direction と大きく逆の flow が支配的

補足:

- invalid でも hard fail にしない
- advisory を出したうえで `Retry / Accept and continue / Skip` を許す

## 14. Dual-SDP 診断情報の扱い

flow verification は dual-SDP system の挙動確認も目的に含む。
したがって、各 stroke では measurement accuracy だけでなく
selector の振る舞いも見える必要がある。

v1 で見せる値:

- `selected source`
- `dominant source`
- `source switch count`
- `SDP810 raw`
- `SDP811 raw`
- `selected differential pressure`

設計判断:

- pass/fail の主判定は volume accuracy で行う
- dual-SDP 情報は diagnostic visibility として提示する

## 15. 保存データモデル

### 15.1 VerificationSession

session 単位の保存モデル:

- `session_id`
- `started_at_iso`
- `completed_at_iso`
- `status`
- `transport_type`
- `mode`
- `device_identifier`
- `firmware_version`
- `protocol_version`
- `criterion_version`
- `zero_check_result`
- `exhalation_result`
- `inhalation_result`
- `overall_result`
- `operator_note`

### 15.2 VerificationStrokeResult

stroke 単位の保存モデル:

- `step_id`
- `direction`
- `speed_band`
- `result_status`
- `attempt_count`
- `accepted_attempt_index`
- `recovered_volume_l`
- `reference_volume_l`
- `volume_error_l`
- `volume_error_percent`
- `peak_flow_lps`
- `stroke_duration_s`
- `dominant_source`
- `source_switch_count`
- `selected_dp_mean_pa`
- `selected_dp_peak_abs_pa`
- `sdp810_mean_pa`
- `sdp811_mean_pa`
- `warning_flags`
- `note`

### 15.3 ZeroCheckResult

- `status`
- `mean_flow_lpm`
- `peak_abs_flow_lpm`
- `selected_dp_mean_pa`
- `sdp810_mean_pa`
- `sdp811_mean_pa`
- `warning_flags`

### 15.4 保存形式

v1 は JSON ベースを推奨する。

理由:

- session / stroke / zero check の nested structure を持ちやすい
- future history view と相性がよい
- review summary をそのまま保持しやすい

## 16. Controller 責務

### 16.1 `FlowVerificationController`

責務:

- session 開始 / 中断 / 保存
- session step 遷移
- capture state 管理
- measurement を見た stroke capture 判定
- zero check 結果生成
- stroke 結果生成
- review summary 生成

### 16.2 Measurement Feed Adapter

責務:

- live telemetry から verification 用の measurement を抜き出す
- `flow_rate_lpm`
- `selected differential pressure`
- `SDP810 raw`
- `SDP811 raw`
- `selected source`
- sample timestamp

### 16.3 Verification Persistence

責務:

- verification session の保存
- latest result summary の読み出し
- future history view への拡張点を提供

## 17. 実装順

推奨順:

1. `VerificationSession` / `VerificationStrokeResult` / `ZeroCheckResult` dataclass 相当の定義
2. `FlowVerificationController` の状態機械
3. fake telemetry feed で 1 stroke capture を確認
4. `FlowVerificationDialog` skeleton
5. exhalation 3 stroke
6. inhalation 3 stroke
7. review + persistence
8. advisory polish

## 18. v1 でやらないこと

- strict compliance gate
- formal model calibration
- coefficient fitting
- waveform full export
- verification certificate 生成
- long-term history compare dashboard

## 19. Open Questions

- `start / stop / settle` の初期閾値をどこから始めるか
- verification result の local storage path をどうするか
- latest result summary を settings にどう見せるか
- future に `history` を同じ dialog に入れるか、別 dialog にするか

## 20. まとめ

v1 の `Flow Verification` は、以下の性格を持つものとして実装する。

- `ATS/ERS-aligned 3 L syringe guided verification`
- exhalation / inhalation の両方向を含む
- strict gate ではなく soft advisory を中心にする
- dual-SDP diagnostics を operator に見える形で併置する
- formal calibration は future feature として分離する
