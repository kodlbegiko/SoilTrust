from __future__ import annotations

from soiltrust.explanation import deterministic_explanation
from soiltrust.models import DecisionReport, SoilRecord, WeatherRecord, utc_now_iso
from soiltrust.quality import evaluate_quality, score_quality


def build_report(latitude: float, longitude: float, soil: SoilRecord | None, weather: WeatherRecord | None) -> DecisionReport:
    issues = evaluate_quality(soil, weather)
    score = score_quality(issues)
    has_critical = any(i.severity == "critical" for i in issues)
    has_warning = any(i.severity == "warning" for i in issues)

    if has_critical:
        status = "ABSTAIN"
    elif has_warning:
        status = "CAUTION"
    else:
        status = "PASS"

    next_measurements: list[str] = []
    codes = {i.code for i in issues}
    if "soil.demo_fixture" in codes or "soil.missing" in codes or "soil.distance" in codes:
        next_measurements.append("Obtain an official/local field soil record for the exact site.")
    if "soil.stale" in codes or "soil.date_unknown" in codes:
        next_measurements.append("Collect a recent soil sample or verified local soil analysis before field-level use.")
    if {"soil.ph_missing", "soil.om_missing", "soil.cec_missing"} & codes:
        next_measurements.append("Inspect the G32 DBF schema and explicitly map required chemistry fields; do not guess field meanings.")
    if "weather.demo_fixture" in codes or "weather.missing" in codes:
        next_measurements.append("Retrieve live or reanalysis weather/model data for the site and time window.")
    if "weather.grid_offset" in codes:
        next_measurements.append("Add a closer weather station or field sensor if local conditions materially affect the decision.")
    if "cross_source.spatial_scale_mismatch" in codes or "cross_source.weather_resolution_unknown" in codes:
        next_measurements.append("Do not infer field-scale conditions from a weather-model grid without independent local validation.")
    if not next_measurements:
        next_measurements.append("Validate against an independent field observation before any operational agronomic use.")

    explanation = deterministic_explanation(status, score, issues)
    return DecisionReport(
        generated_at=utc_now_iso(),
        requested_location={"latitude": latitude, "longitude": longitude},
        soil=soil,
        weather=weather,
        issues=issues,
        status=status,  # type: ignore[arg-type]
        reliability_score=score,
        can_make_field_decision=(status == "PASS"),
        explanation=explanation,
        next_measurements=next_measurements,
    )
