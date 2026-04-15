from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


def default_profile_state() -> Dict[str, str]:
    return {
        "heater_profile_id": "unknown",
        "heater_profile_temp_c": "",
        "heater_profile_duration_mult": "",
        "heater_profile_time_base_ms": "",
    }


@dataclass
class SegmentState:
    segment_id: str
    label: str
    target_ppm: str
    start_iso: str
    start_elapsed: float
    end_iso: Optional[str] = None
    end_elapsed: Optional[float] = None


@dataclass
class ConnectionState:
    is_connected: bool = False
    last_selected_port: str = ""
    last_pong_iso: str = ""


@dataclass
class RecordingState:
    is_recording: bool = False
    current_segment: Optional[SegmentState] = None
    segment_counter: int = 0
    completed_segments: List[SegmentState] = field(default_factory=list)
    recording_path: Optional[Path] = None
    recording_temp_path: Optional[Path] = None
    pending_csv_rows: int = 0
    last_csv_flush_at: float = 0.0
    recording_glow_phase: float = 0.0


@dataclass
class PlotViewState:
    last_plot_time_ms: Optional[int] = None
    selected_span_seconds: Optional[float] = None
    selected_span_label: Optional[str] = "All"
    time_axis_mode: str = "relative"
    session_start_epoch: Optional[float] = None
    plot_dirty: bool = False
    suppress_span_reset_until: float = 0.0


@dataclass
class ProfileState:
    current: Dict[str, str] = field(default_factory=default_profile_state)
    presets: Dict[str, Dict[str, str]] = field(default_factory=dict)


@dataclass
class ProtocolState:
    capabilities: Dict[str, str] = field(default_factory=dict)


@dataclass
class AppState:
    connection: ConnectionState = field(default_factory=ConnectionState)
    recording: RecordingState = field(default_factory=RecordingState)
    plot: PlotViewState = field(default_factory=PlotViewState)
    profile: ProfileState = field(default_factory=ProfileState)
    protocol: ProtocolState = field(default_factory=ProtocolState)
