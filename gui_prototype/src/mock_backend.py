from __future__ import annotations

import asyncio
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from PySide6.QtCore import QObject, QTimer, Signal

from ble_protocol import (
    decode_ble_capabilities_packet,
    decode_ble_event_packet,
    decode_ble_status_snapshot,
    decode_ble_telemetry_packet,
)
from protocol_constants import (
    BLE_MODE,
    BLE_OPCODE_GET_CAPABILITIES,
    BLE_OPCODE_GET_STATUS,
    BLE_OPCODE_PING,
    BLE_OPCODE_SET_PUMP_OFF,
    BLE_OPCODE_SET_PUMP_ON,
    DERIVED_METRIC_POLICY_ID,
    DEVICE_TYPE_ZIRCONIA_SENSOR,
    FIRMWARE_VERSION_PLACEHOLDER,
    PROTOCOL_VERSION_TEXT,
    STATUS_FLAG_TELEMETRY_RATE_WARNING,
    SUPPORTED_COMMANDS,
    TELEMETRY_FIELDS,
    WIRED_COMMAND_ID_GET_CAPABILITIES,
    WIRED_COMMAND_ID_GET_STATUS,
    WIRED_COMMAND_ID_PING,
    WIRED_COMMAND_ID_SET_PUMP_STATE,
    WIRED_DEFAULT_BAUDRATE,
    WIRED_MODE,
    build_status_flags,
    format_status_flags,
    nominal_sample_period_ms_for_mode,
    result_code_to_text,
    transport_type_for_mode,
)
from wired_protocol import (
    WiredFrame,
    WiredFrameBuffer,
    build_command_frame,
    command_name_from_id,
    decode_capabilities,
    decode_command_ack,
    decode_event,
    decode_status_snapshot,
    decode_telemetry_sample,
)

try:
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover - optional in prototype bootstrap
    serial = None
    list_ports = None

try:
    from bleak import BleakClient, BleakScanner
except Exception:  # pragma: no cover - optional in prototype bootstrap
    BleakClient = None
    BleakScanner = None


BLE_CONTROL_CHARACTERISTIC_UUID = "00002A19-0000-1000-8000-00805F9B34FB"
BLE_TELEMETRY_CHARACTERISTIC_UUID = "00002A58-0000-1000-8000-00805F9B34FB"
BLE_STATUS_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10001"
BLE_CAPABILITIES_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10002"
BLE_EVENT_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10003"


@dataclass
class TelemetryPoint:
    sequence: int
    host_received_at: datetime
    nominal_sample_period_ms: int
    status_flags: int
    zirconia_output_voltage_v: float
    heater_rtd_resistance_ohm: float
    flow_sensor_voltage_v: float


class MockBackend(QObject):
    telemetry_generated = Signal(object)
    connection_changed = Signal(bool, str)
    status_changed = Signal(object)
    capabilities_changed = Signal(object)
    log_generated = Signal(str, str)
    ble_devices_discovered = Signal(list)
    ports_discovered = Signal(list)

    def __init__(self, mode: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self._connected = False
        self._connected_name = ""
        self._pump_on = False
        self._sequence = 0
        self._start_monotonic = time.monotonic()
        self._warning_latched = False
        self._last_firmware_version = FIRMWARE_VERSION_PLACEHOLDER
        self._last_protocol_version = PROTOCOL_VERSION_TEXT

        self._sample_timer = QTimer(self)
        self._sample_timer.timeout.connect(self._emit_sample)

        self._wired_poll_timer = QTimer(self)
        self._wired_poll_timer.setInterval(5)
        self._wired_poll_timer.timeout.connect(self._poll_wired_serial)
        self._wired_serial = None
        self._wired_frame_buffer = WiredFrameBuffer()
        self._next_request_id = 1
        self._pending_requests: dict[int, str] = {}
        self._wired_received_capabilities = False
        self._wired_received_status = False

        self._ble_discovered_devices: dict[str, str | None] = {}
        self._ble_loop: asyncio.AbstractEventLoop | None = None
        self._ble_thread: threading.Thread | None = None
        self._ble_client: Any | None = None
        self._ble_disconnect_requested = False
        self._ble_session_kind = "mock" if BleakClient is None or BleakScanner is None else "live"
        self._ble_status_notify_available = False
        self._ble_event_notify_available = False
        self._ble_capabilities_read_available = False

        self._set_timer_interval()

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if self._connected:
            self.disconnect_device()
        self._mode = mode
        self._set_timer_interval()
        self._reset_common_state()
        self.log_generated.emit("info", f"Switched prototype backend to {mode} mode.")

    def is_connected(self) -> bool:
        return self._connected

    def scan_ble_devices(self) -> None:
        if self._mode != BLE_MODE:
            self.ble_devices_discovered.emit([])
            return

        if BleakScanner is None:
            self._ble_discovered_devices = {
                "M5STAMP-MONITOR": None,
                "M5STAMP-MONITOR-LAB-B": None,
                "ZSS-PROTOTYPE-NODE": None,
            }
            self.ble_devices_discovered.emit(list(self._ble_discovered_devices.keys()))
            self.log_generated.emit("warn", "BLE live scan is unavailable; using mock device list.")
            return

        threading.Thread(target=self._scan_ble_worker, daemon=True).start()

    def refresh_ports(self) -> None:
        ports: List[str] = []
        if list_ports is not None:
            ports = [port.device for port in list_ports.comports()]
        if not ports:
            ports = ["Prototype-Port", "/dev/cu.usbmodem-prototype"]
        self.ports_discovered.emit(ports)
        if self._mode == WIRED_MODE:
            self.log_generated.emit("info", "Serial port list refreshed.")

    def connect_device(self, identifier: str) -> None:
        if self._mode == WIRED_MODE:
            self._connect_wired_device(identifier)
            return

        target = self._ble_discovered_devices.get(identifier)
        if BleakClient is not None and target is not None:
            self._connect_live_ble_device(identifier, target)
            return

        self._connect_mock_ble_device(identifier)

    def disconnect_device(self) -> None:
        if not self._connected and self._mode != BLE_MODE:
            return

        if self._mode == BLE_MODE and self._ble_session_kind == "live":
            self._disconnect_live_ble_device()
            return

        if not self._connected:
            return

        identifier = self._connected_name
        self._connected = False
        self._connected_name = ""
        self._sample_timer.stop()
        self._wired_poll_timer.stop()
        self._pending_requests.clear()
        self._wired_frame_buffer.clear()
        self._wired_received_capabilities = False
        self._wired_received_status = False

        if self._wired_serial is not None:
            try:
                self._wired_serial.close()
            except Exception:
                pass
            self._wired_serial = None

        self.connection_changed.emit(False, identifier)
        self.log_generated.emit("warn", f"Disconnected from {identifier}.")

    def set_pump_state(self, on: bool) -> None:
        if self._mode == WIRED_MODE:
            state = "ON" if on else "OFF"
            if self._send_wired_command(WIRED_COMMAND_ID_SET_PUMP_STATE, arg0_u32=1 if on else 0):
                self.log_generated.emit("info", f"Pump command requested: {state}.")
            return

        if self._ble_session_kind == "live" and self._connected:
            opcode = BLE_OPCODE_SET_PUMP_ON if on else BLE_OPCODE_SET_PUMP_OFF
            if self._send_ble_opcode(opcode):
                self.log_generated.emit("info", f"Pump command requested over BLE: {'ON' if on else 'OFF'}.")
                self._schedule_ble_status_refresh()
            return

        self._pump_on = on
        self.log_generated.emit("info", f"Pump set to {'ON' if on else 'OFF'}.")
        self.request_status()

    def request_status(self) -> None:
        if self._mode == WIRED_MODE:
            self._send_wired_command(WIRED_COMMAND_ID_GET_STATUS)
            return

        if self._ble_session_kind == "live" and self._connected:
            if not self._ble_status_notify_available:
                if self._ble_loop is None or self._ble_client is None:
                    self.log_generated.emit("warn", "BLE session is not ready for status read.")
                    return
                future = asyncio.run_coroutine_threadsafe(self._ble_read_status_snapshot(), self._ble_loop)
                future.add_done_callback(self._handle_async_future_result)
                return
            if self._send_ble_opcode(BLE_OPCODE_GET_STATUS):
                self.log_generated.emit("info", "BLE status request sent.")
            return

        status = self._status_payload()
        self.status_changed.emit(status)
        self.log_generated.emit("info", "Status snapshot refreshed.")

    def request_capabilities(self) -> None:
        if self._mode == WIRED_MODE:
            self._send_wired_command(WIRED_COMMAND_ID_GET_CAPABILITIES)
            return

        if self._ble_session_kind == "live" and self._connected:
            if not self._ble_capabilities_read_available:
                self._emit_ble_degraded_capabilities("extension capabilities read is unavailable")
                return
            if self._ble_loop is None or self._ble_client is None:
                self.log_generated.emit("warn", "BLE session is not ready for capabilities read.")
                return
            future = asyncio.run_coroutine_threadsafe(self._ble_read_capabilities(), self._ble_loop)
            future.add_done_callback(self._handle_async_future_result)
            return

        nominal = nominal_sample_period_ms_for_mode(self._mode)
        transport = transport_type_for_mode(self._mode)
        capabilities: Dict[str, object] = {
            "protocol_version": PROTOCOL_VERSION_TEXT,
            "device_type": DEVICE_TYPE_ZIRCONIA_SENSOR,
            "transport_type": transport,
            "firmware_version": FIRMWARE_VERSION_PLACEHOLDER,
            "nominal_sample_period_ms": nominal,
            "supported_commands": list(SUPPORTED_COMMANDS),
            "telemetry_fields": list(TELEMETRY_FIELDS),
            "derived_metric_policy": DERIVED_METRIC_POLICY_ID,
        }
        self.capabilities_changed.emit(capabilities)
        self.log_generated.emit("info", "Capabilities loaded.")

    def ping(self) -> None:
        if self._mode == WIRED_MODE:
            self._send_wired_command(WIRED_COMMAND_ID_PING)
            return

        if self._ble_session_kind == "live" and self._connected:
            if self._send_ble_opcode(BLE_OPCODE_PING):
                self.log_generated.emit("info", "BLE ping requested.")
            return

        self.log_generated.emit("info", "Ping successful in prototype backend.")

    def _reset_common_state(self) -> None:
        self._sequence = 0
        self._pump_on = False
        self._warning_latched = False
        self._start_monotonic = time.monotonic()
        self._last_firmware_version = FIRMWARE_VERSION_PLACEHOLDER
        self._last_protocol_version = PROTOCOL_VERSION_TEXT
        self._wired_frame_buffer.clear()
        self._pending_requests.clear()
        self._next_request_id = 1
        self._wired_received_capabilities = False
        self._wired_received_status = False
        self._ble_disconnect_requested = False
        self._ble_session_kind = "mock" if BleakClient is None or BleakScanner is None else "live"
        self._ble_status_notify_available = False
        self._ble_event_notify_available = False
        self._ble_capabilities_read_available = False

    def _set_timer_interval(self) -> None:
        self._sample_timer.setInterval(nominal_sample_period_ms_for_mode(self._mode))

    def _schedule_ble_status_refresh(self, delay_ms: int = 250) -> None:
        QTimer.singleShot(delay_ms, self._request_ble_status_if_connected)

    def _request_ble_status_if_connected(self) -> None:
        if self._mode == BLE_MODE and self._connected and self._ble_session_kind == "live":
            self.request_status()

    def _emit_ble_degraded_capabilities(self, reason: str) -> None:
        capabilities: Dict[str, object] = {
            "protocol_version": self._last_protocol_version,
            "device_type": DEVICE_TYPE_ZIRCONIA_SENSOR,
            "transport_type": transport_type_for_mode(BLE_MODE),
            "firmware_version": self._last_firmware_version,
            "nominal_sample_period_ms": nominal_sample_period_ms_for_mode(BLE_MODE),
            "supported_commands": ["get_status", "set_pump_state", "ping"],
            "telemetry_fields": list(TELEMETRY_FIELDS),
            "derived_metric_policy": DERIVED_METRIC_POLICY_ID,
            "degraded_mode": True,
        }
        self.capabilities_changed.emit(capabilities)
        self.log_generated.emit("warn", f"BLE capabilities degraded mode: {reason}")

    def _scan_ble_worker(self) -> None:
        try:
            devices = asyncio.run(BleakScanner.discover(timeout=6.0))
        except Exception as exc:
            self._ble_discovered_devices = {}
            self.ble_devices_discovered.emit([])
            self.log_generated.emit("error", f"BLE scan failed: {exc}")
            return

        labels: list[str] = []
        mapped: dict[str, str] = {}
        name_counts: dict[str, int] = {}
        for device in devices:
            name = getattr(device, "name", "") or getattr(device, "address", "Unknown")
            name_counts[name] = name_counts.get(name, 0) + 1

        for device in devices:
            name = getattr(device, "name", "") or getattr(device, "address", "Unknown")
            address = str(getattr(device, "address", "") or "").strip()
            target_identifier = address or name
            label = f"{name} [{address}]" if name_counts.get(name, 0) > 1 else name
            labels.append(label)
            mapped[label] = target_identifier

        self._ble_discovered_devices = mapped
        self.ble_devices_discovered.emit(labels)
        self.log_generated.emit("info", f"BLE scan completed with {len(labels)} device(s).")

    def _connect_mock_ble_device(self, identifier: str) -> None:
        self._ble_session_kind = "mock"
        self._connected = True
        self._connected_name = identifier
        self._start_monotonic = time.monotonic()
        self._sequence = 0
        self._sample_timer.start()
        self.connection_changed.emit(True, identifier)
        self.log_generated.emit("info", f"Connected to {identifier} in mock BLE mode.")
        self.request_capabilities()
        self.request_status()

    def _connect_live_ble_device(self, identifier: str, target_identifier: str) -> None:
        if self._ble_thread is not None and self._ble_thread.is_alive():
            self.log_generated.emit("warn", "BLE session is already active.")
            return

        self._ble_session_kind = "live"
        self._ble_disconnect_requested = False
        self._ble_thread = threading.Thread(
            target=self._run_ble_session_thread,
            args=(identifier, target_identifier),
            daemon=True,
        )
        self._ble_thread.start()

    def _disconnect_live_ble_device(self) -> None:
        self._ble_disconnect_requested = True
        if self._ble_loop is not None and self._ble_client is not None:
            future = asyncio.run_coroutine_threadsafe(self._ble_disconnect_async(), self._ble_loop)
            future.add_done_callback(self._handle_async_future_result)

    def _run_ble_session_thread(self, identifier: str, target_identifier: str) -> None:
        loop = asyncio.new_event_loop()
        self._ble_loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._ble_session(identifier, target_identifier))
        except Exception as exc:
            self.log_generated.emit("error", f"BLE session failed: {exc}")
            if self._connected:
                self._emit_ble_disconnected(identifier)
        finally:
            self._ble_client = None
            self._ble_loop = None
            self._ble_thread = None
            try:
                loop.close()
            except Exception:
                pass

    async def _ble_session(self, identifier: str, target_identifier: str) -> None:
        client = BleakClient(target_identifier)
        self._ble_client = client
        await client.connect()
        self._connected = True
        self._connected_name = identifier
        self._start_monotonic = time.monotonic()
        self.connection_changed.emit(True, identifier)
        self.log_generated.emit("info", f"Connected to {identifier} over BLE.")

        await client.start_notify(BLE_TELEMETRY_CHARACTERISTIC_UUID, self._on_ble_telemetry_notification)

        self._ble_status_notify_available = await self._start_ble_notify_if_available(
            BLE_STATUS_CHARACTERISTIC_UUID,
            self._on_ble_status_notification,
            "status",
        )
        self._ble_event_notify_available = await self._start_ble_notify_if_available(
            BLE_EVENT_CHARACTERISTIC_UUID,
            self._on_ble_event_notification,
            "event",
        )

        try:
            await self._ble_read_capabilities()
            self._ble_capabilities_read_available = True
        except Exception as exc:
            self._ble_capabilities_read_available = False
            self._emit_ble_degraded_capabilities(str(exc))

        await self._ble_write_opcode(BLE_OPCODE_GET_STATUS)

        while not self._ble_disconnect_requested and client.is_connected:
            await asyncio.sleep(0.1)

        await self._ble_disconnect_async()

    async def _ble_disconnect_async(self) -> None:
        client = self._ble_client
        if client is None:
            return

        try:
            for uuid in (
                BLE_EVENT_CHARACTERISTIC_UUID,
                BLE_STATUS_CHARACTERISTIC_UUID,
                BLE_TELEMETRY_CHARACTERISTIC_UUID,
            ):
                try:
                    await client.stop_notify(uuid)
                except Exception:
                    pass
            if client.is_connected:
                await client.disconnect()
        finally:
            identifier = self._connected_name or "BLE device"
            if self._connected:
                self._emit_ble_disconnected(identifier)

    async def _start_ble_notify_if_available(self, uuid: str, handler: Any, label: str) -> bool:
        if self._ble_client is None:
            return False
        try:
            await self._ble_client.start_notify(uuid, handler)
            return True
        except Exception as exc:
            self.log_generated.emit("warn", f"BLE {label} notify unavailable: {exc}")
            return False

    async def _ble_read_capabilities(self) -> None:
        if self._ble_client is None:
            return
        capabilities_raw = await self._ble_client.read_gatt_char(BLE_CAPABILITIES_CHARACTERISTIC_UUID)
        payload = decode_ble_capabilities_packet(bytes(capabilities_raw))
        payload["derived_metric_policy"] = DERIVED_METRIC_POLICY_ID
        payload["degraded_mode"] = False
        self._last_firmware_version = str(payload["firmware_version"])
        self._last_protocol_version = str(payload["protocol_version"])
        self.capabilities_changed.emit(payload)
        self.log_generated.emit("info", f"Capabilities loaded from {self._connected_name}.")

    async def _ble_read_status_snapshot(self) -> None:
        if self._ble_client is None:
            return
        status_raw = await self._ble_client.read_gatt_char(BLE_STATUS_CHARACTERISTIC_UUID)
        self._on_ble_status_notification(None, bytearray(status_raw))
        self.log_generated.emit("info", "BLE status snapshot read directly.")

    async def _ble_write_opcode(self, opcode: int) -> None:
        if self._ble_client is None:
            return
        await self._ble_client.write_gatt_char(
            BLE_CONTROL_CHARACTERISTIC_UUID,
            bytes([opcode]),
            response=False,
        )

    def _send_ble_opcode(self, opcode: int) -> bool:
        if self._ble_session_kind != "live" or not self._connected or self._ble_loop is None:
            self.log_generated.emit("warn", "Connect to a BLE device before sending commands.")
            return False
        future = asyncio.run_coroutine_threadsafe(self._ble_write_opcode(opcode), self._ble_loop)
        future.add_done_callback(self._handle_async_future_result)
        return True

    def _handle_async_future_result(self, future: Any) -> None:
        try:
            future.result()
        except Exception as exc:
            self.log_generated.emit("error", f"Background operation failed: {exc}")

    def _emit_ble_disconnected(self, identifier: str) -> None:
        self._connected = False
        self._connected_name = ""
        self._ble_disconnect_requested = False
        self._ble_status_notify_available = False
        self._ble_event_notify_available = False
        self._ble_capabilities_read_available = False
        self.connection_changed.emit(False, identifier)
        self.log_generated.emit("warn", f"Disconnected from {identifier}.")

    def _on_ble_telemetry_notification(self, _: Any, data: bytearray) -> None:
        try:
            payload = decode_ble_telemetry_packet(bytes(data))
        except Exception as exc:
            self.log_generated.emit("warn", f"BLE telemetry decode failed: {exc}")
            return

        self._pump_on = bool(payload["pump_on"])
        self._warning_latched = bool(int(payload["status_flags"]) & STATUS_FLAG_TELEMETRY_RATE_WARNING)
        self._last_protocol_version = str(payload["protocol_version"])
        point = TelemetryPoint(
            sequence=int(payload["sequence"]),
            host_received_at=datetime.now(),
            nominal_sample_period_ms=int(payload["nominal_sample_period_ms"]),
            status_flags=int(payload["status_flags"]),
            zirconia_output_voltage_v=float(payload["zirconia_output_voltage_v"]),
            heater_rtd_resistance_ohm=float(payload["heater_rtd_resistance_ohm"]),
            flow_sensor_voltage_v=float(payload["flow_sensor_voltage_v"]),
        )
        self.telemetry_generated.emit(point)

    def _on_ble_status_notification(self, _: Any, data: bytearray) -> None:
        try:
            payload = decode_ble_status_snapshot(bytes(data))
        except Exception as exc:
            self.log_generated.emit("warn", f"BLE status decode failed: {exc}")
            return

        self._pump_on = bool(payload["pump_on"])
        self._warning_latched = bool(int(payload["status_flags"]) & STATUS_FLAG_TELEMETRY_RATE_WARNING)
        self._last_protocol_version = str(payload["protocol_version"])
        status = {
            "pump_state": "ON" if payload["pump_on"] else "OFF",
            "transport_state": "Connected" if self._connected else "Disconnected",
            "status_flags_hex": str(payload["status_flags_hex"]),
            "nominal_sample_period_ms": int(payload["nominal_sample_period_ms"]),
            "firmware_version": self._last_firmware_version,
            "protocol_version": self._last_protocol_version,
        }
        self.status_changed.emit(status)

    def _on_ble_event_notification(self, _: Any, data: bytearray) -> None:
        try:
            payload = decode_ble_event_packet(bytes(data))
        except Exception as exc:
            self.log_generated.emit("warn", f"BLE event decode failed: {exc}")
            return

        self.log_generated.emit(
            str(payload["severity"]),
            f"BLE event {payload['event_name']} detail={payload['detail_u32']}",
        )

    def _connect_wired_device(self, identifier: str) -> None:
        if serial is None:
            self.log_generated.emit("error", "pyserial is not available for wired mode.")
            return

        try:
            self._wired_serial = serial.Serial(identifier, WIRED_DEFAULT_BAUDRATE, timeout=0, write_timeout=0.25)
            self._wired_serial.reset_input_buffer()
            self._wired_serial.reset_output_buffer()
        except Exception as exc:
            self._wired_serial = None
            self.log_generated.emit("error", f"Could not open {identifier}: {exc}")
            return

        self._connected = True
        self._connected_name = identifier
        self._sequence = 0
        self._pump_on = False
        self._warning_latched = False
        self._start_monotonic = time.monotonic()
        self._wired_frame_buffer.clear()
        self._pending_requests.clear()
        self._next_request_id = 1
        self._wired_received_capabilities = False
        self._wired_received_status = False
        self._wired_poll_timer.start()
        self.connection_changed.emit(True, identifier)
        self.log_generated.emit("info", f"Connected to {identifier} using wired serial transport.")
        QTimer.singleShot(300, self._bootstrap_wired_session)
        QTimer.singleShot(700, self._bootstrap_wired_session)

    def _bootstrap_wired_session(self) -> None:
        if not self._connected or self._mode != WIRED_MODE or self._wired_serial is None:
            return
        if not self._wired_received_capabilities:
            self.request_capabilities()
        if not self._wired_received_status:
            self.request_status()

    def _send_wired_command(self, command_id: int, arg0_u32: int = 0) -> bool:
        if self._mode != WIRED_MODE or not self._connected or self._wired_serial is None:
            self.log_generated.emit("warn", "Connect to a wired device before sending commands.")
            return False

        request_id = self._next_request_id
        self._next_request_id += 1
        self._pending_requests[request_id] = command_name_from_id(command_id)

        try:
            frame = build_command_frame(command_id, request_id=request_id, arg0_u32=arg0_u32)
            self._wired_serial.write(frame)
            self._wired_serial.flush()
        except Exception as exc:
            self._pending_requests.pop(request_id, None)
            self.log_generated.emit("error", f"Serial write failed: {exc}")
            self.disconnect_device()
            return False
        return True

    def _poll_wired_serial(self) -> None:
        if self._wired_serial is None:
            return

        try:
            waiting = int(self._wired_serial.in_waiting)
            if waiting <= 0:
                return
            chunk = self._wired_serial.read(waiting)
        except Exception as exc:
            self.log_generated.emit("error", f"Serial read failed: {exc}")
            self.disconnect_device()
            return

        for frame in self._wired_frame_buffer.push(chunk):
            self._handle_wired_frame(frame)

    def _handle_wired_frame(self, frame: WiredFrame) -> None:
        self._last_protocol_version = f"{frame.version_major}.{frame.version_minor}"

        if frame.message_type == 0x01:
            payload = decode_telemetry_sample(frame)
            self._pump_on = bool(payload["pump_on"])
            self._warning_latched = bool(payload["status_flags"] & STATUS_FLAG_TELEMETRY_RATE_WARNING)
            point = TelemetryPoint(
                sequence=int(payload["sequence"]),
                host_received_at=datetime.now(),
                nominal_sample_period_ms=int(payload["nominal_sample_period_ms"]),
                status_flags=int(payload["status_flags"]),
                zirconia_output_voltage_v=float(payload["zirconia_output_voltage_v"]),
                heater_rtd_resistance_ohm=float(payload["heater_rtd_resistance_ohm"]),
                flow_sensor_voltage_v=float(payload["flow_sensor_voltage_v"]),
            )
            self.telemetry_generated.emit(point)
            return

        if frame.message_type == 0x02:
            payload = decode_status_snapshot(frame)
            self._wired_received_status = True
            self._pump_on = bool(payload["pump_on"])
            self._warning_latched = bool(payload["status_flags"] & STATUS_FLAG_TELEMETRY_RATE_WARNING)
            status = {
                "pump_state": "ON" if payload["pump_on"] else "OFF",
                "transport_state": "Connected" if self._connected else "Disconnected",
                "status_flags_hex": format_status_flags(int(payload["status_flags"])),
                "nominal_sample_period_ms": int(payload["nominal_sample_period_ms"]),
                "firmware_version": self._last_firmware_version,
                "protocol_version": self._last_protocol_version,
            }
            self.status_changed.emit(status)
            return

        if frame.message_type == 0x03:
            payload = decode_capabilities(frame)
            self._wired_received_capabilities = True
            self._last_firmware_version = str(payload["firmware_version"])
            self._last_protocol_version = str(payload["protocol_version"])
            payload["derived_metric_policy"] = DERIVED_METRIC_POLICY_ID
            self.capabilities_changed.emit(payload)
            self.log_generated.emit("info", f"Capabilities loaded from {self._connected_name}.")
            return

        if frame.message_type == 0x11:
            ack = decode_command_ack(frame)
            command_name = self._pending_requests.pop(frame.request_id, command_name_from_id(int(ack["command_id"])))
            result_code = int(ack["result_code"])
            severity = "info" if result_code == 0 else "warn"
            detail_text = ""
            if int(ack["detail_u32"]) != 0:
                detail_text = f" detail={int(ack['detail_u32'])}"
            self.log_generated.emit(
                severity,
                f"ACK {command_name}: {result_code_to_text(result_code)}{detail_text}",
            )
            return

        if frame.message_type == 0x12:
            event = decode_event(frame)
            detail_text = f" detail={int(event['detail_u32'])}" if int(event["detail_u32"]) != 0 else ""
            self.log_generated.emit(
                str(event["severity"]),
                f"Wired event {event['event_name']}{detail_text}",
            )
            return

    def _status_payload(self) -> Dict[str, object]:
        status_flags = build_status_flags(
            pump_on=self._pump_on,
            transport_session_active=self._connected,
            telemetry_rate_warning=self._warning_latched,
        )
        nominal = nominal_sample_period_ms_for_mode(self._mode)
        return {
            "pump_state": "ON" if self._pump_on else "OFF",
            "transport_state": "Connected" if self._connected else "Disconnected",
            "status_flags_hex": format_status_flags(status_flags),
            "nominal_sample_period_ms": nominal,
            "firmware_version": FIRMWARE_VERSION_PLACEHOLDER,
            "protocol_version": PROTOCOL_VERSION_TEXT,
        }

    def _emit_sample(self) -> None:
        if not self._connected or self._mode != BLE_MODE or self._ble_session_kind != "mock":
            return

        elapsed = time.monotonic() - self._start_monotonic
        next_sequence = self._sequence + 1
        if next_sequence % 180 == 0:
            next_sequence += 1
            self._warning_latched = True
            self.log_generated.emit("warn", "Sequence gap simulated to visualize warning handling.")
        elif next_sequence % 75 == 0:
            self._warning_latched = True
        elif next_sequence % 76 == 0:
            self._warning_latched = False

        self._sequence = next_sequence
        nominal = nominal_sample_period_ms_for_mode(self._mode)

        zirconia = 0.64 + 0.03 * math.sin(elapsed * 1.5)
        heater = 121.5 + 2.6 * math.sin(elapsed * 0.55 + 0.8)
        flow_voltage = 1.18 + 0.18 * math.sin(elapsed * 0.95 + (0.7 if self._pump_on else 0.2))

        status_flags = build_status_flags(
            pump_on=self._pump_on,
            transport_session_active=True,
            telemetry_rate_warning=self._warning_latched,
        )

        point = TelemetryPoint(
            sequence=self._sequence,
            host_received_at=datetime.now(),
            nominal_sample_period_ms=nominal,
            status_flags=status_flags,
            zirconia_output_voltage_v=zirconia,
            heater_rtd_resistance_ohm=heater,
            flow_sensor_voltage_v=flow_voltage,
        )

        self.telemetry_generated.emit(point)
        if self._sequence == 1:
            self.request_capabilities()
            self.request_status()
