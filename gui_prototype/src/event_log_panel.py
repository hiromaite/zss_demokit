from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controllers import LogEntry, WarningController


class EventLogPanel(QWidget):
    def __init__(
        self,
        warning_controller: WarningController,
        recording_directory_provider: Callable[[], Path],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._warning_controller = warning_controller
        self._recording_directory_provider = recording_directory_provider
        self.latest_export_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.severity_filter_combo = QComboBox()
        self.severity_filter_combo.addItems(list(self._warning_controller.SEVERITY_FILTERS))
        self.severity_filter_combo.currentTextChanged.connect(self.refresh)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter log text")
        self.search_edit.textChanged.connect(self.refresh)
        self.copy_visible_button = QPushButton("Copy Visible")
        self.copy_visible_button.setObjectName("SecondaryButton")
        self.copy_visible_button.clicked.connect(self.copy_visible)
        self.export_visible_button = QPushButton("Export Visible")
        self.export_visible_button.setObjectName("SecondaryButton")
        self.export_visible_button.clicked.connect(self.export_visible)
        filter_row.addWidget(QLabel("Show"))
        filter_row.addWidget(self.severity_filter_combo, 0)
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.copy_visible_button, 0)
        filter_row.addWidget(self.export_visible_button, 0)
        layout.addLayout(filter_row)

        self.summary_label = QLabel("0 visible / 0 total")
        self.summary_label.setObjectName("SectionHint")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.log_pane = QPlainTextEdit()
        self.log_pane.setObjectName("LogPane")
        self.log_pane.setReadOnly(True)
        self.log_pane.setMinimumHeight(225)
        layout.addWidget(self.log_pane)
        self.refresh()

    def append_entry(self, entry: LogEntry) -> None:
        visible_entries = self.visible_entries()
        if entry in visible_entries:
            self.log_pane.appendPlainText(self._warning_controller.format_entry(entry))
            self._update_summary(visible_entries)
            return
        self.refresh()

    def visible_entries(self) -> list[LogEntry]:
        return self._warning_controller.filtered_entries(
            severity_filter=self.severity_filter_combo.currentText(),
            query=self.search_edit.text(),
        )

    def refresh(self) -> None:
        entries = self.visible_entries()
        self.log_pane.setPlainText(
            "\n".join(self._warning_controller.format_entry(entry) for entry in entries)
        )
        self._update_summary(entries)

    def copy_visible(self) -> bool:
        entries = self.visible_entries()
        if not entries:
            return False
        QApplication.clipboard().setText(
            "\n".join(self._warning_controller.format_entry(entry, include_date=True) for entry in entries)
        )
        return True

    def export_visible(self) -> Path | None:
        entries = self.visible_entries()
        if not entries:
            return None
        export_dir = self._recording_directory_provider() / "event_logs"
        export_path = export_dir / f"event_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.latest_export_path = self._warning_controller.export_csv(export_path, entries)
        return self.latest_export_path

    def _update_summary(self, visible_entries: list[LogEntry]) -> None:
        all_entries = self._warning_controller.entries()
        visible_counts = self._warning_controller.severity_counts(visible_entries)
        total_counts = self._warning_controller.severity_counts(all_entries)
        self.summary_label.setText(
            f"{len(visible_entries)} visible / {len(all_entries)} total | "
            f"visible warn/error: {visible_counts.get('warn', 0)}/{visible_counts.get('error', 0)} | "
            f"total warn/error: {total_counts.get('warn', 0)}/{total_counts.get('error', 0)}"
        )
        has_visible = bool(visible_entries)
        self.copy_visible_button.setEnabled(has_visible)
        self.export_visible_button.setEnabled(has_visible)
