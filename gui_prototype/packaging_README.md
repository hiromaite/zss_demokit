# GUI Packaging Notes

This note tracks the repeatable PyInstaller path for the desktop GUI.

## Current Target

- spec file: `gui_prototype/zss_demokit_gui.spec`
- application version: `0.1.0-beta.2`
- distribution directory: `dist/zss_demokit_gui_win64_beta2/`
- executable name: `zss_demokit_gui`
- metadata source: `gui_prototype/src/app_metadata.py`

The current package is a beta-quality `onedir` bundle. Windows 11 Pro source
run, PyInstaller packaging, wired smoke, and BLE smoke have been confirmed by
user testing for beta2.

## Build

macOS / shell:

```bash
source .venv_gui_prototype/bin/activate
pip install "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean gui_prototype/zss_demokit_gui.spec
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv_gui_prototype
.venv_gui_prototype\Scripts\Activate.ps1
pip install -r gui_prototype\requirements.txt
pip install "pyinstaller>=6,<7"
pyinstaller --noconfirm --clean gui_prototype\zss_demokit_gui.spec
```

## Expected Output

- `dist/zss_demokit_gui_win64_beta2/`
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
- release notes are still maintained through docs / commit history rather than
  a formal packaged changelog
- `onefile` packaging has not been selected; `onedir` remains the recommended
  beta default because startup is faster and debugging is easier
