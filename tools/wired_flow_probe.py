from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_SRC = REPO_ROOT / "gui_prototype" / "src"
sys.path.insert(0, str(GUI_SRC))

from protocol_constants import (  # noqa: E402
    TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED,
    WIRED_COMMAND_ID_GET_CAPABILITIES,
    WIRED_DEFAULT_BAUDRATE,
    derive_flow_rate_lpm_from_selected_differential_pressure_pa,
)
from wired_protocol import (  # noqa: E402
    WiredFrameBuffer,
    build_command_frame,
    decode_capabilities,
    decode_telemetry_sample,
)

import serial  # noqa: E402


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return math.nan
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def format_stats(label: str, values: list[float], unit: str) -> str:
    if not values:
        return f"{label}: no finite samples"
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    return (
        f"{label}: mean={mean:.4f} {unit} "
        f"stdev={stdev:.4f} {unit} "
        f"min={min(values):.4f} {unit} "
        f"p95={percentile(values, 0.95):.4f} {unit} "
        f"max={max(values):.4f} {unit}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe selected differential pressure and derived flow over wired transport.")
    parser.add_argument("--port", required=True, help="Serial port path, e.g. /dev/cu.usbmodem3101")
    parser.add_argument("--baudrate", type=int, default=WIRED_DEFAULT_BAUDRATE)
    parser.add_argument("--duration-s", type=float, default=8.0)
    parser.add_argument("--warmup-s", type=float, default=0.8)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.2, write_timeout=0.25) as ser:
        ser.dtr = False
        ser.rts = False
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        frame_buffer = WiredFrameBuffer()
        ser.write(build_command_frame(WIRED_COMMAND_ID_GET_CAPABILITIES, request_id=1))
        ser.flush()

        deadline = time.time() + max(1.0, args.duration_s + args.warmup_s)
        warmup_deadline = time.time() + max(0.0, args.warmup_s)

        telemetry_count = 0
        first_sequence: int | None = None
        last_sequence: int | None = None
        non_unit_gap_total = 0
        field_bits_seen: set[int] = set()
        capabilities = None
        has_dp_bit = False
        differential_pressures: list[float] = []
        low_range_pressures: list[float] = []
        high_range_pressures: list[float] = []
        flow_rates: list[float] = []

        while time.time() < deadline:
            waiting = int(ser.in_waiting)
            if waiting <= 0:
                time.sleep(0.02)
                continue

            chunk = ser.read(waiting)
            for frame in frame_buffer.push(chunk):
                if frame.message_type == 0x03 and capabilities is None:
                    capabilities = decode_capabilities(frame)
                    continue

                if frame.message_type != 0x01:
                    continue

                payload = decode_telemetry_sample(frame)
                telemetry_count += 1
                field_bits_seen.add(int(payload["telemetry_field_bits"]))

                sequence = int(payload["sequence"])
                if first_sequence is None:
                    first_sequence = sequence
                if last_sequence is not None and sequence != last_sequence + 1:
                    non_unit_gap_total += max(0, sequence - last_sequence - 1)
                last_sequence = sequence

                if time.time() < warmup_deadline:
                    continue

                differential_pressure_selected_pa = payload.get("differential_pressure_selected_pa")
                if differential_pressure_selected_pa is not None and math.isfinite(float(differential_pressure_selected_pa)):
                    differential_pressures.append(float(differential_pressure_selected_pa))
                low_range_raw = payload.get("differential_pressure_low_range_pa")
                if low_range_raw is not None and math.isfinite(float(low_range_raw)):
                    low_range_pressures.append(float(low_range_raw))
                high_range_raw = payload.get("differential_pressure_high_range_pa")
                if high_range_raw is not None and math.isfinite(float(high_range_raw)):
                    high_range_pressures.append(float(high_range_raw))

                flow_rate_lpm = derive_flow_rate_lpm_from_selected_differential_pressure_pa(
                    float(differential_pressure_selected_pa)
                    if differential_pressure_selected_pa is not None
                    else None
                )
                if math.isfinite(flow_rate_lpm):
                    flow_rates.append(float(flow_rate_lpm))

        print(f"Telemetry samples observed: {telemetry_count}")
        if first_sequence is not None and last_sequence is not None:
            print(f"Sequence span: {first_sequence} -> {last_sequence}")
        print(f"Non-unit sequence gap total: {non_unit_gap_total}")
        print(f"Telemetry field bits seen: {sorted(field_bits_seen)}")
        if capabilities is not None:
            print(f"Capabilities field bits: {capabilities['telemetry_field_bits']}")
            print(f"Capabilities fields: {capabilities['telemetry_fields']}")
            has_dp_bit = (
                int(capabilities["telemetry_field_bits"])
                & TELEMETRY_FIELD_DIFFERENTIAL_PRESSURE_SELECTED
            ) != 0
        print(f"Differential pressure advertised: {has_dp_bit}")
        print(format_stats("Selected differential pressure", differential_pressures, "Pa"))
        print(format_stats("SDP810 low-range raw", low_range_pressures, "Pa"))
        print(format_stats("SDP811 high-range raw", high_range_pressures, "Pa"))
        print(format_stats("Derived flow rate", flow_rates, "L/min"))

    print("wired_flow_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
