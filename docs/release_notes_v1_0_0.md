# Release Notes: ZSS Demo Kit `1.0.0`

Status: first stable PoC / hardware-development release

Package target: `dist/zss_demokit_gui_win64_1_0_0/`

Executable: `zss_demokit_gui.exe`

## Audience

This package is intended for PoC and hardware-development use with the ZSS Demo
Kit sensor device. It is the first stable release of the current firmware / GUI
system, but it does not yet include an installer, updater, code-signing
workflow, or final flow calibration.

## Highlights

- Builds on the Windows-validated `0.1.0-beta.4` baseline.
- Supports both `Wired` and `BLE` workflows from the packaged Windows app.
- Records 10 ms CSV data in wired mode and BLE batch-capable mode.
- Adds BLE startup behavior so the app can skip the launcher, open BLE mode,
  and continue through scan / auto-connect when the target device is powered.
- Uses `2.55 V` as the default 0% O2 reference voltage while preserving explicit
  user-customized O2 zero-reference settings.
- Includes configurable O2 output filtering, O2 clamp diagnostics, and O2
  calibration controls in Settings.
- Includes flow verification / characterization history, event-log filtering
  and export, post-run recording review, device elapsed time in CSV, plot pause,
  series visibility, and cross-resolution layout hardening.
- Keeps beta4 compatibility behavior: host filtering accepts both preferred
  `GasSensor-Proto` and legacy `M5STAMP-MONITOR*` BLE names during transition.

## Validation Evidence

Primary validation evidence is recorded in `docs/validation_checklist_v1.md`.

- PyInstaller packaging smoke: `GUI-VAL-020`
- Windows packaged GUI smoke: `GUI-VAL-021`
- Windows packaged end-to-end smoke: `INT-VAL-012`
- Cross-resolution layout smoke: `GUI-VAL-028`
- Plot controls smoke: `GUI-VAL-029`
- Recording quick review smoke: `GUI-VAL-036`
- Warning / Event Log export smoke: `GUI-VAL-037`
- Flow history comparison smoke: `GUI-VAL-038`
- Release readiness metadata / document smoke: `GUI-VAL-040`
- O2 output filter / zero-reference smoke: `GUI-VAL-041`
- Startup mode / O2 zero-reference polish smoke: `GUI-VAL-042`
- Windows release-candidate packaged smoke: `GUI-VAL-043`

Before packaging from a fresh checkout, run:

```sh
python tools/release_readiness_check.py
```

## Distribution Checklist

1. Confirm the checkout is on `main` at the intended release commit or on
   `v1.0.0` after tagging.
2. Run `python tools/release_readiness_check.py`.
3. Run the local release gate:
   `python -m compileall gui_prototype/src tools`,
   `python tools/protocol_fixture_smoke.py`,
   `python tools/gui_layout_smoke.py`,
   `python tools/gui_log_history_smoke.py`,
   `python tools/gui_engineering_tools_smoke.py`,
   `python tools/gui_startup_mode_smoke.py`,
   `python tools/o2_filter_smoke.py`,
   `python tools/gui_o2_filter_smoke.py`,
   `python tools/command_processor_smoke.py`,
   and `pio run`.
4. Build with `pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec`.
5. Confirm `dist/zss_demokit_gui_win64_1_0_0/zss_demokit_gui.exe` exists.
6. Execute `docs/windows_beta_smoke_checklist_v1.md` on Windows 11 Pro when
   producing the final shared artifact.

## Known Gaps

- No installer recipe yet.
- No code-signing path yet.
- No updater path yet.
- Generated icon is acceptable for the first stable PoC release, but final art
  direction may change.
- `onedir` remains the release default. `onefile` can be reconsidered later if
  the current smoke path remains stable and startup/debug tradeoffs are
  acceptable.
- Flow calibration and selector tuning remain provisional until the physical
  flow hardware and reference measurement setup are complete.
- Pump-noise characterization requires hardware-assisted testing.

## Release Tag

The source release tag for this package is:

```sh
v1.0.0
```
