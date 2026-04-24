# zss_demokit

`zss_demokit` は、ジルコニアセンサを使ったデモキットを制御・可視化・記録するための
firmware と desktop GUI のプロジェクトです。

M5Stack StampS3 ベースのデバイス firmware と、Python / PySide6 製の GUI アプリを
同じリポジトリで管理しています。デバイスは BLE または USB serial の wired 接続で扱うことができ、
GUI からリアルタイム計測値の表示、pump 制御、状態確認、CSV 記録、実機検証を行います。

## 何をするシステムか

- 1 つの desktop GUI から `BLE` mode と `Wired` mode のデモキットに接続する
- zirconia output voltage、heater RTD resistance、selected differential pressure、derived flow rate などをリアルタイム表示する
- GUI、BLE command、wired command、device 上の physical button から pump を制御する
- telemetry session を CSV として記録し、partial file recovery に対応する
- status flags、diagnostics、device capabilities、command acknowledgement、event を扱う
- BLE continuity、wired 10 ms telemetry、flow probe、Windows beta packaging などの検証を行う
- 旧 firmware / GUI と参考 GUI を参照しつつ、現行実装は shared protocol と modular firmware architecture へ移行する

## 現在の状態

このリポジトリは、初期検討や静的な試作だけの置き場ではありません。現在は firmware、
GUI、transport protocol、validation tools、Windows packaging を実装・修正・検証しながら
育てている作業ディレクトリです。

2026-04-24 時点の主な状態:

- firmware は repo-local PlatformIO 環境で `m5stack-stamps3` 向けに build できる
- wired serial transport は telemetry、capabilities、status snapshot、command ack、event、timing diagnostic に対応している
- BLE transport は legacy control path と、新しい status / capabilities / telemetry / event path を持つ
- GUI は wired / BLE の実接続、settings persistence、recording、warning log、plot control、flow / O2 表示を持つ
- Windows beta package は `zss_demokit_gui_win64_beta2` / `0.1.0-beta.2` として smoke 済み
- firmware 追加機能や operator validation は、小さな branch 単位で継続して進める

## ディレクトリ構成

| Path | 内容 |
| :--- | :--- |
| `src/` | firmware の実装。measurement、command、transport、protocol payload、service 群を含む |
| `include/` | firmware header、board config、protocol constants、各 module interface |
| `platformio.ini` | M5Stack StampS3 向け PlatformIO 設定 |
| `gui_prototype/` | PySide6 desktop GUI の現行実装と packaging 関連ファイル |
| `tools/` | smoke test、probe、fixture check、実機検証 helper |
| `test/fixtures/` | GUI / firmware の両方で参照する protocol golden fixture |
| `docs/` | 要求、設計、protocol、backlog、validation checklist、実装計画 |
| `resource/old_firmware/` | 旧 BLE firmware の参照実装 |
| `resource/old_gui/` | 旧 browser GUI の参照実装 |
| `resource/example_gui/` | UI 方針や実装比較に使う PySide6 参考 GUI |

## Firmware

top-level PlatformIO project が現在の firmware 本体です。measurement core、app state、
command processor、BLE transport、serial transport、payload builder、pump controller、
button controller、logger、WS2812 status LED などに責務を分けています。

Build:

```sh
./.venv_pio/bin/pio run
```

Upload:

```sh
./.venv_pio/bin/pio run -t upload --upload-port <PORT>
```

Serial monitor:

```sh
./.venv_pio/bin/pio device monitor --port <PORT> --baud 115200
```

この開発環境では global `pio` command が使えない場合があるため、基本的には repository 内の
`.venv_pio` を使います。

## Desktop GUI

GUI は `gui_prototype/` にあります。directory 名は prototype ですが、現在は実接続や packaging も
含む desktop GUI の実装ベースです。

Run:

```sh
python3.12 -m venv .venv_gui_prototype
source .venv_gui_prototype/bin/activate
pip install -r gui_prototype/requirements.txt
python gui_prototype/main.py
```

Windows beta package build:

```sh
source .venv_gui_prototype/bin/activate
pip install "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec
```

package metadata は `gui_prototype/src/app_metadata.py` で管理しています。

## 検証

firmware、GUI、protocol の変更は、実機観察だけに頼らず既存の probe / smoke tool で確認します。

共通 check:

```sh
./.venv_pio/bin/pio run
.venv_gui_prototype/bin/python -m compileall gui_prototype/src
.venv_gui_prototype/bin/python tools/protocol_fixture_smoke.py
```

Wired device:

```sh
.venv_gui_prototype/bin/python tools/wired_serial_smoke.py --port <PORT> --baudrate 115200
.venv_gui_prototype/bin/python tools/gui_wired_session_probe.py --port <PORT> --duration-s 18 --toggle-interval-s 3
.venv_gui_prototype/bin/python tools/wired_flow_probe.py --port <PORT> --duration-s 6
```

BLE device:

```sh
.venv_gui_prototype/bin/python tools/ble_smoke.py --name M5STAMP-MONITOR --telemetry-count 20 --telemetry-timeout 10 --observe-duration 8
.venv_gui_prototype/bin/python tools/gui_ble_session_probe.py --device-prefix M5STAMP-MONITOR --duration-s 180 --recording-duration-s 45 --reconnect-at-s 60
```

最新の検証状況は `docs/validation_checklist_v1.md` に記録します。

## ドキュメント

仕様変更や機能追加を始めるときは、まず以下を確認します。

- `docs/README.md`: 文書一覧
- `docs/implementation_backlog_v1.md`: milestone と extension backlog
- `docs/validation_checklist_v1.md`: 検証状況と残タスク
- `docs/communication_protocol.md`: BLE / wired に共通する logical protocol
- `docs/wired_transport_v1.md`: wired binary frame protocol
- `docs/ble_transport_v1.md`: BLE GATT / packet protocol
- `docs/firmware_worktree_plan_v1.md`: この worktree での firmware branch 運用と baseline check

古い文書には実装前の表現が残っている場合があります。現在地を判断するときは、実コード、
`implementation_backlog_v1.md`、`validation_checklist_v1.md` を優先して照合します。

## 開発ワークフロー

この worktree では、細かな機能単位で branch を切って作業します。

```sh
git status -sb
git switch -c codex/fw-<feature-name>
./.venv_pio/bin/pio run
```

実装変更、検証結果の記録、設計メモは必要に応じて分けます。これにより、`main` や別 worktree の
作業に影響を与えずに firmware 実験と修正を進めやすくします。
