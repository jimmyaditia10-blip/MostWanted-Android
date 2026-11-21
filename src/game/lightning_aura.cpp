#include "lightning_aura.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <mutex>

namespace game::lightning_aura {
namespace {
constexpr float kPi = 3.14159265358979323846f;
constexpr float kTwoPi = 2.0f * kPi;
constexpr float kHalfWidth = 1.35f, kHalfLength = 2.25f, kHeight = 1.15f;
constexpr float kMinLineLengthSq = 0.0004f;
std::atomic<float> g_measured_speed_kmh{0.0f};
std::mutex g_streak_mutex;
ParticleLine g_native_streaks[256]{};
std::size_t g_native_streak_count = 0;
float Hash01(std::uint32_t v) noexcept {
    v ^= v >> 16; v *= 0x7feb352du; v ^= v >> 15; v *= 0x846ca68bu; v ^= v >> 16;
    return float(v & 0x00ffffffu) / float(0x01000000u);
}
float Clamp01(float v) noexcept { return std::clamp(v, 0.0f, 1.0f); }
bool Finite3(float x, float y, float z) noexcept {
    return std::isfinite(x) && std::isfinite(y) && std::isfinite(z);
}
struct Vec3 { float x, y, z; };
Vec3 Cross(Vec3 a, Vec3 b) noexcept {
    return {a.y*b.z-a.z*b.y, a.z*b.x-a.x*b.z, a.x*b.y-a.y*b.x};
}
float LengthSq(Vec3 v) noexcept { return v.x*v.x+v.y*v.y+v.z*v.z; }
Vec3 Scale(Vec3 v, float s) noexcept { return {v.x*s,v.y*s,v.z*s}; }
Vec3 Add(Vec3 a, Vec3 b) noexcept { return {a.x+b.x,a.y+b.y,a.z+b.z}; }
Vec3 Sub(Vec3 a, Vec3 b) noexcept { return {a.x-b.x,a.y-b.y,a.z-b.z}; }
}
void PublishMeasuredSpeed(float speed_kmh) noexcept {
    g_measured_speed_kmh.store(std::isfinite(speed_kmh) && speed_kmh >= 0.0f ? speed_kmh : 0.0f,
                                std::memory_order_relaxed);
}
float MeasuredSpeedKmh() noexcept { return g_measured_speed_kmh.load(std::memory_order_relaxed); }
float IntensityForSpeed(float speed_kmh) noexcept {
    if (!std::isfinite(speed_kmh) || speed_kmh < 150.0f) return 0.0f;
    return Clamp01((speed_kmh - 150.0f) / 350.0f);
}
std::size_t BuildVertices(float intensity, float time_seconds, Vertex* output,
                          std::size_t capacity) noexcept {
    if (!output || capacity < kVertexCount || !std::isfinite(intensity) ||
        !std::isfinite(time_seconds) || time_seconds < 0.0f || intensity <= 0.0f) return 0;
    intensity = Clamp01(intensity);
    const float phase = time_seconds * (8.0f + 12.0f * intensity);
    // Local-space emission points: three across each bumper, plus both side skirts.
    // The z sign is mirrored so the same pattern wraps both ends of the vehicle.
    struct Root { float x, y, z, dx, dy, dz; };
    constexpr Root roots[kBoltCount] = {
        {-1.05f,0.22f, 2.18f,-0.34f,0.72f, 0.62f}, {0.0f,0.30f, 2.24f,0.08f,0.94f,0.36f},
        { 1.05f,0.22f, 2.18f, 0.38f,0.72f,0.58f}, {-1.18f,0.25f,-2.16f,-0.42f,0.76f,-0.48f},
        {0.0f,0.30f,-2.22f,-0.06f,0.95f,-0.34f}, {1.18f,0.25f,-2.16f,0.44f,0.74f,-0.48f},
        {-1.22f,0.28f, 1.05f,-0.92f,0.48f, 0.12f}, {-1.22f,0.28f, 0.0f,-0.98f,0.34f, 0.08f},
        {-1.22f,0.28f,-1.05f,-0.90f,0.48f,-0.12f}, {1.22f,0.28f, 1.05f,0.92f,0.48f,0.12f},
        {1.22f,0.28f, 0.0f,0.98f,0.34f,-0.08f}, {1.22f,0.28f,-1.05f,0.90f,0.48f,-0.12f}
    };
    std::size_t at = 0;
    for (unsigned bolt = 0; bolt < kBoltCount; ++bolt) {
        const Root& root = roots[bolt];
        const float seed = float(bolt * 17u + 3u);
        const float pulse = 0.72f + 0.28f * std::sin(phase * 1.35f + seed);
        const float length = 0.75f + 0.85f * intensity + 0.18f * std::sin(phase + seed);
        Vec3 dir{root.dx, root.dy, root.dz};
        const float dl = std::sqrt(std::max(LengthSq(dir), 1.0e-6f));
        dir = Scale(dir, 1.0f / dl);
        const Vec3 side = Scale(Cross(dir, Vec3{0,1,0}), 1.0f);
        Vec3 previous{root.x, root.y, root.z};
        for (unsigned segment = 0; segment < kSegmentsPerBolt; ++segment) {
            const float t = float(segment + 1) / float(kSegmentsPerBolt);
            const float jitter = (Hash01(bolt*101u + segment*13u +
                                  std::uint32_t(time_seconds*18.0f)) - 0.5f) *
                                  (0.16f + 0.24f*intensity);
            Vec3 next = Add(Vec3{root.x,root.y,root.z}, Scale(dir, length*t));
            next = Add(next, Scale(side, jitter));
            next.y += 0.10f * std::sin(phase + seed + t*8.0f);
            const float brightness = intensity * pulse * (0.78f + 0.22f*std::sin(phase + seed + t*5.0f));
            output[at++] = {previous.x,previous.y,previous.z,brightness};
            output[at++] = {next.x,next.y,next.z,brightness};
            previous = next;
        }
    }
    return at;
}

void PublishNativeSpeedStreaks(const ParticleLine* lines, std::size_t line_count) noexcept {
    std::lock_guard<std::mutex> lock(g_streak_mutex);
    g_native_streak_count = 0;
    if (!lines) return;
    const std::size_t count = std::min<std::size_t>(line_count, 256);
    for (std::size_t i=0; i<count; ++i) {
        const ParticleLine& p=lines[i];
        if (!Finite3(p.start_x,p.start_y,p.start_z) || !Finite3(p.end_x,p.end_y,p.end_z) ||
            !std::isfinite(p.alpha) || p.alpha<=0.001f) continue;
        const float dx=p.end_x-p.start_x, dy=p.end_y-p.start_y, dz=p.end_z-p.start_z;
        if (dx*dx+dy*dy+dz*dz<kMinLineLengthSq) continue;
        g_native_streaks[g_native_streak_count++]=p;
    }
}
std::size_t CopyNativeSpeedStreaks(ParticleLine* output, std::size_t capacity) noexcept {
    if (!output || !capacity) return 0;
    std::lock_guard<std::mutex> lock(g_streak_mutex);
    const std::size_t count=std::min(capacity,g_native_streak_count);
    std::copy_n(g_native_streaks,count,output);
    return count;
}

std::size_t BuildParticleMaskVertices(float speed_kmh, float time_seconds,
                                      const ParticleLine* lines, std::size_t line_count,
                                      Vertex* output, std::size_t capacity) noexcept {
    const float intensity = IntensityForSpeed(speed_kmh);
    if (intensity <= 0.0f || !std::isfinite(time_seconds) || time_seconds < 0.0f ||
        !lines || !line_count || !output) return 0;
    const std::size_t count = std::min(line_count, capacity / kParticleMaskVerticesPerLine);
    std::size_t at = 0;
    const float phase = time_seconds * (12.0f + 18.0f*intensity);
    for (std::size_t i=0; i<count; ++i) {
        const ParticleLine& p=lines[i];
        if (!Finite3(p.start_x,p.start_y,p.start_z) || !Finite3(p.end_x,p.end_y,p.end_z) ||
            !std::isfinite(p.alpha)) continue;
        const Vec3 start{p.start_x,p.start_y,p.start_z}, end{p.end_x,p.end_y,p.end_z};
        const Vec3 delta=Sub(end,start);
        const float len2=LengthSq(delta);
        if (!std::isfinite(len2) || len2<kMinLineLengthSq) continue;
        const float len=std::sqrt(len2);
        const Vec3 dir=Scale(delta,1.0f/len);
        const Vec3 ref=std::fabs(dir.y)<0.88f ? Vec3{0,1,0} : Vec3{1,0,0};
        Vec3 side=Cross(dir,ref);
        side=Scale(side,1.0f/std::sqrt(std::max(LengthSq(side),1.0e-8f)));
        const float pulse=0.82f+0.18f*std::sin(phase+float(i)*1.73f);
        const float brightness=Clamp01(Clamp01(p.alpha)*intensity*pulse);
        if (brightness<=0.001f) continue;
        const float amp=std::min(0.18f,len*0.075f)*(0.35f+0.65f*intensity);
        Vec3 previous=start;
        for (std::size_t s=0;s<kParticleMaskSegments;++s) {
            const float t=float(s+1)/float(kParticleMaskSegments);
            Vec3 next=Add(start,Scale(delta,t));
            if (s+1<kParticleMaskSegments) {
                const float sign=(s&1u)?-1.0f:1.0f;
                const float noise=0.55f+0.45f*Hash01(std::uint32_t(i*131u+s*17u+std::uint32_t(phase*11.0f)));
                next=Add(next,Scale(side,sign*amp*noise));
            }
            output[at++]={previous.x,previous.y,previous.z,brightness};
            output[at++]={next.x,next.y,next.z,brightness*(0.72f+0.28f*intensity)};
            previous=next;
        }
    }
    return at;
}
}  // namespace game::lightning_aura
