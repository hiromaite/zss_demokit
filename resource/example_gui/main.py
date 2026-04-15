from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from app_metadata import APP_ID, APP_NAME, APP_VERSION
from gui_app import create_main_window
from qt_runtime import configure_qt_runtime


def _create_splash_pixmap() -> QPixmap:
    width = 520
    height = 220
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#f5efe4"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.fillRect(0, 0, width, height, QColor("#f2eadc"))

    painter.setPen(QColor("#9b2226"))
    painter.setBrush(QColor("#9b2226"))
    painter.drawRoundedRect(28, 34, 64, 64, 16, 16)

    painter.setPen(QColor("#fff7ed"))
    painter.setFont(QFont("Helvetica Neue", 20, QFont.Bold))
    painter.drawText(28, 34, 64, 64, Qt.AlignCenter, "B")

    painter.setPen(QColor("#3d2c1d"))
    painter.setFont(QFont("Helvetica Neue", 22, QFont.Bold))
    painter.drawText(116, 52, width - 140, 34, Qt.AlignLeft | Qt.AlignVCenter, APP_NAME)

    painter.setPen(QColor("#6b5b4d"))
    painter.setFont(QFont("Helvetica Neue", 13))
    painter.drawText(116, 92, width - 140, 28, Qt.AlignLeft | Qt.AlignVCenter, f"v{APP_VERSION}")

    painter.setPen(QColor("#7c6a58"))
    painter.setFont(QFont("Helvetica Neue", 15, QFont.Medium))
    painter.drawText(40, 148, width - 80, 24, Qt.AlignLeft | Qt.AlignVCenter, "起動中...")

    painter.setPen(QColor("#9a8b7d"))
    painter.setFont(QFont("Helvetica Neue", 11))
    painter.drawText(40, 178, width - 80, 20, Qt.AlignLeft | Qt.AlignVCenter, "Serial, plots, and session controls are being prepared.")

    painter.end()
    return pixmap


def main() -> int:
    configure_qt_runtime()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    splash = QSplashScreen(_create_splash_pixmap())
    splash.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    splash.show()
    app.processEvents()

    window = create_main_window()
    window.show()
    splash.finish(window)
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
