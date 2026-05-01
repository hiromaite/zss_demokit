from __future__ import annotations

import argparse
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BatchBudget:
    mtu_bytes: int
    att_payload_bytes: int
    header_bytes: int
    sample_bytes: int
    notify_interval_ms: float
    sample_period_ms: float

    @property
    def samples_required(self) -> int:
        return max(1, math.ceil(self.notify_interval_ms / self.sample_period_ms))

    @property
    def samples_fit(self) -> int:
        return max(0, (self.att_payload_bytes - self.header_bytes) // self.sample_bytes)

    @property
    def payload_required_bytes(self) -> int:
        return self.header_bytes + self.samples_required * self.sample_bytes

    @property
    def margin_bytes(self) -> int:
        return self.att_payload_bytes - self.payload_required_bytes

    @property
    def fits(self) -> bool:
        return self.samples_required <= self.samples_fit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate whether a BLE telemetry batch can carry fixed-rate samples.",
    )
    parser.add_argument("--mtu-bytes", type=int, default=185, help="Negotiated BLE ATT MTU bytes")
    parser.add_argument(
        "--att-overhead-bytes",
        type=int,
        default=3,
        help="ATT notification overhead to subtract from MTU",
    )
    parser.add_argument("--header-bytes", type=int, default=8, help="Batch packet header bytes")
    parser.add_argument(
        "--sample-bytes",
        type=int,
        default=20,
        help="Compact per-sample bytes in the proposed batch payload",
    )
    parser.add_argument("--notify-interval-ms", type=float, default=50.0)
    parser.add_argument("--sample-period-ms", type=float, default=10.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    budget = BatchBudget(
        mtu_bytes=args.mtu_bytes,
        att_payload_bytes=args.mtu_bytes - args.att_overhead_bytes,
        header_bytes=args.header_bytes,
        sample_bytes=args.sample_bytes,
        notify_interval_ms=args.notify_interval_ms,
        sample_period_ms=args.sample_period_ms,
    )

    print(f"MTU bytes: {budget.mtu_bytes}")
    print(f"ATT payload bytes: {budget.att_payload_bytes}")
    print(f"Batch header bytes: {budget.header_bytes}")
    print(f"Per-sample bytes: {budget.sample_bytes}")
    print(f"Sample period ms: {budget.sample_period_ms:0.3f}")
    print(f"Notify interval ms: {budget.notify_interval_ms:0.3f}")
    print(f"Samples required per notify: {budget.samples_required}")
    print(f"Samples fit per notify: {budget.samples_fit}")
    print(f"Payload required bytes: {budget.payload_required_bytes}")
    print(f"Payload margin bytes: {budget.margin_bytes}")
    print(f"Verdict: {'fit' if budget.fits else 'does_not_fit'}")
    return 0 if budget.fits else 1


if __name__ == "__main__":
    raise SystemExit(main())
