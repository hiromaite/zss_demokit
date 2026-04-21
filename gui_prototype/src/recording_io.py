from __future__ import annotations

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
    "nominal_sample_period_ms",
    "status_flags_hex",
    "pump_state",
    "zirconia_output_voltage_v",
    "heater_rtd_resistance_ohm",
    "differential_pressure_selected_pa",
    "differential_pressure_low_range_pa",
    "differential_pressure_high_range_pa",
    "flow_rate_lpm",
]


@dataclass(frozen=True)
class RecordingPaths:
    recording_path: Path
    partial_path: Path


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
