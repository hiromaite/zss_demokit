# Project Status v1

更新日: 2026-05-04

## 1. Snapshot

`zss_demokit` is active beta software. Firmware and desktop GUI are both active
implementation surfaces. The current Windows distribution candidate is:

| Item | Value |
| :--- | :--- |
| App version | `0.1.0-beta.4` |
| Distribution directory | `dist/zss_demokit_gui_win64_beta4/` |
| Packaging style | PyInstaller `onedir` |
| Target OS for packaged smoke | Windows 11 Pro |
| Preferred BLE name | `GasSensor-Proto` |
| Legacy BLE compatibility | `M5STAMP-MONITOR*` remains accepted by host filters |

The existing `v0.1.0-beta.3` tag points to the Windows-validated beta3
baseline and must not be moved. The next tag should be `v0.1.0-beta.4` after
Windows packaged smoke passes.

## 2. Firmware State

- Firmware builds as a top-level PlatformIO project for `m5stack-stamps3`.
- Wired serial supports capabilities, status, telemetry, command ack, events,
  and 10 ms sample recording.
- Firmware-side acquisition scheduling has been tightened so device-side sample
  cadence can stay near nominal `10 ms` under the validated configuration.
- Pump / heater safety interlock behavior is covered by host-side command
  processor smoke.
- Flow calibration, selector thresholds, and pump-noise characterization remain
  hardware-dependent follow-up items.

## 3. Desktop GUI State

- The PySide6 GUI can run from source and package with PyInstaller.
- BLE and wired serial connection modes are both supported.
- BLE batch telemetry can reconstruct 10 ms plot / CSV rows when supported by
  the connected firmware.
- The GUI records CSV files, finalizes partial recordings, and shows post-run
  summaries.
- Real-time metrics, two plot panels, manual pan / zoom, plot pause, series
  visibility, retained history, and cross-resolution layout smoke are in place.
- Warning / Event Log filtering, search, visible-copy, and CSV export are in
  place.
- Flow Verification and Flow Characterization workflows include history
  comparison and summary CSV export.
- Settings now separates routine device settings from Engineering / Tools
  actions.
- Beta4 adds configurable O2 output filtering, O2 zero-reference handling, O2
  clamp diagnostics, and GUI telemetry data-flow documentation.

## 4. Validation State

Primary validation evidence is in `docs/validation_checklist_v1.md`.

Common local gates:

- `python tools/release_readiness_check.py`
- `python -m compileall gui_prototype/src tools`
- `python tools/protocol_fixture_smoke.py`
- `python tools/gui_layout_smoke.py`
- `python tools/gui_log_history_smoke.py`
- `python tools/gui_engineering_tools_smoke.py`
- `python tools/o2_filter_smoke.py`
- `python tools/gui_o2_filter_smoke.py`

Windows beta3 packaging and wired / BLE packaged smoke were confirmed by user
testing. Beta4 still needs Windows packaged smoke before tagging.

## 5. Current Non-Blocking Gaps

- No installer recipe yet.
- No code-signing path yet.
- No updater path yet.
- Final icon art direction may change.
- Flow calibration / selector tuning remains provisional until the physical
  flow hardware and reference measurement setup are complete.
- Pump-noise characterization requires hardware-assisted testing.

These gaps do not block PoC / hardware-development beta4 distribution.
