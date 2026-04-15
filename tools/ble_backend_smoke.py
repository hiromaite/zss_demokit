from __future__ import annotations

import asyncio
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QCoreApplication, QTimer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui_prototype" / "src"))

import mock_backend as backend_module  # noqa: E402
from mock_backend import MockBackend  # noqa: E402
from protocol_constants import (  # noqa: E402
    BLE_MODE,
    BLE_OPCODE_GET_STATUS,
    BLE_OPCODE_PING,
    BLE_OPCODE_SET_PUMP_OFF,
    BLE_OPCODE_SET_PUMP_ON,
    STATUS_FLAG_PUMP_ON,
    STATUS_FLAG_TRANSPORT_SESSION_ACTIVE,
)


CONTROL_CHARACTERISTIC_UUID = "00002A19-0000-1000-8000-00805F9B34FB"
TELEMETRY_CHARACTERISTIC_UUID = "00002A58-0000-1000-8000-00805F9B34FB"
STATUS_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10001"
CAPABILITIES_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10002"
EVENT_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10003"


@dataclass
class FakePeripheralState:
    sequence: int = 0
    pump_on: bool = False
    nominal_sample_period_ms: int = 80


_FAKE_PERIPHERALS: dict[str, FakePeripheralState] = {}


def _write_u16le(value: int) -> bytes:
    return struct.pack("<H", value)


def _write_u32le(value: int) -> bytes:
    return struct.pack("<I", value)


def _write_f32le(value: float) -> bytes:
    return struct.pack("<f", value)


def _status_flags(state: FakePeripheralState) -> int:
    flags = STATUS_FLAG_TRANSPORT_SESSION_ACTIVE
    if state.pump_on:
        flags |= STATUS_FLAG_PUMP_ON
    return flags


def build_capabilities_packet(state: FakePeripheralState) -> bytes:
    return b"".join(
        [
            bytes([1, 0, 1, 1, 1, 0, 1, 0]),
            _write_u16le(0x000F),
            _write_u16le(0x0007),
            _write_u16le(state.nominal_sample_period_ms),
            _write_u16le(1),
            _write_u16le(32),
            _write_u32le(0x0000000F),
        ]
    )


def build_status_packet(state: FakePeripheralState) -> bytes:
    return b"".join(
        [
            bytes([1, 0, 1, 0]),
            _write_u32le(state.sequence),
            _write_u32le(_status_flags(state)),
            _write_u16le(state.nominal_sample_period_ms),
            _write_u16le(0x0007),
            _write_f32le(0.64),
            _write_f32le(121.5),
            _write_f32le(1.18 if not state.pump_on else 1.24),
        ]
    )


def build_telemetry_packet(state: FakePeripheralState) -> bytes:
    return b"".join(
        [
            bytes([1, 0, 1, 0]),
            _write_u32le(state.sequence),
            _write_u32le(_status_flags(state)),
            _write_f32le(0.64 + (state.sequence % 5) * 0.001),
            _write_f32le(121.5 + (state.sequence % 3) * 0.1),
            _write_f32le(1.18 if not state.pump_on else 1.24),
            _write_u16le(state.nominal_sample_period_ms),
            _write_u16le(0x0007),
            _write_u32le(0),
        ]
    )


def build_event_packet(event_code: int, severity: int, sequence: int, detail_u32: int) -> bytes:
    return b"".join(
        [
            bytes([1, 0, event_code, severity]),
            _write_u32le(sequence),
            _write_u32le(detail_u32),
        ]
    )


class FakeBleakClient:
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        self._state = _FAKE_PERIPHERALS.setdefault(identifier, FakePeripheralState())
        self._notify_callbacks: dict[str, Callable[[str, bytearray], None]] = {}
        self._telemetry_task: asyncio.Task[Any] | None = None
        self.is_connected = False

    async def __aenter__(self) -> "FakeBleakClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.disconnect()

    async def connect(self) -> None:
        self.is_connected = True

    async def disconnect(self) -> None:
        self.is_connected = False
        if self._telemetry_task is not None:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass
            self._telemetry_task = None

    async def start_notify(self, uuid: str, callback) -> None:
        self._notify_callbacks[uuid] = callback
        if uuid == TELEMETRY_CHARACTERISTIC_UUID and self._telemetry_task is None:
            self._telemetry_task = asyncio.create_task(self._run_telemetry())
        if uuid == EVENT_CHARACTERISTIC_UUID:
            callback(uuid, bytearray(build_event_packet(0x01, 0, self._state.sequence, 0)))

    async def stop_notify(self, uuid: str) -> None:
        self._notify_callbacks.pop(uuid, None)
        if uuid == TELEMETRY_CHARACTERISTIC_UUID and self._telemetry_task is not None:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass
            self._telemetry_task = None

    async def read_gatt_char(self, uuid: str) -> bytes:
        if uuid == CAPABILITIES_CHARACTERISTIC_UUID:
            return build_capabilities_packet(self._state)
        if uuid == STATUS_CHARACTERISTIC_UUID:
            return build_status_packet(self._state)
        raise RuntimeError(f"unsupported read uuid: {uuid}")

    async def write_gatt_char(self, uuid: str, data: bytes, response: bool = False) -> None:
        if uuid != CONTROL_CHARACTERISTIC_UUID:
            raise RuntimeError(f"unsupported write uuid: {uuid}")
        if not data:
            return
        opcode = data[0]
        if opcode == BLE_OPCODE_SET_PUMP_ON:
            self._state.pump_on = True
            await self._emit_status()
        elif opcode == BLE_OPCODE_SET_PUMP_OFF:
            self._state.pump_on = False
            await self._emit_status()
        elif opcode == BLE_OPCODE_GET_STATUS:
            await self._emit_status()
        elif opcode == BLE_OPCODE_PING:
            await self._emit_event(0x01, 0, 0)

    async def _run_telemetry(self) -> None:
        while self.is_connected:
            self._state.sequence += 1
            callback = self._notify_callbacks.get(TELEMETRY_CHARACTERISTIC_UUID)
            if callback is not None:
                callback(TELEMETRY_CHARACTERISTIC_UUID, bytearray(build_telemetry_packet(self._state)))
            await asyncio.sleep(self._state.nominal_sample_period_ms / 1000.0)

    async def _emit_status(self) -> None:
        callback = self._notify_callbacks.get(STATUS_CHARACTERISTIC_UUID)
        if callback is not None:
            callback(STATUS_CHARACTERISTIC_UUID, bytearray(build_status_packet(self._state)))

    async def _emit_event(self, event_code: int, severity: int, detail: int) -> None:
        callback = self._notify_callbacks.get(EVENT_CHARACTERISTIC_UUID)
        if callback is not None:
            callback(EVENT_CHARACTERISTIC_UUID, bytearray(build_event_packet(event_code, severity, self._state.sequence, detail)))


def main() -> int:
    original_bleak_client = backend_module.BleakClient
    original_bleak_scanner = backend_module.BleakScanner
    backend_module.BleakClient = FakeBleakClient
    backend_module.BleakScanner = object

    try:
        app = QCoreApplication([])
        backend = MockBackend(BLE_MODE)
        backend._ble_discovered_devices = {"M5STAMP-MONITOR": "FAKE-UUID-001"}

        connection_events: list[tuple[bool, str]] = []
        capabilities_events: list[dict[str, object]] = []
        status_events: list[dict[str, object]] = []
        telemetry_sequences: list[int] = []
        logs: list[tuple[str, str]] = []

        backend.connection_changed.connect(lambda connected, identifier: connection_events.append((connected, identifier)))
        backend.capabilities_changed.connect(lambda payload: capabilities_events.append(payload))
        backend.status_changed.connect(lambda payload: status_events.append(payload))
        backend.telemetry_generated.connect(lambda point: telemetry_sequences.append(int(point.sequence)))
        backend.log_generated.connect(lambda severity, message: logs.append((severity, message)))

        QTimer.singleShot(0, lambda: backend.connect_device("M5STAMP-MONITOR"))
        QTimer.singleShot(500, lambda: backend.set_pump_state(True))
        QTimer.singleShot(1700, backend.disconnect_device)
        QTimer.singleShot(2500, lambda: backend.connect_device("M5STAMP-MONITOR"))
        QTimer.singleShot(3000, lambda: backend.set_pump_state(False))
        QTimer.singleShot(3400, backend.ping)
        QTimer.singleShot(4700, backend.disconnect_device)
        QTimer.singleShot(5200, app.quit)
        app.exec()

        if len([event for event in connection_events if event[0]]) < 2:
            raise AssertionError(f"expected 2 BLE connect events, got {connection_events}")
        if len([event for event in connection_events if not event[0]]) < 2:
            raise AssertionError(f"expected 2 BLE disconnect events, got {connection_events}")
        if len(capabilities_events) < 2:
            raise AssertionError(f"expected 2 capabilities events, got {len(capabilities_events)}")
        if len(status_events) < 2:
            raise AssertionError(f"expected status updates across reconnects, got {len(status_events)}")
        if len(telemetry_sequences) < 10:
            raise AssertionError(f"expected telemetry across reconnects, got {telemetry_sequences}")
        if telemetry_sequences != sorted(telemetry_sequences):
            raise AssertionError(f"telemetry sequence is not monotonic: {telemetry_sequences}")
        if not any(str(payload.get("pump_state")) == "ON" for payload in status_events):
            raise AssertionError(f"expected at least one pump ON status update, got {status_events}")
        if not any(str(payload.get("pump_state")) == "OFF" for payload in status_events):
            raise AssertionError(f"expected at least one pump OFF status update, got {status_events}")
        if not any("BLE event" in message for _, message in logs):
            raise AssertionError(f"expected BLE event log entries, got {logs}")
        if any(severity == "error" for severity, _ in logs):
            raise AssertionError(f"unexpected error logs: {logs}")

        print("connection_events", connection_events)
        print("capabilities_events", len(capabilities_events))
        print("status_events", len(status_events))
        print("telemetry_first_last", telemetry_sequences[0], telemetry_sequences[-1])
        print("event_logs", sum(1 for _, message in logs if "BLE event" in message))
        print("ble_backend_reconnect_smoke_ok")
        return 0
    finally:
        backend_module.BleakClient = original_bleak_client
        backend_module.BleakScanner = original_bleak_scanner


if __name__ == "__main__":
    raise SystemExit(main())
