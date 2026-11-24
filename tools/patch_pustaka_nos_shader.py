#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, struct, subprocess, sys, zipfile
from pathlib import Path

EXPECTED_APK = "222da4e42a2c14bba5adf44df1539964b9809a0a4f44c8b688f944503f8d49bc"
EXPECTED_SO = "9cea9cc3767d8cb0a72cad33a44edf68a66daecd75104ddd1032a17b55e9c906"
EXPECTED_SHADER_SHA = "3d9c6de0265acc9afe0865beed89a0a551da709405566def4f2ad63d400b6b82"
EXPECTED_CANDIDATE_SHA = "b23da2a3ed577be3da1c2af2382b9320759b10a1aef78a223411a842f383b173"
SHADER_VA = 0x53CF5E
SHADER_LEN = 2343
KSHADER_OBJECT = 0x1D5C0A0
MARKERS = ("d3d::DrawNosTrail", "streetlight::UpdateNosTrail", "streetlight::BuildNosTrail",
           "nosfx::History::Update", "nosfx::History::Mesh", "nosfx::kShader")

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout

def va_to_offset(elf: bytes, va: int, size: int) -> int:
    if elf[:4] != b"\x7fELF" or elf[4] != 2 or elf[5] != 1:
        raise SystemExit("libmain.so must be little-endian ELF64")
    hdr = struct.unpack_from("<16sHHIQQQIHHHHHH", elf, 0)
    machine, phoff, phentsize, phnum = hdr[2], hdr[5], hdr[9], hdr[10]
    if machine != 183:
        raise SystemExit("libmain.so is not AArch64")
    for i in range(phnum):
        p = struct.unpack_from("<IIQQQQQQ", elf, phoff + i * phentsize)
        p_type, p_offset, p_vaddr, p_filesz = p[0], p[2], p[3], p[5]
        if p_type == 1 and p_vaddr <= va and va + size <= p_vaddr + p_filesz:
            return p_offset + (va - p_vaddr)
    raise SystemExit(f"shader VA {va:#x} is not file-backed by a PT_LOAD segment")

def strip_signature(name: str) -> bool:
    u = name.upper()
    base = u.rsplit("/", 1)[-1]
    return u == "META-INF/MANIFEST.MF" or (
        u.startswith("META-INF/") and base.endswith((".SF", ".RSA", ".DSA", ".EC"))
    )

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: patch_pustaka_nos_shader.py ORIGINAL.apk CANDIDATE.hlsl PATCHED.apk")
    apk_path, candidate_path, out_path = map(Path, sys.argv[1:])
    apk_bytes = apk_path.read_bytes()
    if sha(apk_bytes) != EXPECTED_APK:
        raise SystemExit("Pustaka APK SHA-256 mismatch; refusing unknown binary")
    candidate = candidate_path.read_bytes()
    if candidate.endswith(b"\n"):
        candidate = candidate[:-1]
    if sha(candidate) != EXPECTED_CANDIDATE_SHA:
        raise SystemExit("Lightning shader source SHA-256 mismatch; refusing unreviewed candidate")
    if not candidate or len(candidate) > SHADER_LEN:
        raise SystemExit("Candidate shader is empty or exceeds original source slot")
    for marker in (b"ATTR0", b"ATTR1", b"SV_Position", b"TEXCOORD0", b"SV_Target", b"Output vs(", b"float4 ps("):
        if marker not in candidate:
            raise SystemExit(f"Candidate missing interface marker: {marker!r}")
    if any(x in candidate for x in (b"Texture2D", b"SamplerState", b"register(t", b"register(s")):
        raise SystemExit("Candidate adds a texture/sampler descriptor; refusing ABI change")

    with zipfile.ZipFile(apk_path) as src:
        bad = src.testzip()
        if bad:
            raise SystemExit("Source APK CRC failure: " + bad)
        names = [n for n in src.namelist() if not n.endswith("/") and not strip_signature(n)]
        if len(names) != len(set(names)):
            raise SystemExit("Source APK has duplicate ZIP entries")
        so_name = "lib/arm64-v8a/libmain.so"
        if so_name not in names:
            raise SystemExit("Pustaka ARM64 libmain.so missing")
        so = src.read(so_name)
        if sha(so) != EXPECTED_SO:
            raise SystemExit("Pustaka libmain.so SHA-256 mismatch")
        symbols = run("bash", "-lc", "readelf -Ws " + str(apk_path) + " 2>/dev/null") if False else ""
        # Verify the ELF symbol table and the relocation that binds kShader to the source string.
        tmp = out_path.with_suffix(".libmain.verify.so")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(so)
        symbol_text = run("bash", "-lc", "readelf -Ws " + str(tmp) + " | c++filt")
        for marker in MARKERS:
            if marker not in symbol_text:
                raise SystemExit("Required renderer symbol missing: " + marker)
        reloc = run("readelf", "-rW", str(tmp))
        rel = next((line.split() for line in reloc.splitlines()
                    if line.split() and line.split()[0].lower() == f"{KSHADER_OBJECT:016x}"), None)
        if not rel or len(rel) < 4 or rel[2] != "R_AARCH64_RELATIVE" or rel[-1].lower() != f"{SHADER_VA:x}":
            raise SystemExit(f"nosfx::kShader relocation mismatch: {rel}")
        offset = va_to_offset(so, SHADER_VA, SHADER_LEN + 1)
        end = so.find(b"\0", offset)
        original = so[offset:end]
        if len(original) != SHADER_LEN or sha(original) != EXPECTED_SHADER_SHA:
            raise SystemExit(f"Original NOS shader signature mismatch: len={len(original)} sha256={sha(original)}")
        patched_so = bytearray(so)
        replacement = candidate + b"\0" * (SHADER_LEN - len(candidate) + 1)
        patched_so[offset:offset + SHADER_LEN + 1] = replacement
        if patched_so[:offset] != so[:offset] or patched_so[offset + SHADER_LEN + 1:] != so[offset + SHADER_LEN + 1:]:
            raise SystemExit("Patch escaped the exact shader source range")
        if patched_so[offset:offset + len(candidate)] != candidate or patched_so[offset + len(candidate)] != 0:
            raise SystemExit("Patched shader bytes or NUL terminator mismatch")
        tmp.write_bytes(patched_so)
        run("readelf", "-h", str(tmp))
        symbol_after = run("bash", "-lc", "readelf -Ws " + str(tmp) + " | c++filt")
        for marker in MARKERS:
            if marker not in symbol_after:
                raise SystemExit("Patched ELF lost renderer symbol: " + marker)
        report = (
            f"original_apk_sha256={sha(apk_bytes)}\n"
            f"original_libmain_sha256={sha(so)}\n"
            f"patched_libmain_sha256={sha(bytes(patched_so))}\n"
            f"shader_virtual_address={SHADER_VA:#x}\n"
            f"shader_file_offset={offset:#x}\n"
            f"original_shader_bytes={len(original)}\n"
            f"candidate_shader_bytes={len(candidate)}\n"
            f"zero_padding_bytes={SHADER_LEN-len(candidate)}\n"
            f"changed_bytes_only_inside_shader_slot=true\n"
            f"all_required_renderer_symbols_preserved=true\n"
            f"new_texture_or_sampler_descriptors=false\n"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w") as dst:
            for name in names:
                info = src.getinfo(name)
                data = bytes(patched_so) if name == so_name else src.read(name)
                dst.writestr(info, data)
    with zipfile.ZipFile(out_path) as check, zipfile.ZipFile(apk_path) as src:
        if check.testzip():
            raise SystemExit("Patched APK ZIP CRC failure")
        for name in names:
            expected = bytes(patched_so) if name == so_name else src.read(name)
            if check.read(name) != expected:
                raise SystemExit("Patched APK entry verification failed: " + name)
    out_path.with_suffix(".patch-report.txt").write_text(report, encoding="utf-8")
    print(report, end="")
    print("PATCHED PUSTAKA APK:", out_path, "bytes:", out_path.stat().st_size)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
