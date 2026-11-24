#!/usr/bin/env python3
"""Read-only AArch64 audit of the verified Pustaka NOS trail implementation."""
import hashlib
import struct
import sys
from pathlib import Path

from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN

TARGETS = (
    "DrawNosTrail",
    "History4Mesh",
    "History6Update",
    "History5Prune",
    "History5Clear",
    "HistoryD2",
    "kShader",
    "UpdateNosTrail",
    "BeginVehicleLights",
    "IncludeBodyMarker",
    "ValidPose",
    "VehicleLightReady",
    "SeedSources",
    "CaptureDraw",
    "RelativeProjection",
    "DrawPanel",
    "Compile",
    "streetlight",
    "vehiclelighting",
    "PixelSource",
    "FillViewport",
    "VulkanBackend4Draw",
    "d3d",
    "Renderer",
    "Backend",
)

def hx(v):
    return f"0x{v:016X}"

def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/pustaka-libmain.so")
    raw = path.read_bytes()
    print(f"FILE {path} size={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    with path.open("rb") as f:
        elf = ELFFile(f)
        print(f"ELF class={elf.elfclass} endian={elf.little_endian} machine={elf['e_machine']}")
        sections = []
        for sec in elf.iter_sections():
            if sec['sh_size']:
                sections.append((sec.name, int(sec['sh_addr']), int(sec['sh_offset']),
                                 int(sec['sh_size']), sec.data()))
        symtab = elf.get_section_by_name(".symtab")
        if symtab is None:
            symtab = elf.get_section_by_name(".dynsym")
        if symtab is None:
            print("NO_SYMBOL_TABLE")
            return
        symbols = []
        for sym in symtab.iter_symbols():
            name = sym.name or ""
            if any(k in name.lower() for k in ("nosfx", "drawnostrail", "streetlight", "vehiclelighting", "vkshader", "vulkanbackend", "pixelshader", "vertexshader", "gpu::backend", "d3d", "renderer", "backend")):
                symbols.append((name, int(sym['st_value']), int(sym['st_size']),
                                sym['st_info']['type'], sym['st_shndx']))
        symbols.sort(key=lambda x: (x[1], x[0]))
        print("\n=== NOSFX SYMBOLS ===")
        for name, addr, size, typ, shndx in symbols:
            print(f"{hx(addr)} size=0x{size:X} type={typ} shndx={shndx} {name}")

        def section_for(addr):
            for name, va, off, size, data in sections:
                if va <= addr < va + size:
                    return name, va, off, size, data
            return None

        target_symbols = []
        for name, addr, size, typ, shndx in symbols:
            if any(key.lower() in name.lower() for key in TARGETS):
                target_symbols.append((name, addr, size))
        target_addrs = {addr: name for name, addr, size in target_symbols}

        # AArch64 BL immediate scan for direct callers, without disassembling the whole .text.
        text_sections = [s for s in sections if "text" in s[0].lower()]
        callers = {addr: [] for addr in target_addrs}
        for secname, va, off, size, data in text_sections:
            end = len(data) - (len(data) % 4)
            for pos in range(0, end, 4):
                word = struct.unpack_from("<I", data, pos)[0]
                if (word & 0xFC000000) != 0x94000000:
                    continue
                imm26 = word & 0x03FFFFFF
                if imm26 & 0x02000000:
                    imm26 -= 0x04000000
                target = va + pos + (imm26 << 2)
                if target in callers:
                    callers[target].append((va + pos, secname))

        md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        print("\n=== TARGET FUNCTION DISASSEMBLY ===")
        for name, addr, size in target_symbols:
            sec = section_for(addr)
            if sec is None:
                print(f"\n{ name } {hx(addr)}: no containing section")
                continue
            secname, va, off, secsize, data = sec
            length = size if size else 0x800
            length = min(max(length, 0x40), 0x5000, va + secsize - addr)
            code = data[addr - va:addr - va + length]
            print(f"\n--- {name} {hx(addr)} size=0x{size:X} section={secname} disasm=0x{length:X} ---")
            for ins in md.disasm(code, addr):
                print(f"{ins.address:016X}: {ins.mnemonic:8s} {ins.op_str}")
            for caller, csec in callers.get(addr, []):
                print(f"CALLER {hx(caller)} section={csec}")

        print("\n=== SHADER / TRAIL STRING CONTEXT ===")
        needles = (b"coreLight", b"glowLight", b"sampler", b"texture", b"NOS", b"lightning")
        for secname, va, off, size, data in sections:
            if "rodata" not in secname.lower() and "data" not in secname.lower():
                continue
            for needle in needles:
                start = 0
                while True:
                    pos = data.find(needle, start)
                    if pos < 0:
                        break
                    lo = max(0, pos - 160)
                    hi = min(len(data), pos + 480)
                    excerpt = data[lo:hi].split(b"\0", 1)[0]
                    print(f"{secname} VA={hx(va+pos)} needle={needle.decode(errors='ignore')} excerpt={excerpt.decode('utf-8','replace')!r}")
                    start = pos + 1

        print("\n=== kShader OBJECT BYTES ===")
        for name, addr, size in target_symbols:
            if "kShader" not in name:
                continue
            sec = section_for(addr)
            if sec:
                secname, va, off, secsize, data = sec
                blob = data[addr-va:addr-va+min(size, 4096)]
                print(f"{name} {hx(addr)} size={size} section={secname} bytes={blob[:256].hex(' ')}")
                print(blob.decode("utf-8", "replace"))


        print("\\n=== FULL NOSFX SHADER SOURCE ===")
        for secname, va, off, size, data in sections:
            if "rodata" not in secname.lower() and "data" not in secname.lower():
                continue
            for needle in (b"coreLight", b"glowLight"):
                start = 0
                while True:
                    pos = data.find(needle, start)
                    if pos < 0:
                        break
                    lo = pos
                    hi = pos
                    allowed = set(range(32, 127)) | {9, 10, 13}
                    while lo > 0 and data[lo - 1] in allowed:
                        lo -= 1
                    while hi < len(data) and data[hi] in allowed:
                        hi += 1
                    blob = data[lo:hi]
                    if b"coreLight" in blob or b"glowLight" in blob:
                        print(f"\\n--- {secname} VA={hx(va+lo)} bytes={len(blob)} ---")
                        print(blob.decode("utf-8", "replace"))
                    start = pos + len(needle)

        print("\\n=== NOSFX / STREETLIGHT / RENDER RELATED SYMBOLS ===")
        shown = 0
        for sym in symtab.iter_symbols():
            name = sym.name or ""
            low = name.lower()
            if any(k in low for k in ("nosfx", "streetlight", "drawnostrail", "texturepack", "shader", "trail")):
                print(f"{hx(int(sym['st_value']))} size=0x{int(sym['st_size']):X} {name}")
                shown += 1
                if shown >= 240:
                    print("... symbol list capped at 240")
                    break

        print("\\n=== DrawNosTrail FOLLOW-ON HELPER ===")
        helper = 0x0000000000910AD8
        sec = section_for(helper)
        if sec:
            secname, va, off, secsize, data = sec
            length = min(0x600, va + secsize - helper)
            print(f"helper={hx(helper)} section={secname} bytes={length}")
            for ins in md.disasm(data[helper-va:helper-va+length], helper):
                print(f"{ins.address:016X}: {ins.mnemonic:8s} {ins.op_str}")


        print("\\n=== TRAIL ANCHOR GLOBAL XREFS ===")
        for secname, va, off, size, data in text_sections:
            instructions = list(md.disasm(data, va))
            for i, ins in enumerate(instructions):
                if ins.mnemonic != "adrp" or "#0x1d7d000" not in ins.op_str:
                    continue
                window = instructions[i:min(i+10, len(instructions))]
                if any("#0xd08" in x.op_str or "#0xd68" in x.op_str for x in window):
                    print(f"\\n--- {secname} around {hx(ins.address)} ---")
                    for x in window:
                        print(f"{x.address:016X}: {x.mnemonic:8s} {x.op_str}")

        print("\\n=== LOCAL HELPER CALLED BY BeginVehicleLights ===")
        helper = 0x0000000000984FF0
        sec = section_for(helper)
        if sec:
            secname, va, off, secsize, data = sec
            length = min(0x500, va + secsize - helper)
            print(f"helper={hx(helper)} section={secname} bytes={length}")
            for ins in md.disasm(data[helper-va:helper-va+length], helper):
                print(f"{ins.address:016X}: {ins.mnemonic:8s} {ins.op_str}")

        print("\\n=== NAMED SYMBOLS NEAR TRAIL GLOBALS ===")
        for sym in symtab.iter_symbols():
            addr = int(sym["st_value"])
            if (0x1CFE000 <= addr < 0x1CFF000) or (0x1D7D000 <= addr < 0x1D7E000):
                if sym.name:
                    print(f"{hx(addr)} size=0x{int(sym['st_size']):X} {sym.name}")


        print("\\n=== NOSFX GLOBAL / SHADER / RENDERER XREFS ===")
        pages = {
            0x1D5C000: {0xA0, 0xA8},
            0x1D610000: {0x680, 0x688},
            0x1D450000: {0xA48, 0xA58},
            0x1D430000: {0x4F0, 0x2548, 0x2550},
            0x1D7D000: {0xD08, 0xD68},
            0x053C000: {0xF5E},
        }
        for secname, va, off, size, data in text_sections:
            insns = list(md.disasm(data, va))
            for i, ins in enumerate(insns):
                if ins.mnemonic != "adrp":
                    continue
                target_page = None
                try:
                    target_page = int(ins.op_str.split("#")[-1], 16)
                except Exception:
                    pass
                if target_page not in pages:
                    continue
                window = insns[i:min(i+8, len(insns))]
                if not any(any(f"#{off:x}" in x.op_str for off in pages[target_page]) for x in window[1:]):
                    continue
                print(f"\\n--- {secname} {hx(ins.address)} page={hx(target_page)} ---")
                for x in window:
                    print(f"{x.address:016X}: {x.mnemonic:8s} {x.op_str}")

        print("\\n=== NOSFX GLOBAL OBJECT SYMBOLS ===")
        for sym in symtab.iter_symbols():
            name = sym.name or ""
            if any(k in name.lower() for k in ("kshader", "drawnostrail", "d3d", "renderer", "backend", "pixelshader")):
                print(f"{hx(int(sym['st_value']))} size=0x{int(sym['st_size']):X} type={sym['st_info']['type']} {name}")

if __name__ == "__main__":
    main()
