from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def panel(title: str, hint: str | None = None, object_name: str = "PanelCard") -> tuple[QFrame, QVBoxLayout]:
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


class PreferredHeightSplitter(QSplitter):
    def __init__(self, orientation: Qt.Orientation, preferred_height: int, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self._preferred_height = preferred_height

    def sizeHint(self):  # type: ignore[override]
        size = super().sizeHint()
        size.setHeight(self._preferred_height)
        return size
