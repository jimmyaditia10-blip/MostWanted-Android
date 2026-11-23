#!/usr/bin/env python3
"""Find Xbox XBE code references related to the aerodynamic contrail/wind path.

Usage:
  python tools/xbe_contrail_xrefs.py ~/MostWanted-XBE/default.xbe

This is a discovery aid, not an address patcher. It deliberately reports Xbox
addresses only; never copy PC XenonEffects addresses into the Xbox XBE.
"""
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

XBE_BASE = 0x00010000
TEXT_RAW = 0x1000
TEXT_VA = 0x11000
TEXT_SIZE = 0x3604D4

# String VAs verified in this XBE during the earlier string census.
TARGETS = {
    "CarRenderConn": 0x003E2818,
    "Velocity": 0x003DEC84,
    "EmitterPositionSlotPool": 0x003DEC13,
    "EmitterSlotPool": 0x003D32C8,
    "EmitterGroupSlotPool": 0x003D32D8,
    "ParticleSlotPool": 0x003D32B4,
}

def main():
    path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path("~/MostWanted-XBE/default.xbe").expanduser()
    data = path.read_bytes()
    if data[:4] != b"XBEH":
        raise SystemExit(f"Not an XBEH image: {path}")
    if len(data) < TEXT_RAW + TEXT_SIZE:
        raise SystemExit("XBE is shorter than the known .text section")

    code = data[TEXT_RAW:TEXT_RAW + TEXT_SIZE]
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    instructions = list(md.disasm(code, TEXT_VA))

    refs = {name: [] for name in TARGETS}
    for i, ins in enumerate(instructions):
        for op in ins.operands:
            if op.type == 2:  # X86_OP_IMM
                value = op.imm & 0xFFFFFFFF
                for name, va in TARGETS.items():
                    if value == va:
                        refs[name].append(i)

    print(f"XBE: {path}")
    print(f".text VA={TEXT_VA:#x} raw={TEXT_RAW:#x} size={TEXT_SIZE:#x}")
    for name, indices in refs.items():
        print(f"\n=== {name} ({TARGETS[name]:#010x}) : {len(indices)} immediate xrefs ===")
        for idx in indices:
            lo, hi = max(0, idx - 8), min(len(instructions), idx + 13)
            for j in range(lo, hi):
                ins = instructions[j]
                mark = ">>" if j == idx else "  "
                print(f"{mark} {ins.address:08X}: {ins.mnemonic:8s} {ins.op_str}")
            print("--")

    # Show all direct CALL targets in the neighborhoods, so likely owning
    # routines can be followed in the next disassembly pass.
    print("\n=== CALL targets near the discovered references ===")
    for name, indices in refs.items():
        for idx in indices:
            lo, hi = max(0, idx - 24), min(len(instructions), idx + 25)
            calls = [(ins.address, ins.operands[0].imm & 0xFFFFFFFF)
                     for ins in instructions[lo:hi]
                     if ins.mnemonic == "call" and ins.operands and ins.operands[0].type == 2]
            if calls:
                print(name, "xref", hex(instructions[idx].address),
                      "calls", ", ".join(f"{a:#x}->{t:#x}" for a, t in calls))


    # Search every section, including .rdata/.data, for literal VA pointers.
    # The game often reaches named pools through pointer tables rather than code immediates.
    print("\\n=== RAW IMAGE POINTER REFERENCES (all sections) ===")
    for name, va in TARGETS.items():
        needle = struct.pack("<I", va)
        hits = []
        start = 0
        while True:
            off = data.find(needle, start)
            if off < 0:
                break
            hits.append(off)
            start = off + 1
        print(f"{name} VA={va:#010x}: {len(hits)} raw references")
        for off in hits[:80]:
            print(f"  file+0x{off:06X}")

if __name__ == "__main__":
    main()
