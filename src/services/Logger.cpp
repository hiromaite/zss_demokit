#include "services/Logger.h"

#include <Arduino.h>

#include <stdarg.h>
#include <stdio.h>

namespace zss::services {

namespace {

bool g_logger_enabled = true;

const char* levelToString(LogLevel level) {
    switch (level) {
        case LogLevel::Debug:
            return "DEBUG";
        case LogLevel::Info:
            return "INFO";
        case LogLevel::Warn:
            return "WARN";
        case LogLevel::Error:
            return "ERROR";
        default:
            return "LOG";
    }
}

}  // namespace

void Logger::begin(unsigned long baudrate) {
    Serial.begin(baudrate);
}

void Logger::setEnabled(bool enabled) {
    g_logger_enabled = enabled;
}

bool Logger::isEnabled() {
    return g_logger_enabled;
}

void Logger::log(LogLevel level, const char* tag, const char* format, ...) {
    if (!g_logger_enabled) {
        return;
    }

    char message_buffer[192];
    va_list args;
    va_start(args, format);
    vsnprintf(message_buffer, sizeof(message_buffer), format, args);
    va_end(args);

    Serial.printf("[%10lu] %-5s %-12s %s\n", millis(), levelToString(level), tag, message_buffer);
}

}  // namespace zss::services
