# Timing Jitter Investigation v1

この文書は、wired `10 ms` path に対して観測されている timing jitter について、
現時点の事実、仮説、切り分け順を整理するための investigation note である。

## 1. Question

ユーザー観測では、CSV 上の `inter_arrival_ms` は平均すると `10 ms` 近傍だが、
`1 ms` 未満から `60 ms` 級まで大きくばらつくことがある。

ここで確認したいのは、以下の切り分けである。

- device-side sampling cadence が本当に大きく揺れているのか
- host-side receive timing / GUI-side timestamping の揺れを見ているだけなのか
- ADS1115 / I2C / serial transport / GUI loop のどこが支配的要因か

## 2. Current Protocol / Runtime Understanding

現行実装の理解は次のとおりである。

- `Wired` 接続時の nominal sample period は `10 ms`
- `BLE` 接続時の nominal sample period は `80 ms`
- どちらも現時点では `1 sample` ごとに transport publish している
- BLE 側は「複数 sample をまとめて 1 packet に束ねる」実装ではない

関連実装:

- scheduler: `/Users/hiromasa/Documents/PlatformIO/Projects/zss_demokit/src/main.cpp`
- wired publish: `/Users/hiromasa/Documents/PlatformIO/Projects/zss_demokit/src/transport/SerialTransport.cpp`
- BLE publish: `/Users/hiromasa/Documents/PlatformIO/Projects/zss_demokit/src/transport/BleTransport.cpp`

## 3. Current Evidence

### 3.1 Device / Host Probe

`tools/wired_timing_probe.py` の recent run では次を観測した。

- collected telemetry samples: `1200`
- reported nominal sample period: `10 ms`
- non-unit sequence gaps: `0`
- host inter-arrival:
  - mean `10.007 ms`
  - stdev `6.521 ms`
  - min `0.003 ms`
  - p95 `20.728 ms`
  - max `21.160 ms`

### 3.2 Existing Historical Runs

過去 run でも host inter-arrival は
`mean≈10 ms`, `p95≈20 ms`, `max≈20 ms` に近い傾向を示している。
一方で `sequence gap = 0` は一貫して維持されている。

### 3.3 Host Batching Probe

`tools/wired_batch_probe.py` の recent run では、
同一 serial read chunk から複数 frame がまとめて decode されることを観測した。

- collected telemetry samples: `1200`
- non-unit sequence gap total: `0`
- receive inter-arrival:
  - mean `9.117 ms`
  - stdev `6.480 ms`
  - min `0.000 ms`
  - p95 `20.656 ms`
  - max `20.931 ms`
- samples decoded from multi-frame chunks: `513 / 1200`
- consecutive samples sharing identical receive timestamp: `304`
- frames-per-chunk histogram:
  - `1 frame`: `687`
  - `2 frames`: `405`
  - `20 frames`: `18`
- `21 frames`: `1`
- `22 frames`: `66`
- `23 frames`: `23`

### 3.4 Receive Path Sensitivity Probe

`tools/wired_receive_path_probe.py` により、
`reader-side receive timestamp` と `GUI に近い poll-handled timestamp` の差を比較した。

`poll_interval=5 ms` では次を観測した。

- reader-side receive inter-arrival:
  - mean `9.999 ms`
  - stdev `6.390 ms`
  - min `0.000 ms`
  - p95 `20.679 ms`
  - max `21.343 ms`
- poll-handled inter-arrival:
  - mean `9.995 ms`
  - stdev `6.903 ms`
  - min `0.000 ms`
  - p95 `23.707 ms`
  - max `25.404 ms`
- handling delay (`handled_at - chunk_received_at`):
  - mean `3.063 ms`
  - p95 `5.730 ms`
  - max `6.282 ms`

`poll_interval=1 ms` では handling delay は
`mean=0.657 ms`, `p95=1.180 ms` まで低下した。

`poll_interval=10 ms` では handling delay は
`mean=5.983 ms`, `p95=11.583 ms` まで増加した。

この比較から、poll interval は handled timestamp の jitter を増減させるが、
reader-side receive timestamp 自体の broad distribution は大きく変わらないと判断できる。

### 3.5 GUI Recording Semantics

CSV の `inter_arrival_ms` は、
device-side timestamp ではなく GUI/host 側の `host_received_at` 差分である。

現行では:

- wired serial read は dedicated `QThread` ではなく `QTimer(5 ms)` poll
- `host_received_at` は `frame decode 完了時刻` ではなく `serial chunk read 直後` の timestamp に寄せた
- ただし依然として GUI / host 側 timestamp であり、device-side sample tick ではない

つまり CSV の `inter_arrival_ms` は、本質的に
`host receive / GUI handling jitter` をかなり含む。

### 3.6 Device Tick Diagnostic Probe

debug branch では wired telemetry と並行して
`TimingDiagnostic` frame を publish し、
`sample_started_us` を host probe から観測できるようにした。

`tools/wired_device_tick_probe.py` の recent run では次を観測した。

- collected paired telemetry/timing samples: `1200`
- non-unit sequence gap total: `0`
- host receive inter-arrival:
  - mean `10.001 ms`
  - stdev `1.217 ms`
  - min `8.152 ms`
  - p95 `11.031 ms`
  - max `11.164 ms`
- device sample tick interval:
  - mean `10.001 ms`
  - stdev `1.204 ms`
  - min `8.378 ms`
  - p95 `10.932 ms`
  - max `10.962 ms`
- device minus host interval:
  - mean `0.000 ms`
  - stdev `0.081 ms`
  - min `-0.278 ms`
  - p95 `0.132 ms`
  - max `0.256 ms`

一方で、同じ debug firmware 上の `wired_timing_probe.py` では
`mean=9.025 ms`, `stdev=3.183 ms`, `min=0.004 ms`, `p95=11.115 ms`, `max=12.291 ms`
を観測している。

この差は、device cadence 自体よりも host 側の frame grouping / timestamp semantics が
観測値を大きく歪めていることを示す。

## 4. Interpretation

現時点では、CSV / host probe の大きな揺れをそのまま
`device-side sampling jitter` と解釈するのは危険である。

特に次の事実が重要である。

- `min=0.003 ms` は device cadence ではなく host-side batching を強く示唆する
- `wired_batch_probe.py` では `513 / 1200` sample が multi-frame chunk から decode され、
  `304` 件の consecutive sample が同一 receive timestamp を共有した
- `wired_receive_path_probe.py` では poll interval を `1 ms -> 10 ms` に振ると handling delay は増減するが、
  reader-side receive inter-arrival の broad distribution はほぼ維持された
- `wired_device_tick_probe.py` では device-side cadence が `stdev≈1.2 ms`, `p95≈10.9 ms` に収まり、
  current transport / scheduler は少なくとも `1 ms〜60 ms` 級の真の sample jitter を示していない
- `sequence gap = 0` なので sample drop は観測されていない
- `mean≈10 ms` は nominal cadence と整合する

したがって、現時点の主仮説は次である。

1. 最も支配的なのは host-side receive / buffering / serial chunking である
2. GUI poll cadence は handled timestamp jitter をさらに増やす secondary factor である
3. device-side scheduler には 1 ms 単位の量子化と数 ms 級の揺れがあるが、current evidence の範囲では許容レベルに収まる
4. ADS1115 / dual-SDP I2C read は margin を削るが、`0 ms` 近傍や `20 ms` 超の host inter-arrival を単独では説明しにくい

## 5. Plausible Sources of Jitter

### 5.1 Host / GUI Side

- serial poll が `5 ms` timer driven
- `datetime.now()` timestamp は frame decode 時点
- USB CDC buffering
- main thread / event loop scheduling

### 5.2 Device Side

- scheduler が `millis()` ベース
- ADS1115 は `860 SPS`
- legacy ADS1115 3ch read + dual-SDP read の I2C 負荷
- telemetry publish を sampling loop 内で実施

## 6. Recommended Investigation Order

### Phase 1. No-Behavior-Change Confirmation

目的:

- まず「どの観測値が何を表しているか」を固定する

実施項目:

1. `wired_timing_probe.py` を複数回実施し、host inter-arrival 分布の再現性を確認する
2. `wired_batch_probe.py` を実施し、multi-frame chunk と同一 receive timestamp の頻度を確認する
3. `wired_receive_path_probe.py` を実施し、poll interval が handled timestamp に与える影響を確認する
4. `wired_device_tick_probe.py` を実施し、device cadence と host receive cadence を直接比較する
5. GUI recording CSV と CLI timing probe を同じ session 条件で比較する
6. `sequence gap` と `status_flags` の overrun bit の有無を優先観測値として扱う

### Phase 2. Low-Risk Instrumentation

目的:

- device cadence と host receive jitter を分離して観測する

候補:

1. worker-side receive timestamp を GUI main thread timestamp と分けて記録
2. current CSV の `inter_arrival_ms` を device cadence 優先にし、host 側の値を別列で保存する
3. serial parser worker 化の前に、standalone probe 側だけ blocking read timestamp を採用
4. debug-only の `device_sample_tick_us` 追加

注記:

- production schema をすぐ広げるのではなく、まず debug/investigation path で試す
- user-facing behavior を変えないことを優先する

### Phase 3. Decision

Phase 1 / 2 の結果で次を決める。

- 主因が host 側なら:
  - GUI serial ingest の worker 化
  - CSV semantics の明確化
- 主因が device 側なら:
  - `millis()` -> `micros()` ベース scheduler 検討
  - acquisition / publish 分離
  - I2C read restructuring

## 7. Current Recommendation

現時点の推奨は、いきなり timing 改善を実装するのではなく、
まず `host jitter` と `device jitter` を分離して観測することである。

最初の安全な一手は次の 2 つ。

1. `wired_timing_probe.py`, `wired_batch_probe.py`, `wired_receive_path_probe.py`, `wired_device_tick_probe.py` による repeat measurement
2. GUI recording CSV に device cadence と host cadence を併記する
3. worker-side receive timestamp 分離の low-risk instrumentation design

## 8. Exit Criteria for This Investigation

この investigation phase は、最低限次が説明できた時点で完了とする。

- CSV `inter_arrival_ms` が何を意味するか
- device-side cadence がどの程度の jitter を持つか
- 改善対象が主に host 側か device 側か
- 次の実装変更が low-risk か high-risk か
