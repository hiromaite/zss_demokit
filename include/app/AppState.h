#pragma once

#include <stdint.h>

#include "app/StatusFlags.h"
#include "measurement/SensorData.h"
#include "protocol/ProtocolConstants.h"

namespace zss::app {

class AppState {
  public:
    explicit AppState(uint16_t nominal_sample_period_ms);

    uint32_t nextSequence();
    void updateMeasurements(uint32_t sequence, const measurement::SensorMeasurements& measurements);
    void setNominalSamplePeriodMs(uint16_t nominal_sample_period_ms);
    void setTransportSessionActive(bool active);
    void setPumpOn(bool enabled);
    void setStatusFlag(uint32_t mask, bool enabled);
    void setDiagnosticBit(uint32_t mask, bool enabled);
    void incrementSampleOverrunCount(uint32_t amount = 1u);
    void incrementCommandErrorCount();

    uint32_t latestSequence() const;
    uint32_t statusFlags() const;
    uint32_t diagnosticBits() const;
    uint16_t nominalSamplePeriodMs() const;
    const measurement::SensorMeasurements& latestMeasurements() const;
    const char* firmwareVersion() const;
    uint32_t sampleOverrunCount() const;
    uint32_t commandErrorCount() const;

  private:
    uint32_t latest_sequence_ = 0;
    uint32_t status_flags_ = 0;
    uint32_t diagnostic_bits_ = 0;
    uint16_t nominal_sample_period_ms_ = 0;
    measurement::SensorMeasurements latest_measurements_{};
    uint32_t sample_overrun_count_ = 0;
    uint32_t command_error_count_ = 0;
};

}  // namespace zss::app
