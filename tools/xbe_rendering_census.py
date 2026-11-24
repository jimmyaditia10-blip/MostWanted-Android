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
  # Candidate helpers reached from CarRenderInfo::Render; labels are provisional.
  0x000BF780:"car render candidate: material/mesh submit A",
  0x000C3DA0:"car render candidate: material/mesh submit B",
  0x000BF900:"car render candidate: material/mesh submit C",
  0x000D4D40:"car render candidate: body/flare helper",
  0x000BD820:"car render candidate: connection helper",
  0x000C4C80:"car render candidate: light/material helper",
  0x000C4EF0:"car render candidate: matrix/material helper",
  0x000C44B0:"car render candidate subroutine A",
  0x000C45E0:"car render candidate subroutine B",
  0x000BD790:"car render candidate subroutine C",
  0x000BD740:"car render candidate subroutine D",
  0x000C0070:"particle/render candidate helper A",
  0x000C2C40:"particle/render candidate helper B",
  0x000C5900:"particle/render candidate helper C",
  0x000C1F50:"particle/render candidate helper D",
  0x000C62F0:"frame/view render candidate helper",
  0x000C21B0:"particle/render candidate subroutine E",
  0x000C5380:"particle/render candidate subroutine F",
}
FLOW_TARGETS={**KNOWN,
  0x000BF780:"car render helper: mesh/material submission",
  0x000C3DA0:"car render helper: mesh/material submission",
  0x000C4C80:"car render helper", 0x000BF900:"car render helper",
  0x000D4D40:"car render helper", 0x000BD820:"car render helper",
  0x00243B30:"car render helper",
  0x00257B60:"car render view helper", 0x00257B70:"car render view helper",
  0x002579E0:"car render view helper", 0x00012D90:"car render helper",
  0x00012D40:"car render helper", 0x0003FD00:"car render helper",
  0x0003FCE0:"car render helper", 0x000C4EF0:"car render helper",
  0x00243860:"car render helper",
  0x000C5900:"particle helper", 0x00209680:"particle helper",
  0x00209610:"particle helper", 0x000C1F50:"particle helper",
  0x0004FCB0:"particle helper", 0x000C2C40:"particle helper",
  0x000C0070:"particle helper", 0x00209650:"particle helper",
  0x0020A770:"particle helper",
  0x000CFBC0:"frame/view helper", 0x000D82D0:"frame/view helper",
  0x000C8D40:"frame/view helper", 0x00053AF0:"frame/view helper",
  0x000D7810:"frame/view helper", 0x000D4860:"frame/view helper",
  0x000D4B30:"frame/view helper", 0x000C62F0:"frame/view helper",
  0x000511D0:"frame/view helper", 0x001C3150:"frame/view helper",
  0x000C1680:"frame/view helper", 0x000C1EA0:"frame/view helper",
  0x000C0B30:"frame/view helper", 0x000C55D0:"frame/view helper",
  0x00239A60:"frame/view helper", 0x000BDCF0:"frame/view helper",
  0x00236AB0:"frame/view helper", 0x00236AA0:"frame/view helper",
  0x000BD420:"frame/view helper", 0x001C3210:"frame/view helper",
  0x00353670:"frame/view helper",
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
  if s["name"] not in (".text","D3D","XGRPH") or not s["raw_size"]: continue
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
 # Resolve the brake-light/NOS attribute names through the XBE's bStringHash
 # convention (h = h * 33 + byte, seed 0xFFFFFFFF), then locate code immediates.
 add("\\nBRAKE-LIGHT / NOS ATTRIBUTE HASH XREFS:")
 attr_names=("BRAKELIGHT","LIGHT_BRAKELIGHTS","LIGHT_RBRAKE","LIGHT_LBRAKE",
             "CARFX_NOS_BLOWOFF","BRAKELIGHT_CENTRE","BRAKELIGHT_RIGHT",
             "BRAKELIGHT_LEFT","REAR_BRAKE","RIGHT_BRAKELIGHT","LEFT_BRAKELIGHT")
 for attr in attr_names:
  hv=0xFFFFFFFF
  for ch in attr.encode("ascii"): hv=(hv*33+ch)&0xFFFFFFFF
  refs=[]
  for sec,x in all_instructions:
   if any(op.type==x86_const.X86_OP_IMM and (op.imm&0xFFFFFFFF)==hv for op in x.operands):
    refs.append((sec,x))
  add(f"\\n  {attr} hash=0x{hv:08X}: {len(refs)} immediate refs")
  for sec,x in refs[:80]:
   add(f"    [{sec}] {x.address:08X}: {x.mnemonic:8s} {x.op_str}")
   seq=[ins for sec2,ins in all_instructions if sec2==sec and x.address-12<=ins.address<=x.address+16]
   for ins in seq: add(f"      {ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
 # Also locate literal pointers to the actual XBE string-table entries.
 add("\\nRAW POINTER XREFS TO BRAKE-LIGHT / NOS STRINGS:")
 for va,val in strings:
  if not any(k in val.upper() for k in ("BRAKE","NOS","WIND","TRAIL")): continue
  needle=struct.pack("<I",va); hits=[]; start=0
  while True:
   off=b.find(needle,start)
   if off<0: break
   hits.append(off); start=off+1
  if hits:
   add(f"  {val} VA=0x{va:08X}: "+", ".join(f"file+0x{o:X}" for o in hits[:32]))
   for hit in hits[:12]:
    sec=next((ss for ss in sections if ss["raw"]<=hit<ss["raw"]+ss["raw_size"]),None)
    if not sec: continue
    ptr_va=sec["va"]+(hit-sec["raw"])
    refs=[(ss,x) for ss,x in all_instructions
          if any(op.type==x86_const.X86_OP_IMM and (op.imm&0xFFFFFFFF)==ptr_va for op in x.operands)]
    lo=max(sec["raw"],hit-0x20); hi=min(sec["raw"]+sec["raw_size"],hit+0x24)
    add(f"    pointer-slot VA=0x{ptr_va:08X} refs={len(refs)} bytes[{lo:06X}:{hi:06X}]={b[lo:hi].hex(' ')}")
    for ss,x in refs[:12]: add(f"      code [{ss}] {x.address:08X}: {x.mnemonic:8s} {x.op_str}")
    # Decode adjacent pointer words that land on known XBE strings.
    for pos in range(max(sec["raw"],hit-0x18),min(sec["raw"]+sec["raw_size"],hit+0x1C),4):
     if pos+4>len(b): break
     valptr=u32(b,pos)
     match=next((name for sva,name in strings if sva==valptr),None)
     if match: add(f"      adjacent string pointer file+0x{pos:X} -> {match}")
 add("\nDIRECT CALLS TO KNOWN RENDER FUNCTIONS:")
 for sec,x in all_instructions:
  if x.mnemonic=="call" and x.operands and x.operands[0].type==x86_const.X86_OP_IMM:
   dest=x.operands[0].imm&0xFFFFFFFF
   if dest in KNOWN: add(f"  [{sec}] {x.address:08X} -> {dest:08X} {KNOWN[dest]}")
 add("\nTARGETED FUNCTION DISASSEMBLY (direct decode at known XBE addresses):")
 for va,label in sorted(KNOWN.items()):
  candidates=[va]
  if va<base: candidates.insert(0,base+va)
  chosen=None; chosen_sec=None; chosen_off=None
  for actual in candidates:
   for s in sections:
    if s["name"] not in (".text","D3D","XGRPH"): continue
    if s["va"]<=actual<s["va"]+s["raw_size"]:
     chosen,chosen_sec,chosen_off=actual,s,s["raw"]+(actual-s["va"]); break
   if chosen is not None: break
  if chosen is None:
   add(f"\n  {label} @ 0x{va:08X}: outside executable sections")
   continue
  md=Cs(CS_ARCH_X86,CS_MODE_32)
  seq=list(md.disasm(b[chosen_off:chosen_off+0x300],chosen))
  add(f"\n  {label} requested=0x{va:08X} decoded=0x{chosen:08X} section={chosen_sec['name']}")
  for x in seq[:64]: add(f"    {x.address:08X}: {x.mnemonic:8s} {x.op_str}")
 add("\nCONTROL-FLOW CALL CENSUS FOR EACH GAME / D3D ENTRY:")
 for start,label in sorted(FLOW_TARGETS.items()):
  sec=next((s for s in sections if s["name"] in (".text","D3D","XGRPH") and s["va"]<=start<s["va"]+s["raw_size"]),None)
  if not sec: continue
  todo=[start]; seen=set(); direct=Counter(); indirect=[]; decoded=0
  md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True
  while todo and decoded<10000:
   pc=todo.pop()
   while sec["va"]<=pc<sec["va"]+sec["raw_size"] and pc not in seen and decoded<10000:
    seen.add(pc); off=sec["raw"]+(pc-sec["va"])
    one=next(md.disasm(b[off:off+15],pc,count=1),None)
    if one is None: break
    decoded+=1
    if one.mnemonic=="call" and one.operands:
     op=one.operands[0]
     if op.type==x86_const.X86_OP_IMM: direct[op.imm&0xFFFFFFFF]+=1
     else: indirect.append(f"{one.address:08X}: {one.mnemonic} {one.op_str}")
    if one.mnemonic.startswith("ret") or one.mnemonic in ("int3","ud2"): break
    if one.mnemonic=="jmp":
     if one.operands and one.operands[0].type==x86_const.X86_OP_IMM:
      dest=one.operands[0].imm&0xFFFFFFFF
      if sec["va"]<=dest<sec["va"]+sec["raw_size"]: todo.append(dest)
     break
    if one.mnemonic.startswith("j") or one.mnemonic.startswith("loop"):
     if one.operands and one.operands[0].type==x86_const.X86_OP_IMM:
      dest=one.operands[0].imm&0xFFFFFFFF
      if sec["va"]<=dest<sec["va"]+sec["raw_size"]: todo.append(dest)
    pc+=one.size
  add(f"\n  {label} @ 0x{start:08X}: reachable={decoded} direct_calls={sum(direct.values())} indirect_calls={len(indirect)}")
  for dest,n in direct.most_common(45):
   add(f"    call {n:3d}x -> 0x{dest:08X} {KNOWN.get(dest,'')}")
  for item in indirect[:35]: add("    indirect "+item)
 add("\nTOP DIRECT CALL TARGETS IN GAME .text (frequency only; not symbol names):")
 textsec=next((s for s in sections if s["name"]==".text"),None)
 seq=[x for sec,x in all_instructions if sec==".text"]
 calls=Counter(x.operands[0].imm&0xFFFFFFFF for x in seq if x.mnemonic=="call" and x.operands and x.operands[0].type==x86_const.X86_OP_IMM and textsec and textsec["va"]<=(x.operands[0].imm&0xFFFFFFFF)<textsec["va"]+textsec["vsize"])
 for va,n in calls.most_common(120): add(f"  {n:4d} 0x{va:08X}")
 OUT.write_text("\n".join(out)+"\n",encoding="utf-8")
 print("\n".join(out[:160])); print(f"\nFull report: {OUT} ({OUT.stat().st_size} bytes)")
if __name__=="__main__": main()
