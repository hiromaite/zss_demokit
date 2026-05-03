#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SMOKE_SOURCE = REPO_ROOT / "tools" / "command_processor_smoke.cpp"


ARDUINO_STUB = """#pragma once
#include <stdint.h>

inline constexpr int OUTPUT = 1;
inline constexpr int HIGH = 1;
inline constexpr int LOW = 0;

inline void pinMode(int8_t, int) {}
inline void digitalWrite(int8_t, int) {}
inline void analogWrite(int8_t, int) {}
inline void analogWriteResolution(uint8_t) {}
inline void analogWriteFrequency(uint32_t) {}
"""


def main() -> int:
    compiler = shutil.which("c++")
    if compiler is None:
        raise RuntimeError("c++ compiler was not found in PATH")

    with tempfile.TemporaryDirectory(prefix="zss_command_processor_smoke_") as temp_dir:
        temp_path = Path(temp_dir)
        stub_dir = temp_path / "arduino_stub"
        stub_dir.mkdir()
        (stub_dir / "Arduino.h").write_text(ARDUINO_STUB, encoding="utf-8")
        binary_path = temp_path / "command_processor_smoke"
        command = [
            compiler,
            "-std=gnu++17",
            "-I",
            str(stub_dir),
            "-I",
            str(REPO_ROOT / "include"),
            "-o",
            str(binary_path),
            str(SMOKE_SOURCE),
            str(REPO_ROOT / "src" / "app" / "CommandProcessor.cpp"),
            str(REPO_ROOT / "src" / "app" / "AppState.cpp"),
            str(REPO_ROOT / "src" / "services" / "PumpController.cpp"),
            str(REPO_ROOT / "src" / "services" / "HeaterPowerController.cpp"),
        ]
        subprocess.run(command, check=True, cwd=REPO_ROOT)
        result = subprocess.run(
            [str(binary_path)],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
