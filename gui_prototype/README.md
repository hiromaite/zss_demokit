# GUI Prototype

This directory contains a runnable desktop UI prototype for the new ZSS GUI.

Purpose:

- verify layout and information density on macOS before implementation starts
- confirm mode switching, settings flow, plot composition, and panel hierarchy
- keep reference assets in `resource/example_gui/` untouched

Notes:

- this is now the practical implementation base for the desktop GUI, not just a visual mock
- wired mode can talk to the firmware over real serial
- BLE mode now has a real transport path via `bleak`, with manual scan from the UI
- BLE mode schedules a status refresh after live `Pump ON/OFF` requests to improve operator feedback
- if `bleak` is unavailable, BLE falls back to the prototype mock path
- if BLE extension reads are unavailable, the UI degrades to telemetry-first operation instead of aborting the session
- telemetry continuity is monitored in the GUI so delayed start / stalled stream conditions appear in the warning log
- the wired mode uses the approved default `115200 baud / 8N1` in the UI
- `flow_rate_lpm` uses the approved placeholder policy `dummy_linear_v1`
- settings are persisted locally with `QSettings`
- recording directory, plot defaults, and launcher / main window sizes are restored on next startup
- partial recovery detection uses the configured recording directory

## Run

```bash
python3.12 -m venv .venv_gui_prototype
source .venv_gui_prototype/bin/activate
pip install -r gui_prototype/requirements.txt
python gui_prototype/main.py
```

## Current Scope

- `BLE` mode: real scan / connect path is implemented, with mock fallback only when `bleak` is unavailable
- `Wired` mode: real serial transport against the current firmware scaffold
- controller layer split is in place for connection, plotting, recording, and warning log concerns
- recording writes the shared CSV schema to the configured directory, defaulting to `~/Documents/ZSS Demo Kit/`
- validated path today: connect, capabilities, status, telemetry ingest, `Pump ON/OFF`, recording finalize

## Smoke Tools

- wired end-to-end smoke: `python3.12 tools/wired_serial_smoke.py --port /dev/cu.usbmodem5101 --baudrate 115200`
- BLE live smoke: `python3.12 tools/ble_smoke.py --name M5STAMP-MONITOR --telemetry-count 8 --telemetry-timeout 8 --reconnect-cycles 2`
- BLE backend reconnect smoke: `python3.12 tools/ble_backend_smoke.py`
