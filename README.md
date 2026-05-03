# zss_demokit

`zss_demokit` is the firmware and desktop GUI workspace for the ZSS Demo Kit.
The system connects to an M5Stack StampS3 based sensor device over USB serial
or BLE, visualizes zirconia / flow related telemetry, controls the pump and
heater path, and records measurement sessions to CSV for later analysis.

This repository is no longer a static prototype archive. It contains the
current PlatformIO firmware, the current PySide6 desktop application, shared
protocol definitions, validation probes, packaging notes, and reference copies
of older implementations.

## Current Status

As of 2026-05-03:

- Firmware builds as a top-level PlatformIO project for `m5stack-stamps3`.
- Wired serial supports capabilities, status, telemetry, command ack, events,
  and 10 ms sample recording.
- BLE supports the current control path and batch telemetry path used by the
  GUI to reconstruct 10 ms plot / CSV rows when supported by the device.
- The operator-facing BLE name is `GasSensor-Proto`; host filters still accept
  legacy `M5STAMP-MONITOR*` names during transition.
- The desktop GUI can run from source, package with PyInstaller, connect over
  BLE or wired serial, record CSV files, show diagnostics, and run flow
  verification / characterization workflows.
- Windows beta packaging has been smoke-tested through `0.1.0-beta.2`.

## Repository Map

| Path | Role |
| :--- | :--- |
| `src/` | Current firmware implementation |
| `include/` | Current firmware headers and module interfaces |
| `platformio.ini` | PlatformIO target configuration |
| `gui_prototype/` | Current desktop GUI implementation; the directory name is historical |
| `tools/` | Smoke tests, probes, analyzers, and developer helpers |
| `test/fixtures/` | Shared protocol regression fixtures |
| `docs/` | Requirements, architecture, protocol, backlog, validation, and release notes |
| `resource/` | Reference-only legacy firmware / GUI and example GUI assets |
| `build/`, `dist/`, `.pio/`, `.venv*` | Local generated artifacts; ignored by Git |

## Firmware Quick Start

Use the repository-local PlatformIO environment when available.

```sh
./.venv_pio/bin/pio run
./.venv_pio/bin/pio run -t upload --upload-port <PORT>
./.venv_pio/bin/pio device monitor --port <PORT> --baud 115200
```

If `.venv_pio` has not been created yet, create or restore the PlatformIO
environment before building.

## Desktop GUI Quick Start

The current GUI implementation lives in `gui_prototype/`. The name remains for
path stability, but the contents are the active desktop application.

```sh
python3.12 -m venv .venv_gui_prototype
source .venv_gui_prototype/bin/activate
pip install -r gui_prototype/requirements.txt
python gui_prototype/main.py
```

Packaging:

```sh
source .venv_gui_prototype/bin/activate
pip install "pyinstaller>=6,<7"
python tools/release_readiness_check.py
pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec
```

Packaging metadata is centralized in
`gui_prototype/src/app_metadata.py`. The current beta target is
`0.1.0-beta.2` with distribution directory
`dist/zss_demokit_gui_win64_beta2/`.

## Validation

Run the smallest relevant checks before and after a change.

No-device baseline:

```sh
.venv_gui_prototype/bin/python -m compileall gui_prototype/src tools
.venv_gui_prototype/bin/python tools/protocol_fixture_smoke.py
.venv_gui_prototype/bin/python tools/gui_layout_smoke.py
.venv_gui_prototype/bin/python tools/gui_log_history_smoke.py
```

Firmware baseline:

```sh
./.venv_pio/bin/pio run
.venv_gui_prototype/bin/python tools/command_processor_smoke.py
```

Wired device:

```sh
.venv_gui_prototype/bin/python tools/wired_serial_smoke.py --port <PORT> --baudrate 115200
.venv_gui_prototype/bin/python tools/gui_wired_session_probe.py --port <PORT> --duration-s 18 --toggle-interval-s 3
.venv_gui_prototype/bin/python tools/wired_flow_probe.py --port <PORT> --duration-s 6
```

BLE device:

```sh
.venv_gui_prototype/bin/python tools/ble_smoke.py --name GasSensor-Proto --telemetry-count 20 --telemetry-timeout 10 --observe-duration 8
.venv_gui_prototype/bin/python tools/gui_ble_session_probe.py --device-prefix GasSensor-Proto --duration-s 180 --recording-duration-s 45 --reconnect-at-s 60
```

The authoritative validation log is
`docs/validation_checklist_v1.md`.

## Documentation

Start with:

- `docs/README.md` for the documentation index and status labels.
- `docs/system_requirements.md` for scope and system requirements.
- `docs/system_architecture.md` for component boundaries.
- `docs/protocol_catalog_v1.md` for canonical protocol names and fields.
- `docs/implementation_backlog_v1.md` for active backlog and milestone state.
- `docs/validation_checklist_v1.md` for tested behavior.
- `docs/project_organization_review_v1.md` for repository cleanup decisions.
- `docs/release_notes_beta2.md` for the current beta package notes and known gaps.

Some documents intentionally preserve historical planning context. When a
document disagrees with current code, prefer the implementation, the active
backlog, and the validation checklist, then update the stale document.

## Development Workflow

Use focused branches, normally prefixed with `codex/`.

```sh
git status -sb
git switch -c codex/<short-topic>
```

Keep implementation, validation updates, and documentation close together when
they describe the same behavior. Avoid deleting reference material until it has
been classified in `docs/README.md` or `resource/README.md`.
