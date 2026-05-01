from __future__ import annotations

from datetime import datetime, timedelta
import math
from pathlib import Path
from typing import Callable

import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app_metadata import APP_NAME, APP_VERSION
from app_state import AppSettings, AppUiState
from controllers import (
    ConnectionController,
    PlotController,
    RecordingController,
    TelemetryHealthMonitor,
    TelemetrySessionStats,
    WarningController,
)
from dialogs import (
    FlowCharacterizationDialog,
    FlowVerificationDetailsDialog,
    FlowVerificationDialog,
    FlowVerificationHistoryDialog,
    ModeSwitchDialog,
    SettingsDialog,
)
from flow_characterization import FlowCharacterizationController, FlowCharacterizationPersistence
from flow_verification import FlowVerificationController, FlowVerificationPersistence
from mock_backend import MockBackend, TelemetryPoint
from mock_backend import PREFERRED_BLE_NAME_PREFIXES, PREFERRED_WIRED_PORT_TOKENS
from protocol_constants import (
    BLE_MODE,
    STATUS_FLAG_HEATER_POWER_ON,
    STATUS_FLAG_PUMP_ON,
    WIRED_MODE,
    derive_o2_concentration_percent,
    infer_differential_pressure_selected_source,
    transport_type_for_mode,
)
from settings_store import SettingsStore
from theme import COLORS


FLOW_DEFAULT_Y_RANGE_LPM = (-5.0, 5.0)
O2_DEFAULT_Y_RANGE_PERCENT = (0.0, 25.0)


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
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.name_label = QLabel(name)
        self.name_label.setObjectName("MetricName")
        self.value_label = QLabel("--")
        self.value_label.setObjectName("MetricValue")
        self.detail_label = QLabel("")
        self.detail_label.setObjectName("MetricDetail")
        self.detail_label.setWordWrap(True)
        self.detail_label.setVisible(False)

        layout.addWidget(self.name_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value_text: str) -> None:
        self.value_label.setText(value_text)

    def set_detail(self, detail_text: str) -> None:
        self.detail_label.setText(detail_text)
        self.detail_label.setVisible(bool(detail_text))


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


class TimeAxisItem(PlotInteractionAxisItem):
    def __init__(
        self,
        orientation: str,
        plot_key: str,
        axis_kind: str,
        interaction_callback: Callable[[str, bool, bool], None],
        axis_mode_provider: Callable[[], str],
        session_start_provider: Callable[[], datetime],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(orientation, plot_key, axis_kind, interaction_callback, *args, **kwargs)
        self._axis_mode_provider = axis_mode_provider
        self._session_start_provider = session_start_provider

    def tickStrings(self, values, scale, spacing):  # type: ignore[override]
        if self._axis_mode_provider() == "Clock":
            session_start = self._session_start_provider()
            labels = []
            for value in values:
                timestamp = session_start + timedelta(seconds=float(value))
                if spacing >= 3600:
                    labels.append(timestamp.strftime("%H:%M"))
                else:
                    labels.append(timestamp.strftime("%H:%M:%S"))
            return labels

        labels = []
        for value in values:
            total_seconds = max(0.0, float(value))
            if spacing >= 60:
                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)
                hours = minutes // 60
                minutes = minutes % 60
                if hours > 0:
                    labels.append(f"{hours:d}:{minutes:02d}:{seconds:02d}")
                else:
                    labels.append(f"{minutes:02d}:{seconds:02d}")
            elif spacing >= 1:
                labels.append(f"{total_seconds:.0f}s")
            else:
                labels.append(f"{total_seconds:.1f}s")
        return labels


class CollapsiblePanel(QFrame):
    def __init__(self, title: str, hint: str | None = None, *, expanded: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PanelCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        self.toggle_button = QToolButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.setText(title)
        self.toggle_button.setObjectName("SectionToggle")
        self.toggle_button.toggled.connect(self._set_expanded)
        header_row.addWidget(self.toggle_button, 0)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self.hint_label = QLabel(hint or "")
        self.hint_label.setObjectName("SectionHint")
        self.hint_label.setWordWrap(True)
        self.hint_label.setVisible(expanded and bool(hint))
        layout.addWidget(self.hint_label)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.content.setVisible(expanded)
        layout.addWidget(self.content)

    def _set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.content.setVisible(expanded)
        self.hint_label.setVisible(expanded and bool(self.hint_label.text()))


class VerticalOnlyScrollArea(QScrollArea):
    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        content = self.widget()
        if content is not None:
            content.setFixedWidth(self.viewport().width())


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
        self.telemetry_session_stats = TelemetrySessionStats(mode)
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
        self._ignore_manual_range_signal = False
        self._viewbox_to_plot_key: dict[object, str] = {}
        self._secondary_y_views: dict[str, pg.ViewBox] = {}
        self._last_plot_data_key: tuple[object, ...] | None = None
        self._active_plot_key = self._plot_key_from_label(self.app_settings.plot.selected_plot)
        self._pending_mode_switch_target: str | None = None
        self._latest_low_range_differential_pressure_pa: float | None = None
        self._latest_high_range_differential_pressure_pa: float | None = None
        self._latest_zirconia_ip_voltage_v: float | None = None
        self._latest_internal_voltage_v: float | None = None

        self._build_ui()
        self._bind_controllers()
        self._prime_mode_specific_lists()
        self._sync_connection_controls()
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

        self.left_column_content = self._build_left_column()
        self.left_column_content.setMinimumWidth(0)
        self.left_column = VerticalOnlyScrollArea()
        self.left_column.setWidgetResizable(True)
        self.left_column.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.left_column.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.left_column.setFrameShape(QFrame.NoFrame)
        self.left_column.setWidget(self.left_column_content)
        self.right_column_content = self._build_right_column()
        self.right_column = VerticalOnlyScrollArea()
        self.right_column.setWidgetResizable(True)
        self.right_column.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.right_column.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.right_column.setFrameShape(QFrame.NoFrame)
        self.right_column.setWidget(self.right_column_content)
        self.left_column.setMinimumWidth(272)
        self.left_column.setMaximumWidth(420)
        self.right_column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(14)
        columns.addWidget(self.left_column, 0)
        columns.addWidget(self.right_column, 1)
        layout.addLayout(columns, 1)
        QTimer.singleShot(0, self._apply_column_widths)

    def _build_left_column(self) -> QWidget:
        shell = QWidget()
        shell.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

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
        frame, layout = _panel("BLE Connection", "Scan and connect to a wireless sensor.")

        row = QHBoxLayout()
        row.setSpacing(8)
        self.ble_device_selector = QComboBox()
        self.ble_device_selector.addItem("M5STAMP-MONITOR")
        row.addWidget(self.ble_device_selector, 1)
        self.ble_scan_button = QPushButton("Scan")
        self.ble_scan_button.setObjectName("SecondaryButton")
        self.ble_scan_button.clicked.connect(self.connection_controller.scan_ble_devices)
        self.ble_connect_button = QPushButton("Connect")
        self.ble_connect_button.setObjectName("PrimaryButton")
        self.ble_connect_button.clicked.connect(self._toggle_connection)
        row.addWidget(self.ble_connect_button)
        row.addWidget(self.ble_scan_button)
        layout.addLayout(row)
        return frame

    def _build_wired_connection_panel(self) -> QWidget:
        frame, layout = _panel("Wired Connection", "Connect through a COM-style serial link.")
        row = QHBoxLayout()
        row.setSpacing(8)
        self.port_selector = QComboBox()
        self.refresh_ports_button = QPushButton("Refresh")
        self.refresh_ports_button.setObjectName("SecondaryButton")
        self.refresh_ports_button.clicked.connect(self.connection_controller.refresh_ports)
        self.wired_connect_button = QPushButton("Connect")
        self.wired_connect_button.setObjectName("PrimaryButton")
        self.wired_connect_button.clicked.connect(self._toggle_connection)
        row.addWidget(self.port_selector, 1)
        row.addWidget(self.refresh_ports_button)
        row.addWidget(self.wired_connect_button)
        layout.addLayout(row)

        serial_hint = QLabel("Fixed serial setting: 115200 baud / 8N1")
        serial_hint.setObjectName("SectionHint")
        layout.addWidget(serial_hint)
        return frame

    def _build_status_panel(self) -> QWidget:
        frame = CollapsiblePanel(
            "Device Status",
            "This section reflects the latest normalized status snapshot.",
            expanded=False,
        )
        layout = frame.content_layout
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.pump_state_value = QLabel("OFF")
        self.heater_power_state_value = QLabel("OFF")
        self.transport_state_value = QLabel("Disconnected")
        self.status_flags_value = QLabel("0x00000000")
        self.sample_period_value = QLabel("--")
        self.firmware_value = QLabel("--")
        self.protocol_value = QLabel("--")
        self.gap_value = QLabel("0")
        self.zirconia_ip_value = QLabel("--")
        self.internal_voltage_value = QLabel("--")

        rows = [
            ("Pump State", self.pump_state_value),
            ("Heater Power", self.heater_power_state_value),
            ("Transport", self.transport_state_value),
            ("Status Flags", self.status_flags_value),
            ("Sample Period", self.sample_period_value),
            ("Firmware", self.firmware_value),
            ("Protocol", self.protocol_value),
            ("Sequence Gaps", self.gap_value),
            ("Zirconia Ip", self.zirconia_ip_value),
            ("Internal Voltage", self.internal_voltage_value),
        ]
        for row_index, (name, value_label) in enumerate(rows):
            grid.addWidget(QLabel(name), row_index, 0)
            grid.addWidget(value_label, row_index, 1)

        layout.addLayout(grid)
        settings_row = QHBoxLayout()
        settings_row.setSpacing(8)
        self.status_settings_button = QPushButton("Settings")
        self.status_settings_button.setObjectName("SecondaryButton")
        self.status_settings_button.clicked.connect(self._open_settings)
        settings_row.addWidget(self.status_settings_button)
        settings_row.addStretch(1)
        layout.addLayout(settings_row)
        return frame

    def _build_controls_panel(self) -> QWidget:
        frame, layout = _panel("Controls", "Commands are routed through the shared controller layer.")
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(8)
        self.pump_toggle_button = QPushButton("Start Pump")
        self.pump_toggle_button.setObjectName("ToggleButton")
        self.pump_toggle_button.setCheckable(True)
        self.pump_toggle_button.clicked.connect(self._toggle_pump_from_button)
        toggle_row.addWidget(self.pump_toggle_button)
        self.heater_toggle_button = QPushButton("Enable Heater")
        self.heater_toggle_button.setObjectName("ToggleButton")
        self.heater_toggle_button.setCheckable(True)
        self.heater_toggle_button.clicked.connect(self._toggle_heater_from_button)
        toggle_row.addWidget(self.heater_toggle_button)
        toggle_row.addStretch(1)
        layout.addLayout(toggle_row)
        return frame

    def _build_recording_panel(self) -> QWidget:
        frame, layout = _panel("Recording", "Session files are written as .partial.csv and finalized to .csv on stop.")
        frame.setObjectName("RecordingPanel")
        frame.setProperty("recordingActive", False)
        self.recording_panel_frame = frame

        state_row = QHBoxLayout()
        state_row.setSpacing(8)
        self.recording_state_badge = QLabel("Idle")
        self.recording_state_badge.setObjectName("RecordingStateBadge")
        self.recording_state_badge.setProperty("recordingActive", False)
        self.recording_state_detail = QLabel("No active session.")
        self.recording_state_detail.setObjectName("SectionHint")
        state_row.addWidget(self.recording_state_badge, 0)
        state_row.addWidget(self.recording_state_detail, 1)
        layout.addLayout(state_row)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.record_toggle_button = QPushButton("Start Recording")
        self.record_toggle_button.setObjectName("RecordToggleButton")
        self.record_toggle_button.setCheckable(True)
        self.record_toggle_button.clicked.connect(self._toggle_recording_from_button)
        row.addWidget(self.record_toggle_button)
        row.addStretch(1)
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
        layout.setSpacing(10)

        cards = QWidget()
        cards_layout = QHBoxLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)

        self.metric_zirconia = MetricCard("Zirconia Output Voltage", "V")
        self.metric_o2 = MetricCard("O2 Concentration (1-cell)", "%")
        self.metric_heater = MetricCard("Heater RTD Resistance", "Ohm")
        self.metric_flow = MetricCard("Flow Rate", "L/min")
        cards_layout.addWidget(self.metric_flow, 1)
        cards_layout.addWidget(self.metric_o2, 1)
        cards_layout.addWidget(self.metric_zirconia, 1)
        cards_layout.addWidget(self.metric_heater, 1)
        layout.addWidget(cards)

        toolbar, toolbar_layout = _panel("Plot Toolbar", "Time range, time-axis display, and view reset controls.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
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
        self.reset_view_button = QPushButton("Reset View")
        self.reset_view_button.setObjectName("SecondaryButton")
        self.reset_view_button.clicked.connect(self._reset_plot_view)

        grid.addWidget(QLabel("Span"), 0, 0)
        grid.addWidget(self.time_span_combo, 0, 1)
        grid.addWidget(QLabel("Axis"), 0, 2)
        grid.addWidget(self.axis_mode_combo, 0, 3)
        grid.addWidget(self.auto_scale_check, 0, 4)
        grid.addWidget(self.reset_view_button, 0, 5)
        toolbar_layout.addLayout(grid)
        layout.addWidget(toolbar)

        pg.setConfigOptions(antialias=False)
        self.plot_widgets: dict[str, pg.PlotWidget] = {}
        self.plot_curves: dict[str, object] = {}

        self.plot_splitter = QSplitter(Qt.Vertical)
        self.plot_splitter.setChildrenCollapsible(False)
        self.plot_splitter.setHandleWidth(10)
        self.plot_splitter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.plot_splitter.setFixedHeight(600)
        layout.addWidget(self.plot_splitter, 0)

        sensor_frame, sensor_layout = _panel("Flow / O2 Concentration", "Blue: flow rate, orange: O2 concentration when calibrated.")
        sensor_frame.setMinimumHeight(260)
        sensor_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sensor_view_box = PlotInteractionViewBox("sensor", self._handle_plot_user_interaction)
        sensor_axis_items = {
            "bottom": TimeAxisItem(
                "bottom",
                "sensor",
                "x",
                self._handle_plot_user_interaction,
                self._current_axis_mode,
                self._session_start_time,
            ),
            "left": PlotInteractionAxisItem("left", "sensor", "y", self._handle_plot_user_interaction),
            "right": PlotInteractionAxisItem("right", "sensor_o2", "y", self._handle_plot_user_interaction),
        }
        sensor_plot = pg.PlotWidget(viewBox=sensor_view_box, axisItems=sensor_axis_items)
        self._configure_plot_widget(sensor_plot)
        sensor_plot.setMinimumHeight(180)
        sensor_legend = sensor_plot.addLegend(offset=(10, 10))
        sensor_plot.getPlotItem().showAxis("right")
        sensor_plot.getPlotItem().getAxis("left").setLabel("Flow (L/min)")
        sensor_plot.getPlotItem().getAxis("right").setLabel("O2 (%)")
        sensor_plot.getPlotItem().getAxis("right").setTextPen(QColor("#B5781A"))
        sensor_plot.getPlotItem().getAxis("right").setPen(QColor("#B5781A"))
        sensor_view_box.sigRangeChangedManually.connect(self._on_plot_range_changed_manually)
        self._viewbox_to_plot_key[sensor_view_box] = "sensor"
        sensor_curve = sensor_plot.plot(pen=pg.mkPen(color="#315C8C", width=2.1), name="Flow")
        sensor_curve.setSkipFiniteCheck(True)

        self.sensor_secondary_view = pg.ViewBox()
        self.sensor_secondary_view.setMouseEnabled(x=False, y=False)
        sensor_plot.scene().addItem(self.sensor_secondary_view)
        sensor_plot.getPlotItem().getAxis("right").linkToView(self.sensor_secondary_view)
        self.sensor_secondary_view.setXLink(sensor_plot.getPlotItem().vb)
        self.sensor_secondary_curve = pg.PlotCurveItem(pen=pg.mkPen(color="#B5781A", width=2.0))
        self.sensor_secondary_curve.setSkipFiniteCheck(True)
        self.sensor_secondary_view.addItem(self.sensor_secondary_curve)
        self._secondary_y_views["sensor_o2"] = self.sensor_secondary_view
        sensor_legend.addItem(self.sensor_secondary_curve, "O2")
        self.sensor_secondary_legend_item = sensor_legend.items[-1]
        sensor_plot.getPlotItem().vb.sigResized.connect(self._update_sensor_secondary_geometry)
        sensor_layout.addWidget(sensor_plot)
        self.plot_splitter.addWidget(sensor_frame)
        self.plot_widgets["sensor"] = sensor_plot
        self.plot_curves["sensor"] = sensor_curve

        heater_frame, heater_layout = _panel("Zirconia Output Voltage / Heater RTD Resistance")
        heater_frame.setMinimumHeight(180)
        heater_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        heater_view_box = PlotInteractionViewBox("heater", self._handle_plot_user_interaction)
        heater_axis_items = {
            "bottom": TimeAxisItem(
                "bottom",
                "heater",
                "x",
                self._handle_plot_user_interaction,
                self._current_axis_mode,
                self._session_start_time,
            ),
            "left": PlotInteractionAxisItem("left", "heater", "y", self._handle_plot_user_interaction),
            "right": PlotInteractionAxisItem(
                "right",
                "heater_zirconia",
                "y",
                self._handle_plot_user_interaction,
            ),
        }
        heater_plot = pg.PlotWidget(viewBox=heater_view_box, axisItems=heater_axis_items)
        self._configure_plot_widget(heater_plot)
        heater_plot.setMinimumHeight(140)
        heater_legend = heater_plot.addLegend(offset=(10, 10))
        heater_plot.getPlotItem().showAxis("right")
        heater_plot.getPlotItem().getAxis("left").setLabel("Heater (Ohm)")
        heater_plot.getPlotItem().getAxis("right").setLabel("Zirconia (V)")
        heater_plot.getPlotItem().getAxis("right").setTextPen(QColor("#315C8C"))
        heater_plot.getPlotItem().getAxis("right").setPen(QColor("#315C8C"))
        heater_view_box.sigRangeChangedManually.connect(self._on_plot_range_changed_manually)
        self._viewbox_to_plot_key[heater_view_box] = "heater"
        heater_curve = heater_plot.plot(pen=pg.mkPen(color="#5E7D4B", width=2.1), name="Heater")
        heater_curve.setSkipFiniteCheck(True)

        self.heater_secondary_view = pg.ViewBox()
        self.heater_secondary_view.setMouseEnabled(x=False, y=False)
        heater_plot.scene().addItem(self.heater_secondary_view)
        heater_plot.getPlotItem().getAxis("right").linkToView(self.heater_secondary_view)
        self.heater_secondary_view.setXLink(heater_plot.getPlotItem().vb)
        self.heater_secondary_curve = pg.PlotCurveItem(pen=pg.mkPen(color="#315C8C", width=2.0))
        self.heater_secondary_curve.setSkipFiniteCheck(True)
        self.heater_secondary_view.addItem(self.heater_secondary_curve)
        self._secondary_y_views["heater_zirconia"] = self.heater_secondary_view
        heater_legend.addItem(self.heater_secondary_curve, "Zirconia")
        self.heater_secondary_legend_item = heater_legend.items[-1]
        heater_plot.getPlotItem().vb.sigResized.connect(self._update_heater_secondary_geometry)
        heater_layout.addWidget(heater_plot)
        self.plot_splitter.addWidget(heater_frame)
        self.plot_widgets["heater"] = heater_plot
        self.plot_curves["heater"] = heater_curve

        self.plot_widgets["heater"].setXLink(self.plot_widgets["sensor"])
        self._apply_default_plot_ranges()
        QTimer.singleShot(0, self._apply_plot_splitter_sizes)

        log_frame = CollapsiblePanel(
            "Warning / Event Log",
            "Review runtime warnings, events, and transport diagnostics.",
            expanded=False,
        )
        log_frame.setObjectName("WarningCard")
        log_layout = log_frame.content_layout
        self.log_pane = QPlainTextEdit()
        self.log_pane.setObjectName("LogPane")
        self.log_pane.setReadOnly(True)
        self.log_pane.setMinimumHeight(225)
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
        self._refresh_metric_cards()
        self._sync_pump_toggle()
        self._sync_heater_toggle()
        self._sync_recording_controls()
        self._refresh_plots()

    def _current_recording_directory(self):
        return self.settings_store.recording_directory_path(self.app_settings)

    def _persist_current_settings(self) -> None:
        self.app_settings.last_mode = self.mode
        self.app_settings.plot.time_span = self.time_span_combo.currentText()
        self.app_settings.plot.axis_mode = self.axis_mode_combo.currentText()
        self.app_settings.plot.auto_scale = self.auto_scale_check.isChecked()
        self.app_settings.plot.selected_plot = self._plot_label_for_key(self._active_plot_key)
        self.app_settings.plot.x_follow_enabled = self.plot_controller.x_follow_enabled
        self.app_settings.plot.manual_y_ranges = dict(self.plot_controller.manual_y_ranges)
        self.app_settings.windows.main_window_width = self.width()
        self.app_settings.windows.main_window_height = self.height()
        self.settings_store.save(self.app_settings)

    def _apply_dialog_settings(self, dialog: SettingsDialog) -> None:
        self.app_settings.plot.time_span = dialog.selected_time_span
        self.app_settings.plot.axis_mode = dialog.selected_axis_mode
        self.app_settings.plot.auto_scale = dialog.selected_auto_scale
        self.app_settings.plot.selected_plot = dialog.selected_plot
        self.app_settings.logging.recording_directory = dialog.recording_directory
        self.app_settings.logging.partial_recovery_notice_enabled = dialog.partial_recovery_notice_enabled
        self.app_settings.o2.air_calibration_voltage_v = dialog.selected_o2_air_calibration_voltage_v
        self.app_settings.o2.calibrated_at_iso = dialog.selected_o2_calibrated_at_iso

    def _apply_settings_to_widgets(self) -> None:
        self.time_span_combo.setCurrentText(self.app_settings.plot.time_span)
        self.axis_mode_combo.setCurrentText(self.app_settings.plot.axis_mode)
        self.auto_scale_check.setChecked(self.app_settings.plot.auto_scale)
        self._active_plot_key = self._plot_key_from_label(self.app_settings.plot.selected_plot)
        self.plot_controller.x_follow_enabled = self.app_settings.plot.x_follow_enabled
        self.plot_controller.manual_y_ranges = dict(self.app_settings.plot.manual_y_ranges)
        for plot_key, y_range in self.plot_controller.manual_y_ranges.items():
            if plot_key in self.plot_widgets:
                plot = self.plot_widgets[plot_key]
                plot.enableAutoRange(axis="y", enable=False)
                plot.setYRange(y_range[0], y_range[1], padding=0.02)
            elif plot_key in self._secondary_y_views:
                view = self._secondary_y_views[plot_key]
                view.enableAutoRange(axis="y", enable=False)
                view.setYRange(y_range[0], y_range[1], padding=0.02)
        self._update_axis_labels()
        self._update_sensor_secondary_visibility()

    def _prime_mode_specific_lists(self) -> None:
        if self.mode == BLE_MODE:
            self.ble_device_selector.clear()
            self.ble_device_selector.addItem("Scanning for compatible BLE device...")
            self.ble_device_selector.setEnabled(False)
            self._append_log("info", "BLE mode is ready. Starting an initial scan for compatible devices.")
            QTimer.singleShot(0, self.connection_controller.scan_ble_devices)
            return

        self.port_selector.clear()
        self.port_selector.addItem("Scanning for compatible serial device...")
        self.port_selector.setEnabled(False)
        self.connection_controller.refresh_ports()
        self._append_log("info", f"{self.mode} mode is ready for visual review.")

    def _sync_connection_stack(self) -> None:
        self.connection_stack.setCurrentIndex(0 if self.mode == BLE_MODE else 1)

    def _sync_connection_controls(self) -> None:
        connected = self.connection_controller.is_connected()
        connect_text = "Disconnect" if connected else "Connect"
        ble_available = self._has_expected_ble_selection()
        wired_available = self._has_expected_wired_selection()
        self.ble_connect_button.setText(connect_text)
        self.wired_connect_button.setText(connect_text)
        self.ble_connect_button.setEnabled(connected or ble_available)
        self.wired_connect_button.setEnabled(connected or wired_available)
        self.ble_device_selector.setEnabled((not connected) and ble_available)
        self.ble_scan_button.setEnabled(not connected)
        self.port_selector.setEnabled((not connected) and wired_available)
        self.refresh_ports_button.setEnabled(not connected)

    def _toggle_connection(self) -> None:
        if self.connection_controller.is_connected():
            self.ui_state.connection.phase = "disconnecting"
            self.connection_controller.disconnect_device()
            return
        if self.mode == BLE_MODE:
            identifier = self.ble_device_selector.currentText().strip() or "M5STAMP-MONITOR"
        else:
            identifier = self.port_selector.currentText() or "Prototype-Port"
        self.ui_state.connection.phase = "connecting"
        self.connection_controller.connect_device(identifier)

    def _on_connection_changed(self, connected: bool, identifier: str) -> None:
        had_plot_samples = bool(self.plot_controller.time_values)
        self.ui_state.connection.phase = "connected" if connected else "disconnected"
        self.ui_state.connection.identifier = identifier if connected else "Disconnected"
        self.transport_state_value.setText("Connected" if connected else "Disconnected")
        self._sync_connection_controls()
        self._sync_pump_toggle()
        self._sync_heater_toggle()
        for severity, message in self.telemetry_health_monitor.on_connection_changed(connected, identifier):
            self._append_log(severity, message)
        for severity, message in self.telemetry_session_stats.on_connection_changed(connected, identifier):
            self._append_log(severity, message)
        if not connected:
            self._stop_recording()
            self._clear_plot_buffers()
            self._refresh_metric_cards({})
            if had_plot_samples:
                self._append_log("info", "Cleared plot data after disconnect.")
            if self._pending_mode_switch_target is not None:
                pending_target = self._pending_mode_switch_target
                self._pending_mode_switch_target = None
                self._complete_mode_switch(pending_target)
        self._sync_recording_controls()

    def _on_status_changed(self, payload: dict) -> None:
        self.pump_state_value.setText(str(payload["pump_state"]))
        self.heater_power_state_value.setText(str(payload.get("heater_power_state", "OFF")))
        self.transport_state_value.setText(str(payload["transport_state"]))
        self.status_flags_value.setText(str(payload["status_flags_hex"]))
        self.sample_period_value.setText(f"{payload['nominal_sample_period_ms']} ms")
        self.firmware_value.setText(str(payload["firmware_version"]))
        self.protocol_value.setText(str(payload["protocol_version"]))
        self.ui_state.session_metadata.firmware_version = str(payload["firmware_version"])
        self.ui_state.session_metadata.protocol_version = str(payload["protocol_version"])
        self.ui_state.session_metadata.nominal_sample_period_ms = str(payload["nominal_sample_period_ms"])
        self.telemetry_health_monitor.update_nominal_sample_period(payload["nominal_sample_period_ms"])
        self.telemetry_session_stats.update_nominal_sample_period(payload["nominal_sample_period_ms"])
        self._latest_zirconia_ip_voltage_v = payload.get("zirconia_ip_voltage_v")
        self._latest_internal_voltage_v = payload.get("internal_voltage_v")
        self._update_service_visibility_labels()
        self._sync_pump_toggle()
        self._sync_heater_toggle()

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
        self.telemetry_session_stats.update_nominal_sample_period(nominal)

    def _on_ble_devices_discovered(self, devices: list[str]) -> None:
        current = self.ble_device_selector.currentText()
        self.ble_device_selector.clear()
        if devices:
            self.ble_device_selector.addItems(devices)
            preferred_index = max(0, self.ble_device_selector.findText(current))
            self.ble_device_selector.setCurrentIndex(preferred_index)
        else:
            self.ble_device_selector.addItem("No compatible BLE device detected")
        self._sync_connection_controls()

    def _on_ports_discovered(self, ports: list[str]) -> None:
        self.port_selector.clear()
        if ports:
            self.port_selector.addItems(ports)
        else:
            self.port_selector.addItem("No compatible serial device detected")
        self._sync_connection_controls()

    def _on_telemetry(self, point: TelemetryPoint) -> None:
        plot_update = self.plot_controller.append_sample(point)
        if float(plot_update["elapsed_seconds"]) == 0.0:
            self._session_started = point.host_received_at
        self.telemetry_session_stats.on_telemetry(point)
        self.pump_state_value.setText("ON" if (point.status_flags & STATUS_FLAG_PUMP_ON) != 0 else "OFF")
        self.heater_power_state_value.setText("ON" if (point.status_flags & STATUS_FLAG_HEATER_POWER_ON) != 0 else "OFF")
        self.gap_value.setText(str(plot_update["sequence_gap_total"]))
        self._latest_low_range_differential_pressure_pa = point.differential_pressure_low_range_pa
        self._latest_high_range_differential_pressure_pa = point.differential_pressure_high_range_pa
        self._latest_zirconia_ip_voltage_v = point.zirconia_ip_voltage_v
        self._latest_internal_voltage_v = point.internal_voltage_v
        self._update_service_visibility_labels()
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
        self._refresh_metric_cards(metrics, point)

        if self.recording_controller.is_recording and self.recording_controller.started_at is not None:
            elapsed_record = max(0, int((datetime.now() - self.recording_controller.started_at).total_seconds()))
            mins, secs = divmod(elapsed_record, 60)
            self.elapsed_value.setText(f"{mins:02d}:{secs:02d}")
        self._sync_pump_toggle()
        self._sync_heater_toggle()

    def _refresh_plots(self) -> None:
        time_span = self.time_span_combo.currentText()
        render_data = self.plot_controller.render_data(time_span)
        x_values = render_data["x_values"]
        if not x_values:
            return

        flow_values = render_data["series"]["flow"]
        zirconia_values = render_data["series"]["zirconia"]
        heater_values = render_data["series"]["heater"]
        data_key = (
            render_data["revision"],
            time_span,
            self.app_settings.o2.air_calibration_voltage_v,
            self.app_settings.o2.zero_reference_voltage_v,
            self.app_settings.o2.ambient_reference_percent,
            self.app_settings.o2.invert_polarity,
        )
        if data_key != self._last_plot_data_key:
            o2_values = self._build_o2_series(zirconia_values)

            self.plot_curves["sensor"].setData(x_values, flow_values)
            if o2_values is None:
                self.sensor_secondary_curve.setData([], [])
            else:
                self.sensor_secondary_curve.setData(x_values, o2_values)
            self._update_sensor_secondary_visibility()

            self.plot_curves["heater"].setData(x_values, heater_values)
            self.heater_secondary_curve.setData(x_values, zirconia_values)
        self._last_plot_data_key = data_key
        if self.plot_controller.x_follow_enabled:
            self._set_plot_x_range(render_data["xmin"], render_data["xmax"])

    def _update_axis_labels(self) -> None:
        label = "Elapsed time" if self._current_axis_mode() == "Relative" else "Clock time"
        for plot in self.plot_widgets.values():
            plot.setLabel("bottom", label)
            plot.getPlotItem().getAxis("bottom").picture = None
            plot.getPlotItem().getAxis("bottom").update()

    def _on_axis_mode_changed(self) -> None:
        self._update_axis_labels()
        self._refresh_plots()
        self._persist_current_settings()

    def _on_time_span_changed(self) -> None:
        self.plot_controller.x_follow_enabled = True
        self.app_settings.plot.x_follow_enabled = True
        self._refresh_plots()
        self._persist_current_settings()

    def _on_auto_scale_toggled(self, checked: bool) -> None:
        if checked:
            self.plot_widgets["sensor"].enableAutoRange(axis="y", enable=True)
            self.sensor_secondary_view.enableAutoRange(axis="y", enable=True)
            self.plot_widgets["heater"].enableAutoRange(axis="y", enable=True)
            self.heater_secondary_view.enableAutoRange(axis="y", enable=True)
            self.plot_controller.manual_y_ranges.clear()
        self._persist_current_settings()

    def _reset_plot_view(self) -> None:
        self.plot_controller.x_follow_enabled = True
        for plot_key in ["sensor", "sensor_o2", "heater", "heater_zirconia"]:
            self.plot_controller.manual_y_ranges.pop(plot_key, None)
        self._apply_default_plot_ranges()
        self.plot_widgets["heater"].enableAutoRange(axis="y", enable=self.auto_scale_check.isChecked())
        self.heater_secondary_view.enableAutoRange(axis="y", enable=True)
        self._last_plot_data_key = None
        self._refresh_plots()
        self._persist_current_settings()

    def _set_plot_x_range(self, xmin: float, xmax: float) -> None:
        if "sensor" not in self.plot_widgets:
            return
        self._ignore_manual_range_signal = True
        try:
            self.plot_widgets["sensor"].setXRange(xmin, xmax, padding=0.0)
        finally:
            self._ignore_manual_range_signal = False

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

        if plot_key is not None:
            self._active_plot_key = self._primary_plot_key(plot_key)

        if y_changed and plot_key is not None:
            if self.auto_scale_check.isChecked():
                self.auto_scale_check.blockSignals(True)
                self.auto_scale_check.setChecked(False)
                self.auto_scale_check.blockSignals(False)
            view = self._y_range_view_for_plot_key(plot_key)
            if view is not None:
                _, y_range = view.viewRange()
                self.plot_controller.set_manual_y_range(plot_key, y_range[0], y_range[1])

        self._persist_current_settings()

    def _sync_recording_controls(self) -> None:
        can_toggle = self._has_expected_connected_device() or self.recording_controller.is_recording
        self.record_toggle_button.setEnabled(can_toggle)
        checked = self.recording_controller.is_recording
        self.record_toggle_button.blockSignals(True)
        self.record_toggle_button.setChecked(checked)
        self.record_toggle_button.setText("Stop Recording" if checked else "Start Recording")
        self.record_toggle_button.blockSignals(False)
        self._sync_recording_emphasis(checked)

    def _sync_recording_emphasis(self, active: bool) -> None:
        self.recording_panel_frame.setProperty("recordingActive", active)
        self.recording_state_badge.setProperty("recordingActive", active)
        self.recording_state_badge.setText("REC ACTIVE" if active else "Idle")
        self.recording_state_detail.setText(
            "Session is being written to a partial CSV file."
            if active
            else "No active session."
        )
        for widget in (self.recording_panel_frame, self.recording_state_badge):
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            widget.update()

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
        if not self._has_expected_connected_device():
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

    def _toggle_pump_from_button(self, checked: bool) -> None:
        if not self._has_expected_connected_device():
            self._append_log("warn", "Connect to a device before controlling the pump.")
            self._sync_pump_toggle()
            return
        self.connection_controller.set_pump_state(checked)

    def _toggle_heater_from_button(self, checked: bool) -> None:
        if not self._has_expected_connected_device():
            self._append_log("warn", "Connect to a device before controlling the heater.")
            self._sync_heater_toggle()
            return
        if checked and self.pump_state_value.text() != "ON":
            self._append_log("warn", "Heater can only be enabled while the pump is ON.")
            self._sync_heater_toggle()
            return
        self.connection_controller.set_heater_power_state(checked)

    def _toggle_recording_from_button(self, checked: bool) -> None:
        if checked:
            self._start_recording()
        else:
            self._stop_recording()
        self._sync_recording_controls()

    def _sync_pump_toggle(self) -> None:
        is_on = self.pump_state_value.text() == "ON"
        self.pump_toggle_button.setEnabled(self._has_expected_connected_device())
        self.pump_toggle_button.blockSignals(True)
        self.pump_toggle_button.setChecked(is_on)
        self.pump_toggle_button.setText("Stop Pump" if is_on else "Start Pump")
        self.pump_toggle_button.blockSignals(False)

    def _sync_heater_toggle(self) -> None:
        connected = self._has_expected_connected_device()
        pump_on = self.pump_state_value.text() == "ON"
        heater_on = self.heater_power_state_value.text() == "ON"
        self.heater_toggle_button.setEnabled(connected and (pump_on or heater_on))
        self.heater_toggle_button.blockSignals(True)
        self.heater_toggle_button.setChecked(heater_on)
        self.heater_toggle_button.setText("Disable Heater" if heater_on else "Enable Heater")
        self.heater_toggle_button.blockSignals(False)

    def _append_log(self, severity: str, message: str) -> None:
        entry = self.warning_controller.append(severity, message)
        self.log_pane.appendPlainText(f"[{entry.timestamp.strftime('%H:%M:%S')}] {entry.severity.upper():<5} {entry.message}")

    def _poll_telemetry_health(self) -> None:
        for severity, message in self.telemetry_health_monitor.poll():
            self._append_log(severity, message)

    def _open_settings(self) -> None:
        current_metrics = self.plot_controller.metric_snapshot()
        current_zirconia_voltage_v = current_metrics.get("zirconia_output_voltage_v")
        if current_zirconia_voltage_v is not None and not math.isfinite(current_zirconia_voltage_v):
            current_zirconia_voltage_v = None

        dialog = SettingsDialog(
            self.app_settings,
            current_mode=self.mode,
            connection_identifier=self.ui_state.connection.identifier,
            current_zirconia_voltage_v=current_zirconia_voltage_v,
            flow_verification_summary=self._latest_flow_verification_summary(),
            flow_verification_recent_summaries=self._recent_flow_verification_summaries(),
            flow_verification_available=self._has_expected_connected_device(),
            flow_characterization_available=self._has_expected_connected_device(),
            parent=self,
        )
        dialog.device_action_requested.connect(self._handle_settings_device_action)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        previous_mode = self.mode
        requested_mode = dialog.requested_mode
        flow_verification_requested = dialog.flow_verification_requested
        flow_verification_details_requested = dialog.flow_verification_details_requested
        flow_verification_history_requested = dialog.flow_verification_history_requested
        flow_characterization_requested = dialog.flow_characterization_requested
        previous_o2_air_calibration_voltage_v = self.app_settings.o2.air_calibration_voltage_v
        previous_o2_calibrated_at_iso = self.app_settings.o2.calibrated_at_iso
        if flow_verification_history_requested:
            self._open_flow_verification_history_dialog()
            return
        if flow_verification_details_requested:
            self._open_flow_verification_details_dialog()
            return
        if flow_verification_requested:
            self._open_flow_verification_dialog()
            return
        if flow_characterization_requested:
            self._open_flow_characterization_dialog()
            return
        self._apply_dialog_settings(dialog)
        if requested_mode == previous_mode:
            self.app_settings.last_mode = previous_mode
            self._apply_settings_to_widgets()
            self._refresh_metric_cards()
            self._persist_current_settings()
            self._log_o2_calibration_changes(
                previous_o2_air_calibration_voltage_v,
                previous_o2_calibrated_at_iso,
            )
            self._append_log("info", "Settings updated.")
            return

        confirm = ModeSwitchDialog(previous_mode, requested_mode, self)
        if confirm.exec() != QDialog.DialogCode.Accepted:
            self.app_settings.last_mode = previous_mode
            self._apply_settings_to_widgets()
            self._persist_current_settings()
            return
        self._log_o2_calibration_changes(
            previous_o2_air_calibration_voltage_v,
            previous_o2_calibrated_at_iso,
        )
        if flow_verification_requested:
            self._append_log(
                "info",
                "Flow verification request was staged, but reconnect in the new mode before starting it.",
            )
        if flow_characterization_requested:
            self._append_log(
                "info",
                "Flow characterization request was staged, but reconnect in the new mode before starting it.",
            )
        self._switch_mode(requested_mode)

    def _switch_mode(self, new_mode: str) -> None:
        if self.connection_controller.is_connected():
            self._pending_mode_switch_target = new_mode
            self.ui_state.connection.phase = "disconnecting"
            self._append_log("info", f"Disconnecting current session before switching to {new_mode}.")
            self.connection_controller.disconnect_device()
            return
        self._complete_mode_switch(new_mode)

    def _complete_mode_switch(self, new_mode: str) -> None:
        self._stop_recording()
        self.mode = new_mode
        self.ui_state.mode = new_mode
        self.app_settings.last_mode = new_mode
        self.telemetry_health_monitor.set_mode(new_mode)
        self.connection_controller.set_mode(new_mode)
        self._clear_plot_buffers()
        self._sync_connection_stack()
        self._sync_connection_controls()
        self._apply_settings_to_widgets()
        self._prime_mode_specific_lists()
        self.metric_zirconia.set_value("--")
        self.metric_o2.set_value("Calibrate")
        self.metric_heater.set_value("--")
        self.metric_flow.set_value("--")
        self.metric_flow.set_detail("")
        self._sync_pump_toggle()
        self._sync_heater_toggle()
        self._sync_recording_controls()
        self._persist_current_settings()
        self._append_log("info", f"Mode switched to {new_mode}.")

    def _handle_settings_device_action(self, action: str) -> None:
        if action == "get_status":
            self.connection_controller.request_status()
        elif action == "get_capabilities":
            self.connection_controller.request_capabilities()
        elif action == "ping":
            self.connection_controller.ping()

    def _flow_verification_persistence(self) -> FlowVerificationPersistence:
        return FlowVerificationPersistence(self._current_recording_directory())

    def _flow_characterization_persistence(self) -> FlowCharacterizationPersistence:
        return FlowCharacterizationPersistence(self._current_recording_directory())

    def _latest_flow_verification_summary(self):
        return self._flow_verification_persistence().load_latest_summary()

    def _latest_flow_verification_session(self):
        return self._flow_verification_persistence().load_latest_session()

    def _recent_flow_verification_summaries(self):
        return self._flow_verification_persistence().list_recent_summaries(limit=5)

    def _open_flow_verification_dialog(self) -> None:
        if not self._has_expected_connected_device():
            self._append_log("warn", "Connect to an expected device before starting flow verification.")
            return

        controller = FlowVerificationController(
            mode=self.mode,
            transport_type=transport_type_for_mode(self.mode),
            device_identifier=self.ui_state.connection.identifier,
            firmware_version="" if self.firmware_value.text() == "--" else self.firmware_value.text(),
            protocol_version="" if self.protocol_value.text() == "--" else self.protocol_value.text(),
            parent=self,
        )
        persistence = self._flow_verification_persistence()
        controller.on_connection_changed(
            self.connection_controller.is_connected(),
            self.ui_state.connection.identifier,
        )
        self.connection_controller.telemetry_received.connect(controller.on_telemetry)
        self.connection_controller.connection_changed.connect(controller.on_connection_changed)
        try:
            dialog = FlowVerificationDialog(controller, persistence, parent=self)
            if self.mode == BLE_MODE:
                self._append_log(
                    "info",
                    "Flow verification opened in BLE mode. Wired mode is still recommended for the highest-fidelity flow checks.",
                )
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_session_path is not None:
                self._append_log(
                    "info",
                    f"Flow verification saved: {dialog.saved_session_path}",
                )
        finally:
            self.connection_controller.telemetry_received.disconnect(controller.on_telemetry)
            self.connection_controller.connection_changed.disconnect(controller.on_connection_changed)

    def _open_flow_verification_details_dialog(self) -> None:
        session = self._latest_flow_verification_session()
        if session is None:
            self._append_log("warn", "No saved flow verification session is available yet.")
            return
        summary = self._latest_flow_verification_summary()
        session_path = Path(summary.path) if summary is not None and summary.path else None
        dialog = FlowVerificationDetailsDialog(session, session_path=session_path, parent=self)
        dialog.exec()

    def _open_flow_verification_history_dialog(self) -> None:
        persistence = self._flow_verification_persistence()
        summaries = persistence.list_recent_summaries(limit=12)
        if not summaries:
            self._append_log("warn", "No saved flow verification history is available yet.")
            return
        dialog = FlowVerificationHistoryDialog(summaries, persistence, parent=self)
        dialog.exec()

    def _open_flow_characterization_dialog(self) -> None:
        if not self._has_expected_connected_device():
            self._append_log("warn", "Connect to an expected device before starting flow characterization.")
            return

        controller = FlowCharacterizationController(
            mode=self.mode,
            transport_type=transport_type_for_mode(self.mode),
            device_identifier=self.ui_state.connection.identifier,
            firmware_version="" if self.firmware_value.text() == "--" else self.firmware_value.text(),
            protocol_version="" if self.protocol_value.text() == "--" else self.protocol_value.text(),
            parent=self,
        )
        persistence = self._flow_characterization_persistence()
        controller.on_connection_changed(
            self.connection_controller.is_connected(),
            self.ui_state.connection.identifier,
        )
        self.connection_controller.telemetry_received.connect(controller.on_telemetry)
        self.connection_controller.connection_changed.connect(controller.on_connection_changed)
        try:
            dialog = FlowCharacterizationDialog(controller, persistence, parent=self)
            if self.mode == BLE_MODE:
                self._append_log(
                    "warn",
                    "Flow characterization opened in BLE mode. Wired mode is recommended because raw SDP810 / SDP811 fields may be unavailable over BLE.",
                )
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_session_result is not None:
                self._append_log(
                    "info",
                    f"Flow characterization saved: {dialog.saved_session_result.json_path}",
                )
                self._append_log(
                    "info",
                    f"Flow characterization samples saved: {dialog.saved_session_result.csv_path}",
                )
        finally:
            self.connection_controller.telemetry_received.disconnect(controller.on_telemetry)
            self.connection_controller.connection_changed.disconnect(controller.on_connection_changed)

    def _clear_plot_buffers(self) -> None:
        self.plot_controller.clear()
        self.gap_value.setText("0")
        self._session_started = datetime.now()
        self._latest_low_range_differential_pressure_pa = None
        self._latest_high_range_differential_pressure_pa = None
        self._latest_zirconia_ip_voltage_v = None
        self._latest_internal_voltage_v = None
        self._update_service_visibility_labels()
        for curve in self.plot_curves.values():
            curve.setData([], [])
        self.sensor_secondary_curve.setData([], [])
        self.heater_secondary_curve.setData([], [])
        self._last_plot_data_key = None

    def _refresh_metric_cards(self, metrics: dict[str, float] | None = None, point: TelemetryPoint | None = None) -> None:
        metrics = metrics or self.plot_controller.metric_snapshot()
        zirconia_value = metrics.get("zirconia_output_voltage_v")
        heater_value = metrics.get("heater_rtd_resistance_ohm")
        flow_value = metrics.get("flow_rate_lpm")
        low_range_differential_pressure_pa = self._latest_low_range_differential_pressure_pa
        high_range_differential_pressure_pa = self._latest_high_range_differential_pressure_pa
        selected_differential_pressure_pa = None

        if point is not None:
            zirconia_value = zirconia_value if zirconia_value is not None else point.zirconia_output_voltage_v
            heater_value = heater_value if heater_value is not None else point.heater_rtd_resistance_ohm
            flow_value = flow_value if flow_value is not None else 0.0
            selected_differential_pressure_pa = point.differential_pressure_selected_pa
            low_range_differential_pressure_pa = point.differential_pressure_low_range_pa
            high_range_differential_pressure_pa = point.differential_pressure_high_range_pa
        elif self.plot_controller.differential_pressure_selected_values:
            latest_selected = self.plot_controller.differential_pressure_selected_values[-1]
            if math.isfinite(latest_selected):
                selected_differential_pressure_pa = latest_selected

        self.metric_zirconia.set_value("--" if zirconia_value is None else f"{zirconia_value:0.3f} V")
        self.metric_heater.set_value("--" if heater_value is None else f"{heater_value:0.1f} Ohm")
        self.metric_flow.set_value("--" if flow_value is None else f"{flow_value:0.3f} L/min")
        if (
            low_range_differential_pressure_pa is not None
            and high_range_differential_pressure_pa is not None
            and math.isfinite(low_range_differential_pressure_pa)
            and math.isfinite(high_range_differential_pressure_pa)
        ):
            selected_source = infer_differential_pressure_selected_source(
                selected_differential_pressure_pa,
                low_range_differential_pressure_pa,
                high_range_differential_pressure_pa,
            )
            selected_text = f"SEL: {selected_source} / " if selected_source else ""
            self.metric_flow.set_detail(
                f"{selected_text}"
                f"SDP811: {high_range_differential_pressure_pa:+0.2f} Pa / "
                f"SDP810: {low_range_differential_pressure_pa:+0.2f} Pa"
            )
        else:
            self.metric_flow.set_detail("")
        self.metric_o2.set_value(self._format_o2_metric_value(zirconia_value))

    def _format_o2_metric_value(self, zirconia_value: float | None) -> str:
        if zirconia_value is None or not math.isfinite(zirconia_value):
            return "--"

        o2_percent = derive_o2_concentration_percent(
            zirconia_value,
            air_calibration_voltage_v=self.app_settings.o2.air_calibration_voltage_v,
            zero_reference_voltage_v=self.app_settings.o2.zero_reference_voltage_v,
            ambient_reference_percent=self.app_settings.o2.ambient_reference_percent,
            invert_polarity=self.app_settings.o2.invert_polarity,
        )
        if o2_percent is None:
            return "Calibrate"
        return f"{o2_percent:0.1f} %"

    def _log_o2_calibration_changes(
        self,
        previous_air_calibration_voltage_v: float | None,
        previous_calibrated_at_iso: str,
    ) -> None:
        current_air_calibration_voltage_v = self.app_settings.o2.air_calibration_voltage_v
        current_calibrated_at_iso = self.app_settings.o2.calibrated_at_iso
        if (
            previous_air_calibration_voltage_v == current_air_calibration_voltage_v
            and previous_calibrated_at_iso == current_calibrated_at_iso
        ):
            return

        if current_air_calibration_voltage_v is None:
            self._append_log("info", "O2 ambient-air calibration reset.")
            return

        timestamp_text = current_calibrated_at_iso or "timestamp unavailable"
        self._append_log(
            "info",
            f"O2 ambient-air calibration updated at {current_air_calibration_voltage_v:0.3f} V ({timestamp_text}).",
        )

    def _update_service_visibility_labels(self) -> None:
        self.zirconia_ip_value.setText(self._format_optional_voltage(self._latest_zirconia_ip_voltage_v))
        self.internal_voltage_value.setText(self._format_optional_voltage(self._latest_internal_voltage_v))

    @staticmethod
    def _format_optional_voltage(value: float | None) -> str:
        if value is None or not math.isfinite(value):
            return "--"
        return f"{value:0.3f} V"

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
        available_width = max(640, self.width() - 36)
        left_width = max(272, min(360, int(available_width * 0.26)))
        self.left_column.setFixedWidth(left_width)

    def _apply_plot_splitter_sizes(self) -> None:
        if hasattr(self, "plot_splitter"):
            self.plot_splitter.setSizes([350, 240])

    def _sync_left_column_content_width(self) -> None:
        if not hasattr(self, "left_column") or not hasattr(self, "left_column_content"):
            return
        viewport_width = self.left_column.viewport().width()
        if viewport_width > 0:
            self.left_column_content.setFixedWidth(viewport_width)

    def _configure_plot_widget(self, plot: pg.PlotWidget) -> None:
        plot.setBackground(None)
        plot.showGrid(x=True, y=True, alpha=0.22)
        plot.setClipToView(True)
        plot.setDownsampling(auto=True, mode="peak")
        plot.getPlotItem().getAxis("left").setTextPen(QColor(COLORS["muted"]))
        plot.getPlotItem().getAxis("bottom").setTextPen(QColor(COLORS["muted"]))
        plot.getPlotItem().getAxis("left").setPen(QColor(COLORS["muted"]))
        plot.getPlotItem().getAxis("bottom").setPen(QColor(COLORS["muted"]))

    def _apply_default_plot_ranges(self) -> None:
        if "sensor" in self.plot_widgets:
            sensor_plot = self.plot_widgets["sensor"]
            sensor_plot.enableAutoRange(axis="y", enable=False)
            sensor_plot.setYRange(*FLOW_DEFAULT_Y_RANGE_LPM, padding=0.0)
        if "sensor_o2" in self._secondary_y_views:
            sensor_o2_view = self._secondary_y_views["sensor_o2"]
            sensor_o2_view.enableAutoRange(axis="y", enable=False)
            sensor_o2_view.setYRange(*O2_DEFAULT_Y_RANGE_PERCENT, padding=0.0)

    def _update_sensor_secondary_geometry(self) -> None:
        plot = self.plot_widgets.get("sensor")
        if plot is None:
            return
        self.sensor_secondary_view.setGeometry(plot.getPlotItem().vb.sceneBoundingRect())
        self.sensor_secondary_view.linkedViewChanged(plot.getPlotItem().vb, self.sensor_secondary_view.XAxis)

    def _update_heater_secondary_geometry(self) -> None:
        plot = self.plot_widgets.get("heater")
        if plot is None:
            return
        self.heater_secondary_view.setGeometry(plot.getPlotItem().vb.sceneBoundingRect())
        self.heater_secondary_view.linkedViewChanged(plot.getPlotItem().vb, self.heater_secondary_view.XAxis)

    def _current_axis_mode(self) -> str:
        return self.axis_mode_combo.currentText()

    def _session_start_time(self) -> datetime:
        return self._session_started

    def _plot_key_from_label(self, label: str) -> str:
        return "heater" if label == "Zirconia / Heater" else "sensor"

    def _plot_label_for_key(self, plot_key: str) -> str:
        return "Zirconia / Heater" if self._primary_plot_key(plot_key) == "heater" else "Flow / O2"

    @staticmethod
    def _primary_plot_key(plot_key: str) -> str:
        if plot_key.startswith("heater"):
            return "heater"
        return "sensor"

    def _y_range_view_for_plot_key(self, plot_key: str) -> pg.ViewBox | None:
        if plot_key in self.plot_widgets:
            return self.plot_widgets[plot_key].getViewBox()
        return self._secondary_y_views.get(plot_key)

    def _is_expected_ble_identifier(self, identifier: str) -> bool:
        return any(identifier.startswith(prefix) for prefix in PREFERRED_BLE_NAME_PREFIXES)

    def _is_expected_wired_identifier(self, identifier: str) -> bool:
        haystack = identifier.lower()
        return any(token in haystack for token in PREFERRED_WIRED_PORT_TOKENS)

    def _is_expected_identifier_for_mode(self, mode: str, identifier: str) -> bool:
        if not identifier or identifier == "Disconnected":
            return False
        if mode == BLE_MODE:
            return self._is_expected_ble_identifier(identifier)
        return self._is_expected_wired_identifier(identifier)

    def _has_expected_ble_selection(self) -> bool:
        return self._is_expected_ble_identifier(self.ble_device_selector.currentText().strip())

    def _has_expected_wired_selection(self) -> bool:
        return self._is_expected_wired_identifier(self.port_selector.currentText().strip())

    def _has_expected_connected_device(self) -> bool:
        return self.connection_controller.is_connected() and self._is_expected_identifier_for_mode(
            self.mode,
            self.ui_state.connection.identifier,
        )

    def _build_o2_series(self, zirconia_values: list[float]) -> list[float] | None:
        if self.app_settings.o2.air_calibration_voltage_v is None:
            return None
        o2_values: list[float] = []
        for zirconia_value in zirconia_values:
            o2_percent = derive_o2_concentration_percent(
                zirconia_value,
                air_calibration_voltage_v=self.app_settings.o2.air_calibration_voltage_v,
                zero_reference_voltage_v=self.app_settings.o2.zero_reference_voltage_v,
                ambient_reference_percent=self.app_settings.o2.ambient_reference_percent,
                invert_polarity=self.app_settings.o2.invert_polarity,
            )
            o2_values.append(float("nan") if o2_percent is None else o2_percent)
        return o2_values

    def _update_sensor_secondary_visibility(self) -> None:
        visible = self.app_settings.o2.air_calibration_voltage_v is not None
        plot = self.plot_widgets.get("sensor")
        if plot is None:
            return
        if visible:
            plot.getPlotItem().showAxis("right")
        else:
            plot.getPlotItem().hideAxis("right")
        self._set_legend_entry_visible(self.sensor_secondary_legend_item, visible)

    @staticmethod
    def _set_legend_entry_visible(entry: object, visible: bool) -> None:
        if not isinstance(entry, tuple) or len(entry) != 2:
            return
        sample, label = entry
        for item in (sample, label):
            if hasattr(item, "setVisible"):
                item.setVisible(visible)
