from __future__ import annotations

from soiltrust.models import Provenance, WeatherRecord, utc_now_iso


class FixtureWeatherSource:
    """Offline deterministic weather fixture used for tests and demos.

    It is intentionally marked as demo data so the final decision must abstain.
    """

    def fetch(self, latitude: float, longitude: float) -> WeatherRecord:
        return WeatherRecord(
            latitude=latitude,
            longitude=longitude,
            soil_moisture_m3_m3=0.31,
            soil_temperature_c=24.8,
            precipitation_mm=0.0,
            observed_at="2026-11-03T12:00",
            provenance=Provenance(
                source_name="SoilTrust offline weather fixture",
                source_url="local://data/demo_weather.json",
                source_type="demo_fixture",
                retrieved_at=utc_now_iso(),
                spatial_resolution_m=9000,
                temporal_resolution="hourly-demo",
                observation_time="2026-11-03T12:00",
                license="Demo only",
                notes="Synthetic representative value; not observational evidence.",
            ),
            demo_fixture=True,
        )
