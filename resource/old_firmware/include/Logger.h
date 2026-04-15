#pragma once

#include <M5Unified.h>

enum class LogLevel {
    INFO,
    WARN,
    ERROR
};

namespace Logger {
    void log(LogLevel level, const char* module, const char* format, ...);
}
