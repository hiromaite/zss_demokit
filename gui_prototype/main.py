from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION
from launcher_window import LauncherWindow
from qt_runtime import configure_qt_runtime
from theme import app_stylesheet


def main() -> int:
    configure_qt_runtime()
    app = QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    app.setFont(QFont("Avenir Next", 11))
    app.setStyleSheet(app_stylesheet())

    window = LauncherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
