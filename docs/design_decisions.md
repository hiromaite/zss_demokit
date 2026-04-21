# Design Decisions

本書は、2026-04-08 時点で確定した設計判断をまとめたメモである。

未確定の詳細項目は各ドラフト文書の `Open Questions` を参照すること。

## 1. 運用モード

- GUI は `BLE mode` と `Wired mode` の 2 モードを持つ
- 起動時には、インタラクティブなスプラッシュ / ランチャー画面でモードを選択する
- 起動後も、設定画面または設定モーダルからモード変更できるようにする
- 同時接続は行わない

補足:

- 実装上は、モード変更時に接続中デバイスの切断を要求する構成を推奨する

## 2. デバイス構成

- Wired デバイスのハードウェアは、BLE デバイスと同系統の構成を想定する
- Wired firmware は BLE firmware の改造版または派生設計を許容する
- Wired モードの GUI から見える接続形態は `Windows COM port` とする
- v1 の wired serial default は `115200 baud`, `8N1` とする

補足:

- 基板側の実装が USB CDC か USB-UART bridge かは問わず、GUI 契約上は byte-stream serial として扱う

## 3. BLE 識別子

- BLE の device name と既存 UUID は、可能な限り維持する

理由:

- 既存資産の移行を容易にするため
- GUI 実装とデバッグ時の混乱を減らすため

変更を検討する条件:

- 現行 characteristic の責務分割では新仕様を無理なく載せられない場合
- 旧仕様と新仕様を同時運用したい場合

## 4. v1 の必須操作

- `Pump ON/OFF`
- `Get Status`
- `Get Capabilities`

方針:

- BLE / Wired の両モードで、同一の論理機能セットを持たせる

## 5. v1 の表示項目

両モードで共通の主要表示項目は以下とする。

- `Zirconia Output Voltage` [V]
- `Heater RTD Resistance` [Ohm]
- `Flow Rate` [L/min]

補足:

- v1 の UI 文言は英語表記を採用する

## 6. サンプリング要求

- BLE: `50 to 100 ms` は目標値
- Wired: `10 ms` は必須要件

設計上の意味:

- Wired では parser 負荷や描画負荷よりも、まず通信安定性を優先する

## 7. タイムスタンプ方針

- 記録ファイルには GUI 受信時刻のみを残す
- デバイス側タイムスタンプは v1 の必須要件にしない

補足:

- 欠落検知のため、`sequence` などの連番は引き続き推奨する

## 8. 記録フォーマット

- BLE / Wired で共通フォーマットを採用する

## 9. グラフ UI 方針

- `example_gui` の方向性をそのまま踏襲する
- 可視化ライブラリが持つ操作性と、`example_gui` で意図的に実装された操作性を維持する
- manual pan / zoom / scale の挙動は BLE / Wired で一致させる
- plot history は数分で暗黙に消えない方針とし、pruning が必要なら explicit policy にする

## 10. GUI レイアウト方針

- `LauncherWindow` は compact に保ち、初期 mode 選択のためだけに過剰な面積を使わない
- `MainWindow` に redundant な top bar は設けない
- mode、connection、recording、warning の主要状態は left-side panels と log に集約する
- `Settings` button は left-side `Connection` panel に配置する
- left / right の主要カラム幅は content length に依存させない
- 長い status text や recording path は、panel を広げず省略表示または折り返しで扱う
- visual theme は `example_gui` に寄せた dark direction を採用する

## 11. 通信異常時の動作

- v1 では警告表示のみを要求とする
- 自動再接続は必須にしない
- 自動安全停止も必須にしない

## 12. 派生値の計算責務

推奨判断:

- 表示・解析寄りの派生値は GUI 側で計算する
- ハードウェア依存が強い値は device 側の canonical measurement として送る

v1 の解釈:

- `Flow Rate` のような表示寄りの換算値は GUI 側計算を第一候補とする
- transport では `selected_differential_pressure_pa` を canonical measurement として送る
- raw `SDP810 / SDP811` 値は diagnostic field として扱い、transport ごとに availability が違ってよい
- v1 実装では `dummy_selected_dp_orifice_v1` を使い、`selected_differential_pressure_pa -> signed flow_rate_lpm` の placeholder を採用する

placeholder formula:

```text
flow_rate_lpm = sign(selected_differential_pressure_pa) * (1.0 * sqrt(abs(selected_differential_pressure_pa)) + 0.0)
```

補足:

- 旧 `flow_sensor_voltage_v` アナログ経路は廃止した
- 正式な差圧変換係数とオリフィス係数は後続フェーズで置き換える

## 13. v1 対象外

- 校正機能
- 旧ログ / 旧 GUI / 旧 firmware との後方互換
- インストーラ作成
- オンライン配布

## 14. 配布条件

- `PyInstaller` によるパッケージ化
- 実行環境は `Windows 11 Pro`
- インストーラなし
- 管理者権限なし

補足:

- release 前の試作確認とローカルテストは macOS 上で行う
- local GUI prototype とその仮想環境は `Python 3.12` を前提とする

## 15. 優先順位

優先度は以下の順とする。

1. 通信安定性
2. UI / UX
3. 将来拡張性

## 16. 反映済みの user feedback

- serial mode でも BLE mode と同じ manual plot interaction を保証する
- plot の古い履歴が数分で暗黙に消えないよう、retention policy を見直す
- intended BLE device / serial port は filter と auto-preselect を行う
- GUI theme を `example_gui` の dark palette 方向へ戻す
- `SettingsDialog` からの BLE / Wired mode switch を正式に機能させる

## 17. 直近の未確定事項

- BLE extension service / response carrier の最終方針
- raw payload の debug 保存方針

## 18. BLE Beta Proposal

- beta 扱いの最低線として、local Mac GUI で `180 s` 以上の BLE live session を 1 回以上完走する
- 同一 session 中に `Pump ON/OFF`、`Get Status`、recording start/stop を各 1 回以上成功させる
- 同一 app run 中に manual disconnect / reconnect を 1 回以上行い、capabilities / status / telemetry が `10 s` 以内に復帰する
- BLE は目標周期系であるため、beta gate は厳密な周期保証ではなく session continuity を重視する
- planned reconnect を含む probe では、`observed telemetry duration >= session duration - reconnect timeout budget` を目安とする
- `sequence_gap_total` は connected telemetry segment 内での欠落を数え、planned reconnect downtime は含めない
- 目安として `sequence_gap_total <= 5`、transient stall warning は最大 1 回までを許容候補とする

## 19. Post-Beta Extension Direction

- old parity の quick win は、まず `protocol non-breaking` な機能から回収する
- 具体的には以下を先行対象にする
  - local physical button pump toggle
  - BLE advertising / connected LED patterns
  - voltage-target aware WS2812 LED behavior
  - recording-active visual emphasis

理由:

- operator value が高い
- 既存 transport / GUI contract を壊さずに進めやすい

## 20. O2 1-Cell Calculation Direction

- `O2 Concentration (1-cell)` は GUI derived metric として実装する
- raw / canonical measurement は引き続き `zirconia_output_voltage_v` とする
- calibration は GUI ローカルに保存し、device 側 persistent state にはしない

初期 calibration model:

```text
v_zero_ref = 2.5 V
v_air_cal = zirconia_output_voltage_v captured in ambient air
o2_percent = clamp(((v_zero_ref - v_measured) / (v_zero_ref - v_air_cal)) * 21.0, 0.0, 100.0)
```

補足:

- この式は `v_measured` が低いほど O2% が高い前提である
- 実機極性が逆なら GUI config で反転可能にする

## 21. Dual-SDP Flow Measurement Direction

- flow の新実装は `Sensirion SDP811-500Pa-D` と `SDP810-125Pa` の dual-range differential pressure sensing を前提にする
- dual-SDP は先に PoC を行い、その後に production integration へ進む
- first production target は `selector + hysteresis` であり、blend は PoC 後の改善項目とする
- flow の最終オリフィス係数は gas line 実測フェーズで確定する

推奨 placeholder:

```text
flow_rate_lpm =
    sign(differential_pressure_selected_pa) *
    k_flow_gain *
    sqrt(max(0.0, abs(differential_pressure_selected_pa) - dp_offset_pa))
```

補足:

- `k_flow_gain` と `dp_offset_pa` は初期実装では placeholder のままでよい
- dual-SDP 導入後は `selected_differential_pressure_pa` を core field とし、raw 2ch は diagnostic field として扱う
