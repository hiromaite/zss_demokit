#include <Arduino.h>

#include <math.h>
#include <type_traits>

#include "app/AppState.h"
#include "app/CapabilityBuilder.h"
#include "app/CommandProcessor.h"
#include "board/BoardConfig.h"
#include "measurement/AdcFrontend.h"
#include "measurement/DifferentialPressureFrontend.h"
#include "measurement/MeasurementCore.h"
#include "protocol/PayloadBuilders.h"
#include "services/Logger.h"
#include "services/InputButtonController.h"
#include "services/HeaterPowerController.h"
#include "services/PumpController.h"
#include "services/StatusLedController.h"
#include "transport/BleTransport.h"
#include "transport/SerialTransport.h"

namespace {

zss::measurement::AdcFrontend g_adc_frontend;
zss::measurement::DifferentialPressureFrontend g_differential_pressure_frontend;
zss::measurement::MeasurementCore g_measurement_core(
    g_adc_frontend,
    g_differential_pressure_frontend);
zss::services::PumpController g_pump_controller(zss::board::kPumpOutputPin);
zss::services::HeaterPowerController g_heater_power_controller(zss::board::kHeaterPowerEnablePin);
zss::services::InputButtonController g_pump_toggle_button(zss::board::kPumpToggleButtonPin);
zss::services::StatusLedController g_status_led(zss::board::kStatusLedDataPin);
zss::app::AppState g_app_state(zss::board::kDefaultNominalSamplePeriodMs);
zss::app::CommandProcessor g_command_processor(
    g_app_state,
    g_pump_controller,
    g_heater_power_controller);
zss::transport::BleTransport g_ble_transport;
zss::transport::SerialTransport g_serial_transport;

uint32_t g_next_sample_deadline_us = 0;
uint32_t g_last_summary_log_ms = 0;
bool g_measurement_core_ready = false;
bool g_ble_transport_ready = false;
bool g_serial_transport_ready = false;

constexpr uint8_t kEventSeverityInfo = 0;
constexpr uint8_t kEventSeverityWarn = 1;
constexpr uint8_t kEventSeverityError = 2;

uint32_t warningMaskFromStatusFlags(uint32_t status_flags) {
    return status_flags &
           (zss::protocol::kStatusFlagAdcFaultMask |
            zss::protocol::kStatusFlagSamplingOverrunMask |
            zss::protocol::kStatusFlagSensorFaultMask |
            zss::protocol::kStatusFlagTelemetryRateWarningMask |
            zss::protocol::kStatusFlagCommandErrorLatchedMask);
}

void updateDiagnosticBits() {
    g_app_state.setDiagnosticBit(
        zss::protocol::kDiagnosticBitMeasurementCoreReadyMask,
        g_measurement_core_ready);
    g_app_state.setDiagnosticBit(
        zss::protocol::kDiagnosticBitExternalAdcReadyMask,
        g_measurement_core.externalAdcAvailable());
    g_app_state.setDiagnosticBit(
        zss::protocol::kDiagnosticBitBleTransportReadyMask,
        g_ble_transport_ready);
    g_app_state.setDiagnosticBit(
        zss::protocol::kDiagnosticBitSerialTransportReadyMask,
        g_serial_transport_ready);
    g_app_state.setDiagnosticBit(
        zss::protocol::kDiagnosticBitBleSessionObservedMask,
        g_ble_transport.isConnected());
    g_app_state.setDiagnosticBit(
        zss::protocol::kDiagnosticBitSerialSessionObservedMask,
        g_serial_transport.isConnected());
}

void publishEventToTransports(const zss::protocol::EventPayloadV1& payload) {
    g_ble_transport.publishEvent(payload);
    g_serial_transport.publishEvent(payload);
}

void emitEvent(zss::protocol::EventCode event_code, uint8_t severity, uint32_t detail_u32) {
    publishEventToTransports(
        zss::protocol::buildEventPayload(
            event_code,
            severity,
            g_app_state.latestSequence(),
            detail_u32));
}

void emitStatusTransitionEvents(uint32_t previous_status_flags, uint32_t current_status_flags) {
    const uint32_t previous_warning_mask = warningMaskFromStatusFlags(previous_status_flags);
    const uint32_t current_warning_mask = warningMaskFromStatusFlags(current_status_flags);
    if (previous_warning_mask != current_warning_mask) {
        if (current_warning_mask != 0u) {
            emitEvent(
                zss::protocol::EventCode::WarningRaised,
                kEventSeverityWarn,
                current_warning_mask);
        } else {
            emitEvent(
                zss::protocol::EventCode::WarningCleared,
                kEventSeverityInfo,
                previous_warning_mask);
        }
    }

    const bool previous_adc_fault = (previous_status_flags & zss::protocol::kStatusFlagAdcFaultMask) != 0u;
    const bool current_adc_fault = (current_status_flags & zss::protocol::kStatusFlagAdcFaultMask) != 0u;
    if (!previous_adc_fault && current_adc_fault) {
        emitEvent(
            zss::protocol::EventCode::AdcFaultRaised,
            kEventSeverityError,
            current_status_flags);
    } else if (previous_adc_fault && !current_adc_fault) {
        emitEvent(
            zss::protocol::EventCode::AdcFaultCleared,
            kEventSeverityInfo,
            0u);
    }
}

void logCapabilitiesPreview() {
    const auto ble_capabilities = zss::app::CapabilityBuilder::build(
        zss::transport::TransportKind::Ble,
        zss::board::kBleNominalSamplePeriodMs,
        g_measurement_core.differentialPressureAvailable(),
        false,
        false,
        false,
        false);
    const auto serial_capabilities = zss::app::CapabilityBuilder::build(
        zss::transport::TransportKind::Serial,
        zss::board::kWiredNominalSamplePeriodMs,
        g_measurement_core.differentialPressureAvailable(),
        g_measurement_core.differentialPressureLowRangeAvailable(),
        g_measurement_core.differentialPressureHighRangeAvailable(),
        true,
        zss::board::kLegacyInputAdcPin >= 0);

    const auto ble_payload = zss::protocol::buildCapabilitiesPayload(ble_capabilities);
    const auto serial_payload = zss::protocol::buildCapabilitiesPayload(serial_capabilities);

    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "Boot",
        "BLE caps: period=%u ms max_payload=%u",
        ble_payload.nominal_sample_period_ms,
        ble_payload.max_payload_bytes);
    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "Boot",
        "Serial caps: period=%u ms max_payload=%u",
        serial_payload.nominal_sample_period_ms,
        serial_payload.max_payload_bytes);
}

void logDifferentialPressureFrontendStatus() {
    if (g_measurement_core.differentialPressureAvailable()) {
        zss::services::Logger::log(
            zss::services::LogLevel::Info,
            "Boot",
            "SDP frontend initialized: low=%u high=%u.",
            static_cast<unsigned>(g_measurement_core.differentialPressureLowRangeAvailable()),
            static_cast<unsigned>(g_measurement_core.differentialPressureHighRangeAvailable()));
        return;
    }

    zss::services::Logger::log(
        zss::services::LogLevel::Warn,
        "Boot",
        "Dual-SDP frontend unavailable: %s",
        g_measurement_core.differentialPressureLastError());
}

uint16_t selectNominalSamplePeriodMs() {
    if (g_serial_transport.isConnected()) {
        return zss::board::kWiredNominalSamplePeriodMs;
    }
    if (g_ble_transport.isConnected()) {
        return zss::board::kBleNominalSamplePeriodMs;
    }
    return zss::board::kDefaultNominalSamplePeriodMs;
}

uint32_t nominalSamplePeriodUs() {
    return static_cast<uint32_t>(g_app_state.nominalSamplePeriodMs()) * 1000u;
}

void updateSamplingCadenceForActiveTransport(uint32_t now_us) {
    const uint16_t target_period_ms = selectNominalSamplePeriodMs();
    if (target_period_ms == g_app_state.nominalSamplePeriodMs()) {
        return;
    }

    g_app_state.setNominalSamplePeriodMs(target_period_ms);
    g_next_sample_deadline_us = now_us + (static_cast<uint32_t>(target_period_ms) * 1000u);
    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "Timing",
        "Sampling cadence switched to %u ms",
        static_cast<unsigned>(target_period_ms));
}

void runSamplingStep(uint32_t now_us) {
    const uint32_t nominal_period_us = nominalSamplePeriodUs();
    if (nominal_period_us == 0u) {
        return;
    }

    if (g_next_sample_deadline_us == 0) {
        g_next_sample_deadline_us = now_us + nominal_period_us;
        return;
    }

    if (static_cast<int32_t>(now_us - g_next_sample_deadline_us) < 0) {
        return;
    }

    const uint32_t previous_status_flags = g_app_state.statusFlags();
    const uint32_t sample_started_us = micros();
    const uint32_t scheduler_lateness_us = sample_started_us - g_next_sample_deadline_us;
    const uint32_t missed_intervals = scheduler_lateness_us / nominal_period_us;
    const bool overrun =
        scheduler_lateness_us > (zss::board::kSamplingOverrunToleranceMs * 1000u) ||
        missed_intervals > 0u;

    g_app_state.setStatusFlag(zss::protocol::kStatusFlagSamplingOverrunMask, overrun);
    g_app_state.setStatusFlag(zss::protocol::kStatusFlagTelemetryRateWarningMask, overrun);
    if (overrun) {
        g_app_state.incrementSampleOverrunCount(missed_intervals + 1u);
    }

    g_next_sample_deadline_us += (missed_intervals + 1u) * nominal_period_us;

    const auto measurements = g_measurement_core.acquire();
    const uint32_t acquisition_duration_us = micros() - sample_started_us;
    const auto& differential_pressure = g_measurement_core.latestDifferentialPressureMeasurements();
    auto canonical_measurements = measurements;
    updateDiagnosticBits();
    g_app_state.setStatusFlag(zss::protocol::kStatusFlagAdcFaultMask, !g_measurement_core.isHealthy());
    const bool sensor_fault =
        !g_measurement_core.lastReadSucceeded() ||
        !isfinite(measurements.zirconia_ip_voltage_v) ||
        !isfinite(measurements.zirconia_output_voltage_v) ||
        !isfinite(measurements.heater_rtd_resistance_ohm);
    g_app_state.setStatusFlag(zss::protocol::kStatusFlagSensorFaultMask, sensor_fault);
    if (g_measurement_core.differentialPressureHealthy() &&
        isfinite(differential_pressure.selected_differential_pressure_pa)) {
        canonical_measurements.differential_pressure_selected_pa =
            differential_pressure.selected_differential_pressure_pa;
        g_app_state.setDifferentialPressureSelectedPa(
            differential_pressure.selected_differential_pressure_pa);
    } else {
        canonical_measurements.differential_pressure_selected_pa = NAN;
        g_app_state.clearDifferentialPressureSelectedPa();
    }
    const bool has_low_range_dp = g_measurement_core.differentialPressureHealthy() &&
        isfinite(differential_pressure.low_range_differential_pressure_pa);
    const bool has_high_range_dp = g_measurement_core.differentialPressureHealthy() &&
        isfinite(differential_pressure.high_range_differential_pressure_pa);
    if (has_low_range_dp || has_high_range_dp) {
        g_app_state.setDifferentialPressureRawPa(
            differential_pressure.low_range_differential_pressure_pa,
            has_low_range_dp,
            differential_pressure.high_range_differential_pressure_pa,
            has_high_range_dp);
    } else {
        g_app_state.clearDifferentialPressureRawPa();
    }
    const uint32_t sequence = g_app_state.nextSequence();
    g_app_state.updateMeasurements(sequence, canonical_measurements);

    emitStatusTransitionEvents(previous_status_flags, g_app_state.statusFlags());

    g_app_state.setDiagnosticBit(zss::protocol::kDiagnosticBitTelemetryPublishedMask, true);
    const auto telemetry_payload = zss::protocol::buildTelemetryPayload(g_app_state);
    const uint32_t telemetry_publish_started_us = micros();
    g_ble_transport.publishTelemetry(telemetry_payload);
    g_serial_transport.publishTelemetry(telemetry_payload);
    const uint32_t telemetry_publish_duration_us = micros() - telemetry_publish_started_us;
    g_serial_transport.publishTimingDiagnostic(
        sequence,
        sample_started_us,
        acquisition_duration_us,
        telemetry_publish_duration_us,
        scheduler_lateness_us,
        g_measurement_core.latestAcquisitionTiming());
}

void emitSummaryLog(uint32_t now_ms) {
    if (now_ms - g_last_summary_log_ms < zss::board::kSummaryLogIntervalMs) {
        return;
    }
    g_last_summary_log_ms = now_ms;

    const auto& measurements = g_app_state.latestMeasurements();
    const auto& differential_pressure =
        g_measurement_core.latestDifferentialPressureMeasurements();
    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "Sample",
        "seq=%lu Vip=%.3fV Vin=%.3fV Vout=%.3fV RTD=%.1fOhm DpMeas=%.2fPa DpSel=%.2fPa Dp125=%.2fPa Dp500=%.2fPa DpLow=%u flags=0x%08lX diag=0x%08lX overruns=%lu",
        static_cast<unsigned long>(g_app_state.latestSequence()),
        measurements.zirconia_ip_voltage_v,
        measurements.internal_voltage_v,
        measurements.zirconia_output_voltage_v,
        measurements.heater_rtd_resistance_ohm,
        measurements.differential_pressure_selected_pa,
        differential_pressure.selected_differential_pressure_pa,
        differential_pressure.low_range_differential_pressure_pa,
        differential_pressure.high_range_differential_pressure_pa,
        static_cast<unsigned>(differential_pressure.selected_from_low_range),
        static_cast<unsigned long>(g_app_state.statusFlags()),
        static_cast<unsigned long>(g_app_state.diagnosticBits()),
        static_cast<unsigned long>(g_app_state.sampleOverrunCount()));
}

void updateStatusLedContext() {
    zss::services::StatusLedContext context{};
    context.status_flags = g_app_state.statusFlags();
    context.ble_ready = g_ble_transport_ready;
    context.ble_connected = g_ble_transport.isConnected();
    context.recording_active = false;
    context.measurement_ready = g_app_state.latestSequence() > 0u;
    context.zirconia_ip_voltage_v = g_app_state.latestMeasurements().zirconia_ip_voltage_v;
    g_status_led.setContext(context);
}

}  // namespace

void setup() {
    zss::services::Logger::begin(zss::board::kSerialMonitorBaudRate);
    delay(50);

    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "Boot",
        "Starting ZSS firmware skeleton %s",
        zss::protocol::kFirmwareVersionString);

    g_pump_controller.begin();
    g_heater_power_controller.begin();
    g_status_led.begin();
    g_pump_toggle_button.begin(millis());

    g_measurement_core_ready = g_measurement_core.begin();
    if (!g_measurement_core_ready) {
        g_app_state.setStatusFlag(zss::protocol::kStatusFlagAdcFaultMask, true);
        zss::services::Logger::log(zss::services::LogLevel::Error, "Boot", "Measurement core initialization failed.");
    } else if (!g_measurement_core.isHealthy()) {
        g_app_state.setStatusFlag(zss::protocol::kStatusFlagAdcFaultMask, true);
        zss::services::Logger::log(
            zss::services::LogLevel::Warn,
            "Boot",
            "Measurement core started with ADC fault: %s",
            g_measurement_core.lastError());
    }

    g_ble_transport_ready = g_ble_transport.begin();
    g_serial_transport_ready = g_serial_transport.begin();
    g_app_state.setTransportSessionActive(false);
    updateDiagnosticBits();

    const auto ble_capabilities = zss::app::CapabilityBuilder::build(
        zss::transport::TransportKind::Ble,
        zss::board::kBleNominalSamplePeriodMs,
        g_measurement_core.differentialPressureAvailable(),
        false,
        false,
        false,
        false);
    g_ble_transport.publishCapabilities(
        zss::protocol::buildCapabilitiesPayload(ble_capabilities));
    g_ble_transport.publishStatusSnapshot(
        zss::protocol::buildStatusSnapshotPayload(g_app_state));

    zss::app::CommandRequest startup_request{};
    startup_request.command_id = zss::protocol::CommandId::SetPumpState;
    startup_request.arg0_u32 = 0u;
    startup_request.source_transport = zss::transport::TransportKind::Local;
    const auto startup_result = g_command_processor.handle(startup_request);
    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "Boot",
        "Startup command result=%u",
        static_cast<unsigned>(startup_result.result_code));

    logCapabilitiesPreview();
    logDifferentialPressureFrontendStatus();
    zss::services::Logger::log(
        zss::services::LogLevel::Info,
        "Boot",
        "Board config: pump=%d pwm=%luHz/%ubit on=%u%% off=%u%% heater_en=%d button=%d led=%d led_pwr_en=%d i2c=(%d,%d)",
        zss::board::kPumpOutputPin,
        static_cast<unsigned long>(zss::board::kPumpPwmFrequencyHz),
        static_cast<unsigned>(zss::board::kPumpPwmResolutionBits),
        static_cast<unsigned>(zss::board::kPumpPwmDutyOnPercent),
        static_cast<unsigned>(zss::board::kPumpPwmDutyOffPercent),
        zss::board::kHeaterPowerEnablePin,
        zss::board::kPumpToggleButtonPin,
        zss::board::kStatusLedDataPin,
        zss::board::kStatusLedPowerEnablePin,
        zss::board::kI2cSdaPin,
        zss::board::kI2cSclPin);
    g_app_state.setDiagnosticBit(zss::protocol::kDiagnosticBitBootCompleteMask, true);
    emitEvent(zss::protocol::EventCode::BootComplete, kEventSeverityInfo, g_app_state.diagnosticBits());
    updateStatusLedContext();
}

void loop() {
    g_ble_transport.update();
    g_serial_transport.update();
    g_app_state.setTransportSessionActive(g_serial_transport.isConnected() || g_ble_transport.isConnected());
    updateDiagnosticBits();
    g_pump_toggle_button.poll(millis());

    auto handleCommandForTransport =
        [](auto& transport, zss::transport::TransportKind transport_kind) {
            zss::app::CommandRequest pending_request{};
            uint32_t request_id = 0;
            while (transport.takePendingCommand(pending_request, request_id)) {
                const uint32_t previous_status_flags = g_app_state.statusFlags();
                const auto result = g_command_processor.handle(pending_request);

                if constexpr (std::is_same_v<std::decay_t<decltype(transport)>, zss::transport::SerialTransport>) {
                    const auto ack_payload = zss::protocol::buildCommandAckPayload(
                        pending_request.command_id,
                        result.result_code,
                        result.detail_u32);
                    transport.publishCommandAck(ack_payload, request_id);
                }

                if (result.result_code != zss::protocol::ResultCode::Ok) {
                    emitEvent(
                        zss::protocol::EventCode::CommandError,
                        kEventSeverityError,
                        static_cast<uint32_t>(pending_request.command_id));
                }
                emitStatusTransitionEvents(previous_status_flags, g_app_state.statusFlags());

                if (result.request_capabilities) {
                    const auto capabilities = zss::app::CapabilityBuilder::build(
                        transport_kind,
                        transport_kind == zss::transport::TransportKind::Ble
                            ? zss::board::kBleNominalSamplePeriodMs
                            : g_app_state.nominalSamplePeriodMs(),
                        g_measurement_core.differentialPressureAvailable(),
                        transport_kind == zss::transport::TransportKind::Serial &&
                            g_measurement_core.differentialPressureLowRangeAvailable(),
                        transport_kind == zss::transport::TransportKind::Serial &&
                            g_measurement_core.differentialPressureHighRangeAvailable(),
                        transport_kind == zss::transport::TransportKind::Serial,
                        transport_kind == zss::transport::TransportKind::Serial &&
                            zss::board::kLegacyInputAdcPin >= 0);
                    if constexpr (std::is_same_v<std::decay_t<decltype(transport)>, zss::transport::SerialTransport>) {
                        transport.publishCapabilities(
                            zss::protocol::buildCapabilitiesPayload(capabilities),
                            request_id);
                    } else {
                        transport.publishCapabilities(
                            zss::protocol::buildCapabilitiesPayload(capabilities));
                    }
                }

                if (result.request_status_snapshot) {
                    if constexpr (std::is_same_v<std::decay_t<decltype(transport)>, zss::transport::SerialTransport>) {
                        transport.publishStatusSnapshot(
                            zss::protocol::buildStatusSnapshotPayload(g_app_state),
                            request_id);
                    } else {
                        transport.publishStatusSnapshot(
                            zss::protocol::buildStatusSnapshotPayload(g_app_state));
                    }
                }
            }
        };

    handleCommandForTransport(g_ble_transport, zss::transport::TransportKind::Ble);
    handleCommandForTransport(g_serial_transport, zss::transport::TransportKind::Serial);

    if (g_pump_toggle_button.takeToggleRequest()) {
        const uint32_t previous_status_flags = g_app_state.statusFlags();
        zss::app::CommandRequest local_request{};
        local_request.command_id = zss::protocol::CommandId::SetPumpState;
        local_request.arg0_u32 = g_pump_controller.isEnabled() ? 0u : 1u;
        local_request.source_transport = zss::transport::TransportKind::Local;
        const auto result = g_command_processor.handle(local_request);
        if (result.result_code != zss::protocol::ResultCode::Ok) {
            emitEvent(
                zss::protocol::EventCode::CommandError,
                kEventSeverityError,
                static_cast<uint32_t>(local_request.command_id));
        }
        emitStatusTransitionEvents(previous_status_flags, g_app_state.statusFlags());
        zss::services::Logger::log(
            zss::services::LogLevel::Info,
            "Input",
            "Local pump button toggled state=%u",
            static_cast<unsigned>(local_request.arg0_u32));
    }

    const uint32_t now_ms = millis();
    const uint32_t now_us = micros();
    updateSamplingCadenceForActiveTransport(now_us);
    runSamplingStep(now_us);
    updateStatusLedContext();
    g_status_led.tick(now_ms);
    emitSummaryLog(now_ms);
}
