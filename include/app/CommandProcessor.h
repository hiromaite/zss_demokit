#pragma once

#include <stdint.h>

#include "app/AppState.h"
#include "protocol/ProtocolConstants.h"
#include "services/PumpController.h"
#include "transport/TransportTypes.h"

namespace zss::app {

struct CommandRequest {
    protocol::CommandId command_id = protocol::CommandId::Ping;
    uint32_t arg0_u32 = 0;
    transport::TransportKind source_transport = transport::TransportKind::Local;
};

struct CommandResult {
    protocol::CommandId command_id = protocol::CommandId::Ping;
    protocol::ResultCode result_code = protocol::ResultCode::Ok;
    uint32_t detail_u32 = 0;
    bool request_status_snapshot = false;
    bool request_capabilities = false;
};

class CommandProcessor {
  public:
    CommandProcessor(AppState& app_state, services::PumpController& pump_controller);

    CommandResult handle(const CommandRequest& request);

  private:
    AppState& app_state_;
    services::PumpController& pump_controller_;
};

}  // namespace zss::app
