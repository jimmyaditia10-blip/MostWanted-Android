import io
import struct
import unittest

from tools import xdvdfs


def directory(name, sector, size, attr=0):
    raw_name = name.encode("latin-1")
    table = bytearray(14 + len(raw_name))
    struct.pack_into("<HHIIBB", table, 0, 0, 0, sector, size, attr, len(raw_name))
    table[14:] = raw_name
    return bytes(table)


class XdvdfsReaderTest(unittest.TestCase):
    def test_reads_directory_entry_case_insensitively(self):
        image = bytearray(4 * xdvdfs.SECTOR)
        table = directory("GLOBAL.BIN", 2, 5)
        image[xdvdfs.SECTOR: xdvdfs.SECTOR + len(table)] = table
        image[2 * xdvdfs.SECTOR: 2 * xdvdfs.SECTOR + 5] = b"hello"
        f = io.BytesIO(image)
        entries = xdvdfs.read_directory(f, 0, 1, len(table), len(image))
        self.assertEqual(("GLOBAL.BIN", 2, 5, 0), entries["global.bin"])
        start, size = xdvdfs.resolve_file(f, 0, 1, len(table), "global.bin", len(image))
        self.assertEqual(b"hello", image[start:start + size])

    def test_resolves_nested_directory(self):
        image = bytearray(5 * xdvdfs.SECTOR)
        child = directory("TEXTURES.BIN", 3, 4)
        root = directory("GLOBAL", 2, len(child), xdvdfs.DIR)
        image[xdvdfs.SECTOR: xdvdfs.SECTOR + len(root)] = root
        image[2 * xdvdfs.SECTOR: 2 * xdvdfs.SECTOR + len(child)] = child
        image[3 * xdvdfs.SECTOR: 3 * xdvdfs.SECTOR + 4] = b"data"
        f = io.BytesIO(image)
        start, size = xdvdfs.resolve_file(f, 0, 1, len(root), "GLOBAL/TEXTURES.BIN", len(image))
        self.assertEqual(b"data", image[start:start + size])

    def test_rejects_parent_path(self):
        f = io.BytesIO(bytearray(4 * xdvdfs.SECTOR))
        with self.assertRaises(ValueError):
            xdvdfs.resolve_file(f, 0, 1, 14, "../GLOBAL.BIN", len(f.getvalue()))

    def test_rejects_entry_outside_image(self):
        table = directory("BAD.BIN", 99, 8)
        image = bytearray(xdvdfs.SECTOR)
        image[:len(table)] = table
        with self.assertRaises(ValueError):
            xdvdfs.resolve_file(io.BytesIO(image), 0, 0, len(table), "BAD.BIN", len(image))

    def test_rejects_directory_tree_cycle(self):
        table = bytearray(32)
        struct.pack_into("<HHIIBB", table, 0, 4, 0, 1, 1, 0, 1)
        table[14] = ord("A")
        struct.pack_into("<HHIIBB", table, 16, 4, 0, 1, 1, 0, 1)
        table[30] = ord("B")
        image = bytearray(xdvdfs.SECTOR)
        image[:len(table)] = table
        with self.assertRaises(ValueError):
            xdvdfs.read_directory(io.BytesIO(image), 0, 0, len(table), len(image))


if __name__ == "__main__":
    unittest.main()
