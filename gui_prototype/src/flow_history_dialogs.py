from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dialogs import FlowVerificationDetailsDialog, _dialog_header, _format_optional, _style_dialog_buttons
from flow_characterization import (
    FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS,
    FlowCharacterizationLatestSummary,
    FlowCharacterizationPersistence,
    compare_characterization_summaries,
)
from flow_verification import (
    FlowVerificationLatestSummary,
    FlowVerificationPersistence,
    compare_verification_summaries,
)


class FlowVerificationHistoryDialog(QDialog):
    def __init__(
        self,
        summaries: list[FlowVerificationLatestSummary],
        persistence: FlowVerificationPersistence,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._summaries = summaries
        self._persistence = persistence
        self.setWindowTitle("Flow Verification History")
        self.resize(980, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(
            _dialog_header(
                "Flow Verification History",
                "Review recent verification sessions and reopen a saved session summary when you need to compare PoC runs.",
            )
        )

        shell = QHBoxLayout()
        shell.setSpacing(14)
        layout.addLayout(shell, 1)

        self.history_list = QListWidget()
        shell.addWidget(self.history_list, 0)

        detail_card = QFrame()
        detail_card.setObjectName("SurfaceCard")
        detail_layout = QVBoxLayout(detail_card)
        self.history_summary_label = QLabel("Select a session to review its summary.")
        self.history_summary_label.setObjectName("SectionHint")
        self.history_summary_label.setWordWrap(True)
        detail_layout.addWidget(self.history_summary_label)

        self.history_note_label = QLabel("--")
        self.history_note_label.setObjectName("SectionHint")
        self.history_note_label.setWordWrap(True)
        detail_layout.addWidget(self.history_note_label)

        self.history_compare_label = QLabel("--")
        self.history_compare_label.setObjectName("SectionHint")
        self.history_compare_label.setWordWrap(True)
        detail_layout.addWidget(self.history_compare_label)

        self.open_selected_button = QPushButton("Open Selected Details")
        self.open_selected_button.setObjectName("PrimaryButton")
        self.open_selected_button.setEnabled(False)
        self.open_selected_button.clicked.connect(self._open_selected_details)
        self.export_history_button = QPushButton("Export Summary CSV")
        self.export_history_button.setObjectName("SecondaryButton")
        self.export_history_button.clicked.connect(self._export_history_summary)
        button_row = QHBoxLayout()
        button_row.addWidget(self.open_selected_button, 0)
        button_row.addWidget(self.export_history_button, 0)
        button_row.addStretch(1)
        detail_layout.addLayout(button_row)
        detail_layout.addStretch(1)
        shell.addWidget(detail_card, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        _style_dialog_buttons(button_box)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.history_list.currentRowChanged.connect(self._refresh_selected_summary)
        self._populate_history()

    def _populate_history(self) -> None:
        for summary in self._summaries:
            counts = []
            if summary.advisory_count:
                counts.append(f"adv {summary.advisory_count}")
            if summary.out_of_target_count:
                counts.append(f"oot {summary.out_of_target_count}")
            if summary.incomplete_count:
                counts.append(f"inc {summary.incomplete_count}")
            suffix = "" if not counts else f" [{', '.join(counts)}]"
            self.history_list.addItem(f"{summary.completed_at_iso} | {summary.result}{suffix}")
        if self.history_list.count() > 0:
            self.history_list.setCurrentRow(0)

    def _refresh_selected_summary(self, index: int) -> None:
        if index < 0 or index >= len(self._summaries):
            self.history_summary_label.setText("Select a session to review its summary.")
            self.history_note_label.setText("--")
            self.history_compare_label.setText("--")
            self.open_selected_button.setEnabled(False)
            return
        summary = self._summaries[index]
        self.history_summary_label.setText(
            f"Overall: {summary.result}\n"
            f"Exhalation: {summary.exhalation_result or '--'}\n"
            f"Inhalation: {summary.inhalation_result or '--'}\n"
            f"Mean abs error: {_format_optional(summary.mean_abs_error_percent, '{:0.2f} %')}\n"
            f"Max abs error: {_format_optional(summary.max_abs_error_percent, '{:0.2f} %')}\n"
            f"Source switches: {summary.total_source_switch_count}\n"
            f"Criterion: {summary.criterion_version or '--'}\n"
            f"Path: {summary.path or '--'}"
        )
        self.history_note_label.setText(
            "Note preview: " + (summary.note_preview or "--")
        )
        previous = self._summaries[index + 1] if index + 1 < len(self._summaries) else None
        self.history_compare_label.setText("\n".join(compare_verification_summaries(summary, previous)))
        self.open_selected_button.setEnabled(True)

    def _open_selected_details(self) -> None:
        index = self.history_list.currentRow()
        if index < 0 or index >= len(self._summaries):
            return
        summary = self._summaries[index]
        path = Path(summary.path) if summary.path else None
        session = self._persistence.load_session(path)
        if session is None:
            return
        dialog = FlowVerificationDetailsDialog(session, session_path=path, parent=self)
        dialog.exec()

    def _export_history_summary(self) -> None:
        if not self._summaries:
            return
        base_path = Path(self._summaries[0].path) if self._summaries[0].path else Path.cwd()
        export_path = (
            base_path.parent
            / f"flow_verification_history_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self._persistence.export_summary_csv(export_path, self._summaries)
        self.history_note_label.setText(f"Summary CSV exported: {export_path}")


class FlowCharacterizationHistoryDialog(QDialog):
    def __init__(
        self,
        summaries: list[FlowCharacterizationLatestSummary],
        persistence: FlowCharacterizationPersistence,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._summaries = summaries
        self._persistence = persistence
        self.setWindowTitle("Flow Characterization History")
        self.resize(980, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        layout.addWidget(
            _dialog_header(
                "Flow Characterization History",
                "Compare recent raw SDP characterization sessions before deciding selector thresholds or rough flow scaling.",
            )
        )

        shell = QHBoxLayout()
        shell.setSpacing(14)
        layout.addLayout(shell, 1)

        self.history_list = QListWidget()
        shell.addWidget(self.history_list, 0)

        detail_card = QFrame()
        detail_card.setObjectName("SurfaceCard")
        detail_layout = QVBoxLayout(detail_card)
        self.history_summary_label = QLabel("Select a characterization session to review its summary.")
        self.history_summary_label.setObjectName("SectionHint")
        self.history_summary_label.setWordWrap(True)
        detail_layout.addWidget(self.history_summary_label)

        self.history_compare_label = QLabel("--")
        self.history_compare_label.setObjectName("SectionHint")
        self.history_compare_label.setWordWrap(True)
        detail_layout.addWidget(self.history_compare_label)

        self.history_path_label = QLabel("--")
        self.history_path_label.setObjectName("SectionHint")
        self.history_path_label.setWordWrap(True)
        detail_layout.addWidget(self.history_path_label)

        self.export_history_button = QPushButton("Export Summary CSV")
        self.export_history_button.setObjectName("SecondaryButton")
        self.export_history_button.clicked.connect(self._export_history_summary)
        detail_layout.addWidget(self.export_history_button, 0)
        detail_layout.addStretch(1)
        shell.addWidget(detail_card, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        _style_dialog_buttons(button_box)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

        self.history_list.currentRowChanged.connect(self._refresh_selected_summary)
        self._populate_history()

    def _populate_history(self) -> None:
        for summary in self._summaries:
            rough = "--" if summary.rough_gain_multiplier is None else f"{summary.rough_gain_multiplier:0.2f}x"
            self.history_list.addItem(
                f"{summary.completed_at_iso} | {summary.status} | "
                f"captures {summary.completed_capture_steps}/{len(FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)} | rough {rough}"
            )
        if self.history_list.count() > 0:
            self.history_list.setCurrentRow(0)

    def _refresh_selected_summary(self, index: int) -> None:
        if index < 0 or index >= len(self._summaries):
            self.history_summary_label.setText("Select a characterization session to review its summary.")
            self.history_compare_label.setText("--")
            self.history_path_label.setText("--")
            return
        summary = self._summaries[index]
        self.history_summary_label.setText(
            f"Status: {summary.status}\n"
            f"Completed captures: {summary.completed_capture_steps}/{len(FLOW_CHARACTERIZATION_CAPTURE_STEP_IDS)}\n"
            f"Missing steps: {summary.missing_step_count}\n"
            f"Polarity: {summary.polarity_hint}\n"
            f"Low/high consistency: {summary.low_high_sign_consistency}\n"
            f"Selected peak abs: {_format_optional(summary.selected_peak_abs_pa, '{:0.3f} Pa')}\n"
            f"SDP810 peak abs: {_format_optional(summary.sdp810_peak_abs_pa, '{:0.3f} Pa')}\n"
            f"SDP811 peak abs: {_format_optional(summary.sdp811_peak_abs_pa, '{:0.3f} Pa')}\n"
            f"Rough gain: {_format_optional(summary.rough_gain_multiplier, '{:0.3f}x')} "
            f"({summary.rough_gain_confidence or '--'})\n"
            f"Note preview: {summary.note_preview or '--'}"
        )
        previous = self._summaries[index + 1] if index + 1 < len(self._summaries) else None
        self.history_compare_label.setText("\n".join(compare_characterization_summaries(summary, previous)))
        self.history_path_label.setText(
            f"JSON: {summary.path or '--'}\nCSV: {summary.csv_path or '--'}"
        )

    def _export_history_summary(self) -> None:
        if not self._summaries:
            return
        base_path = Path(self._summaries[0].path) if self._summaries[0].path else Path.cwd()
        export_path = (
            base_path.parent
            / f"flow_characterization_history_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self._persistence.export_summary_csv(export_path, self._summaries)
        self.history_path_label.setText(f"Summary CSV exported: {export_path}")
