# zss_demokit

`zss_demokit` is the firmware and desktop GUI workspace for the ZSS Demo Kit.
The system connects to an M5Stack StampS3 based sensor device over USB serial
or BLE, visualizes zirconia / flow related telemetry, controls the pump and
heater path, and records measurement sessions to CSV for later analysis.

This repository contains the current PlatformIO firmware, the current PySide6
desktop application, shared protocol definitions, validation probes, packaging
notes, and reference copies of older implementations.

## Project State

This project is active beta software. Firmware and desktop GUI are both active
implementation surfaces. The current Windows distribution candidate is
`0.1.0-beta.4` with package directory `dist/zss_demokit_gui_win64_beta4/`.

See `docs/project_status_v1.md`, `docs/validation_checklist_v1.md`, and
`docs/release_notes_beta4.md` for the current implementation snapshot,
validation evidence, and beta package notes.

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

## Prerequisites

- Python `3.12.x`
- PlatformIO for firmware work
- A Python virtual environment for the desktop GUI
- A Windows 11 Pro machine for packaged-app smoke testing
- Target hardware when running wired, BLE, upload, or flow probes

Virtual environment names are not fixed. The examples below use `<gui-venv>`
and `<pio-venv>` as placeholders; choose names that fit your local workflow.

## Firmware Setup

Option A: use a globally available PlatformIO command.

```sh
pio run
pio run -t upload --upload-port <PORT>
pio device monitor --port <PORT> --baud 115200
```

Option B: install PlatformIO into a project-local virtual environment.

```sh
python3.12 -m venv <pio-venv>
source <pio-venv>/bin/activate
python -m pip install --upgrade pip
python -m pip install platformio
pio run
```

On Windows PowerShell:

```powershell
py -3.12 -m venv <pio-venv>
<pio-venv>\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install platformio
pio run
```

## Desktop GUI Setup

The current GUI implementation lives in `gui_prototype/`. The name remains for
path stability, but the contents are the active desktop application.

macOS / Linux shell:

```sh
python3.12 -m venv <gui-venv>
source <gui-venv>/bin/activate
python -m pip install --upgrade pip
python -m pip install -r gui_prototype/requirements.txt
python gui_prototype/main.py
```

Windows PowerShell:

```powershell
py -3.12 -m venv <gui-venv>
<gui-venv>\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r gui_prototype\requirements.txt
python gui_prototype\main.py
```

## Packaging

Run the release-readiness preflight before building a Windows package.

macOS / Linux shell:

```sh
source <gui-venv>/bin/activate
python -m pip install "pyinstaller>=6,<7"
python tools/release_readiness_check.py
pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec
```

Windows PowerShell:

```powershell
<gui-venv>\Scripts\Activate.ps1
pip install "pyinstaller>=6,<7"
python tools\release_readiness_check.py
pyinstaller --noconfirm --clean gui_prototype\zss_demokit_gui.spec
```

Expected beta4 output:

```text
dist/zss_demokit_gui_win64_beta4/
```

Packaging metadata is centralized in `gui_prototype/src/app_metadata.py`.
The full distribution gate is documented in `docs/distribution_plan_v1.md`.

## Validation

Run the smallest relevant checks before and after a change. Activate the GUI
virtual environment first unless your shell already resolves the intended
Python interpreter.

No-device baseline:

```sh
python -m compileall gui_prototype/src tools
python tools/protocol_fixture_smoke.py
python tools/gui_layout_smoke.py
python tools/gui_log_history_smoke.py
python tools/gui_startup_mode_smoke.py
python tools/o2_filter_smoke.py
python tools/gui_o2_filter_smoke.py
```

Firmware baseline:

```sh
pio run
python tools/command_processor_smoke.py
```

Wired device:

```sh
python tools/wired_serial_smoke.py --port <PORT> --baudrate 115200
python tools/gui_wired_session_probe.py --port <PORT> --duration-s 18 --toggle-interval-s 3
python tools/wired_flow_probe.py --port <PORT> --duration-s 6
```

BLE device:

```sh
python tools/ble_smoke.py --name GasSensor-Proto --telemetry-count 20 --telemetry-timeout 10 --observe-duration 8
python tools/gui_ble_session_probe.py --device-prefix GasSensor-Proto --duration-s 180 --recording-duration-s 45 --reconnect-at-s 60
```

The authoritative validation log is `docs/validation_checklist_v1.md`.

## Documentation

Start with:

- `docs/README.md` for the documentation index and status labels.
- `docs/project_status_v1.md` for the current implementation snapshot.
- `docs/system_requirements.md` for scope and system requirements.
- `docs/system_architecture.md` for component boundaries.
- `docs/protocol_catalog_v1.md` for canonical protocol names and fields.
- `docs/implementation_backlog_v1.md` for active backlog and milestone state.
- `docs/validation_checklist_v1.md` for tested behavior.
- `docs/distribution_plan_v1.md` for beta distribution policy and task order.
- `docs/release_notes_beta4.md` for the current beta package notes and known gaps.

Some documents intentionally preserve historical planning context. When a
document disagrees with current code, prefer the implementation, the active
backlog, the project status snapshot, and the validation checklist, then update
the stale document.

## Agent Guidance

Coding-agent-specific workflow rules live in `AGENTS.md`. Human contributors
can read it too, but the root README intentionally avoids agent-only branch
prefixes, tool behavior, or Codex-specific operating rules.
