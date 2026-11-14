from __future__ import annotations

import csv
import math
from pathlib import Path

from soiltrust.models import Provenance, SoilRecord, utc_now_iso


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _float_or_none(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


class NormalizedTaiwanSoilCSVSource:
    """Read a normalized Taiwan soil-grid CSV and return the nearest record.

    V0.1 deliberately separates *normalization* from *reasoning*. This keeps the
    reliability layer deterministic even if the upstream official file format changes.
    """

    def __init__(self, csv_path: str | Path):
        self.csv_path = Path(csv_path)

    def nearest(self, latitude: float, longitude: float) -> SoilRecord | None:
        nearest_row: dict[str, str] | None = None
        nearest_distance = float("inf")

        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                row_lat = float(row["latitude"])
                row_lon = float(row["longitude"])
                distance = haversine_m(latitude, longitude, row_lat, row_lon)
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_row = row

        if nearest_row is None:
            return None

        return SoilRecord(
            record_id=nearest_row["record_id"],
            latitude=float(nearest_row["latitude"]),
            longitude=float(nearest_row["longitude"]),
            ph=_float_or_none(nearest_row.get("ph")),
            organic_matter_pct=_float_or_none(nearest_row.get("organic_matter_pct")),
            cec_cmol_kg=_float_or_none(nearest_row.get("cec_cmol_kg")),
            texture=nearest_row.get("texture") or None,
            observed_on=nearest_row.get("observed_on") or None,
            distance_m=round(nearest_distance, 1),
            demo_fixture=(nearest_row.get("demo_fixture", "false").lower() == "true"),
            provenance=Provenance(
                source_name=nearest_row.get("source_name", "Taiwan soil data"),
                source_url=nearest_row.get("source_url", ""),
                source_type=nearest_row.get("source_type", "normalized_csv"),
                retrieved_at=utc_now_iso(),
                spatial_resolution_m=_float_or_none(nearest_row.get("spatial_resolution_m")),
                temporal_resolution=nearest_row.get("temporal_resolution") or None,
                observation_time=nearest_row.get("observed_on") or None,
                license=nearest_row.get("license") or None,
                notes=nearest_row.get("notes") or None,
            ),
        )
