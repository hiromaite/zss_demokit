# Release Notes: ZSS Demo Kit `0.1.0-beta.4`

Status: final beta candidate before the first major release decision

Package target: `dist/zss_demokit_gui_win64_beta4/`

Executable: `zss_demokit_gui.exe`

## Audience

This beta package is intended for PoC and hardware-development use with the
ZSS Demo Kit sensor device. It is not a formal production release and does not
yet include an installer, updater, or code-signing workflow.

## Highlights

- Builds on the Windows-validated `0.1.0-beta.3` package baseline.
- Adds configurable O2 output filtering for quieter O2 concentration display
  and plot behavior.
- Adds O2 zero-reference handling so the calibration path defaults to the
  observed 2.55 V zero anchor while preserving legacy migration behavior.
- Adds an operator setting for startup behavior: keep the mode-selection
  launcher, or open BLE mode directly and continue into scan / auto-connect.
- Adds O2 clamp diagnostics so invalid or above-zero-reference input conditions
  are visible to the operator instead of silently flattening the value.
- Adds GUI smoke coverage for O2 filter controls, settings migration, clamp
  diagnostics, and filtered plot output.
- Documents the GUI telemetry data flow from device telemetry through
  controller buffers, derived O2 values, plots, metrics, and CSV recording.
- Retains beta3 core capabilities: wired / BLE operation, 10 ms CSV support
  including BLE batch telemetry, post-run recording review, event-log export,
  flow verification / characterization history, and cross-resolution layout
  smoke coverage.

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
- O2 output filter / zero-reference smoke: `GUI-VAL-041`
- Startup mode / O2 zero-reference polish smoke: `GUI-VAL-042`

Before packaging from a fresh checkout, run:

```sh
python tools/release_readiness_check.py
```

## Distribution Checklist

1. Confirm the checkout is on the intended branch or release tag. See
   `docs/distribution_plan_v1.md` for the full gate and tag policy.
2. Run `python tools/release_readiness_check.py`.
3. Run the beta4 polish local gate:
   `python tools/gui_startup_mode_smoke.py`, `python tools/o2_filter_smoke.py`,
   and `python tools/gui_o2_filter_smoke.py`.
4. Build with `pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec`.
5. Confirm `dist/zss_demokit_gui_win64_beta4/zss_demokit_gui.exe` exists.
6. Execute `docs/windows_beta_smoke_checklist_v1.md` on Windows 11 Pro.
7. Record the smoke result in `docs/validation_checklist_v1.md` before tagging
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
- Pump-noise characterization requires hardware-assisted testing.

## First Major Release Decision

If beta4 passes Windows packaged testing and no critical O2 calibration,
recording, or transport regressions are found, the next planning step should be
one of:

- `1.0.0-rc.1` when a release-candidate soak is desired.
- `1.0.0` when beta4 is accepted as sufficient for the first major release.
