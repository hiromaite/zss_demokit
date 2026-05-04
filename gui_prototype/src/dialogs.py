from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app_metadata import APP_NAME
from app_state import (
    AppSettings,
    O2_FILTER_PRESET_CUSTOM,
    O2_FILTER_PRESETS,
    O2_FILTER_TYPES,
    O2_FILTER_TYPE_CENTERED_GAUSSIAN,
    O2_FILTER_TYPE_EMA_1,
    O2_FILTER_TYPE_EMA_2,
    O2_FILTER_TYPE_GAUSSIAN,
    O2_FILTER_TYPE_SAVGOL_7,
    O2_FILTER_TYPE_SAVGOL_9,
    O2OutputFilterPreferences,
)
from dialog_helpers import dialog_header, format_optional, style_dialog_buttons
from flow_characterization import (
    FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS,
    FLOW_CHARACTERIZATION_STEPS,
    FlowCharacterizationAttempt,
    FlowCharacterizationAttemptSummary,
    FlowCharacterizationController,
    FlowCharacterizationLatestSummary,
    FlowCharacterizationPersistence,
    FlowCharacterizationSaveResult,
)
from flow_verification import (
    FLOW_VERIFICATION_STEPS,
    FlowVerificationController,
    FlowVerificationLatestSummary,
    FlowVerificationPersistence,
    VerificationSession,
    VerificationStrokeResult,
    ZeroCheckResult,
)
from o2_filter import effective_o2_filter_preferences
from protocol_constants import (
    BLE_MODE,
    DERIVED_METRIC_POLICY_ID,
    PROTOCOL_VERSION_TEXT,
    WIRED_DEFAULT_BAUDRATE,
    WIRED_DEFAULT_LINE_SETTINGS,
    WIRED_MODE,
)
from recording_io import find_partial_recordings, summarize_partial_recordings
from ui_helpers import VerticalOnlyScrollArea


class PartialRecoveryDialog(QDialog):
    def __init__(self, base_dir: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        partials = find_partial_recordings(base_dir)
        self.setWindowTitle("Partial Session Recovery")
        self.resize(760, 520)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addWidget(
            dialog_header(
                "Partial Session Recovery",
                "Unfinished session files are kept as .partial.csv until a recording is finalized.",
            )
        )

        banner = QFrame()
        banner.setObjectName("WarningCard")
        banner_layout = QVBoxLayout(banner)
        if partials:
            banner_layout.addWidget(QLabel(f"{len(partials)} unfinished session file(s) detected."))
            summary_label = QLabel(summarize_partial_recordings(partials, limit=8))
        else:
            banner_layout.addWidget(QLabel("No unfinished session files were found."))
            summary_label = QLabel("Start a recording and force-close the app to leave a partial file behind.")
        summary_label.setWordWrap(True)
        banner_layout.addWidget(summary_label)
        root.addWidget(banner)

        listing = QListWidget()
        for path in partials:
            listing.addItem(path.name)
        root.addWidget(listing, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        style_dialog_buttons(button_box)
        button_box.accepted.connect(self.accept)
        root.addWidget(button_box)


class ModeSwitchDialog(QDialog):
    def __init__(self, current_mode: str, next_mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Mode Change")
        self.resize(520, 260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        warning = QFrame()
        warning.setObjectName("WarningCard")
        warning_layout = QVBoxLayout(warning)

        title = QLabel("Current session will be interrupted.")
        title.setObjectName("SectionTitle")
        copy = QLabel(
            f"Switching from {current_mode} mode to {next_mode} mode will disconnect the active device, "
            "stop recording if needed, and reopen the main screen in a disconnected state."
        )
        copy.setWordWrap(True)
        copy.setObjectName("SectionHint")
        warning_layout.addWidget(title)
        warning_layout.addWidget(copy)
        layout.addWidget(warning)

        button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        style_dialog_buttons(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class SettingsDialog(QDialog):
    device_action_requested = Signal(str)

    def __init__(
        self,
        settings: AppSettings,
        current_mode: str,
        connection_identifier: str,
        current_zirconia_voltage_v: float | None = None,
        flow_verification_summary: FlowVerificationLatestSummary | None = None,
        flow_verification_recent_summaries: list[FlowVerificationLatestSummary] | None = None,
        flow_characterization_summary: FlowCharacterizationLatestSummary | None = None,
        flow_characterization_recent_summaries: list[FlowCharacterizationLatestSummary] | None = None,
        flow_verification_available: bool = False,
        flow_characterization_available: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._current_mode = current_mode
        self._connection_identifier = connection_identifier
        self._current_zirconia_voltage_v = current_zirconia_voltage_v
        self._flow_verification_summary = flow_verification_summary
        self._flow_verification_recent_summaries = flow_verification_recent_summaries or []
        self._flow_characterization_summary = flow_characterization_summary
        self._flow_characterization_recent_summaries = flow_characterization_recent_summaries or []
        self._flow_verification_available = flow_verification_available
        self._flow_characterization_available = flow_characterization_available
        self._open_flow_verification_requested = False
        self._show_flow_verification_details_requested = False
        self._show_flow_verification_history_requested = False
        self._open_flow_characterization_requested = False
        self._show_flow_characterization_history_requested = False
        self._pending_o2_air_calibration_voltage_v = settings.o2.air_calibration_voltage_v
        self._pending_o2_calibrated_at_iso = settings.o2.calibrated_at_iso
        self._pending_o2_zero_reference_voltage_v = settings.o2.zero_reference_voltage_v
        self._syncing_o2_filter_controls = False
        self.setWindowTitle("Settings")
        self.resize(880, 580)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("SurfaceCard")
        header_layout = QVBoxLayout(header)
        title = QLabel("Settings")
        title.setObjectName("SectionTitle")
        copy = QLabel(
            "Operator-facing settings stay in General, Plot, Recording, and Device. "
            "Diagnostics and development workflows live under Engineering / Tools."
        )
        copy.setObjectName("SectionHint")
        copy.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(copy)
        layout.addWidget(header)

        shell = QHBoxLayout()
        shell.setSpacing(14)
        layout.addLayout(shell, 1)

        self.nav = QListWidget()
        self.nav.setObjectName("SettingsNav")
        for label in ["General", "Plot", "Recording", "Device", "Engineering / Tools", "About"]:
            QListWidgetItem(label, self.nav)
        self.nav.setCurrentRow(0)
        shell.addWidget(self.nav, 0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_general_page())
        self.stack.addWidget(self._create_plot_page())
        self.stack.addWidget(self._create_recording_page())
        self.stack.addWidget(self._create_device_page())
        self.stack.addWidget(self._create_engineering_tools_page())
        self.stack.addWidget(self._create_about_page())
        shell.addWidget(self.stack, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        style_dialog_buttons(button_box)
        self.button_box = button_box
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self._update_mode_page_state()

    @property
    def requested_mode(self) -> str:
        return BLE_MODE if self.ble_mode_radio.isChecked() else WIRED_MODE

    @property
    def selected_time_span(self) -> str:
        return self.default_time_span_combo.currentText()

    @property
    def selected_axis_mode(self) -> str:
        return self.axis_mode_combo.currentText()

    @property
    def selected_auto_scale(self) -> bool:
        return self.auto_scale_check.isChecked()

    @property
    def selected_plot(self) -> str:
        return self.default_plot_combo.currentText()

    @property
    def recording_directory(self) -> str:
        return self.recording_directory_edit.text().strip()

    @property
    def partial_recovery_notice_enabled(self) -> bool:
        return self.partial_recovery_notice_check.isChecked()

    @property
    def selected_o2_air_calibration_voltage_v(self) -> float | None:
        return self._pending_o2_air_calibration_voltage_v

    @property
    def selected_o2_zero_reference_voltage_v(self) -> float:
        if hasattr(self, "o2_zero_reference_spin"):
            return self.o2_zero_reference_spin.value()
        return self._pending_o2_zero_reference_voltage_v

    @property
    def selected_o2_calibrated_at_iso(self) -> str:
        return self._pending_o2_calibrated_at_iso

    @property
    def selected_o2_filter_preferences(self) -> O2OutputFilterPreferences:
        return O2OutputFilterPreferences(
            enabled=self.o2_filter_enabled_check.isChecked(),
            filter_type=self.o2_filter_type_combo.currentText(),
            preset=self.o2_filter_preset_combo.currentText(),
            ema_cutoff_hz=self.o2_filter_ema_cutoff_spin.value(),
            gaussian_sigma_ms=self.o2_filter_gaussian_sigma_spin.value(),
            gaussian_tail_sigma=self.o2_filter_gaussian_tail_spin.value(),
            centered_gaussian_sigma_samples=self.o2_filter_centered_gaussian_sigma_spin.value(),
        )

    @property
    def flow_verification_requested(self) -> bool:
        return self._open_flow_verification_requested

    @property
    def flow_verification_details_requested(self) -> bool:
        return self._show_flow_verification_details_requested

    @property
    def flow_verification_history_requested(self) -> bool:
        return self._show_flow_verification_history_requested

    @property
    def flow_characterization_requested(self) -> bool:
        return self._open_flow_characterization_requested

    @property
    def flow_characterization_history_requested(self) -> bool:
        return self._show_flow_characterization_history_requested

    def _page_wrapper(self, *, scrollable: bool = False) -> tuple[QWidget, QVBoxLayout]:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        if not scrollable:
            return content, layout

        page = VerticalOnlyScrollArea()
        page.setWidgetResizable(True)
        page.setFrameShape(QFrame.NoFrame)
        page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page.setWidget(content)
        return page, layout

    def _create_general_page(self) -> QWidget:
        page, layout = self._page_wrapper()

        card = QFrame()
        card.setObjectName("AccentCard")
        card_layout = QVBoxLayout(card)
        title = QLabel("General")
        title.setObjectName("SectionTitle")
        hint = QLabel("Choose the active transport mode and review the current connection context.")
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(hint)

        self.ble_mode_radio = QRadioButton("BLE mode")
        self.wired_mode_radio = QRadioButton("Wired mode")
        if self._settings.last_mode == BLE_MODE:
            self.ble_mode_radio.setChecked(True)
        else:
            self.wired_mode_radio.setChecked(True)
        self.ble_mode_radio.toggled.connect(self._update_mode_page_state)
        self.wired_mode_radio.toggled.connect(self._update_mode_page_state)

        summary = QLabel(f"Current session target: {self._connection_identifier}")
        summary.setObjectName("SectionHint")
        summary.setWordWrap(True)

        self.mode_status_label = QLabel("")
        self.mode_status_label.setObjectName("ModeStatusLabel")
        self.mode_status_label.setWordWrap(True)

        card_layout.addWidget(self.ble_mode_radio)
        card_layout.addWidget(self.wired_mode_radio)
        card_layout.addWidget(summary)
        card_layout.addWidget(self.mode_status_label)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _create_plot_page(self) -> QWidget:
        page, layout = self._page_wrapper()
        card = QFrame()
        card.setObjectName("SurfaceCard")
        form = QFormLayout(card)
        self.default_time_span_combo = QComboBox()
        self.default_time_span_combo.addItems(["30 s", "2 min", "10 min", "All"])
        self.default_time_span_combo.setCurrentText(self._settings.plot.time_span)
        self.axis_mode_combo = QComboBox()
        self.axis_mode_combo.addItems(["Relative", "Clock"])
        self.axis_mode_combo.setCurrentText(self._settings.plot.axis_mode)
        self.auto_scale_check = QCheckBox("Enable auto scale by default")
        self.auto_scale_check.setChecked(self._settings.plot.auto_scale)
        self.default_plot_combo = QComboBox()
        self.default_plot_combo.addItems(["Flow / O2", "Zirconia / Heater"])
        self.default_plot_combo.setCurrentText(self._settings.plot.selected_plot)
        form.addRow("Default time span", self.default_time_span_combo)
        form.addRow("Time axis display", self.axis_mode_combo)
        form.addRow("Selected plot", self.default_plot_combo)
        form.addRow("Auto scale", self.auto_scale_check)
        form.addRow("Refresh policy", QLabel("Timer-driven, 150 ms target"))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _create_recording_page(self) -> QWidget:
        page, layout = self._page_wrapper()
        card = QFrame()
        card.setObjectName("SurfaceCard")
        form = QFormLayout(card)
        directory_row = QHBoxLayout()
        self.recording_directory_edit = self._create_recording_directory_field()
        browse_button = QPushButton("Browse")
        browse_button.setObjectName("SecondaryButton")
        browse_button.clicked.connect(self._browse_recording_directory)
        directory_row.addWidget(self.recording_directory_edit, 1)
        directory_row.addWidget(browse_button)
        directory_shell = QWidget()
        directory_shell.setLayout(directory_row)
        self.partial_recovery_notice_check = QCheckBox("Show partial recovery notice at startup")
        self.partial_recovery_notice_check.setChecked(self._settings.logging.partial_recovery_notice_enabled)
        form.addRow("Recording directory", directory_shell)
        form.addRow("Partial recovery", self.partial_recovery_notice_check)
        form.addRow("Derived metric policy", QLabel(DERIVED_METRIC_POLICY_ID))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _create_device_page(self) -> QWidget:
        page, layout = self._page_wrapper(scrollable=True)
        summary_card = QFrame()
        summary_card.setObjectName("SurfaceCard")
        summary_form = QFormLayout(summary_card)
        summary_form.addRow("Current mode", QLabel(self._current_mode))
        summary_form.addRow("Target device", QLabel(self._connection_identifier))
        summary_form.addRow("Protocol family", QLabel(f"v{PROTOCOL_VERSION_TEXT} prototype"))
        summary_form.addRow("Serial defaults", QLabel(f"{WIRED_DEFAULT_BAUDRATE} baud / {WIRED_DEFAULT_LINE_SETTINGS}"))
        summary_form.addRow("BLE identity policy", QLabel("Prefer GasSensor-Proto; accept legacy names"))
        layout.addWidget(summary_card)

        calibration_card = QFrame()
        calibration_card.setObjectName("SurfaceCard")
        calibration_layout = QVBoxLayout(calibration_card)
        calibration_title = QLabel("O2 Calibration (1-cell)")
        calibration_title.setObjectName("SectionTitle")
        calibration_hint = QLabel(
            "Use the current zirconia output voltage while the sensor is resting in ambient air. "
            "Set the 0 % anchor voltage for this prototype and store the ambient point as the 21 % anchor."
        )
        calibration_hint.setObjectName("SectionHint")
        calibration_hint.setWordWrap(True)
        calibration_layout.addWidget(calibration_title)
        calibration_layout.addWidget(calibration_hint)

        self.o2_calibration_status_label = QLabel("")
        self.o2_calibration_status_label.setObjectName("SectionHint")
        self.o2_calibration_status_label.setWordWrap(True)
        calibration_layout.addWidget(self.o2_calibration_status_label)

        self.o2_calibration_live_label = QLabel("")
        self.o2_calibration_live_label.setObjectName("SectionHint")
        self.o2_calibration_live_label.setWordWrap(True)
        calibration_layout.addWidget(self.o2_calibration_live_label)

        calibration_form = QFormLayout()
        self.o2_zero_reference_spin = QDoubleSpinBox()
        self.o2_zero_reference_spin.setRange(0.0, 5.0)
        self.o2_zero_reference_spin.setDecimals(3)
        self.o2_zero_reference_spin.setSingleStep(0.05)
        self.o2_zero_reference_spin.setSuffix(" V")
        self.o2_zero_reference_spin.setValue(self._pending_o2_zero_reference_voltage_v)
        self.o2_zero_reference_spin.valueChanged.connect(self._update_o2_zero_reference_voltage)
        calibration_form.addRow("0% reference voltage", self.o2_zero_reference_spin)
        calibration_layout.addLayout(calibration_form)

        calibration_row = QHBoxLayout()
        self.o2_calibrate_button = QPushButton("Calibrate to Ambient Air (21%)")
        self.o2_calibrate_button.setObjectName("PrimaryButton")
        self.o2_calibrate_button.clicked.connect(self._calibrate_o2_to_ambient_air)
        self.o2_reset_button = QPushButton("Reset O2 Calibration")
        self.o2_reset_button.setObjectName("SecondaryButton")
        self.o2_reset_button.clicked.connect(self._reset_o2_calibration)
        calibration_row.addWidget(self.o2_calibrate_button)
        calibration_row.addWidget(self.o2_reset_button)
        calibration_row.addStretch(1)
        calibration_layout.addLayout(calibration_row)
        layout.addWidget(calibration_card)

        filter_card = QFrame()
        filter_card.setObjectName("SurfaceCard")
        filter_layout = QVBoxLayout(filter_card)
        filter_title = QLabel("O2 Output Filter")
        filter_title.setObjectName("SectionTitle")
        filter_layout.addWidget(filter_title)

        filter_form = QFormLayout()
        self.o2_filter_enabled_check = QCheckBox("Enable O2 output smoothing")
        self.o2_filter_enabled_check.setChecked(self._settings.o2_filter.enabled)
        self.o2_filter_type_combo = QComboBox()
        self.o2_filter_type_combo.addItems(list(O2_FILTER_TYPES))
        self.o2_filter_type_combo.setCurrentText(self._settings.o2_filter.filter_type)
        self.o2_filter_preset_combo = QComboBox()
        self.o2_filter_preset_combo.addItems(list(O2_FILTER_PRESETS))
        self.o2_filter_preset_combo.setCurrentText(self._settings.o2_filter.preset)

        self.o2_filter_ema_cutoff_spin = QDoubleSpinBox()
        self.o2_filter_ema_cutoff_spin.setRange(0.1, 25.0)
        self.o2_filter_ema_cutoff_spin.setDecimals(1)
        self.o2_filter_ema_cutoff_spin.setSingleStep(0.5)
        self.o2_filter_ema_cutoff_spin.setSuffix(" Hz")
        self.o2_filter_ema_cutoff_spin.setValue(self._settings.o2_filter.ema_cutoff_hz)

        self.o2_filter_gaussian_sigma_spin = QDoubleSpinBox()
        self.o2_filter_gaussian_sigma_spin.setRange(1.0, 1000.0)
        self.o2_filter_gaussian_sigma_spin.setDecimals(1)
        self.o2_filter_gaussian_sigma_spin.setSingleStep(5.0)
        self.o2_filter_gaussian_sigma_spin.setSuffix(" ms")
        self.o2_filter_gaussian_sigma_spin.setValue(self._settings.o2_filter.gaussian_sigma_ms)

        self.o2_filter_gaussian_tail_spin = QDoubleSpinBox()
        self.o2_filter_gaussian_tail_spin.setRange(1.0, 6.0)
        self.o2_filter_gaussian_tail_spin.setDecimals(2)
        self.o2_filter_gaussian_tail_spin.setSingleStep(0.25)
        self.o2_filter_gaussian_tail_spin.setSuffix(" sigma")
        self.o2_filter_gaussian_tail_spin.setValue(self._settings.o2_filter.gaussian_tail_sigma)

        self.o2_filter_centered_gaussian_sigma_spin = QDoubleSpinBox()
        self.o2_filter_centered_gaussian_sigma_spin.setRange(1.0, 1.5)
        self.o2_filter_centered_gaussian_sigma_spin.setDecimals(2)
        self.o2_filter_centered_gaussian_sigma_spin.setSingleStep(0.05)
        self.o2_filter_centered_gaussian_sigma_spin.setSuffix(" samples")
        self.o2_filter_centered_gaussian_sigma_spin.setValue(
            self._settings.o2_filter.centered_gaussian_sigma_samples
        )

        filter_form.addRow("Enabled", self.o2_filter_enabled_check)
        filter_form.addRow("Type", self.o2_filter_type_combo)
        filter_form.addRow("Preset", self.o2_filter_preset_combo)
        filter_form.addRow("EMA cutoff", self.o2_filter_ema_cutoff_spin)
        filter_form.addRow("Gaussian sigma", self.o2_filter_gaussian_sigma_spin)
        filter_form.addRow("Gaussian tail", self.o2_filter_gaussian_tail_spin)
        filter_form.addRow("Centered Gaussian sigma", self.o2_filter_centered_gaussian_sigma_spin)
        filter_layout.addLayout(filter_form)
        layout.addWidget(filter_card)

        self.o2_filter_enabled_check.toggled.connect(self._update_o2_filter_control_state)
        self.o2_filter_type_combo.currentTextChanged.connect(self._handle_o2_filter_type_changed)
        self.o2_filter_preset_combo.currentTextChanged.connect(self._handle_o2_filter_preset_changed)
        for spin_box in (
            self.o2_filter_ema_cutoff_spin,
            self.o2_filter_gaussian_sigma_spin,
            self.o2_filter_gaussian_tail_spin,
            self.o2_filter_centered_gaussian_sigma_spin,
        ):
            spin_box.valueChanged.connect(self._mark_o2_filter_custom)
        self._update_o2_filter_control_state()

        self._refresh_o2_calibration_state()
        layout.addStretch(1)
        return page

    def _update_o2_filter_control_state(self) -> None:
        if not hasattr(self, "o2_filter_enabled_check"):
            return
        filter_type = self.o2_filter_type_combo.currentText()
        is_ema = filter_type in {O2_FILTER_TYPE_EMA_1, O2_FILTER_TYPE_EMA_2}
        is_one_sided_gaussian = filter_type == O2_FILTER_TYPE_GAUSSIAN
        is_centered_gaussian = filter_type == O2_FILTER_TYPE_CENTERED_GAUSSIAN
        is_fixed_coefficients = filter_type in {O2_FILTER_TYPE_SAVGOL_7, O2_FILTER_TYPE_SAVGOL_9}

        self.o2_filter_type_combo.setEnabled(True)
        self.o2_filter_preset_combo.setEnabled(not is_fixed_coefficients)
        self.o2_filter_ema_cutoff_spin.setEnabled(is_ema)
        self.o2_filter_gaussian_sigma_spin.setEnabled(is_one_sided_gaussian)
        self.o2_filter_gaussian_tail_spin.setEnabled(is_one_sided_gaussian)
        self.o2_filter_centered_gaussian_sigma_spin.setEnabled(is_centered_gaussian)

    def _handle_o2_filter_type_changed(self, *_args: object) -> None:
        self._apply_o2_filter_preset_values()
        self._update_o2_filter_control_state()

    def _handle_o2_filter_preset_changed(self, *_args: object) -> None:
        self._apply_o2_filter_preset_values()
        self._update_o2_filter_control_state()

    def _apply_o2_filter_preset_values(self) -> None:
        if self._syncing_o2_filter_controls:
            return
        if self.o2_filter_preset_combo.currentText() == O2_FILTER_PRESET_CUSTOM:
            return

        effective = effective_o2_filter_preferences(self.selected_o2_filter_preferences)
        self._syncing_o2_filter_controls = True
        try:
            self.o2_filter_ema_cutoff_spin.setValue(effective.ema_cutoff_hz)
            self.o2_filter_gaussian_sigma_spin.setValue(effective.gaussian_sigma_ms)
            self.o2_filter_gaussian_tail_spin.setValue(effective.gaussian_tail_sigma)
            self.o2_filter_centered_gaussian_sigma_spin.setValue(
                effective.centered_gaussian_sigma_samples
            )
        finally:
            self._syncing_o2_filter_controls = False

    def _mark_o2_filter_custom(self, *_args: object) -> None:
        if self._syncing_o2_filter_controls:
            return
        if self.o2_filter_preset_combo.currentText() == O2_FILTER_PRESET_CUSTOM:
            return
        self.o2_filter_preset_combo.setCurrentText(O2_FILTER_PRESET_CUSTOM)

    def _create_engineering_tools_page(self) -> QWidget:
        page, layout = self._page_wrapper()

        overview_card = QFrame()
        overview_card.setObjectName("AccentCard")
        overview_layout = QVBoxLayout(overview_card)
        overview_title = QLabel("Engineering / Tools")
        overview_title.setObjectName("SectionTitle")
        overview_hint = QLabel(
            "Use this page for diagnostics, protocol checks, and flow-development workflows. "
            "These tools are useful during bring-up, validation, and troubleshooting, "
            "but are separated from routine operator settings."
        )
        overview_hint.setObjectName("SectionHint")
        overview_hint.setWordWrap(True)
        overview_layout.addWidget(overview_title)
        overview_layout.addWidget(overview_hint)
        layout.addWidget(overview_card)

        verification_card = QFrame()
        verification_card.setObjectName("AccentCard")
        verification_layout = QVBoxLayout(verification_card)
        verification_title = QLabel("Flow Verification")
        verification_title.setObjectName("SectionTitle")
        verification_hint = QLabel(
            "Open the guided 3 L syringe verification workflow for exhalation and inhalation strokes."
        )
        verification_hint.setObjectName("SectionHint")
        verification_hint.setWordWrap(True)
        verification_layout.addWidget(verification_title)
        verification_layout.addWidget(verification_hint)

        self.flow_verification_status_label = QLabel("")
        self.flow_verification_status_label.setObjectName("SectionHint")
        self.flow_verification_status_label.setWordWrap(True)
        verification_layout.addWidget(self.flow_verification_status_label)

        self.flow_verification_detail_label = QLabel("")
        self.flow_verification_detail_label.setObjectName("SectionHint")
        self.flow_verification_detail_label.setWordWrap(True)
        verification_layout.addWidget(self.flow_verification_detail_label)

        self.flow_verification_history_label = QLabel("")
        self.flow_verification_history_label.setObjectName("SectionHint")
        self.flow_verification_history_label.setWordWrap(True)
        verification_layout.addWidget(self.flow_verification_history_label)

        verification_row = QHBoxLayout()
        self.flow_verification_button = QPushButton("Open Guided Verification")
        self.flow_verification_button.setObjectName("PrimaryButton")
        self.flow_verification_button.setEnabled(self._flow_verification_available)
        self.flow_verification_button.clicked.connect(self._request_flow_verification)
        self.flow_verification_details_button = QPushButton("Show Latest Details")
        self.flow_verification_details_button.setObjectName("SecondaryButton")
        self.flow_verification_details_button.setEnabled(self._flow_verification_summary is not None)
        self.flow_verification_details_button.clicked.connect(self._request_flow_verification_details)
        self.flow_verification_history_button = QPushButton("Show History")
        self.flow_verification_history_button.setObjectName("SecondaryButton")
        self.flow_verification_history_button.setEnabled(bool(self._flow_verification_recent_summaries))
        self.flow_verification_history_button.clicked.connect(self._request_flow_verification_history)
        verification_row.addWidget(self.flow_verification_button)
        verification_row.addWidget(self.flow_verification_details_button)
        verification_row.addWidget(self.flow_verification_history_button)
        verification_row.addStretch(1)
        verification_layout.addLayout(verification_row)
        layout.addWidget(verification_card)

        characterization_card = QFrame()
        characterization_card.setObjectName("SurfaceCard")
        characterization_layout = QVBoxLayout(characterization_card)
        characterization_title = QLabel("Flow Characterization (PoC)")
        characterization_title.setObjectName("SectionTitle")
        characterization_hint = QLabel(
            "Development-only guided capture for raw SDP810 / SDP811 polarity and range handoff analysis."
        )
        characterization_hint.setObjectName("SectionHint")
        characterization_hint.setWordWrap(True)
        characterization_layout.addWidget(characterization_title)
        characterization_layout.addWidget(characterization_hint)

        self.flow_characterization_status_label = QLabel("")
        self.flow_characterization_status_label.setObjectName("SectionHint")
        self.flow_characterization_status_label.setWordWrap(True)
        characterization_layout.addWidget(self.flow_characterization_status_label)

        self.flow_characterization_history_label = QLabel("")
        self.flow_characterization_history_label.setObjectName("SectionHint")
        self.flow_characterization_history_label.setWordWrap(True)
        characterization_layout.addWidget(self.flow_characterization_history_label)

        characterization_row = QHBoxLayout()
        self.flow_characterization_button = QPushButton("Open Characterization PoC")
        self.flow_characterization_button.setObjectName("PrimaryButton")
        self.flow_characterization_button.setEnabled(self._flow_characterization_available)
        self.flow_characterization_button.clicked.connect(self._request_flow_characterization)
        self.flow_characterization_history_button = QPushButton("Show History")
        self.flow_characterization_history_button.setObjectName("SecondaryButton")
        self.flow_characterization_history_button.setEnabled(bool(self._flow_characterization_recent_summaries))
        self.flow_characterization_history_button.clicked.connect(self._request_flow_characterization_history)
        characterization_row.addWidget(self.flow_characterization_button)
        characterization_row.addWidget(self.flow_characterization_history_button)
        characterization_row.addStretch(1)
        characterization_layout.addLayout(characterization_row)
        layout.addWidget(characterization_card)

        action_card = QFrame()
        action_card.setObjectName("SurfaceCard")
        action_layout = QVBoxLayout(action_card)
        action_title = QLabel("Device Diagnostics")
        action_title.setObjectName("SectionTitle")
        action_hint = QLabel(
            "Send on-demand status, capabilities, or ping requests without adding these controls back to the main screen."
        )
        action_hint.setObjectName("SectionHint")
        action_hint.setWordWrap(True)
        action_layout.addWidget(action_title)
        action_layout.addWidget(action_hint)

        action_row = QHBoxLayout()
        self.status_request_button = QPushButton("Get Status")
        self.status_request_button.setObjectName("SecondaryButton")
        self.status_request_button.clicked.connect(
            lambda: self.device_action_requested.emit("get_status")
        )
        self.capabilities_request_button = QPushButton("Get Capabilities")
        self.capabilities_request_button.setObjectName("SecondaryButton")
        self.capabilities_request_button.clicked.connect(
            lambda: self.device_action_requested.emit("get_capabilities")
        )
        self.ping_request_button = QPushButton("Ping")
        self.ping_request_button.setObjectName("SecondaryButton")
        self.ping_request_button.clicked.connect(
            lambda: self.device_action_requested.emit("ping")
        )
        action_row.addWidget(self.status_request_button)
        action_row.addWidget(self.capabilities_request_button)
        action_row.addWidget(self.ping_request_button)
        action_row.addStretch(1)
        action_layout.addLayout(action_row)
        layout.addWidget(action_card)

        self._refresh_flow_verification_state()
        self._refresh_flow_characterization_state()
        layout.addStretch(1)
        return page

    def _create_about_page(self) -> QWidget:
        page, layout = self._page_wrapper()
        card = QFrame()
        card.setObjectName("SurfaceCard")
        card_layout = QVBoxLayout(card)
        title = QLabel(APP_NAME)
        title.setObjectName("SectionTitle")
        copy = QLabel(
            "This prototype exists to confirm screen hierarchy, visual direction, and layout decisions before full implementation."
        )
        copy.setWordWrap(True)
        card_layout.addWidget(title)
        card_layout.addWidget(copy)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _create_recording_directory_field(self) -> QLineEdit:
        field = QLineEdit(self._settings.logging.recording_directory)
        field.setPlaceholderText(str(Path.home() / "Documents" / "ZSS Demo Kit"))
        return field

    def _browse_recording_directory(self) -> None:
        start_dir = self.recording_directory_edit.text().strip() or str(Path.home())
        selected_dir = QFileDialog.getExistingDirectory(self, "Select Recording Directory", start_dir)
        if selected_dir:
            self.recording_directory_edit.setText(selected_dir)

    def _update_mode_page_state(self) -> None:
        requested = self.requested_mode
        if requested == self._current_mode:
            self.mode_status_label.setText(
                f"Current mode is {self._current_mode}. Save will keep the current session type."
            )
            ok_button = self.button_box.button(QDialogButtonBox.Ok)
            if ok_button is not None:
                ok_button.setText("Save Settings")
            return

        self.mode_status_label.setText(
            f"Current mode is {self._current_mode}. Save will request a switch to {requested} mode and reopen the main window in a disconnected state."
        )
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setText("Save and Switch")

    def _calibrate_o2_to_ambient_air(self) -> None:
        if self._current_zirconia_voltage_v is None:
            self._refresh_o2_calibration_state(message="Live zirconia voltage is unavailable.")
            return

        self._pending_o2_air_calibration_voltage_v = float(self._current_zirconia_voltage_v)
        self._pending_o2_calibrated_at_iso = datetime.now().isoformat(timespec="seconds")
        self._refresh_o2_calibration_state(message="Ambient-air O2 calibration staged. Save settings to apply it.")

    def _reset_o2_calibration(self) -> None:
        self._pending_o2_air_calibration_voltage_v = None
        self._pending_o2_calibrated_at_iso = ""
        self._refresh_o2_calibration_state(message="O2 calibration reset is staged. Save settings to apply it.")

    def _update_o2_zero_reference_voltage(self, value: float) -> None:
        self._pending_o2_zero_reference_voltage_v = float(value)
        self._refresh_o2_calibration_state()

    def _refresh_o2_calibration_state(self, message: str | None = None) -> None:
        live_voltage = self._current_zirconia_voltage_v
        if live_voltage is None:
            self.o2_calibration_live_label.setText("Live zirconia voltage: unavailable")
            self.o2_calibrate_button.setEnabled(False)
        else:
            self.o2_calibration_live_label.setText(f"Live zirconia voltage: {live_voltage:0.3f} V")
            self.o2_calibrate_button.setEnabled(True)

        if self._pending_o2_air_calibration_voltage_v is None:
            status_text = (
                "Current calibration state: not calibrated; "
                f"0% anchor {self._pending_o2_zero_reference_voltage_v:0.3f} V"
            )
            if message:
                status_text = f"{status_text}. {message}"
            self.o2_calibration_status_label.setText(status_text)
            self.o2_reset_button.setEnabled(bool(self._settings.o2.air_calibration_voltage_v))
            return

        timestamp_text = self._pending_o2_calibrated_at_iso or "timestamp unavailable"
        status_text = (
            "Current calibration state: "
            f"0% anchor {self._pending_o2_zero_reference_voltage_v:0.3f} V, "
            f"ambient anchor {self._pending_o2_air_calibration_voltage_v:0.3f} V "
            f"({timestamp_text})"
        )
        if message:
            status_text = f"{status_text}. {message}"
        self.o2_calibration_status_label.setText(status_text)
        self.o2_reset_button.setEnabled(True)

    def _refresh_flow_verification_state(self) -> None:
        self.flow_verification_button.setEnabled(self._flow_verification_available)
        self.flow_verification_details_button.setEnabled(self._flow_verification_summary is not None)
        self.flow_verification_history_button.setEnabled(bool(self._flow_verification_recent_summaries))
        if self._flow_verification_summary is None:
            self.flow_verification_status_label.setText("Last result: not verified")
            if self._flow_verification_available:
                self.flow_verification_detail_label.setText(
                    "An expected connected device is available. You can start the guided workflow now."
                )
            else:
                self.flow_verification_detail_label.setText(
                    "Connect an expected device to enable the guided workflow."
                )
            self.flow_verification_history_label.setText("Recent sessions: none")
            return

        summary = self._flow_verification_summary
        self.flow_verification_status_label.setText(
            f"Last result: {summary.result} ({summary.completed_at_iso or 'timestamp unavailable'})"
        )
        self.flow_verification_detail_label.setText(
            f"Criterion: {summary.criterion_version} | "
            f"Exhalation: {summary.exhalation_result or '--'} | "
            f"Inhalation: {summary.inhalation_result or '--'}"
        )
        if not self._flow_verification_recent_summaries:
            self.flow_verification_history_label.setText("Recent sessions: none")
            return
        preview_lines = []
        for item in self._flow_verification_recent_summaries[:3]:
            counts = []
            if item.advisory_count:
                counts.append(f"adv {item.advisory_count}")
            if item.out_of_target_count:
                counts.append(f"oot {item.out_of_target_count}")
            if item.incomplete_count:
                counts.append(f"inc {item.incomplete_count}")
            suffix = "" if not counts else f" [{', '.join(counts)}]"
            preview_lines.append(f"{item.completed_at_iso}: {item.result}{suffix}")
        self.flow_verification_history_label.setText(
            "Recent sessions:\n" + "\n".join(preview_lines)
        )

    def _request_flow_verification(self) -> None:
        self._open_flow_verification_requested = True
        self.accept()

    def _request_flow_verification_details(self) -> None:
        self._show_flow_verification_details_requested = True
        self.accept()

    def _request_flow_verification_history(self) -> None:
        self._show_flow_verification_history_requested = True
        self.accept()

    def _refresh_flow_characterization_state(self) -> None:
        self.flow_characterization_button.setEnabled(self._flow_characterization_available)
        self.flow_characterization_history_button.setEnabled(bool(self._flow_characterization_recent_summaries))
        status_prefix = ""
        if self._flow_characterization_summary is not None:
            summary = self._flow_characterization_summary
            status_prefix = (
                f"Last characterization: {summary.status} "
                f"({summary.completed_at_iso or 'timestamp unavailable'}), "
                f"captures {summary.completed_capture_steps}/{len(FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)}, "
                f"polarity {summary.polarity_hint}."
            )
        if self._flow_characterization_available:
            self.flow_characterization_status_label.setText(
                (
                    status_prefix + "\n"
                    if status_prefix
                    else ""
                )
                + "An expected connected device is available. Wired mode is recommended for raw dual-SDP capture."
            )
        else:
            self.flow_characterization_status_label.setText(
                (
                    status_prefix + "\n"
                    if status_prefix
                    else ""
                )
                + "Connect an expected device to enable the characterization PoC."
            )
        if not self._flow_characterization_recent_summaries:
            self.flow_characterization_history_label.setText("Recent characterization sessions: none")
            return
        preview_lines = []
        for item in self._flow_characterization_recent_summaries[:3]:
            rough = "--" if item.rough_gain_multiplier is None else f"{item.rough_gain_multiplier:0.2f}x"
            preview_lines.append(
                f"{item.completed_at_iso}: {item.status}, captures "
                f"{item.completed_capture_steps}/{len(FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)}, rough {rough}"
            )
        self.flow_characterization_history_label.setText(
            "Recent characterization sessions:\n" + "\n".join(preview_lines)
        )

    def _request_flow_characterization(self) -> None:
        self._open_flow_characterization_requested = True
        self.accept()

    def _request_flow_characterization_history(self) -> None:
        self._show_flow_characterization_history_requested = True
        self.accept()


class FlowCharacterizationDialog(QDialog):
    def __init__(
        self,
        controller: FlowCharacterizationController,
        persistence: FlowCharacterizationPersistence,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.persistence = persistence
        self.saved_session_result: FlowCharacterizationSaveResult | None = None
        self.setWindowTitle("Flow Characterization PoC")
        self.resize(940, 780)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.header_title = QLabel("Flow Characterization PoC")
        self.header_title.setObjectName("SectionTitle")
        self.header_subtitle = QLabel("")
        self.header_subtitle.setObjectName("SectionHint")
        self.header_subtitle.setWordWrap(True)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("SectionHint")
        self.section_badge = QLabel("")
        self.section_badge.setObjectName("RecordingStateBadge")
        header = QFrame()
        header.setObjectName("AccentCard")
        header_layout = QVBoxLayout(header)
        badge_row = QHBoxLayout()
        badge_row.addWidget(self.section_badge, 0)
        badge_row.addStretch(1)
        header_layout.addWidget(self.header_title)
        header_layout.addWidget(self.header_subtitle)
        header_layout.addWidget(self.progress_label)
        header_layout.addLayout(badge_row)
        layout.addWidget(header)

        self.instruction_card = QFrame()
        self.instruction_card.setObjectName("SurfaceCard")
        instruction_layout = QVBoxLayout(self.instruction_card)
        self.instruction_label = QLabel("")
        self.instruction_label.setObjectName("SectionHint")
        self.instruction_label.setWordWrap(True)
        self.message_label = QLabel("")
        self.message_label.setObjectName("SectionHint")
        self.message_label.setWordWrap(True)
        instruction_layout.addWidget(self.instruction_label)
        instruction_layout.addWidget(self.message_label)
        layout.addWidget(self.instruction_card)

        self.live_card = QFrame()
        self.live_card.setObjectName("SurfaceCard")
        live_layout = QGridLayout(self.live_card)
        live_layout.setHorizontalSpacing(10)
        live_layout.setVerticalSpacing(8)
        self.capture_state_label = QLabel("--")
        self.live_sample_count_label = QLabel("--")
        self.live_flow_label = QLabel("--")
        self.live_source_label = QLabel("--")
        self.live_selected_dp_label = QLabel("--")
        self.live_sdp811_label = QLabel("--")
        self.live_sdp810_label = QLabel("--")
        live_rows = [
            ("Capture state", self.capture_state_label),
            ("Current samples", self.live_sample_count_label),
            ("Derived flow", self.live_flow_label),
            ("Selected source", self.live_source_label),
            ("Selected DP", self.live_selected_dp_label),
            ("SDP811", self.live_sdp811_label),
            ("SDP810", self.live_sdp810_label),
        ]
        for row_index, (name, label) in enumerate(live_rows):
            live_layout.addWidget(QLabel(name), row_index, 0)
            live_layout.addWidget(label, row_index, 1)
        layout.addWidget(self.live_card)

        self.result_card = QFrame()
        self.result_card.setObjectName("SurfaceCard")
        result_layout = QGridLayout(self.result_card)
        result_layout.setHorizontalSpacing(10)
        result_layout.setVerticalSpacing(8)
        self.result_status_label = QLabel("--")
        self.result_duration_label = QLabel("--")
        self.result_selected_label = QLabel("--")
        self.result_sdp810_label = QLabel("--")
        self.result_sdp811_label = QLabel("--")
        self.result_polarity_label = QLabel("--")
        self.result_sources_label = QLabel("--")
        self.result_sources_label.setWordWrap(True)
        result_rows = [
            ("Attempt", self.result_status_label),
            ("Duration", self.result_duration_label),
            ("Selected peak abs", self.result_selected_label),
            ("SDP810 peak abs", self.result_sdp810_label),
            ("SDP811 peak abs", self.result_sdp811_label),
            ("Polarity", self.result_polarity_label),
            ("Selected source counts", self.result_sources_label),
        ]
        for row_index, (name, label) in enumerate(result_rows):
            result_layout.addWidget(QLabel(name), row_index, 0)
            result_layout.addWidget(label, row_index, 1)
        layout.addWidget(self.result_card)

        self.review_card = QFrame()
        self.review_card.setObjectName("SurfaceCard")
        review_layout = QVBoxLayout(self.review_card)
        self.review_guidance_label = QLabel("--")
        self.review_guidance_label.setObjectName("SectionHint")
        self.review_guidance_label.setWordWrap(True)
        review_layout.addWidget(self.review_guidance_label)

        self.review_rows_labels: dict[str, dict[str, QLabel]] = {}
        review_table = QGridLayout()
        review_table.setHorizontalSpacing(10)
        review_table.setVerticalSpacing(6)
        headers = ["Step", "Status", "Samples", "Selected", "SDP810", "SDP811", "Polarity"]
        for column_index, header_text in enumerate(headers):
            header_label = QLabel(header_text)
            header_label.setObjectName("SectionTitle")
            review_table.addWidget(header_label, 0, column_index)
        row_index = 1
        for step in FLOW_CHARACTERIZATION_STEPS:
            if step.kind != "capture":
                continue
            review_table.addWidget(QLabel(step.title), row_index, 0)
            status_value = QLabel("--")
            samples_value = QLabel("--")
            selected_value = QLabel("--")
            sdp810_value = QLabel("--")
            sdp811_value = QLabel("--")
            polarity_value = QLabel("--")
            review_table.addWidget(status_value, row_index, 1)
            review_table.addWidget(samples_value, row_index, 2)
            review_table.addWidget(selected_value, row_index, 3)
            review_table.addWidget(sdp810_value, row_index, 4)
            review_table.addWidget(sdp811_value, row_index, 5)
            review_table.addWidget(polarity_value, row_index, 6)
            self.review_rows_labels[step.step_id] = {
                "status": status_value,
                "samples": samples_value,
                "selected": selected_value,
                "sdp810": sdp810_value,
                "sdp811": sdp811_value,
                "polarity": polarity_value,
            }
            row_index += 1
        review_layout.addLayout(review_table)

        note_title = QLabel("Operator Note")
        note_title.setObjectName("SectionTitle")
        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Optional note for this characterization session")
        self.note_edit.setMinimumHeight(90)
        review_layout.addWidget(note_title)
        review_layout.addWidget(self.note_edit)
        layout.addWidget(self.review_card)

        button_row = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("SecondaryButton")
        self.start_button = QPushButton("Start Capture")
        self.start_button.setObjectName("PrimaryButton")
        self.finish_button = QPushButton("Finish Step")
        self.finish_button.setObjectName("PrimaryButton")
        self.retry_button = QPushButton("Retry")
        self.retry_button.setObjectName("SecondaryButton")
        self.continue_button = QPushButton("Accept and continue")
        self.continue_button.setObjectName("PrimaryButton")
        self.skip_button = QPushButton("Skip")
        self.skip_button.setObjectName("SecondaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.save_button = QPushButton("Save Characterization")
        self.save_button.setObjectName("PrimaryButton")
        button_row.addWidget(self.back_button)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.finish_button)
        button_row.addWidget(self.retry_button)
        button_row.addWidget(self.continue_button)
        button_row.addWidget(self.skip_button)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.save_button)
        layout.addLayout(button_row)

        self.back_button.clicked.connect(self.controller.go_back)
        self.start_button.clicked.connect(self.controller.start_capture)
        self.finish_button.clicked.connect(self.controller.finish_capture)
        self.retry_button.clicked.connect(self.controller.retry_step)
        self.continue_button.clicked.connect(self.controller.continue_step)
        self.skip_button.clicked.connect(self.controller.skip_step)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save_session)
        self.controller.updated.connect(self._refresh)
        self.controller.session_saved.connect(self._on_session_saved)
        self._refresh()

    def _save_session(self) -> None:
        self.controller.set_operator_note(self.note_edit.toPlainText())
        self.saved_session_result = self.controller.save_session(self.persistence)
        self.accept()

    def _on_session_saved(self, result: object) -> None:
        if isinstance(result, FlowCharacterizationSaveResult):
            self.saved_session_result = result

    def _refresh(self) -> None:
        snapshot = self.controller.snapshot()
        step = snapshot["step"]
        self.header_title.setText(step.title)
        self.header_subtitle.setText(step.instruction)
        self.progress_label.setText(f"Step {snapshot['step_index']} of {snapshot['step_total']}")
        self.section_badge.setText(step.section)
        self.instruction_label.setText(step.instruction)
        self.message_label.setText(snapshot["message"])

        self.capture_state_label.setText(str(snapshot["capture_state"]))
        self.live_sample_count_label.setText(str(snapshot["capturing_sample_count"]))
        live_flow = snapshot["live_flow_lpm"]
        self.live_flow_label.setText("--" if live_flow is None else f"{live_flow:+0.3f} L/min")
        self.live_source_label.setText(snapshot["live_selected_source"] or "--")
        self.live_selected_dp_label.setText(
            "--"
            if snapshot["live_selected_dp_pa"] is None
            else f"{snapshot['live_selected_dp_pa']:+0.3f} Pa"
        )
        self.live_sdp811_label.setText(
            "--"
            if snapshot["live_high_range_pa"] is None
            else f"{snapshot['live_high_range_pa']:+0.3f} Pa"
        )
        self.live_sdp810_label.setText(
            "--"
            if snapshot["live_low_range_pa"] is None
            else f"{snapshot['live_low_range_pa']:+0.3f} Pa"
        )

        self._refresh_result_card(snapshot["current_attempt"], snapshot["current_summary"])
        self._refresh_review(snapshot)

        is_review = step.kind == "review"
        is_overview = step.kind == "overview"
        is_capture = step.kind == "capture"
        self.live_card.setVisible(is_capture)
        self.result_card.setVisible(is_capture)
        self.review_card.setVisible(is_review)
        self.start_button.setVisible(is_capture)
        self.finish_button.setVisible(is_capture)
        self.retry_button.setVisible(is_capture)
        self.skip_button.setVisible(is_capture)
        self.continue_button.setVisible(not is_review)
        self.save_button.setVisible(is_review)

        self.back_button.setEnabled(bool(snapshot["can_back"]))
        self.start_button.setEnabled(bool(snapshot["can_start"]))
        self.finish_button.setEnabled(bool(snapshot["can_finish"]))
        self.retry_button.setEnabled(bool(snapshot["can_retry"]))
        self.skip_button.setEnabled(bool(snapshot["can_skip"]))
        self.continue_button.setEnabled(bool(snapshot["can_continue"]))
        self.save_button.setEnabled(bool(snapshot["can_save"]))

        if is_overview:
            self.continue_button.setText("Start Characterization")
        else:
            self.continue_button.setText("Accept and continue")

    def _refresh_result_card(self, attempt: object, summary: object) -> None:
        if not isinstance(attempt, FlowCharacterizationAttempt):
            for label in (
                self.result_status_label,
                self.result_duration_label,
                self.result_selected_label,
                self.result_sdp810_label,
                self.result_sdp811_label,
                self.result_polarity_label,
                self.result_sources_label,
            ):
                label.setText("--")
            return

        self.result_status_label.setText(
            f"{attempt.operator_event} #{attempt.attempt_index} ({attempt.sample_count} samples)"
        )
        self.result_duration_label.setText(f"{attempt.duration_s:0.2f} s")
        if not isinstance(summary, FlowCharacterizationAttemptSummary):
            self.result_selected_label.setText("--")
            self.result_sdp810_label.setText("--")
            self.result_sdp811_label.setText("--")
            self.result_polarity_label.setText("--")
            self.result_sources_label.setText("--")
            return
        self.result_duration_label.setText(f"{summary.duration_s:0.2f} s")
        self.result_selected_label.setText(format_optional(summary.selected_peak_abs_pa, "{:0.3f} Pa"))
        self.result_sdp810_label.setText(format_optional(summary.sdp810_peak_abs_pa, "{:0.3f} Pa"))
        self.result_sdp811_label.setText(format_optional(summary.sdp811_peak_abs_pa, "{:0.3f} Pa"))
        self.result_polarity_label.setText(
            f"selected={summary.selected_polarity}, SDP810={summary.sdp810_polarity}, SDP811={summary.sdp811_polarity}"
        )
        if summary.source_counts:
            self.result_sources_label.setText(
                ", ".join(f"{source}:{count}" for source, count in summary.source_counts.items())
            )
        else:
            self.result_sources_label.setText("--")

    def _refresh_review(self, snapshot: dict[str, object]) -> None:
        self.review_guidance_label.setText("\n".join(snapshot["analysis_lines"]))
        for row in snapshot["review_rows"]:
            labels = self.review_rows_labels.get(row["step_id"])
            if labels is None:
                continue
            labels["status"].setText(row["status"] or "--")
            labels["samples"].setText("--" if row["sample_count"] is None else str(row["sample_count"]))
            labels["selected"].setText(
                "--" if row["selected_peak_abs_pa"] is None else f"{row['selected_peak_abs_pa']:0.3f} Pa"
            )
            labels["sdp810"].setText(
                "--" if row["sdp810_peak_abs_pa"] is None else f"{row['sdp810_peak_abs_pa']:0.3f} Pa"
            )
            labels["sdp811"].setText(
                "--" if row["sdp811_peak_abs_pa"] is None else f"{row['sdp811_peak_abs_pa']:0.3f} Pa"
            )
            labels["polarity"].setText(row["polarity"] or "--")


class FlowVerificationDetailsDialog(QDialog):
    def __init__(self, session: VerificationSession, session_path: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Latest Flow Verification Details")
        self.resize(920, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = dialog_header(
            "Latest Flow Verification Details",
            "Review the latest saved verification session summary and stroke-level results.",
        )
        layout.addWidget(header)

        summary_card = QFrame()
        summary_card.setObjectName("AccentCard")
        summary_layout = QGridLayout(summary_card)
        summary_layout.setHorizontalSpacing(12)
        summary_layout.setVerticalSpacing(8)
        summary_rows = [
            ("Overall", session.overall_result or "--"),
            ("Exhalation", session.exhalation_result or "--"),
            ("Inhalation", session.inhalation_result or "--"),
            ("Completed at", session.completed_at_iso or "--"),
            ("Device", session.device_identifier or "--"),
            ("Transport", session.transport_type or "--"),
            ("Protocol", session.protocol_version or "--"),
            ("Criterion", session.criterion_version or "--"),
            ("Saved path", str(session_path) if session_path is not None else "--"),
        ]
        for row_index, (name, value) in enumerate(summary_rows):
            summary_layout.addWidget(QLabel(name), row_index, 0)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            summary_layout.addWidget(value_label, row_index, 1)
        layout.addWidget(summary_card)

        zero_card = QFrame()
        zero_card.setObjectName("SurfaceCard")
        zero_layout = QGridLayout(zero_card)
        zero_layout.setHorizontalSpacing(12)
        zero_layout.setVerticalSpacing(8)
        zero_result = session.zero_check_result
        zero_rows = [
            ("Zero status", "--" if zero_result is None else zero_result.status),
            ("Mean flow", format_optional(zero_result.mean_flow_lpm, "{:+0.3f} L/min") if zero_result else "--"),
            ("Peak abs flow", format_optional(zero_result.peak_abs_flow_lpm, "{:0.3f} L/min") if zero_result else "--"),
            ("Selected DP mean", format_optional(zero_result.selected_dp_mean_pa, "{:+0.3f} Pa") if zero_result else "--"),
            ("SDP811 mean", format_optional(zero_result.sdp811_mean_pa, "{:+0.3f} Pa") if zero_result else "--"),
            ("SDP810 mean", format_optional(zero_result.sdp810_mean_pa, "{:+0.3f} Pa") if zero_result else "--"),
            ("Warnings", "--" if zero_result is None or not zero_result.warning_flags else ", ".join(zero_result.warning_flags)),
        ]
        for row_index, (name, value) in enumerate(zero_rows):
            zero_layout.addWidget(QLabel(name), row_index, 0)
            value_label = QLabel(value)
            value_label.setWordWrap(True)
            zero_layout.addWidget(value_label, row_index, 1)
        layout.addWidget(zero_card)

        stroke_card = QFrame()
        stroke_card.setObjectName("SurfaceCard")
        stroke_layout = QVBoxLayout(stroke_card)
        stroke_title = QLabel("Stroke Results")
        stroke_title.setObjectName("SectionTitle")
        stroke_layout.addWidget(stroke_title)
        stroke_table = QGridLayout()
        stroke_table.setHorizontalSpacing(10)
        stroke_table.setVerticalSpacing(6)
        headers = ["Step", "Result", "Recovered", "Error %", "Peak flow", "Source", "Switches", "Warnings"]
        for column_index, header_text in enumerate(headers):
            header_label = QLabel(header_text)
            header_label.setObjectName("SectionTitle")
            stroke_table.addWidget(header_label, 0, column_index)
        for row_index, result in enumerate(session.stroke_results, start=1):
            values = [
                _format_step_label(result),
                result.result_status or "--",
                f"{result.recovered_volume_l:0.3f} L",
                f"{result.volume_error_percent:+0.2f} %",
                f"{result.peak_flow_lps:0.3f} L/s",
                result.dominant_source or "--",
                str(result.source_switch_count),
                ", ".join(result.warning_flags) if result.warning_flags else "--",
            ]
            for column_index, value in enumerate(values):
                label = QLabel(value)
                label.setWordWrap(True)
                stroke_table.addWidget(label, row_index, column_index)
        stroke_layout.addLayout(stroke_table)
        layout.addWidget(stroke_card)

        note_card = QFrame()
        note_card.setObjectName("SurfaceCard")
        note_layout = QVBoxLayout(note_card)
        note_title = QLabel("Operator Note")
        note_title.setObjectName("SectionTitle")
        note_value = QLabel(session.operator_note or "--")
        note_value.setWordWrap(True)
        note_layout.addWidget(note_title)
        note_layout.addWidget(note_value)
        layout.addWidget(note_card)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        style_dialog_buttons(button_box)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class FlowVerificationDialog(QDialog):
    def __init__(
        self,
        controller: FlowVerificationController,
        persistence: FlowVerificationPersistence,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.persistence = persistence
        self.saved_session_path: Path | None = None
        self.setWindowTitle("Flow Verification")
        self.resize(900, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.header_title = QLabel("Flow Verification")
        self.header_title.setObjectName("SectionTitle")
        self.header_subtitle = QLabel("")
        self.header_subtitle.setObjectName("SectionHint")
        self.header_subtitle.setWordWrap(True)
        self.progress_label = QLabel("")
        self.progress_label.setObjectName("SectionHint")
        self.section_badge = QLabel("")
        self.section_badge.setObjectName("RecordingStateBadge")
        header = QFrame()
        header.setObjectName("AccentCard")
        header_layout = QVBoxLayout(header)
        badge_row = QHBoxLayout()
        badge_row.addWidget(self.section_badge, 0)
        badge_row.addStretch(1)
        header_layout.addWidget(self.header_title)
        header_layout.addWidget(self.header_subtitle)
        header_layout.addWidget(self.progress_label)
        header_layout.addLayout(badge_row)
        layout.addWidget(header)

        self.instruction_card = QFrame()
        self.instruction_card.setObjectName("SurfaceCard")
        instruction_layout = QVBoxLayout(self.instruction_card)
        self.instruction_label = QLabel("")
        self.instruction_label.setObjectName("SectionHint")
        self.instruction_label.setWordWrap(True)
        self.message_label = QLabel("")
        self.message_label.setObjectName("SectionHint")
        self.message_label.setWordWrap(True)
        instruction_layout.addWidget(self.instruction_label)
        instruction_layout.addWidget(self.message_label)
        layout.addWidget(self.instruction_card)

        self.live_card = QFrame()
        self.live_card.setObjectName("SurfaceCard")
        live_layout = QGridLayout(self.live_card)
        live_layout.setHorizontalSpacing(10)
        live_layout.setVerticalSpacing(8)
        self.capture_state_label = QLabel("--")
        self.live_flow_label = QLabel("--")
        self.live_volume_label = QLabel("--")
        self.live_source_label = QLabel("--")
        self.live_selected_dp_label = QLabel("--")
        self.live_sdp811_label = QLabel("--")
        self.live_sdp810_label = QLabel("--")
        live_rows = [
            ("Capture state", self.capture_state_label),
            ("Live flow", self.live_flow_label),
            ("Integrated volume", self.live_volume_label),
            ("Selected source", self.live_source_label),
            ("Selected DP", self.live_selected_dp_label),
            ("SDP811", self.live_sdp811_label),
            ("SDP810", self.live_sdp810_label),
        ]
        for row_index, (name, label) in enumerate(live_rows):
            live_layout.addWidget(QLabel(name), row_index, 0)
            live_layout.addWidget(label, row_index, 1)
        layout.addWidget(self.live_card)

        self.result_card = QFrame()
        self.result_card.setObjectName("SurfaceCard")
        result_layout = QGridLayout(self.result_card)
        result_layout.setHorizontalSpacing(10)
        result_layout.setVerticalSpacing(8)
        self.result_status_label = QLabel("--")
        self.result_volume_label = QLabel("--")
        self.result_error_label = QLabel("--")
        self.result_peak_label = QLabel("--")
        self.result_duration_label = QLabel("--")
        self.result_source_label = QLabel("--")
        self.result_warning_label = QLabel("--")
        self.result_warning_label.setWordWrap(True)
        result_rows = [
            ("Result", self.result_status_label),
            ("Recovered volume", self.result_volume_label),
            ("Volume error", self.result_error_label),
            ("Peak flow", self.result_peak_label),
            ("Stroke duration", self.result_duration_label),
            ("Dominant source", self.result_source_label),
            ("Warnings", self.result_warning_label),
        ]
        for row_index, (name, label) in enumerate(result_rows):
            result_layout.addWidget(QLabel(name), row_index, 0)
            result_layout.addWidget(label, row_index, 1)
        layout.addWidget(self.result_card)

        self.review_card = QFrame()
        self.review_card.setObjectName("SurfaceCard")
        review_layout = QVBoxLayout(self.review_card)
        summary_grid = QGridLayout()
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(8)
        self.review_zero_label = QLabel("--")
        self.review_exhalation_label = QLabel("--")
        self.review_inhalation_label = QLabel("--")
        self.review_overall_label = QLabel("--")
        self.review_guidance_label = QLabel("--")
        self.review_guidance_label.setObjectName("SectionHint")
        self.review_guidance_label.setWordWrap(True)
        for row_index, (name, label) in enumerate(
            [
                ("Zero Check", self.review_zero_label),
                ("Exhalation", self.review_exhalation_label),
                ("Inhalation", self.review_inhalation_label),
                ("Overall", self.review_overall_label),
            ]
        ):
            summary_grid.addWidget(QLabel(name), row_index, 0)
            summary_grid.addWidget(label, row_index, 1)
        review_layout.addLayout(summary_grid)
        review_layout.addWidget(self.review_guidance_label)

        self.review_rows_labels: dict[str, dict[str, QLabel]] = {}
        review_table = QGridLayout()
        review_table.setHorizontalSpacing(10)
        review_table.setVerticalSpacing(6)
        headers = ["Step", "Result", "Recovered", "Error %", "Peak flow", "Source"]
        for column_index, header_text in enumerate(headers):
            header_label = QLabel(header_text)
            header_label.setObjectName("SectionTitle")
            review_table.addWidget(header_label, 0, column_index)
        for row_index, step in enumerate(FLOW_VERIFICATION_STEPS, start=1):
            if step.kind != "stroke":
                continue
            review_table.addWidget(QLabel(step.title), row_index, 0)
            result_value = QLabel("--")
            recovered_value = QLabel("--")
            error_value = QLabel("--")
            peak_value = QLabel("--")
            source_value = QLabel("--")
            review_table.addWidget(result_value, row_index, 1)
            review_table.addWidget(recovered_value, row_index, 2)
            review_table.addWidget(error_value, row_index, 3)
            review_table.addWidget(peak_value, row_index, 4)
            review_table.addWidget(source_value, row_index, 5)
            self.review_rows_labels[step.step_id] = {
                "result": result_value,
                "recovered": recovered_value,
                "error": error_value,
                "peak": peak_value,
                "source": source_value,
            }
        review_layout.addLayout(review_table)

        note_title = QLabel("Operator Note")
        note_title.setObjectName("SectionTitle")
        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Optional note for this verification session")
        self.note_edit.setMinimumHeight(110)
        review_layout.addWidget(note_title)
        review_layout.addWidget(self.note_edit)
        layout.addWidget(self.review_card)

        button_row = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.setObjectName("SecondaryButton")
        self.retry_button = QPushButton("Retry")
        self.retry_button.setObjectName("SecondaryButton")
        self.continue_button = QPushButton("Accept and continue")
        self.continue_button.setObjectName("PrimaryButton")
        self.skip_button = QPushButton("Skip")
        self.skip_button.setObjectName("SecondaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.save_button = QPushButton("Save Verification")
        self.save_button.setObjectName("PrimaryButton")
        button_row.addWidget(self.back_button)
        button_row.addWidget(self.retry_button)
        button_row.addWidget(self.continue_button)
        button_row.addWidget(self.skip_button)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.save_button)
        layout.addLayout(button_row)

        self.back_button.clicked.connect(self.controller.go_back)
        self.retry_button.clicked.connect(self.controller.retry_step)
        self.continue_button.clicked.connect(self.controller.continue_step)
        self.skip_button.clicked.connect(self.controller.skip_step)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save_session)
        self.controller.updated.connect(self._refresh)
        self.controller.session_saved.connect(self._on_session_saved)
        self._refresh()

    def _save_session(self) -> None:
        self.controller.set_operator_note(self.note_edit.toPlainText())
        self.saved_session_path = self.controller.save_session(self.persistence)
        self.accept()

    def _on_session_saved(self, path: object) -> None:
        if isinstance(path, Path):
            self.saved_session_path = path

    def _refresh(self) -> None:
        snapshot = self.controller.snapshot()
        step = snapshot["step"]
        self.header_title.setText(step.title)
        self.header_subtitle.setText(step.instruction)
        self.progress_label.setText(f"Step {snapshot['step_index']} of {snapshot['step_total']}")
        self.section_badge.setText(step.section)
        self.instruction_label.setText(step.instruction)
        self.message_label.setText(snapshot["message"])

        self.capture_state_label.setText(str(snapshot["capture_state"]))
        live_flow = snapshot["live_flow_lpm"]
        self.live_flow_label.setText("--" if live_flow is None else f"{live_flow:+0.3f} L/min")
        current_result = snapshot["current_result"]
        integrated_volume = "--"
        if isinstance(current_result, VerificationStrokeResult):
            integrated_volume = f"{current_result.recovered_volume_l:0.3f} L"
        self.live_volume_label.setText(integrated_volume)
        self.live_source_label.setText(snapshot["live_selected_source"] or "--")
        self.live_selected_dp_label.setText(
            "--"
            if snapshot["live_selected_dp_pa"] is None
            else f"{snapshot['live_selected_dp_pa']:+0.3f} Pa"
        )
        self.live_sdp811_label.setText(
            "--"
            if snapshot["live_high_range_pa"] is None
            else f"{snapshot['live_high_range_pa']:+0.3f} Pa"
        )
        self.live_sdp810_label.setText(
            "--"
            if snapshot["live_low_range_pa"] is None
            else f"{snapshot['live_low_range_pa']:+0.3f} Pa"
        )

        self._refresh_result_card(current_result)
        self._refresh_review(snapshot)

        is_review = step.kind == "review"
        is_overview = step.kind == "overview"
        self.live_card.setVisible(not is_review and not is_overview)
        self.result_card.setVisible(not is_review and not is_overview)
        self.review_card.setVisible(is_review)
        self.retry_button.setVisible(step.kind in {"zero", "stroke"})
        self.skip_button.setVisible(step.kind in {"zero", "stroke"})
        self.continue_button.setVisible(not is_review)
        self.save_button.setVisible(is_review)

        self.back_button.setEnabled(bool(snapshot["can_back"]))
        self.retry_button.setEnabled(bool(snapshot["can_retry"]))
        self.skip_button.setEnabled(bool(snapshot["can_skip"]))
        self.continue_button.setEnabled(bool(snapshot["can_continue"]))
        self.save_button.setEnabled(bool(snapshot["can_save"]))

        if is_overview:
            self.continue_button.setText("Start Verification")
        else:
            self.continue_button.setText("Accept and continue")

    def _refresh_result_card(self, current_result: object) -> None:
        if isinstance(current_result, ZeroCheckResult):
            self.result_status_label.setText(current_result.status)
            self.result_volume_label.setText(f"{current_result.mean_flow_lpm:+0.3f} L/min")
            self.result_error_label.setText(
                f"Peak abs flow: {current_result.peak_abs_flow_lpm:0.3f} L/min"
            )
            self.result_peak_label.setText(
                "--"
                if current_result.sdp811_mean_pa is None
                else f"SDP811 mean: {current_result.sdp811_mean_pa:+0.3f} Pa"
            )
            self.result_duration_label.setText(
                "--"
                if current_result.sdp810_mean_pa is None
                else f"SDP810 mean: {current_result.sdp810_mean_pa:+0.3f} Pa"
            )
            self.result_source_label.setText(
                "--"
                if current_result.selected_dp_mean_pa is None
                else f"Selected mean: {current_result.selected_dp_mean_pa:+0.3f} Pa"
            )
            self.result_warning_label.setText(
                "--" if not current_result.warning_flags else ", ".join(current_result.warning_flags)
            )
            return

        if isinstance(current_result, VerificationStrokeResult):
            self.result_status_label.setText(current_result.result_status)
            self.result_volume_label.setText(f"{current_result.recovered_volume_l:0.3f} L")
            self.result_error_label.setText(f"{current_result.volume_error_percent:+0.2f} %")
            self.result_peak_label.setText(f"{current_result.peak_flow_lps:0.3f} L/s")
            self.result_duration_label.setText(f"{current_result.stroke_duration_s:0.2f} s")
            self.result_source_label.setText(current_result.dominant_source or "--")
            self.result_warning_label.setText(
                "--" if not current_result.warning_flags else ", ".join(current_result.warning_flags)
            )
            return

        for label in (
            self.result_status_label,
            self.result_volume_label,
            self.result_error_label,
            self.result_peak_label,
            self.result_duration_label,
            self.result_source_label,
            self.result_warning_label,
        ):
            label.setText("--")

    def _refresh_review(self, snapshot: dict[str, object]) -> None:
        zero_result = snapshot["zero_result"]
        if isinstance(zero_result, ZeroCheckResult):
            self.review_zero_label.setText(zero_result.status)
        else:
            self.review_zero_label.setText("--")
        self.review_exhalation_label.setText(str(snapshot["exhalation_result"]))
        self.review_inhalation_label.setText(str(snapshot["inhalation_result"]))
        self.review_overall_label.setText(str(snapshot["overall_result"]))
        self.review_guidance_label.setText(str(snapshot["review_guidance"]))

        for row in snapshot["review_rows"]:
            labels = self.review_rows_labels.get(row["step_id"])
            if labels is None:
                continue
            labels["result"].setText(row["status"] or "--")
            labels["recovered"].setText(
                "--" if row["recovered_volume_l"] is None else f"{row['recovered_volume_l']:0.3f} L"
            )
            labels["error"].setText(
                "--" if row["error_percent"] is None else f"{row['error_percent']:+0.2f} %"
            )
            labels["peak"].setText(
                "--" if row["peak_flow_lps"] is None else f"{row['peak_flow_lps']:0.3f} L/s"
            )
            labels["source"].setText(row["source"] or "--")


def _format_step_label(result: VerificationStrokeResult) -> str:
    direction = "Exh" if result.direction == "exhalation" else "Inh"
    band = result.speed_band.capitalize()
    return f"{direction} {band}"
