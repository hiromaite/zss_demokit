# Repository Guidelines For Coding Agents

This file is the agent-facing companion to `README.md`. The README is the
shared entry point for all developers; this document contains operating rules
for AI coding agents working in this repository.

## Project Context

- Firmware is a top-level PlatformIO project for M5Stack StampS3.
- Desktop GUI code lives under `gui_prototype/`; the directory name is
  historical, but the code is active.
- Protocol, architecture, validation, backlog, and release planning live in
  `docs/`.
- Reference-only legacy firmware / GUI assets live under `resource/`.
- The current distribution candidate is `0.1.0-beta.3`; do not retag or move
  the existing `v0.1.0-beta.2` tag.

## Branch And Git Workflow

- Use focused branches for agent work. For Codex-created branches, use
  `codex/<short-topic>` unless the user asks for another name.
- Keep implementation, tests or probes, and documentation updates together
  when they describe the same behavior.
- Prefer fast-forward merges when a branch is strictly ahead of its base.
- Do not create release tags until the Windows packaged smoke has passed.
- Never rewrite, move, or delete existing release tags unless the user
  explicitly asks for that.
- Do not revert user changes or unrelated dirty worktree changes.

## Environment Guidance

- Virtual environment names are examples, not requirements. Use the active
  environment provided by the user or create a task-local one when needed.
- GUI commands assume Python `3.12.x` and dependencies from
  `gui_prototype/requirements.txt`.
- Firmware commands assume either a global `pio` command or a virtual
  environment with `platformio` installed.
- Run commands from the repository root unless a tool document says otherwise.

## Common Commands

GUI no-device baseline:

```sh
python -m compileall gui_prototype/src tools
python tools/protocol_fixture_smoke.py
python tools/gui_layout_smoke.py
python tools/gui_log_history_smoke.py
python tools/gui_engineering_tools_smoke.py
```

Firmware baseline:

```sh
pio run
python tools/command_processor_smoke.py
```

Release readiness:

```sh
python tools/release_readiness_check.py
```

Live wired and BLE probes require connected hardware. Do not mark those as
passed unless the command was actually run against the relevant device or the
user reports the result.

## Documentation Rules

- Keep `README.md` concise and developer-facing.
- Keep agent-only workflow, branch-prefix, and safety rules in `AGENTS.md`.
- Put volatile implementation snapshots in `docs/project_status_v1.md`.
- Put release gates, tag policy, and artifact handling in
  `docs/distribution_plan_v1.md`.
- Update `docs/validation_checklist_v1.md` when a smoke, probe, manual test, or
  release-readiness check becomes part of the expected gate.

## Coding And Editing Rules

- Preserve existing project style and naming.
- Prefer small, responsibility-focused modules over expanding
  `main_window.py`, `dialogs.py`, or `mock_backend.py`.
- Avoid large renames or physical directory moves unless the task is dedicated
  to that migration.
- Generated artifacts such as `.pio/`, `.venv*`, `build/`, `dist/`, and
  `__pycache__/` should not be committed.

## Release Rules

- The next Windows package candidate is `0.1.0-beta.3` with distribution
  directory `dist/zss_demokit_gui_win64_beta3/`.
- Before packaging, run `python tools/release_readiness_check.py`.
- After Windows packaging, execute `docs/windows_beta_smoke_checklist_v1.md`.
- Create `v0.1.0-beta.3` only after packaged Windows smoke passes.
