#pragma once

#include "app/CommandProcessor.h"
#include "protocol/PayloadBuilders.h"

namespace zss::transport {

class BleTransport {
  public:
    bool begin();
    void update();
    bool isConnected() const;
    bool takePendingCommand(app::CommandRequest& request, uint32_t& request_id);
    bool queueOpcode(uint8_t opcode);
    void publishTelemetry(const protocol::TelemetryPayloadV1& payload);
    void publishStatusSnapshot(const protocol::StatusSnapshotPayloadV1& payload);
    void publishCapabilities(const protocol::CapabilitiesPayloadV1& payload);
    void publishEvent(const protocol::EventPayloadV1& payload);

  private:
    using PendingCommand = app::CommandRequest;

    bool connected_ = false;
    uint32_t published_telemetry_count_ = 0;
    bool has_pending_command_ = false;
    PendingCommand pending_command_{};
    uint32_t pending_request_id_ = 0;
    uint32_t next_request_id_ = 1;
};

}  // namespace zss::transport
