from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_SRC = REPO_ROOT / "gui_prototype" / "src"
FIXTURE_PATH = REPO_ROOT / "test" / "fixtures" / "protocol_golden_v1.json"
CPP_VERIFIER_SOURCE = REPO_ROOT / "tools" / "firmware_fixture_verify.cpp"

sys.path.insert(0, str(GUI_SRC))

from ble_protocol import (  # noqa: E402
    decode_ble_capabilities_packet,
    decode_ble_event_packet,
    decode_ble_status_snapshot,
    decode_ble_telemetry_batch_packet,
    decode_ble_telemetry_packet,
)
from controllers import RecordingController  # noqa: E402
from mock_backend import TelemetryPoint  # noqa: E402
from wired_protocol import (  # noqa: E402
    WiredFrame,
    WiredFrameBuffer,
    decode_capabilities,
    decode_command_ack,
    decode_event,
    decode_status_snapshot,
    decode_telemetry_sample,
)


FLOAT_TOLERANCE = 1e-6

BLE_DECODERS = {
    "ble_telemetry": decode_ble_telemetry_packet,
    "ble_telemetry_batch": decode_ble_telemetry_batch_packet,
    "ble_status": decode_ble_status_snapshot,
    "ble_capabilities": decode_ble_capabilities_packet,
    "ble_event": decode_ble_event_packet,
}

WIRED_DECODERS = {
    "wired_telemetry": decode_telemetry_sample,
    "wired_status": decode_status_snapshot,
    "wired_capabilities": decode_capabilities,
    "wired_event": decode_event,
    "wired_command_ack": decode_command_ack,
}

INVALID_BLE_DECODERS = {
    "ble_telemetry": decode_ble_telemetry_packet,
    "ble_status": decode_ble_status_snapshot,
}


def load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def assert_close(expected: Any, actual: Any, path: str) -> None:
    if isinstance(expected, bool):
        if expected is not actual:
            raise AssertionError(f"{path}: expected {expected!r}, got {actual!r}")
        return

    if isinstance(expected, (int, str)):
        if expected != actual:
            raise AssertionError(f"{path}: expected {expected!r}, got {actual!r}")
        return

    if isinstance(expected, float):
        if not isinstance(actual, (float, int)) or not math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=FLOAT_TOLERANCE):
            raise AssertionError(f"{path}: expected {expected!r}, got {actual!r}")
        return

    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            raise AssertionError(f"{path}: expected list length {len(expected)}, got {actual!r}")
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            assert_close(expected_item, actual_item, f"{path}[{index}]")
        return

    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise AssertionError(f"{path}: expected dict, got {actual!r}")
        for key, expected_value in expected.items():
            if key not in actual:
                raise AssertionError(f"{path}: missing key {key!r} in {actual!r}")
            assert_close(expected_value, actual[key], f"{path}.{key}")
        return

    raise TypeError(f"Unsupported comparison type at {path}: {type(expected)!r}")


def assert_frame(expected: dict[str, Any], frame: WiredFrame, path: str) -> None:
    actual = {
        "version_major": frame.version_major,
        "version_minor": frame.version_minor,
        "message_type": frame.message_type,
        "sequence": frame.sequence,
        "request_id": frame.request_id,
    }
    assert_close(expected, actual, path)


def build_cpp_verifier() -> Path:
    compiler = shutil.which("c++")
    if compiler is None:
        raise RuntimeError("c++ compiler was not found in PATH")

    output_path = Path(tempfile.gettempdir()) / "zss_protocol_fixture_verify"
    sources = [
        CPP_VERIFIER_SOURCE,
        REPO_ROOT / "src" / "protocol" / "PayloadBuilders.cpp",
        REPO_ROOT / "src" / "app" / "AppState.cpp",
        REPO_ROOT / "src" / "app" / "CapabilityBuilder.cpp",
    ]
    command = [
        compiler,
        "-std=gnu++17",
        "-I",
        str(REPO_ROOT / "include"),
        "-o",
        str(output_path),
        *(str(source) for source in sources),
    ]
    subprocess.run(command, check=True, cwd=REPO_ROOT)
    return output_path


def verify_firmware_case(binary_path: Path, case_id: str, expected_hex: str) -> None:
    result = subprocess.run(
        [str(binary_path), case_id],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    actual_hex = result.stdout.strip().lower()
    if actual_hex != expected_hex.lower():
        raise AssertionError(
            f"firmware case {case_id}: expected {expected_hex.lower()}, got {actual_hex}"
        )


def run_valid_cases(fixtures: dict[str, Any], firmware_binary: Path) -> None:
    for case in fixtures["valid_cases"]:
        raw = bytes.fromhex(case["raw_hex"])
        kind = case["kind"]
        case_id = case["id"]

        if kind in BLE_DECODERS:
            actual = BLE_DECODERS[kind](raw)
            assert_close(case["expected"], actual, case_id)
        else:
            frames = WiredFrameBuffer().push(raw)
            if len(frames) != 1:
                raise AssertionError(f"{case_id}: expected 1 frame, got {len(frames)}")
            frame = frames[0]
            assert_frame(case["expected_frame"], frame, f"{case_id}.frame")
            actual = WIRED_DECODERS[kind](frame)
            assert_close(case["expected"], actual, case_id)

        if case.get("firmware_case"):
            verify_firmware_case(firmware_binary, case_id, case["raw_hex"])

        print(f"PASS {case_id}")


def run_invalid_cases(fixtures: dict[str, Any]) -> None:
    for case in fixtures["invalid_cases"]:
        raw = bytes.fromhex(case["raw_hex"])
        kind = case["kind"]
        case_id = case["id"]

        if kind == "ble_invalid_length":
            decoder = INVALID_BLE_DECODERS[case["decoder"]]
            try:
                decoder(raw)
            except ValueError as error:
                message = str(error)
                if case["expected_error_substring"] not in message:
                    raise AssertionError(
                        f"{case_id}: expected error containing {case['expected_error_substring']!r}, got {message!r}"
                    ) from error
            else:
                raise AssertionError(f"{case_id}: expected ValueError")
        elif kind == "wired_bad_crc":
            frames = WiredFrameBuffer().push(raw)
            if len(frames) != int(case["expected_frame_count"]):
                raise AssertionError(
                    f"{case_id}: expected {case['expected_frame_count']} frames, got {len(frames)}"
                )
        elif kind == "wired_resync_stream":
            frames = WiredFrameBuffer().push(raw)
            if len(frames) != int(case["expected_frame_count"]):
                raise AssertionError(
                    f"{case_id}: expected {case['expected_frame_count']} frames, got {len(frames)}"
                )
            frame = frames[0]
            assert_frame(case["expected_frame"], frame, f"{case_id}.frame")
            actual = WIRED_DECODERS[case["decoder"]](frame)
            assert_close(case["expected"], actual, case_id)
        else:
            raise AssertionError(f"{case_id}: unknown invalid fixture kind {kind!r}")

        print(f"PASS {case_id}")


def build_point(payload: dict[str, Any]) -> TelemetryPoint:
    return TelemetryPoint(
        sequence=int(payload["sequence"]),
        host_received_at=datetime.fromisoformat(str(payload["host_received_at_iso"])),
        nominal_sample_period_ms=int(payload["nominal_sample_period_ms"]),
        status_flags=int(payload["status_flags"]),
        zirconia_output_voltage_v=float(payload["zirconia_output_voltage_v"]),
        heater_rtd_resistance_ohm=float(payload["heater_rtd_resistance_ohm"]),
        zirconia_ip_voltage_v=(
            float(payload["zirconia_ip_voltage_v"])
            if payload.get("zirconia_ip_voltage_v") not in (None, "")
            else None
        ),
        internal_voltage_v=(
            float(payload["internal_voltage_v"])
            if payload.get("internal_voltage_v") not in (None, "")
            else None
        ),
        differential_pressure_selected_pa=(
            float(payload["differential_pressure_selected_pa"])
            if payload.get("differential_pressure_selected_pa") not in (None, "")
            else None
        ),
        differential_pressure_low_range_pa=(
            float(payload["differential_pressure_low_range_pa"])
            if payload.get("differential_pressure_low_range_pa") not in (None, "")
            else None
        ),
        differential_pressure_high_range_pa=(
            float(payload["differential_pressure_high_range_pa"])
            if payload.get("differential_pressure_high_range_pa") not in (None, "")
            else None
        ),
    )


def run_csv_cases(fixtures: dict[str, Any]) -> None:
    for case in fixtures["csv_cases"]:
        controller = RecordingController()
        with tempfile.TemporaryDirectory(prefix="zss_fixture_csv_") as temp_dir:
            controller.start(
                base_dir=Path(temp_dir),
                gui_app_name="fixture-smoke",
                gui_app_version="1.0",
                mode=str(case["mode"]),
                transport_type=str(case["transport_type"]),
                device_identifier="fixture-device",
                firmware_version="0.1.0",
                protocol_version="1.0",
                nominal_sample_period_ms=str(case["target_point"]["nominal_sample_period_ms"]),
                source_endpoint="fixture://local",
            )
            controller.append_row(
                point=build_point(case["seed_point"]),
                mode=str(case["mode"]),
                transport_type=str(case["transport_type"]),
            )
            controller.append_row(
                point=build_point(case["target_point"]),
                mode=str(case["mode"]),
                transport_type=str(case["transport_type"]),
            )
            controller.flush()
            if controller.partial_path is None:
                raise AssertionError(f"{case['id']}: partial path was not created")
            lines = controller.partial_path.read_text(encoding="utf-8").splitlines()
            actual_row = lines[-1].split(",")
            assert_close(case["expected_row"], actual_row, case["id"])
            controller.stop()
        print(f"PASS {case['id']}")


def main() -> int:
    fixtures = load_fixture()
    firmware_binary = build_cpp_verifier()
    run_valid_cases(fixtures, firmware_binary)
    run_invalid_cases(fixtures)
    run_csv_cases(fixtures)
    print("protocol_fixture_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
