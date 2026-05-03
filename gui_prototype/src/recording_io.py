from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence, TextIO


FILE_FORMAT_ID = "zss_demokit_session_csv_v1"
CSV_COLUMNS = [
    "host_received_at_iso",
    "host_received_at_unix_ms",
    "mode",
    "transport_type",
    "sequence",
    "sequence_gap",
    "inter_arrival_ms",
    "host_inter_arrival_ms",
    "device_inter_arrival_ms",
    "device_sample_tick_us",
    "device_elapsed_s",
    "nominal_sample_period_ms",
    "status_flags_hex",
    "pump_state",
    "heater_power_state",
    "zirconia_output_voltage_v",
    "heater_rtd_resistance_ohm",
    "zirconia_ip_voltage_v",
    "internal_voltage_v",
    "differential_pressure_selected_pa",
    "differential_pressure_selected_source",
    "differential_pressure_low_range_pa",
    "differential_pressure_high_range_pa",
    "flow_rate_lpm",
]


@dataclass(frozen=True)
class RecordingPaths:
    recording_path: Path
    partial_path: Path


@dataclass(frozen=True)
class RecordingCsvSummary:
    path: Path
    row_count: int
    sequence_first: int | None
    sequence_last: int | None
    sequence_gap_total: int
    device_duration_s: float | None
    host_duration_s: float | None
    size_bytes: int

    @property
    def duration_s(self) -> float | None:
        return self.device_duration_s if self.device_duration_s is not None else self.host_duration_s

    def short_text(self) -> str:
        duration = "--" if self.duration_s is None else f"{self.duration_s:0.2f} s"
        size_kib = self.size_bytes / 1024.0
        sequence_range = (
            "--"
            if self.sequence_first is None or self.sequence_last is None
            else f"{self.sequence_first}->{self.sequence_last}"
        )
        return (
            f"Rows: {self.row_count} | Duration: {duration} | "
            f"Seq: {sequence_range} | Gaps: {self.sequence_gap_total} | "
            f"Size: {size_kib:0.1f} KiB"
        )


def recording_directory() -> Path:
    return Path.home() / "Documents" / "ZSS Demo Kit"


def create_recording_paths(base_dir: Path, now: datetime) -> RecordingPaths:
    filename_root = now.strftime("session_%Y%m%d_%H%M%S")
    recording_path = base_dir / f"{filename_root}.csv"
    suffix = 1
    while recording_path.exists() or recording_path.with_suffix(".partial.csv").exists():
        recording_path = base_dir / f"{filename_root}_{suffix:02d}.csv"
        suffix += 1
    return RecordingPaths(
        recording_path=recording_path,
        partial_path=recording_path.with_suffix(".partial.csv"),
    )


def write_csv_header(
    file_obj: TextIO,
    *,
    exported_at: datetime,
    gui_app_name: str,
    gui_app_version: str,
    session_id: str,
    mode: str,
    transport_type: str,
    device_type: str,
    device_identifier: str,
    firmware_version: str,
    protocol_version: str,
    nominal_sample_period_ms: str,
    derived_metric_policy: str,
    source_endpoint: str,
    notes: str = "",
) -> None:
    lines = [
        f"# file_format={FILE_FORMAT_ID}",
        f"# exported_at_iso={exported_at.astimezone().isoformat(timespec='seconds')}",
        f"# gui_app_name={gui_app_name}",
        f"# gui_app_version={gui_app_version}",
        f"# session_id={session_id}",
        f"# mode={mode}",
        f"# transport_type={transport_type}",
        f"# device_type={device_type}",
        f"# device_identifier={device_identifier}",
        f"# firmware_version={firmware_version}",
        f"# protocol_version={protocol_version}",
        f"# nominal_sample_period_ms={nominal_sample_period_ms}",
        f"# derived_metric_policy={derived_metric_policy}",
        f"# source_endpoint={source_endpoint}",
        f"# notes={notes}",
    ]
    file_obj.write("\n".join(lines) + "\n")
    file_obj.write(",".join(CSV_COLUMNS) + "\n")


def find_partial_recordings(base_dir: Path | None = None) -> list[Path]:
    target_dir = base_dir or recording_directory()
    if not target_dir.exists():
        return []
    return sorted(target_dir.glob("*.partial.csv"))


def summarize_partial_recordings(partials: Sequence[Path], limit: int = 5) -> str:
    if not partials:
        return "No unfinished session files were found."

    preview = "\n".join(f"- {path.name}" for path in partials[:limit])
    if len(partials) > limit:
        preview += f"\n- ... and {len(partials) - limit} more"
    return preview


def summarize_recording_csv(path: Path) -> RecordingCsvSummary:
    row_count = 0
    sequence_first: int | None = None
    sequence_last: int | None = None
    sequence_gap_total = 0
    first_host_received_at: datetime | None = None
    last_host_received_at: datetime | None = None
    latest_device_elapsed_s: float | None = None

    with path.open("r", newline="", encoding="utf-8") as file_obj:
        data_lines = (line for line in file_obj if line.strip() and not line.startswith("#"))
        reader = csv.DictReader(data_lines)
        for row in reader:
            row_count += 1
            sequence = _to_optional_int(row.get("sequence", ""))
            if sequence is not None:
                if sequence_first is None:
                    sequence_first = sequence
                sequence_last = sequence

            sequence_gap_total += max(0, _to_optional_int(row.get("sequence_gap", "")) or 0)

            device_elapsed_s = _to_optional_float(row.get("device_elapsed_s", ""))
            if device_elapsed_s is not None:
                latest_device_elapsed_s = device_elapsed_s

            host_received_at = _to_optional_datetime(row.get("host_received_at_iso", ""))
            if host_received_at is not None:
                if first_host_received_at is None:
                    first_host_received_at = host_received_at
                last_host_received_at = host_received_at

    host_duration_s = None
    if first_host_received_at is not None and last_host_received_at is not None:
        host_duration_s = max(0.0, (last_host_received_at - first_host_received_at).total_seconds())

    return RecordingCsvSummary(
        path=path,
        row_count=row_count,
        sequence_first=sequence_first,
        sequence_last=sequence_last,
        sequence_gap_total=sequence_gap_total,
        device_duration_s=latest_device_elapsed_s,
        host_duration_s=host_duration_s,
        size_bytes=path.stat().st_size if path.exists() else 0,
    )


def _to_optional_int(value: object) -> int | None:
    if value in {"", None}:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _to_optional_float(value: object) -> float | None:
    if value in {"", None}:
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _to_optional_datetime(value: object) -> datetime | None:
    if value in {"", None}:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
