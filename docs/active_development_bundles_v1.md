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

- BLE / Wired ともに expected device が 1 件なら auto-connect する option を追加する
- scan 中、port refresh 中、connect 中、disconnect 中の button label / enable state / color を明確化する
- BLE scan timeout は短めの first scan と manual rescan を分ける
- device label は GUI 表示上 `Gas Sensor Proto` を優先し、protocol / BLE filter は旧 `M5STAMP-MONITOR` と新候補名の両方を受ける
- firmware の BLE advertising name 変更は compatibility risk があるため、C branch では候補実装または configurable constant として扱う

この端末で可能な確認:

- offscreen GUI state smoke
- mock BLE / fake port list smoke
- Python compile

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

この端末で可能な確認:

- offscreen plot controller smoke
- Python compile
- render data helper smoke

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

この端末で可能な確認:

- design document
- host-side encoder / decoder PoC
- fixture smoke

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

## 10. 現時点の推奨着手順

1. Planning commit を作る
2. `A` を進め、device / host timing を分離できるようにする
3. `B` を進め、Windows serial handshake と UI state を堅牢化する
4. `D` を進め、実機不要の plot logic と UI throttle を実装する
5. `C` を `B` と整合させながら進める
6. `E` は architecture note と payload PoC から開始する
