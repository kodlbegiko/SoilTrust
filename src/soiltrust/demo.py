"""Reproducible demonstration adapter. The V0.2 evaluation rules are unchanged.

The bundled CSV is synthetic. Arbitrary coordinates perform a nearest-fixture
lookup, NOT a query for official soil observations at that location.
"""
from __future__ import annotations

import math
from pathlib import Path

from soiltrust.models import DecisionReport
from soiltrust.pipeline import build_report
from soiltrust.sources.fixture_weather import FixtureWeatherSource
from soiltrust.sources.local_soil import NormalizedTaiwanSoilCSVSource
from soiltrust.sources.open_meteo import OpenMeteoForecastSource


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_SOIL_CSV = REPO_ROOT / "data" / "demo_taiwan_soil.csv"

# Coordinates select the nearest synthetic fixture; none represents a real field.
SCENARIOS = {
    "Taichung — synthetic record": (24.1236, 120.6753),
    "Changhua — synthetic record": (24.0687, 120.5440),
    "Tainan — synthetic record": (23.0000, 120.2200),
    "Out-of-coverage — distance check": (25.0330, 121.5654),
    "Custom coordinates": (24.1236, 120.6753),
}


def evaluate_demo(
    latitude: float,
    longitude: float,
    weather_mode: str = "fixture",
    *,
    live_weather_source: OpenMeteoForecastSource | None = None,
) -> tuple[DecisionReport, str | None]:
    """Run actual V0.2 source adapters and build_report, never a precomputed result.

    In live mode, upstream failures result in weather=None and the existing
    critical 'weather.missing' issue. No synthetic data is relabelled as live.
    """
    if not (math.isfinite(latitude) and -90 <= latitude <= 90):
        raise ValueError("Latitude must be a finite number between -90 and 90.")
    if not (math.isfinite(longitude) and -180 <= longitude <= 180):
        raise ValueError("Longitude must be a finite number between -180 and 180.")
    if weather_mode not in {"fixture", "open-meteo"}:
        raise ValueError("Unsupported weather mode.")

    soil = NormalizedTaiwanSoilCSVSource(DEMO_SOIL_CSV).nearest(
        latitude, longitude
    )
    weather_error: str | None = None

    if weather_mode == "fixture":
        weather = FixtureWeatherSource().fetch(latitude, longitude)
    else:
        try:
            source = live_weather_source or OpenMeteoForecastSource()
            weather = source.fetch(latitude, longitude)
        except Exception as exc:
            # Failure is explicit and cannot become PASS. Do not silently fall
            # back to a fixture presented as observed/model data.
            weather = None
            weather_error = f"{type(exc).__name__}: {str(exc)[:240]}"

    return build_report(latitude, longitude, soil, weather), weather_error
