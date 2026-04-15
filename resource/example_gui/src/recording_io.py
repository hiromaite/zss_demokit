from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Sequence, TextIO

from app_state import SegmentState


@dataclass(frozen=True)
class RecordingPaths:
    recording_path: Path
    partial_path: Path


def recording_directory() -> Path:
    return Path("data")


def create_recording_paths(base_dir: Path, now: datetime) -> RecordingPaths:
    filename = now.strftime("session_%Y%m%d_%H%M%S.csv")
    recording_path = base_dir / filename
    return RecordingPaths(
        recording_path=recording_path,
        partial_path=recording_path.with_suffix(".partial.csv"),
    )


def write_csv_header(
    file_obj: TextIO,
    *,
    exported_at: datetime,
    app_name: str,
    app_version: str,
    operator_id: str,
    serial_port: str,
    profile_state: Dict[str, str],
) -> None:
    lines = [
        "# file_format=h2s_benchmark_csv_v1",
        f"# exported_at_iso={exported_at.astimezone().isoformat(timespec='seconds')}",
        f"# gui_app_name={app_name}",
        f"# gui_app_version={app_version}",
        f"# operator_id={operator_id}",
        f"# session_id={exported_at.strftime('%Y%m%d_%H%M%S_run01')}",
        "# gui_git_commit=working_tree",
        "# board_type=M5StampS3",
        "# sensor_type=BME688",
        f"# serial_port={serial_port}",
        f"# heater_profile_id={profile_state.get('heater_profile_id', 'unknown')}",
        f"# heater_profile_temp_c={profile_state.get('heater_profile_temp_c', '')}",
        f"# heater_profile_duration_mult={profile_state.get('heater_profile_duration_mult', '')}",
        f"# heater_profile_time_base_ms={profile_state.get('heater_profile_time_base_ms', '')}",
        "# label_target_gas=H2S",
        "# label_unit=ppm",
        "# label_scope=exposure_segment",
        "# notes=",
    ]
    file_obj.write("\n".join(lines) + "\n")


def segment_export_fields(segment: Optional[SegmentState]) -> Dict[str, str]:
    if segment is None:
        return {
            "segment_id": "",
            "segment_label": "",
            "segment_target_ppm": "",
            "segment_start_iso": "",
            "segment_end_iso": "",
        }
    return {
        "segment_id": segment.segment_id,
        "segment_label": segment.label,
        "segment_target_ppm": segment.target_ppm,
        "segment_start_iso": segment.start_iso,
        "segment_end_iso": segment.end_iso or "",
    }


def find_partial_recordings(base_dir: Optional[Path] = None) -> list[Path]:
    data_dir = base_dir or recording_directory()
    if not data_dir.exists():
        return []
    return sorted(data_dir.glob("*.partial.csv"))


def summarize_partial_recordings(partials: Sequence[Path], limit: int = 5) -> str:
    preview = "\n".join(f"- {path.name}" for path in partials[:limit])
    if len(partials) > limit:
        preview += f"\n- ... and {len(partials) - limit} more"
    return preview
