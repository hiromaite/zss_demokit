#include "Logger.h"
#include <cstdarg>

// ANSIエスケープコードによる色定義
#define ANSI_COLOR_RESET   "\x1b[0m"
#define ANSI_COLOR_GREEN   "\x1b[32m"
#define ANSI_COLOR_YELLOW  "\x1b[33m"
#define ANSI_COLOR_RED     "\x1b[31m"

namespace Logger {
    void log(LogLevel level, const char* module, const char* format, ...) {
        char buf[256];
        va_list args;
        va_start(args, format);
        vsnprintf(buf, sizeof(buf), format, args);
        va_end(args);

        const char* levelStr;
        const char* colorStr;

        switch (level) {
            case LogLevel::INFO:
                levelStr = "INFO";
                colorStr = ANSI_COLOR_GREEN;
                break;
            case LogLevel::WARN:
                levelStr = "WARN";
                colorStr = ANSI_COLOR_YELLOW;
                break;
            case LogLevel::ERROR:
                levelStr = "ERROR";
                colorStr = ANSI_COLOR_RED;
                break;
            default:
                levelStr = "UNKN";
                colorStr = ANSI_COLOR_RESET;
                break;
        }

        M5.Log.printf("[%9lu] %s[%-5s]%s [%-8s] %s\n", 
            millis(), colorStr, levelStr, ANSI_COLOR_RESET, module, buf);
    }
}
