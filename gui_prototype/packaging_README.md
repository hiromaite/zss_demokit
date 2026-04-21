# GUI Packaging Notes

This note tracks the current packaging path for the desktop GUI.

## Goal

- keep the regular local Python run working on macOS during development
- prepare a repeatable `PyInstaller` path for the later Windows 11 Pro packaging pass

## Current Packaging Entry Point

- spec file: `gui_prototype/zss_demokit_gui.spec`
- current beta naming target: `zss_demokit_gui_win64_beta2`
- current application version: `0.1.0-beta.2`

The current spec is intentionally conservative:

- `onedir` style output
- icon embedding is optional and auto-enabled when an asset is placed at `gui_prototype/assets/app_icon.ico` or another configured candidate path
- no installer yet
- `bleak.backends` is collected so the transport backend can be resolved on the target OS
- `pyqtgraph` data files are bundled
- Windows version metadata file is generated from `gui_prototype/src/app_metadata.py`
- packaging icon asset can be regenerated with `python3.12 tools/generate_app_icon.py`

## Local Build Smoke

```bash
source .venv_gui_prototype/bin/activate
pip install "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec
```

Expected output:

- bundle directory under `dist/zss_demokit_gui_win64_beta2/`
- executable launches the same `LauncherWindow` as the source run

## Windows-Focused Follow-up

Before the first Windows packaging pass, confirm:

- generated icon is acceptable, or replace `gui_prototype/assets/app_icon.*` with the final art
- product / publisher metadata text in `gui_prototype/src/app_metadata.py`
- whether `onefile` is desirable or if `onedir` should remain the release default
- output directory and archive naming convention
- whether BLE on Windows needs any extra runtime prerequisites documented for users

## Known Gaps

- generated icon is a first-pass geometric asset and may still be art-directed later
- Windows 11 Pro での packaging / launch / serial / BLE smoke は通過済み
- no installer recipe yet
