#pragma once

#include <stddef.h>
#include <stdint.h>

#include "app/CommandProcessor.h"
#include "board/BoardConfig.h"
#include "protocol/PayloadBuilders.h"

namespace zss::transport {

class SerialTransport {
  public:
    bool begin();
    void update();
    bool isConnected() const;
    bool takePendingCommand(app::CommandRequest& request, uint32_t& request_id);
    void publishTelemetry(const protocol::TelemetryPayloadV1& payload);
    void publishStatusSnapshot(const protocol::StatusSnapshotPayloadV1& payload, uint32_t request_id = 0);
    void publishCapabilities(const protocol::CapabilitiesPayloadV1& payload, uint32_t request_id = 0);
    void publishEvent(const protocol::EventPayloadV1& payload, uint32_t request_id = 0);
    void publishCommandAck(const protocol::CommandAckPayloadV1& payload, uint32_t request_id);
    void publishTimingDiagnostic(uint32_t sequence, uint32_t sample_tick_us);

  private:
    using PendingCommand = app::CommandRequest;

    void silenceTextLoggerIfNeeded();
    void appendReceivedByte(uint8_t byte);
    void consumeRxBuffer();
    bool tryDecodeFrame();
    void discardBytes(size_t count);
    void markSessionActive();
    void writeFrame(
        protocol::WiredMessageType message_type,
        uint32_t sequence,
        uint32_t request_id,
        const uint8_t* payload,
        size_t payload_length);
    static uint16_t computeCrcCcittFalse(const uint8_t* data, size_t length);

    uint8_t rx_buffer_[zss::board::kSerialRxBufferSize]{};
    size_t rx_size_ = 0;
    bool session_active_ = false;
    bool logger_silenced_ = false;
    uint32_t published_telemetry_count_ = 0;
    bool has_pending_command_ = false;
    PendingCommand pending_command_{};
    uint32_t pending_request_id_ = 0;
};

}  // namespace zss::transport
