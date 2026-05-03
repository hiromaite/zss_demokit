# Tools

This directory contains developer-facing smoke tests, device probes, analyzers,
and small helper scripts.

Run tools from the repository root. Prefer the GUI virtual environment for
Python tools:

```sh
source .venv_gui_prototype/bin/activate
python tools/<tool>.py
```

## No-Device / Offscreen GUI Checks

| Tool | Purpose |
| :--- | :--- |
| `protocol_fixture_smoke.py` | Shared protocol / CSV fixture regression |
| `gui_layout_smoke.py` | Cross-resolution offscreen layout regression |
| `gui_plot_controls_smoke.py` | Plot pause and series visibility regression |
| `gui_recording_review_smoke.py` | Recording finalization and quick review regression |
| `gui_log_history_smoke.py` | Event log filter/export and flow history comparison regression |
| `gui_engineering_tools_smoke.py` | Settings Engineering / Tools navigation regression |
| `gui_observability_smoke.py` | Diagnostic availability label regression |
| `ble_backend_smoke.py` | Fake BLE backend command / reconnect regression |

## Live GUI Session Probes

| Tool | Purpose |
| :--- | :--- |
| `gui_wired_session_probe.py` | Offscreen GUI wired connect / telemetry / recording probe |
| `gui_ble_session_probe.py` | Offscreen GUI BLE connect / batch / reconnect / recording probe |

## Transport And Firmware Probes

| Tool | Purpose |
| :--- | :--- |
| `wired_serial_smoke.py` | Wired protocol handshake / command / telemetry smoke |
| `wired_flow_probe.py` | Wired flow telemetry probe |
| `wired_timing_probe.py` | Wired timing and device sample interval probe |
| `wired_soak_probe.py` | Longer wired continuity probe |
| `ble_smoke.py` | Live BLE scan / connect / telemetry probe |
| `sdp_serial_probe.py` | Raw SDP differential pressure serial probe |
| `command_processor_smoke.py` | Host-side firmware command processor regression |
| `command_processor_smoke.cpp` | C++ command processor smoke source |
| `firmware_fixture_verify.cpp` | Firmware-side protocol fixture verifier |

## Analysis And Helpers

| Tool | Purpose |
| :--- | :--- |
| `flow_characterization_analyze.py` | Analyze saved flow characterization sessions |
| `sampling_batch_budget.py` | Estimate BLE batch payload budget |
| `generate_app_icon.py` | Generate beta GUI icon assets |

## Notes

- Some probes require a connected device and a port or BLE name.
- `GasSensor-Proto` is the preferred BLE name in new commands.
- Legacy `M5STAMP-MONITOR*` remains accepted by host-side filters during the
  transition.
- Keep tool behavior documented in `docs/validation_checklist_v1.md` when a
  tool becomes part of the expected regression path.
