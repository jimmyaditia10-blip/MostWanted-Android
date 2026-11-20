import unittest

from scan_zdir import scan_bytes


class ZdirSignatureScanTests(unittest.TestCase):
    def test_finds_ascii_markers_and_keeps_offsets(self):
        data = b"HEAD" + b"ZDIR" + b"middle" + b"ZZDIR16" + b"TAIL"
        hits = scan_bytes(data, context=2)
        self.assertEqual(
            [(hit["signature"], hit["offset"]) for hit in hits],
            [("ZDIR", 4), ("ZZDIR16", 14)],
        )

    def test_finds_utf16le_marker(self):
        data = b"\x00" + "ZZDIR16".encode("utf-16le") + b"\x00"
        hits = scan_bytes(data, context=0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["signature"], "ZZDIR16")
        self.assertEqual(hits[0]["encoding"], "utf-16le")
        self.assertEqual(hits[0]["offset"], 1)

    def test_rejects_negative_context(self):
        with self.assertRaises(ValueError):
            scan_bytes(b"ZDIR", context=-1)

    def test_no_false_hit_on_empty_data(self):
        self.assertEqual(scan_bytes(b""), [])


if __name__ == "__main__":
    unittest.main()
