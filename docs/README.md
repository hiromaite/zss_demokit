# Documentation Index

この README は、`docs/` に置かれた `zss_demokit` 関連文書の入口です。
プロジェクト全体の概要、構成、使い方は repository root の `README.md` を参照してください。

このディレクトリには、要求、設計、実装計画、検証結果、今後の追加機能実験に関する
詳細文書を置いています。

現在のプロジェクトは初期検討フェーズを越えており、top-level PlatformIO firmware、
PySide6 GUI prototype、BLE / wired transport、CSV recording、Windows beta packaging、
flow verification などを実装・修正・検証しながら育てている段階です。一部機能は
beta 相当の smoke や operator validation を通過しており、文書は設計案だけでなく
実装済み内容、検証ログ、残タスク、次の実験候補を追跡する役割を持ちます。

文書は、以下の既存資産も参照しつつ更新しています。

- `resource/old_firmware/`: BLE ベースの旧センサデバイス firmware
- `resource/old_gui/`: 旧 Web GUI
- `resource/example_gui/`: Python / PySide6 ベースの参考 GUI

GUI / firmware / integration 関連の文書は、`gui_prototype/` と top-level firmware の
実装、local smoke、実機確認、beta packaging の結果を反映して更新します。古い文書には
実装前の表現が残っている場合があるため、現在地を確認するときは `implementation_backlog_v1.md`、
`validation_checklist_v1.md`、および実コードを優先して照合します。

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
- `flow_verification_plan_v1.md`
  - ATS/ERS / ISO を踏まえた guided flow verification の導線、状態遷移、保存モデルの設計
- `system_usability_review_v1.md`
  - 現時点の GUI / firmware / system を usability と提供価値の観点で再確認した優先順位レビュー
- `active_development_bundles_v1.md`
  - 2026-05-02 時点の課題群を bundle / branch 単位に分けた実装・検証計画
- `sampling_architecture_v1.md`
  - 100 Hz sampling、device-side timing、BLE batch 化へ進む前の task ownership / ring buffer / payload budget 設計
- `sampling_ble_flow_integration_plan_v1.md`
  - `fw-acquisition-scheduler`、Serial/BLE parity、BLE batch、flow baseline を段階統合するための実行計画
- `implementation_backlog_v1.md`
  - GUI / firmware / integration を含む実装バックログとマイルストーン
- `firmware_implementation_plan_v1.md`
  - 新 firmware のモジュール分割案、ランタイムモデル、実装順
- `firmware_worktree_plan_v1.md`
  - この worktree で firmware 機能追加を進めるための branch 運用、baseline check、次候補
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
11. `flow_verification_plan_v1.md` で guided verification の UX と state model を確認する
12. `system_usability_review_v1.md` で current system の UX / usability 優先順位を確認する
13. `active_development_bundles_v1.md` で現在の bundle / branch 計画を確認する
14. `sampling_architecture_v1.md` で sampling / BLE batch の次段設計を確認する
15. `sampling_ble_flow_integration_plan_v1.md` で現在の統合順、parity方針、BLE batch / flow baseline の進め方を確認する
16. `firmware_implementation_plan_v1.md` で firmware の骨格を確認する
17. `implementation_backlog_v1.md` で着手順と依存関係を確認する
18. `firmware_worktree_plan_v1.md` でこの worktree での branch 運用と次候補を確認する
19. `validation_checklist_v1.md` で現段階の検証対象を確認する
20. `windows_beta_smoke_checklist_v1.md` で Windows packaging / smoke の流れを確認する

## 運用メモ

- 要求、設計、実装、検証結果は同じ粒度で更新し、文書だけが古く残らないようにする
- 旧資産の実装詳細は参考にするが、そのまま踏襲する前提にはしない
- 文書内の `TODO` / `TBD` / `Open Questions` は、実装・実機検証・operator feedback に応じて順次確定する
- 古い `現状` セクションは、最新の backlog、validation checklist、実コードと照合して読む
- GUI 関連文書は、layout、controller layer、`QSettings` persistence、packaging、operator feedback の進捗を反映して更新する
- shared regression baseline は `test/fixtures/protocol_golden_v1.json` に置き、protocol / CSV 回帰は `tools/protocol_fixture_smoke.py` で確認する
