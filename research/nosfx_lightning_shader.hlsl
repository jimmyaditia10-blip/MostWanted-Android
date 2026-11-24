struct Input { float4 v0 : ATTR0; float4 v1 : ATTR1; };
struct Output { float4 pos : SV_Position; float4 effect : TEXCOORD0; };
Output vs(Input i) { Output o; o.pos=i.v0; o.effect=i.v1; return o; }
float Hash(float x) { return frac(sin(x*127.1+311.7)*43758.5453); }
float LightningPath(float t) {
    float k=floor(t*26), f=frac(t*26);
    float a=Hash(k), b=Hash(k+1);
    return .72*(lerp(a,b,f)-.5)+.13*sin(t*83)+.05*sin(t*181);
}
float Fork(float t,float u,float a,float b,float side,float seed) {
    float q=saturate((t-a)/(b-a));
    float j=(Hash(floor(q*7)+seed)-.5)*.24;
    float x=LightningPath(a)+side*(.34*q+j*q);
    float m=smoothstep(a,a+.025,t)*(1-smoothstep(b-.025,b,t));
    return (1-smoothstep(.025,.085,abs(u-x)))*m;
}
float4 ps(Output i) : SV_Target {
    float t=saturate(i.effect.z);
    float tail=smoothstep(.88,1,t);
    float age=saturate(i.effect.y)*(1-tail);
    float head=smoothstep(0,.16,t);
    float taper=smoothstep(.82,1,t);
    float width=.94*(.86+.14*head)*(1-.75*taper);
    float across=(1-i.effect.x*i.effect.w)*.5;
    float u=2*across/width-1;
    float center=LightningPath(t);
    float d=abs(u-center);
    float core=1-smoothstep(.018,.09,d);
    float hot=exp2(-130*d*d), halo=exp2(-18*d*d);
    float f1=Fork(t,u,.08,.31,-1,2);
    float f2=Fork(t,u,.17,.42,1,5);
    float f3=Fork(t,u,.34,.58,-1,8);
    float f4=Fork(t,u,.46,.70,1,11);
    float f5=Fork(t,u,.62,.84,-1,14);
    float f6=Fork(t,u,.73,.96,1,17);
    float branches=max(max(max(f1,f2),max(f3,f4)),max(f5,f6));
    float pulse=.82+.18*sin((t*19+age*8)*6.28318);
    float coverage=saturate(core*.96+branches*.78)*age*pulse;
    float3 coreLight=lerp(float3(1,.72,.04),float3(1,1,.78),hot);
    float3 glowLight=float3(1,.30,.01)*halo*.30;
    float3 branchLight=float3(1,.78,.10)*branches*.92;
    float3 colour=(coreLight*core+branchLight+glowLight)*age*pulse;
    return float4(colour,coverage);
}