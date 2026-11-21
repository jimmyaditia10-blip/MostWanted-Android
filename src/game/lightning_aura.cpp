#include "lightning_aura.h"

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstdint>

namespace game::lightning_aura {
namespace {
constexpr float kPi = 3.14159265358979323846f;
constexpr float kTwoPi = 2.0f * kPi;
constexpr float kHalfWidth = 1.35f, kHalfLength = 2.25f, kHeight = 1.15f;
constexpr float kMinLineLengthSq = 0.0004f;
std::atomic<float> g_measured_speed_kmh{0.0f};
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
    const float phase = time_seconds * (5.0f + 4.0f * intensity);
    std::size_t at = 0;
    for (unsigned bolt = 0; bolt < kBoltCount; ++bolt) {
        const float angle = kTwoPi * (float(bolt) / float(kBoltCount));
        const float cs = std::cos(angle), sn = std::sin(angle), seed = float(bolt * 17u + 3u);
        float px = cs * (kHalfWidth + 0.12f), py = sn * (kHalfLength + 0.12f);
        float pz = 0.18f + 0.16f * std::sin(phase + seed);
        for (unsigned segment = 0; segment < kSegmentsPerBolt; ++segment) {
            const float t = float(segment + 1) / float(kSegmentsPerBolt);
            const float jitter = (Hash01(bolt*101u + segment*13u + std::uint32_t(time_seconds*12.0f)) - 0.5f) *
                                 (0.22f + 0.18f*intensity);
            const float radius = 1.0f + 0.12f*std::sin(phase + seed + t*7.0f);
            const float nx = cs*(kHalfWidth*radius+jitter)-sn*(jitter*0.7f);
            const float ny = sn*(kHalfLength*radius+jitter)+cs*(jitter*0.7f);
            const float nz = kHeight*t + 0.22f*std::sin(phase+seed+t*9.0f);
            const float brightness = intensity*(0.65f+0.35f*std::sin(phase*1.7f+seed+t*5.0f));
            output[at++] = {px,py,pz,brightness}; output[at++] = {nx,ny,nz,brightness};
            px=nx; py=ny; pz=nz;
        }
    }
    return at;
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
