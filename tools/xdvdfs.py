#!/usr/bin/env python3
"""Read-only XDVDFS inspection helpers for Xbox disc images.

This module deliberately does not rebuild or modify an Xbox image.  It validates
volume metadata, resolves nested paths, and extracts regular files only.
"""
import os
import struct
import sys

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
PARTITIONS = (0, 0x18300000, 0xFD90000, 0x2080000)
MAX_DIRECTORY = 16 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024 * 1024
DIR = 0x10


def _read_exact(f, size, what):
    data = f.read(size)
    if len(data) != size:
        raise ValueError("truncated " + what)
    return data


def read_directory(f, base, sector, size, image_size=None):
    if size < 14 or size > MAX_DIRECTORY:
        raise ValueError("invalid XDVDFS directory table size")
    start = base + sector * SECTOR
    if start < base or (image_size is not None and start + size > image_size):
        raise ValueError("XDVDFS directory table is outside the image")
    f.seek(start)
    table = _read_exact(f, size, "XDVDFS directory table")

    entries = {}
    seen = set()
    todo = [0]
    while todo:
        offset = todo.pop()
        if offset in seen:
            raise ValueError("cyclic XDVDFS directory tree")
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
        key = name.casefold()
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise ValueError("invalid XDVDFS entry name")
        if key in entries:
            raise ValueError("duplicate XDVDFS entry name")
        entries[key] = (name, child_sector, child_size, attr)
        if left:
            todo.append(left)
        if right:
            todo.append(right)
    return entries


def open_volume(f):
    image_size = os.fstat(f.fileno()).st_size
    for partition in PARTITIONS:
        descriptor = partition + 32 * SECTOR
        if descriptor + 2048 > image_size:
            continue
        f.seek(descriptor)
        if f.read(len(MAGIC)) != MAGIC:
            continue
        f.seek(descriptor + 20)
        root_sector, root_size = struct.unpack("<II", _read_exact(f, 8, "XDVDFS root descriptor"))
        root_start = partition + root_sector * SECTOR
        if root_size < 14 or root_size > MAX_DIRECTORY or root_start + root_size > image_size:
            raise ValueError("invalid XDVDFS root directory bounds")
        return partition, root_sector, root_size, image_size
    raise ValueError("not an Xbox XDVDFS image")


def resolve_file(f, base, root_sector, root_size, path, image_size):
    parts = [p for p in path.replace("/", "\\").split("\\") if p and p != "."]
    if not parts or any(p == ".." for p in parts):
        raise ValueError("path must stay inside the Xbox disc")

    directory = read_directory(f, base, root_sector, root_size, image_size)
    hit = None
    for index, part in enumerate(parts):
        hit = directory.get(part.casefold())
        if hit is None:
            raise FileNotFoundError(part + " not found")
        name, sector, size, attr = hit
        start = base + sector * SECTOR
        if size < 0 or size > MAX_FILE or start < base or start + size > image_size:
            raise ValueError("XDVDFS entry is outside the image")
        if index + 1 < len(parts):
            if not (attr & DIR):
                raise ValueError(name + " is not a directory")
            directory = read_directory(f, base, sector, size, image_size)
        elif attr & DIR:
            raise ValueError(name + " is a directory, not a file")
    return base + hit[1] * SECTOR, hit[2]


def extract_file(image, path, output):
    with open(image, "rb") as f:
        base, root_sector, root_size, image_size = open_volume(f)
        start, size = resolve_file(f, base, root_sector, root_size, path, image_size)
        f.seek(start)
        data = _read_exact(f, size, "XDVDFS file data")
    parent = os.path.dirname(os.path.abspath(output))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(output, "wb") as out:
        out.write(data)
    return base, size


def main():
    if len(sys.argv) != 4:
        raise SystemExit("usage: xdvdfs.py <iso> <disc-relative-path> <out>")
    image, wanted, output = sys.argv[1:]
    try:
        base, size = extract_file(image, wanted, output)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
    print("wrote", output, size, "bytes from partition at", hex(base))


if __name__ == "__main__":
    main()
