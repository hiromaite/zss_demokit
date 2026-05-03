from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox, QFrame, QLabel, QVBoxLayout


def dialog_header(title: str, subtitle: str) -> QFrame:
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


def style_dialog_buttons(button_box: QDialogButtonBox) -> None:
    ok_button = button_box.button(QDialogButtonBox.Ok)
    cancel_button = button_box.button(QDialogButtonBox.Cancel)
    if ok_button is not None:
        ok_button.setObjectName("PrimaryButton")
    if cancel_button is not None:
        cancel_button.setObjectName("SecondaryButton")


def format_optional(value: float | None, pattern: str) -> str:
    if value is None:
        return "--"
    return pattern.format(value)
