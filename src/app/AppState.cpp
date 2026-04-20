#include "app/AppState.h"

namespace zss::app {

AppState::AppState(uint16_t nominal_sample_period_ms)
    : nominal_sample_period_ms_(nominal_sample_period_ms) {}

uint32_t AppState::nextSequence() {
    latest_sequence_ += 1u;
    return latest_sequence_;
}

void AppState::updateMeasurements(uint32_t sequence, const measurement::SensorMeasurements& measurements) {
    latest_sequence_ = sequence;
    latest_measurements_ = measurements;
}

void AppState::setNominalSamplePeriodMs(uint16_t nominal_sample_period_ms) {
    if (nominal_sample_period_ms == 0u) {
        return;
    }
    nominal_sample_period_ms_ = nominal_sample_period_ms;
}

void AppState::setTransportSessionActive(bool active) {
    assignStatusFlag(status_flags_, protocol::kStatusFlagTransportSessionActiveMask, active);
}

void AppState::setPumpOn(bool enabled) {
    assignStatusFlag(status_flags_, protocol::kStatusFlagPumpOnMask, enabled);
}

void AppState::setStatusFlag(uint32_t mask, bool enabled) {
    assignStatusFlag(status_flags_, mask, enabled);
}

void AppState::setDiagnosticBit(uint32_t mask, bool enabled) {
    assignStatusFlag(diagnostic_bits_, mask, enabled);
}

void AppState::incrementSampleOverrunCount(uint32_t amount) {
    sample_overrun_count_ += amount;
    assignStatusFlag(status_flags_, protocol::kStatusFlagSamplingOverrunMask, true);
}

void AppState::incrementCommandErrorCount() {
    command_error_count_ += 1u;
    assignStatusFlag(status_flags_, protocol::kStatusFlagCommandErrorLatchedMask, true);
}

uint32_t AppState::latestSequence() const {
    return latest_sequence_;
}

uint32_t AppState::statusFlags() const {
    return status_flags_;
}

uint32_t AppState::diagnosticBits() const {
    return diagnostic_bits_;
}

uint16_t AppState::nominalSamplePeriodMs() const {
    return nominal_sample_period_ms_;
}

const measurement::SensorMeasurements& AppState::latestMeasurements() const {
    return latest_measurements_;
}

const char* AppState::firmwareVersion() const {
    return protocol::kFirmwareVersionString;
}

uint32_t AppState::sampleOverrunCount() const {
    return sample_overrun_count_;
}

uint32_t AppState::commandErrorCount() const {
    return command_error_count_;
}

}  // namespace zss::app
