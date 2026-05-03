# System Usability Review v1

更新日: 2026-04-30

## 1. 目的

本書は、現時点の GUI、firmware、通信 protocol、検証 tool、既存 document を横断して見直し、
次に実装すべき機能と対処すべき課題を usability / user experience の観点も含めて順位付けするための
review note である。

この review は、現在の beta-quality 実装を否定するものではなく、ここまで積み上げた実装を
「PoC と実機調整に強い道具」から「operator が迷わず使える計測システム」へ近づけるための整理である。

## 2. 確認範囲

以下の範囲を、file inventory、keyword scan、主要責務の targeted read、既存 validation log の照合により確認した。
この review は formal static analysis ではないが、GUI / firmware / document / tool の現状認識に必要な
files は省略せず対象にした。

### 2.1 Documentation and Project Files

```text
README.md
platformio.ini
docs/README.md
docs/ble_transport_v1.md
docs/communication_protocol.md
docs/design_decisions.md
docs/device_adapter_contract_v1.md
docs/feature_extension_plan_v1.md
docs/firmware_implementation_plan_v1.md
docs/firmware_worktree_plan_v1.md
docs/flow_verification_plan_v1.md
docs/gui_implementation_spec_v1.md
docs/implementation_backlog_v1.md
docs/legacy_current_feature_matrix.md
docs/protocol_catalog_v1.md
docs/recording_schema.md
docs/system_architecture.md
docs/system_requirements.md
docs/validation_checklist_v1.md
docs/windows_beta_smoke_checklist_v1.md
docs/wired_transport_v1.md
gui_prototype/README.md
gui_prototype/packaging_README.md
gui_prototype/requirements.txt
gui_prototype/zss_demokit_gui.spec
```

### 2.2 GUI Source

```text
gui_prototype/src/app_metadata.py
gui_prototype/src/app_state.py
gui_prototype/src/ble_protocol.py
gui_prototype/src/controllers.py
gui_prototype/src/dialogs.py
gui_prototype/src/flow_characterization.py
gui_prototype/src/flow_verification.py
gui_prototype/src/launcher_window.py
gui_prototype/src/main_window.py
gui_prototype/src/mock_backend.py
gui_prototype/src/protocol_constants.py
gui_prototype/src/qt_runtime.py
gui_prototype/src/recording_io.py
gui_prototype/src/settings_store.py
gui_prototype/src/theme.py
gui_prototype/src/wired_protocol.py
```

### 2.3 Firmware Source

```text
include/README
include/app/AppState.h
include/app/CapabilityBuilder.h
include/app/CommandProcessor.h
include/app/StatusFlags.h
include/board/BoardConfig.h
include/measurement/AdcFrontend.h
include/measurement/DifferentialPressureFrontend.h
include/measurement/MeasurementCore.h
include/measurement/Sdp8xxSensor.h
include/measurement/SensorData.h
include/protocol/PayloadBuilders.h
include/protocol/ProtocolConstants.h
include/services/HeaterPowerController.h
include/services/InputButtonController.h
include/services/Logger.h
include/services/PumpController.h
include/services/StatusLedController.h
include/transport/BleTransport.h
include/transport/SerialTransport.h
include/transport/TransportTypes.h
src/app/AppState.cpp
src/app/CapabilityBuilder.cpp
src/app/CommandProcessor.cpp
src/main.cpp
src/measurement/AdcFrontend.cpp
src/measurement/DifferentialPressureFrontend.cpp
src/measurement/MeasurementCore.cpp
src/measurement/Sdp8xxSensor.cpp
src/protocol/PayloadBuilders.cpp
src/services/HeaterPowerController.cpp
src/services/InputButtonController.cpp
src/services/Logger.cpp
src/services/PumpController.cpp
src/services/StatusLedController.cpp
src/transport/BleTransport.cpp
src/transport/SerialTransport.cpp
```

### 2.4 Tools and Fixtures

```text
test/README
test/fixtures/protocol_golden_v1.json
tools/ble_backend_smoke.py
tools/ble_smoke.py
tools/firmware_fixture_verify.cpp
tools/flow_characterization_analyze.py
tools/generate_app_icon.py
tools/gui_ble_session_probe.py
tools/gui_wired_session_probe.py
tools/protocol_fixture_smoke.py
tools/sdp_serial_probe.py
tools/wired_flow_probe.py
tools/wired_serial_smoke.py
tools/wired_soak_probe.py
tools/wired_timing_probe.py
```

## 3. 現状認識

### 3.1 GUI

現行 GUI は、prototype という directory 名ではあるが、実質的には current desktop application の実装ベースである。
BLE / Wired mode、device auto-filter / preselect、mode switch、recording、plot、warning/event log、
O2 calibration、Flow Verification、Flow Characterization PoC、Windows packaging path まで持っている。

良い点:

- left column に connection / control / recording / device status が集約され、top bar redundancy は解消済みである
- right column は metric cards、2 plots、log に整理され、operator が中心値と波形を同時に見られる
- plot は manual pan / zoom、history retention、downsampling、antialias off により実用寄りになっている
- disconnect 時に plot buffer を clear するため、再接続後に古い session と重なりにくい
- Settings から O2 calibration、Flow Verification、Flow Characterization に到達できる

弱い点:

- `SettingsDialog` に device action、mode setting、O2 calibration、Flow Verification、Flow Characterization が集まり始めている
- operator が日常的に見る画面と、engineering / diagnostic の深い情報がまだ明確には分離されていない
- right column の plot / log 高さは local macOS では accept だが、Windows や低解像度での visual regression risk が残る
- plot は操作できるが、operator 向けの `Pause graph` や series visibility toggle がない
- warning/event log は折りたたみ可能だが、filter / export / search / session persistence はまだ薄い
- `main_window.py` と `dialogs.py` が大きく、今後の UI 追加時に regression risk が上がりやすい

### 3.2 Firmware

firmware は top-level PlatformIO project に統合され、measurement、state、command、payload、transport、service の
責務分割が成立している。wired は `10 ms` path、BLE は目標周期 path として整理されており、
dual-SDP differential pressure、ADS1115、pump PWM、physical button、WS2812 LED も統合済みである。

良い点:

- `CommandProcessor` は pump / heater command を共通処理し、pump OFF 時に heater を OFF へ落とす
- pump OFF のまま heater ON を要求した場合は `InvalidState` として拒否する
- active transport に応じた telemetry cadence と payload capability がある
- diagnostic bits、status flags、event emission により、異常の可視化に必要な土台がある
- dual-SDP は raw readout、selector、selected differential pressure の production integration が始まっている

弱い点:

- flow の最終 calibration、selector threshold、hysteresis tuning は物理流路 / orifice / gas line 完成待ちである
- diagnostic bits は firmware 側にはあるが、GUI で operator-readable label として十分には見えていない
- safety interlock は実装済みだが、今後の変更で壊さないための explicit regression item が必要である
- BLE payload は制約があるため、wired-first diagnostic と BLE-unavailable fields の扱いを UX 上も明示する必要がある

### 3.3 Integration and Validation

protocol fixture、GUI session probe、wired / BLE smoke、flow probe、timing probe、Windows beta smoke が整備されている。
現時点の最大の強みは、実機確認と local regression の両方で前進できることである。

良い点:

- Windows beta packaging と Wired / BLE smoke が通過済みで、配布前提の path がある
- BLE continuity / reconnect は long probe で `sequence_gap_total=0` を確認済みである
- wired path は `10 ms` telemetry、recording、CSV finalize、plot ingest を確認済みである
- flow characterization / verification は、hardware completion 前でもデータ取りの作業導線として使える

弱い点:

- cross-resolution / Windows visual QA はまだ smoke checklist として明確に固定されていない
- verification / characterization history は保存と閲覧が始まった段階で、比較・傾向把握は浅い
- recording 後の quick review、latest file summary、folder open などの post-run UX がまだ薄い

## 4. 理想状態との差分

理想状態では、通常 operator は以下の流れだけで迷わず使える。

1. mode を選ぶ
2. intended device に自動接続または明確に接続する
3. pump / recording / plot を操作する
4. 必要なら O2 calibration や flow verification を guided workflow として実施する
5. 終了後に CSV / summary / warning をすぐ確認できる

一方、開発者や hardware bring-up では以下が必要である。

1. raw SDP values、selected source、diagnostic bits、service voltages を見られる
2. characterization session を保存して後から比較できる
3. BLE / Wired の field availability 差を誤解なく把握できる
4. timing / continuity / sequence gap を probe と GUI 上の summary で確認できる

現状は両方の機能が同じ面に集まり始めている。したがって次の UX 改善は、
機能追加そのものよりも `operator simple surface` と `engineering tools surface` を分けることが効果的である。

## 5. 優先順位

| Rank | Item | Criticality | Value | Frequency | 判定 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `P0-HW` | Flow calibration / selector final tuning | High | High | Medium | hardware 完成待ち。現時点では dummy law と characterization support を維持する |
| `P0-SAFE` | Pump / heater interlock regression protection | High | High | Low | 現行 firmware には interlock があるため、今後の regression test 項目として明示する |
| `P1-UX-001` | Operator surface と Engineering / Tools surface の分離 | Medium | High | High | Settings が肥大化し始めたため、次の大きな UX 改善候補 |
| `P1-UX-002` | Plot pause / freeze と series visibility toggle | Low | High | High | 計測中に「止めずに見たい」「必要な系列だけ見たい」需要が高い |
| `P1-UX-003` | Windows / low-resolution visual validation | Medium | High | Medium | 既に layout feedback が複数回発生しており、beta 配布前に固定したい |
| `P1-OBS-001` | Diagnostic availability と diagnostic bits の label 表示 | Medium | High | Medium | BLE / Wired 差、optional field、service diagnostics の誤解を減らす |
| `P2-DATA-001` | Recording latest summary / open folder / quick review | Low | Medium | High | 計測後の導線を短くし、operator の作業摩擦を下げる |
| `P2-HIST-001` | Verification / Characterization history comparison | Low | Medium | Medium | calibration 準備や hardware tuning の判断材料を蓄積しやすくする |
| `P2-LOG-001` | Warning / event log filter, export, persistence | Medium | Medium | Medium | debug とユーザー報告の再現性を上げる |
| `P2-MAINT-001` | GUI module split | Low | Medium | Medium | `main_window.py` / `dialogs.py` 肥大化による将来 regression risk を下げる |
| `P3-REL-001` | Installer / updater / signing / formal release notes | Low | Medium | Low | beta2 以降、外部配布が増える段階で検討する |
| `P3-ADV-001` | BLE raw diagnostics on-demand expansion | Low | Low | Low | BLE payload 制約があるため、必要性が明確になるまで後回し |

## 6. 推奨実装順

### 6.1 直近で進めるべき順序

1. `P0-SAFE` を validation checklist へ固定し、pump / heater interlock を壊さない smoke を明確化する
2. `P1-OBS-001` として diagnostic bits / optional fields を GUI で読める label に近づける
3. `P1-UX-002` として plot pause / series visibility toggle を入れ、計測中の観察体験を改善する
4. `P1-UX-001` として Settings 内の tools を整理し、Engineering / Tools hub を検討する
5. `P1-UX-003` として Windows / low-resolution visual validation checklist を追加し、右 column / plot splitter / log height を確認する
6. hardware 完成後に `P0-HW` の flow calibration / selector tuning / verification threshold を再開する

### 6.2 並列化しやすい単位

| Stream | 内容 | 備考 |
| :--- | :--- | :--- |
| `Safety / Firmware` | interlock regression、diagnostic bit definition、event/status parity | GUI polish と独立しやすい |
| `GUI Operator UX` | plot pause、series visibility、recording quick review | 実装後すぐ user feedback を取りやすい |
| `Engineering Tools` | Tools hub、Flow Verification / Characterization の IA 整理、history comparison | hardware completion までの準備価値が高い |
| `Validation / Release` | Windows visual smoke、packaging checklist、known-gap update | 実装 stream と並行可能 |

2026-05-03 update:

- `P0-SAFE` は `tools/command_processor_smoke.py` により host-side regression として固定した
- `P1-OBS-001` は Device Status の raw SDP / service voltage / BLE batch availability label と `tools/gui_observability_smoke.py` により first slice を完了した
- `P1-UX-002` は Plot Toolbar に `Pause Plot` と series visibility toggle を追加し、取得 / recording を止めずに表示だけ freeze できる first slice を完了した
- 次に進めるなら `P1-UX-001` Settings 内の Engineering / Tools hub 整理か、`P1-UX-003` Windows / low-resolution visual validation が実機完成待ち期間でも価値を出しやすい

## 7. 今は深追いしないこと

- flow の最終換算式、selector threshold、bidirectional threshold は、物理流路と gas-line 測定が揃うまで仮のままにする
- BLE payload を raw diagnostics のためだけに大きくする判断は、必要性が明確になるまで避ける
- Flow Verification v1 は soft advisory のまま維持し、PoC / design validation の速度を優先する
- Settings の全面作り直しは急がず、まず `Tools / Engineering` への動線整理から始める

## 8. ドキュメント反映方針

- 実装順と優先順位は `implementation_backlog_v1.md` に反映する
- operator / engineering surface の分離判断は `design_decisions.md` に反映する
- smoke / regression に落とせるものは `validation_checklist_v1.md` に反映する
- 本書は、次の UX / usability planning の入口として `docs/README.md` から参照する
