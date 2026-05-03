#pragma once

#include <stddef.h>
#include <stdint.h>

#include <array>

#include "measurement/SensorData.h"
#include "protocol/PayloadBuilders.h"

namespace zss::app {

struct SampleFrame {
    protocol::TelemetryPayloadV1 telemetry{};
    uint32_t sample_tick_us = 0;
    uint32_t acquisition_duration_us = 0;
    uint32_t telemetry_publish_duration_us = 0;
    uint32_t scheduler_lateness_us = 0;
    measurement::AcquisitionTiming acquisition_timing{};
};

template <size_t Capacity>
class SampleFrameRingBuffer {
  public:
    static_assert(Capacity > 0, "SampleFrameRingBuffer capacity must be greater than zero");

    void push(const SampleFrame& frame) {
        frames_[write_index_] = frame;
        write_index_ = (write_index_ + 1u) % Capacity;
        if (size_ < Capacity) {
            size_ += 1u;
        } else {
            dropped_frame_count_ += 1u;
        }
    }

    bool latest(SampleFrame& out) const {
        if (size_ == 0u) {
            return false;
        }
        const size_t latest_index = (write_index_ + Capacity - 1u) % Capacity;
        out = frames_[latest_index];
        return true;
    }

    size_t copySince(uint32_t sequence, SampleFrame* out, size_t max_count) const {
        if (out == nullptr || max_count == 0u || size_ == 0u) {
            return 0u;
        }

        size_t copied = 0u;
        const size_t oldest_index = size_ == Capacity ? write_index_ : 0u;
        for (size_t offset = 0u; offset < size_; ++offset) {
            const size_t index = (oldest_index + offset) % Capacity;
            const auto& frame = frames_[index];
            if (frame.telemetry.sequence <= sequence) {
                continue;
            }
            out[copied] = frame;
            copied += 1u;
            if (copied >= max_count) {
                break;
            }
        }
        return copied;
    }

    size_t countSince(uint32_t sequence) const {
        if (size_ == 0u) {
            return 0u;
        }

        size_t count = 0u;
        const size_t oldest_index = size_ == Capacity ? write_index_ : 0u;
        for (size_t offset = 0u; offset < size_; ++offset) {
            const size_t index = (oldest_index + offset) % Capacity;
            const auto& frame = frames_[index];
            if (frame.telemetry.sequence > sequence) {
                count += 1u;
            }
        }
        return count;
    }

    size_t size() const {
        return size_;
    }

    size_t capacity() const {
        return Capacity;
    }

    uint32_t droppedFrameCount() const {
        return dropped_frame_count_;
    }

  private:
    std::array<SampleFrame, Capacity> frames_{};
    size_t write_index_ = 0u;
    size_t size_ = 0u;
    uint32_t dropped_frame_count_ = 0u;
};

}  // namespace zss::app
