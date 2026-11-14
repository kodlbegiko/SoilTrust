from __future__ import annotations

import json
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from soiltrust.models import Provenance, WeatherRecord, utc_now_iso
from soiltrust.sources.local_soil import haversine_m


class OpenMeteoForecastSource:
    ENDPOINT = "https://api.open-meteo.com/v1/forecast"

    def fetch(self, latitude: float, longitude: float, timeout_s: int = 15) -> WeatherRecord:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join([
                "soil_moisture_0_to_1cm",
                "soil_temperature_0cm",
                "precipitation",
            ]),
            "daily": ",".join([
                "precipitation_sum",
                "et0_fao_evapotranspiration",
            ]),
            "past_days": 7,
            "forecast_days": 1,
            "timezone": "auto",
            "cell_selection": "land",
        }
        url = f"{self.ENDPOINT}?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": "soiltrust/0.2 (+https://github.com/kodlbegiko)"})
        with urlopen(req, timeout=timeout_s) as response:
            payload = json.load(response)
        return self.from_payload(latitude, longitude, url, payload)

    @staticmethod
    def from_payload(requested_latitude: float, requested_longitude: float, source_url: str, payload: dict) -> WeatherRecord:
        current = payload.get("current", {})
        if not current or not current.get("time"):
            raise ValueError("Open-Meteo returned no current weather/model record")

        grid_lat = float(payload.get("latitude", requested_latitude))
        grid_lon = float(payload.get("longitude", requested_longitude))
        grid_distance = haversine_m(requested_latitude, requested_longitude, grid_lat, grid_lon)

        daily = payload.get("daily", {})
        daily_dates = daily.get("time", [])
        daily_precip = daily.get("precipitation_sum", [])
        daily_et0 = daily.get("et0_fao_evapotranspiration", [])
        current_date_text = str(current.get("time", ""))[:10]
        try:
            current_day = date.fromisoformat(current_date_text)
        except ValueError:
            current_day = None

        precip_7d: list[float] = []
        et0_7d: list[float] = []
        for i, day_text in enumerate(daily_dates):
            try:
                day = date.fromisoformat(str(day_text)[:10])
            except ValueError:
                continue
            if current_day is not None and day >= current_day:
                continue
            if len(precip_7d) < 7 and i < len(daily_precip) and daily_precip[i] is not None:
                precip_7d.append(float(daily_precip[i]))
            if len(et0_7d) < 7 and i < len(daily_et0) and daily_et0[i] is not None:
                et0_7d.append(float(daily_et0[i]))

        return WeatherRecord(
            latitude=grid_lat,
            longitude=grid_lon,
            soil_moisture_m3_m3=_float(current.get("soil_moisture_0_to_1cm")),
            soil_temperature_c=_float(current.get("soil_temperature_0cm")),
            precipitation_mm=_float(current.get("precipitation")),
            observed_at=str(current.get("time")),
            provenance=Provenance(
                source_name="Open-Meteo Weather Forecast API",
                source_url=source_url,
                source_type="forecast_model",
                retrieved_at=utc_now_iso(),
                spatial_resolution_m=None,
                temporal_resolution="current model condition + 7-day daily context",
                observation_time=str(current.get("time")),
                license="Open-Meteo terms plus upstream weather-model licences",
                notes=(
                    "Model-derived gridded weather/soil state; not a field sensor measurement. "
                    "Open-Meteo automatically selects the highest-resolution applicable model; "
                    "therefore SoilTrust does not invent a fixed spatial resolution when the response does not identify one."
                ),
            ),
            demo_fixture=False,
            precipitation_7d_mm=round(sum(precip_7d), 3) if precip_7d else None,
            et0_7d_mm=round(sum(et0_7d), 3) if et0_7d else None,
            grid_cell_distance_m=round(grid_distance, 1),
        )


def _float(value) -> float | None:
    if value is None:
        return None
    return float(value)
