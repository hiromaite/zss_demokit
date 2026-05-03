# Desktop GUI

This directory contains the current PySide6 desktop GUI implementation for the
ZSS Demo Kit.

The directory name `gui_prototype/` is historical. It is kept for path stability
because tools, docs, and the PyInstaller spec already refer to it. Treat this
directory as the active desktop application unless a later cleanup branch
renames it.

## Capabilities

- BLE and wired serial connection modes
- preferred device filtering for `GasSensor-Proto` with legacy
  `M5STAMP-MONITOR*` compatibility
- capabilities, status, telemetry, command, and event handling
- real-time metric cards and two plot panels
- plot pause, series visibility, manual pan / zoom, and retained history
- pump and heater controls with firmware-side safety interlock support
- CSV recording with partial-file finalization and post-run review
- warning / event log filtering, search, copy, and CSV export
- O2 ambient calibration
- flow verification and flow characterization workflows
- Windows-oriented PyInstaller packaging

## Run From Source

```bash
python3.12 -m venv .venv_gui_prototype
source .venv_gui_prototype/bin/activate
pip install -r gui_prototype/requirements.txt
python gui_prototype/main.py
```

Settings are stored with `QSettings` under the `zss-demokit` organization and
`gui-prototype` application key. The settings key is also historical.

## Packaging

```bash
source .venv_gui_prototype/bin/activate
pip install "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec
```

See `gui_prototype/packaging_README.md` for the current beta package name,
metadata, release-readiness preflight, known gaps, and Windows smoke path.

## Useful Smoke Tools

No-device / offscreen:

```bash
python3.12 tools/protocol_fixture_smoke.py
python3.12 tools/gui_layout_smoke.py
python3.12 tools/gui_plot_controls_smoke.py
python3.12 tools/gui_recording_review_smoke.py
python3.12 tools/gui_log_history_smoke.py
```

Wired:

```bash
python3.12 tools/wired_serial_smoke.py --port <PORT> --baudrate 115200
python3.12 tools/gui_wired_session_probe.py --port <PORT> --duration-s 18 --toggle-interval-s 3
```

BLE:

```bash
python3.12 tools/ble_backend_smoke.py
python3.12 tools/gui_ble_session_probe.py --use-fake-live --offscreen --duration-s 12 --recording-duration-s 4 --reconnect-at-s 6 --min-observed-duration-s 6 --connect-timeout-s 6
python3.12 tools/gui_ble_session_probe.py --device-prefix GasSensor-Proto --duration-s 180 --recording-duration-s 45 --reconnect-at-s 60
```

## Code Organization Notes

- `main_window.py` still owns too much UI assembly and orchestration.
- `dialogs.py` still contains several large dialog classes.
- `event_log_panel.py` owns the Warning / Event Log UI and export actions.
- `flow_history_dialogs.py` owns flow history comparison dialogs.
- `ui_helpers.py` owns generic panel, metric, collapsible, and scroll helper widgets.
- `plot_interactions.py` owns manual pan / zoom interaction helper items.
- `dialog_helpers.py` owns shared dialog header, button styling, and optional value formatting.
- `mock_backend.py` contains both fake behavior and live transport integration.
- Future maintenance work should split these files by responsibility before
  adding much more UI surface area.
