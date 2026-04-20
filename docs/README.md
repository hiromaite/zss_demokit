# New System Planning Docs

このディレクトリは、`zss_demokit` における新システムの要件定義と設計検討の
初期ドラフトをまとめるための場所です。

現時点の文書は、以下の既存資産を踏まえた「雛形」です。

- `resource/old_firmware/`: BLE ベースの旧センサデバイス firmware
- `resource/old_gui/`: 旧 Web GUI
- `resource/example_gui/`: Python / PySide6 ベースの参考 GUI

GUI レイアウト関連の文書は、`gui_prototype/` に置いた local PySide6 prototype の
確認結果も反映して更新していく。
現時点では、approved layout に加えて local settings persistence、configured recording
directory、partial recovery detection、wired real transport まで反映済みである。

## 文書一覧

- `design_decisions.md`
  - 現時点で確定した設計判断の一覧
- `system_requirements.md`
  - システム全体の目的、スコープ、要求事項、制約、未決事項
- `system_architecture.md`
  - 新システムの責務分割、接続モデル、コンポーネント構成、データフロー
- `gui_implementation_spec_v1.md`
  - GUI の画面構成、状態遷移、主要操作、描画方針の実装仕様
- `device_adapter_contract_v1.md`
  - `DeviceAdapter` の責務、signals、I/O 契約、threading 方針
- `communication_protocol.md`
  - 通信方式の設計方針、共通論理メッセージ、BLE / wired への割り当て案
- `ble_transport_v1.md`
  - BLE transport の具体仕様、GATT 構成、packet layout、message flow
- `wired_transport_v1.md`
  - wired transport の具体仕様、binary frame layout、message flow
- `protocol_catalog_v1.md`
  - v1 の canonical field、status flag、command、capability の一覧
- `recording_schema.md`
  - BLE / wired 共通の記録ファイルスキーマ案
- `legacy_current_feature_matrix.md`
  - 旧 firmware / 旧 GUI と現行 firmware / 現行 GUI の機能比較表
- `feature_extension_plan_v1.md`
  - parity restore と新規拡張機能の実装順、PoC、依存関係の計画
- `implementation_backlog_v1.md`
  - GUI / firmware / integration を含む実装バックログとマイルストーン
- `firmware_implementation_plan_v1.md`
  - 新 firmware のモジュール分割案、ランタイムモデル、実装順
- `validation_checklist_v1.md`
  - 現段階で実施可能な GUI / firmware / integration 検証項目
- `windows_beta_smoke_checklist_v1.md`
  - Windows 11 Pro で beta packaging と実機 smoke を行うための手順

## 読み進め方

1. `system_requirements.md` で要求の前提を合わせる
2. `system_architecture.md` で責務分割とシステム境界を固める
3. `gui_implementation_spec_v1.md` で GUI の画面と振る舞いを確認する
4. `device_adapter_contract_v1.md` で adapter 境界を固定する
5. `communication_protocol.md` で transport ごとの実装方針を詰める
6. `ble_transport_v1.md` と `wired_transport_v1.md` で transport 詳細を確認する
7. `protocol_catalog_v1.md` で v1 の名前と意味を固定する
8. `recording_schema.md` で保存形式を確認する
9. `legacy_current_feature_matrix.md` で旧資産との差分と未回収機能を確認する
10. `feature_extension_plan_v1.md` で次フェーズの機能追加計画を確認する
11. `firmware_implementation_plan_v1.md` で firmware の骨格を確認する
12. `implementation_backlog_v1.md` で着手順と依存関係を確認する
13. `validation_checklist_v1.md` で現段階の検証対象を確認する
14. `windows_beta_smoke_checklist_v1.md` で Windows packaging / smoke の流れを確認する

## 運用メモ

- まずは「新システムで何を満たすべきか」を先に固定する
- 旧資産の実装詳細は参考にするが、そのまま踏襲する前提にはしない
- 文書内の `TODO` / `TBD` / `Open Questions` は、以後の設計会話で順次確定する
- GUI 関連文書は、top bar を持たない main layout、compact launcher、stable column width の prototype feedback を取り込んで更新する
- GUI 関連文書は、controller layer と `QSettings` ベースの persistence 実装進捗も反映して更新する
- shared regression baseline は `test/fixtures/protocol_golden_v1.json` に置き、protocol / CSV 回帰は `tools/protocol_fixture_smoke.py` で確認する
