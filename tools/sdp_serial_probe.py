from __future__ import annotations

import argparse
import math
import re
import statistics
import time

import serial


SAMPLE_PATTERN = re.compile(
    r"DpSel=(?P<dp_sel>-?\d+\.\d+)Pa\s+"
    r"Dp125=(?P<dp_low>-?\d+\.\d+)Pa\s+"
    r"Dp500=(?P<dp_high>-?\d+\.\d+)Pa\s+"
    r"DpLow=(?P<dp_low_selected>[01])"
)


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    index_95 = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * 0.95))))
    return {
        "mean": statistics.fmean(values),
        "stdev": statistics.pstdev(values) if len(values) > 1 else 0.0,
        "min": ordered[0],
        "p95": ordered[index_95],
        "max": ordered[-1],
    }


def print_summary(label: str, values: list[float]) -> None:
    summary = summarize(values)
    if not summary:
        print(f"{label}: no samples")
        return
    print(
        f"{label}: "
        f"mean={summary['mean']:.4f} "
        f"stdev={summary['stdev']:.4f} "
        f"min={summary['min']:.4f} "
        f"p95={summary['p95']:.4f} "
        f"max={summary['max']:.4f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--duration-s", type=float, default=10.0)
    parser.add_argument("--settle-s", type=float, default=1.5)
    args = parser.parse_args()

    dp_sel_values: list[float] = []
    dp_low_values: list[float] = []
    dp_high_values: list[float] = []
    selected_low_count = 0
    selected_high_count = 0

    with serial.Serial(args.port, args.baudrate, timeout=0.25) as ser:
        ser.dtr = False
        ser.rts = False
        time.sleep(args.settle_s)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        deadline = time.monotonic() + args.duration_s
        while time.monotonic() < deadline:
            raw_line = ser.readline()
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="replace").strip()
            match = SAMPLE_PATTERN.search(line)
            if not match:
                continue

            dp_sel_values.append(float(match.group("dp_sel")))
            dp_low_values.append(float(match.group("dp_low")))
            dp_high_values.append(float(match.group("dp_high")))
            if int(match.group("dp_low_selected")) == 1:
                selected_low_count += 1
            else:
                selected_high_count += 1

    if not dp_sel_values:
        raise RuntimeError("No differential-pressure samples found in serial log")

    print(f"Collected samples: {len(dp_sel_values)}")
    print_summary("DpSel (Pa)", dp_sel_values)
    print_summary("Dp125 (Pa)", dp_low_values)
    print_summary("Dp500 (Pa)", dp_high_values)
    print(
        f"Selector state count: low={selected_low_count} high={selected_high_count}"
    )

    if any(not math.isfinite(value) for value in dp_sel_values + dp_low_values + dp_high_values):
        raise RuntimeError("Non-finite differential-pressure value observed")

    print("sdp_serial_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
