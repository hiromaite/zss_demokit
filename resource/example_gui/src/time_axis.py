from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):
    def __init__(self, orientation: str = "bottom") -> None:
        super().__init__(orientation=orientation)
        self.mode = "relative"
        self.latest_elapsed = 0.0
        self.session_start_epoch: Optional[float] = None

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def set_reference(self, latest_elapsed: float, session_start_epoch: Optional[float]) -> None:
        self.latest_elapsed = latest_elapsed
        self.session_start_epoch = session_start_epoch

    def tickStrings(self, values: Sequence[float], scale: float, spacing: float) -> List[str]:
        if not values:
            return []

        labels: List[str] = []
        for value in values:
            if self.mode == "clock":
                if self.session_start_epoch is None:
                    labels.append("—")
                else:
                    try:
                        dt = datetime.fromtimestamp(
                            self.session_start_epoch + float(value),
                            tz=timezone.utc,
                        ).astimezone()
                        labels.append(dt.strftime("%H:%M:%S"))
                    except (OSError, OverflowError, ValueError):
                        labels.append("—")
                continue

            delta = float(value) - self.latest_elapsed
            sign = "-" if delta < 0 else ""
            total_seconds = max(0, int(round(abs(delta))))
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            labels.append(f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}")
        return labels
