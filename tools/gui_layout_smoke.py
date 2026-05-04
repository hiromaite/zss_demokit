#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GUI_ROOT = PROJECT_ROOT / "gui_prototype"
GUI_SRC = GUI_ROOT / "src"
for candidate in [str(GUI_ROOT), str(GUI_SRC)]:
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


LAYOUT_CASES = (
    (1480, 1100, "tall_desktop"),
    (1480, 940, "default"),
    (1366, 768, "windows_common"),
    (1280, 720, "compact_hd"),
    (1024, 700, "narrow_lab"),
)


def _run_parent() -> int:
    failures: list[str] = []
    for width, height, label in LAYOUT_CASES:
        case = f"{width}x{height}:{label}"
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--case", case],
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        if result.returncode != 0:
            failures.append(f"{case} exited with {result.returncode}")

    if failures:
        raise AssertionError("; ".join(failures))
    print("gui_layout_smoke_ok")
    return 0


def _parse_case(raw_case: str) -> tuple[int, int, str]:
    size, _, label = raw_case.partition(":")
    raw_width, raw_height = size.lower().split("x", 1)
    return int(raw_width), int(raw_height), label or size


def _metric_card_geometries(window) -> list[tuple[int, int, int, int]]:
    cards = [
        window.metric_flow,
        window.metric_o2,
        window.metric_zirconia,
        window.metric_heater,
    ]
    return [
        (
            card.mapTo(window.right_column_content, card.rect().topLeft()).x(),
            card.mapTo(window.right_column_content, card.rect().topLeft()).y(),
            card.width(),
            card.height(),
        )
        for card in cards
    ]


def _assert_metric_cards_single_row(window, label: str) -> None:
    geometries = _metric_card_geometries(window)
    y_positions = {geometry[1] for geometry in geometries}
    if len(y_positions) != 1:
        raise AssertionError(f"{label}: metric cards wrapped vertically: {geometries}")
    if window.metric_cards_container.height() > 96:
        raise AssertionError(
            f"{label}: metric cards container grew too tall: {window.metric_cards_container.height()}"
        )

    previous_right = -1
    for x, _y, width, height in sorted(geometries):
        if width < 120:
            raise AssertionError(f"{label}: metric card became too narrow: {geometries}")
        if height < 44:
            raise AssertionError(f"{label}: metric card became too short: {geometries}")
        if x < previous_right:
            raise AssertionError(f"{label}: metric cards overlap horizontally: {geometries}")
        previous_right = x + width


def _assert_compact_toolbar(window, label: str) -> None:
    if window.plot_toolbar.height() > 170:
        raise AssertionError(f"{label}: plot toolbar grew too tall: {window.plot_toolbar.height()}")


def _assert_scroll_area_widths(window, label: str) -> None:
    if window.left_column.horizontalScrollBar().maximum() != 0:
        raise AssertionError(f"{label}: left column developed horizontal scroll")
    if window.right_column.horizontalScrollBar().maximum() != 0:
        raise AssertionError(f"{label}: right column developed horizontal scroll")
    if window.left_column_content.width() != window.left_column.viewport().width():
        raise AssertionError(
            f"{label}: left content width {window.left_column_content.width()} "
            f"!= viewport {window.left_column.viewport().width()}"
        )
    if not (272 <= window.left_column.width() <= 360):
        raise AssertionError(f"{label}: left column width out of intended bounds: {window.left_column.width()}")
    if window.right_column.width() < 620:
        raise AssertionError(f"{label}: right column too narrow for plot area: {window.right_column.width()}")


def _assert_plot_splitter(window, label: str) -> None:
    min_height = 600
    initial_height = window.plot_splitter.height()
    if initial_height < min_height:
        raise AssertionError(
            f"{label}: plot splitter height {initial_height} is below minimum {min_height}"
        )
    if window.height() >= 1000 and initial_height <= min_height:
        raise AssertionError(
            f"{label}: plot splitter did not grow in a tall window: {initial_height}"
        )

    initial_sizes = window.plot_splitter.sizes()
    if len(initial_sizes) != 2 or min(initial_sizes) < 180:
        raise AssertionError(f"{label}: unexpected initial plot splitter sizes: {initial_sizes}")

    window.plot_splitter.setSizes([240, 350])
    window.repaint()
    adjusted_sizes = window.plot_splitter.sizes()
    if adjusted_sizes == initial_sizes or adjusted_sizes[0] >= initial_sizes[0]:
        raise AssertionError(
            f"{label}: plot splitter did not respond to programmatic resize: "
            f"{initial_sizes} -> {adjusted_sizes}"
        )
    if window.plot_splitter.height() != initial_height:
        raise AssertionError(
            f"{label}: plot splitter height changed after resize: {window.plot_splitter.height()}"
        )


def _run_case(raw_case: str) -> int:
    from PySide6.QtWidgets import QApplication

    from app_metadata import APP_ID, APP_NAME, APP_ORGANIZATION, APP_VERSION
    from gui_smoke_support import isolate_gui_settings
    from main_window import MainWindow
    from protocol_constants import BLE_MODE
    from qt_runtime import configure_qt_runtime

    width, height, label = _parse_case(raw_case)
    settings_dir = isolate_gui_settings(f"zss_layout_{label}_")
    configure_qt_runtime()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    window = MainWindow(BLE_MODE)
    try:
        window._plot_refresh_timer.stop()  # noqa: SLF001 - deterministic layout smoke
        window._telemetry_health_timer.stop()  # noqa: SLF001
        window.resize(width, height)
        window.show()
        for _ in range(3):
            app.processEvents()

        if window.width() != width or window.height() != height:
            raise AssertionError(
                f"{label}: actual window size {(window.width(), window.height())} "
                f"!= requested {(width, height)}"
            )
        _assert_scroll_area_widths(window, label)
        _assert_metric_cards_single_row(window, label)
        _assert_compact_toolbar(window, label)
        _assert_plot_splitter(window, label)
        print(
            f"PASS {label} {width}x{height}: "
            f"left={window.left_column.width()} right={window.right_column.width()} "
            f"cards={window.metric_cards_container.height()} toolbar={window.plot_toolbar.height()} "
            f"plot={window.plot_splitter.height()} splitter={window.plot_splitter.sizes()}"
        )
        sys.stdout.flush()
        window.hide()
        app.processEvents()
        settings_dir.cleanup()
        os._exit(0)
    except Exception as exc:
        print(f"FAIL {label} {width}x{height}: {exc}", file=sys.stderr)
        sys.stderr.flush()
        settings_dir.cleanup()
        os._exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Offscreen cross-resolution GUI layout smoke.")
    parser.add_argument("--case", default="", help="Internal single-case mode, e.g. 1280x720:compact.")
    args = parser.parse_args()
    if args.case:
        return _run_case(args.case)
    return _run_parent()


if __name__ == "__main__":
    raise SystemExit(main())
