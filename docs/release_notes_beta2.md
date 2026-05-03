# Release Notes: ZSS Demo Kit `0.1.0-beta.2`

Status: beta distribution candidate

Package target: `dist/zss_demokit_gui_win64_beta2/`

Executable: `zss_demokit_gui.exe`

## Audience

This beta package is intended for PoC and hardware-development use with the
ZSS Demo Kit sensor device. It is not a formal production release and does not
yet include an installer, updater, or code-signing workflow.

## Highlights

- Windows-oriented PyInstaller `onedir` package for the PySide6 desktop GUI.
- Wired serial and BLE connection modes with preferred `GasSensor-Proto`
  discovery and legacy `M5STAMP-MONITOR*` compatibility.
- 10 ms telemetry recording support, including BLE batch telemetry when the
  connected firmware advertises support.
- Real-time zirconia voltage, heater resistance, flow rate, O2 concentration,
  raw differential pressure, and engineering diagnostic visibility.
- CSV recording with partial-file finalization, post-run summary, open-folder,
  and copy-path actions.
- Warning / Event Log filtering, search, visible-copy, and CSV export.
- Flow Verification and Flow Characterization workflows with history comparison
  and summary CSV export.
- Plot pause, series visibility toggles, manual pan / zoom, retained plot
  history, and cross-resolution layout smoke coverage.
- Firmware-side pump / heater safety interlock regression smoke coverage.

## Expected Hardware And Environment

- Windows 11 Pro for packaged app smoke testing.
- M5Stack StampS3 based ZSS Demo Kit firmware target.
- USB serial device for `Wired` mode.
- BLE device advertising as `GasSensor-Proto`; host filtering still accepts
  legacy `M5STAMP-MONITOR*` names during transition.
- Current flow calibration is still PoC-grade. Final flow law, selector
  thresholds, and verification thresholds remain hardware-completion dependent.

## Validation Evidence

The following validation paths are recorded in
`docs/validation_checklist_v1.md`.

- PyInstaller packaging smoke: `GUI-VAL-020`
- Windows packaged GUI smoke: `GUI-VAL-021`
- Windows packaged end-to-end smoke: `INT-VAL-012`
- Cross-resolution layout smoke: `GUI-VAL-028`
- Plot controls smoke: `GUI-VAL-029`
- Recording quick review smoke: `GUI-VAL-036`
- Warning / Event Log export smoke: `GUI-VAL-037`
- Flow history comparison smoke: `GUI-VAL-038`
- Project organization cleanup smoke: `GUI-VAL-039`
- Release readiness metadata / document smoke: `GUI-VAL-040`

Before packaging from a fresh checkout, run:

```sh
python tools/release_readiness_check.py
```

## Distribution Checklist

1. Confirm the checkout is on the intended branch or release tag.
2. Run `python tools/release_readiness_check.py`.
3. Build with `pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec`.
4. Confirm `dist/zss_demokit_gui_win64_beta2/zss_demokit_gui.exe` exists.
5. Execute `docs/windows_beta_smoke_checklist_v1.md` on Windows 11 Pro.
6. Record the smoke result in `docs/validation_checklist_v1.md` before tagging
   or sharing a package as the latest beta.

## Known Gaps

- No installer recipe yet.
- No code-signing path yet.
- No updater path yet.
- Generated icon is acceptable for beta, but final art direction may change.
- `onedir` remains the beta default. `onefile` can be reconsidered later if the
  current smoke path remains stable and startup/debug tradeoffs are acceptable.
- Flow calibration and selector tuning remain provisional until the physical
  flow hardware and reference measurement setup are complete.
- Pump-noise characterization remains a hardware-assisted follow-up item.
