// validated with the Pustaka runtime's glslang 16.0.0 compiler
struct Input {
    float4 v0 : ATTR0;
    float4 v1 : ATTR1;
};
struct Output { float4 pos : SV_Position; float4 effect : TEXCOORD0; };
Output vs(Input i) { Output o; o.pos=i.v0; o.effect=i.v1; return o; }
float LightningPath(float t) {
    float k=floor(t*18), f=frac(t*18);
    float a=frac(sin(k*127.1+31.7)*43758.5453);
    float b=frac(sin((k+1)*127.1+31.7)*43758.5453);
    return .30*(lerp(a,b,f)-.5)+.075*sin(t*39)+.035*sin(t*91);
}
float4 ps(Output i) : SV_Target {
    float t=saturate(i.effect.z);
    float tail=smoothstep(.75,1,t);
    float age=saturate(i.effect.y)*(1-tail);
    float head=smoothstep(0,.20,t);
    float taper=smoothstep(.45,1,t);
    float width=.775*(.40+.60*head)*(1-.98*taper);
    float across=(1-i.effect.x*i.effect.w)*.5;
    float u=2*across/width-1;
    float center=LightningPath(t);
    float d=abs(u-center);
    float core=1-smoothstep(.012,.055,d);
    float hot=exp2(-220*d*d);
    float halo=exp2(-32*d*d);
    float c1=LightningPath(.20), c2=LightningPath(.47), c3=LightningPath(.70);
    float b1=1-smoothstep(.010,.045,abs(u-(c1+1.05*(t-.20))));
    b1*=smoothstep(.20,.235,t)*(1-smoothstep(.395,.43,t));
    float b2=1-smoothstep(.010,.045,abs(u-(c2-1.10*(t-.47))));
    b2*=smoothstep(.47,.505,t)*(1-smoothstep(.665,.70,t));
    float b3=1-smoothstep(.010,.045,abs(u-(c3+.85*(t-.70))));
    b3*=smoothstep(.70,.735,t)*(1-smoothstep(.875,.91,t));
    float branches=max(b1,max(b2,b3));
    float pulse=.84+.16*sin((t*16+age*7)*6.28318);
    float coverage=saturate((core*.82+branches*.25)*age*pulse);
    float3 coreLight=lerp(float3(1,.72,.05),float3(1,.99,.70),hot);
    float3 glowLight=float3(1,.34,.015)*halo*.22;
    float3 branchLight=float3(1,.78,.12)*branches*.72;
    float3 colour=(coreLight*core+branchLight+glowLight)*age*pulse;
    return float4(colour,coverage);
}
