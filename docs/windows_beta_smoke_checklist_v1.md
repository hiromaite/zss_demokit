# Windows Release Smoke Checklist v1

## Goal

- verify that the desktop GUI can be packaged on Windows 11 Pro
- verify that the packaged app launches and performs the minimum release workflows for both `Wired` and `BLE`

## Current Packaging Target

- package style: `onedir`
- package directory name: `zss_demokit_gui_win64_1_0_0`
- app version: `1.0.0`
- executable name: `zss_demokit_gui.exe`

## Preconditions

- Windows 11 Pro machine
- Python `3.12.x`
- repository checked out
- Python virtual environment available for packaging; the name is local and
  does not need to be `.venv_gui_prototype`
- target hardware available:
  - one wired device
  - one BLE device advertising as `GasSensor-Proto`

Legacy `M5STAMP-MONITOR*` names are still accepted during the device-name
transition, but new smoke notes should prefer `GasSensor-Proto`.

## Build Steps

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

Expected result:

- package directory exists at `dist\zss_demokit_gui_win64_1_0_0\`
- executable exists at `dist\zss_demokit_gui_win64_1_0_0\zss_demokit_gui.exe`

## Launch Smoke

1. Launch `dist\zss_demokit_gui_win64_1_0_0\zss_demokit_gui.exe`
2. Confirm that the launcher window appears
3. Confirm that the app version displayed is `1.0.0`
4. Confirm that the generated app icon is shown in the window / taskbar if Windows picks it up

## Wired Smoke

1. Select `Wired` mode
2. Confirm that the intended serial device is auto-preselected if only one likely device is attached
3. Connect to the wired device
4. Confirm that plots update continuously
5. Start recording and let it run for at least `15 s`
6. Toggle `Pump ON` then `Pump OFF`
7. Stop recording
8. Confirm:
   - no error log is emitted
   - telemetry is visible
   - a finalized CSV file is produced
   - warning log remains reasonable

## BLE Smoke

1. Switch to `BLE` mode
2. Scan and confirm `GasSensor-Proto` is discovered
3. Connect to the BLE device
4. Confirm:
   - capabilities load
   - status events appear
   - telemetry updates the plots
5. Start recording and let it run for at least `30 s`
6. Toggle `Pump ON` then `Pump OFF`
7. Request status at least once
8. Stop recording
9. Disconnect and reconnect once in the same app session
10. Confirm:
   - reconnect succeeds within `10 s`
   - telemetry resumes
   - no unexpected error log appears
   - finalized CSV is produced

## O2 Display And Filter Smoke

1. Open Settings and confirm the O2 calibration / zero-reference fields are visible
2. Confirm the default 0% reference voltage is `2.550 V` unless intentionally customized
3. Confirm O2 filter controls are visible and presets can be selected
4. Select a quieter O2 filter preset and apply settings
5. Confirm the O2 metric and O2 plot continue to update
6. If the current signal is above the configured zero reference, confirm the O2
   metric shows the expected clamp diagnostic instead of silently hiding the condition

## Startup Behavior Smoke

1. Open Settings > General
2. Set Startup behavior to `BLE startup mode`
3. Close the app and relaunch it
4. Confirm the main window opens in BLE mode without showing the launcher
5. If the target device is powered, confirm scan / auto-connect starts without manual mode selection
6. Return Startup behavior to `Selection mode` unless the next tester wants BLE startup mode

## Pass Criteria

- package build succeeds
- packaged app launches without immediate crash
- `Wired` and `BLE` both complete their minimum smoke workflows
- recording finalizes in both modes
- `python tools\release_readiness_check.py` reports `release_readiness_check_ok`
- Startup behavior can switch between launcher and BLE startup mode
- O2 filter / 2.55 V zero-reference controls are visible and do not block telemetry display
- no blocking packaging issue is discovered

## Last Confirmed Result

- `0.1.0-beta.2` は Windows 11 Pro 上で user 実施により packaging 成功
- `0.1.0-beta.2` packaged app の起動成功
- `0.1.0-beta.2` では `Wired` / `BLE` の両モードで blocking issue なし
- `0.1.0-beta.3` は Windows 11 Pro 上で user 実施により packaging / smoke 成功
- `0.1.0-beta.4` は Windows 11 Pro 上で user 実施により packaging / smoke 成功
- `1.0.0` release candidate は Windows 11 Pro 上で user 実施により packaging / smoke 成功

## Follow-up Notes

- if the icon looks soft or mis-scaled in Windows, replace `gui_prototype/assets/app_icon.ico`
- if company metadata should be organization-only for release, change `APP_COMPANY_NAME` in `gui_prototype/src/app_metadata.py`
- if `onedir` distribution is judged cumbersome after beta, reconsider `onefile` only after current smoke passes
- before manual Windows visual QA, run `python tools/gui_layout_smoke.py` on the packaging source checkout to catch horizontal-scroll, metric-row, compact-toolbar, and plot-growth regressions
- during manual Windows visual QA, still sanity-check that plot heights feel reasonable and that the vertical splitter between the two plots can be dragged smoothly on the actual display scale
