from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from bleak import BleakClient, BleakScanner

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gui_prototype" / "src"))

from ble_protocol import (  # noqa: E402
    decode_ble_capabilities_packet,
    decode_ble_event_packet,
    decode_ble_status_snapshot,
    decode_ble_telemetry_packet,
)
from protocol_constants import (  # noqa: E402
    BLE_OPCODE_GET_STATUS,
    BLE_OPCODE_PING,
    BLE_OPCODE_SET_PUMP_OFF,
    BLE_OPCODE_SET_PUMP_ON,
)


CONTROL_CHARACTERISTIC_UUID = "00002A19-0000-1000-8000-00805F9B34FB"
TELEMETRY_CHARACTERISTIC_UUID = "00002A58-0000-1000-8000-00805F9B34FB"
STATUS_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10001"
CAPABILITIES_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10002"
EVENT_CHARACTERISTIC_UUID = "8B1F1001-5C4B-47C1-A742-9D6617B10003"


@dataclass
class TelemetryObservation:
    packet: dict[str, object]
    received_at_monotonic: float


@dataclass
class BleCycleResult:
    capabilities: dict[str, object] | None = None
    telemetry: list[TelemetryObservation] = field(default_factory=list)
    status_packets: list[dict[str, object]] = field(default_factory=list)
    event_packets: list[dict[str, object]] = field(default_factory=list)
    status_notify_available: bool = False
    event_notify_available: bool = False
    capabilities_read_available: bool = False

    def telemetry_sequences(self) -> list[int]:
        return [int(item.packet["sequence"]) for item in self.telemetry]

    def telemetry_gaps(self) -> int:
        sequences = self.telemetry_sequences()
        if len(sequences) < 2:
            return 0
        gaps = 0
        for current, nxt in zip(sequences, sequences[1:]):
            if nxt > current + 1:
                gaps += nxt - current - 1
        return gaps

    def inter_arrival_ms(self) -> list[float]:
        if len(self.telemetry) < 2:
            return []
        samples: list[float] = []
        for previous, current in zip(self.telemetry, self.telemetry[1:]):
            samples.append((current.received_at_monotonic - previous.received_at_monotonic) * 1000.0)
        return samples


class BleCycleCollector:
    def __init__(self) -> None:
        self.result = BleCycleResult()

    def on_telemetry(self, _: str, data: bytearray) -> None:
        self.result.telemetry.append(
            TelemetryObservation(
                packet=decode_ble_telemetry_packet(bytes(data)),
                received_at_monotonic=time.monotonic(),
            )
        )

    def on_status(self, _: str, data: bytearray) -> None:
        self.result.status_packets.append(decode_ble_status_snapshot(bytes(data)))

    def on_event(self, _: str, data: bytearray) -> None:
        self.result.event_packets.append(decode_ble_event_packet(bytes(data)))

    async def wait_for_telemetry(self, minimum_count: int, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if len(self.result.telemetry) >= minimum_count:
                return
            await asyncio.sleep(0.05)
        raise AssertionError(
            f"Expected at least {minimum_count} telemetry packets, got {len(self.result.telemetry)}"
        )


async def discover_target(name: str, address: str | None, timeout_s: float) -> str:
    if address:
        return address

    devices = await BleakScanner.discover(timeout=timeout_s)
    matched_identifier: str | None = None
    for device in devices:
        print(f"scan {device.name} {device.address}")
        if device.name == name and matched_identifier is None:
            matched_identifier = str(getattr(device, "address", "") or name)

    if matched_identifier is None:
        raise RuntimeError(f"BLE device not found: {name}")
    return matched_identifier


async def start_notify_if_available(client: BleakClient, uuid: str, callback, label: str) -> bool:
    try:
        await client.start_notify(uuid, callback)
        return True
    except Exception as exc:
        print(f"{label}_notify_unavailable: {exc}")
        return False


async def read_status_directly_if_needed(client: BleakClient, collector: BleCycleCollector) -> None:
    status_raw = await client.read_gatt_char(STATUS_CHARACTERISTIC_UUID)
    collector.result.status_packets.append(decode_ble_status_snapshot(bytes(status_raw)))
    print("status_read_direct")


async def run_cycle(
    *,
    target_identifier: str,
    telemetry_count: int,
    telemetry_timeout_s: float,
    cycle_index: int,
) -> BleCycleResult:
    collector = BleCycleCollector()

    async with BleakClient(target_identifier) as client:
        print(f"cycle_{cycle_index}_connected", client.is_connected)
        await client.start_notify(TELEMETRY_CHARACTERISTIC_UUID, collector.on_telemetry)

        collector.result.status_notify_available = await start_notify_if_available(
            client,
            STATUS_CHARACTERISTIC_UUID,
            collector.on_status,
            "status",
        )
        collector.result.event_notify_available = await start_notify_if_available(
            client,
            EVENT_CHARACTERISTIC_UUID,
            collector.on_event,
            "event",
        )

        try:
            capabilities_raw = await client.read_gatt_char(CAPABILITIES_CHARACTERISTIC_UUID)
            collector.result.capabilities = decode_ble_capabilities_packet(bytes(capabilities_raw))
            collector.result.capabilities_read_available = True
            print(f"cycle_{cycle_index}_capabilities", collector.result.capabilities)
        except Exception as exc:
            print(f"cycle_{cycle_index}_capabilities_degraded: {exc}")

        if collector.result.status_notify_available:
            await client.write_gatt_char(CONTROL_CHARACTERISTIC_UUID, bytes([BLE_OPCODE_GET_STATUS]), response=False)
            print(f"cycle_{cycle_index}_status_request_sent")
        else:
            await read_status_directly_if_needed(client, collector)

        await collector.wait_for_telemetry(telemetry_count, telemetry_timeout_s)

        await client.write_gatt_char(CONTROL_CHARACTERISTIC_UUID, bytes([BLE_OPCODE_SET_PUMP_ON]), response=False)
        print(f"cycle_{cycle_index}_pump_on_sent")
        await asyncio.sleep(0.35)

        if collector.result.status_notify_available:
            await client.write_gatt_char(CONTROL_CHARACTERISTIC_UUID, bytes([BLE_OPCODE_GET_STATUS]), response=False)
        else:
            await read_status_directly_if_needed(client, collector)
        await asyncio.sleep(0.35)

        await client.write_gatt_char(CONTROL_CHARACTERISTIC_UUID, bytes([BLE_OPCODE_SET_PUMP_OFF]), response=False)
        print(f"cycle_{cycle_index}_pump_off_sent")
        await asyncio.sleep(0.35)

        await client.write_gatt_char(CONTROL_CHARACTERISTIC_UUID, bytes([BLE_OPCODE_PING]), response=False)
        print(f"cycle_{cycle_index}_ping_sent")
        await asyncio.sleep(0.35)

        try:
            await client.stop_notify(TELEMETRY_CHARACTERISTIC_UUID)
        except Exception:
            pass
        if collector.result.status_notify_available:
            try:
                await client.stop_notify(STATUS_CHARACTERISTIC_UUID)
            except Exception:
                pass
        if collector.result.event_notify_available:
            try:
                await client.stop_notify(EVENT_CHARACTERISTIC_UUID)
            except Exception:
                pass

    return collector.result


def assert_cycle_result(result: BleCycleResult, telemetry_count: int, cycle_index: int) -> None:
    if len(result.telemetry) < telemetry_count:
        raise AssertionError(
            f"cycle {cycle_index}: expected at least {telemetry_count} telemetry packets, got {len(result.telemetry)}"
        )

    sequences = result.telemetry_sequences()
    if sequences != sorted(sequences):
        raise AssertionError(f"cycle {cycle_index}: telemetry sequence is not monotonic: {sequences}")

    if not result.status_packets:
        raise AssertionError(f"cycle {cycle_index}: no status snapshot was received or read")


def print_cycle_summary(result: BleCycleResult, cycle_index: int) -> None:
    sequences = result.telemetry_sequences()
    gaps = result.telemetry_gaps()
    inter_arrivals = result.inter_arrival_ms()
    summary = {
        "telemetry_count": len(result.telemetry),
        "first_sequence": sequences[0] if sequences else None,
        "last_sequence": sequences[-1] if sequences else None,
        "gap_total": gaps,
        "status_count": len(result.status_packets),
        "event_count": len(result.event_packets),
        "status_notify_available": result.status_notify_available,
        "event_notify_available": result.event_notify_available,
        "capabilities_read_available": result.capabilities_read_available,
    }
    if inter_arrivals:
        summary["inter_arrival_avg_ms"] = round(sum(inter_arrivals) / len(inter_arrivals), 2)
        summary["inter_arrival_min_ms"] = round(min(inter_arrivals), 2)
        summary["inter_arrival_max_ms"] = round(max(inter_arrivals), 2)

    print(f"cycle_{cycle_index}_summary", summary)
    if result.status_packets:
        print(f"cycle_{cycle_index}_latest_status", result.status_packets[-1])
    if result.event_packets:
        print(f"cycle_{cycle_index}_latest_event", result.event_packets[-1])


async def run_smoke(
    *,
    name: str,
    address: str | None,
    scan_timeout_s: float,
    telemetry_count: int,
    telemetry_timeout_s: float,
    reconnect_cycles: int,
) -> None:
    target_identifier = await discover_target(name, address, scan_timeout_s)
    print("target_identifier", target_identifier)

    previous_last_sequence: int | None = None
    for cycle_index in range(1, reconnect_cycles + 1):
        result = await run_cycle(
            target_identifier=target_identifier,
            telemetry_count=telemetry_count,
            telemetry_timeout_s=telemetry_timeout_s,
            cycle_index=cycle_index,
        )
        assert_cycle_result(result, telemetry_count, cycle_index)
        print_cycle_summary(result, cycle_index)

        sequences = result.telemetry_sequences()
        if previous_last_sequence is not None and sequences and sequences[0] <= previous_last_sequence:
            raise AssertionError(
                f"cycle {cycle_index}: sequence did not advance across reconnect "
                f"({sequences[0]} <= {previous_last_sequence})"
            )
        if sequences:
            previous_last_sequence = sequences[-1]

        if cycle_index < reconnect_cycles:
            await asyncio.sleep(0.8)

    print("ble_smoke_ok")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="M5STAMP-MONITOR")
    parser.add_argument("--address")
    parser.add_argument("--scan-timeout", type=float, default=8.0)
    parser.add_argument("--telemetry-count", type=int, default=8)
    parser.add_argument("--telemetry-timeout", type=float, default=6.0)
    parser.add_argument("--reconnect-cycles", type=int, default=2)
    args = parser.parse_args()

    try:
        asyncio.run(
            run_smoke(
                name=args.name,
                address=args.address,
                scan_timeout_s=args.scan_timeout,
                telemetry_count=args.telemetry_count,
                telemetry_timeout_s=args.telemetry_timeout,
                reconnect_cycles=args.reconnect_cycles,
            )
        )
    except Exception as exc:
        print(f"ble_smoke_failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
