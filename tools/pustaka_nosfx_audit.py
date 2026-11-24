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
            if "nosfx" in name.lower() or "drawnostrail" in name.lower():
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

if __name__ == "__main__":
    main()
