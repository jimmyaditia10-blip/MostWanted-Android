#!/usr/bin/env python3
from __future__ import annotations
import hashlib, re, sys, zipfile
from pathlib import Path

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: extract_pustaka_diagnostics.py PUSTAKA.apk OUTPUT_DIR")
    apk, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    report = []
    with zipfile.ZipFile(apk) as z:
        names = sorted(n for n in z.namelist() if not n.endswith("/"))
        targets = [n for n in names if n == "lib/arm64-v8a/libmain.so" or re.fullmatch(r"classes\d*\.dex", n)]
        for name in targets:
            data = z.read(name)
            target = out / Path(name).name
            target.write_bytes(data)
            report.append(f"{name}\t{len(data)}\t{sha(data)}")
            if name.endswith(".so"):
                for match in re.finditer(rb"nosfx|DrawNosTrail|BuildNosTrail|UpdateNosTrail|kShader|History::|coreLight|glowLight|SV_Position|TEXCOORD", data, re.I):
                    start = max(0, match.start() - 48)
                    end = min(len(data), match.start() + 180)
                    snippet = data[start:end].replace(b"\0", b" ")
                    report.append(f"STRING_OFFSET 0x{match.start():x}\t{snippet.decode('ascii','replace')}")
    (out / "SHA256-AND-RENDERER-STRINGS.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report[:80]))
    print("Diagnostics extracted:", len(targets), "files")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
