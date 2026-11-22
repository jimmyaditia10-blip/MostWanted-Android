#pragma once

#include <cstddef>
#include <cstdint>

namespace game::lightning_aura {
float IntensityForSpeed(float speed_kmh) noexcept;
void PublishMeasuredSpeed(float speed_kmh) noexcept;
float MeasuredSpeedKmh() noexcept;

struct Vertex {
    float x, y, z;
    float intensity;
};

// Legacy procedural preview only. Production masking should use BuildParticleMaskVertices.
inline constexpr std::size_t kBoltCount = 8;
// Eight wheel-origin trunks, each with one main run and two fork branches.
inline constexpr std::size_t kSegmentsPerBolt = 14;
inline constexpr std::size_t kDominantSegments = 16;
inline constexpr std::size_t kStraightSegments = 8;
inline constexpr std::size_t kVertexCount =
    (kDominantSegments + kStraightSegments + kBoltCount * kSegmentsPerBolt) * 2;
std::size_t BuildVertices(float intensity, float time_seconds, Vertex* output,
                          std::size_t capacity) noexcept;

// A line sampled from the game's native white speed streaks. Coordinates must already be
// converted to player-car-local space; start/end remain anchored to the native line.
struct ParticleLine {
    float start_x, start_y, start_z;
    float end_x, end_y, end_z;
    float alpha;
};

// Replaces each native white streak with a narrow, jagged yellow filament while preserving
// its position, orientation, and length. Returns 0 when speed/effect/inputs are off.
inline constexpr std::size_t kParticleMaskSegments = 6;
inline constexpr std::size_t kParticleMaskVerticesPerLine = kParticleMaskSegments * 2;
std::size_t BuildParticleMaskVertices(float speed_kmh, float time_seconds,
                                      const ParticleLine* lines, std::size_t line_count,
                                      Vertex* output, std::size_t capacity) noexcept;

// Thread-safe bridge for a verified game-side streak capture hook. Samples must be player-car-local.
void PublishNativeSpeedStreaks(const ParticleLine* lines, std::size_t line_count) noexcept;
std::size_t CopyNativeSpeedStreaks(ParticleLine* output, std::size_t capacity) noexcept;
}  // namespace game::lightning_aura
