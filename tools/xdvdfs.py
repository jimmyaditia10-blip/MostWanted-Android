#!/usr/bin/env python3
"""Extract a file from an Xbox XDVDFS image by its relative path.

Usage: xdvdfs.py <iso> <path\u0020inside\u0020disc> <out>
Paths may contain nested directories and use either slash style.
"""
import os
import struct
import sys

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
PARTITIONS = (0, 0x18300000, 0xFD90000, 0x2080000)


def read_directory(f, base, sector, size):
    if size < 14 or size > 16 * 1024 * 1024:
        raise ValueError("invalid XDVDFS directory table size")
    f.seek(base + sector * SECTOR)
    table = f.read(size)
    if len(table) != size:
        raise ValueError("truncated XDVDFS directory table")

    entries = {}
    seen = set()
    todo = [0]
    while todo:
        offset = todo.pop()
        if offset in seen:
            continue
        seen.add(offset)
        at = offset * 4
        if at + 14 > len(table):
            raise ValueError("directory tree pointer is outside its table")
        left, right, child_sector, child_size, attr, name_len = struct.unpack_from("<HHIIBB", table, at)
        if left == 0xFFFF:
            continue
        end = at + 14 + name_len
        if end > len(table):
            raise ValueError("truncated XDVDFS directory entry")
        name = table[at + 14:end].decode("latin-1")
        entries[name.casefold()] = (name, child_sector, child_size, attr)
        if left:
            todo.append(left)
        if right:
            todo.append(right)
    return entries


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: xdvdfs.py <iso> <disc-relative-path> <out>")
    iso, wanted, out = sys.argv[1:]
    parts = [p for p in wanted.replace("/", "\\").split("\\") if p and p != "."]
    if not parts or any(p == ".." for p in parts):
        raise SystemExit("path must stay inside the Xbox disc")

    with open(iso, "rb") as f:
        base = None
        for part in PARTITIONS:
            f.seek(part + 32 * SECTOR)
            if f.read(len(MAGIC)) == MAGIC:
                base = part
                break
        if base is None:
            raise SystemExit("not an Xbox disc image")

        f.seek(base + 32 * SECTOR + 20)
        root_sector, root_size = struct.unpack("<II", f.read(8))
        directory = read_directory(f, base, root_sector, root_size)
        hit = None
        for index, part in enumerate(parts):
            hit = directory.get(part.casefold())
            if hit is None:
                raise SystemExit(part + " not found")
            name, sector, size, attr = hit
            if index + 1 < len(parts):
                if not (attr & 0x10):
                    raise SystemExit(name + " is not a directory")
                directory = read_directory(f, base, sector, size)
            elif attr & 0x10:
                raise SystemExit(name + " is a directory, not a file")

        _, sector, size, _ = hit
        f.seek(base + sector * SECTOR)
        data = f.read(size)
        if len(data) != size:
            raise SystemExit("truncated file data")
    parent = os.path.dirname(os.path.abspath(out))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out, "wb") as output:
        output.write(data)
    print("wrote", out, size, "bytes from partition at", hex(base))


if __name__ == "__main__":
    main()
