# Sampling Architecture v1

## 1. Purpose

This note captures the next firmware / protocol direction for reducing sampling jitter while preserving the current stable beta behavior.
It is intentionally a design gate before a larger RTOS refactor.

Primary goals:

- keep device-side sampling at a deterministic `10 ms` target
- measure timing on the device clock, not only host receive timing
- keep serial capable of publishing every sample
- let BLE carry multiple fixed-rate samples per notification
- avoid breaking current BLE / wired v1 clients while batch transport is still experimental

## 2. Current Understanding

The current system already records approximately `10 ms` mean sample cadence over wired transport, but host-side CSV intervals can look jittery because they include USB buffering, GUI event-loop scheduling, decode time, and disk flush timing.
Bundle A separated host inter-arrival from device-side `sample_tick_us`, which is the right diagnostic direction.
The follow-up cadence diagnostics slice extends the wired timing frame with acquisition duration, telemetry publish duration, and scheduler lateness so the next live test can identify whether the remaining error is sensor acquisition, transport blocking, or scheduling overhead.

The remaining architectural risk is that measurement, transport, BLE stack work, command handling, LED updates, and logs still share too much timing fate.
The next substantial firmware change should therefore separate sampling ownership before changing calibration-sensitive behavior.

## 3. Proposed Task Ownership

| Task | Suggested Core | Priority | Owns | Notes |
| :--- | :--- | :--- | :--- | :--- |
| `MeasurementTask` | Core 1 | High | ADS1115 / SDP reads, sample sequence, `sample_tick_us` | Runs from a periodic schedule and writes immutable sample frames |
| `TransportTask` | Core 0 | Medium | Serial publish, BLE notify, protocol framing | Reads sample frames from a ring buffer; never blocks measurement |
| `CommandTask` | Core 0 | Medium | Pump / heater command application, status requests | Converts host commands into small state updates |
| `UiLedTask` | Core 0 | Low | WS2812 / visual state | Consumes state snapshots; must not block measurement |
| `DiagnosticsTask` | Core 0 | Low | summary logs, timing counters | Publishes aggregated counters and warnings |

Core assignment is a starting point rather than a hard rule. The important invariant is ownership:
measurement writes sample frames, transport reads them, and shared mutable device state is updated through explicit queues or short critical sections.

## 4. Ring Buffer Contract

Use a fixed-size single-producer / multi-consumer-friendly ring buffer for `SampleFrame`.

Recommended `SampleFrame` fields:

| Field | Type | Notes |
| :--- | :--- | :--- |
| `sequence` | `uint32_t` | Monotonic sample id |
| `sample_tick_us` | `uint32_t` | Device monotonic timestamp at sampling point |
| `status_flags` | `uint32_t` | Snapshot at sample time |
| `zirconia_output_voltage_v` | `float` | Required |
| `heater_rtd_resistance_ohm` | `float` | Required |
| `differential_pressure_selected_pa` | `float` | Required once flow hardware is complete |
| `diagnostic_bits` | `uint32_t` | Snapshot at sample time |

The serial path can publish every `SampleFrame`.
The BLE path should consume the same frames but pack several frames into one notification.
If the BLE consumer falls behind, it should report dropped-frame counters rather than delaying `MeasurementTask`.

## 5. BLE Batch Direction

Keep the current 32-byte BLE telemetry packet as v1 compatibility.
Add a capability-gated batch telemetry extension for newer GUI builds.

Candidate compact batch shape:

```text
BleTelemetryBatchV1
  protocol_major: u8
  protocol_minor: u8
  batch_schema: u8
  sample_count: u8
  first_sequence: u32
  repeated sample_count times:
    sample_tick_delta_us: u16 or u32
    status_flags_delta_or_u16: u16
    zirconia_output_voltage_v: float32
    heater_rtd_resistance_ohm: float32
    differential_pressure_selected_pa: float32
```

For PoC budgeting, `8` bytes header plus `20` bytes per compact sample is conservative enough to check feasibility.
With an ATT MTU of `185`, ATT notification payload is typically `182` bytes, which can fit `8` compact samples.
At `100 Hz` sampling and `50 ms` BLE notify interval, `5` samples are required, so this budget has margin.

The GUI decoder should accept both:

- v1 single-sample packet for compatibility
- batch packet when capabilities advertise the batch feature bit

## 6. Jitter Diagnostics

Keep reporting these separately:

- device sample interval: `sample_tick_us[n] - sample_tick_us[n-1]`
- firmware acquisition duration: `acquisition_duration_us`
- firmware acquisition breakdown: `adc_total_duration_us`, `ads_ch0_duration_us`, `ads_ch1_duration_us`, `ads_ch2_duration_us`, `differential_pressure_total_duration_us`, `sdp_low_range_duration_us`, `sdp_high_range_duration_us`
- firmware telemetry publish duration: `telemetry_publish_duration_us`
- firmware scheduler lateness: `scheduler_lateness_us`
- transport sequence gap: `sequence[n] - sequence[n-1] - 1`
- host receive interval: `host_received_at[n] - host_received_at[n-1]`
- CSV write interval: optional, only for GUI performance diagnostics

Acceptance should be based primarily on device sample interval.
Host receive and CSV intervals are still useful, but they should not be mistaken for ADC sampling jitter.

## 7. Development Order

1. Add firmware-side `SampleFrame` and ring buffer without changing external payloads.
2. Keep current serial and BLE single-sample behavior fed from the ring buffer.
3. Validate wired timing with device-side ticks and no sequence gaps.
4. Add capability-gated BLE batch encoder / GUI decoder behind a feature bit.
5. Validate fake batch fixtures and recording schema compatibility.
6. Only after that, consider task affinity / priority tuning and ADS1115 continuous-conversion mode.

Short diagnostic slice before step 1:

- use `micros()` for the current cooperative scheduler deadline instead of `millis()`
- enlarge the USB CDC TX ring and avoid blocking on full TX capacity
- extend wired timing diagnostics while keeping the legacy `sample_tick_us` decoder path valid
- use the resulting timing breakdown to choose the next implementation target

Acquisition scheduling slice:

- publish `10 ms` sample frames from latest cached measurements
- keep zirconia output voltage (`ADS1115 ch2`) as the highest-priority per-sample ADC read
- keep `SDP810` / `SDP811` in Continuous Mode; cache scale factor from startup full sample and use pressure-word runtime reads
- track `SDP810` / `SDP811` availability independently so an absent or failed sensor does not block the 10 ms sample loop
- advertise and publish raw differential-pressure field bits independently; a system with only `SDP811` available may publish `differential_pressure_high_range_pa` while omitting `differential_pressure_low_range_pa`
- after the faulty `SDP810` was replaced, restore all ADS1115 channels (`ch0/ch1/ch2`) to every `10 ms` sample because the full ADC set fits comfortably within the period
- treat raw differential pressure channels as diagnostic values that may be one scheduling phase stale

Current result on `codex/fw-acquisition-scheduler`:

- current hardware reports `SDP frontend initialized: low=1 high=1` after replacing the faulty `SDP810`
- wired timing probe after restoring full ADS reads and adding deadline-aware cooperative waiting: sequence gap `0`, device sample jitter `max_abs=5 us`, scheduler lateness `max=0.006 ms`
- acquisition remains stable with all ADS channels and both SDP channels: acquisition `mean=5.464 ms`, ADC total `mean=5.052 ms`, differential-pressure read `mean=0.392 ms`
- the wired cooperative scheduler now meets the sub-100 us device-side jitter target in this live test; remaining architecture work should focus on keeping this behavior under BLE/batch and heavier GUI interaction scenarios

## 8. Local PoC

Use:

```bash
python3.12 tools/sampling_batch_budget.py --mtu-bytes 185 --notify-interval-ms 50 --sample-period-ms 10
```

Expected current PoC result:

- `Samples required per notify: 5`
- `Samples fit per notify: 8`
- `Verdict: fit`

## 9. User Test Required

- firmware upload after the ring buffer slice
- wired timing probe with device-side tick summary
- BLE batch continuity probe on macOS
- Windows packaged GUI batch decode / recording check
