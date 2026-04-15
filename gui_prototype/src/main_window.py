from __future__ import annotations

from datetime import datetime
from typing import Callable

import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app_metadata import APP_NAME, APP_VERSION
from app_state import AppSettings, AppUiState
from controllers import ConnectionController, PlotController, RecordingController, TelemetryHealthMonitor, WarningController
from dialogs import ModeSwitchDialog, SettingsDialog
from mock_backend import MockBackend, TelemetryPoint
from protocol_constants import (
    BLE_MODE,
    WIRED_MODE,
    transport_type_for_mode,
)
from settings_store import SettingsStore
from theme import COLORS


def _panel(title: str, hint: str | None = None, object_name: str = "PanelCard") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(object_name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)

    title_label = QLabel(title)
    title_label.setObjectName("SectionTitle")
    layout.addWidget(title_label)
    if hint:
        hint_label = QLabel(hint)
        hint_label.setObjectName("SectionHint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)
    return frame, layout


class MetricCard(QFrame):
    def __init__(self, name: str, unit: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(6)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("MetricName")
        self.value_label = QLabel(f"-- {unit}")
        self.value_label.setObjectName("MetricValue")
        self.unit_label = QLabel(unit)
        self.unit_label.setObjectName("SectionHint")

        layout.addWidget(self.name_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.unit_label)

    def set_value(self, value_text: str) -> None:
        self.value_label.setText(value_text)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        self.setText(text)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def setText(self, text: str) -> None:  # type: ignore[override]
        self._full_text = text
        self._apply_elide()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self) -> None:
        width = max(20, self.contentsRect().width() - 4)
        elided = self.fontMetrics().elidedText(self._full_text, Qt.ElideRight, width)
        super().setText(elided)
        self.setToolTip(self._full_text if elided != self._full_text else "")


class PlotInteractionViewBox(pg.ViewBox):
    def __init__(self, plot_key: str, interaction_callback: Callable[[str, bool, bool], None], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._plot_key = plot_key
        self._interaction_callback = interaction_callback

    def wheelEvent(self, ev, axis=None) -> None:  # type: ignore[override]
        super().wheelEvent(ev, axis=axis)
        self._notify_manual_interaction(x_changed=True, y_changed=True)

    def mouseDragEvent(self, ev, axis=None) -> None:  # type: ignore[override]
        super().mouseDragEvent(ev, axis=axis)
        self._notify_manual_interaction(x_changed=True, y_changed=True)

    def _notify_manual_interaction(self, *, x_changed: bool, y_changed: bool) -> None:
        self._interaction_callback(self._plot_key, x_changed, y_changed)


class PlotInteractionAxisItem(pg.AxisItem):
    def __init__(
        self,
        orientation: str,
        plot_key: str,
        axis_kind: str,
        interaction_callback: Callable[[str, bool, bool], None],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(orientation=orientation, *args, **kwargs)
        self._plot_key = plot_key
        self._axis_kind = axis_kind
        self._interaction_callback = interaction_callback

    def wheelEvent(self, ev) -> None:  # type: ignore[override]
        super().wheelEvent(ev)
        self._notify_manual_interaction()

    def mouseDragEvent(self, ev) -> None:  # type: ignore[override]
        super().mouseDragEvent(ev)
        self._notify_manual_interaction()

    def _notify_manual_interaction(self) -> None:
        self._interaction_callback(
            self._plot_key,
            self._axis_kind == "x",
            self._axis_kind == "y",
        )


class MainWindow(QMainWindow):
    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings_store = SettingsStore()
        self.app_settings: AppSettings = self.settings_store.load()
        self.app_settings.last_mode = mode
        self.ui_state = AppUiState(mode=mode)
        self.mode = mode
        self.setObjectName("AppShell")
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(
            self.app_settings.windows.main_window_width,
            self.app_settings.windows.main_window_height,
        )

        self.backend = MockBackend(mode, self)
        self.connection_controller = ConnectionController(self.backend, self)
        self.warning_controller = WarningController()
        self.plot_controller = PlotController()
        self.recording_controller = RecordingController()
        self.telemetry_health_monitor = TelemetryHealthMonitor(mode)
        self.plot_controller.x_follow_enabled = self.app_settings.plot.x_follow_enabled
        self.plot_controller.manual_y_ranges = dict(self.app_settings.plot.manual_y_ranges)
        self._session_started = datetime.now()
        self._plot_refresh_timer = QTimer(self)
        self._plot_refresh_timer.setInterval(150)
        self._plot_refresh_timer.timeout.connect(self._refresh_plots)
        self._telemetry_health_timer = QTimer(self)
        self._telemetry_health_timer.setInterval(400)
        self._telemetry_health_timer.timeout.connect(self._poll_telemetry_health)
        self._csv_flush_timer = QTimer(self)
        self._csv_flush_timer.setInterval(1000)
        self._csv_flush_timer.setSingleShot(True)
        self._csv_flush_timer.timeout.connect(self._flush_csv)
        self._left_column_ratio = 0.305
        self._ignore_manual_range_signal = False
        self._viewbox_to_plot_key: dict[object, str] = {}

        self._build_ui()
        self._bind_controllers()
        self._prime_mode_specific_lists()
        QTimer.singleShot(0, self._sync_manual_inputs_to_selected_plot)
        QTimer.singleShot(0, self._sync_recording_controls)
        QTimer.singleShot(0, self._apply_persisted_preferences)
        self._plot_refresh_timer.start()
        self._telemetry_health_timer.start()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppShell")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        content_row = QHBoxLayout()
        content_row.setSpacing(14)
        self.left_column = self._build_left_column()
        self.right_column = self._build_right_column()
        self.left_column.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.right_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_row.addWidget(self.left_column, 0)
        content_row.addWidget(self.right_column, 1)
        layout.addLayout(content_row, 1)
        QTimer.singleShot(0, self._apply_column_widths)

    def _build_left_column(self) -> QWidget:
        shell = QWidget()
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.connection_stack = QStackedWidget()
        self.connection_stack.addWidget(self._build_ble_connection_panel())
        self.connection_stack.addWidget(self._build_wired_connection_panel())
        self._sync_connection_stack()
        layout.addWidget(self.connection_stack)

        self.status_panel = self._build_status_panel()
        self.controls_panel = self._build_controls_panel()
        self.recording_panel = self._build_recording_panel()
        layout.addWidget(self.status_panel)
        layout.addWidget(self.controls_panel)
        layout.addWidget(self.recording_panel)
        layout.addStretch(1)
        return shell

    def _build_ble_connection_panel(self) -> QWidget:
        frame, layout = _panel("BLE Connection", "Scan for devices and connect to a wireless sensor.")
        utility_row = QHBoxLayout()
        utility_row.addStretch(1)
        self.ble_settings_button = QPushButton("Settings")
        self.ble_settings_button.setObjectName("SecondaryButton")
        self.ble_settings_button.clicked.connect(self._open_settings)
        utility_row.addWidget(self.ble_settings_button)
        layout.addLayout(utility_row)

        row = QHBoxLayout()
        self.ble_scan_button = QPushButton("Scan")
        self.ble_scan_button.setObjectName("SecondaryButton")
        self.ble_scan_button.clicked.connect(self.connection_controller.scan_ble_devices)
        self.ble_connect_button = QPushButton("Connect")
        self.ble_connect_button.setObjectName("PrimaryButton")
        self.ble_connect_button.clicked.connect(self._toggle_connection)
        row.addWidget(self.ble_scan_button)
        row.addWidget(self.ble_connect_button)
        layout.addLayout(row)

        self.ble_device_list = QListWidget()
        self.ble_device_list.addItem("M5STAMP-MONITOR")
        layout.addWidget(self.ble_device_list)
        return frame

    def _build_wired_connection_panel(self) -> QWidget:
        frame, layout = _panel("Wired Connection", "Connect through a COM-style serial link.")
        utility_row = QHBoxLayout()
        utility_row.addStretch(1)
        self.wired_settings_button = QPushButton("Settings")
        self.wired_settings_button.setObjectName("SecondaryButton")
        self.wired_settings_button.clicked.connect(self._open_settings)
        utility_row.addWidget(self.wired_settings_button)
        layout.addLayout(utility_row)

        row = QHBoxLayout()
        self.port_selector = QComboBox()
        self.refresh_ports_button = QPushButton("Refresh")
        self.refresh_ports_button.clicked.connect(self.connection_controller.refresh_ports)
        self.wired_connect_button = QPushButton("Connect")
        self.wired_connect_button.setObjectName("PrimaryButton")
        self.wired_connect_button.clicked.connect(self._toggle_connection)
        row.addWidget(self.port_selector, 1)
        row.addWidget(self.refresh_ports_button)
        layout.addLayout(row)
        layout.addWidget(self.wired_connect_button)

        serial_hint = QLabel("Fixed serial setting: 115200 baud / 8N1")
        serial_hint.setObjectName("SectionHint")
        layout.addWidget(serial_hint)
        return frame

    def _build_status_panel(self) -> QWidget:
        frame, layout = _panel("Device Status", "This section reflects the latest normalized status snapshot.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.pump_state_value = QLabel("OFF")
        self.transport_state_value = QLabel("Disconnected")
        self.status_flags_value = QLabel("0x00000000")
        self.sample_period_value = QLabel("--")
        self.firmware_value = QLabel("--")
        self.protocol_value = QLabel("--")
        self.gap_value = QLabel("0")

        rows = [
            ("Pump State", self.pump_state_value),
            ("Transport", self.transport_state_value),
            ("Status Flags", self.status_flags_value),
            ("Sample Period", self.sample_period_value),
            ("Firmware", self.firmware_value),
            ("Protocol", self.protocol_value),
            ("Sequence Gaps", self.gap_value),
        ]
        for row_index, (name, value_label) in enumerate(rows):
            grid.addWidget(QLabel(name), row_index, 0)
            grid.addWidget(value_label, row_index, 1)

        layout.addLayout(grid)
        return frame

    def _build_controls_panel(self) -> QWidget:
        frame, layout = _panel("Controls", "Commands are routed through the shared controller layer.")
        button_grid = QGridLayout()

        self.pump_on_button = QPushButton("Pump ON")
        self.pump_on_button.setObjectName("PrimaryButton")
        self.pump_on_button.clicked.connect(lambda: self.connection_controller.set_pump_state(True))
        self.pump_off_button = QPushButton("Pump OFF")
        self.pump_off_button.clicked.connect(lambda: self.connection_controller.set_pump_state(False))
        self.get_status_button = QPushButton("Get Status")
        self.get_status_button.clicked.connect(self.connection_controller.request_status)
        self.get_capabilities_button = QPushButton("Get Capabilities")
        self.get_capabilities_button.clicked.connect(self.connection_controller.request_capabilities)
        self.ping_button = QPushButton("Ping")
        self.ping_button.clicked.connect(self.connection_controller.ping)

        buttons = [
            self.pump_on_button,
            self.pump_off_button,
            self.get_status_button,
            self.get_capabilities_button,
            self.ping_button,
        ]
        for idx, button in enumerate(buttons):
            button_grid.addWidget(button, idx // 2, idx % 2)

        layout.addLayout(button_grid)
        return frame

    def _build_recording_panel(self) -> QWidget:
        frame, layout = _panel("Recording", "Session files are written as .partial.csv and finalized to .csv on stop.")
        row = QHBoxLayout()
        self.record_start_button = QPushButton("Start Recording")
        self.record_start_button.setObjectName("PrimaryButton")
        self.record_start_button.clicked.connect(self._start_recording)
        self.record_stop_button = QPushButton("Stop Recording")
        self.record_stop_button.clicked.connect(self._stop_recording)
        row.addWidget(self.record_start_button)
        row.addWidget(self.record_stop_button)
        layout.addLayout(row)

        self.session_id_value = QLabel("--")
        self.session_id_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.recording_file_value = ElidedLabel("--")
        self.recording_file_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.elapsed_value = QLabel("00:00")
        layout.addWidget(QLabel("Session ID"))
        layout.addWidget(self.session_id_value)
        layout.addWidget(QLabel("Current File"))
        layout.addWidget(self.recording_file_value)
        layout.addWidget(QLabel("Elapsed"))
        layout.addWidget(self.elapsed_value)
        return frame

    def _build_right_column(self) -> QWidget:
        shell = QWidget()
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        cards = QWidget()
        cards_layout = QHBoxLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        self.metric_zirconia = MetricCard("Zirconia Output Voltage", "V")
        self.metric_heater = MetricCard("Heater RTD Resistance", "Ohm")
        self.metric_flow = MetricCard("Flow Rate", "L/min")
        cards_layout.addWidget(self.metric_zirconia)
        cards_layout.addWidget(self.metric_heater)
        cards_layout.addWidget(self.metric_flow)
        layout.addWidget(cards)

        toolbar, toolbar_layout = _panel("Plot Toolbar", "Relative and manual-scale controls are active in the prototype.")
        row = QHBoxLayout()
        self.time_span_combo = QComboBox()
        self.time_span_combo.addItems(["30 s", "2 min", "10 min", "All"])
        self.time_span_combo.setCurrentText(self.app_settings.plot.time_span)
        self.time_span_combo.currentTextChanged.connect(self._on_time_span_changed)
        self.axis_mode_combo = QComboBox()
        self.axis_mode_combo.addItems(["Relative", "Clock"])
        self.axis_mode_combo.setCurrentText(self.app_settings.plot.axis_mode)
        self.axis_mode_combo.currentTextChanged.connect(self._on_axis_mode_changed)
        self.auto_scale_check = QCheckBox("Auto scale")
        self.auto_scale_check.setChecked(self.app_settings.plot.auto_scale)
        self.auto_scale_check.toggled.connect(self._on_auto_scale_toggled)
        self.plot_selector = QComboBox()
        self.plot_selector.addItems(["Zirconia", "Heater", "Flow"])
        self.plot_selector.setCurrentText(self.app_settings.plot.selected_plot)
        self.plot_selector.currentTextChanged.connect(self._on_plot_selector_changed)
        self.manual_min_input = QLineEdit()
        self.manual_min_input.setPlaceholderText("Y min")
        self.manual_max_input = QLineEdit()
        self.manual_max_input.setPlaceholderText("Y max")
        apply_button = QPushButton("Apply Scale")
        apply_button.clicked.connect(self._apply_scaling_controls)
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.clicked.connect(self._reset_plot_view)

        for widget in [
            QLabel("Span"),
            self.time_span_combo,
            QLabel("Axis"),
            self.axis_mode_combo,
            self.auto_scale_check,
            QLabel("Manual"),
            self.plot_selector,
            self.manual_min_input,
            self.manual_max_input,
            apply_button,
            self.reset_view_button,
        ]:
            row.addWidget(widget)
        row.addStretch(1)
        toolbar_layout.addLayout(row)
        layout.addWidget(toolbar)

        pg.setConfigOptions(antialias=False)
        self.plot_widgets: dict[str, pg.PlotWidget] = {}
        self.plot_curves: dict[str, object] = {}

        for title, key, color in [
            ("Zirconia Output Voltage", "zirconia", "#315C8C"),
            ("Heater RTD Resistance", "heater", "#5E7D4B"),
            ("Flow Rate", "flow", "#B5781A"),
        ]:
            plot_frame, plot_layout = _panel(title)
            view_box = PlotInteractionViewBox(key, self._handle_plot_user_interaction)
            axis_items = {
                "bottom": PlotInteractionAxisItem("bottom", key, "x", self._handle_plot_user_interaction),
                "left": PlotInteractionAxisItem("left", key, "y", self._handle_plot_user_interaction),
            }
            plot = pg.PlotWidget(viewBox=view_box, axisItems=axis_items)
            plot.setBackground(None)
            plot.showGrid(x=True, y=True, alpha=0.22)
            plot.setClipToView(True)
            plot.setDownsampling(auto=True, mode="peak")
            plot.getPlotItem().getAxis("left").setTextPen(QColor(COLORS["muted"]))
            plot.getPlotItem().getAxis("bottom").setTextPen(QColor(COLORS["muted"]))
            plot.getPlotItem().getAxis("left").setPen(QColor(COLORS["muted"]))
            plot.getPlotItem().getAxis("bottom").setPen(QColor(COLORS["muted"]))
            plot.setMinimumHeight(160)
            view_box.sigRangeChangedManually.connect(self._on_plot_range_changed_manually)
            self._viewbox_to_plot_key[view_box] = key
            curve = plot.plot(pen=pg.mkPen(color=color, width=2.2))
            curve.setSkipFiniteCheck(True)
            plot_layout.addWidget(plot)
            layout.addWidget(plot_frame, 1)
            self.plot_widgets[key] = plot
            self.plot_curves[key] = curve

        self.plot_widgets["heater"].setXLink(self.plot_widgets["zirconia"])
        self.plot_widgets["flow"].setXLink(self.plot_widgets["zirconia"])

        log_frame, log_layout = _panel("Warning / Event Log", object_name="WarningCard")
        self.log_pane = QPlainTextEdit()
        self.log_pane.setObjectName("LogPane")
        self.log_pane.setReadOnly(True)
        self.log_pane.setMinimumHeight(150)
        log_layout.addWidget(self.log_pane)
        layout.addWidget(log_frame)

        return shell

    def _bind_controllers(self) -> None:
        self.connection_controller.connection_changed.connect(self._on_connection_changed)
        self.connection_controller.status_changed.connect(self._on_status_changed)
        self.connection_controller.capabilities_changed.connect(self._on_capabilities_changed)
        self.connection_controller.telemetry_received.connect(self._on_telemetry)
        self.connection_controller.log_generated.connect(self._append_log)
        self.connection_controller.ble_devices_discovered.connect(self._on_ble_devices_discovered)
        self.connection_controller.ports_discovered.connect(self._on_ports_discovered)

    def _apply_persisted_preferences(self) -> None:
        self._update_axis_labels()
        self._sync_manual_inputs_to_selected_plot()
        self._sync_recording_controls()
        self._refresh_plots()

    def _current_recording_directory(self):
        return self.settings_store.recording_directory_path(self.app_settings)

    def _persist_current_settings(self) -> None:
        self.app_settings.last_mode = self.mode
        self.app_settings.plot.time_span = self.time_span_combo.currentText()
        self.app_settings.plot.axis_mode = self.axis_mode_combo.currentText()
        self.app_settings.plot.auto_scale = self.auto_scale_check.isChecked()
        self.app_settings.plot.selected_plot = self.plot_selector.currentText()
        self.app_settings.plot.x_follow_enabled = self.plot_controller.x_follow_enabled
        self.app_settings.plot.manual_y_ranges = dict(self.plot_controller.manual_y_ranges)
        self.app_settings.windows.main_window_width = self.width()
        self.app_settings.windows.main_window_height = self.height()
        self.settings_store.save(self.app_settings)

    def _apply_dialog_settings(self, dialog: SettingsDialog) -> None:
        self.app_settings.last_mode = dialog.requested_mode
        self.app_settings.plot.time_span = dialog.selected_time_span
        self.app_settings.plot.axis_mode = dialog.selected_axis_mode
        self.app_settings.plot.auto_scale = dialog.selected_auto_scale
        self.app_settings.plot.selected_plot = dialog.selected_plot
        self.app_settings.logging.recording_directory = dialog.recording_directory
        self.app_settings.logging.partial_recovery_notice_enabled = dialog.partial_recovery_notice_enabled

    def _apply_settings_to_widgets(self) -> None:
        self.time_span_combo.setCurrentText(self.app_settings.plot.time_span)
        self.axis_mode_combo.setCurrentText(self.app_settings.plot.axis_mode)
        self.auto_scale_check.setChecked(self.app_settings.plot.auto_scale)
        self.plot_selector.setCurrentText(self.app_settings.plot.selected_plot)
        self.plot_controller.x_follow_enabled = self.app_settings.plot.x_follow_enabled
        self.plot_controller.manual_y_ranges = dict(self.app_settings.plot.manual_y_ranges)
        for plot_key, y_range in self.plot_controller.manual_y_ranges.items():
            if plot_key in self.plot_widgets:
                plot = self.plot_widgets[plot_key]
                plot.enableAutoRange(axis="y", enable=False)
                plot.setYRange(y_range[0], y_range[1], padding=0.02)
        self._update_axis_labels()
        self._sync_manual_inputs_to_selected_plot()

    def _prime_mode_specific_lists(self) -> None:
        if self.mode == BLE_MODE:
            self.ble_device_list.clear()
            self._append_log("info", "BLE mode is ready. Click Scan to discover devices.")
            return

        self.connection_controller.refresh_ports()
        self._append_log("info", f"{self.mode} mode is ready for visual review.")

    def _sync_connection_stack(self) -> None:
        self.connection_stack.setCurrentIndex(0 if self.mode == BLE_MODE else 1)

    def _toggle_connection(self) -> None:
        if self.connection_controller.is_connected():
            self.ui_state.connection.phase = "disconnecting"
            self.connection_controller.disconnect_device()
            return
        if self.mode == BLE_MODE:
            item = self.ble_device_list.currentItem() or self.ble_device_list.item(0)
            identifier = item.text() if item else "M5STAMP-MONITOR"
        else:
            identifier = self.port_selector.currentText() or "Prototype-Port"
        self.ui_state.connection.phase = "connecting"
        self.connection_controller.connect_device(identifier)

    def _on_connection_changed(self, connected: bool, identifier: str) -> None:
        self.ui_state.connection.phase = "connected" if connected else "disconnected"
        self.ui_state.connection.identifier = identifier if connected else "Disconnected"
        self.transport_state_value.setText("Connected" if connected else "Disconnected")
        connect_text = "Disconnect" if connected else "Connect"
        self.ble_connect_button.setText(connect_text)
        self.wired_connect_button.setText(connect_text)
        for severity, message in self.telemetry_health_monitor.on_connection_changed(connected, identifier):
            self._append_log(severity, message)
        if not connected:
            self._stop_recording()
        self._sync_recording_controls()

    def _on_status_changed(self, payload: dict) -> None:
        self.pump_state_value.setText(str(payload["pump_state"]))
        self.transport_state_value.setText(str(payload["transport_state"]))
        self.status_flags_value.setText(str(payload["status_flags_hex"]))
        self.sample_period_value.setText(f"{payload['nominal_sample_period_ms']} ms")
        self.firmware_value.setText(str(payload["firmware_version"]))
        self.protocol_value.setText(str(payload["protocol_version"]))
        self.ui_state.session_metadata.firmware_version = str(payload["firmware_version"])
        self.ui_state.session_metadata.protocol_version = str(payload["protocol_version"])
        self.ui_state.session_metadata.nominal_sample_period_ms = str(payload["nominal_sample_period_ms"])
        self.telemetry_health_monitor.update_nominal_sample_period(payload["nominal_sample_period_ms"])

    def _on_capabilities_changed(self, payload: dict) -> None:
        nominal = payload["nominal_sample_period_ms"]
        self.sample_period_value.setText(f"{nominal} ms")
        self.firmware_value.setText(str(payload["firmware_version"]))
        self.protocol_value.setText(str(payload["protocol_version"]))
        self.ui_state.session_metadata.firmware_version = str(payload["firmware_version"])
        self.ui_state.session_metadata.protocol_version = str(payload["protocol_version"])
        self.ui_state.session_metadata.nominal_sample_period_ms = str(nominal)
        self.ui_state.session_metadata.transport_type = str(payload.get("transport_type", transport_type_for_mode(self.mode)))
        self.telemetry_health_monitor.update_nominal_sample_period(nominal)

    def _on_ble_devices_discovered(self, devices: list[str]) -> None:
        self.ble_device_list.clear()
        for device in devices:
            QListWidgetItem(device, self.ble_device_list)
        if self.ble_device_list.count():
            self.ble_device_list.setCurrentRow(0)

    def _on_ports_discovered(self, ports: list[str]) -> None:
        self.port_selector.clear()
        self.port_selector.addItems(ports)

    def _on_telemetry(self, point: TelemetryPoint) -> None:
        plot_update = self.plot_controller.append_sample(point)
        self.gap_value.setText(str(plot_update["sequence_gap_total"]))
        for severity, message in self.telemetry_health_monitor.on_telemetry(point):
            self._append_log(severity, message)

        if self.recording_controller.is_recording:
            self.recording_controller.append_row(
                point=point,
                mode=self.mode,
                transport_type=transport_type_for_mode(self.mode),
            )
            self._schedule_csv_flush()

        metrics = self.plot_controller.metric_snapshot()
        self.metric_zirconia.set_value(f"{metrics.get('zirconia_output_voltage_v', point.zirconia_output_voltage_v):0.3f} V")
        self.metric_heater.set_value(f"{metrics.get('heater_rtd_resistance_ohm', point.heater_rtd_resistance_ohm):0.1f} Ohm")
        self.metric_flow.set_value(f"{metrics.get('flow_rate_lpm', 0.0):0.3f} L/min")

        if self.recording_controller.is_recording and self.recording_controller.started_at is not None:
            elapsed_record = max(0, int((datetime.now() - self.recording_controller.started_at).total_seconds()))
            mins, secs = divmod(elapsed_record, 60)
            self.elapsed_value.setText(f"{mins:02d}:{secs:02d}")

    def _refresh_plots(self) -> None:
        render_data = self.plot_controller.render_data(self.time_span_combo.currentText())
        x_values = render_data["x_values"]
        if not x_values:
            return

        for key, curve in self.plot_curves.items():
            curve.setData(x_values, render_data["series"][key])
        if self.plot_controller.x_follow_enabled:
            self._set_plot_x_range(render_data["xmin"], render_data["xmax"])
        self._update_axis_labels()

    def _update_axis_labels(self) -> None:
        axis_mode = self.axis_mode_combo.currentText()
        label = "Time (s)" if axis_mode == "Relative" else "Clock-like time (prototype)"
        for plot in self.plot_widgets.values():
            plot.setLabel("bottom", label)

    def _on_axis_mode_changed(self) -> None:
        self._update_axis_labels()
        self._persist_current_settings()

    def _on_plot_selector_changed(self) -> None:
        self._sync_manual_inputs_to_selected_plot()
        self._persist_current_settings()

    def _on_time_span_changed(self) -> None:
        self.plot_controller.x_follow_enabled = True
        self.app_settings.plot.x_follow_enabled = True
        self._refresh_plots()
        self._persist_current_settings()

    def _on_auto_scale_toggled(self, checked: bool) -> None:
        selected_key = self._selected_plot_key()
        plot = self.plot_widgets[selected_key]
        if checked:
            plot.enableAutoRange(axis="y", enable=True)
            self.plot_controller.manual_y_ranges.pop(selected_key, None)
            self._sync_manual_inputs_to_selected_plot()
        self._persist_current_settings()

    def _apply_scaling_controls(self) -> None:
        selected_key = self._selected_plot_key()
        plot = self.plot_widgets[selected_key]

        if self.auto_scale_check.isChecked():
            plot.enableAutoRange(axis="y", enable=True)
            self._sync_manual_inputs_to_selected_plot()
            return

        try:
            y_min = float(self.manual_min_input.text())
            y_max = float(self.manual_max_input.text())
        except ValueError:
            return
        if y_max <= y_min:
            return

        plot.enableAutoRange(axis="y", enable=False)
        plot.setYRange(y_min, y_max, padding=0.02)
        self.plot_controller.set_manual_y_range(selected_key, y_min, y_max)
        self._sync_manual_inputs_to_selected_plot()
        self._persist_current_settings()

    def _reset_plot_view(self) -> None:
        self.plot_controller.x_follow_enabled = True
        self._sync_manual_inputs_to_selected_plot()
        self._refresh_plots()
        self._persist_current_settings()

    def _selected_plot_key(self) -> str:
        return {
            "Zirconia": "zirconia",
            "Heater": "heater",
            "Flow": "flow",
        }[self.plot_selector.currentText()]

    def _set_plot_x_range(self, xmin: float, xmax: float) -> None:
        if "zirconia" not in self.plot_widgets:
            return
        self._ignore_manual_range_signal = True
        try:
            self.plot_widgets["zirconia"].setXRange(xmin, xmax, padding=0.02)
        finally:
            self._ignore_manual_range_signal = False

    def _sync_manual_inputs_to_selected_plot(self) -> None:
        if not getattr(self, "plot_widgets", None):
            return
        selected_key = self._selected_plot_key()
        if selected_key not in self.plot_widgets:
            return
        y_range = self.plot_controller.manual_y_range_for(selected_key)
        if y_range is None:
            plot = self.plot_widgets[selected_key]
            _, current_y_range = plot.getViewBox().viewRange()
            y_range = (current_y_range[0], current_y_range[1])
        self.manual_min_input.setText(f"{y_range[0]:0.3f}")
        self.manual_max_input.setText(f"{y_range[1]:0.3f}")

    def _on_plot_range_changed_manually(self, axes_enabled: object) -> None:
        if self._ignore_manual_range_signal:
            return

        axis_flags = list(axes_enabled) if isinstance(axes_enabled, (list, tuple)) else [True, True]
        x_changed = bool(axis_flags[0]) if axis_flags else True
        y_changed = bool(axis_flags[1]) if len(axis_flags) > 1 else True

        sender = self.sender()
        plot_key = self._viewbox_to_plot_key.get(sender)
        self._handle_plot_user_interaction(plot_key, x_changed, y_changed)

    def _handle_plot_user_interaction(self, plot_key: str | None, x_changed: bool, y_changed: bool) -> None:
        if self._ignore_manual_range_signal:
            return

        if x_changed:
            self.plot_controller.x_follow_enabled = False

        if plot_key == "zirconia":
            self.plot_selector.setCurrentText("Zirconia")
        elif plot_key == "heater":
            self.plot_selector.setCurrentText("Heater")
        elif plot_key == "flow":
            self.plot_selector.setCurrentText("Flow")

        if y_changed and plot_key is not None and plot_key in self.plot_widgets:
            if self.auto_scale_check.isChecked():
                self.auto_scale_check.blockSignals(True)
                self.auto_scale_check.setChecked(False)
                self.auto_scale_check.blockSignals(False)
            _, y_range = self.plot_widgets[plot_key].getViewBox().viewRange()
            self.plot_controller.set_manual_y_range(plot_key, y_range[0], y_range[1])

        self._sync_manual_inputs_to_selected_plot()
        self._persist_current_settings()

    def _sync_recording_controls(self) -> None:
        can_start = self.connection_controller.is_connected() and not self.recording_controller.is_recording
        self.record_start_button.setEnabled(can_start)
        self.record_stop_button.setEnabled(self.recording_controller.is_recording)

    def _recording_source_endpoint(self) -> str:
        if self.mode == BLE_MODE:
            return f"BLE:{self.ui_state.connection.identifier}"
        return f"SERIAL:{self.ui_state.connection.identifier}"

    def _schedule_csv_flush(self) -> None:
        if not self.recording_controller.is_recording:
            return
        if self.recording_controller.should_flush(25):
            self._flush_csv()
            return
        if not self._csv_flush_timer.isActive():
            self._csv_flush_timer.start()

    def _flush_csv(self) -> None:
        self.recording_controller.flush()

    def _start_recording(self) -> None:
        if self.recording_controller.is_recording:
            return
        if not self.connection_controller.is_connected():
            self._append_log("warn", "Connect to a device before starting recording.")
            return

        try:
            self.recording_controller.start(
                base_dir=self._current_recording_directory(),
                gui_app_name=APP_NAME,
                gui_app_version=APP_VERSION,
                mode=self.mode,
                transport_type=transport_type_for_mode(self.mode),
                device_identifier=self.ui_state.connection.identifier,
                firmware_version="" if self.firmware_value.text() == "--" else self.firmware_value.text(),
                protocol_version="" if self.protocol_value.text() == "--" else self.protocol_value.text(),
                nominal_sample_period_ms="" if self.sample_period_value.text() == "--" else self.sample_period_value.text().replace(" ms", ""),
                source_endpoint=self._recording_source_endpoint(),
            )
        except Exception as exc:
            self._append_log("error", f"Recording could not be started: {exc}")
            return

        self.ui_state.recording.phase = "recording"
        self.ui_state.recording.session_id = self.recording_controller.session_id
        self.ui_state.recording.current_file = str(self.recording_controller.partial_path)
        self.ui_state.recording.started_at = self.recording_controller.started_at
        self.session_id_value.setText(self.recording_controller.session_id)
        self.recording_file_value.setText(str(self.recording_controller.partial_path))
        self.elapsed_value.setText("00:00")
        self._sync_recording_controls()
        self._append_log("info", f"Recording started: {self.recording_controller.session_id}")

    def _stop_recording(self) -> None:
        if not self.recording_controller.is_recording:
            return
        self._csv_flush_timer.stop()
        try:
            final_path = self.recording_controller.stop()
        except Exception as exc:
            self._append_log("error", f"Recording finalization failed: {exc}")
            self.recording_controller.abort()
            final_path = None

        self.ui_state.recording.phase = "idle"
        self.ui_state.recording.current_file = "" if final_path is None else str(final_path)
        self.ui_state.recording.started_at = None
        self._sync_recording_controls()
        if final_path is not None:
            self.recording_file_value.setText(str(final_path))
        self._append_log("info", "Recording stopped.")

    def _append_log(self, severity: str, message: str) -> None:
        entry = self.warning_controller.append(severity, message)
        self.log_pane.appendPlainText(f"[{entry.timestamp.strftime('%H:%M:%S')}] {entry.severity.upper():<5} {entry.message}")

    def _poll_telemetry_health(self) -> None:
        for severity, message in self.telemetry_health_monitor.poll():
            self._append_log(severity, message)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.app_settings, self)
        if dialog.exec() != dialog.Accepted:
            return
        previous_mode = self.mode
        self._apply_dialog_settings(dialog)
        self._apply_settings_to_widgets()
        self._persist_current_settings()
        requested_mode = dialog.requested_mode
        if requested_mode == previous_mode:
            self._append_log("info", "Settings updated.")
            return

        confirm = ModeSwitchDialog(previous_mode, requested_mode, self)
        if confirm.exec() != confirm.Accepted:
            self.app_settings.last_mode = previous_mode
            self._apply_settings_to_widgets()
            self._persist_current_settings()
            return
        self._switch_mode(requested_mode)

    def _switch_mode(self, new_mode: str) -> None:
        if self.connection_controller.is_connected():
            self.connection_controller.disconnect_device()
        self._stop_recording()
        self.mode = new_mode
        self.ui_state.mode = new_mode
        self.app_settings.last_mode = new_mode
        self.telemetry_health_monitor.set_mode(new_mode)
        self.connection_controller.set_mode(new_mode)
        self._clear_plot_buffers()
        self._sync_connection_stack()
        self._prime_mode_specific_lists()
        self.metric_zirconia.set_value("-- V")
        self.metric_heater.set_value("-- Ohm")
        self.metric_flow.set_value("-- L/min")
        self._persist_current_settings()
        self._append_log("info", f"Mode switched to {new_mode}.")

    def _clear_plot_buffers(self) -> None:
        self.plot_controller.clear()
        self.gap_value.setText("0")
        self._session_started = datetime.now()
        for curve in self.plot_curves.values():
            curve.setData([], [])

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._stop_recording()
        self.connection_controller.disconnect_device()
        self._persist_current_settings()
        super().closeEvent(event)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_column_widths()

    def _apply_column_widths(self) -> None:
        if not hasattr(self, "left_column"):
            return
        available_width = max(900, self.width() - 36)
        left_width = int(available_width * self._left_column_ratio)
        left_width = max(348, min(418, left_width))
        self.left_column.setFixedWidth(left_width)
