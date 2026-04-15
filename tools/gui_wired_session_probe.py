from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
for candidate in [str(GUI_ROOT), str(GUI_SRC)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION
from main_window import MainWindow
from protocol_constants import WIRED_MODE
from qt_runtime import configure_qt_runtime


@dataclass
class ProbeSummary:
    connection_events: int
    telemetry_count: int
    warning_count: int
    error_count: int
    pump_toggle_requests: int
    csv_rows: int
    non_unit_gaps: int
    final_recording_path: Path


class GuiWiredSessionProbe(QObject):
    def __init__(
        self,
        *,
        window: MainWindow,
        port: str,
        duration_s: float,
        toggle_interval_s: float,
        original_recording_directory: str,
    ) -> None:
        super().__init__(window)
        self.window = window
        self.port = port
        self.duration_s = duration_s
        self.toggle_interval_ms = max(250, int(toggle_interval_s * 1000))
        self.original_recording_directory = original_recording_directory
        self.connection_events = 0
        self.telemetry_count = 0
        self.warning_count = 0
        self.error_count = 0
        self.pump_toggle_requests = 0
        self._pump_next_state = True
        self._finished = False
        self._result: ProbeSummary | None = None
        self._failure_message: str | None = None

        self._toggle_timer = QTimer(self)
        self._toggle_timer.timeout.connect(self._toggle_pump)
        self._finish_timer = QTimer(self)
        self._finish_timer.setSingleShot(True)
        self._finish_timer.timeout.connect(self._finish_session)

        self.window.connection_controller.connection_changed.connect(self._on_connection_changed)
        self.window.connection_controller.telemetry_received.connect(self._on_telemetry)
        self.window.connection_controller.log_generated.connect(self._on_log)

    @property
    def result(self) -> ProbeSummary | None:
        return self._result

    @property
    def failure_message(self) -> str | None:
        return self._failure_message

    def start(self) -> None:
        self.window.port_selector.clear()
        self.window.port_selector.addItem(self.port)
        self.window.port_selector.setCurrentText(self.port)
        self.window.show()
        self.window.connection_controller.connect_device(self.port)
        QTimer.singleShot(1600, self._start_recording)

    def _on_connection_changed(self, connected: bool, identifier: str) -> None:
        self.connection_events += 1
        if not connected and not self._finished and self.telemetry_count > 0:
            self._abort(f"Session disconnected unexpectedly from {identifier}.")

    def _on_telemetry(self, _point: object) -> None:
        self.telemetry_count += 1

    def _on_log(self, severity: str, message: str) -> None:
        if severity == "warn":
            self.warning_count += 1
        elif severity == "error":
            self.error_count += 1
        if severity == "error" and "Recording could not be started" not in message:
            self._abort(f"GUI probe observed error log: {message}")

    def _start_recording(self) -> None:
        if self._finished:
            return
        if not self.window.connection_controller.is_connected():
            self._abort("GUI probe could not establish a wired connection.")
            return
        self.window._start_recording()
        if not self.window.recording_controller.is_recording:
            self._abort("GUI probe failed to enter recording state.")
            return
        self._toggle_timer.start(self.toggle_interval_ms)
        self._finish_timer.start(max(1000, int(self.duration_s * 1000)))

    def _toggle_pump(self) -> None:
        if self._finished or not self.window.connection_controller.is_connected():
            return
        self.window.connection_controller.set_pump_state(self._pump_next_state)
        self._pump_next_state = not self._pump_next_state
        self.pump_toggle_requests += 1

    def _finish_session(self) -> None:
        if self._finished:
            return
        self._toggle_timer.stop()
        self.window._stop_recording()
        if self.window.recording_controller.is_recording:
            self._abort("GUI probe could not finalize recording.")
            return
        final_path_raw = self.window.ui_state.recording.current_file
        final_path = Path(final_path_raw) if final_path_raw else None
        if final_path is None or not final_path.exists():
            self._abort("GUI probe did not produce a finalized CSV file.")
            return
        csv_rows, non_unit_gaps = _analyze_recording_csv(final_path)
        self._result = ProbeSummary(
            connection_events=self.connection_events,
            telemetry_count=self.telemetry_count,
            warning_count=self.warning_count,
            error_count=self.error_count,
            pump_toggle_requests=self.pump_toggle_requests,
            csv_rows=csv_rows,
            non_unit_gaps=non_unit_gaps,
            final_recording_path=final_path,
        )
        self._finished = True
        self.window.app_settings.logging.recording_directory = self.original_recording_directory
        self.window.connection_controller.disconnect_device()
        QTimer.singleShot(400, QApplication.instance().quit)

    def _abort(self, message: str) -> None:
        if self._finished:
            return
        self._failure_message = message
        self._finished = True
        self._toggle_timer.stop()
        self._finish_timer.stop()
        self.window.app_settings.logging.recording_directory = self.original_recording_directory
        self.window._stop_recording()
        self.window.connection_controller.disconnect_device()
        QTimer.singleShot(0, QApplication.instance().quit)


def _analyze_recording_csv(path: Path) -> tuple[int, int]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        content_lines = [line for line in handle if not line.startswith("#")]
    reader = csv.DictReader(content_lines)
    rows.extend(reader)
    non_unit_gaps = sum(1 for row in rows if int(row["sequence_gap"]) > 0)
    return len(rows), non_unit_gaps


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an offscreen GUI-level wired session/recording probe.")
    parser.add_argument("--port", required=True, help="Serial port to use, e.g. /dev/cu.usbmodem4101")
    parser.add_argument("--duration-s", type=float, default=18.0, help="Recording duration in seconds")
    parser.add_argument("--toggle-interval-s", type=float, default=3.0, help="Pump toggle interval in seconds")
    parser.add_argument(
        "--recording-dir",
        default="",
        help="Optional directory for generated CSV files. A temporary directory is used when omitted.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    configure_qt_runtime()
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    recording_dir = Path(args.recording_dir) if args.recording_dir else None
    if recording_dir is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="zss_gui_probe_")
        recording_dir = Path(temp_dir.name)
    recording_dir.mkdir(parents=True, exist_ok=True)

    window = MainWindow(WIRED_MODE)
    original_recording_directory = window.app_settings.logging.recording_directory
    window.app_settings.logging.recording_directory = str(recording_dir)

    probe = GuiWiredSessionProbe(
        window=window,
        port=args.port,
        duration_s=args.duration_s,
        toggle_interval_s=args.toggle_interval_s,
        original_recording_directory=original_recording_directory,
    )
    QTimer.singleShot(0, probe.start)
    app.exec()

    if temp_dir is not None:
        retained_dir = recording_dir
    else:
        retained_dir = recording_dir

    if probe.failure_message is not None:
        print(f"gui_wired_session_probe_failed: {probe.failure_message}")
        print(f"recording_dir={retained_dir}")
        return 1

    if probe.result is None:
        print("gui_wired_session_probe_failed: no result produced")
        print(f"recording_dir={retained_dir}")
        return 1

    summary = probe.result
    print(f"Connection events: {summary.connection_events}")
    print(f"Telemetry samples observed: {summary.telemetry_count}")
    print(f"Pump toggle requests: {summary.pump_toggle_requests}")
    print(f"Warning logs observed: {summary.warning_count}")
    print(f"Error logs observed: {summary.error_count}")
    print(f"CSV rows written: {summary.csv_rows}")
    print(f"CSV non-unit gaps: {summary.non_unit_gaps}")
    print(f"Final recording: {summary.final_recording_path}")
    print(f"recording_dir={retained_dir}")
    print("gui_wired_session_probe_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
