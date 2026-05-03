#include <stdexcept>
#include <iostream>

#include "app/AppState.h"
#include "app/CommandProcessor.h"
#include "protocol/ProtocolConstants.h"
#include "services/HeaterPowerController.h"
#include "services/PumpController.h"

namespace {

void require(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

zss::app::CommandRequest command(
    zss::protocol::CommandId command_id,
    uint32_t arg0_u32) {
    zss::app::CommandRequest request{};
    request.command_id = command_id;
    request.arg0_u32 = arg0_u32;
    return request;
}

}  // namespace

int main() {
    using zss::protocol::CommandId;
    using zss::protocol::ResultCode;

    zss::app::AppState app_state(10);
    zss::services::PumpController pump(-1);
    zss::services::HeaterPowerController heater(-1);
    zss::app::CommandProcessor processor(app_state, pump, heater);

    auto result = processor.handle(command(CommandId::SetHeaterPowerState, 1u));
    require(result.result_code == ResultCode::InvalidState, "heater ON while pump OFF must be rejected");
    require(result.request_status_snapshot, "heater rejection must request a status snapshot");
    require(!heater.isEnabled(), "heater must stay OFF after rejected ON command");
    require((app_state.statusFlags() & zss::protocol::kStatusFlagHeaterPowerOnMask) == 0u,
            "heater status flag must stay clear after rejected ON command");
    require((app_state.statusFlags() & zss::protocol::kStatusFlagCommandErrorLatchedMask) != 0u,
            "command error latch must be set after rejected ON command");
    require(app_state.commandErrorCount() == 1u, "command error count must increment after rejected ON command");

    result = processor.handle(command(CommandId::SetPumpState, 1u));
    require(result.result_code == ResultCode::Ok, "pump ON must be accepted");
    require(pump.isEnabled(), "pump controller must be ON after accepted command");
    require((app_state.statusFlags() & zss::protocol::kStatusFlagPumpOnMask) != 0u,
            "pump status flag must be set after pump ON");

    result = processor.handle(command(CommandId::SetHeaterPowerState, 1u));
    require(result.result_code == ResultCode::Ok, "heater ON must be accepted while pump is ON");
    require(heater.isEnabled(), "heater controller must be ON after accepted command");
    require((app_state.statusFlags() & zss::protocol::kStatusFlagHeaterPowerOnMask) != 0u,
            "heater status flag must be set after heater ON");

    result = processor.handle(command(CommandId::SetPumpState, 0u));
    require(result.result_code == ResultCode::Ok, "pump OFF must be accepted");
    require(!pump.isEnabled(), "pump controller must be OFF after pump OFF");
    require(!heater.isEnabled(), "pump OFF must force heater OFF");
    require((app_state.statusFlags() & zss::protocol::kStatusFlagPumpOnMask) == 0u,
            "pump status flag must clear after pump OFF");
    require((app_state.statusFlags() & zss::protocol::kStatusFlagHeaterPowerOnMask) == 0u,
            "heater status flag must clear when pump is turned OFF");

    result = processor.handle(command(CommandId::SetPumpState, 2u));
    require(result.result_code == ResultCode::InvalidArgument, "invalid pump argument must be rejected");
    require(app_state.commandErrorCount() == 2u, "invalid pump argument must increment command errors");

    result = processor.handle(command(CommandId::SetHeaterPowerState, 2u));
    require(result.result_code == ResultCode::InvalidArgument, "invalid heater argument must be rejected");
    require(app_state.commandErrorCount() == 3u, "invalid heater argument must increment command errors");

    std::cout << "command_processor_smoke_ok\n";
    return 0;
}
