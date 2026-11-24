#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, struct, sys, zipfile
from pathlib import Path

EXPECTED_APK = "222da4e42a2c14bba5adf44df1539964b9809a0a4f44c8b688f944503f8d49bc"
EXPECTED_SO = "9cea9cc3767d8cb0a72cad33a44edf68a66daecd75104ddd1032a17b55e9c906"
EXPECTED_SHADER_SHA = "3d9c6de0265acc9afe0865beed89a0a551da709405566def4f2ad63d400b6b82"
EXPECTED_CANDIDATE_SHA = "4a187539d3f23fa22a4803db0444317c9703842e15345e39dfd651aa3fc8cbd2"
SHADER_VA = 0x53CF5E
SHADER_LEN = 2343
KSHADER_OBJECT = 0x1D5C0A0
KSHADER_RELOC_TYPE = 1027
SYMBOLS = (
    "_ZN3d3d12DrawNosTrailEv",
    "_ZN11streetlight14UpdateNosTrailEjj",
    "_ZN11streetlight13BuildNosTrailERN3gpu5StateERNSt6__ndk16vectorIfNS3_9allocatorIfEEEE",
    "_ZN5nosfx7History6UpdateEdbN11streetlight3VecES2_",
    "_ZN5nosfx7History4MeshEdN11streetlight3VecERKNSt6__ndk15arrayIfLm16EEERNS3_6vectorIfNS3_9allocatorIfEEEE",
    "_ZN5nosfx7kShaderE",
)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def elf_layout(elf: bytes):
    if elf[:4] != b"\x7fELF" or elf[4] != 2 or elf[5] != 1:
        raise SystemExit("libmain.so must be little-endian ELF64")
    h = struct.unpack_from("<16sHHIQQQIHHHHHH", elf, 0)
    if h[2] != 183:
        raise SystemExit("libmain.so is not AArch64")
    return h

def va_to_offset(elf: bytes, va: int, size: int) -> int:
    h = elf_layout(elf)
    phoff, phentsize, phnum = h[5], h[9], h[10]
    for i in range(phnum):
        p = struct.unpack_from("<IIQQQQQQ", elf, phoff + i * phentsize)
        p_type, p_offset, p_vaddr, p_filesz = p[0], p[2], p[3], p[5]
        if p_type == 1 and p_vaddr <= va and va + size <= p_vaddr + p_filesz:
            return p_offset + (va - p_vaddr)
    raise SystemExit(f"shader VA {va:#x} is not file-backed by a PT_LOAD segment")

def elf_sections(elf: bytes):
    h = elf_layout(elf)
    shoff, shentsize, shnum = h[6], h[11], h[12]
    return [struct.unpack_from("<IIQQQQIIQQ", elf, shoff + i * shentsize) for i in range(shnum)]

def verify_symbols_and_relocation(elf: bytes):
    h = elf_layout(elf)
    sections = elf_sections(elf)
    found = set()
    for sec in sections:
        if sec[1] not in (2, 11):  # SHT_SYMTAB, SHT_DYNSYM
            continue
        link, off, size, entsize = sec[6], sec[4], sec[5], sec[9]
        if not entsize or link >= len(sections):
            continue
        st = sections[link]
        strings = elf[st[4]:st[4] + st[5]]
        for pos in range(off, off + size, entsize):
            name_off = struct.unpack_from("<I", elf, pos)[0]
            if name_off < len(strings):
                end = strings.find(b"\0", name_off)
                if end >= 0:
                    found.add(strings[name_off:end].decode("ascii", "replace"))
    missing = [s for s in SYMBOLS if s not in found]
    if missing:
        raise SystemExit("Required NOS renderer ELF symbols missing: " + ", ".join(missing))
    relocation_ok = False
    for sec in sections:
        if sec[1] != 4:  # SHT_RELA
            continue
        off, size, entsize = sec[4], sec[5], sec[9]
        if not entsize:
            continue
        for pos in range(off, off + size, entsize):
            r_offset, r_info, addend = struct.unpack_from("<QQq", elf, pos)
            if r_offset == KSHADER_OBJECT:
                relocation_ok = (r_info & 0xffffffff) == KSHADER_RELOC_TYPE and addend == SHADER_VA
                break
    if not relocation_ok:
        raise SystemExit("nosfx::kShader relocation no longer targets the verified shader source")

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
    candidate = candidate_path.read_bytes().replace(bytes([13, 10]), bytes([10]))
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
        verify_symbols_and_relocation(so)
        offset = va_to_offset(so, SHADER_VA, SHADER_LEN + 1)
        end = so.find(b"\0", offset)
        original = so[offset:end]
        if len(original) != SHADER_LEN or sha(original) != EXPECTED_SHADER_SHA:
            raise SystemExit(f"Original NOS shader signature mismatch: len={len(original)} sha256={sha(original)}")
        patched_so = bytearray(so)
        patched_so[offset:offset + SHADER_LEN + 1] = candidate + b"\0" * (SHADER_LEN - len(candidate) + 1)
        if patched_so[:offset] != so[:offset] or patched_so[offset + SHADER_LEN + 1:] != so[offset + SHADER_LEN + 1:]:
            raise SystemExit("Patch escaped the exact shader source range")
        if patched_so[offset:offset + len(candidate)] != candidate or patched_so[offset + len(candidate)] != 0:
            raise SystemExit("Patched shader bytes or NUL terminator mismatch")
        verify_symbols_and_relocation(bytes(patched_so))
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
            f"kShader_relocation_preserved=true\n"
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
    Path(str(out_path) + ".patch-report.txt").write_text(report, encoding="utf-8")
    print(report, end="")
    print("PATCHED PUSTAKA APK:", out_path, "bytes:", out_path.stat().st_size)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
