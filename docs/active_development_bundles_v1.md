# Active Development Bundles v1

更新日: 2026-05-02

## 1. 目的

本書は、2026-05-02 時点で合意した 5 つの課題群について、今後しばらく実機操作ができない前提で、
実機不要で進められる設計・実装・検証を bundle 単位に分けて管理するための作業計画である。

ここでの主眼は、すぐに merge することではなく、各 bundle を独立 branch で前進させ、
後から operator 実機テスト結果を受けて merge / 追加修正を判断できる状態にすることである。

## 2. 前提と制約

- user は当面、実機での追加テスト、配線変更、ポンプ操作、Windows 実行確認を行えない
- 開発側では local macOS 上で code review、static check、compile、offscreen GUI smoke、host-side probe logic smoke を実施する
- 実機が必要な確認は `USER_TEST_REQUIRED` として各 branch の notes に残す
- 既存の比較的安定した beta2 相当状態を壊さないため、bundle ごとに branch を分ける
- hardware 完成待ちの flow calibration / selector tuning は、今回の即時実装 scope には含めない

## 3. Branch Strategy

planning commit を起点に、以下の独立 branch を作る。

| Bundle | Branch | 主対象 | Merge 方針 |
| :--- | :--- | :--- | :--- |
| `A` | `codex/bundle-a-diagnostics` | noise / timing diagnostics | 低リスクなので最初に merge 候補 |
| `B` | `codex/bundle-b-windows-serial` | Windows wired handshake hardening | 実機 Windows 確認後に merge |
| `C` | `codex/bundle-c-connection-ux` | scan / connect UX and device naming | B の状態遷移と整合させて merge |
| `D` | `codex/bundle-d-plot-performance` | plot axis behavior and GUI performance | offscreen smoke 後、visual check を待つ |
| `E` | `codex/bundle-e-sampling-architecture` | RTOS / BLE batch architecture | まず design / PoC branch として扱う |

衝突を避けるため、`B` と `C` は `mock_backend.py` / `main_window.py` の近接領域を触る可能性が高い。
必要なら `C` は `B` を取り込んだ後の follow-up branch として rebase する。

## 4. Bundle A: Diagnostics for Pump Noise and Timing

対象課題:

- 課題1: ポンプ由来ノイズ
- 課題3: sampling jitter の観測

実装方針:

- `tools/wired_timing_probe.py` を device-side `sample_tick_us` 対応へ強化する
- host inter-arrival と device inter-arrival を分けて集計し、GUI / USB / OS 側 jitter と firmware sampling jitter を切り分ける
- pump noise 比較用の手順を validation checklist に追加する
- CSV / probe summary で `pump OFF`, `pump ON same supply`, `pump ON separate supply`, `pneumatic isolated` などの条件を比較できるようにする

この端末で可能な確認:

- Python compile
- probe logic smoke
- local wired port がある場合の短時間 non-invasive probe

USER_TEST_REQUIRED:

- pump OFF / ON 条件比較
- pump 別電源条件比較
- 空気ライン切り離しまたは疑似入力での電気ノイズ切り分け
- oscilloscope による 5V / 3.3V / ADS1115 input / PWM / FG 相関観測

## 5. Bundle B: Windows Wired Serial Handshake Hardening

対象課題:

- 課題2: Windows で serial device は見えるが接続後にデータを受け取れない
- 課題4: 接続試行中状態が分かりにくい

実装方針:

- GUI wired path で `DTR=False`, `RTS=False` を明示する
- COM open 成功と protocol handshake 成功を分離する
- `Connecting...` / `Handshake...` / `Connected` / `Failed` を UI state として扱う
- capabilities / status を受信するまで bootstrap command を数秒 retry する
- handshake timeout 時は port を閉じて、理由を event log に出す
- 成功判定は最低限 `capabilities` または `telemetry` の受信とする

この端末で可能な確認:

- Python compile
- fake / offscreen smoke
- macOS wired short probe
- retry state の unit-like helper smoke

USER_TEST_REQUIRED:

- Windows Python run
- Windows packaged exe run
- unplug / replug 後の COM 再列挙
- PlatformIO monitor や別 app が COM を掴んでいる場合のエラー表示

## 6. Bundle C: Connection UX and Auto Connect

対象課題:

- 課題4: 測定までの UX

実装方針:

- BLE は expected device が見つかったら auto-connect する。Wired は Windows COM reopen risk があるため、Bundle B 検証後に同じ方針を広げる
- scan 中、port refresh 中、connect 中、disconnect 中の button label / enable state / color を明確化する
- BLE scan timeout は短めの first scan と manual rescan を分ける
- device label は GUI 表示上 `GasSensor-Proto` を優先し、protocol / BLE filter は旧 `M5STAMP-MONITOR*` と新候補名の両方を受ける
- firmware の BLE advertising name は `GasSensor-Proto` へ変更し、UUID は維持する

Bundle C current slice:

- BLE scan phase signal を追加し、`Scan` button / selector / connect button を scanning state に同期させる
- startup scan または manual scan で expected BLE device が見つかった場合、自動で connect を開始する
- BLE live / mock connect は `connecting / connected / failed / disconnected` phase を GUI へ通知する
- probe / smoke tool の default BLE name を `GasSensor-Proto` へ更新し、fake device は legacy name も残す

この端末で可能な確認:

- offscreen GUI state smoke
- mock BLE / fake port list smoke: startup auto-connect smoke passed with `GasSensor-Proto`
- fake-live BLE GUI session probe: `gui_ble_session_probe_ok`
- Python compile and firmware build: `compileall`, `pio run`

USER_TEST_REQUIRED:

- BLE scan / auto-connect の体感速度
- Windows packaged app での button state 視認性
- 新旧 BLE name の discovery / filter

## 7. Bundle D: Plot Behavior and GUI Performance

対象課題:

- 課題5: plot axis / scrolling / responsiveness

実装方針:

- Flow Y-axis は default fixed range を持たせる
- O2 secondary axis は manual range 操作または明示的な reset path を持たせる
- X-axis は測定開始直後でも selected span 固定幅を維持する
- follow mode では latest sample time ではなく GUI real-time based range を使い、BLE interval でも滑らかに流れるようにする
- `setData()` は新規 sample がある時だけ、`setXRange()` は timer で軽く動かす
- metric cards / status labels / service visibility 更新は telemetry 全サンプルではなく UI refresh rate に throttle する

Bundle D current slice:

- Flow / O2 plot の primary Y-axis は reset / startup 時に `-5.0..+5.0 L/min` の fixed default range を使う
- O2 secondary Y-axis は `sensor_o2` の manual range state として保存できるようにする
- selected span が `2 min` 等の場合、測定開始直後でも X-axis 幅を固定し、経過後は wall-clock follow で滑らかに動かす
- plot data `setData()` は render revision / selected span / O2 calibration key が変わった時だけ更新し、follow 中の timer tick は主に X range 更新に使う
- User test で O2 right axis の実操作が効かないことを確認したため、secondary `ViewBox` の Y-axis mouse interaction を有効化した

この端末で可能な確認:

- offscreen plot controller smoke: `plot_bundle_d_smoke_ok`
- Python compile: `gui_prototype/src/controllers.py`, `gui_prototype/src/main_window.py`
- render data helper smoke: `plot_follow_bounds_smoke_ok`
- secondary axis helper smoke: `secondary_axis_mouse_enabled_smoke_ok`

USER_TEST_REQUIRED:

- manual pan / zoom / wheel の体感
- O2 right-axis 操作性
- Windows / low-resolution visual check
- long run での GUI かくつき確認

## 8. Bundle E: Sampling Architecture and BLE Batch PoC

対象課題:

- 課題3: sampling rate 向上、jitter 低減、BLE batch

実装方針:

- まず architecture note を作り、現行 loop の bottleneck と RTOS 化の候補を整理する
- measurement task、transport task、control task、LED/log task を分ける案を検討する
- ESP32-S3 の dual core / FreeRTOS task affinity を使う場合の ownership と data race 対策を明記する
- fixed-size ring buffer から serial は全サンプル送信、BLE は batch notify する設計を検討する
- BLE v1 compatibility を残し、batch は capability gated extension とする

Bundle E current slice:

- `docs/sampling_architecture_v1.md` に task ownership、ring buffer contract、BLE batch direction、jitter diagnostics、開発順を固定した
- `tools/sampling_batch_budget.py` を追加し、MTU / notify interval / sample period / compact sample size から batch feasibility を見積もれるようにした
- 初期 PoC budget では `MTU=185`, `notify=50 ms`, `sample=10 ms`, `header=8`, `sample=20` の条件で `5 samples required`, `8 samples fit`, `Verdict: fit`
- `codex/fw-acquisition-scheduler` の first BLE batch implementation slice で header は `16` bytes に確定し、firmware-side `SampleFrame` ring buffer、BLE batch characteristic、GUI batch decoder、fake-live GUI probe を追加した
- raw SDP対応後の batch schema v2 budget は `header=16`, `sample=28` で `5 samples required`, `5 samples fit`, `Payload required bytes=156`, `Payload margin bytes=26`, `Verdict: fit`
- 2026-05-03 user実機GUI確認で、BLE mode の flow card detail に raw `SDP811` / `SDP810` が表示され、CSV も `10 ms` cadence で記録されることを確認した

この端末で可能な確認:

- design document
- host-side batch budget PoC
- Python compile

USER_TEST_REQUIRED:

- firmware upload 後の timing probe
- BLE batch 実機 continuity
- Windows packaged GUI での batch decode / recording

## 9. Merge Gate

各 bundle の merge 判断は以下を最低条件にする。

- code branch は `git diff --check` を通過する
- GUI 変更は `python -m compileall gui_prototype/src tools` を通過する
- protocol / CSV 変更は `tools/protocol_fixture_smoke.py` を通過する
- firmware 変更は `pio run` を通過する
- 実機が必要な項目は `USER_TEST_REQUIRED` として明示し、未実施のまま merge しないか、risk accepted として記録する

## 10. User Test Outcome

2026-05-02 の user test 結果:

| Bundle | Result | Merge / Next Action |
| :--- | :--- | :--- |
| `A` | Diagnostics passed; device-side cadence issue detected | 診断強化は merge 候補。`10 ms` cadence 未達は Bundle E 後続の firmware scheduling task として扱う |
| `B` | Passed after Windows `COMx` selection fix | merge 候補 |
| `C` | Passed | B の修正を含む integration branch 上で merge 候補 |
| `D` | Passed after O2 right-axis interaction fix | merge 候補 |
| `E` | Batch budget PoC passed | design / PoC baseline として merge 候補 |

Bundle A の重要な観測:

- `tools/wired_timing_probe.py --samples 1200 --warmup 20`
- sequence gap: `0`
- timing diagnostics matched: `1199/1199`
- device sample interval: `mean=13.268 ms`, `p95=12.899 ms`, `max=34.816 ms`
- nominal `10 ms` を維持できていないため、次は measurement scheduling / ADS1115・SDP read timing / ring buffer 化の検討に進む

## 11. 現時点の推奨着手順

1. `codex/validated-bundles-integration` で A/B/C/D/E の validated changes をまとめる
2. integration branch で compile / fixture / firmware build を再確認する
3. merge 後の次タスクとして、`FW-VAL-020` device-side `10 ms` cadence failure を解消する firmware scheduling slice に進む
4. その後、Bundle E の設計に沿って ring buffer / BLE batch を段階実装する

## 12. Active Follow-up: Firmware Sampling Cadence

Branch: `codex/fw-sampling-cadence`

目的:

- Bundle A の live timing probe で見えた `FW-VAL-020` を、次の ring buffer / RTOS 化へ進む前に分解する
- `device sample interval` だけでなく、firmware 内の `acquisition duration`, `telemetry publish duration`, `scheduler lateness` を同時に見る
- まず cooperative scheduler の範囲で `micros()` deadline と USB CDC TX preflight を入れ、どこまで改善するか確認する

実機テストで見るポイント:

- `Device sample interval ms` が `10 ms` に近づくか
- `Firmware acquisition duration ms` が支配的か
- `Firmware telemetry publish duration ms` が支配的か
- `Firmware scheduler lateness ms` が積み上がっているか
- sequence gap が出ないか

この結果で次の実装を選ぶ:

- acquisition が支配的: ADS1115 continuous conversion / SDP read staggering / frontend scheduling を優先
- telemetry publish が支配的: SampleFrame ring buffer / transport task / diagnostic gating を優先
- scheduler lateness が支配的: FreeRTOS task affinity と priority 分離を優先

2026-05-02 実機結果:

- upload: `/dev/cu.usbmodem4101` へ成功
- final probe: sequence gap `0`, extended timing `1200/1200`
- device interval: `mean=10.293 ms`, `p95=11.950 ms`, `max=29.050 ms`
- acquisition duration: `mean=6.994 ms`, `p95=6.668 ms`, `max=28.548 ms`
- telemetry publish duration: `mean=0.080 ms`, `p95=0.090 ms`, `max=0.104 ms`
- scheduler lateness: `mean=1.654 ms`, `p95=2.474 ms`, `max=21.031 ms`

判断:

- `micros()` deadline と USB CDC TX preflight により平均 cadence は大きく改善した
- telemetry publish は支配要因ではない
- 残る spike は acquisition duration と scheduler lateness に強く出ており、次は ADS1115 / SDP acquisition scheduling を優先する

## 13. Active Follow-up: Acquisition Breakdown

Branch: `codex/fw-acquisition-scheduler`

目的:

- `FW-VAL-020` の残スパイクが ADS1115 / SDP のどちらに由来するかを確定する
- ADS1115 ch0/ch1/ch2、SDP810、SDP811 の read duration を wired timing diagnostic に追加する
- `tools/wired_timing_probe.py` で slow acquisition sample を列挙し、取得方式変更前に根拠を作る

次の判断:

- ADS1115 が支配的なら、single-shot 3ch 同期読みをやめて continuous conversion / staggered channel / lower-rate diagnostic channel を検討する
- SDP が支配的なら、SDP810 / SDP811 の交互読み、selected range 優先、raw diagnostic の低頻度化を検討する
- 両方が安定しているのに scheduler lateness が残る場合は、SampleFrame ring buffer / FreeRTOS task 分離へ進む

2026-05-02 実機結果:

- final 1200-sample probe: sequence gap `0`, acquisition breakdown `1200/1200`
- device interval: `mean=12.217 ms`, `p95=12.322 ms`
- acquisition duration: `mean=11.685 ms`, `p95=11.776 ms`
- ADC total: `mean=5.063 ms`
- ADS ch0/ch1/ch2: roughly `1.7 ms` each
- differential pressure total: `mean=6.600 ms`
- SDP low-range: `mean=6.280 ms`
- SDP high-range: `mean=0.310 ms`

判断:

- 残課題はランダムな spike ではなく、全センサー逐次取得が `10 ms` を恒常的に超える構造的問題
- 次の実装は「毎サンプル全センサーを必ず読む」から「最新値キャッシュを 10 ms sample frame に載せる」へ切り替える
- 最小実装では SDP low/high を同一 tick で両方読まず、交互または選択レンジ優先で read し、raw diagnostic は stale 値許容とする

実装方針:

- ADS1115 ch2 (`zirconia_output_voltage_v`) は毎 sample で読む
- SDP8xx は Continuous Mode のまま、起動時に full sample から scale factor を取得し、通常 loop では pressure word のみを読む
- SDP low-range / high-range は sensor availability を個別に持ち、初期化できていない、または read failure になった sensor を毎 sample で読み続けない
- ADS1115 ch0 (`zirconia_ip_voltage_v`), ch1 (`heater_rtd_resistance_ohm`), ch2 (`zirconia_output_voltage_v`) は、faulty SDP810 交換後の実測で全 channel 毎 sample 取得へ戻す
- telemetry は各 channel の latest cached value を publish する
- これは RTOS / ring buffer 化前の最小リスク slice であり、正式な高頻度取得方式は追加実測後に決める

2026-05-02 follow-up:

- Sensirion SDP8xx digital datasheet を確認し、`0x3615` Continuous Differential Pressure Average Till Read は本用途に適合するため、測定 mode 自体は変更しない
- Datasheet reference: https://sensirion.com/media/documents/90500156/6167E43B/Sensirion_Differential_Pressure_Datasheet_SDP8xx_Digital.pdf
- 実装上は `Sdp8xxSensor` が startup full sample で scale factor を cache し、runtime read は pressure word のみを取得するよう変更した
- 実機ログで current hardware は `SDP frontend initialized: low=0 high=1` であり、SDP810 low-range が初期化できていないことを確認した
- 旧実装は low-range 不在でも毎 sample read を試み、I2C timeout により `sdp_low_range_duration_us ~= 6.3 ms` を発生させていた
- sensor availability を low/high 個別に持つよう変更し、不在 channel を capabilities / telemetry field bits から外すようにした
- final 1200-sample probe: sequence gap `0`, acquisition breakdown `1200/1200`
- device interval: `mean=9.999 ms`, `p95=11.459 ms`, `max=12.492 ms`
- acquisition duration: `mean=2.325 ms`, `p95=3.663 ms`, `max=3.686 ms`
- differential pressure total: `mean=0.250 ms`, SDP low-range `0.000 ms`, SDP high-range `mean=0.237 ms`
- `tools/wired_serial_smoke.py` は capabilities / payload とも `telemetry_field_bits=107` で high-range raw のみを広告・送信することを確認した
- `tools/wired_flow_probe.py --duration-s 4` は sequence gap `0`, finite `differential_pressure_selected_pa`, finite `SDP811 high-range raw`, no finite `SDP810 low-range raw` を確認した

判断:

- 今回観測した `~6.3 ms` の支配要因は SDP81x のレンジ差や Continuous Mode の測定時間ではなく、現在の接続状態で不在の SDP810 low-range を毎 sample で読み続けていたこと
- acquisition bottleneck は current hardware 条件では解消した
- 残る timing 課題は sensor read ではなく、loop scheduler lateness / cooperative task scheduling 側として扱う
- SDP810 を再接続した状態では、capabilities が low/high 両方を広告し、low/high raw が両方 finite になることを再検証する

2026-05-02 second follow-up:

- SDP810 個体交換後、boot log と flow probe で `low=1 high=1`、capabilities `telemetry_field_bits=123`、low/high raw とも finite を確認した
- 故障個体対策として入れた safety behavior のうち、per-sensor availability / unavailable WARN log / capabilities field gating は堅牢性向上として維持する
- 一方、ADS1115 ch0/ch1 の低頻度 stagger は情報量低下にあたるため、全 ADS channel を毎 `10 ms` sample で読む構成へ戻した
- full ADS + dual SDP pressure-word read の 1200-sample probe では sequence gap `0`, acquisition `mean=5.464 ms`, ADC total `mean=5.052 ms`, differential pressure total `mean=0.392 ms`, slow acquisition `0`
- cooperative loop では deadline 直前に BLE / serial / LED などの非クリティカル処理へ入ることが jitter の主因だったため、sample deadline が近い場合は短く待って sample を先に実行する guard を追加した
- final 1200-sample probe: device interval `mean=10.000 ms`, `min=9.995 ms`, `p95=10.001 ms`, `max=10.004 ms`, device jitter `max_abs=5 us`, scheduler lateness `max=0.006 ms`
- `tools/wired_serial_smoke.py` と `tools/wired_flow_probe.py --duration-s 4` は通過し、wired commands / telemetry continuity / low-high raw payload は維持された
