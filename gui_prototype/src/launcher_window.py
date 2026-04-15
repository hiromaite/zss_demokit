from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_metadata import APP_NAME, APP_SUBTITLE, APP_VERSION
from dialogs import PartialRecoveryDialog
from main_window import MainWindow
from protocol_constants import BLE_MODE, WIRED_DEFAULT_BAUDRATE, WIRED_DEFAULT_LINE_SETTINGS, WIRED_MODE
from recording_io import find_partial_recordings
from settings_store import SettingsStore


class ModeCard(QFrame):
    def __init__(self, title: str, subtitle: str, action_text: str, object_name: str) -> None:
        super().__init__()
        self.setObjectName(object_name)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        copy_label = QLabel(subtitle)
        copy_label.setObjectName("SectionHint")
        copy_label.setWordWrap(True)
        self.action_button = QPushButton(action_text)
        self.action_button.setObjectName("ModeCardButton")

        layout.addWidget(title_label)
        layout.addWidget(copy_label, 1)
        layout.addWidget(self.action_button)


class LauncherWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings_store = SettingsStore()
        self._app_settings = self._settings_store.load()
        self.setObjectName("LauncherShell")
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(
            self._app_settings.windows.launcher_window_width,
            self._app_settings.windows.launcher_window_height,
        )
        self.setMinimumSize(820, 560)
        self._main_window: MainWindow | None = None

        root = QWidget()
        root.setObjectName("LauncherShell")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("SurfaceCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(6)

        title = QLabel(APP_NAME)
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignCenter)
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("AppSubtitle")
        version.setAlignment(Qt.AlignCenter)
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("AppSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        intro = QLabel(
            "Select a device mode to start a prototype session. "
            "You can switch modes later from Settings in the main window."
        )
        intro.setObjectName("SectionHint")
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(title)
        hero_layout.addWidget(version)
        hero_layout.addWidget(subtitle)
        hero_layout.addWidget(intro)
        layout.addWidget(hero)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        self.ble_card = ModeCard(
            "BLE Mode",
            "Wireless sensor workflow.\nTarget telemetry interval: 50 to 100 ms.\nUse scan and connect operations.",
            "Open BLE Mode",
            "AccentCard",
        )
        self.wired_card = ModeCard(
            "Wired Mode",
            f"Serial sensor workflow.\nRequired telemetry interval: 10 ms.\nCOM-style connection with {WIRED_DEFAULT_BAUDRATE} baud / {WIRED_DEFAULT_LINE_SETTINGS}.",
            "Open Wired Mode",
            "MetricCard",
        )
        self.ble_card.action_button.clicked.connect(lambda: self._open_mode(BLE_MODE))
        self.wired_card.action_button.clicked.connect(lambda: self._open_mode(WIRED_MODE))
        cards_row.addWidget(self.ble_card, 1)
        cards_row.addWidget(self.wired_card, 1)
        layout.addLayout(cards_row, 1)

        recovery = QFrame()
        recovery.setObjectName("WarningCard")
        recovery_layout = QHBoxLayout(recovery)
        recovery_layout.setContentsMargins(16, 16, 16, 16)
        recovery_layout.setSpacing(12)
        partials = find_partial_recordings(self._settings_store.recording_directory_path(self._app_settings))
        if partials:
            recovery_copy = f"{len(partials)} unfinished session file(s) were found in the recording directory."
            button_text = "Review Partial Files"
        else:
            recovery_copy = "Partial recovery notice: unfinished session files will be surfaced here at startup."
            button_text = "Review Recovery Flow"
        copy = QLabel(
            recovery_copy
        )
        copy.setWordWrap(True)
        review_button = QPushButton(button_text)
        review_button.clicked.connect(self._open_partial_recovery)
        recovery_layout.addWidget(copy, 1)
        recovery_layout.addWidget(review_button, 0)
        recovery.setVisible(self._app_settings.logging.partial_recovery_notice_enabled or bool(partials))
        layout.addWidget(recovery)

    def _open_partial_recovery(self) -> None:
        dialog = PartialRecoveryDialog(
            self._settings_store.recording_directory_path(self._app_settings),
            self,
        )
        dialog.exec()

    def _open_mode(self, mode: str) -> None:
        self._app_settings.last_mode = mode
        self._main_window = MainWindow(mode)
        self._main_window.show()
        self.close()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._app_settings.windows.launcher_window_width = self.width()
        self._app_settings.windows.launcher_window_height = self.height()
        self._settings_store.save(self._app_settings)
        super().closeEvent(event)
