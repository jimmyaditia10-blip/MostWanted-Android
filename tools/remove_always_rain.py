#!/usr/bin/env python3
from __future__ import annotations
import hashlib, struct, sys, zipfile
from pathlib import Path

APK_LIB = "lib/arm64-v8a/libmain.so"
SYMBOL = b"_Z17AlwaysRainWeatherR10X86ContextPh"
SYMBOL_VA = 0x919E60
SYMBOL_SIZE = 1048
RET = bytes.fromhex("c0035fd6")
NOP = bytes.fromhex("1f2003d5")

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def elf_sections(elf: bytes):
    if elf[:4] != b"\x7fELF" or elf[4] != 2 or elf[5] != 1:
        raise SystemExit("libmain.so must be little-endian ELF64")
    h = struct.unpack_from("<16sHHIQQQIHHHHHH", elf, 0)
    if h[2] != 183:
        raise SystemExit("libmain.so is not AArch64")
    shoff, shentsize, shnum = h[6], h[11], h[12]
    sections = [struct.unpack_from("<IIQQQQIIQQ", elf, shoff+i*shentsize) for i in range(shnum)]
    return h, sections

def verify_symbol(elf: bytes):
    h, sections = elf_sections(elf)
    matches = []
    for sec in sections:
        if sec[1] not in (2, 11):
            continue
        strings_sec = sections[sec[6]]
        strings = elf[strings_sec[4]:strings_sec[4]+strings_sec[5]]
        for pos in range(sec[4], sec[4]+sec[5], sec[9]):
            name_off = struct.unpack_from("<I", elf, pos)[0]
            if name_off >= len(strings):
                continue
            end = strings.find(b"\0", name_off)
            if end < 0 or strings[name_off:end] != SYMBOL:
                continue
            st = struct.unpack_from("<IBBHQQ", elf, pos)
            matches.append((st[4], st[5]))
    if len(matches) != 1 or matches[0] != (SYMBOL_VA, SYMBOL_SIZE):
        raise SystemExit(f"AlwaysRainWeather symbol mismatch: {matches!r}")
    return h, sections

def va_to_offset(elf: bytes, h, va: int, size: int):
    phoff, phentsize, phnum = h[5], h[9], h[10]
    for i in range(phnum):
        p = struct.unpack_from("<IIQQQQQQ", elf, phoff+i*phentsize)
        typ, off, vaddr, filesz = p[0], p[2], p[3], p[5]
        if typ == 1 and vaddr <= va and va+size <= vaddr+filesz:
            return off+(va-vaddr)
    raise SystemExit("AlwaysRainWeather function is not file-backed")

def verify_no_direct_references(elf: bytes, h, sections):
    # Reject direct AArch64 BL calls and dynamic relocations to the function.
    phoff, phentsize, phnum = h[5], h[9], h[10]
    executable = []
    for i in range(phnum):
        p = struct.unpack_from("<IIQQQQQQ", elf, phoff+i*phentsize)
        if p[0] == 1 and (p[1] & 1):
            executable.append((p[2], p[2]+p[5]))
    calls = []
    for start, end in executable:
        for off in range(start, end-3, 4):
            ins = struct.unpack_from("<I", elf, off)[0]
            if ins & 0xFC000000 == 0x94000000:
                imm = ins & 0x03FFFFFF
                if imm & (1 << 25):
                    imm -= 1 << 26
                if off+(imm << 2) == SYMBOL_VA:
                    calls.append(off)
    if calls:
        raise SystemExit("Direct BL references to AlwaysRainWeather remain: "+", ".join(hex(x) for x in calls))
    relocations = []
    for sec in sections:
        if sec[1] not in (4, 9):
            continue
        for pos in range(sec[4], sec[4]+sec[5], sec[9]):
            if sec[1] == 4:
                ro, ri, add = struct.unpack_from("<QQq", elf, pos)
                if add == SYMBOL_VA or ro == SYMBOL_VA:
                    relocations.append((ro, add))
            else:
                ro, ri = struct.unpack_from("<QQ", elf, pos)
                if ro == SYMBOL_VA:
                    relocations.append((ro, None))
    if relocations:
        raise SystemExit("Dynamic relocation references AlwaysRainWeather: "+repr(relocations))

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: remove_always_rain.py INPUT.apk OUTPUT.apk")
    src, dst = map(Path, sys.argv[1:])
    with zipfile.ZipFile(src, "r") as zin:
        bad = zin.testzip()
        if bad:
            raise SystemExit("Input APK ZIP CRC failure: "+bad)
        names = [n for n in zin.namelist() if not n.endswith("/")]
        if APK_LIB not in names:
            raise SystemExit("arm64 libmain.so missing")
        lib = bytearray(zin.read(APK_LIB))
        h, sections = verify_symbol(bytes(lib))
        verify_no_direct_references(bytes(lib), h, sections)
        off = va_to_offset(bytes(lib), h, SYMBOL_VA, SYMBOL_SIZE)
        before = bytes(lib)
        original = before[off:off+SYMBOL_SIZE]
        if original == RET + NOP*(SYMBOL_SIZE//4-1):
            raise SystemExit("AlwaysRainWeather implementation already erased")
        # Preserve the exported entry as a compatibility return stub; erase every
        # instruction/data byte in its dedicated function body after the entry.
        lib[off:off+SYMBOL_SIZE] = RET + NOP*(SYMBOL_SIZE//4-1)
        changed = [i for i,(a,b) in enumerate(zip(before,lib)) if a != b]
        if not changed or changed[0] != off or changed[-1] >= off+SYMBOL_SIZE:
            raise SystemExit("Unexpected AlwaysRainWeather patch range")
        if bytes(lib[off:off+SYMBOL_SIZE]) != RET + NOP*(SYMBOL_SIZE//4-1):
            raise SystemExit("AlwaysRainWeather body was not fully cleared")
        for name in names:
            pass
        entries, infos = {}, {}
        for name in names:
            entries[name] = bytes(lib) if name == APK_LIB else zin.read(name)
            infos[name] = zin.getinfo(name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w") as zout:
        for name, data in entries.items():
            zout.writestr(infos[name], data)
    with zipfile.ZipFile(dst, "r") as check:
        if check.testzip():
            raise SystemExit("Output APK ZIP CRC check failed")
        out = check.read(APK_LIB)
        if out[off:off+SYMBOL_SIZE] != RET + NOP*(SYMBOL_SIZE//4-1):
            raise SystemExit("AlwaysRainWeather body not erased in output")
        if out[:off] != before[:off] or out[off+SYMBOL_SIZE:] != before[off+SYMBOL_SIZE:]:
            raise SystemExit("Native bytes outside AlwaysRainWeather function changed")
        for name in names:
            if name != APK_LIB and check.read(name) != entries[name]:
                raise SystemExit("Non-native APK entry changed: "+name)
    print("AlwaysRainWeather implementation erased: 1048-byte function body replaced with RET + AArch64 NOPs")
    print("Exported symbol retained as a safe compatibility stub; unrelated symbols and features preserved")
    print("Direct BL references: 0; dynamic relocations to function: 0")
    print("Changed native bytes:", len(changed), "within", hex(SYMBOL_VA), "-", hex(SYMBOL_VA+SYMBOL_SIZE))
    print("Patched library SHA-256:", sha256(bytes(lib)))
    print("Output APK bytes:", dst.stat().st_size)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
