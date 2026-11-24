struct Input { float4 v0:ATTR0; float4 v1:ATTR1; };
struct Output { float4 pos:SV_Position; float4 effect:TEXCOORD0; };
Output vs(Input i){Output o;o.pos=i.v0;o.effect=i.v1;return o;}
float H(float x){return frac(sin(x*127.1+311.7)*43758.5453);}
float Bolt(float t,float seed){
 float k=floor(t*15),f=frac(t*15);
 float a=(H(k+seed)-.5)*.72;
 float b=(H(k+1+seed)-.5)*.72;
 return lerp(a,b,f);
}
float Strand(float t,float u,float a,float b,float side,float seed){
 float q=saturate((t-a)/(b-a));
 float base=Bolt(a,3);
 float tip=base+side*(.20+.18*H(seed));
 float seg=floor(q*8),f=frac(q*8);
 float zig=(lerp(H(seg+seed),H(seg+1+seed),f)-.5)*.16;
 float x=lerp(base,tip,q)+zig*sin(q*28.27);
 float gate=smoothstep(a,a+.018,t)*(1-smoothstep(b-.018,b,t));
 return (1-smoothstep(.009,.027,abs(u-x)))*gate;
}
float4 ps(Output i):SV_Target{
 float t=saturate(i.effect.z), age=saturate(i.effect.y);
 float tail=smoothstep(.88,1,t);
 float life=age*(1-tail);
 float across=(1-i.effect.x*i.effect.w)*.5;
 float u=2*across/.94-1;
 float main=Bolt(t,3);
 float d=abs(u-main);
 float core=1-smoothstep(.010,.030,d);
 float halo=exp2(-420*d*d);
 float b1=Strand(t,u,.10,.43,-1,4);
 float b2=Strand(t,u,.24,.57,1,7);
 float b3=Strand(t,u,.43,.76,-1,10);
 float b4=Strand(t,u,.61,.91,1,13);
 float b5=Strand(t,u,.70,.98,-1,16);
 float branches=max(max(b1,b2),max(max(b3,b4),b5));
 float flick=.78+.22*sin((t*31+age*5)*6.28318);
 float filaments=saturate(core+branches*.92);
 float alpha=saturate(filaments*.98+halo*.16)*life*flick;
 float3 whiteCore=float3(1,1,.82)*(core*.95);
 float3 yellow=float3(1,.68,.035)*(branches*.95+halo*.38);
 float3 amber=float3(1,.24,.005)*halo*.18;
 float3 colour=(whiteCore+yellow+amber)*life*flick;
 return float4(colour,alpha);
}