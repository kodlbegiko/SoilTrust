import unittest

from soiltrust.demo import SCENARIOS, evaluate_demo
from soiltrust.models import Provenance, WeatherRecord


class FailingLiveWeather:
    def fetch(self, latitude, longitude):
        raise OSError("Simulated upstream failure")


class StubLiveWeather:
    def fetch(self, latitude, longitude):
        return WeatherRecord(
            latitude=latitude,
            longitude=longitude,
            soil_moisture_m3_m3=0.3,
            soil_temperature_c=25.0,
            precipitation_mm=0.0,
            observed_at="2026-11-14T12:00",
            provenance=Provenance(
                source_name="Stub model for unit test",
                source_url="https://example.invalid/test",
                source_type="forecast_model",
                retrieved_at="2026-11-14T12:00:00+08:00",
                spatial_resolution_m=None,
                observation_time="2026-11-14T12:00",
            ),
            demo_fixture=False,
        )


class InteractiveDemoTests(unittest.TestCase):
    def test_all_bundled_scenarios_still_abstain(self):
        for name, (lat, lon) in SCENARIOS.items():
            with self.subTest(name=name):
                report, error = evaluate_demo(lat, lon)
                self.assertIsNone(error)
                self.assertEqual(report.status, "ABSTAIN")
                self.assertFalse(report.can_make_field_decision)
                self.assertIn("soil.demo_fixture", {issue.code for issue in report.issues})

    def test_out_of_coverage_flags_distance(self):
        report, _ = evaluate_demo(25.0330, 121.5654)
        codes = {issue.code for issue in report.issues}
        self.assertIn("soil.distance", codes)
        self.assertGreater(report.soil.distance_m, 2000)

    def test_upstream_error_fails_closed_without_faux_live_fallback(self):
        report, error = evaluate_demo(
            24.1236, 120.6753, "open-meteo",
            live_weather_source=FailingLiveWeather(),
        )
        self.assertIn("Simulated upstream failure", error)
        self.assertIsNone(report.weather)
        self.assertEqual(report.status, "ABSTAIN")
        self.assertIn("weather.missing", {issue.code for issue in report.issues})

    def test_live_weather_does_not_upgrade_synthetic_soil(self):
        report, error = evaluate_demo(
            24.1236, 120.6753, "open-meteo",
            live_weather_source=StubLiveWeather(),
        )
        self.assertIsNone(error)
        self.assertFalse(report.weather.demo_fixture)
        self.assertTrue(report.soil.demo_fixture)
        self.assertEqual(report.status, "ABSTAIN")

    def test_invalid_coordinates_and_mode_rejected(self):
        for lat, lon, mode in [
            (float("nan"), 120.0, "fixture"),
            (91.0, 120.0, "fixture"),
            (24.0, -181.0, "fixture"),
            (24.0, 120.0, "unknown"),
        ]:
            with self.subTest(lat=lat, lon=lon, mode=mode):
                with self.assertRaises(ValueError):
                    evaluate_demo(lat, lon, mode)


if __name__ == "__main__":
    unittest.main()
