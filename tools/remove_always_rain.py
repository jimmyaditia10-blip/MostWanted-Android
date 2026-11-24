#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, struct, sys, zipfile
from pathlib import Path

APK_LIB = "lib/arm64-v8a/libmain.so"
SYMBOL = b"_Z17AlwaysRainWeatherR10X86ContextPh"
SYMBOL_VA = 0x919E60
SYMBOL_SIZE = 1048
ORIGINAL_PROLOGUE = bytes.fromhex("fd7bbda9")
RET = bytes.fromhex("c0035fd6")

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: remove_always_rain.py INPUT.apk OUTPUT.apk")
    src, dst = map(Path, sys.argv[1:])
    with zipfile.ZipFile(src, "r") as zin:
        names = [n for n in zin.namelist() if not n.endswith("/")]
        if APK_LIB not in names:
            raise SystemExit("arm64 libmain.so missing")
        lib = bytearray(zin.read(APK_LIB))
        if SYMBOL not in lib:
            raise SystemExit("dedicated AlwaysRainWeather symbol missing; refusing unsafe patch")
        off = SYMBOL_VA  # verified PT_LOAD maps VA 0x919e60 to file offset 0x919e60
        if off + SYMBOL_SIZE > len(lib):
            raise SystemExit("AlwaysRainWeather function range outside library")
        if bytes(lib[off:off+4]) == RET:
            raise SystemExit("AlwaysRainWeather is already disabled")
        if bytes(lib[off:off+4]) != ORIGINAL_PROLOGUE:
            raise SystemExit("unexpected AlwaysRainWeather prologue; refusing to patch a different binary")
        before = bytes(lib)
        lib[off:off+4] = RET
        changed = [i for i,(a,b) in enumerate(zip(before,lib)) if a != b]
        if changed != list(range(off,off+4)):
            raise SystemExit("patch changed bytes outside the function entry")
        entries = {}
        infos = {}
        for name in names:
            info = zin.getinfo(name)
            data = bytes(lib) if name == APK_LIB else zin.read(name)
            entries[name], infos[name] = data, info
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w") as zout:
        for name, data in entries.items():
            zout.writestr(infos[name], data)
    with zipfile.ZipFile(dst, "r") as check:
        if check.testzip():
            raise SystemExit("output APK ZIP CRC check failed")
        out = check.read(APK_LIB)
        if out[off:off+4] != RET:
            raise SystemExit("AlwaysRainWeather return patch not present in output")
        if SYMBOL not in out:
            raise SystemExit("AlwaysRainWeather symbol unexpectedly lost")
    print("AlwaysRainWeather disabled: entry replaced with AArch64 RET")
    print("Patched library SHA-256:", sha256(bytes(lib)))
    print("Changed native bytes:", len(changed), "at", hex(off))
    print("No other native bytes changed")
    print("Output APK bytes:", dst.stat().st_size)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
