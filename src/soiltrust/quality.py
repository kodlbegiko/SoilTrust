from __future__ import annotations

from datetime import date

from soiltrust.models import QualityIssue, SoilRecord, WeatherRecord


def _age_years(date_text: str | None) -> float | None:
    if not date_text:
        return None
    try:
        d = date.fromisoformat(date_text[:10])
    except ValueError:
        return None
    return (date.today() - d).days / 365.25


def evaluate_quality(soil: SoilRecord | None, weather: WeatherRecord | None) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    if soil is None:
        issues.append(QualityIssue("soil.missing", "critical", "No soil record is available for the requested location."))
    else:
        if soil.demo_fixture:
            issues.append(QualityIssue(
                "soil.demo_fixture", "critical",
                "The soil record is a demo fixture, not official field evidence. Field-level decisions are blocked.",
            ))
        if soil.ph is None:
            issues.append(QualityIssue("soil.ph_missing", "warning", "Soil pH is missing or the G32 pH field could not be mapped."))
        elif not 0.0 <= soil.ph <= 14.0:
            issues.append(QualityIssue("soil.ph_range", "critical", "Soil pH is outside the physically valid 0–14 range.", {"ph": soil.ph}))
        if soil.organic_matter_pct is None:
            issues.append(QualityIssue("soil.om_missing", "warning", "Soil organic matter is missing or its source field could not be mapped."))
        elif soil.organic_matter_pct < 0:
            issues.append(QualityIssue("soil.om_range", "critical", "Organic matter cannot be negative.", {"organic_matter_pct": soil.organic_matter_pct}))
        if soil.cec_cmol_kg is None:
            issues.append(QualityIssue("soil.cec_missing", "warning", "CEC is missing or its source field could not be mapped."))
        elif soil.cec_cmol_kg < 0:
            issues.append(QualityIssue("soil.cec_range", "critical", "CEC cannot be negative.", {"cec_cmol_kg": soil.cec_cmol_kg}))
        if soil.distance_m is not None:
            if soil.distance_m > 2000:
                issues.append(QualityIssue("soil.distance", "critical", "Nearest soil record is more than 2 km away; it should not be treated as field-level ground truth.", {"distance_m": soil.distance_m}))
            elif soil.distance_m > 500:
                issues.append(QualityIssue("soil.distance", "warning", "Nearest soil record is more than 500 m away; spatial representativeness is uncertain.", {"distance_m": soil.distance_m}))
        age = _age_years(soil.observed_on)
        if age is None:
            issues.append(QualityIssue(
                "soil.date_unknown", "warning",
                "Soil observation date is unavailable. Dataset publication/update time is not substituted for sampling time.",
            ))
        elif age > 5:
            issues.append(QualityIssue("soil.stale", "warning", "Soil observation is older than five years; current field conditions may differ.", {"age_years": round(age, 1)}))

    if weather is None:
        issues.append(QualityIssue("weather.missing", "critical", "No weather/soil-moisture model record is available."))
    else:
        if weather.demo_fixture:
            issues.append(QualityIssue(
                "weather.demo_fixture", "critical",
                "The weather record is a demo fixture, not live model output. Field-level decisions are blocked.",
            ))
        m = weather.soil_moisture_m3_m3
        if m is None:
            issues.append(QualityIssue("weather.moisture_missing", "warning", "Model soil moisture is missing."))
        elif not 0.0 <= m <= 1.0:
            issues.append(QualityIssue("weather.moisture_range", "critical", "Volumetric soil moisture is outside the valid 0–1 range.", {"soil_moisture_m3_m3": m}))
        t = weather.soil_temperature_c
        if t is not None and not -60 <= t <= 90:
            issues.append(QualityIssue("weather.temperature_range", "warning", "Soil temperature is outside a conservative plausibility range.", {"soil_temperature_c": t}))
        p = weather.precipitation_mm
        if p is not None and p < 0:
            issues.append(QualityIssue("weather.precipitation_range", "critical", "Precipitation cannot be negative.", {"precipitation_mm": p}))
        if weather.precipitation_7d_mm is not None and weather.precipitation_7d_mm < 0:
            issues.append(QualityIssue("weather.precipitation_7d_range", "critical", "Seven-day precipitation cannot be negative.", {"precipitation_7d_mm": weather.precipitation_7d_mm}))
        if weather.et0_7d_mm is not None and weather.et0_7d_mm < 0:
            issues.append(QualityIssue("weather.et0_7d_range", "critical", "Seven-day ET0 cannot be negative.", {"et0_7d_mm": weather.et0_7d_mm}))
        if weather.grid_cell_distance_m is not None:
            if weather.grid_cell_distance_m > 20_000:
                issues.append(QualityIssue(
                    "weather.grid_offset", "critical",
                    "The model grid cell selected for this location is more than 20 km away.",
                    {"grid_cell_distance_m": weather.grid_cell_distance_m},
                ))
            elif weather.grid_cell_distance_m > 5_000:
                issues.append(QualityIssue(
                    "weather.grid_offset", "warning",
                    "The model grid-cell centre is more than 5 km from the requested location; local conditions may differ.",
                    {"grid_cell_distance_m": weather.grid_cell_distance_m},
                ))

    if soil and weather:
        soil_res = soil.provenance.spatial_resolution_m
        weather_res = weather.provenance.spatial_resolution_m
        if soil_res and weather_res and weather_res / soil_res >= 10:
            issues.append(QualityIssue(
                "cross_source.spatial_scale_mismatch", "warning",
                "Weather/model data are much coarser than the soil grid; do not interpret both as the same field-scale measurement.",
                {"soil_resolution_m": soil_res, "weather_resolution_m": weather_res, "ratio": round(weather_res / soil_res, 1)},
            ))
        elif soil_res and weather_res is None:
            issues.append(QualityIssue(
                "cross_source.weather_resolution_unknown", "warning",
                "The soil grid resolution is known, but the automatically selected weather model resolution is not exposed in this response. Do not assume equal spatial scale.",
                {"soil_resolution_m": soil_res},
            ))

    if not issues:
        issues.append(QualityIssue("quality.no_flags", "info", "No deterministic quality rule was triggered. This does not prove agronomic validity."))

    return issues


def score_quality(issues: list[QualityIssue]) -> int:
    score = 100
    for issue in issues:
        if issue.severity == "critical":
            score -= 35
        elif issue.severity == "warning":
            score -= 12
    return max(0, min(100, score))
