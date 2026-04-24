# Firmware Worktree Plan v1

作成日: 2026-04-24

この文書は、現在の `zss_demokit` worktree で firmware の追加機能を進めるための
短い作業メモである。詳細仕様は既存の設計文書を参照し、ここではこの worktree で
迷わず作業を始めるための現在地と運用だけを固定する。

## 1. 現在地

- この worktree は `main` から機能単位の branch を切って作業する
- 2026-04-24 時点で `main` は `origin/main` と同じ commit を指していた
- top-level PlatformIO project は firmware 本体として実装済みであり、雛形状態ではない
- firmware build は repo-local PlatformIO 環境で確認する
- baseline build は `./.venv_pio/bin/pio run` で成功済み
- global `pio` command はこの shell では利用できないため、repo-local `.venv_pio` を使う

## 2. Branch Policy

作業は細かな機能単位で branch を分ける。

推奨 branch 名:

- `codex/fw-baseline-audit`
- `codex/fw-flow-operator-sweep`
- `codex/fw-<feature-name>`

運用:

- `main` では直接実装しない
- 1 branch は 1 つの確認項目または 1 つの機能追加に絞る
- 実機 upload や operator validation が必要なものは、code change と validation result を分けて記録する
- 既存の別 worktree や main branch の作業を取り込む場合は、先に `git status -sb` と `git worktree list` を確認する

## 3. Baseline Checks

実装 branch を切った直後は、まず以下を確認する。

```sh
git status -sb
git branch --show-current
./.venv_pio/bin/pio run
```

GUI / protocol まで触る場合は、変更範囲に応じて以下も追加する。

```sh
.venv_gui_prototype/bin/python -m compileall gui_prototype/src
.venv_gui_prototype/bin/python tools/protocol_fixture_smoke.py
```

実機 serial path を触る場合は、接続 port を確認してから既存 probe を使う。

```sh
.venv_gui_prototype/bin/python tools/wired_serial_smoke.py --port <PORT> --baudrate 115200
.venv_gui_prototype/bin/python tools/wired_flow_probe.py --port <PORT> --duration-s 6
```

## 4. Next Firmware-Oriented Candidates

### Candidate A: EXT-006 wired flow operator sweep

目的:

- `INT-VAL-015` を完了させる
- low / medium / high flow で `tools/wired_flow_probe.py` が handoff を観測できることを確認する

性質:

- 主に実機 validation
- code change は最小または不要
- 実施結果は `docs/validation_checklist_v1.md` に記録する

最初に切る branch:

- `codex/fw-flow-operator-sweep`

### Candidate B: firmware documentation sync

目的:

- `docs/firmware_implementation_plan_v1.md` の古い現状説明を、現在の実装状態に合わせる
- firmware がすでに modular implementation 済みであることを明示する

性質:

- documentation-only
- 次の実装者の認知負荷を下げる

最初に切る branch:

- `codex/fw-doc-sync`

### Candidate C: next firmware feature selection

目的:

- `legacy_current_feature_matrix.md` の remaining gaps から、firmware に閉じて進められる機能を選ぶ
- protocol / GUI に波及するものは別 bundle として分ける

候補:

- internal voltage telemetry
- zirconia Ip voltage exposure beyond local LED use
- ZSS 2-cell raw value restoration
- flow calibration / selector tuning after hardware completion

性質:

- 要件確認が必要
- protocol 変更が絡む可能性があるため、実装 branch 前に small design note を置く

## 5. Backlog-Driven Default Move

未完了 validation を backlog 順に閉じる場合は、`Candidate A` が自然な既定候補になる。

理由:

- 現在の backlog で明示的に残っている未完了 validation が `INT-VAL-015` である
- 既存 build は成功しており、まず実機 sweep で現状の完成度を確認する価値が高い
- sweep 結果によって、次に code fix が必要か、単に validation close でよいかが決まる

ただし、これはこの worktree の作業順を固定するものではない。追加したい firmware 機能が
別に決まっている場合は、その機能専用 branch を切り、必要なら小さな design note を先に置く。
実機 flow source がすぐ使えない場合は、`Candidate B` の documentation sync を先に行う。
