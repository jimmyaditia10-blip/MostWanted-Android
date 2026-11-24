struct Input { float4 v0 : ATTR0; float4 v1 : ATTR1; };
struct Output { float4 pos : SV_Position; float4 effect : TEXCOORD0; };
Output vs(Input i) { Output o; o.pos=i.v0; o.effect=i.v1; return o; }
float4 ps(Output i) : SV_Target {
    float t=saturate(i.effect.z);
    float tail=smoothstep(.75,1,t);
    float age=saturate(i.effect.y)*(1-tail);
    float head=smoothstep(0,.20,t);
    float taper=smoothstep(.45,1,t);
    float width=.775*(.40+.60*head)*(1-.98*taper);
    float across=(1-i.effect.x*i.effect.w)*.5;
    float u=2*across/width-1;
    float seg=floor(t*18), f=frac(t*18);
    float n0=frac(sin(seg*127.1+31.7)*43758.5453);
    float n1=frac(sin((seg+1)*127.1+31.7)*43758.5453);
    float center=.30*(lerp(n0,n1,f)-.5)+.075*sin(t*39)+.035*sin(t*91);
    float d=abs(u-center);
    float core=1-smoothstep(.012,.060,d);
    float hot=exp2(-220*d*d);
    float halo=exp2(-32*d*d);
    float b1=1-smoothstep(.012,.050,abs(u-(center+(t-.22)*1.05)));
    b1*=smoothstep(.18,.24,t)*(1-smoothstep(.50,.57,t));
    float b2=1-smoothstep(.012,.050,abs(u-(center-(t-.54)*1.15)));
    b2*=smoothstep(.50,.57,t)*(1-smoothstep(.84,.91,t));
    float branches=max(b1,b2);
    float pulse=.84+.16*sin((t*16+age*7)*6.28318);
    float coverage=saturate((core*.82+branches*.25)*age*pulse);
    float3 coreLight=lerp(float3(1,.72,.05),float3(1,.99,.70),hot);
    float3 glowLight=float3(1,.34,.015)*halo*.22;
    float3 branchLight=float3(1,.78,.12)*branches*.72;
    float3 colour=(coreLight*core+branchLight+glowLight)*age*pulse;
    return float4(colour,coverage);
}
