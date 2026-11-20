#!/usr/bin/env python3
"""Locate ZDIR / ZZDIR16 markers without assuming an undocumented layout.

This is an evidence-gathering tool, not an archive parser. It reports raw
signature offsets and surrounding bytes so a real Xbox image can be examined
before any field offsets or entry structures are implemented.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

SIGNATURES = {
    "ZDIR": (b"ZDIR", b"Z\x00D\x00I\x00R\x00"),
    "ZZDIR16": (b"ZZDIR16", b"Z\x00Z\x00D\x00I\x00R\x001\x006\x00"),
}


def find_all(data: bytes, needle: bytes) -> Iterable[int]:
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            return
        yield offset
        start = offset + 1


def scan_bytes(data: bytes, context: int = 24) -> list[dict[str, object]]:
    if context < 0:
        raise ValueError("context must be non-negative")
    hits: list[dict[str, object]] = []
    seen: set[tuple[str, int, int]] = set()
    for name, variants in SIGNATURES.items():
        for needle in variants:
            for offset in find_all(data, needle):
                key = (name, offset, len(needle))
                if key in seen:
                    continue
                seen.add(key)
                left = max(0, offset - context)
                right = min(len(data), offset + len(needle) + context)
                hits.append({
                    "signature": name,
                    "encoding": "utf-16le" if len(needle) > len(name) else "ascii",
                    "offset": offset,
                    "length": len(needle),
                    "context_offset": left,
                    "context_hex": data[left:right].hex(" "),
                })
    hits.sort(key=lambda item: (int(item["offset"]), str(item["signature"])))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Xbox game file or extracted archive")
    parser.add_argument("--context", type=int, default=24, help="bytes shown on each side")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()
    data = args.file.read_bytes()
    hits = scan_bytes(data, args.context)
    result = {
        "file": str(args.file),
        "file_size": len(data),
        "signatures_found": len(hits),
        "hits": hits,
        "warning": "Signature hits are candidates only; they do not prove a valid directory structure.",
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"FILE: {args.file} ({len(data)} bytes)")
        print(f"HITS: {len(hits)}")
        for hit in hits:
            print(f'{hit["signature"]} {hit["encoding"]} @ 0x{int(hit["offset"]):X} '
                  f'({hit["offset"]})')
            print(f'  {hit["context_offset"]}: {hit["context_hex"]}')
        print(result["warning"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
