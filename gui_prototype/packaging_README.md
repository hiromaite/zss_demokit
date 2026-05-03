# GUI Packaging Notes

This note tracks the repeatable PyInstaller path for the desktop GUI.

## Current Target

- spec file: `gui_prototype/zss_demokit_gui.spec`
- application version: `0.1.0-beta.3`
- distribution directory: `dist/zss_demokit_gui_win64_beta3/`
- executable name: `zss_demokit_gui`
- metadata source: `gui_prototype/src/app_metadata.py`

The current package is a beta-quality `onedir` bundle. Windows 11 Pro source
run, PyInstaller packaging, wired smoke, and BLE smoke have been confirmed by
user testing for beta2. The next package candidate is beta3 because the existing
`v0.1.0-beta.2` tag already points to an earlier packaging baseline.

See `docs/distribution_plan_v1.md` for the beta3 distribution gate, tag policy,
and artifact handling.

## Release Readiness Preflight

Before building from a fresh checkout, verify that packaging metadata, icon
assets, the PyInstaller spec, and release documents agree:

```bash
python tools/release_readiness_check.py
```

## Build

macOS / shell:

```bash
source <gui-venv>/bin/activate
pip install "pyinstaller>=6,<7"
python tools/release_readiness_check.py
pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec
```

Windows PowerShell:

```powershell
py -3.12 -m venv <gui-venv>
<gui-venv>\Scripts\Activate.ps1
pip install -r gui_prototype\requirements.txt
pip install "pyinstaller>=6,<7"
python tools\release_readiness_check.py
pyinstaller --noconfirm --clean gui_prototype\zss_demokit_gui.spec
```

## Expected Output

- `dist/zss_demokit_gui_win64_beta3/`
- `zss_demokit_gui.exe` on Windows
- the same launcher flow as `python gui_prototype/main.py`

## Bundled Assets And Metadata

- `bleak.backends` is collected for target OS BLE resolution.
- `pyqtgraph` data files are bundled.
- Windows version metadata is generated from `app_metadata.py`.
- The icon is optional and auto-enabled from `gui_prototype/assets/app_icon.*`.
- The icon can be regenerated with `python3.12 tools/generate_app_icon.py`.

## Known Gaps Before Formal Release

- no installer recipe yet
- no code signing path yet
- no updater path yet
- generated icon is acceptable for beta but may still need art direction
- beta3 release notes are tracked in `docs/release_notes_beta3.md`; there is
  no installer-integrated changelog yet
- `onefile` packaging has not been selected; `onedir` remains the recommended
  beta default because startup is faster and debugging is easier
