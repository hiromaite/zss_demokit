from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections import deque
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui_prototype" / "src"))

from protocol_constants import (  # noqa: E402
    WIRED_COMMAND_ID_GET_CAPABILITIES,
    WIRED_MESSAGE_TYPE_CAPABILITIES,
    WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE,
    WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC,
)
from wired_protocol import (  # noqa: E402
    WiredFrame,
    WiredFrameBuffer,
    build_command_frame,
    decode_capabilities,
    decode_timing_diagnostic,
    decode_telemetry_sample,
)


class SerialProtocolSession:
    def __init__(self, ser: serial.Serial) -> None:
        self._serial = ser
        self._frame_buffer = WiredFrameBuffer()
        self._pending_frames: deque[WiredFrame] = deque()

    def _pump_frames(self) -> None:
        waiting = max(1, int(getattr(self._serial, "in_waiting", 0)))
        chunk = self._serial.read(waiting)
        if chunk:
            self._pending_frames.extend(self._frame_buffer.push(chunk))

    def read_matching_frame(
        self,
        *,
        message_type: int,
        request_id: int | None = None,
        timeout_s: float = 3.0,
    ) -> WiredFrame:
        deadline = time.monotonic() + timeout_s
        skipped: deque[WiredFrame] = deque()

        while time.monotonic() < deadline:
            while self._pending_frames:
                frame = self._pending_frames.popleft()
                if frame.message_type == message_type and (request_id is None or frame.request_id == request_id):
                    while skipped:
                        self._pending_frames.appendleft(skipped.pop())
                    return frame
                skipped.append(frame)

            self._pump_frames()
            time.sleep(0.001)

        while skipped:
            self._pending_frames.appendleft(skipped.pop())
        raise TimeoutError(
            f"Timed out waiting for message_type=0x{message_type:02X}"
            + (f" request_id={request_id}" if request_id is not None else "")
        )

    def read_next_frame(self, *, timeout_s: float = 3.0) -> WiredFrame:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._pending_frames:
                return self._pending_frames.popleft()

            self._pump_frames()
            time.sleep(0.001)

        raise TimeoutError("Timed out waiting for next wired frame")

    def clear_pending_frames(self) -> None:
        self._pending_frames.clear()
        self._frame_buffer = WiredFrameBuffer()


def summarize_intervals(intervals_ms: list[float]) -> dict[str, float]:
    if not intervals_ms:
        return {}
    ordered = sorted(intervals_ms)
    index_95 = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * 0.95))))
    return {
        "mean_ms": statistics.fmean(intervals_ms),
        "stdev_ms": statistics.pstdev(intervals_ms) if len(intervals_ms) > 1 else 0.0,
        "min_ms": ordered[0],
        "p95_ms": ordered[index_95],
        "max_ms": ordered[-1],
    }


def summarize_jitter_us(intervals_ms: list[float], nominal_period_ms: float) -> dict[str, float]:
    if not intervals_ms:
        return {}
    jitter_us = [(interval - nominal_period_ms) * 1000.0 for interval in intervals_ms]
    abs_jitter_us = [abs(value) for value in jitter_us]
    ordered_abs = sorted(abs_jitter_us)
    index_95 = min(len(ordered_abs) - 1, max(0, int(round((len(ordered_abs) - 1) * 0.95))))
    return {
        "mean_jitter_us": statistics.fmean(jitter_us),
        "stdev_jitter_us": statistics.pstdev(jitter_us) if len(jitter_us) > 1 else 0.0,
        "min_jitter_us": min(jitter_us),
        "max_jitter_us": max(jitter_us),
        "mean_abs_jitter_us": statistics.fmean(abs_jitter_us),
        "p95_abs_jitter_us": ordered_abs[index_95],
        "max_abs_jitter_us": ordered_abs[-1],
    }


def format_interval_summary(label: str, summary: dict[str, float]) -> str:
    if not summary:
        return f"{label}: no intervals"
    return (
        f"{label}: "
        f"mean={summary['mean_ms']:.3f} "
        f"stdev={summary['stdev_ms']:.3f} "
        f"min={summary['min_ms']:.3f} "
        f"p95={summary['p95_ms']:.3f} "
        f"max={summary['max_ms']:.3f}"
    )


def format_jitter_summary(label: str, summary: dict[str, float]) -> str:
    if not summary:
        return f"{label}: no jitter data"
    return (
        f"{label}: "
        f"mean={summary['mean_jitter_us']:.1f} "
        f"stdev={summary['stdev_jitter_us']:.1f} "
        f"min={summary['min_jitter_us']:.1f} "
        f"max={summary['max_jitter_us']:.1f} "
        f"mean_abs={summary['mean_abs_jitter_us']:.1f} "
        f"p95_abs={summary['p95_abs_jitter_us']:.1f} "
        f"max_abs={summary['max_abs_jitter_us']:.1f}"
    )


def tick_delta_us(previous_tick: int, current_tick: int) -> int:
    return (current_tick - previous_tick) & 0xFFFFFFFF


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--samples", type=int, default=1200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--slow-threshold-ms", type=float, default=12.0)
    parser.add_argument("--slow-limit", type=int, default=12)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate, timeout=0.05) as ser:
        session = SerialProtocolSession(ser)
        time.sleep(1.5)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        ser.write(build_command_frame(WIRED_COMMAND_ID_GET_CAPABILITIES, request_id=1))
        capabilities_frame = session.read_matching_frame(
            message_type=WIRED_MESSAGE_TYPE_CAPABILITIES,
            request_id=1,
            timeout_s=4.0,
        )
        capabilities = decode_capabilities(capabilities_frame)
        session.clear_pending_frames()
        ser.reset_input_buffer()

        host_timestamps: list[float] = []
        sequences: list[int] = []
        status_flags: list[int] = []
        status_by_sequence: dict[int, int] = {}
        timing_by_sequence: dict[int, dict[str, int]] = {}

        while len(sequences) < args.warmup + args.samples:
            frame = session.read_next_frame(timeout_s=4.0)
            if frame.message_type == WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC:
                timing = decode_timing_diagnostic(frame)
                timing_by_sequence[int(timing["sequence"])] = timing
                continue
            if frame.message_type != WIRED_MESSAGE_TYPE_TELEMETRY_SAMPLE:
                continue

            host_timestamps.append(time.monotonic())
            sample = decode_telemetry_sample(frame)
            sequences.append(int(sample["sequence"]))
            status_flag = int(sample["status_flags"])
            status_flags.append(status_flag)
            status_by_sequence[int(sample["sequence"])] = status_flag

        drain_deadline = time.monotonic() + 0.25
        while time.monotonic() < drain_deadline:
            try:
                frame = session.read_next_frame(timeout_s=0.02)
            except TimeoutError:
                continue
            if frame.message_type == WIRED_MESSAGE_TYPE_TIMING_DIAGNOSTIC:
                timing = decode_timing_diagnostic(frame)
                timing_by_sequence[int(timing["sequence"])] = timing

    host_timestamps = host_timestamps[args.warmup:]
    sequences = sequences[args.warmup:]
    status_flags = status_flags[args.warmup:]
    nominal_period_ms = float(capabilities["nominal_sample_period_ms"])

    inter_arrival_ms = [
        (host_timestamps[index] - host_timestamps[index - 1]) * 1000.0
        for index in range(1, len(host_timestamps))
    ]
    device_inter_arrival_ms: list[float] = []
    acquisition_duration_ms: list[float] = []
    telemetry_publish_duration_ms: list[float] = []
    scheduler_lateness_ms: list[float] = []
    adc_total_duration_ms: list[float] = []
    differential_pressure_total_duration_ms: list[float] = []
    ads_ch0_duration_ms: list[float] = []
    ads_ch1_duration_ms: list[float] = []
    ads_ch2_duration_ms: list[float] = []
    sdp_low_range_duration_ms: list[float] = []
    sdp_high_range_duration_ms: list[float] = []
    residual_or_wait_ms: list[float] = []
    slow_samples: list[dict[str, float | int]] = []
    matched_device_ticks = 0
    matched_extended_timing = 0
    matched_acquisition_breakdown = 0
    for sequence in sequences:
        timing = timing_by_sequence.get(sequence)
        if timing is None:
            continue
        acquisition_us = timing.get("acquisition_duration_us")
        publish_us = timing.get("telemetry_publish_duration_us")
        lateness_us = timing.get("scheduler_lateness_us")
        if acquisition_us is None or publish_us is None or lateness_us is None:
            continue
        matched_extended_timing += 1
        acquisition_duration_ms.append(float(acquisition_us) / 1000.0)
        telemetry_publish_duration_ms.append(float(publish_us) / 1000.0)
        scheduler_lateness_ms.append(float(lateness_us) / 1000.0)
        breakdown_keys = (
            "adc_total_duration_us",
            "differential_pressure_total_duration_us",
            "ads_ch0_duration_us",
            "ads_ch1_duration_us",
            "ads_ch2_duration_us",
            "sdp_low_range_duration_us",
            "sdp_high_range_duration_us",
        )
        if all(timing.get(key) is not None for key in breakdown_keys):
            matched_acquisition_breakdown += 1
            adc_total_ms = float(timing["adc_total_duration_us"]) / 1000.0
            dp_total_ms = float(timing["differential_pressure_total_duration_us"]) / 1000.0
            ads_ch0_ms = float(timing["ads_ch0_duration_us"]) / 1000.0
            ads_ch1_ms = float(timing["ads_ch1_duration_us"]) / 1000.0
            ads_ch2_ms = float(timing["ads_ch2_duration_us"]) / 1000.0
            sdp_low_ms = float(timing["sdp_low_range_duration_us"]) / 1000.0
            sdp_high_ms = float(timing["sdp_high_range_duration_us"]) / 1000.0
            adc_total_duration_ms.append(adc_total_ms)
            differential_pressure_total_duration_ms.append(dp_total_ms)
            ads_ch0_duration_ms.append(ads_ch0_ms)
            ads_ch1_duration_ms.append(ads_ch1_ms)
            ads_ch2_duration_ms.append(ads_ch2_ms)
            sdp_low_range_duration_ms.append(sdp_low_ms)
            sdp_high_range_duration_ms.append(sdp_high_ms)
            if float(acquisition_us) / 1000.0 >= args.slow_threshold_ms:
                slow_samples.append(
                    {
                        "sequence": sequence,
                        "status_flags": status_by_sequence.get(sequence, 0),
                        "acquisition_ms": float(acquisition_us) / 1000.0,
                        "adc_ms": adc_total_ms,
                        "dp_ms": dp_total_ms,
                        "ads_ch0_ms": ads_ch0_ms,
                        "ads_ch1_ms": ads_ch1_ms,
                        "ads_ch2_ms": ads_ch2_ms,
                        "sdp_low_ms": sdp_low_ms,
                        "sdp_high_ms": sdp_high_ms,
                        "lateness_ms": float(lateness_us) / 1000.0,
                    }
                )

    for previous_sequence, current_sequence in zip(sequences, sequences[1:]):
        previous_timing = timing_by_sequence.get(previous_sequence)
        current_timing = timing_by_sequence.get(current_sequence)
        if previous_timing is None or current_timing is None:
            continue
        previous_tick = int(previous_timing["sample_tick_us"])
        current_tick = int(current_timing["sample_tick_us"])
        if current_sequence != previous_sequence + 1:
            continue
        matched_device_ticks += 1
        interval_us = tick_delta_us(previous_tick, current_tick)
        device_inter_arrival_ms.append(interval_us / 1000.0)
        acquisition_us = previous_timing.get("acquisition_duration_us")
        publish_us = previous_timing.get("telemetry_publish_duration_us")
        if acquisition_us is not None and publish_us is not None:
            residual_or_wait_ms.append(
                (interval_us - int(acquisition_us) - int(publish_us)) / 1000.0
            )

    sequence_gaps = [
        sequences[index] - sequences[index - 1]
        for index in range(1, len(sequences))
    ]
    gap_count = sum(1 for gap in sequence_gaps if gap != 1)
    host_summary = summarize_intervals(inter_arrival_ms)
    device_summary = summarize_intervals(device_inter_arrival_ms)
    device_jitter_summary = summarize_jitter_us(device_inter_arrival_ms, nominal_period_ms)
    acquisition_summary = summarize_intervals(acquisition_duration_ms)
    telemetry_publish_summary = summarize_intervals(telemetry_publish_duration_ms)
    scheduler_lateness_summary = summarize_intervals(scheduler_lateness_ms)
    adc_total_summary = summarize_intervals(adc_total_duration_ms)
    differential_pressure_total_summary = summarize_intervals(differential_pressure_total_duration_ms)
    ads_ch0_summary = summarize_intervals(ads_ch0_duration_ms)
    ads_ch1_summary = summarize_intervals(ads_ch1_duration_ms)
    ads_ch2_summary = summarize_intervals(ads_ch2_duration_ms)
    sdp_low_summary = summarize_intervals(sdp_low_range_duration_ms)
    sdp_high_summary = summarize_intervals(sdp_high_range_duration_ms)
    residual_summary = summarize_intervals(residual_or_wait_ms)

    print("Capabilities:", capabilities)
    print(f"Collected telemetry samples: {len(sequences)}")
    print(f"Nominal sample period (reported): {capabilities['nominal_sample_period_ms']} ms")
    print(f"Sequence first/last: {sequences[0]} -> {sequences[-1]}")
    print(f"Non-unit sequence gaps: {gap_count}")
    print(f"Observed status flags: {sorted(set(status_flags))}")
    print(f"Timing diagnostics matched: {matched_device_ticks}/{max(0, len(sequences) - 1)} interval(s)")
    print(f"Extended timing diagnostics matched: {matched_extended_timing}/{len(sequences)} sample(s)")
    print(f"Acquisition breakdown diagnostics matched: {matched_acquisition_breakdown}/{len(sequences)} sample(s)")
    print(format_interval_summary("Host read/decode inter-arrival ms", host_summary))
    print(format_interval_summary("Device sample interval ms", device_summary))
    print(format_jitter_summary("Device sample jitter us", device_jitter_summary))
    print(format_interval_summary("Firmware acquisition duration ms", acquisition_summary))
    print(format_interval_summary("Firmware telemetry publish duration ms", telemetry_publish_summary))
    print(format_interval_summary("Firmware scheduler lateness ms", scheduler_lateness_summary))
    print(format_interval_summary("Firmware ADC total duration ms", adc_total_summary))
    print(format_interval_summary("Firmware differential pressure total duration ms", differential_pressure_total_summary))
    print(format_interval_summary("Firmware ADS ch0 duration ms", ads_ch0_summary))
    print(format_interval_summary("Firmware ADS ch1 duration ms", ads_ch1_summary))
    print(format_interval_summary("Firmware ADS ch2 duration ms", ads_ch2_summary))
    print(format_interval_summary("Firmware SDP low-range duration ms", sdp_low_summary))
    print(format_interval_summary("Firmware SDP high-range duration ms", sdp_high_summary))
    print(format_interval_summary("Firmware residual/wait interval ms", residual_summary))
    slow_samples.sort(key=lambda sample: float(sample["acquisition_ms"]), reverse=True)
    print(
        f"Slow acquisition samples >= {args.slow_threshold_ms:.3f} ms: "
        f"{len(slow_samples)}"
    )
    for sample in slow_samples[: max(0, args.slow_limit)]:
        print(
            "  "
            f"seq={sample['sequence']} "
            f"flags=0x{int(sample['status_flags']):08X} "
            f"acq={float(sample['acquisition_ms']):.3f}ms "
            f"adc={float(sample['adc_ms']):.3f}ms "
            f"dp={float(sample['dp_ms']):.3f}ms "
            f"ads0={float(sample['ads_ch0_ms']):.3f}ms "
            f"ads1={float(sample['ads_ch1_ms']):.3f}ms "
            f"ads2={float(sample['ads_ch2_ms']):.3f}ms "
            f"sdp_low={float(sample['sdp_low_ms']):.3f}ms "
            f"sdp_high={float(sample['sdp_high_ms']):.3f}ms "
            f"late={float(sample['lateness_ms']):.3f}ms"
        )
    print("Note: host read/decode intervals include USB/OS buffering and probe loop batching; use device sample interval for firmware cadence.")
    print("wired_timing_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
