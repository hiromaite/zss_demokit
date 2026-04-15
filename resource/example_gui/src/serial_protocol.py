from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


CSV_PREFIX = "[csv] "
PROFILE_PREFIX = "[profile] "
STATUS_PREFIX = "[status] "
EVENT_PREFIX = "[event] "
CAPS_PREFIX = "[caps] "

EXPECTED_COLUMNS = [
    "frame_id",
    "batch_id",
    "frame_step",
    "host_ms",
    "field_index",
    "gas_index",
    "meas_index",
    "temp_c",
    "humidity_pct",
    "pressure_hpa",
    "gas_kohms",
    "status_hex",
    "gas_valid",
    "heat_stable",
]
OUTPUT_COLUMNS = [*EXPECTED_COLUMNS, "received_at_iso", "source_line"]


@dataclass
class ParsedSerialLine:
    line_type: str
    payload: Dict[str, str]
    raw_line: str


def parse_csv_payload(payload: str) -> Optional[Dict[str, str]]:
    values = [part.strip() for part in payload.split(",")]
    if len(values) != len(EXPECTED_COLUMNS):
        return None
    return dict(zip(EXPECTED_COLUMNS, values))


def parse_key_value_payload(payload: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if "=" not in payload:
        result["message"] = payload.strip()
        return result

    key, value = payload.split("=", 1)
    result[key.strip()] = value.strip()
    return result


def parse_serial_line(line: str) -> Optional[ParsedSerialLine]:
    line = line.strip()
    if not line:
        return None

    if line.startswith(CSV_PREFIX):
        payload = parse_csv_payload(line[len(CSV_PREFIX) :])
        if payload is None:
            return None
        return ParsedSerialLine("csv", payload, line)

    if line.startswith(PROFILE_PREFIX):
        return ParsedSerialLine("profile", parse_key_value_payload(line[len(PROFILE_PREFIX) :]), line)

    if line.startswith(STATUS_PREFIX):
        return ParsedSerialLine("status", parse_key_value_payload(line[len(STATUS_PREFIX) :]), line)

    if line.startswith(EVENT_PREFIX):
        return ParsedSerialLine("event", parse_key_value_payload(line[len(EVENT_PREFIX) :]), line)

    if line.startswith(CAPS_PREFIX):
        return ParsedSerialLine("caps", parse_key_value_payload(line[len(CAPS_PREFIX) :]), line)

    return ParsedSerialLine("other", {"message": line}, line)


def enrich_csv_row(payload: Dict[str, str], raw_line: str) -> Dict[str, str]:
    return {
        "received_at_iso": datetime.now().isoformat(timespec="milliseconds"),
        **payload,
        "source_line": raw_line,
    }
