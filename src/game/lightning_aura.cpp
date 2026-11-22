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
    const float phase = time_seconds * (10.0f + 16.0f * intensity);
    // The reference effect is a rear-facing fan: bright trunks leave the rear bumper,
    // fork outward/upward, and taper into long trails behind the car.
    struct Root { float x, y, z, fan; };
    constexpr Root roots[kBoltCount] = {
        {-1.08f,0.30f,-2.18f,-0.72f}, {-0.78f,0.34f,-2.24f,-0.52f},
        {-0.43f,0.38f,-2.28f,-0.30f}, {-0.14f,0.40f,-2.30f,-0.12f},
        { 0.14f,0.40f,-2.30f, 0.12f}, { 0.43f,0.38f,-2.28f, 0.30f},
        { 0.78f,0.34f,-2.24f, 0.52f}, { 1.08f,0.30f,-2.18f, 0.72f}
    };
    std::size_t at = 0;
    auto emit = [&](Vec3 a, Vec3 b, float brightness) {
        if (at + 2 > capacity) return;
        output[at++] = {a.x,a.y,a.z,brightness};
        output[at++] = {b.x,b.y,b.z,brightness};
    };
    for (unsigned bolt = 0; bolt < kBoltCount; ++bolt) {
        const Root& root = roots[bolt];
        const float seed = float(bolt * 19u + 7u);
        const float pulse = 0.68f + 0.32f * std::sin(phase * 1.17f + seed);
        const float length = 5.0f + 8.5f * intensity;
        const Vec3 origin{root.x,root.y,root.z};
        const Vec3 trunk{root.fan * 0.42f, 0.10f + 0.12f*intensity, -1.0f};
        const float trunk_len = std::sqrt(std::max(LengthSq(trunk),1.0e-6f));
        const Vec3 dir=Scale(trunk,1.0f/trunk_len);
        const Vec3 side=Scale(Cross(dir,Vec3{0,1,0}),1.0f);
        Vec3 previous=origin, fork_point=origin;
        for (unsigned s=0;s<8;++s) {
            const float t=float(s+1)/8.0f;
            const float jitter=(Hash01(bolt*101u+s*23u+std::uint32_t(time_seconds*20.0f))-0.5f)*
                               (0.20f+0.34f*intensity);
            Vec3 next=Add(origin,Scale(dir,length*t));
            next=Add(next,Scale(side,jitter));
            next.y+=0.16f*std::sin(phase+seed+t*7.0f);
            const float brightness=intensity*pulse*(0.82f+0.18f*std::sin(phase+seed+t*5.0f));
            emit(previous,next,brightness);
            previous=next;
            if(s==3) fork_point=next;
        }
        // Two lightning forks peel away from the trunk, producing the broad fan seen
        // in the supplied reference instead of a single straight speed streak.
        for(unsigned branch=0;branch<2;++branch) {
            const float sign=branch==0?-1.0f:1.0f;
            const float spread=sign*(0.65f+0.30f*std::fabs(root.fan));
            Vec3 branch_dir{root.fan*0.28f+spread,0.58f+0.10f*intensity,-0.62f};
            const float bl=std::sqrt(std::max(LengthSq(branch_dir),1.0e-6f));
            branch_dir=Scale(branch_dir,1.0f/bl);
            Vec3 bp=fork_point;
            const float branch_len=2.4f+3.8f*intensity;
            for(unsigned s=0;s<3;++s) {
                const float t=float(s+1)/3.0f;
                const float j=(Hash01(bolt*313u+branch*71u+s*29u+
                              std::uint32_t(time_seconds*17.0f))-0.5f)*(0.28f+0.35f*intensity);
                Vec3 bn=Add(fork_point,Scale(branch_dir,branch_len*t));
                bn=Add(bn,Scale(side,j));
                bn.y+=0.12f*std::sin(phase+seed+float(branch)*2.0f+t*9.0f);
                emit(bp,bn,intensity*pulse*(0.70f+0.30f*std::sin(phase+seed+t*8.0f)));
                bp=bn;
            }
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
