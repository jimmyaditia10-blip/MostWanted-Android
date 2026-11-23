#!/usr/bin/env python3
"""Static rendering-path census for the uploaded Need for Speed: Most Wanted Xbox XBE."""
import struct
from pathlib import Path
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

XBE = Path("default.xbe")
OUT = Path("xbe-rendering-report.txt")
ENTRY_KEYS = (0xA8FC57AB, 0x94859D4B)
THUNK_KEYS = (0x5B6D40B6, 0xEFB1F152)
KNOWN = {
    0x000C7740: "BuildViewProjection / camera projection",
    0x002B91C4: "Matrix multiply used by view projection",
    0x000D8720: "Frame render / view traversal",
    0x0025CC70: "Car render-connection update",
    0x00257E70: "Car render per view",
    0x00255490: "CarRenderInfo::Render",
    0x000CE8B0: "Native particle-system draw",
}
WORDS = ("CarRenderConn", "Velocity", "EmitterPositionSlotPool",
         "EmitterSlotPool", "EmitterGroupSlotPool", "ParticleSlotPool",
         "Light Trail", "LightTrail", "Contrail", "Wind", "Particle",
         "Emitter", "Speed", "Trail", "Brake", "NOS")

def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def mapped_offset(sections, base, header_size, va):
    if base <= va < base + header_size: return va - base
    for s in sections:
        if s["va"] <= va < s["va"] + s["raw_size"]:
            return s["raw"] + va - s["va"]
    return None
def cstr(b, off, limit=256):
    if off is None or off < 0 or off >= len(b): return ""
    end=b.find(b"\0", off, min(len(b),off+limit))
    if end<0: end=min(len(b),off+limit)
    return b[off:end].decode("ascii","replace")
def main():
    b=XBE.read_bytes()
    if b[:4] != b"XBEH": raise SystemExit("default.xbe has no XBEH signature")
    base, hs, image_size = u32(b,0x104),u32(b,0x108),u32(b,0x10C)
    sec_count, sec_va = u32(b,0x11C),u32(b,0x120)
    sec_off=sec_va-base
    sections=[]
    for i in range(sec_count):
        o=sec_off+i*56
        flags,va,vs,raw,rs,name_va=struct.unpack_from("<6I",b,o)
        name=cstr(b,mapped_offset([],base,hs,name_va)) if name_va < base+hs else ""
        if not name:
            for s in sections:
                pass
            name=cstr(b, name_va-base) if base <= name_va < base+hs else ""
        sections.append(dict(name=name,flags=flags,va=va,vsize=vs,raw=raw,raw_size=rs))
    ep_enc,thunk_enc=u32(b,0x128),u32(b,0x158)
    ep=next((ep_enc^k for k in ENTRY_KEYS if base <= (ep_enc^k) < base+image_size),None)
    thunk=next((thunk_enc^k for k in THUNK_KEYS if base <= (thunk_enc^k) < base+image_size),None)
    cert=u32(b,0x118); cert_off=cert-base
    title_id=u32(b,cert_off+8) if cert_off+12<=len(b) else 0
    title_name=b[cert_off+12:cert_off+92].decode("utf-16le","replace").split("\0")[0] if cert_off+92<=len(b) else ""
    nlib,lib_va=u32(b,0x160),u32(b,0x164)
    libs=[]
    if lib_va and base<=lib_va<base+hs:
        lo=lib_va-base
        for i in range(min(nlib,256)):
            o=lo+i*16
            if o+16>len(b): break
            nm=b[o:o+8].split(b"\0")[0].decode("ascii","replace")
            major,minor,build,flags=struct.unpack_from("<4H",b,o+8)
            libs.append(f"{nm} {major}.{minor}.{build} flags=0x{flags:04X}")
    out=[]
    add=out.append
    add("NFS MOST WANTED XBE — STATIC RENDERING CENSUS")
    add(f"File bytes: {len(b)} | SHA1: {__import__('hashlib').sha1(b).hexdigest()}")
    add(f"Title: {title_name!r} | title_id=0x{title_id:08X}")
    add(f"Image base=0x{base:08X} headers=0x{hs:X} image=0x{image_size:X}")
    add(f"Entry=0x{(ep or 0):08X} encoded=0x{ep_enc:08X} | kernel_thunk=0x{(thunk or 0):08X}")
    add("Libraries:")
    add("  " + "\n  ".join(libs))
    add("Sections:")
    for s in sections:
        add(f"  {s['name'] or '(unnamed)':10s} VA=0x{s['va']:08X} VS=0x{s['vsize']:08X} RAW=0x{s['raw']:08X} RS=0x{s['raw_size']:08X} flags=0x{s['flags']:X}")
    # Search all raw sections for printable strings, retain the exact XBE VA.
    strings=[]
    for s in sections:
        chunk=b[s["raw"]:s["raw"]+s["raw_size"]]
        start=0
        while start<len(chunk):
            end=chunk.find(b"\0",start)
            if end<0: break
            raw=chunk[start:end]
            if len(raw)>=4 and all(32<=x<127 for x in raw):
                val=raw.decode("ascii","replace")
                if any(w.lower() in val.lower() for w in WORDS):
                    strings.append((s["va"]+start,val[:180]))
            start=end+1
    add("\nRENDER / PARTICLE STRING CANDIDATES:")
    for va,val in strings[:500]: add(f"  0x{va:08X}  {val}")
    textsec=next((s for s in sections if s["name"].lower()==".text"),None)
    if not textsec:
        textsec=next((s for s in sections if s["flags"]&4 and s["raw_size"]>0x100000),None)
    if not textsec: raise SystemExit("No executable .text-like section found")
    code=b[textsec["raw"]:textsec["raw"]+textsec["raw_size"]]
    md=Cs(CS_ARCH_X86,CS_MODE_32); md.detail=True
    ins=list(md.disasm(code,textsec["va"]))
    add(f"\nDISASSEMBLY: {textsec['name']} VA=0x{textsec['va']:08X} RAW=0x{textsec['raw']:X} SIZE=0x{textsec['raw_size']:X}; decoded instructions={len(ins)}")
    by_imm={}
    for i,x in enumerate(ins):
        for op in x.operands:
            if op.type==2: by_imm.setdefault(op.imm&0xFFFFFFFF,[]).append(i)
    targets={**KNOWN}
    for va,val in strings:
        if any(w.lower() in val.lower() for w in WORDS):
            targets.setdefault(va,"string: "+val)
    add("\nXREFS TO RENDER FUNCTIONS AND PARTICLE STRINGS:")
    for va,label in sorted(targets.items()):
        hits=by_imm.get(va,[])
        if not hits: continue
        add(f"\n  {label} @ 0x{va:08X}: {len(hits)} xrefs")
        for idx in hits[:80]:
            lo=max(0,idx-5); hi=min(len(ins),idx+7)
            for j in range(lo,hi):
                x=ins[j]; mark=">>" if j==idx else "  "
                add(f"    {mark} {x.address:08X}: {x.mnemonic:8s} {x.op_str}")
            add("    --")
    add("\nDIRECT CALLS TO KNOWN RENDER FUNCTIONS:")
    for x in ins:
        if x.mnemonic=="call" and x.operands and x.operands[0].type==2:
            dest=x.operands[0].imm&0xFFFFFFFF
            if dest in KNOWN: add(f"  {x.address:08X} -> {dest:08X} {KNOWN[dest]}")
    add("\nTOP INTERNAL DIRECT CALL TARGETS (frequency only; not function labels):")
    from collections import Counter
    calls=Counter(x.operands[0].imm&0xFFFFFFFF for x in ins if x.mnemonic=="call" and x.operands and x.operands[0].type==2 and textsec["va"] <= (x.operands[0].imm&0xFFFFFFFF) < textsec["va"]+textsec["vsize"])
    for va,n in calls.most_common(100): add(f"  {n:4d} 0x{va:08X}")
    OUT.write_text("\n".join(out)+"\n",encoding="utf-8")
    print("\n".join(out[:90]))
    print(f"\nFull report written to {OUT}; bytes={OUT.stat().st_size}")
if __name__=="__main__": main()
