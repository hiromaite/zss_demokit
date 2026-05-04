# Distribution Plan v1

更新日: 2026-05-04

## 1. 目的

この文書は、ZSS Demo Kit desktop GUI を release package として配布するための判断、
前提、作業順、保留事項をまとめる。現時点では PoC / hardware-development 向けの
first stable release を対象とする。

## 2. 先に片付けたこと

`v0.1.0-beta.4` tag は Windows packaged smoke 済みの beta4 baseline を指す。
現在の main は beta4 後の startup behavior と O2 `2.55 V` zero-reference polish を
含み、Windows release-candidate smoke も通過済みであるため、次の配布候補は
`1.0.0` として扱う。

| Item | Decision |
| :--- | :--- |
| App version | `1.0.0` |
| Distribution directory | `dist/zss_demokit_gui_win64_1_0_0/` |
| Executable | `zss_demokit_gui.exe` |
| Release note | `docs/release_notes_v1_0_0.md` |
| Existing beta tags | 維持。retag しない |

## 3. Release Distribution Policy

| Topic | 1.0.0 decision | Follow-up |
| :--- | :--- | :--- |
| Package style | PyInstaller `onedir` | Installer / `onefile` は後で再検討 |
| Installer | なし | Inno / NSIS / MSIX 等の候補を別途比較 |
| Code signing | なし | 外部配布が増える段階で証明書取得と署名 pipeline を検討 |
| Updater | なし | update channel / artifact hosting 方針を別途決定 |
| Artifact sharing | zipped `dist/zss_demokit_gui_win64_1_0_0/` を想定 | GitHub Release / internal share などを選定 |
| Admin rights | 不要を維持 | formal installer 採用時も原則不要にする |
| Target OS | Windows 11 Pro | 必要なら Windows 10 / 11 matrix を拡張 |

1.0.0 では「すぐ配布してテスト継続できること」と「トラブル時に中身を追いやすいこと」を
優先する。したがって `onedir` を維持し、installer / signing / updater は次フェーズの
判断点として残す。

## 4. Distribution Gate

配布候補を作る前に以下を満たす。

1. Release-readiness changes を review し、配布対象 branch へ統合する。
2. tag は feature branch ではなく、配布対象 branch の Windows smoke 後に打つ。
3. macOS / local no-device gate を通す。
4. Windows packaging gate を通す。
5. Windows packaged app smoke を通す。
6. smoke 結果を `docs/validation_checklist_v1.md` へ追記する。

## 5. Recommended Task Order

### Step 1: Branch And Review Preparation

- current release-readiness changes の差分を review 可能な単位にする。
- PR を作る場合は、working branch から配布対象 branch へ向ける。
- 配布対象にする branch を決める。通常は `main` へ merge してから tag を打つ。

### Step 2: Local Preflight

```sh
source <gui-venv>/bin/activate
python tools/release_readiness_check.py
python -m compileall gui_prototype/src tools
python tools/protocol_fixture_smoke.py
python tools/gui_layout_smoke.py
python tools/gui_log_history_smoke.py
python tools/gui_engineering_tools_smoke.py
python tools/gui_startup_mode_smoke.py
python tools/o2_filter_smoke.py
python tools/gui_o2_filter_smoke.py
```

### Step 3: Windows Build

```powershell
cd <repo-root>
py -3.12 -m venv <gui-venv>
<gui-venv>\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r gui_prototype\requirements.txt
pip install "pyinstaller>=6,<7"
python tools\release_readiness_check.py
pyinstaller --noconfirm --clean gui_prototype\zss_demokit_gui.spec
```

Expected output:

- `dist\zss_demokit_gui_win64_1_0_0\`
- `dist\zss_demokit_gui_win64_1_0_0\zss_demokit_gui.exe`

### Step 4: Windows Smoke

`docs/windows_beta_smoke_checklist_v1.md` を実行する。最低限:

- packaged app launch
- Wired connect / telemetry / pump toggle / recording finalize
- BLE connect / telemetry / pump toggle / status request / reconnect / recording finalize
- Startup behavior setting: selector mode and BLE startup mode
- O2 value display, 2.55 V zero reference, filter preset, and clamp diagnostic sanity check
- layout sanity check on the actual Windows display scale

### Step 5: Tag And Artifact

Windows smoke が通った後に、配布対象 branch で tag を作る。

```sh
git tag -a v1.0.0 -m "ZSS Demo Kit 1.0.0"
git push origin v1.0.0
```

Artifact は `dist/zss_demokit_gui_win64_1_0_0/` を zip 化する。zip 名の候補:

```text
zss_demokit_gui_win64_1_0_0.zip
```

## 6. Not Blocking 1.0.0

- final icon art direction
- installer recipe
- code signing
- updater
- formal public changelog format
- final flow calibration / selector threshold
- pump-noise characterization

これらは重要だが、PoC / hardware-development 向け 1.0.0 の配布を止める条件にはしない。
