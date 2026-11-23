#!/usr/bin/env python3
"""Static rendering-path census for the uploaded Need for Speed: Most Wanted Xbox XBE."""
import hashlib, struct
from pathlib import Path
from collections import Counter
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, x86_const

XBE=Path("default.xbe"); OUT=Path("xbe-rendering-report.txt")
ENTRY_KEYS=(0xA8FC57AB,0x94859D4B); THUNK_KEYS=(0x5B6D40B6,0xEFB1F152)
KNOWN={
  0x000C7740:"view projection builder",
  0x002B91C4:"matrix multiply in projection path",
  0x000D8720:"frame render / view traversal",
  0x001B93D0:"camera directors and view camera movers",
  0x0025CC70:"car render-connection update",
  0x00257E70:"car render per view",
  0x00255490:"CarRenderInfo::Render",
  0x000CE8B0:"native particle-system draw",
  0x00377050:"D3DDevice_DrawIndexedVertices",
  0x00376EE0:"D3DDevice_DrawVerticesUP",
  0x00373470:"D3DDevice_SetStreamSource",
  0x003753D0:"D3DDevice_SetIndices",
  0x003744A0:"D3DDevice_SetTransform",
  0x00374F60:"D3DDevice_SetViewport",
  0x003768B0:"D3DDevice_Swap / Present",
  0x00373E10:"D3DDevice_BeginPush",
  0x00373E30:"D3DDevice_EndPush",
  0x003772F0:"D3DDevice_Begin immediate primitive",
  0x00377330:"D3DDevice_End immediate primitive",
  0x003738E0:"D3DDevice_SetVertexShader",
  0x003773D0:"D3DDevice_SetPixelShader",
  0x00373200:"D3DDevice_CreateVertexShader",
  0x00374940:"D3DDevice_SetRenderTarget",
  0x00376A60:"D3DDevice_Clear",
  0x00375190:"D3DDevice_SetTexture",
}
WORDS=("CarRenderConn","Velocity","EmitterPositionSlotPool","EmitterSlotPool",
 "EmitterGroupSlotPool","ParticleSlotPool","Light Trail","LightTrail","Contrail",
 "Wind","Particle","Emitter","Speed","Trail","Brake","NOS","BRAKELIGHT",
 "LIGHT_BRAKE","LIGHT_RBRAKE","LIGHT_LBRAKE","CARFX_NOS")
def u32(b,o): return struct.unpack_from("<I",b,o)[0]
def off_for_va(sections,base,hs,va):
 if base<=va<base+hs: return va-base
 for s in sections:
  if s["va"]<=va<s["va"]+s["raw_size"]: return s["raw"]+va-s["va"]
 return None
def cstr(b,o,limit=512):
 if o is None or o<0 or o>=len(b): return ""
 e=b.find(b"\0",o,min(len(b),o+limit))
 if e<0: e=min(len(b),o+limit)
 return b[o:e].decode("ascii","replace")
def main():
 b=XBE.read_bytes()
 if b[:4]!=b"XBEH": raise SystemExit("Invalid XBEH")
 base,hs,img=u32(b,0x104),u32(b,0x108),u32(b,0x10C)
 nsec,secva=u32(b,0x11C),u32(b,0x120); so=secva-base
 sections=[]
 for i in range(nsec):
  o=so+i*56; flags,va,vs,raw,rs,nameva=struct.unpack_from("<6I",b,o)
  sections.append(dict(name="",flags=flags,va=va,vsize=vs,raw=raw,raw_size=rs,nameva=nameva))
 for s in sections: s["name"]=cstr(b,off_for_va(sections,base,hs,s["nameva"]),16)
 ep0,kt0=u32(b,0x128),u32(b,0x158)
 ep=next((ep0^k for k in ENTRY_KEYS if base<=ep0^k<base+img),0)
 kt=next((kt0^k for k in THUNK_KEYS if base<=kt0^k<base+img),0)
 cert=u32(b,0x118); co=off_for_va(sections,base,hs,cert)
 title_id=u32(b,co+8) if co is not None and co+12<=len(b) else 0
 title=b[co+12:co+92].decode("utf-16le","replace").split("\0")[0] if co is not None and co+92<=len(b) else ""
 nlib,libva=u32(b,0x160),u32(b,0x164); libs=[]
 lo=off_for_va(sections,base,hs,libva) if libva else None
 if lo is not None:
  for i in range(min(nlib,256)):
   o=lo+i*16
   if o+16>len(b): break
   nm=b[o:o+8].split(b"\0")[0].decode("ascii","replace")
   a,c,d,f=struct.unpack_from("<4H",b,o+8); libs.append(f"{nm} {a}.{c}.{d} flags=0x{f:04X}")
 out=[]; add=out.append
 add("NFS MOST WANTED XBE — STATIC RENDERING CENSUS v2")
 add(f"File bytes={len(b)} SHA1={hashlib.sha1(b).hexdigest()}")
 add(f"Title={title!r} title_id=0x{title_id:08X}")
 add(f"Base=0x{base:08X} headers=0x{hs:X} image=0x{img:X} entry=0x{ep:08X} thunk=0x{kt:08X}")
 add("Libraries:"); [add("  "+x) for x in libs]
 add("Sections:")
 for s in sections: add(f"  {s['name']:10s} VA=0x{s['va']:08X} VS=0x{s['vsize']:08X} RAW=0x{s['raw']:08X} RS=0x{s['raw_size']:08X} flags=0x{s['flags']:X}")
 # Strings across all raw sections, with their actual mapped VA.
 strings=[]
 for s in sections:
  ch=b[s["raw"]:s["raw"]+s["raw_size"]]; pos=0
  while pos<len(ch):
   end=ch.find(b"\0",pos)
   if end<0: break
   raw=ch[pos:end]
   if len(raw)>=4 and all(32<=v<127 for v in raw):
    val=raw.decode("ascii","replace")
    if any(w.lower() in val.lower() for w in WORDS): strings.append((s["va"]+pos,val[:160]))
   pos=end+1
 add("\nRENDER / LIGHT-TRAIL STRING CANDIDATES:")
 for va,val in strings[:600]: add(f"  0x{va:08X} {val}")
 # Disassemble every section marked executable, not just game .text.
 all_instructions=[]
 for s in sections:
  if not (s["flags"]&4) or not s["raw_size"]: continue
  md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True
  seq=list(md.disasm(b[s["raw"]:s["raw"]+s["raw_size"]],s["va"]))
  all_instructions.extend((s["name"],x) for x in seq)
  add(f"\nEXEC SECTION {s['name']} VA=0x{s['va']:08X} raw=0x{s['raw']:X} bytes=0x{s['raw_size']:X} decoded={len(seq)}")
 add(f"\nTOTAL EXECUTABLE INSTRUCTIONS DECODED: {len(all_instructions)}")
 xrefs={}
 for name,x in all_instructions:
  vals=[]
  for op in x.operands:
   if op.type==x86_const.X86_OP_IMM: vals.append(op.imm&0xFFFFFFFF)
   elif op.type==x86_const.X86_OP_MEM and op.mem.base==0 and op.mem.index==0: vals.append(op.mem.disp&0xFFFFFFFF)
  for v in vals: xrefs.setdefault(v,[]).append((name,x))
 targets=dict(KNOWN)
 for va,val in strings: targets.setdefault(va,"string: "+val)
 add("\nXREFS TO RENDER FUNCTIONS / LIGHT-TRAIL DATA:")
 for va,label in sorted(targets.items()):
  hits=xrefs.get(va,[])
  if not hits: continue
  add(f"\n  {label} @ 0x{va:08X}: {len(hits)} refs")
  for sec,x in hits[:50]: add(f"    [{sec}] {x.address:08X}: {x.mnemonic:8s} {x.op_str}")
 add("\nDIRECT CALLS TO KNOWN RENDER FUNCTIONS:")
 for sec,x in all_instructions:
  if x.mnemonic=="call" and x.operands and x.operands[0].type==x86_const.X86_OP_IMM:
   dest=x.operands[0].imm&0xFFFFFFFF
   if dest in KNOWN: add(f"  [{sec}] {x.address:08X} -> {dest:08X} {KNOWN[dest]}")
 add("\nTOP DIRECT CALL TARGETS IN GAME .text (frequency only; not symbol names):")
 textsec=next((s for s in sections if s["name"]==".text"),None)
 seq=[x for sec,x in all_instructions if sec==".text"]
 calls=Counter(x.operands[0].imm&0xFFFFFFFF for x in seq if x.mnemonic=="call" and x.operands and x.operands[0].type==x86_const.X86_OP_IMM and textsec and textsec["va"]<=(x.operands[0].imm&0xFFFFFFFF)<textsec["va"]+textsec["vsize"])
 for va,n in calls.most_common(120): add(f"  {n:4d} 0x{va:08X}")
 OUT.write_text("\n".join(out)+"\n",encoding="utf-8")
 print("\n".join(out[:160])); print(f"\nFull report: {OUT} ({OUT.stat().st_size} bytes)")
if __name__=="__main__": main()
