import unittest

from soiltrust.sources.open_meteo import OpenMeteoForecastSource


class OpenMeteoTests(unittest.TestCase):
    def test_current_and_seven_day_context(self):
        payload = {
            "latitude": 24.13,
            "longitude": 120.68,
            "current": {
                "time": "2026-11-03T17:00",
                "soil_moisture_0_to_1cm": 0.29,
                "soil_temperature_0cm": 25.1,
                "precipitation": 0.0,
            },
            "daily": {
                "time": [
                    "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30",
                    "2026-10-31", "2026-11-01", "2026-11-02", "2026-11-03",
                ],
                "precipitation_sum": [1, 2, 3, 4, 5, 6, 7, 999],
                "et0_fao_evapotranspiration": [2, 2, 2, 2, 2, 2, 2, 999],
            },
        }
        record = OpenMeteoForecastSource.from_payload(24.1236, 120.6753, "https://example.test", payload)
        self.assertAlmostEqual(record.soil_moisture_m3_m3, 0.29)
        self.assertAlmostEqual(record.precipitation_7d_mm, 28.0)
        self.assertAlmostEqual(record.et0_7d_mm, 14.0)
        self.assertGreater(record.grid_cell_distance_m, 0)
        self.assertIsNone(record.provenance.spatial_resolution_m)


if __name__ == "__main__":
    unittest.main()
