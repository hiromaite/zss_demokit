from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from stability_analyzer import StabilityConfig


class ProfileDialog(QDialog):
    MAX_PROFILE_STEPS = 10

    def __init__(self, parent: QWidget, current_profile: Dict[str, str]):
        super().__init__(parent)
        self.setWindowTitle("Profile Settings")

        self.base_edit = QLineEdit(current_profile.get("heater_profile_time_base_ms", "140"))
        self.step_temp_edits: List[QLineEdit] = []
        self.step_duration_edits: List[QLineEdit] = []
        self._profile_values: Dict[str, str] = {}

        temp_values = self._split_profile_values(
            current_profile.get("heater_profile_temp_c", "320,100,100,100,200,200,200,320,320,320")
        )
        duration_values = self._split_profile_values(
            current_profile.get("heater_profile_duration_mult", "5,2,10,30,5,5,5,5,5,5")
        )

        form = QFormLayout()
        form.addRow("Time Base (ms)", self.base_edit)

        step_grid = QGridLayout()
        step_grid.addWidget(QLabel("Step"), 0, 0)
        step_grid.addWidget(QLabel("Temperature (C)"), 0, 1)
        step_grid.addWidget(QLabel("Duration Mult"), 0, 2)

        for step_index in range(self.MAX_PROFILE_STEPS):
            temp_edit = QLineEdit(temp_values[step_index] if step_index < len(temp_values) else "")
            dur_edit = QLineEdit(duration_values[step_index] if step_index < len(duration_values) else "")
            temp_edit.setPlaceholderText("unused")
            dur_edit.setPlaceholderText("unused")
            self.step_temp_edits.append(temp_edit)
            self.step_duration_edits.append(dur_edit)

            step_grid.addWidget(QLabel(str(step_index + 1)), step_index + 1, 0)
            step_grid.addWidget(temp_edit, step_index + 1, 1)
            step_grid.addWidget(dur_edit, step_index + 1, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(step_grid)
        layout.addWidget(buttons)

    @staticmethod
    def _split_profile_values(raw_value: str) -> List[str]:
        return [part.strip() for part in raw_value.split(",") if part.strip()]

    def _collect_profile_values(self) -> Optional[Dict[str, str]]:
        temperatures: List[str] = []
        durations: List[str] = []

        for index, (temp_edit, dur_edit) in enumerate(zip(self.step_temp_edits, self.step_duration_edits), start=1):
            temp_value = temp_edit.text().strip()
            dur_value = dur_edit.text().strip()

            if not temp_value and not dur_value:
                continue

            if not temp_value or not dur_value:
                QMessageBox.warning(
                    self,
                    "Incomplete Step",
                    f"Step {index} must have both temperature and duration, or both left blank.",
                )
                return None

            try:
                temp_int = int(temp_value)
                dur_int = int(dur_value)
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Invalid Step",
                    f"Step {index} must use integer values for temperature and duration.",
                )
                return None

            if temp_int < 0 or temp_int > 400:
                QMessageBox.warning(self, "Invalid Temperature", f"Step {index} temperature must be between 0 and 400 C.")
                return None

            if dur_int < 1 or dur_int > 255:
                QMessageBox.warning(self, "Invalid Duration", f"Step {index} duration multiplier must be between 1 and 255.")
                return None

            temperatures.append(str(temp_int))
            durations.append(str(dur_int))

        if not temperatures:
            QMessageBox.warning(self, "Empty Profile", "Enter at least one complete heater step.")
            return None

        base_value = self.base_edit.text().strip()
        try:
            base_int = int(base_value)
        except ValueError:
            QMessageBox.warning(self, "Invalid Time Base", "Time base must be an integer.")
            return None

        if base_int < 1 or base_int > 1000:
            QMessageBox.warning(self, "Invalid Time Base", "Time base must be between 1 and 1000 ms.")
            return None

        return {
            "heater_profile_temp_c": ",".join(temperatures),
            "heater_profile_duration_mult": ",".join(durations),
            "heater_profile_time_base_ms": str(base_int),
            "profile_len": str(len(temperatures)),
        }

    def accept(self) -> None:  # type: ignore[override]
        profile_values = self._collect_profile_values()
        if profile_values is None:
            return
        self._profile_values = profile_values
        super().accept()

    def profile_command(self) -> str:
        if not self._profile_values:
            profile_values = self._collect_profile_values()
            if profile_values is None:
                return ""
            self._profile_values = profile_values
        return (
            f"SET_PROFILE temp={self._profile_values['heater_profile_temp_c']} "
            f"dur={self._profile_values['heater_profile_duration_mult']} "
            f"base_ms={self._profile_values['heater_profile_time_base_ms']}"
        )

    def profile_state(self) -> Dict[str, str]:
        return dict(self._profile_values)


class StabilitySettingsDialog(QDialog):
    def __init__(self, parent: QWidget, config: StabilityConfig):
        super().__init__(parent)
        self.setWindowTitle("Stability Settings")

        self.threshold_edit = QLineEdit(f"{config.ratio_threshold * 100:.1f}")
        self.recent_window_edit = QLineEdit(str(int(config.recent_window_seconds)))
        self.history_window_edit = QLineEdit(str(int(config.history_window_seconds)))
        self.required_count_edit = QLineEdit(str(int(config.required_channel_count)))
        self._config = config

        form = QFormLayout(self)
        form.addRow("Threshold (%)", self.threshold_edit)
        form.addRow("Recent Window (s)", self.recent_window_edit)
        form.addRow("History Window (s)", self.history_window_edit)
        form.addRow("Required Stable Channels", self.required_count_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self) -> None:  # type: ignore[override]
        try:
            threshold_percent = float(self.threshold_edit.text().strip())
            recent_window_seconds = float(self.recent_window_edit.text().strip())
            history_window_seconds = float(self.history_window_edit.text().strip())
            required_channel_count = int(self.required_count_edit.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid Values", "すべての項目に有効な数値を入力してください。")
            return

        if threshold_percent < 0 or threshold_percent > 100:
            QMessageBox.warning(self, "Invalid Threshold", "Threshold は 0 から 100 の範囲で入力してください。")
            return
        if recent_window_seconds <= 0:
            QMessageBox.warning(self, "Invalid Recent Window", "Recent Window は 0 より大きくしてください。")
            return
        if history_window_seconds < recent_window_seconds:
            QMessageBox.warning(self, "Invalid History Window", "History Window は Recent Window 以上にしてください。")
            return
        if required_channel_count < 1 or required_channel_count > 10:
            QMessageBox.warning(self, "Invalid Channel Count", "Required Stable Channels は 1 から 10 の範囲で入力してください。")
            return

        self._config = StabilityConfig(
            history_window_seconds=history_window_seconds,
            recent_window_seconds=recent_window_seconds,
            ratio_threshold=threshold_percent / 100.0,
            required_channel_count=required_channel_count,
        )
        super().accept()

    def config(self) -> StabilityConfig:
        return self._config
