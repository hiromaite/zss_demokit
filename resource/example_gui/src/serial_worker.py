from __future__ import annotations

from threading import Event
from typing import Optional

import serial
from PySide6.QtCore import QThread, Signal


class SerialWorker(QThread):
    line_received = Signal(str)
    connection_changed = Signal(bool, str)
    error_occurred = Signal(str)

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.5):
        super().__init__()
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._stop_requested = Event()
        self._serial: Optional[serial.Serial] = None

    def run(self) -> None:
        try:
            self._serial = serial.Serial(self._port, self._baudrate, timeout=self._timeout, write_timeout=self._timeout)
            self.connection_changed.emit(True, self._port)
            while not self._stop_requested.is_set() and self._serial:
                line_bytes = self._serial.readline()
                if self._stop_requested.is_set():
                    break
                if not line_bytes:
                    continue
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    self.line_received.emit(line)
        except serial.SerialException as exc:
            self.error_occurred.emit(str(exc))
        finally:
            if self._serial:
                try:
                    self._serial.close()
                except serial.SerialException:
                    pass
            self.connection_changed.emit(False, self._port)

    def stop(self) -> None:
        self._stop_requested.set()
        if not self._serial or not self._serial.is_open:
            return
        try:
            self._serial.cancel_read()
        except (AttributeError, serial.SerialException):
            pass

    def send_command(self, command: str) -> None:
        if self._stop_requested.is_set() or not self._serial or not self._serial.is_open:
            return
        self._serial.write((command.strip() + "\n").encode("utf-8"))
        self._serial.flush()
