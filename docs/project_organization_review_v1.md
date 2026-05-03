# Project Organization Review v1

更新日: 2026-05-03

## 1. 目的

この文書は、`zss_demokit` の directory、README、docs、PoC / reference code、
validation tools を今後の開発に耐える形へ整理するための review note である。

今回の整理では、削除や大規模 rename を急がず、まず以下を優先する。

- 現行実装と参照資産の境界を明確にする
- docs の正本 / active plan / reference / archive candidate を明示する
- README 系を現在の実装状態へ合わせる
- 今後の code split や release preparation の足場を作る

## 2. 現状分類

| Area | 現状 | 判断 |
| :--- | :--- | :--- |
| root firmware | `src/`, `include/`, `platformio.ini` が現行 firmware | 維持 |
| desktop GUI | `gui_prototype/` が現行 desktop GUI | path は維持し、README で historical name と明記 |
| tools | smoke / probe / analysis / helper が混在 | まず `tools/README.md` で分類 |
| docs | canonical spec、active plan、validation log、historical note が同階層 | まず `docs/README.md` で status label を付与 |
| resource | old firmware / old GUI / example GUI が参照用に存在 | 削除せず `resource/README.md` で reference-only と明記 |
| generated artifacts | `.pio/`, `.venv*`, `build/`, `dist/`, `__pycache__` | `.gitignore` 済み。local cleanup 対象 |

## 3. 今回の決定

1. `gui_prototype/` は今すぐ rename しない。
   - PyInstaller spec、tools、docs、import path への影響が大きい。
   - README で active desktop GUI であることを明記する。

2. docs の物理移動は今すぐ行わない。
   - リンク切れと履歴追跡の負荷が大きい。
   - まず status label と reading path を整理する。

3. reference assets は削除しない。
   - 旧 firmware / GUI / example GUI は比較と設計判断にまだ価値がある。
   - `resource/README.md` で active implementation ではないことを明記する。

4. generated artifacts は Git では追跡しない。
   - `.gitignore` は現状妥当。
   - 必要なら別途 local cleanup として `build/`, `dist/`, `.pio/`, `__pycache__` を削除する。

5. 次の code cleanup は file split を優先する。
   - `main_window.py`, `dialogs.py`, `mock_backend.py` は肥大化している。
   - rename より先に responsibility split を行う。

## 4. 推奨ステップ

### Step A: Documentation Entry Points

Status: done in this cleanup slice.

- root `README.md` を current implementation summary へ更新
- `docs/README.md` を status label 付き index へ更新
- `gui_prototype/README.md` を active desktop GUI として更新
- `gui_prototype/packaging_README.md` を beta2 packaging state へ更新

### Step B: Reference And Tooling Entry Points

Status: done in this cleanup slice.

- `tools/README.md` を追加し、smoke / probe / analysis / packaging helper を分類
- `resource/README.md` を追加し、reference-only assets を明記

### Step C: Safe GUI Code Split

Status: done in this cleanup slice.

- `dialogs.py` から Flow Verification / Flow Characterization history dialogs を
  `flow_history_dialogs.py` へ分離した
- `main_window.py` と `tools/gui_log_history_smoke.py` の import path を更新した
- `main_window.py` から Warning / Event Log UI と copy / export 操作を
  `event_log_panel.py` へ分離した
- Settings / details / guided workflow dialogs は今回は動かさず、risk を小さく保った

### Step D: Optional Physical Reorganization

Status: future.

候補:

- `gui_prototype/` -> `desktop_app/`
- `docs/archive/` を作成し、archive candidate を移動
- `tools/` を `tools/smoke/`, `tools/probes/`, `tools/analysis/` に分ける

ただし、これらは link / command path / packaging spec に影響するため、配布準備前の
専用 branch で行う。

## 5. 削除候補

現時点で Git tracked file の削除は推奨しない。

local generated artifact として削除してよいもの:

- `.pio/`
- `.venv_pio/`
- `.venv_gui_prototype/`
- `build/`
- `dist/`
- `__pycache__/`

これらは再生成可能だが、開発中の利便性を考えると自動削除はしない。

## 6. 次の立ち止まりポイント

Step A / B が終わった時点では、code behavior は変えないため risk は低い。
今回の cleanup slice 後は、少なくとも以下を通す。

```sh
.venv_gui_prototype/bin/python -m compileall gui_prototype/src tools
.venv_gui_prototype/bin/python tools/gui_log_history_smoke.py
.venv_gui_prototype/bin/python tools/gui_engineering_tools_smoke.py
.venv_gui_prototype/bin/python tools/gui_layout_smoke.py
```
