# PC Logger

このディレクトリには、M5StampS3 + BME688 の `parallel mode` ワークフロー向け
PC 側ツール群が含まれています。

## 構成

- `main.py`: packaging を意識した GUI エントリポイント
- `src/gui_app.py`: GUI 実装本体
- `src/app_metadata.py`: アプリ名とバージョン定数
- `src/app_state.py`: GUI 状態コンテナ
- `src/dialogs.py`: プロファイル / 安定判定ダイアログ
- `src/qt_runtime.py`: Qt runtime 初期化
- `src/serial_worker.py`: シリアル受信 worker
- `src/serial_protocol.py`: 共通 serial 解析ヘルパー
- `src/time_axis.py`: 相対時間 / Clock 表示用 Axis
- `src/recording_io.py`: CSV / partial session 補助
- `src/stability_analyzer.py`: 安定判定ロジック
- `pc_logger.pyproject`: `pyside6-deploy` fallback 用の Qt project 記述
- `poc/serial_logger.py`: 旧 CLI ロガー PoC のアーカイブ
- `poc/README.md`: PoC アーカイブの説明
- `requirements.txt`: Python 依存
- `data/`: 取得ログの既定出力ディレクトリ

## セットアップ

```bash
cd pc_logger
source .venv/bin/activate
pip install -r requirements.txt
```

Windows で実行ファイル化する場合も、まず同じ `requirements.txt` を使って
環境を整えます。

## CLI ロガーの起動

```bash
cd pc_logger
source .venv/bin/activate
python poc/serial_logger.py --port /dev/cu.usbmodem4101
```

## GUI の起動

```bash
cd pc_logger
source .venv/bin/activate
python main.py
```

CLI ロガーで利用できるオプション:

```bash
python poc/serial_logger.py --help
```

## GUI の現在機能

- ポートスキャン
- connect / disconnect
- ライブステータス表示
- `Record` / `Stop`
- `Start Segment` / `End Segment`
- 現在のヒータープロファイル表示
- 可変長ヒータープロファイル編集（`1..10` ステップ）
- 名前付きヒータープロファイルプリセットの保存 / 読込
- 安定判定ランプ表示
- 安定判定しきい値 / 判定窓の設定保存
- profile reset
- firmware capability 表示 (`GET_CAPS`)
- 環境データのライブプロット
- ガス抵抗値とヒーター温度のライブプロット
- 表示スパン切り替え
- 起動時スプラッシュ

## CLI ロガーの現在動作

- 旧 PoC として `poc/` 配下に保管
- `115200` baud で受信
- firmware の `[csv]` 行のみを取得
- 解析済み行を `data/session_YYYYmmdd_HHMMSS.csv` に保存
- frame が 10 step に到達すると簡易進捗行を表示

## 出力スキーマ

ロガーは firmware から次の形式の行を受け取る想定です。

```text
[csv] frame_id,batch_id,frame_step,host_ms,field_index,gas_index,meas_index,temp_c,humidity_pct,pressure_hpa,gas_kohms,status_hex,gas_valid,heat_stable
```

保存される CSV は上記列に加えて、以下の列を持ちます。

- `received_at_iso`
- `source_line`

GUI が現在解釈できる行ファミリ:

- `[csv] ...`
- `[profile] key=value`
- `[status] key=value`
- `[event] key=value`

## Packaging 方針

現在の packaging 対象は Windows 11 です。

主経路:

- `PyInstaller`
- `main.spec` を使った `onedir` パッケージング

fallback:

- `pyside6-deploy`

現在の Windows ビルドメモは [../docs/windows_build.md](../docs/windows_build.md) を参照してください。
Windows 試験ユーザー向けの操作説明は
[../docs/windows_gui_user_guide.md](../docs/windows_gui_user_guide.md) を参照してください。
