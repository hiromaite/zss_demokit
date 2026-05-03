from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

import pyqtgraph as pg


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
