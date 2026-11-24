#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, sys, zipfile
from pathlib import Path

PACKAGE = "com.racas.mostwanted"
DEX_MARKERS = (
    b"Lcom/racas/mostwanted/ModsActivity;",
    b"Lcom/racas/mostwanted/ModArchive;",
    b"Lcom/racas/mostwanted/ModInstaller;",
    b"Lcom/racas/mostwanted/CarConverter;",
    b"Lcom/racas/mostwanted/TexturePacks;",
    b"Lcom/racas/mostwanted/ModTransaction;",
    b"Lcom/racas/mostwanted/FlipCar58;",
    b"Lcom/racas/mostwanted/CarScript;",
    b"Lcom/racas/mostwanted/BinaryNeon65;",
    b"Lcom/racas/mostwanted/NeonPack65;",
    b"flipcar58.nfsms",
)
NATIVE_MARKERS = (
    b"DrawNosTrail", b"BuildNosTrail", b"UpdateNosTrail",
    b"CUSTOM NOS TRAIL", b"_ZN7thunder10InitializeEv",
)
SIGNATURE_SUFFIXES = (".SF", ".RSA", ".DSA", ".EC")

def is_signature(name: str) -> bool:
    upper = name.upper()
    base = upper.rsplit("/", 1)[-1]
    return upper == "META-INF/MANIFEST.MF" or (
        upper.startswith("META-INF/") and base.endswith(SIGNATURE_SUFFIXES)
    )

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def is_base_entry_replaced(name: str) -> bool:
    return (
        name == "resources.arsc"
        or bool(re.fullmatch(r"classes\d*\.dex", name))
        or name == "AndroidManifest.xml"
    )

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: integrate_pustaka_apk.py BASE.apk PUSTAKA.apk OUTPUT.apk")
    base_path, source_path, output_path = map(Path, sys.argv[1:])
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(base_path) as base:
        source_names = [n for n in source.namelist() if not n.endswith("/") and not is_signature(n)]
        source_set = set(source_names)
        if len(source_names) != len(source_set):
            raise SystemExit("Pustaka APK contains duplicate ZIP entries")
        required = {"AndroidManifest.xml", "resources.arsc", "classes.dex",
                    "lib/arm64-v8a/libmain.so"}
        missing = sorted(required - source_set)
        if missing:
            raise SystemExit("Pustaka payload incomplete: " + ", ".join(missing))
        dex_names = sorted(n for n in source_set if re.fullmatch(r"classes\d*\.dex", n))
        native_names = sorted(n for n in source_set if n.startswith("lib/") and n.endswith(".so"))
        if not dex_names or not native_names:
            raise SystemExit("Pustaka DEX or native library set is empty")
        all_dex = b"".join(source.read(n) for n in dex_names)
        native = source.read("lib/arm64-v8a/libmain.so")
        for marker in DEX_MARKERS:
            if marker not in all_dex:
                raise SystemExit("Pustaka Mod Loader/runtime DEX marker missing: " + repr(marker))
        for marker in NATIVE_MARKERS:
            if marker not in native:
                raise SystemExit("Pustaka native marker missing: " + repr(marker))
        manifest = source.read("AndroidManifest.xml")
        if PACKAGE.encode() not in manifest and PACKAGE.encode("utf-16le") not in manifest:
            raise SystemExit("Pustaka package id mismatch")
        # AndroidManifest.xml is compiled binary XML. Attribute strings may be
        # stored as short/long UTF-8 or UTF-16LE entries, and activity names
        # are commonly package-relative (".ModsActivity") rather than fully
        # qualified. The DEX descriptor check above verifies the actual class.
        def axml_has(value: str) -> bool:
            return value.encode("utf-8") in manifest or value.encode("utf-16le") in manifest
        if not axml_has("ModsActivity"):
            raise SystemExit("Pustaka manifest has no ModsActivity declaration")
        if not axml_has("MANAGE_EXTERNAL_STORAGE"):
            raise SystemExit("Pustaka manifest has no all-files storage permission")

        merged: dict[str, bytes] = {}
        merged_info: dict[str, zipfile.ZipInfo] = {}
        base_names = [n for n in base.namelist() if not n.endswith("/") and not is_signature(n)]
        if len(base_names) != len(set(base_names)):
            raise SystemExit("Base APK contains duplicate ZIP entries")
        for name in base_names:
            if not is_base_entry_replaced(name):
                merged[name] = base.read(name)
                merged_info[name] = base.getinfo(name)
        # Keep the complete tested Pustaka runtime together, while retaining the
        # original ZIP compression method of every entry (especially native .so).
        for name in source_names:
            info = source.getinfo(name)
            if name.startswith("lib/") and name.endswith(".so") and info.compress_type != zipfile.ZIP_STORED:
                raise SystemExit("Pustaka native library is compressed; refusing unsafe APK merge: " + name)
            merged[name] = source.read(name)
            merged_info[name] = info

        base_only = {n for n in base_names if not is_base_entry_replaced(n) and n not in source_set}
        for name in base_only:
            if name not in merged:
                raise SystemExit("Base-only asset lost during merge: " + name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w") as out:
        for name in sorted(merged):
            info = merged_info[name]
            out.writestr(info, merged[name])

    with zipfile.ZipFile(output_path) as check:
        out_names = check.namelist()
        if len(out_names) != len(set(out_names)):
            raise SystemExit("Merged APK contains duplicate ZIP entries")
        bad = check.testzip()
        if bad:
            raise SystemExit("Merged APK CRC failure: " + bad)
        out_set = set(out_names)
        missing_source = sorted(source_set - out_set)
        if missing_source:
            raise SystemExit("Merged APK dropped Pustaka entries: " + ", ".join(missing_source[:30]))
        if any(is_signature(n) for n in out_set):
            raise SystemExit("stale APK signing metadata remains")
        for name in source_names:
            if sha256(check.read(name)) != sha256(merged[name]):
                raise SystemExit("Pustaka entry changed after merge: " + name)
        for name in base_only:
            if sha256(check.read(name)) != sha256(merged[name]):
                raise SystemExit("Base game asset changed after merge: " + name)
        for name in native_names:
            if check.getinfo(name).compress_type != zipfile.ZIP_STORED:
                raise SystemExit("native library compression changed: " + name)

    print("Pustaka entries integrated:", len(source_names))
    print("Pustaka Mod Loader DEX markers: all present")
    print("Pustaka DEX files:", len(dex_names))
    print("Pustaka native libraries (stored):", len(native_names))
    print("Base-only assets preserved:", len(base_only))
    print("Pustaka SHA-256:", sha256(source_path.read_bytes()))
    print("Merged APK bytes:", output_path.stat().st_size)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
