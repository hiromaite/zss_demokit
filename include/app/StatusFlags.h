#pragma once

#include <stdint.h>

namespace zss::app {

inline void assignStatusFlag(uint32_t& flags, uint32_t mask, bool enabled) {
    if (enabled) {
        flags |= mask;
    } else {
        flags &= ~mask;
    }
}

inline bool hasStatusFlag(uint32_t flags, uint32_t mask) {
    return (flags & mask) != 0u;
}

}  // namespace zss::app
