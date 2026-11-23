#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, sys, zipfile
from pathlib import Path

REQUIRED = {
    "AndroidManifest.xml", "classes.dex", "resources.arsc",
    "lib/arm64-v8a/libmain.so",
    "assets/thunder/thunder0.wav", "assets/thunder/thunder1.wav",
    "assets/thunder/thunder2.wav", "assets/thunder/thunder3.wav",
}
DEX_MARKERS = (
    b"Lcom/racas/mostwanted/FlipCar58;",
    b"Lcom/racas/mostwanted/ModTransaction;",
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

def signature_entry(name: str) -> bool:
    upper = name.upper()
    base = upper.rsplit("/", 1)[-1]
    return upper == "META-INF/MANIFEST.MF" or (
        upper.startswith("META-INF/") and base.endswith(SIGNATURE_SUFFIXES)
    )

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: integrate_pustaka_apk.py BASE.apk PUSTAKA.apk OUTPUT.apk")
    base_path, source_path, output_path = map(Path, sys.argv[1:])
    with zipfile.ZipFile(source_path) as source:
        names = set(source.namelist())
        missing = sorted(REQUIRED - names)
        if missing:
            raise SystemExit("Pustaka payload incomplete: " + ", ".join(missing))
        dex = source.read("classes.dex")
        native = source.read("lib/arm64-v8a/libmain.so")
        manifest = source.read("AndroidManifest.xml")
        package_ascii = b"com.racas.mostwanted"
        package_utf16 = "com.racas.mostwanted".encode("utf-16le")
        if package_ascii not in manifest and package_utf16 not in manifest:
            raise SystemExit("Pustaka package id mismatch")
        for marker in DEX_MARKERS:
            if marker not in dex:
                raise SystemExit("Pustaka DEX marker missing: " + repr(marker))
        for marker in NATIVE_MARKERS:
            if marker not in native:
                raise SystemExit("Pustaka native marker missing: " + repr(marker))
        merged = {}
        with zipfile.ZipFile(base_path) as base:
            for info in base.infolist():
                name = info.filename
                if info.is_dir() or signature_entry(name):
                    continue
                if name.startswith(("res/", "lib/")) or name == "resources.arsc":
                    continue
                if re.fullmatch(r"classes\d*\.dex", name):
                    continue
                merged[name] = base.read(name)
        # DEX, manifest, resource table, resources and native runtime all come
        # from the same tested APK, so resource IDs and Java/native code agree.
        for info in source.infolist():
            name = info.filename
            if info.is_dir() or signature_entry(name):
                continue
            merged[name] = source.read(name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for name in sorted(merged):
            out.writestr(name, merged[name])
    with zipfile.ZipFile(output_path) as check:
        out_names = set(check.namelist())
        if not REQUIRED.issubset(out_names):
            raise SystemExit("merged APK missing required payload")
        if any(signature_entry(n) for n in out_names):
            raise SystemExit("stale APK signing metadata remains")
    print("Pustaka SHA-256:", sha256(source_path))
    print("Merged APK bytes:", output_path.stat().st_size)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
