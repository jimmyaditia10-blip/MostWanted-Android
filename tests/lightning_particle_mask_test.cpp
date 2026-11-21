#include "game/lightning_aura.h"
#include <cassert>
#include <cmath>
#include <vector>
using namespace game::lightning_aura;
int main() {
    assert(IntensityForSpeed(149.9f)==0.0f);
    assert(IntensityForSpeed(500.0f)==1.0f);
    ParticleLine lines[]={{1,0,0,1,0,-2,1},{0,0,0,0,0,0,1}};
    std::vector<Vertex> out(2*kParticleMaskVerticesPerLine);
    const auto n=BuildParticleMaskVertices(500,0.25f,lines,2,out.data(),out.size());
    assert(n==kParticleMaskVerticesPerLine);
    assert(std::fabs(out.front().x-lines[0].start_x)<1e-6f);
    assert(std::fabs(out[kParticleMaskVerticesPerLine-1].z-lines[0].end_z)<1e-6f);
    assert(BuildParticleMaskVertices(100,0.25f,lines,2,out.data(),out.size())==0);
    return 0;
}
