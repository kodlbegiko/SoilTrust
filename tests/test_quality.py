import unittest
from dataclasses import replace

from soiltrust.models import Provenance, SoilRecord, WeatherRecord
from soiltrust.pipeline import build_report
from soiltrust.quality import evaluate_quality


PROV_SOIL = Provenance(
    source_name="official-style test",
    source_url="https://example.invalid/soil",
    source_type="official",
    retrieved_at="2026-11-03T12:00:00+08:00",
    spatial_resolution_m=250,
    observation_time="2026-10-01",
)
PROV_WEATHER = Provenance(
    source_name="model test",
    source_url="https://example.invalid/weather",
    source_type="forecast_model",
    retrieved_at="2026-11-03T12:00:00+08:00",
    spatial_resolution_m=9000,
    observation_time="2026-11-03T12:00",
)


def valid_soil(**kwargs):
    base = SoilRecord("S1", 24.1, 120.6, 6.5, 2.5, 15.0, "loam", "2026-10-01", 100.0, PROV_SOIL, False)
    return replace(base, **kwargs)


def valid_weather(**kwargs):
    base = WeatherRecord(24.1, 120.6, 0.32, 25.0, 0.0, "2026-11-03T12:00", PROV_WEATHER, False)
    return replace(base, **kwargs)


class QualityTests(unittest.TestCase):
    def test_invalid_ph_blocks_decision(self):
        report = build_report(24.1, 120.6, valid_soil(ph=15.2), valid_weather())
        self.assertEqual(report.status, "ABSTAIN")
        self.assertFalse(report.can_make_field_decision)
        self.assertIn("soil.ph_range", {i.code for i in report.issues})

    def test_demo_fixture_blocks_decision(self):
        report = build_report(24.1, 120.6, valid_soil(demo_fixture=True), valid_weather())
        self.assertEqual(report.status, "ABSTAIN")
        self.assertIn("soil.demo_fixture", {i.code for i in report.issues})

    def test_spatial_scale_mismatch_is_visible(self):
        issues = evaluate_quality(valid_soil(), valid_weather())
        codes = {i.code for i in issues}
        self.assertIn("cross_source.spatial_scale_mismatch", codes)

    def test_weather_missing_blocks_decision(self):
        report = build_report(24.1, 120.6, valid_soil(), None)
        self.assertEqual(report.status, "ABSTAIN")
        self.assertIn("weather.missing", {i.code for i in report.issues})

    def test_clean_equal_scale_inputs_can_pass(self):
        weather = valid_weather(provenance=replace(PROV_WEATHER, spatial_resolution_m=250))
        report = build_report(24.1, 120.6, valid_soil(), weather)
        self.assertEqual(report.status, "PASS")
        self.assertTrue(report.can_make_field_decision)


if __name__ == "__main__":
    unittest.main()
