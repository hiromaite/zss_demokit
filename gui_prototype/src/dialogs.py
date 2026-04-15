from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app_metadata import APP_NAME
from app_state import AppSettings
from protocol_constants import (
    BLE_MODE,
    DERIVED_METRIC_POLICY_ID,
    PROTOCOL_VERSION_TEXT,
    WIRED_DEFAULT_BAUDRATE,
    WIRED_DEFAULT_LINE_SETTINGS,
    WIRED_MODE,
)
from recording_io import find_partial_recordings, summarize_partial_recordings


def _dialog_header(title: str, subtitle: str) -> QFrame:
    header = QFrame()
    header.setObjectName("AccentCard")
    header_layout = QVBoxLayout(header)
    title_label = QLabel(title)
    title_label.setObjectName("SectionTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("SectionHint")
    subtitle_label.setWordWrap(True)
    header_layout.addWidget(title_label)
    header_layout.addWidget(subtitle_label)
    return header


def _style_dialog_buttons(button_box: QDialogButtonBox) -> None:
    ok_button = button_box.button(QDialogButtonBox.Ok)
    cancel_button = button_box.button(QDialogButtonBox.Cancel)
    if ok_button is not None:
        ok_button.setObjectName("PrimaryButton")
    if cancel_button is not None:
        cancel_button.setObjectName("SecondaryButton")


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
            _dialog_header(
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
        _style_dialog_buttons(button_box)
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
        _style_dialog_buttons(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
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
            "These settings are persisted locally and restored when the app starts again."
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
        for label in ["Mode", "Plot", "Logging", "Advanced", "About"]:
            QListWidgetItem(label, self.nav)
        self.nav.setCurrentRow(0)
        shell.addWidget(self.nav, 0)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._create_mode_page())
        self.stack.addWidget(self._create_plot_page())
        self.stack.addWidget(self._create_logging_page())
        self.stack.addWidget(self._create_advanced_page())
        self.stack.addWidget(self._create_about_page())
        shell.addWidget(self.stack, 1)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        button_box = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        _style_dialog_buttons(button_box)
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

    def _page_wrapper(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        return page, layout

    def _create_mode_page(self) -> QWidget:
        page, layout = self._page_wrapper()

        card = QFrame()
        card.setObjectName("AccentCard")
        card_layout = QVBoxLayout(card)
        title = QLabel("Mode")
        title.setObjectName("SectionTitle")
        hint = QLabel("Choose the session context shown by the main window.")
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

        self.mode_status_label = QLabel("")
        self.mode_status_label.setObjectName("ModeStatusLabel")
        self.mode_status_label.setWordWrap(True)

        card_layout.addWidget(self.ble_mode_radio)
        card_layout.addWidget(self.wired_mode_radio)
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
        self.default_plot_combo.addItems(["Zirconia", "Heater", "Flow"])
        self.default_plot_combo.setCurrentText(self._settings.plot.selected_plot)
        form.addRow("Default time span", self.default_time_span_combo)
        form.addRow("Axis mode", self.axis_mode_combo)
        form.addRow("Selected plot", self.default_plot_combo)
        form.addRow("Auto scale", self.auto_scale_check)
        form.addRow("Refresh policy", QLabel("Timer-driven, 150 ms target"))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _create_logging_page(self) -> QWidget:
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

    def _create_advanced_page(self) -> QWidget:
        page, layout = self._page_wrapper()
        card = QFrame()
        card.setObjectName("SurfaceCard")
        form = QFormLayout(card)
        form.addRow("Protocol family", QLabel(f"v{PROTOCOL_VERSION_TEXT} prototype"))
        form.addRow("Serial defaults", QLabel(f"{WIRED_DEFAULT_BAUDRATE} baud / {WIRED_DEFAULT_LINE_SETTINGS}"))
        form.addRow("BLE identity policy", QLabel("Keep existing device name and UUIDs"))
        layout.addWidget(card)
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
        if requested == self._settings.last_mode:
            self.mode_status_label.setText(
                f"Current mode is {self._settings.last_mode}. Save will keep the current session type."
            )
            ok_button = self.button_box.button(QDialogButtonBox.Ok)
            if ok_button is not None:
                ok_button.setText("Save Settings")
            return

        self.mode_status_label.setText(
            f"Current mode is {self._settings.last_mode}. Save will request a switch to {requested} mode and reopen the main window in a disconnected state."
        )
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setText("Save and Switch")
