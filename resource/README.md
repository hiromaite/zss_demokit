# Reference Resources

This directory stores reference-only assets used to compare behavior, recover
old features, or reason about GUI patterns. These files are not the current
implementation entry points.

## Contents

| Path | Role |
| :--- | :--- |
| `old_firmware/` | Legacy BLE firmware reference |
| `old_gui/` | Legacy browser-based GUI reference |
| `example_gui/` | Separate-device PySide6 GUI used as a visual / UX reference |

## Rules

- Do not build or package from this directory for the current ZSS Demo Kit.
- Do not silently delete reference assets; first record the reason in a docs or
  cleanup review note.
- When copying ideas from these resources, re-implement them in the current
  firmware / GUI structure instead of depending on the reference path.
- Current firmware lives in top-level `src/` and `include/`.
- Current desktop GUI lives in `gui_prototype/`.
