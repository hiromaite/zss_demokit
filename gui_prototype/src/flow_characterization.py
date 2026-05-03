from __future__ import annotations

import csv
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from mock_backend import TelemetryPoint
from protocol_constants import (
    derive_flow_rate_lpm_from_selected_differential_pressure_pa,
    infer_differential_pressure_selected_source,
)


FLOW_CHARACTERIZATION_CRITERION_VERSION = "flow_characterization_v1_poc"
FLOW_ROUGH_SCALE_POLICY_ID = "rough_lung_capacity_order_v1"
FLOW_ROUGH_SCALE_DEFAULT_TARGET_VOLUME_L = 4.5
SDP810_NOMINAL_RANGE_PA = 125.0
SDP810_REVIEW_HANDOFF_LOWER_PA = 90.0
SDP810_REVIEW_HANDOFF_UPPER_PA = 110.0


@dataclass(frozen=True)
class FlowCharacterizationStep:
    step_id: str
    title: str
    section: str
    instruction: str
    kind: str
    direction: str = ""
    intensity: str = ""


FLOW_CHARACTERIZATION_STEPS: tuple[FlowCharacterizationStep, ...] = (
    FlowCharacterizationStep(
        step_id="overview",
        title="Flow Characterization PoC",
        section="Overview",
        instruction=(
            "This development workflow records raw SDP810 / SDP811 response while the operator "
            "performs inhale and exhale maneuvers. Use wired mode when possible so both raw "
            "differential pressure channels are available."
        ),
        kind="overview",
    ),
    FlowCharacterizationStep(
        step_id="zero_baseline",
        title="Zero Baseline",
        section="Baseline",
        instruction=(
            "Keep the flow path still. Start capture, wait a few seconds, then finish the step. "
            "This establishes the no-flow offset and raw channel noise floor."
        ),
        kind="capture",
        direction="zero",
        intensity="baseline",
    ),
    FlowCharacterizationStep(
        step_id="small_exhale",
        title="Small Exhale",
        section="Gentle Flow",
        instruction=(
            "Start capture, then exhale gently and continuously. Finish the step after the "
            "small exhale is complete."
        ),
        kind="capture",
        direction="exhalation",
        intensity="small",
    ),
    FlowCharacterizationStep(
        step_id="small_inhale",
        title="Small Inhale",
        section="Gentle Flow",
        instruction=(
            "Start capture, then inhale gently and continuously. Finish the step after the "
            "small inhale is complete."
        ),
        kind="capture",
        direction="inhalation",
        intensity="small",
    ),
    FlowCharacterizationStep(
        step_id="max_exhale",
        title="Maximum Exhale",
        section="Maximum Flow",
        instruction=(
            "Start capture, then exhale as strongly as practical and keep exhaling until done. "
            "Press Finish Step after the maneuver ends."
        ),
        kind="capture",
        direction="exhalation",
        intensity="maximum",
    ),
    FlowCharacterizationStep(
        step_id="max_inhale",
        title="Maximum Inhale",
        section="Maximum Flow",
        instruction=(
            "Start capture, then inhale as strongly as practical and keep inhaling until done. "
            "Press Finish Step after the maneuver ends."
        ),
        kind="capture",
        direction="inhalation",
        intensity="maximum",
    ),
    FlowCharacterizationStep(
        step_id="review",
        title="Review Characterization",
        section="Review",
        instruction=(
            "Review the captured raw response. Save the session to write JSON metadata and a "
            "CSV sample table for threshold and polarity analysis."
        ),
        kind="review",
    ),
)


FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS = tuple(
    step.step_id for step in FLOW_CHARACTERIZATION_STEPS if step.kind == "capture"
)


@dataclass
class FlowCharacterizationSample:
    host_received_at_iso: str
    sequence: int
    elapsed_ms: int
    nominal_sample_period_ms: int
    status_flags: int
    selected_dp_pa: float | None
    sdp810_pa: float | None
    sdp811_pa: float | None
    selected_source: str
    derived_flow_lpm: float
    zirconia_output_voltage_v: float
    heater_rtd_resistance_ohm: float
    zirconia_ip_voltage_v: float | None
    internal_voltage_v: float | None
    device_sample_tick_us: int | None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FlowCharacterizationSample":
        return cls(
            host_received_at_iso=str(payload.get("host_received_at_iso", "")),
            sequence=int(payload.get("sequence", 0)),
            elapsed_ms=int(payload.get("elapsed_ms", 0)),
            nominal_sample_period_ms=int(payload.get("nominal_sample_period_ms", 0)),
            status_flags=int(payload.get("status_flags", 0)),
            selected_dp_pa=_optional_float(payload.get("selected_dp_pa")),
            sdp810_pa=_optional_float(payload.get("sdp810_pa")),
            sdp811_pa=_optional_float(payload.get("sdp811_pa")),
            selected_source=str(payload.get("selected_source", "")),
            derived_flow_lpm=float(payload.get("derived_flow_lpm", 0.0)),
            zirconia_output_voltage_v=float(payload.get("zirconia_output_voltage_v", 0.0)),
            heater_rtd_resistance_ohm=float(payload.get("heater_rtd_resistance_ohm", 0.0)),
            zirconia_ip_voltage_v=_optional_float(payload.get("zirconia_ip_voltage_v")),
            internal_voltage_v=_optional_float(payload.get("internal_voltage_v")),
            device_sample_tick_us=(
                int(payload["device_sample_tick_us"])
                if payload.get("device_sample_tick_us") is not None
                else None
            ),
        )


@dataclass
class FlowCharacterizationAttemptSummary:
    sample_count: int
    duration_s: float
    selected_mean_pa: float | None
    selected_min_pa: float | None
    selected_max_pa: float | None
    selected_peak_abs_pa: float | None
    selected_polarity: str
    sdp810_mean_pa: float | None
    sdp810_min_pa: float | None
    sdp810_max_pa: float | None
    sdp810_peak_abs_pa: float | None
    sdp810_polarity: str
    sdp811_mean_pa: float | None
    sdp811_min_pa: float | None
    sdp811_max_pa: float | None
    sdp811_peak_abs_pa: float | None
    sdp811_polarity: str
    source_counts: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FlowCharacterizationAttemptSummary":
        source_counts_payload = payload.get("source_counts", {})
        if not isinstance(source_counts_payload, dict):
            source_counts_payload = {}
        return cls(
            sample_count=int(payload.get("sample_count", 0)),
            duration_s=float(payload.get("duration_s", 0.0)),
            selected_mean_pa=_optional_float(payload.get("selected_mean_pa")),
            selected_min_pa=_optional_float(payload.get("selected_min_pa")),
            selected_max_pa=_optional_float(payload.get("selected_max_pa")),
            selected_peak_abs_pa=_optional_float(payload.get("selected_peak_abs_pa")),
            selected_polarity=str(payload.get("selected_polarity", "")),
            sdp810_mean_pa=_optional_float(payload.get("sdp810_mean_pa")),
            sdp810_min_pa=_optional_float(payload.get("sdp810_min_pa")),
            sdp810_max_pa=_optional_float(payload.get("sdp810_max_pa")),
            sdp810_peak_abs_pa=_optional_float(payload.get("sdp810_peak_abs_pa")),
            sdp810_polarity=str(payload.get("sdp810_polarity", "")),
            sdp811_mean_pa=_optional_float(payload.get("sdp811_mean_pa")),
            sdp811_min_pa=_optional_float(payload.get("sdp811_min_pa")),
            sdp811_max_pa=_optional_float(payload.get("sdp811_max_pa")),
            sdp811_peak_abs_pa=_optional_float(payload.get("sdp811_peak_abs_pa")),
            sdp811_polarity=str(payload.get("sdp811_polarity", "")),
            source_counts={
                str(key): int(value)
                for key, value in source_counts_payload.items()
            },
        )


@dataclass
class FlowRoughScaleEstimate:
    policy_id: str
    target_volume_l: float
    max_exhale_measured_volume_l: float | None
    max_inhale_measured_volume_l: float | None
    exhale_gain_multiplier: float | None
    inhale_gain_multiplier: float | None
    recommended_gain_multiplier: float | None
    confidence: str
    source_step_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FlowRoughScaleEstimate":
        target_volume_l = _optional_float(payload.get("target_volume_l"))
        return cls(
            policy_id=str(payload.get("policy_id", FLOW_ROUGH_SCALE_POLICY_ID)),
            target_volume_l=target_volume_l or FLOW_ROUGH_SCALE_DEFAULT_TARGET_VOLUME_L,
            max_exhale_measured_volume_l=_optional_float(payload.get("max_exhale_measured_volume_l")),
            max_inhale_measured_volume_l=_optional_float(payload.get("max_inhale_measured_volume_l")),
            exhale_gain_multiplier=_optional_float(payload.get("exhale_gain_multiplier")),
            inhale_gain_multiplier=_optional_float(payload.get("inhale_gain_multiplier")),
            recommended_gain_multiplier=_optional_float(payload.get("recommended_gain_multiplier")),
            confidence=str(payload.get("confidence", "unavailable")),
            source_step_ids=[str(value) for value in payload.get("source_step_ids", [])],
            notes=[str(value) for value in payload.get("notes", [])],
        )


@dataclass
class FlowCharacterizationAttempt:
    step_id: str
    step_title: str
    direction: str
    intensity: str
    attempt_index: int
    started_at_iso: str
    completed_at_iso: str
    operator_event: str
    sample_count: int
    duration_s: float
    summary: FlowCharacterizationAttemptSummary | None
    samples: list[FlowCharacterizationSample] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FlowCharacterizationAttempt":
        summary_payload = payload.get("summary")
        sample_payloads = payload.get("samples", [])
        return cls(
            step_id=str(payload.get("step_id", "")),
            step_title=str(payload.get("step_title", "")),
            direction=str(payload.get("direction", "")),
            intensity=str(payload.get("intensity", "")),
            attempt_index=int(payload.get("attempt_index", 0)),
            started_at_iso=str(payload.get("started_at_iso", "")),
            completed_at_iso=str(payload.get("completed_at_iso", "")),
            operator_event=str(payload.get("operator_event", "")),
            sample_count=int(payload.get("sample_count", 0)),
            duration_s=float(payload.get("duration_s", 0.0)),
            summary=(
                FlowCharacterizationAttemptSummary.from_dict(summary_payload)
                if isinstance(summary_payload, dict)
                else None
            ),
            samples=[
                FlowCharacterizationSample.from_dict(item)
                for item in sample_payloads
                if isinstance(item, dict)
            ],
        )


@dataclass
class FlowCharacterizationAnalysis:
    completed_capture_steps: int
    missing_step_ids: list[str]
    polarity_hint: str
    low_high_sign_consistency: str
    selected_peak_abs_pa: float | None
    low_range_peak_abs_pa: float | None
    high_range_peak_abs_pa: float | None
    review_handoff_lower_pa: float | None
    review_handoff_upper_pa: float | None
    rough_scale_estimate: FlowRoughScaleEstimate | None = None
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FlowCharacterizationAnalysis":
        return cls(
            completed_capture_steps=int(payload.get("completed_capture_steps", 0)),
            missing_step_ids=[str(value) for value in payload.get("missing_step_ids", [])],
            polarity_hint=str(payload.get("polarity_hint", "")),
            low_high_sign_consistency=str(payload.get("low_high_sign_consistency", "")),
            selected_peak_abs_pa=_optional_float(payload.get("selected_peak_abs_pa")),
            low_range_peak_abs_pa=_optional_float(payload.get("low_range_peak_abs_pa")),
            high_range_peak_abs_pa=_optional_float(payload.get("high_range_peak_abs_pa")),
            review_handoff_lower_pa=_optional_float(payload.get("review_handoff_lower_pa")),
            review_handoff_upper_pa=_optional_float(payload.get("review_handoff_upper_pa")),
            rough_scale_estimate=(
                FlowRoughScaleEstimate.from_dict(payload["rough_scale_estimate"])
                if isinstance(payload.get("rough_scale_estimate"), dict)
                else None
            ),
            notes=[str(value) for value in payload.get("notes", [])],
        )


@dataclass
class FlowCharacterizationSession:
    session_id: str
    started_at_iso: str
    completed_at_iso: str
    status: str
    transport_type: str
    mode: str
    device_identifier: str
    firmware_version: str
    protocol_version: str
    criterion_version: str
    operator_note: str
    attempts: list[FlowCharacterizationAttempt]
    analysis: FlowCharacterizationAnalysis | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "FlowCharacterizationSession":
        analysis_payload = payload.get("analysis")
        attempt_payloads = payload.get("attempts", [])
        return cls(
            session_id=str(payload.get("session_id", "")),
            started_at_iso=str(payload.get("started_at_iso", "")),
            completed_at_iso=str(payload.get("completed_at_iso", "")),
            status=str(payload.get("status", "")),
            transport_type=str(payload.get("transport_type", "")),
            mode=str(payload.get("mode", "")),
            device_identifier=str(payload.get("device_identifier", "")),
            firmware_version=str(payload.get("firmware_version", "")),
            protocol_version=str(payload.get("protocol_version", "")),
            criterion_version=str(payload.get("criterion_version", "")),
            operator_note=str(payload.get("operator_note", "")),
            attempts=[
                FlowCharacterizationAttempt.from_dict(item)
                for item in attempt_payloads
                if isinstance(item, dict)
            ],
            analysis=(
                FlowCharacterizationAnalysis.from_dict(analysis_payload)
                if isinstance(analysis_payload, dict)
                else None
            ),
        )


@dataclass(frozen=True)
class FlowCharacterizationSaveResult:
    json_path: Path
    csv_path: Path


@dataclass(frozen=True)
class FlowCharacterizationLatestSummary:
    session_id: str
    status: str
    completed_at_iso: str
    criterion_version: str
    path: str
    csv_path: str
    completed_capture_steps: int
    missing_step_count: int
    polarity_hint: str
    low_high_sign_consistency: str
    selected_peak_abs_pa: float | None
    sdp810_peak_abs_pa: float | None
    sdp811_peak_abs_pa: float | None
    rough_gain_multiplier: float | None
    rough_gain_confidence: str
    note_preview: str


class FlowCharacterizationPersistence:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir / "flow_characterization"

    def save_session(self, session: FlowCharacterizationSession) -> FlowCharacterizationSaveResult:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        json_path = self._base_dir / f"{session.session_id}.json"
        csv_path = self._base_dir / f"{session.session_id}_samples.csv"
        json_path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
        self._write_samples_csv(session, csv_path)
        return FlowCharacterizationSaveResult(json_path=json_path, csv_path=csv_path)

    def load_latest_session(self) -> FlowCharacterizationSession | None:
        return self.load_session(self._latest_path())

    def load_latest_summary(self) -> FlowCharacterizationLatestSummary | None:
        path = self._latest_path()
        session = self.load_session(path)
        if session is None:
            return None
        return self._build_summary(session, path)

    def load_session(self, path: Path | None) -> FlowCharacterizationSession | None:
        if path is None:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return FlowCharacterizationSession.from_dict(payload)

    def list_recent_summaries(self, *, limit: int = 5) -> list[FlowCharacterizationLatestSummary]:
        summaries: list[FlowCharacterizationLatestSummary] = []
        for path in reversed(self._candidate_paths()):
            session = self.load_session(path)
            if session is None:
                continue
            summaries.append(self._build_summary(session, path))
            if len(summaries) >= limit:
                break
        return summaries

    def export_summary_csv(self, path: Path, summaries: list[FlowCharacterizationLatestSummary]) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "session_id",
            "completed_at_iso",
            "status",
            "criterion_version",
            "completed_capture_steps",
            "missing_step_count",
            "polarity_hint",
            "low_high_sign_consistency",
            "selected_peak_abs_pa",
            "sdp810_peak_abs_pa",
            "sdp811_peak_abs_pa",
            "rough_gain_multiplier",
            "rough_gain_confidence",
            "path",
            "csv_path",
            "note_preview",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for summary in summaries:
                writer.writerow(
                    {
                        "session_id": summary.session_id,
                        "completed_at_iso": summary.completed_at_iso,
                        "status": summary.status,
                        "criterion_version": summary.criterion_version,
                        "completed_capture_steps": summary.completed_capture_steps,
                        "missing_step_count": summary.missing_step_count,
                        "polarity_hint": summary.polarity_hint,
                        "low_high_sign_consistency": summary.low_high_sign_consistency,
                        "selected_peak_abs_pa": _csv_float(summary.selected_peak_abs_pa),
                        "sdp810_peak_abs_pa": _csv_float(summary.sdp810_peak_abs_pa),
                        "sdp811_peak_abs_pa": _csv_float(summary.sdp811_peak_abs_pa),
                        "rough_gain_multiplier": _csv_float(summary.rough_gain_multiplier),
                        "rough_gain_confidence": summary.rough_gain_confidence,
                        "path": summary.path,
                        "csv_path": summary.csv_path,
                        "note_preview": summary.note_preview,
                    }
                )
        return path

    def _build_summary(
        self,
        session: FlowCharacterizationSession,
        path: Path | None,
    ) -> FlowCharacterizationLatestSummary:
        analysis = session.analysis or analyze_flow_characterization_session(session)
        estimate = analysis.rough_scale_estimate
        note_preview = " ".join(session.operator_note.split())
        if len(note_preview) > 96:
            note_preview = f"{note_preview[:93]}..."
        json_path = path or self._base_dir / f"{session.session_id}.json"
        csv_path = json_path.with_name(f"{session.session_id}_samples.csv")
        return FlowCharacterizationLatestSummary(
            session_id=session.session_id,
            status=session.status or "unknown",
            completed_at_iso=session.completed_at_iso,
            criterion_version=session.criterion_version,
            path=str(json_path),
            csv_path=str(csv_path),
            completed_capture_steps=analysis.completed_capture_steps,
            missing_step_count=len(analysis.missing_step_ids),
            polarity_hint=analysis.polarity_hint,
            low_high_sign_consistency=analysis.low_high_sign_consistency,
            selected_peak_abs_pa=analysis.selected_peak_abs_pa,
            sdp810_peak_abs_pa=analysis.low_range_peak_abs_pa,
            sdp811_peak_abs_pa=analysis.high_range_peak_abs_pa,
            rough_gain_multiplier=None if estimate is None else estimate.recommended_gain_multiplier,
            rough_gain_confidence="" if estimate is None else estimate.confidence,
            note_preview=note_preview,
        )

    def _latest_path(self) -> Path | None:
        candidates = self._candidate_paths()
        if not candidates:
            return None
        return candidates[-1]

    def _candidate_paths(self) -> list[Path]:
        if not self._base_dir.exists():
            return []
        return sorted(self._base_dir.glob("flow_characterization_*.json"))

    def _write_samples_csv(self, session: FlowCharacterizationSession, path: Path) -> None:
        fieldnames = [
            "session_id",
            "session_started_at_iso",
            "session_completed_at_iso",
            "mode",
            "transport_type",
            "device_identifier",
            "step_id",
            "step_title",
            "direction",
            "intensity",
            "attempt_index",
            "operator_event",
            "attempt_started_at_iso",
            "attempt_completed_at_iso",
            "sample_index",
            "host_received_at_iso",
            "elapsed_ms",
            "sequence",
            "nominal_sample_period_ms",
            "status_flags_hex",
            "selected_dp_pa",
            "selected_source",
            "sdp810_pa",
            "sdp811_pa",
            "derived_flow_lpm",
            "zirconia_output_voltage_v",
            "heater_rtd_resistance_ohm",
            "zirconia_ip_voltage_v",
            "internal_voltage_v",
            "device_sample_tick_us",
        ]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for attempt in session.attempts:
                if not attempt.samples:
                    writer.writerow(self._csv_attempt_row(session, attempt, sample=None, sample_index=None))
                    continue
                for sample_index, sample in enumerate(attempt.samples, start=1):
                    writer.writerow(self._csv_attempt_row(session, attempt, sample=sample, sample_index=sample_index))

    @staticmethod
    def _csv_attempt_row(
        session: FlowCharacterizationSession,
        attempt: FlowCharacterizationAttempt,
        *,
        sample: FlowCharacterizationSample | None,
        sample_index: int | None,
    ) -> dict[str, object]:
        row: dict[str, object] = {
            "session_id": session.session_id,
            "session_started_at_iso": session.started_at_iso,
            "session_completed_at_iso": session.completed_at_iso,
            "mode": session.mode,
            "transport_type": session.transport_type,
            "device_identifier": session.device_identifier,
            "step_id": attempt.step_id,
            "step_title": attempt.step_title,
            "direction": attempt.direction,
            "intensity": attempt.intensity,
            "attempt_index": attempt.attempt_index,
            "operator_event": attempt.operator_event,
            "attempt_started_at_iso": attempt.started_at_iso,
            "attempt_completed_at_iso": attempt.completed_at_iso,
            "sample_index": sample_index if sample_index is not None else "",
        }
        if sample is None:
            row.update(
                {
                    "host_received_at_iso": "",
                    "elapsed_ms": "",
                    "sequence": "",
                    "nominal_sample_period_ms": "",
                    "status_flags_hex": "",
                    "selected_dp_pa": "",
                    "selected_source": "",
                    "sdp810_pa": "",
                    "sdp811_pa": "",
                    "derived_flow_lpm": "",
                    "zirconia_output_voltage_v": "",
                    "heater_rtd_resistance_ohm": "",
                    "zirconia_ip_voltage_v": "",
                    "internal_voltage_v": "",
                    "device_sample_tick_us": "",
                }
            )
            return row
        row.update(
            {
                "host_received_at_iso": sample.host_received_at_iso,
                "elapsed_ms": sample.elapsed_ms,
                "sequence": sample.sequence,
                "nominal_sample_period_ms": sample.nominal_sample_period_ms,
                "status_flags_hex": f"0x{sample.status_flags:08X}",
                "selected_dp_pa": _csv_float(sample.selected_dp_pa),
                "selected_source": sample.selected_source,
                "sdp810_pa": _csv_float(sample.sdp810_pa),
                "sdp811_pa": _csv_float(sample.sdp811_pa),
                "derived_flow_lpm": _csv_float(sample.derived_flow_lpm),
                "zirconia_output_voltage_v": _csv_float(sample.zirconia_output_voltage_v),
                "heater_rtd_resistance_ohm": _csv_float(sample.heater_rtd_resistance_ohm),
                "zirconia_ip_voltage_v": _csv_float(sample.zirconia_ip_voltage_v),
                "internal_voltage_v": _csv_float(sample.internal_voltage_v),
                "device_sample_tick_us": (
                    sample.device_sample_tick_us if sample.device_sample_tick_us is not None else ""
                ),
            }
        )
        return row


def compare_characterization_summaries(
    current: FlowCharacterizationLatestSummary,
    previous: FlowCharacterizationLatestSummary | None,
) -> list[str]:
    if previous is None:
        return ["No older characterization session is available for comparison."]

    lines = [
        f"Compared with {previous.completed_at_iso or previous.session_id}:",
        f"Status: {previous.status} -> {current.status}",
        (
            "Completed captures: "
            f"{previous.completed_capture_steps}/{len(FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)} -> "
            f"{current.completed_capture_steps}/{len(FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)}"
        ),
        f"Polarity hint: {previous.polarity_hint} -> {current.polarity_hint}",
        f"Low/high consistency: {previous.low_high_sign_consistency} -> {current.low_high_sign_consistency}",
    ]
    if current.selected_peak_abs_pa is not None and previous.selected_peak_abs_pa is not None:
        delta = current.selected_peak_abs_pa - previous.selected_peak_abs_pa
        lines.append(
            "Selected peak abs: "
            f"{previous.selected_peak_abs_pa:0.3f} Pa -> {current.selected_peak_abs_pa:0.3f} Pa "
            f"({delta:+0.3f} Pa)"
        )
    if current.rough_gain_multiplier is not None and previous.rough_gain_multiplier is not None:
        delta = current.rough_gain_multiplier - previous.rough_gain_multiplier
        lines.append(
            "Rough gain multiplier: "
            f"{previous.rough_gain_multiplier:0.3f}x -> {current.rough_gain_multiplier:0.3f}x "
            f"({delta:+0.3f}x)"
        )
    return lines


class FlowCharacterizationController(QObject):
    updated = Signal()
    session_saved = Signal(object)

    def __init__(
        self,
        *,
        mode: str,
        transport_type: str,
        device_identifier: str,
        firmware_version: str,
        protocol_version: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.transport_type = transport_type
        self.device_identifier = device_identifier
        self.firmware_version = firmware_version
        self.protocol_version = protocol_version
        self.session_id = f"flow_characterization_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.started_at = datetime.now()
        self.operator_note = ""
        self.device_connected = True
        self.current_identifier = device_identifier

        self.step_index = 0
        self.capture_state = "not_armed"
        self.latest_message = FLOW_CHARACTERIZATION_STEPS[0].instruction
        self.live_selected_source = ""
        self.live_selected_dp_pa: float | None = None
        self.live_low_range_pa: float | None = None
        self.live_high_range_pa: float | None = None
        self.live_flow_lpm: float | None = None
        self.live_received_at: datetime | None = None

        self.attempts: list[FlowCharacterizationAttempt] = []
        self._attempt_counts: dict[str, int] = {}
        self._current_attempt: FlowCharacterizationAttempt | None = None
        self._capture_started_at: datetime | None = None

    @property
    def current_step(self) -> FlowCharacterizationStep:
        return FLOW_CHARACTERIZATION_STEPS[self.step_index]

    def on_connection_changed(self, connected: bool, identifier: str) -> None:
        self.device_connected = connected
        self.current_identifier = identifier
        if not connected:
            self.latest_message = "Device disconnected. Existing captures can still be saved."
        self.updated.emit()

    def on_telemetry(self, point: TelemetryPoint) -> None:
        self.live_selected_dp_pa = point.differential_pressure_selected_pa
        self.live_low_range_pa = point.differential_pressure_low_range_pa
        self.live_high_range_pa = point.differential_pressure_high_range_pa
        self.live_flow_lpm = derive_flow_rate_lpm_from_selected_differential_pressure_pa(
            point.differential_pressure_selected_pa
        )
        self.live_selected_source = infer_differential_pressure_selected_source(
            point.differential_pressure_selected_pa,
            point.differential_pressure_low_range_pa,
            point.differential_pressure_high_range_pa,
        )
        self.live_received_at = point.host_received_at

        if self.current_step.kind == "capture" and self.capture_state == "capturing":
            self._append_current_sample(point)

        self.updated.emit()

    def go_back(self) -> None:
        if self.step_index <= 0 or self.capture_state == "capturing":
            return
        self.step_index -= 1
        self._restore_step_runtime()
        self.updated.emit()

    def continue_step(self) -> None:
        step = self.current_step
        if step.kind == "overview":
            self._advance_to_next_step()
            return
        if step.kind == "capture":
            if self._latest_attempt_for_step(step.step_id) is None:
                return
            self._advance_to_next_step()

    def start_capture(self) -> None:
        step = self.current_step
        if step.kind != "capture":
            return
        if self.capture_state == "capturing":
            return
        if not self.device_connected:
            self.latest_message = "Connect to the device before starting a new capture."
            self.updated.emit()
            return

        attempt_index = self._attempt_counts.get(step.step_id, 0) + 1
        self._attempt_counts[step.step_id] = attempt_index
        now = datetime.now()
        self._capture_started_at = now
        self._current_attempt = FlowCharacterizationAttempt(
            step_id=step.step_id,
            step_title=step.title,
            direction=step.direction,
            intensity=step.intensity,
            attempt_index=attempt_index,
            started_at_iso=now.isoformat(timespec="milliseconds"),
            completed_at_iso="",
            operator_event="capturing",
            sample_count=0,
            duration_s=0.0,
            summary=None,
            samples=[],
        )
        self.capture_state = "capturing"
        self.latest_message = "Capturing raw differential pressure samples."
        self.updated.emit()

    def finish_capture(self) -> None:
        if self.capture_state != "capturing" or self._current_attempt is None:
            return
        now = self.live_received_at or datetime.now()
        attempt = self._current_attempt
        summary = summarize_attempt_samples(attempt.samples)
        attempt.completed_at_iso = now.isoformat(timespec="milliseconds")
        attempt.operator_event = "finish_button"
        attempt.sample_count = len(attempt.samples)
        attempt.duration_s = _duration_between_iso(attempt.started_at_iso, attempt.completed_at_iso)
        if summary.duration_s <= 0.0:
            summary.duration_s = attempt.duration_s
        attempt.summary = summary
        self.attempts.append(attempt)
        self._current_attempt = None
        self._capture_started_at = None
        self.capture_state = "captured"
        self.latest_message = self._attempt_message(attempt)
        self.updated.emit()

    def retry_step(self) -> None:
        step = self.current_step
        if step.kind != "capture" or self.capture_state == "capturing":
            return
        self._current_attempt = None
        self._capture_started_at = None
        self.capture_state = "ready"
        self.latest_message = "Ready for another capture attempt. Previous attempts remain in the saved session."
        self.updated.emit()

    def skip_step(self) -> None:
        step = self.current_step
        if step.kind != "capture" or self.capture_state == "capturing":
            return
        attempt_index = self._attempt_counts.get(step.step_id, 0) + 1
        self._attempt_counts[step.step_id] = attempt_index
        now = datetime.now().isoformat(timespec="milliseconds")
        self.attempts.append(
            FlowCharacterizationAttempt(
                step_id=step.step_id,
                step_title=step.title,
                direction=step.direction,
                intensity=step.intensity,
                attempt_index=attempt_index,
                started_at_iso=now,
                completed_at_iso=now,
                operator_event="skipped",
                sample_count=0,
                duration_s=0.0,
                summary=summarize_attempt_samples([]),
                samples=[],
            )
        )
        self.capture_state = "skipped"
        self.latest_message = "Step skipped."
        self._advance_to_next_step()

    def set_operator_note(self, note: str) -> None:
        self.operator_note = note.strip()

    def save_session(self, persistence: FlowCharacterizationPersistence) -> FlowCharacterizationSaveResult:
        completed_step_ids = {
            attempt.step_id
            for attempt in self.attempts
            if attempt.operator_event != "skipped" and attempt.sample_count > 0
        }
        status = (
            "completed"
            if all(step_id in completed_step_ids for step_id in FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)
            else "partial"
        )
        session = FlowCharacterizationSession(
            session_id=self.session_id,
            started_at_iso=self.started_at.isoformat(timespec="seconds"),
            completed_at_iso=datetime.now().isoformat(timespec="seconds"),
            status=status,
            transport_type=self.transport_type,
            mode=self.mode,
            device_identifier=self.current_identifier or self.device_identifier,
            firmware_version=self.firmware_version,
            protocol_version=self.protocol_version,
            criterion_version=FLOW_CHARACTERIZATION_CRITERION_VERSION,
            operator_note=self.operator_note,
            attempts=list(self.attempts),
            analysis=None,
        )
        session.analysis = analyze_flow_characterization_session(session)
        result = persistence.save_session(session)
        self.session_saved.emit(result)
        return result

    def snapshot(self) -> dict[str, Any]:
        step = self.current_step
        latest_attempt = self._latest_attempt_for_step(step.step_id) if step.kind == "capture" else None
        current_attempt = self._current_attempt if self.capture_state == "capturing" else latest_attempt
        current_summary = None if current_attempt is None else current_attempt.summary
        if self.capture_state == "capturing" and self._current_attempt is not None:
            current_summary = summarize_attempt_samples(self._current_attempt.samples)

        analysis = analyze_flow_characterization_session(self._session_preview())
        review_rows = []
        for review_step in FLOW_CHARACTERIZATION_STEPS:
            if review_step.kind != "capture":
                continue
            attempt = self._latest_attempt_for_step(review_step.step_id)
            summary = None if attempt is None else attempt.summary
            review_rows.append(
                {
                    "step_id": review_step.step_id,
                    "label": review_step.title,
                    "status": _attempt_status(attempt),
                    "sample_count": None if attempt is None else attempt.sample_count,
                    "selected_peak_abs_pa": None if summary is None else summary.selected_peak_abs_pa,
                    "sdp810_peak_abs_pa": None if summary is None else summary.sdp810_peak_abs_pa,
                    "sdp811_peak_abs_pa": None if summary is None else summary.sdp811_peak_abs_pa,
                    "polarity": "" if summary is None else summary.selected_polarity,
                }
            )

        return {
            "session_id": self.session_id,
            "step_index": self.step_index + 1,
            "step_total": len(FLOW_CHARACTERIZATION_STEPS),
            "step": step,
            "capture_state": self.capture_state,
            "message": self._current_message(),
            "device_connected": self.device_connected,
            "live_flow_lpm": self.live_flow_lpm,
            "live_selected_source": self.live_selected_source,
            "live_selected_dp_pa": self.live_selected_dp_pa,
            "live_low_range_pa": self.live_low_range_pa,
            "live_high_range_pa": self.live_high_range_pa,
            "current_attempt": current_attempt,
            "current_summary": current_summary,
            "capturing_sample_count": 0 if self._current_attempt is None else len(self._current_attempt.samples),
            "review_rows": review_rows,
            "analysis": analysis,
            "analysis_lines": format_flow_characterization_analysis(analysis),
            "can_back": self.step_index > 0 and self.capture_state != "capturing",
            "can_start": step.kind == "capture" and self.capture_state != "capturing" and self.device_connected,
            "can_finish": step.kind == "capture" and self.capture_state == "capturing",
            "can_retry": step.kind == "capture" and self.capture_state != "capturing",
            "can_skip": step.kind == "capture" and self.capture_state != "capturing",
            "can_continue": self._can_continue(),
            "can_save": step.kind == "review" and bool(self.attempts),
        }

    def _append_current_sample(self, point: TelemetryPoint) -> None:
        if self._current_attempt is None or self._capture_started_at is None:
            return
        elapsed_ms = max(0, int((point.host_received_at - self._capture_started_at).total_seconds() * 1000))
        selected_source = infer_differential_pressure_selected_source(
            point.differential_pressure_selected_pa,
            point.differential_pressure_low_range_pa,
            point.differential_pressure_high_range_pa,
        )
        sample = FlowCharacterizationSample(
            host_received_at_iso=point.host_received_at.isoformat(timespec="milliseconds"),
            sequence=point.sequence,
            elapsed_ms=elapsed_ms,
            nominal_sample_period_ms=point.nominal_sample_period_ms,
            status_flags=point.status_flags,
            selected_dp_pa=point.differential_pressure_selected_pa,
            sdp810_pa=point.differential_pressure_low_range_pa,
            sdp811_pa=point.differential_pressure_high_range_pa,
            selected_source=selected_source,
            derived_flow_lpm=derive_flow_rate_lpm_from_selected_differential_pressure_pa(
                point.differential_pressure_selected_pa
            ),
            zirconia_output_voltage_v=point.zirconia_output_voltage_v,
            heater_rtd_resistance_ohm=point.heater_rtd_resistance_ohm,
            zirconia_ip_voltage_v=point.zirconia_ip_voltage_v,
            internal_voltage_v=point.internal_voltage_v,
            device_sample_tick_us=point.device_sample_tick_us,
        )
        self._current_attempt.samples.append(sample)
        self._current_attempt.sample_count = len(self._current_attempt.samples)

    def _advance_to_next_step(self) -> None:
        if self.step_index >= len(FLOW_CHARACTERIZATION_STEPS) - 1:
            return
        self.step_index += 1
        self._restore_step_runtime()
        self.updated.emit()

    def _restore_step_runtime(self) -> None:
        step = self.current_step
        self._current_attempt = None
        self._capture_started_at = None
        if step.kind == "overview":
            self.capture_state = "not_armed"
            self.latest_message = step.instruction
            return
        if step.kind == "capture":
            attempt = self._latest_attempt_for_step(step.step_id)
            if attempt is None:
                self.capture_state = "ready"
                self.latest_message = "Start capture when the operator is ready."
                return
            self.capture_state = "skipped" if attempt.operator_event == "skipped" else "captured"
            self.latest_message = self._attempt_message(attempt)
            return
        self.capture_state = "not_armed"
        self.latest_message = step.instruction

    def _latest_attempt_for_step(self, step_id: str) -> FlowCharacterizationAttempt | None:
        for attempt in reversed(self.attempts):
            if attempt.step_id == step_id:
                return attempt
        return None

    def _can_continue(self) -> bool:
        step = self.current_step
        if step.kind == "overview":
            return True
        if step.kind == "review":
            return False
        if step.kind == "capture":
            return self._latest_attempt_for_step(step.step_id) is not None and self.capture_state != "capturing"
        return False

    def _current_message(self) -> str:
        if self.latest_message:
            return self.latest_message
        return self.current_step.instruction

    def _attempt_message(self, attempt: FlowCharacterizationAttempt) -> str:
        if attempt.operator_event == "skipped":
            return "Step was skipped."
        return (
            f"Captured {attempt.sample_count} samples over {attempt.duration_s:0.2f} s. "
            "Accept and continue, or retry to add another attempt."
        )

    def _session_preview(self) -> FlowCharacterizationSession:
        return FlowCharacterizationSession(
            session_id=self.session_id,
            started_at_iso=self.started_at.isoformat(timespec="seconds"),
            completed_at_iso=datetime.now().isoformat(timespec="seconds"),
            status="preview",
            transport_type=self.transport_type,
            mode=self.mode,
            device_identifier=self.current_identifier or self.device_identifier,
            firmware_version=self.firmware_version,
            protocol_version=self.protocol_version,
            criterion_version=FLOW_CHARACTERIZATION_CRITERION_VERSION,
            operator_note=self.operator_note,
            attempts=list(self.attempts),
            analysis=None,
        )


def summarize_attempt_samples(samples: list[FlowCharacterizationSample]) -> FlowCharacterizationAttemptSummary:
    selected_values = _finite_values(sample.selected_dp_pa for sample in samples)
    low_values = _finite_values(sample.sdp810_pa for sample in samples)
    high_values = _finite_values(sample.sdp811_pa for sample in samples)
    source_counts = Counter(sample.selected_source or "unavailable" for sample in samples)
    duration_s = max((sample.elapsed_ms for sample in samples), default=0) / 1000.0
    return FlowCharacterizationAttemptSummary(
        sample_count=len(samples),
        duration_s=duration_s,
        selected_mean_pa=_mean(selected_values),
        selected_min_pa=min(selected_values) if selected_values else None,
        selected_max_pa=max(selected_values) if selected_values else None,
        selected_peak_abs_pa=_peak_abs(selected_values),
        selected_polarity=_polarity_from_values(selected_values),
        sdp810_mean_pa=_mean(low_values),
        sdp810_min_pa=min(low_values) if low_values else None,
        sdp810_max_pa=max(low_values) if low_values else None,
        sdp810_peak_abs_pa=_peak_abs(low_values),
        sdp810_polarity=_polarity_from_values(low_values),
        sdp811_mean_pa=_mean(high_values),
        sdp811_min_pa=min(high_values) if high_values else None,
        sdp811_max_pa=max(high_values) if high_values else None,
        sdp811_peak_abs_pa=_peak_abs(high_values),
        sdp811_polarity=_polarity_from_values(high_values),
        source_counts=dict(source_counts),
    )


def analyze_flow_characterization_session(
    session: FlowCharacterizationSession,
    *,
    rough_scale_target_volume_l: float = FLOW_ROUGH_SCALE_DEFAULT_TARGET_VOLUME_L,
) -> FlowCharacterizationAnalysis:
    latest_attempts: dict[str, FlowCharacterizationAttempt] = {}
    for attempt in session.attempts:
        latest_attempts[attempt.step_id] = attempt

    completed_step_ids = {
        step_id
        for step_id, attempt in latest_attempts.items()
        if attempt.operator_event != "skipped" and attempt.sample_count > 0
    }
    missing_step_ids = [
        step_id
        for step_id in FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS
        if step_id not in completed_step_ids
    ]

    usable_attempts = [
        attempt
        for attempt in latest_attempts.values()
        if attempt.operator_event != "skipped" and attempt.summary is not None and attempt.sample_count > 0
    ]
    selected_peaks = [
        attempt.summary.selected_peak_abs_pa
        for attempt in usable_attempts
        if attempt.summary is not None and attempt.summary.selected_peak_abs_pa is not None
    ]
    low_peaks = [
        attempt.summary.sdp810_peak_abs_pa
        for attempt in usable_attempts
        if attempt.summary is not None and attempt.summary.sdp810_peak_abs_pa is not None
    ]
    high_peaks = [
        attempt.summary.sdp811_peak_abs_pa
        for attempt in usable_attempts
        if attempt.summary is not None and attempt.summary.sdp811_peak_abs_pa is not None
    ]

    polarity_hint = _polarity_hint(usable_attempts)
    low_high_sign_consistency = _low_high_sign_consistency(usable_attempts)
    selected_peak_abs_pa = max(selected_peaks) if selected_peaks else None
    low_range_peak_abs_pa = max(low_peaks) if low_peaks else None
    high_range_peak_abs_pa = max(high_peaks) if high_peaks else None

    notes: list[str] = []
    if missing_step_ids:
        notes.append("Some characterization steps are missing or skipped.")
    if low_range_peak_abs_pa is None:
        notes.append("Low-range raw data is unavailable; wired mode is recommended for characterization.")
    elif low_range_peak_abs_pa >= SDP810_REVIEW_HANDOFF_UPPER_PA:
        notes.append("Low-range SDP810 reached the handoff review region; inspect SDP811 continuity closely.")
    elif low_range_peak_abs_pa >= SDP810_REVIEW_HANDOFF_LOWER_PA:
        notes.append("Low-range SDP810 approached the handoff review region; threshold tuning data is useful.")
    else:
        notes.append("Maximum maneuvers did not reach the current handoff review band.")
    if high_range_peak_abs_pa is None:
        notes.append("High-range raw data is unavailable; threshold decisions will be incomplete.")
    if low_high_sign_consistency != "consistent":
        notes.append("Low/high range sign consistency is not fully established from this run.")

    rough_scale_estimate = estimate_rough_flow_scale(
        latest_attempts,
        target_volume_l=rough_scale_target_volume_l,
    )
    if rough_scale_estimate.recommended_gain_multiplier is None:
        notes.append("Rough lung-capacity scale estimate is unavailable from this run.")
    else:
        notes.append(
            "Rough lung-capacity scale estimate is for development axis-order alignment only; "
            "it is not a formal calibration coefficient."
        )

    return FlowCharacterizationAnalysis(
        completed_capture_steps=len(completed_step_ids),
        missing_step_ids=missing_step_ids,
        polarity_hint=polarity_hint,
        low_high_sign_consistency=low_high_sign_consistency,
        selected_peak_abs_pa=selected_peak_abs_pa,
        low_range_peak_abs_pa=low_range_peak_abs_pa,
        high_range_peak_abs_pa=high_range_peak_abs_pa,
        review_handoff_lower_pa=SDP810_REVIEW_HANDOFF_LOWER_PA,
        review_handoff_upper_pa=SDP810_REVIEW_HANDOFF_UPPER_PA,
        rough_scale_estimate=rough_scale_estimate,
        notes=notes,
    )


def estimate_rough_flow_scale(
    latest_attempts: dict[str, FlowCharacterizationAttempt],
    *,
    target_volume_l: float = FLOW_ROUGH_SCALE_DEFAULT_TARGET_VOLUME_L,
) -> FlowRoughScaleEstimate:
    notes: list[str] = []
    source_step_ids: list[str] = []
    target_volume_l = max(0.1, float(target_volume_l))

    exhale_attempt = latest_attempts.get("max_exhale")
    inhale_attempt = latest_attempts.get("max_inhale")
    exhale_volume_l = _integrated_attempt_volume_l(exhale_attempt)
    inhale_volume_l = _integrated_attempt_volume_l(inhale_attempt)

    exhale_multiplier = _gain_multiplier_for_volume(exhale_volume_l, target_volume_l)
    inhale_multiplier = _gain_multiplier_for_volume(inhale_volume_l, target_volume_l)
    multipliers = [
        value
        for value in (exhale_multiplier, inhale_multiplier)
        if value is not None
    ]
    if exhale_multiplier is not None:
        source_step_ids.append("max_exhale")
    else:
        notes.append("Maximum exhale did not contain enough finite flow samples for rough scaling.")
    if inhale_multiplier is not None:
        source_step_ids.append("max_inhale")
    else:
        notes.append("Maximum inhale did not contain enough finite flow samples for rough scaling.")

    recommended = sum(multipliers) / len(multipliers) if multipliers else None
    confidence = "unavailable"
    if len(multipliers) == 1:
        confidence = "single_direction"
        notes.append("Only one direction contributed; repeat with both maximum exhale and inhale when possible.")
    elif len(multipliers) >= 2 and recommended is not None:
        ratio = max(multipliers) / max(min(multipliers), 1e-9)
        if ratio <= 1.5:
            confidence = "directionally_consistent"
        elif ratio <= 2.5:
            confidence = "review"
            notes.append("Exhale/inhale rough scale estimates differ; inspect maneuver quality and polarity.")
        else:
            confidence = "low"
            notes.append("Exhale/inhale rough scale estimates diverge strongly; treat the coefficient as unreliable.")

    if recommended is not None:
        notes.append(
            "Apply this as a temporary multiplier to the dummy flow gain only after operator review."
        )

    return FlowRoughScaleEstimate(
        policy_id=FLOW_ROUGH_SCALE_POLICY_ID,
        target_volume_l=target_volume_l,
        max_exhale_measured_volume_l=exhale_volume_l,
        max_inhale_measured_volume_l=inhale_volume_l,
        exhale_gain_multiplier=exhale_multiplier,
        inhale_gain_multiplier=inhale_multiplier,
        recommended_gain_multiplier=recommended,
        confidence=confidence,
        source_step_ids=source_step_ids,
        notes=notes,
    )


def format_flow_characterization_analysis(analysis: FlowCharacterizationAnalysis) -> list[str]:
    lines = [
        f"Completed capture steps: {analysis.completed_capture_steps}/{len(FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)}",
        f"Polarity hint: {analysis.polarity_hint}",
        f"Low/high sign consistency: {analysis.low_high_sign_consistency}",
        (
            "Observed peaks: "
            f"selected={_format_optional_pa(analysis.selected_peak_abs_pa)}, "
            f"SDP810={_format_optional_pa(analysis.low_range_peak_abs_pa)}, "
            f"SDP811={_format_optional_pa(analysis.high_range_peak_abs_pa)}"
        ),
    ]
    if analysis.review_handoff_lower_pa is not None and analysis.review_handoff_upper_pa is not None:
        lines.append(
            "Review handoff band: "
            f"{analysis.review_handoff_lower_pa:0.1f}-{analysis.review_handoff_upper_pa:0.1f} Pa "
            "on SDP810 abs pressure"
        )
    if analysis.missing_step_ids:
        lines.append(f"Missing steps: {', '.join(analysis.missing_step_ids)}")
    if analysis.rough_scale_estimate is not None:
        estimate = analysis.rough_scale_estimate
        lines.append(
            "Rough scale target: "
            f"{estimate.target_volume_l:0.2f} L using {estimate.policy_id}"
        )
        lines.append(
            "Rough measured volume: "
            f"max exhale={_format_optional_l(estimate.max_exhale_measured_volume_l)}, "
            f"max inhale={_format_optional_l(estimate.max_inhale_measured_volume_l)}"
        )
        lines.append(
            "Rough gain multiplier: "
            f"{_format_optional_multiplier(estimate.recommended_gain_multiplier)} "
            f"({estimate.confidence})"
        )
        lines.extend(estimate.notes)
    lines.extend(analysis.notes)
    return lines


def _attempt_status(attempt: FlowCharacterizationAttempt | None) -> str:
    if attempt is None:
        return ""
    if attempt.operator_event == "skipped":
        return "skipped"
    if attempt.sample_count <= 0:
        return "empty"
    return "captured"


def _polarity_hint(attempts: list[FlowCharacterizationAttempt]) -> str:
    exhale = _dominant_direction_polarity(attempts, "exhalation")
    inhale = _dominant_direction_polarity(attempts, "inhalation")
    if exhale == "positive" and inhale == "negative":
        return "exhalation_positive_inhalation_negative"
    if exhale == "negative" and inhale == "positive":
        return "exhalation_negative_inhalation_positive"
    if exhale in {"positive", "negative"} and inhale in {"positive", "negative"}:
        return f"same_sign_or_unexpected: exhalation={exhale}, inhalation={inhale}"
    return "insufficient_data"


def _dominant_direction_polarity(attempts: list[FlowCharacterizationAttempt], direction: str) -> str:
    polarities = [
        attempt.summary.selected_polarity
        for attempt in attempts
        if attempt.direction == direction
        and attempt.summary is not None
        and attempt.summary.selected_polarity in {"positive", "negative"}
    ]
    if not polarities:
        return "unavailable"
    counts = Counter(polarities)
    return counts.most_common(1)[0][0]


def _low_high_sign_consistency(attempts: list[FlowCharacterizationAttempt]) -> str:
    comparable_count = 0
    consistent_count = 0
    for attempt in attempts:
        summary = attempt.summary
        if summary is None:
            continue
        low = summary.sdp810_polarity
        high = summary.sdp811_polarity
        if low not in {"positive", "negative"} or high not in {"positive", "negative"}:
            continue
        comparable_count += 1
        if low == high:
            consistent_count += 1
    if comparable_count == 0:
        return "insufficient_data"
    if consistent_count == comparable_count:
        return "consistent"
    return f"mixed:{consistent_count}/{comparable_count}"


def _polarity_from_values(values: list[float], *, near_zero_pa: float = 0.5) -> str:
    if not values:
        return "unavailable"
    positive_peak = max(values)
    negative_peak = min(values)
    peak_abs = max(abs(positive_peak), abs(negative_peak))
    if peak_abs < near_zero_pa:
        return "near_zero"
    if abs(positive_peak) > abs(negative_peak) * 1.15:
        return "positive"
    if abs(negative_peak) > abs(positive_peak) * 1.15:
        return "negative"
    mean_value = _mean(values)
    if mean_value is not None and abs(mean_value) >= near_zero_pa:
        return "positive" if mean_value > 0 else "negative"
    return "mixed"


def _duration_between_iso(start_iso: str, end_iso: str) -> float:
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso)
    except ValueError:
        return 0.0
    return max(0.0, (end - start).total_seconds())


def _integrated_attempt_volume_l(attempt: FlowCharacterizationAttempt | None) -> float | None:
    if attempt is None or len(attempt.samples) < 2:
        return None
    samples = sorted(attempt.samples, key=lambda sample: sample.elapsed_ms)
    volume_l = 0.0
    previous = samples[0]
    for current in samples[1:]:
        if not (
            math.isfinite(previous.derived_flow_lpm)
            and math.isfinite(current.derived_flow_lpm)
        ):
            previous = current
            continue
        delta_ms = max(0, current.elapsed_ms - previous.elapsed_ms)
        if delta_ms == 0:
            previous = current
            continue
        mean_flow_lpm = (previous.derived_flow_lpm + current.derived_flow_lpm) / 2.0
        volume_l += mean_flow_lpm * (delta_ms / 60000.0)
        previous = current
    if abs(volume_l) < 1e-9:
        return None
    return volume_l


def _gain_multiplier_for_volume(measured_volume_l: float | None, target_volume_l: float) -> float | None:
    if measured_volume_l is None or not math.isfinite(measured_volume_l):
        return None
    measured_abs_volume_l = abs(measured_volume_l)
    if measured_abs_volume_l < 1e-6:
        return None
    return target_volume_l / measured_abs_volume_l


def _finite_values(values: Any) -> list[float]:
    finite: list[float] = []
    for value in values:
        if value is None:
            continue
        float_value = float(value)
        if math.isfinite(float_value):
            finite.append(float_value)
    return finite


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _peak_abs(values: list[float]) -> float | None:
    if not values:
        return None
    return max(abs(value) for value in values)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        float_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(float_value):
        return None
    return float_value


def _csv_float(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return ""
    return f"{value:.6f}"


def _format_optional_pa(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:0.3f} Pa"


def _format_optional_l(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:+0.3f} L"


def _format_optional_multiplier(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:0.3f}x"
