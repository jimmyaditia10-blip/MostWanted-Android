#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, sys, zipfile
from pathlib import Path

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
def signed_metadata(name: str) -> bool:
    upper = name.upper()
    base = upper.rsplit("/", 1)[-1]
    return upper == "META-INF/MANIFEST.MF" or (
        upper.startswith("META-INF/") and base.endswith((".SF", ".RSA", ".DSA", ".EC"))
    )
def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
def entries(z: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    result = {}
    for info in z.infolist():
        if info.is_dir() or signed_metadata(info.filename):
            continue
        if info.filename in result:
            raise SystemExit(f"duplicate ZIP entry: {info.filename}")
        result[info.filename] = info
    return result
def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_pustaka_payload.py PUSTAKA.apk FINAL.apk")
    source_path, final_path = map(Path, sys.argv[1:])
    with zipfile.ZipFile(source_path) as source, zipfile.ZipFile(final_path) as final:
        src, dst = entries(source), entries(final)
        missing = sorted(set(src) - set(dst))
        if missing:
            raise SystemExit("FINAL APK MISSING PUSTAKA ENTRIES: " + ", ".join(missing[:40]))
        changed = [n for n in sorted(src) if digest(source.read(n)) != digest(final.read(n))]
        if changed:
            raise SystemExit("FINAL APK PUSTAKA CONTENT MISMATCH: " + ", ".join(changed[:40]))
        dex = b"".join(final.read(n) for n in sorted(dst) if re.fullmatch(r"classes\d*\.dex", n))
        native = final.read("lib/arm64-v8a/libmain.so")
        missing_dex = [m.decode("ascii", "replace") for m in DEX_MARKERS if m not in dex]
        missing_native = [m.decode("ascii", "replace") for m in NATIVE_MARKERS if m not in native]
        if missing_dex:
            raise SystemExit("FINAL APK DEX MARKERS MISSING: " + ", ".join(missing_dex))
        if missing_native:
            raise SystemExit("FINAL APK NATIVE MARKERS MISSING: " + ", ".join(missing_native))
        bad = final.testzip()
        if bad:
            raise SystemExit("FINAL APK CRC FAILURE: " + bad)
        for n in dst:
            if n.startswith("lib/") and n.endswith(".so") and final.getinfo(n).compress_type != zipfile.ZIP_STORED:
                raise SystemExit("FINAL APK NATIVE LIBRARY COMPRESSED: " + n)
        print("FINAL APK PUSTAKA PAYLOAD VERIFIED")
        print("Pustaka entries byte-identical:", len(src))
        print("DEX markers verified:", len(DEX_MARKERS))
        print("Native markers verified:", len(NATIVE_MARKERS))
        print("Final APK SHA-256:", digest(final_path.read_bytes()))
        print("Final APK bytes:", final_path.stat().st_size)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
