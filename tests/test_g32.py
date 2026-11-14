import struct
import tempfile
import unittest
from pathlib import Path

from soiltrust.sources.g32 import (
    G32ShapefileSource,
    detect_g32_schema,
    read_dbf_fields,
    twd97_tm2_121_to_wgs84,
    wgs84_to_twd97_tm2_121,
)


def write_polygon_shp(path: Path, centers: list[tuple[float, float]], size: float = 250.0) -> None:
    contents = []
    all_boxes = []
    half = size / 2
    for cx, cy in centers:
        xmin, ymin, xmax, ymax = cx - half, cy - half, cx + half, cy + half
        all_boxes.append((xmin, ymin, xmax, ymax))
        pts = [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)]
        content = bytearray()
        content += struct.pack("<i", 5)
        content += struct.pack("<4d", xmin, ymin, xmax, ymax)
        content += struct.pack("<2i", 1, len(pts))
        content += struct.pack("<i", 0)
        for x, y in pts:
            content += struct.pack("<2d", x, y)
        contents.append(bytes(content))
    xmin = min(b[0] for b in all_boxes); ymin = min(b[1] for b in all_boxes)
    xmax = max(b[2] for b in all_boxes); ymax = max(b[3] for b in all_boxes)
    total_bytes = 100 + sum(8 + len(c) for c in contents)
    header = bytearray(100)
    struct.pack_into(">i", header, 0, 9994)
    struct.pack_into(">i", header, 24, total_bytes // 2)
    struct.pack_into("<i", header, 28, 1000)
    struct.pack_into("<i", header, 32, 5)
    struct.pack_into("<4d", header, 36, xmin, ymin, xmax, ymax)
    with path.open("wb") as f:
        f.write(header)
        for i, content in enumerate(contents, 1):
            f.write(struct.pack(">2i", i, len(content) // 2))
            f.write(content)


def write_dbf(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        ("GRIDID", "C", 12, 0),
        ("PH", "N", 7, 2),
        ("OM", "N", 7, 2),
        ("CEC", "N", 8, 2),
        ("DATE", "C", 10, 0),
    ]
    header_len = 32 + 32 * len(fields) + 1
    record_len = 1 + sum(f[2] for f in fields)
    header = bytearray(32)
    header[0] = 0x03
    header[1:4] = bytes([126, 11, 3])
    struct.pack_into("<I", header, 4, len(rows))
    struct.pack_into("<H", header, 8, header_len)
    struct.pack_into("<H", header, 10, record_len)
    with path.open("wb") as f:
        f.write(header)
        for name, type_code, length, decimals in fields:
            desc = bytearray(32)
            raw_name = name.encode("ascii")[:11]
            desc[:len(raw_name)] = raw_name
            desc[11] = ord(type_code)
            desc[16] = length
            desc[17] = decimals
            f.write(desc)
        f.write(b"\r")
        for row in rows:
            f.write(b" ")
            for name, type_code, length, decimals in fields:
                value = row.get(name, "")
                if type_code == "N":
                    raw = value.rjust(length).encode("ascii")
                else:
                    raw = value.ljust(length)[:length].encode("ascii")
                f.write(raw)
        f.write(b"\x1a")


class G32Tests(unittest.TestCase):
    def test_twd97_roundtrip(self):
        lat, lon = 24.1236, 120.6753
        x, y = wgs84_to_twd97_tm2_121(lat, lon)
        out_lat, out_lon = twd97_tm2_121_to_wgs84(x, y)
        self.assertAlmostEqual(lat, out_lat, places=5)
        self.assertAlmostEqual(lon, out_lon, places=5)

    def test_schema_detection_and_nearest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            shp = root / "G32_TWD9.shp"
            dbf = root / "G32_TWD9.dbf"
            a = wgs84_to_twd97_tm2_121(24.1236, 120.6753)
            b = wgs84_to_twd97_tm2_121(25.05, 121.52)
            write_polygon_shp(shp, [a, b])
            write_dbf(dbf, [
                {"GRIDID": "A-001", "PH": "6.40", "OM": "2.80", "CEC": "15.20", "DATE": "2026-10-01"},
                {"GRIDID": "B-002", "PH": "7.20", "OM": "3.10", "CEC": "18.50", "DATE": "2026-10-02"},
            ])
            fields = read_dbf_fields(dbf)
            schema = detect_g32_schema(fields)
            self.assertEqual(schema.ph, "PH")
            self.assertEqual(schema.organic_matter, "OM")
            self.assertEqual(schema.cec, "CEC")

            source = G32ShapefileSource(shp)
            record = source.nearest(24.124, 120.676)
            self.assertIsNotNone(record)
            self.assertEqual(record.record_id, "A-001")
            self.assertAlmostEqual(record.ph, 6.4)
            self.assertAlmostEqual(record.organic_matter_pct, 2.8)
            self.assertAlmostEqual(record.cec_cmol_kg, 15.2)
            self.assertLess(record.distance_m, 200)
            self.assertFalse(record.demo_fixture)
            self.assertEqual(record.provenance.spatial_resolution_m, 250.0)
            self.assertIn("SHA-256", record.provenance.notes)


if __name__ == "__main__":
    unittest.main()
