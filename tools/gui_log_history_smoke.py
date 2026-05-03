#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
for candidate in [str(GUI_ROOT), str(GUI_SRC)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION
from app_state import AppSettings
from dialogs import SettingsDialog
from flow_characterization import (
    FLOW_CHARACTERIZATION_CRITERION_VERSION,
    FlowCharacterizationAnalysis,
    FlowCharacterizationPersistence,
    FlowCharacterizationSession,
    FlowRoughScaleEstimate,
)
from flow_history_dialogs import FlowCharacterizationHistoryDialog, FlowVerificationHistoryDialog
from flow_verification import (
    FLOW_VERIFICATION_CRITERION_VERSION,
    FlowVerificationPersistence,
    VerificationSession,
    VerificationStrokeResult,
    ZeroCheckResult,
)
from main_window import MainWindow
from protocol_constants import BLE_MODE
from qt_runtime import configure_qt_runtime


def _stroke(step_id: str, direction: str, speed: str, error_percent: float) -> VerificationStrokeResult:
    return VerificationStrokeResult(
        step_id=step_id,
        direction=direction,
        speed_band=speed,
        result_status="pass" if abs(error_percent) <= 3.0 else "out_of_target",
        attempt_count=1,
        accepted_attempt_index=1,
        recovered_volume_l=3.0 * (1.0 + error_percent / 100.0),
        reference_volume_l=3.0,
        volume_error_l=3.0 * error_percent / 100.0,
        volume_error_percent=error_percent,
        peak_flow_lps=3.0,
        stroke_duration_s=1.0,
        dominant_source="SDP810",
        source_switch_count=1,
        selected_dp_mean_pa=12.0,
        selected_dp_peak_abs_pa=42.0,
        sdp810_mean_pa=12.0,
        sdp811_mean_pa=11.8,
    )


def _verification_session(session_id: str, completed_at: str, error_percent: float) -> VerificationSession:
    return VerificationSession(
        session_id=session_id,
        started_at_iso=completed_at,
        completed_at_iso=completed_at,
        status="completed",
        transport_type="serial",
        mode="Wired",
        device_identifier="COM-smoke",
        firmware_version="smoke",
        protocol_version="1.0",
        criterion_version=FLOW_VERIFICATION_CRITERION_VERSION,
        zero_check_result=ZeroCheckResult(
            status="stable",
            mean_flow_lpm=0.0,
            peak_abs_flow_lpm=0.05,
            selected_dp_mean_pa=0.0,
            sdp810_mean_pa=0.0,
            sdp811_mean_pa=0.0,
        ),
        exhalation_result="pass",
        inhalation_result="pass",
        overall_result="pass" if abs(error_percent) <= 3.0 else "fail",
        operator_note=f"smoke error {error_percent}",
        stroke_results=[
            _stroke("exh_low", "exhalation", "low", error_percent),
            _stroke("inh_low", "inhalation", "low", -error_percent),
        ],
    )


def _characterization_session(
    session_id: str,
    completed_at: str,
    *,
    selected_peak_abs_pa: float,
    rough_gain: float,
) -> FlowCharacterizationSession:
    return FlowCharacterizationSession(
        session_id=session_id,
        started_at_iso=completed_at,
        completed_at_iso=completed_at,
        status="completed",
        transport_type="serial",
        mode="Wired",
        device_identifier="COM-smoke",
        firmware_version="smoke",
        protocol_version="1.0",
        criterion_version=FLOW_CHARACTERIZATION_CRITERION_VERSION,
        operator_note=f"smoke rough {rough_gain}",
        attempts=[],
        analysis=FlowCharacterizationAnalysis(
            completed_capture_steps=5,
            missing_step_ids=[],
            polarity_hint="exhalation_positive_inhalation_negative",
            low_high_sign_consistency="consistent",
            selected_peak_abs_pa=selected_peak_abs_pa,
            low_range_peak_abs_pa=90.0,
            high_range_peak_abs_pa=selected_peak_abs_pa,
            review_handoff_lower_pa=90.0,
            review_handoff_upper_pa=110.0,
            rough_scale_estimate=FlowRoughScaleEstimate(
                policy_id="smoke",
                target_volume_l=4.5,
                max_exhale_measured_volume_l=0.16,
                max_inhale_measured_volume_l=-0.15,
                exhale_gain_multiplier=rough_gain,
                inhale_gain_multiplier=rough_gain,
                recommended_gain_multiplier=rough_gain,
                confidence="directionally_consistent",
            ),
        ),
    )


def _exercise_event_log(window: MainWindow, base_dir: Path) -> None:
    window.app_settings.logging.recording_directory = str(base_dir)
    window._append_log("info", "Boot complete")  # noqa: SLF001
    window._append_log("warn", "Pump noise warning")  # noqa: SLF001
    window._append_log("error", "Serial connection failed")  # noqa: SLF001

    panel = window.event_log_panel
    panel.severity_filter_combo.setCurrentText("Warnings + Errors")
    if "Boot complete" in panel.log_pane.toPlainText():
        raise AssertionError("info log leaked into warn/error filter")
    if "Pump noise warning" not in panel.log_pane.toPlainText():
        raise AssertionError("warning log missing from warn/error filter")

    panel.search_edit.setText("pump")
    visible_text = panel.log_pane.toPlainText()
    if "Pump noise warning" not in visible_text or "Serial connection failed" in visible_text:
        raise AssertionError(f"search filter did not narrow log entries: {visible_text}")

    export_path = window._export_visible_log()  # noqa: SLF001
    if export_path is None or not export_path.exists():
        raise AssertionError("visible event log was not exported")
    with export_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1 or rows[0]["message"] != "Pump noise warning":
        raise AssertionError(f"unexpected event log export rows: {rows}")

    window._copy_visible_log()  # noqa: SLF001
    if "Pump noise warning" not in QApplication.clipboard().text():
        raise AssertionError("visible event log was not copied to clipboard")


def _exercise_history(base_dir: Path) -> None:
    verification_persistence = FlowVerificationPersistence(base_dir)
    verification_persistence.save_session(
        _verification_session("flow_verification_20260503_120000", "2026-05-03T12:00:00", 8.0)
    )
    verification_persistence.save_session(
        _verification_session("flow_verification_20260503_121000", "2026-05-03T12:10:00", 2.0)
    )
    verification_summaries = verification_persistence.list_recent_summaries(limit=5)
    if len(verification_summaries) != 2:
        raise AssertionError(f"unexpected verification summary count: {len(verification_summaries)}")
    verification_dialog = FlowVerificationHistoryDialog(verification_summaries, verification_persistence)
    try:
        if "Mean abs volume error" not in verification_dialog.history_compare_label.text():
            raise AssertionError("verification comparison text was not shown")
        verification_dialog._export_history_summary()  # noqa: SLF001
        if "Summary CSV exported" not in verification_dialog.history_note_label.text():
            raise AssertionError("verification history export did not update the dialog")
    finally:
        verification_dialog.close()

    characterization_persistence = FlowCharacterizationPersistence(base_dir)
    characterization_persistence.save_session(
        _characterization_session(
            "flow_characterization_20260503_120000",
            "2026-05-03T12:00:00",
            selected_peak_abs_pa=95.0,
            rough_gain=30.0,
        )
    )
    characterization_persistence.save_session(
        _characterization_session(
            "flow_characterization_20260503_121000",
            "2026-05-03T12:10:00",
            selected_peak_abs_pa=105.0,
            rough_gain=28.5,
        )
    )
    characterization_summaries = characterization_persistence.list_recent_summaries(limit=5)
    if len(characterization_summaries) != 2:
        raise AssertionError(f"unexpected characterization summary count: {len(characterization_summaries)}")
    characterization_dialog = FlowCharacterizationHistoryDialog(
        characterization_summaries,
        characterization_persistence,
    )
    try:
        if "Selected peak abs" not in characterization_dialog.history_compare_label.text():
            raise AssertionError("characterization comparison text was not shown")
        characterization_dialog._export_history_summary()  # noqa: SLF001
        if "Summary CSV exported" not in characterization_dialog.history_path_label.text():
            raise AssertionError("characterization history export did not update the dialog")
    finally:
        characterization_dialog.close()

    settings_dialog = SettingsDialog(
        AppSettings(last_mode=BLE_MODE),
        current_mode=BLE_MODE,
        connection_identifier="GasSensor-Proto",
        flow_characterization_summary=characterization_summaries[0],
        flow_characterization_recent_summaries=characterization_summaries,
        flow_verification_summary=verification_summaries[0],
        flow_verification_recent_summaries=verification_summaries,
        flow_verification_available=True,
        flow_characterization_available=True,
    )
    try:
        if not settings_dialog.flow_characterization_history_button.isEnabled():
            raise AssertionError("characterization history button should be enabled when summaries exist")
    finally:
        settings_dialog.close()


def main() -> int:
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    with tempfile.TemporaryDirectory(prefix="zss_log_history_smoke_") as tmpdir:
        window = MainWindow(BLE_MODE)
        try:
            window._plot_refresh_timer.stop()  # noqa: SLF001
            window._telemetry_health_timer.stop()  # noqa: SLF001
            _exercise_event_log(window, Path(tmpdir))
        finally:
            window.close()
        _exercise_history(Path(tmpdir))

    print("gui_log_history_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
