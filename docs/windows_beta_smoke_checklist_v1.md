# Windows Beta Smoke Checklist v1

## Goal

- verify that the desktop GUI can be packaged on Windows 11 Pro
- verify that the packaged app launches and performs the minimum beta workflows for both `Wired` and `BLE`

## Current Packaging Target

- package style: `onedir`
- package directory name: `zss_demokit_gui_win64_beta2`
- app version: `0.1.0-beta.2`
- executable name: `zss_demokit_gui.exe`

## Preconditions

- Windows 11 Pro machine
- Python `3.12.x`
- repository checked out
- virtual environment available for packaging
- target hardware available:
  - one wired device
  - one BLE device advertising as `GasSensor-Proto`

Legacy `M5STAMP-MONITOR*` names are still accepted during the device-name
transition, but new smoke notes should prefer `GasSensor-Proto`.

## Build Steps

```powershell
cd <repo-root>
py -3.12 -m venv .venv_gui_prototype
.venv_gui_prototype\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r gui_prototype\requirements.txt
pip install "pyinstaller>=6,<7"
python tools\release_readiness_check.py
pyinstaller --noconfirm --clean gui_prototype\zss_demokit_gui.spec
```

Expected result:

- package directory exists at `dist\zss_demokit_gui_win64_beta2\`
- executable exists at `dist\zss_demokit_gui_win64_beta2\zss_demokit_gui.exe`

## Launch Smoke

1. Launch `dist\zss_demokit_gui_win64_beta2\zss_demokit_gui.exe`
2. Confirm that the launcher window appears
3. Confirm that the app version displayed is `0.1.0-beta.2`
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

## Pass Criteria

- package build succeeds
- packaged app launches without immediate crash
- `Wired` and `BLE` both complete their minimum smoke workflows
- recording finalizes in both modes
- `python tools\release_readiness_check.py` reports `release_readiness_check_ok`
- no blocking packaging issue is discovered

## Current Result

- Windows 11 Pro 上で user 実施により packaging 成功
- packaged app の起動成功
- `Wired` / `BLE` の両モードで blocking issue なし

## Follow-up Notes

- if the icon looks soft or mis-scaled in Windows, replace `gui_prototype/assets/app_icon.ico`
- if company metadata should be organization-only for release, change `APP_COMPANY_NAME` in `gui_prototype/src/app_metadata.py`
- if `onedir` distribution is judged cumbersome after beta, reconsider `onefile` only after current smoke passes
- before manual Windows visual QA, run `python tools/gui_layout_smoke.py` on the packaging source checkout to catch horizontal-scroll, metric-row, compact-toolbar, and plot-growth regressions
- during manual Windows visual QA, still sanity-check that plot heights feel reasonable and that the vertical splitter between the two plots can be dragged smoothly on the actual display scale
