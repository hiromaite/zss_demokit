# Sampling / BLE / Flow Integration Plan v1

更新日: 2026-05-03

## 1. 目的

本書は、`codex/fw-acquisition-scheduler` を次の統合候補として固めながら、
BLE transport、Serial transport、flow hardware bring-up を安全に前進させるための実行計画である。

今回の焦点は以下である。

- 直近の課題解決と機能追加により Serial と BLE の見え方に不整合が出ていないか確認し、必要なら解消する
- `codex/fw-acquisition-scheduler` を main へ段階 merge できる品質まで固める
- BLE でも `10 ms` サンプル列を扱えるように、batch / ring buffer の設計と実装を進める
- GitHub PR #1 の内容を取り込み候補として扱い、flow diagnostics / characterization PoC を活かす
- 3 L syringe が使えない間は、成人男性の肺活量を使った rough な flow scale 合わせを暫定手段として扱う

## 2. 現在のブランチ関係

| Item | Current State | Notes |
| :--- | :--- | :--- |
| `main` | `0e512cb` | flow verification interleaved order まで |
| PR #1 | `codex/flow-characterization-poc` -> `main` | flow diagnostics、verification polish、disconnect plot clear、Flow Characterization PoC |
| 統合候補 | `codex/fw-acquisition-scheduler` | PR #1 相当、validated bundles、sampling cadence diagnostics、acquisition scheduler 改善を含む |

`codex/fw-acquisition-scheduler` は現時点で単なる firmware branch ではなく、
PR #1 と validated bundle integration を含む上積み branch である。
したがって main へ直接大きく merge する前に、統合単位を整理し、検証済みのまとまりごとに戻せる状態を保つ。

## 3. Main Merge 方針

main には、すべてが完了した最後に一括 merge するのではなく、安定した単位ごとに段階 merge する。

推奨順:

1. `fw-acquisition-scheduler` 安定化 slice
2. Serial / BLE parity と BLE batch slice
3. flow baseline / rough scale alignment slice

検証用には一時的な integration branch を使ってもよいが、main への merge は以下を満たした単位に限定する。

- firmware: `pio run`
- protocol / CSV: `python3.12 tools/protocol_fixture_smoke.py`
- wired実機: timing / smoke probe
- BLE変更: fake decode smoke と実機 continuity test
- GUI変更: `python3.12 -m compileall gui_prototype/src gui_prototype/main.py`
- 未実施の実機確認は `USER_TEST_REQUIRED` として文書に残す

## 4. 優先順位と処理順

| Priority | Task | Output | Merge Unit |
| :--- | :--- | :--- | :--- |
| `P0` | `fw-acquisition-scheduler` を固める | 10 ms cadence、SDP availability、full ADS read、timing diagnostics の検証結果 | scheduler stabilization |
| `P1` | Serial / BLE parity audit | transport差異表、許容差異、修正対象 | scheduler stabilization or parity slice |
| `P1` | BLE v1 field contract 修正 | BLE v1 packet が実際に運ぶ field bits のみを出す | parity slice |
| `P2` | firmware-side sample ring buffer | BLE batch 前提の `SampleFrame` 保持 | BLE batch slice |
| `P2` | BLE batch encoder / GUI decoder | 10 ms sample列をBLE notificationでまとめて配送 | BLE batch slice |
| `P3` | Flow Characterization PoC の統合確認 | raw SDP / selected DP の基礎特性取得 | flow baseline slice |
| `P3` | 肺活量を使った rough flow scale | rough coefficient と注意書き付きの暫定縦軸 | flow baseline slice |

## 5. Serial / BLE Parity 方針

完全に同じ packet layout に揃えることは目的にしない。
目的は、GUI / CSV / operator から見た論理データが矛盾しないことである。

### 5.1 揃えるもの

- `sequence`
- `status_flags`
- `nominal_sample_period_ms`
- `zirconia_output_voltage_v`
- `heater_rtd_resistance_ohm`
- `differential_pressure_selected_pa`
- `pump_on` / `heater_power_on`
- `get_capabilities`
- `get_status`
- `set_pump_state`
- `ping`

### 5.2 transport差異として許容するもの

| Item | Serial | BLE | Policy |
| :--- | :--- | :--- | :--- |
| raw `SDP810` / `SDP811` | 可能なら送る | v1単発packetでは省略、batch schema v2では送る | diagnostic扱い。GUI表示/CSVはbatch経由でSerialに寄せる |
| `zirconia_ip_voltage_v` / `internal_voltage_v` | wired-first | v1単発packetでは省略 | service visibilityはSerial中心 |
| timing diagnostic frame | あり | なし | BLEではhost/probe側のcontinuityで代替 |
| transport cadence | 10 ms every sample | batch前は低頻度 | batch導入後に10 ms sample列を復元 |

### 5.3 直近の修正方針

BLE v1の32 byte単発telemetry/status packetは、base 2ch と `differential_pressure_selected_pa` のみを運ぶ。
そのため packet内の `telemetry_field_bits` も、実際にpayloadへ載っているfieldだけにmaskする。
raw SDP や service visibility bit を BLE v1単発packetで立てると、GUIが値の存在を誤解するため禁止する。

## 6. BLE Batch / Ring Buffer 計画

### 6.1 Stage 1: Ring Buffer Skeleton

外部payloadを変えずに firmware 内へ `SampleFrame` ring buffer を追加する。
Serial と BLE の既存publishは最新frameを使い、挙動は変えない。

目的:

- measurement と transport の責務分離へ進む足場を作る
- BLE batch が過去数サンプルをまとめて読む入口を作る
- 将来のdrop counter / overrun診断に接続する

### 6.2 Stage 2: BLE Batch Payload

capability-gated extension として batch telemetry を追加する。
現行 32 byte telemetry は互換性のため残す。

初期候補:

```text
BleTelemetryBatchV2
  protocol_major: u8
  protocol_minor: u8
  batch_schema: u8
  sample_count: u8
  first_sequence: u32
  first_sample_tick_us: u32
  nominal_sample_period_ms: u16
  telemetry_field_bits: u16
  repeated:
    sample_tick_delta_us: u32
    status_flags: u32
    zirconia_output_voltage_v: float32
    heater_rtd_resistance_ohm: float32
    differential_pressure_selected_pa: float32
    differential_pressure_low_range_pa: float32
    differential_pressure_high_range_pa: float32
```

`MTU=185`, notify interval `50 ms`, sample period `10 ms` の見積もりでは、
raw SDP込みのschema v2でも 5 samples required / 5 samples fit で成立する。

### 6.3 Stage 3: GUI Decoder

GUI は batch を受け取ったら個々の `TelemetryPoint` に展開し、
plot / recording / controller は通常の telemetry stream と同じ経路を使う。
これによりBLE batch導入によるGUI側の変更面積を小さくする。

## 7. Flow Hardware Baseline 方針

3 L syringe が使えない間は、成人男性の肺活量を使った rough scale alignment を暫定手段にする。
これはATS/ERSやISOの正式な校正ではなく、縦軸のオーダーを合わせるための開発支援である。

推奨手順:

1. zero flow を複数回記録し、offset / noise floor を確認する
2. small / medium / large の呼気・吸気を記録し、符号とraw SDPの整合を見る
3. 最大呼気または最大吸気の一連操作について、`flow_rate_lpm` を時間積分する
4. operator が仮定した肺活量に積分体積が近づくように rough gain を調整する
5. 係数には `rough_lung_capacity_order_v1` のような暫定名を付け、正式校正値と混同しない

注意:

- この係数は実験・開発用であり、正式な流量校正には使わない
- 後日、3 L syringe または流量計で置き換える
- flow selector / handoff threshold の最終調整はhardware完成後に行う
- current hardware では high-range `SDP811` が low-range `SDP810` と逆向きに実装されているため、firmware 側で `SDP811` pressure polarity を反転して canonical telemetry / CSV / selected DP の符号系を揃える

## 8. 直近の実装タスク

この計画を記録した直後に、以下から着手する。

1. BLE v1単発packetの `telemetry_field_bits` を実payloadに合わせてmaskする
2. firmware-side `SampleFrame` ring buffer skeleton を追加する
3. BLE batch characteristic / encoder と GUI batch decoder を追加する
4. `pio run` と protocol fixture smoke で回帰を確認する
5. 次のbranch/PR整理に向けて、残るBLE batch実機確認項目を小さなTODOへ分解する

2026-05-03 implementation status:

- BLE v1 single-sample packet は実payloadに合わせて base 2ch + selected differential pressure の field bits にmaskするよう修正済み
- firmware-side `SampleFrame` ring buffer を追加済み
- BLE extension service に batch telemetry characteristic `8B1F1001-5C4B-47C1-A742-9D6617B10004` を追加済み
- BLE接続時の測定周期は `10 ms` とし、legacy single telemetry notify は互換用にrate-limit、batch notify は `50 ms` 目安で複数サンプルを配送する構成へ変更済み
- firmware は preferred MTU `185` を要求し、raw SDP込みの current max batch packet `156` bytes が ATT payload budget に収まる前提を明示済み
- GUI live BLE path は capabilities の `telemetry_batch_supported` feature bit を見て batch notify を優先し、受信batchを通常の `TelemetryPoint` 列へ展開する
- fake-live GUI probe では sequence gap `0`, CSV non-unit gap `0` を確認済み
- 2026-05-03 user実機確認で、BLE mode でも plot と CSV が `10 ms` sample列として復元されることを確認済み
- follow-upとして、BLE batch schema v2に raw `SDP810` / `SDP811` を追加し、flow metric card と CSV raw columns をSerialに寄せる
- 2026-05-03 user実機GUI確認で、BLE mode の flow metric card detail に raw `SDP811` / `SDP810` が表示され、CSV も `10 ms` cadence で記録されることを確認済み

## 9. USER_TEST_REQUIRED

- BLE接続時のcapabilities / telemetry field表示に矛盾がないこと
- Windows packaged GUIでBLE batch decode / recordingが破綻しないこと
- Flow Characterization PoCでraw SDP / selected DP / signed flowの符号が直感と合うこと
- 肺活量ベースのrough scaleで、縦軸のオーダーが明らかに外れていないこと

2026-05-03 follow-up:

- `codex/flow-baseline-rough-scale` では、Flow Characterization PoC の `Maximum Exhale` / `Maximum Inhale` から dummy flow の積分体積を計算し、仮定肺活量に対する rough gain multiplier を解析結果として出す
- default target volume は `4.5 L` とし、`rough_lung_capacity_order_v1` として正式校正値と区別する
- この係数は自動適用せず、operator review 後に dummy flow gain の一時調整候補として扱う
- 2026-05-03 実機 session `flow_characterization_20260503_130827` で `SDP811` high-range が `SDP810` low-range と逆極性であることを確認し、firmware 側の `SDP811` polarity normalization を追加した
- 補正後 session `flow_characterization_20260503_132640` では `Low/high sign consistency: consistent`、`SDP810` abs 約 `111 Pa` で `SDP811` へ handoff、約 `95-99 Pa` で `SDP810` へ return、rough gain `28.651x (directionally_consistent)` を確認した
