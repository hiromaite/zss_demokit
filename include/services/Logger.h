#pragma once

#include <stdint.h>

namespace zss::services {

enum class LogLevel : uint8_t {
    Debug,
    Info,
    Warn,
    Error,
};

class Logger {
  public:
    static void begin(unsigned long baudrate);
    static void setEnabled(bool enabled);
    static bool isEnabled();
    static void log(LogLevel level, const char* tag, const char* format, ...);
};

}  // namespace zss::services
