struct Input { float4 v0:ATTR0; float4 v1:ATTR1; };
struct Output { float4 pos:SV_Position; float4 effect:TEXCOORD0; };
Output vs(Input i){Output o;o.pos=i.v0;o.effect=i.v1;return o;}
float H(float x){return frac(sin(x*127.1+311.7)*43758.5453);}
float N(float t,float s){float k=floor(t*19),f=frac(t*19);return lerp(H(k+s),H(k+1+s),f)-.5;}
float MainBolt(float t){return N(t,3)*.48+N(t*2.1,8)*.19+N(t*4.7,13)*.075;}
float Arc(float t,float u,float a,float b,float origin,float drift,float seed,float width){
 float q=saturate((t-a)/(b-a));
 float x=origin+drift*q+N(q*1.7,seed)*.22+N(q*5.3,seed+9)*.075;
 float gate=smoothstep(a,a+.012,t)*(1-smoothstep(b-.012,b,t));
 return (1-smoothstep(width,width*2.8,abs(u-x)))*gate;
}
float4 ps(Output i):SV_Target{
 float t=saturate(i.effect.z),age=saturate(i.effect.y);
 float across=(1-i.effect.x*i.effect.w)*.5;
 float u=2*across/.94-1;
 float m=MainBolt(t),d=abs(u-m);
 float core=1-smoothstep(.006,.021,d);
 float glow=exp2(-92*d*d),wide=exp2(-13*d*d);
 float a0=Arc(t,u,.08,.95,m,.13,21,.012);
 float a1=Arc(t,u,.18,.76,m,-.34,32,.009);
 float a2=Arc(t,u,.32,.88,m,.39,43,.010);
 float a3=Arc(t,u,.48,.97,m,-.22,54,.008);
 float a4=Arc(t,u,.12,.51,m,.48,65,.008);
 float a5=Arc(t,u,.28,.69,m,-.49,76,.007);
 float a6=Arc(t,u,.57,.99,m,.31,87,.007);
 float a7=Arc(t,u,.39,.82,m,-.37,98,.007);
 float a8=Arc(t,u,.22,.62,m,.20,109,.004);
 float a9=Arc(t,u,.43,.91,m,-.18,120,.004);
 float branches=max(max(max(a0,a1),max(a2,a3)),max(max(a4,a5),max(max(a6,a7),max(a8,a9))));
 float fork=saturate(branches+Arc(t,u,.2,.9,m,.05,131,.003)*.7+Arc(t,u,.36,.96,m,-.08,142,.003)*.7);
 float spark=step(.994,H(floor(t*173)+floor(u*91)*17+age*13))*exp2(-18*abs(u-m));
 float flick=.78+.22*sin((t*37+age*7)*6.28318);
 float life=saturate(age*(1-smoothstep(.96,1,t)));
 float white=core*.95+fork*.20;
 float gold=branches*.9+glow*.42+spark*.9;
 float amber=wide*.28+spark*.5;
 float3 col=float3(1,1,.88)*white+float3(1,.66,.025)*gold+float3(1,.19,.005)*amber;
 float alpha=saturate(core+fork*.92+glow*.34+wide*.12+spark)*life*flick;
 return float4(col*life*flick,alpha);
}