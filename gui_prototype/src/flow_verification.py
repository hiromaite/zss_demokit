from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from mock_backend import TelemetryPoint
from protocol_constants import (
    derive_flow_rate_lpm_from_selected_differential_pressure_pa,
    infer_differential_pressure_selected_source,
)

FLOW_VERIFICATION_CRITERION_VERSION = "flow_verification_v1_poc"
FLOW_VERIFICATION_REFERENCE_VOLUME_L = 3.0


@dataclass(frozen=True)
class FlowVerificationThresholds:
    start_threshold_lpm: float = 1.5
    stop_threshold_lpm: float = 0.75
    minimum_duration_ms: int = 250
    settle_duration_ms: int = 350
    minimum_integrated_volume_l: float = 0.5
    capture_timeout_ms: int = 12_000
    zero_stability_window_ms: int = 1_500
    zero_stability_threshold_lpm: float = 0.4
    reference_volume_l: float = FLOW_VERIFICATION_REFERENCE_VOLUME_L
    target_error_percent: float = 3.0


@dataclass(frozen=True)
class FlowVerificationStep:
    step_id: str
    title: str
    section: str
    instruction: str
    kind: str
    direction: str = ""
    speed_band: str = ""


FLOW_VERIFICATION_STEPS: tuple[FlowVerificationStep, ...] = (
    FlowVerificationStep(
        step_id="overview",
        title="Flow Verification",
        section="Overview",
        instruction=(
            "Use a 3 L syringe to check the current flow measurement path. "
            "This guided check records low, medium, and high strokes for exhalation and inhalation. "
            "You can retry, skip, or continue even if a step is out of target."
        ),
        kind="overview",
    ),
    FlowVerificationStep(
        step_id="zero_check",
        title="Zero Check",
        section="Zero Check",
        instruction=(
            "Keep the flow path still and let the device settle. "
            "This step checks whether the zero-flow condition looks stable before stroke capture."
        ),
        kind="zero",
    ),
    FlowVerificationStep(
        step_id="exh_low",
        title="Exhalation · Low",
        section="Exhalation",
        instruction="Push the 3 L syringe slowly and smoothly.",
        kind="stroke",
        direction="exhalation",
        speed_band="low",
    ),
    FlowVerificationStep(
        step_id="exh_med",
        title="Exhalation · Medium",
        section="Exhalation",
        instruction="Move the 3 L syringe at a moderate, steady speed.",
        kind="stroke",
        direction="exhalation",
        speed_band="medium",
    ),
    FlowVerificationStep(
        step_id="exh_high",
        title="Exhalation · High",
        section="Exhalation",
        instruction="Move the 3 L syringe quickly in one smooth stroke.",
        kind="stroke",
        direction="exhalation",
        speed_band="high",
    ),
    FlowVerificationStep(
        step_id="inh_low",
        title="Inhalation · Low",
        section="Inhalation",
        instruction="Pull the 3 L syringe slowly and smoothly.",
        kind="stroke",
        direction="inhalation",
        speed_band="low",
    ),
    FlowVerificationStep(
        step_id="inh_med",
        title="Inhalation · Medium",
        section="Inhalation",
        instruction="Pull the 3 L syringe at a moderate, steady speed.",
        kind="stroke",
        direction="inhalation",
        speed_band="medium",
    ),
    FlowVerificationStep(
        step_id="inh_high",
        title="Inhalation · High",
        section="Inhalation",
        instruction="Pull the 3 L syringe quickly in one smooth stroke.",
        kind="stroke",
        direction="inhalation",
        speed_band="high",
    ),
    FlowVerificationStep(
        step_id="review",
        title="Review Verification Results",
        section="Review",
        instruction=(
            "Check the recorded strokes and save this verification session if the results are useful. "
            "This PoC workflow does not block completion when a step is out of target."
        ),
        kind="review",
    ),
)


@dataclass
class ZeroCheckResult:
    status: str
    mean_flow_lpm: float
    peak_abs_flow_lpm: float
    selected_dp_mean_pa: float | None
    sdp810_mean_pa: float | None
    sdp811_mean_pa: float | None
    warning_flags: list[str] = field(default_factory=list)


@dataclass
class VerificationStrokeResult:
    step_id: str
    direction: str
    speed_band: str
    result_status: str
    attempt_count: int
    accepted_attempt_index: int
    recovered_volume_l: float
    reference_volume_l: float
    volume_error_l: float
    volume_error_percent: float
    peak_flow_lps: float
    stroke_duration_s: float
    dominant_source: str
    source_switch_count: int
    selected_dp_mean_pa: float | None
    selected_dp_peak_abs_pa: float | None
    sdp810_mean_pa: float | None
    sdp811_mean_pa: float | None
    warning_flags: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class VerificationSession:
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
    zero_check_result: ZeroCheckResult | None
    exhalation_result: str
    inhalation_result: str
    overall_result: str
    operator_note: str
    stroke_results: list[VerificationStrokeResult]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FlowVerificationLatestSummary:
    result: str
    completed_at_iso: str
    criterion_version: str
    exhalation_result: str
    inhalation_result: str
    path: str


@dataclass
class _ZeroAccumulator:
    started_at: datetime | None = None
    flow_values: list[float] = field(default_factory=list)
    selected_values: list[float] = field(default_factory=list)
    low_values: list[float] = field(default_factory=list)
    high_values: list[float] = field(default_factory=list)


@dataclass
class _CaptureAccumulator:
    attempt_index: int
    expected_sign: int
    started_at: datetime | None = None
    last_active_at: datetime | None = None
    previous_point: TelemetryPoint | None = None
    integrated_volume_l: float = 0.0
    peak_abs_flow_lpm: float = 0.0
    flow_values: list[float] = field(default_factory=list)
    selected_values: list[float] = field(default_factory=list)
    low_values: list[float] = field(default_factory=list)
    high_values: list[float] = field(default_factory=list)
    source_sequence: list[str] = field(default_factory=list)


class FlowVerificationPersistence:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir / "flow_verification"

    def save_session(self, session: VerificationSession) -> Path:
        self._base_dir.mkdir(parents=True, exist_ok=True)
        path = self._base_dir / f"{session.session_id}.json"
        path.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
        return path

    def load_latest_summary(self) -> FlowVerificationLatestSummary | None:
        if not self._base_dir.exists():
            return None

        candidates = sorted(self._base_dir.glob("flow_verification_*.json"))
        if not candidates:
            return None

        latest = candidates[-1]
        try:
            payload = json.loads(latest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return FlowVerificationLatestSummary(
            result=str(payload.get("overall_result", "unknown")),
            completed_at_iso=str(payload.get("completed_at_iso", "")),
            criterion_version=str(payload.get("criterion_version", "")),
            exhalation_result=str(payload.get("exhalation_result", "")),
            inhalation_result=str(payload.get("inhalation_result", "")),
            path=str(latest),
        )


class FlowVerificationController(QObject):
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
        thresholds: FlowVerificationThresholds | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.mode = mode
        self.transport_type = transport_type
        self.device_identifier = device_identifier
        self.firmware_version = firmware_version
        self.protocol_version = protocol_version
        self.thresholds = thresholds or FlowVerificationThresholds()
        self.session_id = f"flow_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.started_at = datetime.now()
        self.operator_note = ""
        self.device_connected = True
        self.current_identifier = device_identifier

        self.step_index = 0
        self.capture_state = "not_armed"
        self.latest_message = ""
        self.live_flow_lpm: float | None = None
        self.live_selected_source = ""
        self.live_selected_dp_pa: float | None = None
        self.live_low_range_pa: float | None = None
        self.live_high_range_pa: float | None = None
        self.live_received_at: datetime | None = None

        self.zero_result: ZeroCheckResult | None = None
        self.stroke_results: dict[str, VerificationStrokeResult] = {}
        self._attempt_counts: dict[str, int] = {}
        self._zero_accumulator = _ZeroAccumulator()
        self._capture_accumulator: _CaptureAccumulator | None = None
        self._reset_current_step_runtime()

    @property
    def current_step(self) -> FlowVerificationStep:
        return FLOW_VERIFICATION_STEPS[self.step_index]

    def on_connection_changed(self, connected: bool, identifier: str) -> None:
        self.device_connected = connected
        self.current_identifier = identifier
        if not connected:
            self.latest_message = "Device disconnected. You may cancel, skip, or retry after reconnecting."
        self.updated.emit()

    def on_telemetry(self, point: TelemetryPoint) -> None:
        self.live_flow_lpm = derive_flow_rate_lpm_from_selected_differential_pressure_pa(
            point.differential_pressure_selected_pa
        )
        self.live_selected_dp_pa = point.differential_pressure_selected_pa
        self.live_low_range_pa = point.differential_pressure_low_range_pa
        self.live_high_range_pa = point.differential_pressure_high_range_pa
        self.live_selected_source = infer_differential_pressure_selected_source(
            point.differential_pressure_selected_pa,
            point.differential_pressure_low_range_pa,
            point.differential_pressure_high_range_pa,
        )
        self.live_received_at = point.host_received_at

        if self.current_step.kind == "zero" and self.zero_result is None and self.capture_state == "settling":
            self._consume_zero_sample(point)
        elif self.current_step.kind == "stroke" and self.capture_state in {"armed", "capturing"}:
            self._consume_stroke_sample(point)

        self.updated.emit()

    def go_back(self) -> None:
        if self.step_index <= 0:
            return
        self.step_index -= 1
        self._restore_step_runtime()
        self.updated.emit()

    def continue_step(self) -> None:
        step = self.current_step
        if step.kind == "overview":
            self._advance_to_next_step()
            return
        if step.kind == "zero":
            if self.zero_result is None:
                return
            self.capture_state = "accepted"
            self._advance_to_next_step()
            return
        if step.kind == "stroke":
            if step.step_id not in self.stroke_results:
                return
            self.capture_state = "accepted"
            self._advance_to_next_step()
            return

    def retry_step(self) -> None:
        step = self.current_step
        if step.kind == "overview":
            return
        if step.kind == "zero":
            self.zero_result = None
        elif step.kind == "stroke":
            self.stroke_results.pop(step.step_id, None)
        self._reset_current_step_runtime(increment_attempt=True)
        self.updated.emit()

    def skip_step(self) -> None:
        step = self.current_step
        if step.kind == "overview":
            return
        if step.kind == "zero":
            self.zero_result = ZeroCheckResult(
                status="skipped",
                mean_flow_lpm=0.0,
                peak_abs_flow_lpm=0.0,
                selected_dp_mean_pa=None,
                sdp810_mean_pa=None,
                sdp811_mean_pa=None,
                warning_flags=["skipped"],
            )
        elif step.kind == "stroke":
            self.stroke_results[step.step_id] = VerificationStrokeResult(
                step_id=step.step_id,
                direction=step.direction,
                speed_band=step.speed_band,
                result_status="skipped",
                attempt_count=self._attempt_counts.get(step.step_id, 0),
                accepted_attempt_index=0,
                recovered_volume_l=0.0,
                reference_volume_l=self.thresholds.reference_volume_l,
                volume_error_l=0.0,
                volume_error_percent=0.0,
                peak_flow_lps=0.0,
                stroke_duration_s=0.0,
                dominant_source="",
                source_switch_count=0,
                selected_dp_mean_pa=None,
                selected_dp_peak_abs_pa=None,
                sdp810_mean_pa=None,
                sdp811_mean_pa=None,
                warning_flags=["skipped"],
            )
        self.capture_state = "skipped"
        self._advance_to_next_step()

    def set_operator_note(self, note: str) -> None:
        self.operator_note = note.strip()

    def save_session(self, persistence: FlowVerificationPersistence) -> Path:
        session = VerificationSession(
            session_id=self.session_id,
            started_at_iso=self.started_at.isoformat(timespec="seconds"),
            completed_at_iso=datetime.now().isoformat(timespec="seconds"),
            status="completed",
            transport_type=self.transport_type,
            mode=self.mode,
            device_identifier=self.current_identifier or self.device_identifier,
            firmware_version=self.firmware_version,
            protocol_version=self.protocol_version,
            criterion_version=FLOW_VERIFICATION_CRITERION_VERSION,
            zero_check_result=self.zero_result,
            exhalation_result=self._aggregate_section_result("exhalation"),
            inhalation_result=self._aggregate_section_result("inhalation"),
            overall_result=self._aggregate_overall_result(),
            operator_note=self.operator_note,
            stroke_results=[
                self.stroke_results[step.step_id]
                for step in FLOW_VERIFICATION_STEPS
                if step.kind == "stroke" and step.step_id in self.stroke_results
            ],
        )
        path = persistence.save_session(session)
        self.session_saved.emit(path)
        return path

    def snapshot(self) -> dict[str, Any]:
        step = self.current_step
        current_result = None
        if step.kind == "zero":
            current_result = self.zero_result
        elif step.kind == "stroke":
            current_result = self.stroke_results.get(step.step_id)

        review_rows = []
        for review_step in FLOW_VERIFICATION_STEPS:
            if review_step.kind != "stroke":
                continue
            result = self.stroke_results.get(review_step.step_id)
            review_rows.append(
                {
                    "step_id": review_step.step_id,
                    "label": review_step.title,
                    "status": "" if result is None else result.result_status,
                    "recovered_volume_l": None if result is None else result.recovered_volume_l,
                    "error_percent": None if result is None else result.volume_error_percent,
                    "peak_flow_lps": None if result is None else result.peak_flow_lps,
                    "source": "" if result is None else result.dominant_source,
                }
            )

        return {
            "session_id": self.session_id,
            "step_index": self.step_index + 1,
            "step_total": len(FLOW_VERIFICATION_STEPS),
            "step": step,
            "capture_state": self.capture_state,
            "message": self._current_message(),
            "device_connected": self.device_connected,
            "live_flow_lpm": self.live_flow_lpm,
            "live_selected_source": self.live_selected_source,
            "live_selected_dp_pa": self.live_selected_dp_pa,
            "live_low_range_pa": self.live_low_range_pa,
            "live_high_range_pa": self.live_high_range_pa,
            "current_result": current_result,
            "zero_result": self.zero_result,
            "review_rows": review_rows,
            "exhalation_result": self._aggregate_section_result("exhalation"),
            "inhalation_result": self._aggregate_section_result("inhalation"),
            "overall_result": self._aggregate_overall_result(),
            "can_back": self.step_index > 0,
            "can_retry": step.kind in {"zero", "stroke"},
            "can_skip": step.kind in {"zero", "stroke"},
            "can_continue": self._can_continue(),
            "can_save": step.kind == "review",
        }

    def _advance_to_next_step(self) -> None:
        if self.step_index >= len(FLOW_VERIFICATION_STEPS) - 1:
            return
        self.step_index += 1
        self._restore_step_runtime()
        self.updated.emit()

    def _restore_step_runtime(self) -> None:
        step = self.current_step
        if step.kind == "overview":
            self.capture_state = "not_armed"
            self.latest_message = step.instruction
            return
        if step.kind == "zero":
            if self.zero_result is not None:
                self.capture_state = "accepted" if self.zero_result.status != "skipped" else "skipped"
                self.latest_message = self._zero_result_message(self.zero_result)
            else:
                self._reset_current_step_runtime(increment_attempt=False)
            return
        if step.kind == "stroke":
            if step.step_id in self.stroke_results:
                result = self.stroke_results[step.step_id]
                self.capture_state = "accepted" if result.result_status != "skipped" else "skipped"
                self.latest_message = self._stroke_result_message(result)
            else:
                self._reset_current_step_runtime(increment_attempt=False)
            return
        self.capture_state = "not_armed"
        self.latest_message = step.instruction

    def _reset_current_step_runtime(self, *, increment_attempt: bool = False) -> None:
        step = self.current_step
        self.latest_message = step.instruction
        if step.kind == "overview":
            self.capture_state = "not_armed"
            return
        if step.kind == "zero":
            self.capture_state = "settling"
            self._zero_accumulator = _ZeroAccumulator(started_at=None)
            return
        if step.kind == "stroke":
            if increment_attempt or step.step_id not in self._attempt_counts:
                self._attempt_counts[step.step_id] = self._attempt_counts.get(step.step_id, 0) + 1
            attempt_index = self._attempt_counts[step.step_id]
            expected_sign = 1 if step.direction == "exhalation" else -1
            self.capture_state = "armed"
            self._capture_accumulator = _CaptureAccumulator(
                attempt_index=attempt_index,
                expected_sign=expected_sign,
            )
            self.latest_message = "Waiting for motion."
            return
        self.capture_state = "not_armed"

    def _consume_zero_sample(self, point: TelemetryPoint) -> None:
        flow = derive_flow_rate_lpm_from_selected_differential_pressure_pa(point.differential_pressure_selected_pa)
        if self._zero_accumulator.started_at is None:
            self._zero_accumulator.started_at = point.host_received_at
        self._zero_accumulator.flow_values.append(flow)
        if point.differential_pressure_selected_pa is not None and math.isfinite(point.differential_pressure_selected_pa):
            self._zero_accumulator.selected_values.append(point.differential_pressure_selected_pa)
        if point.differential_pressure_low_range_pa is not None and math.isfinite(point.differential_pressure_low_range_pa):
            self._zero_accumulator.low_values.append(point.differential_pressure_low_range_pa)
        if point.differential_pressure_high_range_pa is not None and math.isfinite(point.differential_pressure_high_range_pa):
            self._zero_accumulator.high_values.append(point.differential_pressure_high_range_pa)

        if point.host_received_at - self._zero_accumulator.started_at < timedelta(
            milliseconds=self.thresholds.zero_stability_window_ms
        ):
            return

        mean_flow = self._mean(self._zero_accumulator.flow_values)
        peak_abs_flow = max((abs(value) for value in self._zero_accumulator.flow_values), default=0.0)
        warning_flags: list[str] = []
        if peak_abs_flow > self.thresholds.zero_stability_threshold_lpm:
            status = "unstable"
            warning_flags.append("zero_unstable")
        else:
            status = "stable"

        self.zero_result = ZeroCheckResult(
            status=status,
            mean_flow_lpm=mean_flow,
            peak_abs_flow_lpm=peak_abs_flow,
            selected_dp_mean_pa=self._mean(self._zero_accumulator.selected_values),
            sdp810_mean_pa=self._mean(self._zero_accumulator.low_values),
            sdp811_mean_pa=self._mean(self._zero_accumulator.high_values),
            warning_flags=warning_flags,
        )
        self.capture_state = "captured"
        self.latest_message = self._zero_result_message(self.zero_result)

    def _consume_stroke_sample(self, point: TelemetryPoint) -> None:
        step = self.current_step
        if self._capture_accumulator is None:
            return

        flow = derive_flow_rate_lpm_from_selected_differential_pressure_pa(point.differential_pressure_selected_pa)
        normalized_flow = flow * self._capture_accumulator.expected_sign

        if self.capture_state == "armed":
            if normalized_flow <= self.thresholds.start_threshold_lpm:
                return
            self.capture_state = "capturing"
            self.latest_message = "Capturing stroke."
            self._capture_accumulator.started_at = point.host_received_at
            self._capture_accumulator.last_active_at = point.host_received_at
            self._capture_accumulator.previous_point = point
            self._append_capture_sample(point, flow, interval_s=0.0)
            return

        previous_point = self._capture_accumulator.previous_point
        interval_s = self._sample_interval_s(previous_point, point)
        self._append_capture_sample(point, flow, interval_s=interval_s)
        self._capture_accumulator.previous_point = point

        if normalized_flow > self.thresholds.stop_threshold_lpm:
            self._capture_accumulator.last_active_at = point.host_received_at

        if (
            self._capture_accumulator.started_at is not None
            and point.host_received_at - self._capture_accumulator.started_at
            >= timedelta(milliseconds=self.thresholds.capture_timeout_ms)
        ):
            self._finalize_capture(timeout=True)
            return

        if self._capture_accumulator.last_active_at is None:
            return

        if point.host_received_at - self._capture_accumulator.last_active_at < timedelta(
            milliseconds=self.thresholds.settle_duration_ms
        ):
            return

        duration_ms = self._capture_duration_ms()
        normalized_volume_l = self._capture_accumulator.integrated_volume_l * self._capture_accumulator.expected_sign
        if duration_ms < self.thresholds.minimum_duration_ms:
            self._finalize_capture(incomplete_reason="duration_too_short")
            return
        if normalized_volume_l < self.thresholds.minimum_integrated_volume_l:
            self._finalize_capture(incomplete_reason="volume_too_small")
            return

        self._finalize_capture()

    def _append_capture_sample(self, point: TelemetryPoint, flow_lpm: float, *, interval_s: float) -> None:
        if self._capture_accumulator is None:
            return
        self._capture_accumulator.integrated_volume_l += (flow_lpm / 60.0) * interval_s
        self._capture_accumulator.peak_abs_flow_lpm = max(
            self._capture_accumulator.peak_abs_flow_lpm,
            abs(flow_lpm),
        )
        self._capture_accumulator.flow_values.append(flow_lpm)
        if point.differential_pressure_selected_pa is not None and math.isfinite(point.differential_pressure_selected_pa):
            self._capture_accumulator.selected_values.append(point.differential_pressure_selected_pa)
        if point.differential_pressure_low_range_pa is not None and math.isfinite(point.differential_pressure_low_range_pa):
            self._capture_accumulator.low_values.append(point.differential_pressure_low_range_pa)
        if point.differential_pressure_high_range_pa is not None and math.isfinite(point.differential_pressure_high_range_pa):
            self._capture_accumulator.high_values.append(point.differential_pressure_high_range_pa)
        selected_source = infer_differential_pressure_selected_source(
            point.differential_pressure_selected_pa,
            point.differential_pressure_low_range_pa,
            point.differential_pressure_high_range_pa,
        )
        self._capture_accumulator.source_sequence.append(selected_source)

    def _finalize_capture(
        self,
        *,
        timeout: bool = False,
        incomplete_reason: str | None = None,
    ) -> None:
        step = self.current_step
        if self._capture_accumulator is None or step.kind != "stroke":
            return

        duration_s = max(0.0, self._capture_duration_ms() / 1000.0)
        normalized_volume_l = self._capture_accumulator.integrated_volume_l * self._capture_accumulator.expected_sign
        volume_error_l = normalized_volume_l - self.thresholds.reference_volume_l
        volume_error_percent = (volume_error_l / self.thresholds.reference_volume_l) * 100.0

        warning_flags: list[str] = []
        if timeout:
            warning_flags.append("capture_timeout")
        if incomplete_reason:
            warning_flags.append(incomplete_reason)

        dominant_source, source_switch_count = self._summarize_sources(self._capture_accumulator.source_sequence)

        if timeout or incomplete_reason is not None:
            result_status = "incomplete"
        elif abs(volume_error_percent) <= self.thresholds.target_error_percent:
            result_status = "pass"
        else:
            result_status = "out_of_target"

        if result_status == "pass" and (dominant_source == "mixed" or source_switch_count > 6):
            result_status = "advisory"
            warning_flags.append("selector_unstable")

        result = VerificationStrokeResult(
            step_id=step.step_id,
            direction=step.direction,
            speed_band=step.speed_band,
            result_status=result_status,
            attempt_count=self._capture_accumulator.attempt_index,
            accepted_attempt_index=self._capture_accumulator.attempt_index,
            recovered_volume_l=max(0.0, normalized_volume_l),
            reference_volume_l=self.thresholds.reference_volume_l,
            volume_error_l=volume_error_l,
            volume_error_percent=volume_error_percent,
            peak_flow_lps=self._capture_accumulator.peak_abs_flow_lpm / 60.0,
            stroke_duration_s=duration_s,
            dominant_source=dominant_source,
            source_switch_count=source_switch_count,
            selected_dp_mean_pa=self._mean(self._capture_accumulator.selected_values),
            selected_dp_peak_abs_pa=self._peak_abs(self._capture_accumulator.selected_values),
            sdp810_mean_pa=self._mean(self._capture_accumulator.low_values),
            sdp811_mean_pa=self._mean(self._capture_accumulator.high_values),
            warning_flags=warning_flags,
        )
        self.stroke_results[step.step_id] = result
        self.capture_state = "captured"
        self.latest_message = self._stroke_result_message(result)

    def _capture_duration_ms(self) -> int:
        if self._capture_accumulator is None or self._capture_accumulator.started_at is None:
            return 0
        reference_time = self.live_received_at or datetime.now()
        return max(0, int((reference_time - self._capture_accumulator.started_at).total_seconds() * 1000))

    def _can_continue(self) -> bool:
        step = self.current_step
        if step.kind == "overview":
            return True
        if step.kind == "review":
            return False
        if step.kind == "zero":
            return self.zero_result is not None
        if step.kind == "stroke":
            return step.step_id in self.stroke_results
        return False

    def _current_message(self) -> str:
        if self.latest_message:
            return self.latest_message
        return self.current_step.instruction

    def _sample_interval_s(self, previous_point: TelemetryPoint | None, point: TelemetryPoint) -> float:
        if previous_point is None:
            return 0.0
        if previous_point.device_sample_tick_us is not None and point.device_sample_tick_us is not None:
            delta_us = (point.device_sample_tick_us - previous_point.device_sample_tick_us) & 0xFFFFFFFF
            return max(0.0, min(delta_us / 1_000_000.0, 0.25))
        return max(0.0, min((point.host_received_at - previous_point.host_received_at).total_seconds(), 0.25))

    def _aggregate_section_result(self, direction: str) -> str:
        relevant = [
            result
            for result in self.stroke_results.values()
            if result.direction == direction
        ]
        if len(relevant) < 3:
            return "incomplete"
        statuses = {result.result_status for result in relevant}
        if "out_of_target" in statuses:
            return "out_of_target"
        if "incomplete" in statuses or "skipped" in statuses:
            return "incomplete"
        if "advisory" in statuses:
            return "pass_with_advisory"
        return "pass"

    def _aggregate_overall_result(self) -> str:
        exhalation_result = self._aggregate_section_result("exhalation")
        inhalation_result = self._aggregate_section_result("inhalation")
        if exhalation_result == "out_of_target":
            return "fail"
        if exhalation_result == "incomplete":
            return "incomplete"
        if exhalation_result == "pass_with_advisory":
            return "pass_with_advisory"
        if inhalation_result in {"out_of_target", "pass_with_advisory"}:
            return "pass_with_advisory"
        if inhalation_result == "incomplete":
            return "incomplete"
        return "pass"

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        finite_values = [value for value in values if math.isfinite(value)]
        if not finite_values:
            return None
        return sum(finite_values) / len(finite_values)

    @staticmethod
    def _peak_abs(values: list[float]) -> float | None:
        finite_values = [abs(value) for value in values if math.isfinite(value)]
        if not finite_values:
            return None
        return max(finite_values)

    @staticmethod
    def _summarize_sources(source_sequence: list[str]) -> tuple[str, int]:
        normalized = [source for source in source_sequence if source]
        if not normalized:
            return "", 0

        switches = 0
        for previous, current in zip(normalized, normalized[1:]):
            if previous != current:
                switches += 1

        counts = Counter(normalized)
        dominant_source, dominant_count = counts.most_common(1)[0]
        if dominant_count / len(normalized) < 0.7:
            dominant_source = "mixed"
        return dominant_source, switches

    @staticmethod
    def _zero_result_message(result: ZeroCheckResult) -> str:
        if result.status == "stable":
            return "Zero looks stable."
        if result.status == "unstable":
            return "Zero looks unstable. You may retry or continue."
        return "Zero check was skipped."

    @staticmethod
    def _stroke_result_message(result: VerificationStrokeResult) -> str:
        if result.result_status == "pass":
            return "Looks good."
        if result.result_status == "advisory":
            return "Stroke looks usable, but retry is recommended."
        if result.result_status == "out_of_target":
            return "Recovered volume is outside the current target range. You may retry or continue."
        if result.result_status == "skipped":
            return "Step was skipped."
        return "Capture looks incomplete. Retry is recommended."
