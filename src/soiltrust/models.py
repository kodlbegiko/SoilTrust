from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Literal

Severity = Literal["info", "warning", "critical"]
DecisionStatus = Literal["PASS", "CAUTION", "ABSTAIN"]


@dataclass(slots=True)
class Provenance:
    source_name: str
    source_url: str
    source_type: str
    retrieved_at: str
    spatial_resolution_m: float | None = None
    temporal_resolution: str | None = None
    observation_time: str | None = None
    license: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class SoilRecord:
    record_id: str
    latitude: float
    longitude: float
    ph: float | None
    organic_matter_pct: float | None
    cec_cmol_kg: float | None
    texture: str | None
    observed_on: str | None
    distance_m: float | None
    provenance: Provenance
    demo_fixture: bool = False
    source_attributes: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class WeatherRecord:
    latitude: float
    longitude: float
    soil_moisture_m3_m3: float | None
    soil_temperature_c: float | None
    precipitation_mm: float | None
    observed_at: str | None
    provenance: Provenance
    demo_fixture: bool = False
    precipitation_7d_mm: float | None = None
    et0_7d_mm: float | None = None
    grid_cell_distance_m: float | None = None


@dataclass(slots=True)
class QualityIssue:
    code: str
    severity: Severity
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DecisionReport:
    generated_at: str
    requested_location: dict[str, float]
    soil: SoilRecord | None
    weather: WeatherRecord | None
    issues: list[QualityIssue]
    status: DecisionStatus
    reliability_score: int
    can_make_field_decision: bool
    explanation: str
    next_measurements: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
