import tempfile
import unittest
from pathlib import Path

from soiltrust.sources.local_soil import NormalizedTaiwanSoilCSVSource, haversine_m


class SourceTests(unittest.TestCase):
    def test_haversine_zero(self):
        self.assertAlmostEqual(haversine_m(24.0, 120.0, 24.0, 120.0), 0.0)

    def test_nearest_record(self):
        content = """record_id,latitude,longitude,ph,organic_matter_pct,cec_cmol_kg,texture,observed_on,spatial_resolution_m,temporal_resolution,source_name,source_url,source_type,license,demo_fixture,notes\nA,24.0,120.0,6.0,2.0,10,loam,2026-01-01,250,survey,test,local://a,official,test,false,\nB,25.0,121.0,7.0,3.0,12,clay,2026-01-01,250,survey,test,local://b,official,test,false,\n"""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "soil.csv"
            p.write_text(content, encoding="utf-8")
            record = NormalizedTaiwanSoilCSVSource(p).nearest(24.01, 120.01)
            self.assertIsNotNone(record)
            self.assertEqual(record.record_id, "A")


if __name__ == "__main__":
    unittest.main()
