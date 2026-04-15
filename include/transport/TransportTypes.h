#pragma once

#include <stdint.h>

namespace zss::transport {

enum class TransportKind : uint8_t {
    Ble = 1,
    Serial = 2,
    Local = 255,
};

}  // namespace zss::transport
