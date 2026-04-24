#include "app/CommandProcessor.h"

namespace zss::app {

CommandProcessor::CommandProcessor(
    AppState& app_state,
    services::PumpController& pump_controller,
    services::HeaterPowerController& heater_power_controller)
    : app_state_(app_state),
      pump_controller_(pump_controller),
      heater_power_controller_(heater_power_controller) {}

CommandResult CommandProcessor::handle(const CommandRequest& request) {
    CommandResult result{};
    result.command_id = request.command_id;

    switch (request.command_id) {
        case protocol::CommandId::GetCapabilities:
            result.request_capabilities = true;
            return result;

        case protocol::CommandId::GetStatus:
            result.request_status_snapshot = true;
            return result;

        case protocol::CommandId::SetPumpState:
            if (request.arg0_u32 > 1u) {
                app_state_.incrementCommandErrorCount();
                result.result_code = protocol::ResultCode::InvalidArgument;
                result.detail_u32 = request.arg0_u32;
                return result;
            }
            pump_controller_.setEnabled(request.arg0_u32 == 1u);
            app_state_.setPumpOn(pump_controller_.isEnabled());
            if (!pump_controller_.isEnabled()) {
                heater_power_controller_.setEnabled(false);
                app_state_.setHeaterPowerOn(false);
            }
            result.request_status_snapshot = true;
            return result;

        case protocol::CommandId::Ping:
            return result;

        case protocol::CommandId::SetHeaterPowerState:
            if (request.arg0_u32 > 1u) {
                app_state_.incrementCommandErrorCount();
                result.result_code = protocol::ResultCode::InvalidArgument;
                result.detail_u32 = request.arg0_u32;
                return result;
            }
            if (request.arg0_u32 == 1u && !pump_controller_.isEnabled()) {
                app_state_.incrementCommandErrorCount();
                result.result_code = protocol::ResultCode::InvalidState;
                result.detail_u32 = 0u;
                result.request_status_snapshot = true;
                return result;
            }
            heater_power_controller_.setEnabled(request.arg0_u32 == 1u);
            app_state_.setHeaterPowerOn(heater_power_controller_.isEnabled());
            result.request_status_snapshot = true;
            return result;

        default:
            app_state_.incrementCommandErrorCount();
            result.result_code = protocol::ResultCode::UnsupportedCommand;
            result.detail_u32 = static_cast<uint32_t>(request.command_id);
            return result;
    }
}

}  // namespace zss::app
