from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.request import Request, urlopen

from soiltrust.models import Provenance, SoilRecord, utc_now_iso
from soiltrust.sources.local_soil import haversine_m

G32_DATASET_PAGE = "https://data.gov.tw/dataset/112848"
G32_METADATA_URL = "https://data.moa.gov.tw/api/FileToJson.ashx?DataId=G32&DataTable=OpenDataList"
G32_DEFAULT_RESOURCE_URL = "https://data.moa.gov.tw/OpenData/GetOpenDataFile.aspx?id=G32&FileType=DataMore&RID=2009"
G32_LICENSE = "政府資料開放授權條款-第1版"


@dataclass(frozen=True, slots=True)
class DBFField:
    name: str
    type_code: str
    length: int
    decimals: int


@dataclass(frozen=True, slots=True)
class G32Schema:
    record_id: str | None
    ph: str | None
    organic_matter: str | None
    cec: str | None
    observed_on: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "record_id": self.record_id,
            "ph": self.ph,
            "organic_matter": self.organic_matter,
            "cec": self.cec,
            "observed_on": self.observed_on,
        }


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _decode_dbf(data: bytes) -> str:
    data = data.rstrip(b"\x00 ")
    if not data:
        return ""
    for encoding in ("utf-8", "cp950", "big5", "latin1"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return data.decode("latin1", errors="replace").strip()


def read_dbf_fields(path: str | Path) -> list[DBFField]:
    with Path(path).open("rb") as f:
        header = f.read(32)
        if len(header) != 32:
            raise ValueError("DBF header is truncated")
        header_len = struct.unpack("<H", header[8:10])[0]
        if header_len < 33:
            raise ValueError("Invalid DBF header length")
        descriptors = f.read(header_len - 32)

    fields: list[DBFField] = []
    for offset in range(0, len(descriptors), 32):
        desc = descriptors[offset : offset + 32]
        if not desc or desc[0] == 0x0D:
            break
        if len(desc) < 32:
            break
        name = _decode_dbf(desc[0:11])
        type_code = chr(desc[11])
        fields.append(DBFField(name=name, type_code=type_code, length=desc[16], decimals=desc[17]))
    return fields


def iter_dbf_rows(path: str | Path) -> Iterator[dict[str, str] | None]:
    path = Path(path)
    with path.open("rb") as f:
        header = f.read(32)
        if len(header) != 32:
            raise ValueError("DBF header is truncated")
        num_records = struct.unpack("<I", header[4:8])[0]
        header_len = struct.unpack("<H", header[8:10])[0]
        record_len = struct.unpack("<H", header[10:12])[0]
        f.seek(32)
        descriptor_bytes = f.read(header_len - 32)
        fields: list[DBFField] = []
        for offset in range(0, len(descriptor_bytes), 32):
            desc = descriptor_bytes[offset : offset + 32]
            if not desc or desc[0] == 0x0D:
                break
            if len(desc) < 32:
                break
            fields.append(DBFField(
                name=_decode_dbf(desc[0:11]),
                type_code=chr(desc[11]),
                length=desc[16],
                decimals=desc[17],
            ))
        f.seek(header_len)
        for _ in range(num_records):
            raw = f.read(record_len)
            if len(raw) != record_len:
                raise ValueError("DBF record is truncated")
            if raw[0:1] == b"*":
                yield None
                continue
            pos = 1
            row: dict[str, str] = {}
            for field in fields:
                row[field.name] = _decode_dbf(raw[pos : pos + field.length])
                pos += field.length
            yield row


def iter_shp_centers(path: str | Path) -> Iterator[tuple[float, float] | None]:
    """Yield geometry centers in the SHP coordinate system, preserving record order.

    G32 is distributed as a grid polygon layer. For Polygon/Polyline/MultiPoint
    records we use the record bounding-box centre, which is sufficient for a
    regular 250 m grid lookup and avoids any third-party GIS dependency.
    """
    with Path(path).open("rb") as f:
        header = f.read(100)
        if len(header) != 100:
            raise ValueError("SHP header is truncated")
        if struct.unpack(">i", header[0:4])[0] != 9994:
            raise ValueError("Not an ESRI Shapefile (invalid file code)")
        while True:
            rec_header = f.read(8)
            if not rec_header:
                break
            if len(rec_header) != 8:
                raise ValueError("SHP record header is truncated")
            _, content_words = struct.unpack(">2i", rec_header)
            content = f.read(content_words * 2)
            if len(content) != content_words * 2:
                raise ValueError("SHP record is truncated")
            if len(content) < 4:
                yield None
                continue
            shape_type = struct.unpack("<i", content[:4])[0]
            if shape_type == 0:
                yield None
            elif shape_type in (1, 11, 21):  # Point / PointZ / PointM
                if len(content) < 20:
                    yield None
                else:
                    x, y = struct.unpack("<2d", content[4:20])
                    yield (x, y)
            elif shape_type in (3, 5, 8, 13, 15, 18, 23, 25, 28):
                if len(content) < 36:
                    yield None
                else:
                    xmin, ymin, xmax, ymax = struct.unpack("<4d", content[4:36])
                    yield ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0)
            else:
                raise ValueError(f"Unsupported SHP shape type: {shape_type}")


def twd97_tm2_121_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert TWD97 / TM2 zone 121 (EPSG:3826) to WGS84 lat/lon.

    Pure-Python inverse Transverse Mercator implementation so the official G32
    shapefile can be ingested without geopandas/pyproj.
    """
    a = 6378137.0
    b = 6356752.314245
    lon0 = math.radians(121.0)
    k0 = 0.9999
    dx = 250000.0
    e = math.sqrt(1.0 - (b * b) / (a * a))
    e_sq = e * e
    e1 = (1.0 - math.sqrt(1.0 - e_sq)) / (1.0 + math.sqrt(1.0 - e_sq))

    x_adj = x - dx
    m = y / k0
    mu = m / (a * (1 - e_sq / 4 - 3 * e_sq**2 / 64 - 5 * e_sq**3 / 256))

    j1 = 3 * e1 / 2 - 27 * e1**3 / 32
    j2 = 21 * e1**2 / 16 - 55 * e1**4 / 32
    j3 = 151 * e1**3 / 96
    j4 = 1097 * e1**4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)

    e_prime_sq = e_sq / (1 - e_sq)
    c1 = e_prime_sq * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = a * (1 - e_sq) / (1 - e_sq * math.sin(fp) ** 2) ** 1.5
    n1 = a / math.sqrt(1 - e_sq * math.sin(fp) ** 2)
    d = x_adj / (n1 * k0)

    q1 = n1 * math.tan(fp) / r1
    q2 = d**2 / 2
    q3 = (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * e_prime_sq) * d**4 / 24
    q4 = (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * e_prime_sq - 3 * c1**2) * d**6 / 720
    lat = fp - q1 * (q2 - q3 + q4)

    q5 = d
    q6 = (1 + 2 * t1 + c1) * d**3 / 6
    q7 = (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * e_prime_sq + 24 * t1**2) * d**5 / 120
    lon = lon0 + (q5 - q6 + q7) / math.cos(fp)
    return math.degrees(lat), math.degrees(lon)


def wgs84_to_twd97_tm2_121(latitude: float, longitude: float) -> tuple[float, float]:
    """Forward conversion used for verification/tests and future containment lookup."""
    a = 6378137.0
    b = 6356752.314245
    lon0 = math.radians(121.0)
    k0 = 0.9999
    dx = 250000.0
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    e_sq = 1 - (b * b) / (a * a)
    e_prime_sq = e_sq / (1 - e_sq)
    n = a / math.sqrt(1 - e_sq * math.sin(lat) ** 2)
    t = math.tan(lat) ** 2
    c = e_prime_sq * math.cos(lat) ** 2
    aa = (lon - lon0) * math.cos(lat)
    m = a * (
        (1 - e_sq / 4 - 3 * e_sq**2 / 64 - 5 * e_sq**3 / 256) * lat
        - (3 * e_sq / 8 + 3 * e_sq**2 / 32 + 45 * e_sq**3 / 1024) * math.sin(2 * lat)
        + (15 * e_sq**2 / 256 + 45 * e_sq**3 / 1024) * math.sin(4 * lat)
        - (35 * e_sq**3 / 3072) * math.sin(6 * lat)
    )
    x = dx + k0 * n * (aa + (1 - t + c) * aa**3 / 6 + (5 - 18 * t + t**2 + 72 * c - 58 * e_prime_sq) * aa**5 / 120)
    y = k0 * (m + n * math.tan(lat) * (aa**2 / 2 + (5 - t + 9 * c + 4 * c**2) * aa**4 / 24 + (61 - 58 * t + t**2 + 600 * c - 330 * e_prime_sq) * aa**6 / 720))
    return x, y


def _normalise_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


ALIASES: dict[str, set[str]] = {
    "record_id": {"id", "fid", "objectid", "gridid", "gridno", "no", "number", "code"},
    "ph": {"ph", "soilph", "phvalue", "phh2o", "acidity"},
    "organic_matter": {"om", "organic", "organicmatter", "organicmat", "ompct", "ompercent"},
    "cec": {"cec", "cationexchange", "ceccmolkg", "ceccmol"},
    "observed_on": {"date", "sampledate", "surveydate", "observedon", "obsdate"},
}


def detect_g32_schema(fields: list[DBFField], overrides: dict[str, str] | None = None) -> G32Schema:
    overrides = overrides or {}
    by_norm = {_normalise_name(f.name): f.name for f in fields}

    def pick(role: str) -> str | None:
        if role in overrides:
            wanted = overrides[role]
            if wanted not in {f.name for f in fields}:
                raise ValueError(f"Field override {role}={wanted!r} is not present in DBF")
            return wanted
        for alias in ALIASES[role]:
            if alias in by_norm:
                return by_norm[alias]
        return None

    return G32Schema(
        record_id=pick("record_id"),
        ph=pick("ph"),
        organic_matter=pick("organic_matter"),
        cec=pick("cec"),
        observed_on=pick("observed_on"),
    )


def parse_field_map(text: str | None) -> dict[str, str]:
    if not text:
        return {}
    out: dict[str, str] = {}
    for part in text.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError("field map entries must look like ph=PH,organic_matter=OM,cec=CEC")
        key, value = part.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in ALIASES:
            raise ValueError(f"Unknown field-map role: {key}")
        out[key] = value
    return out


def _float_or_none(value: str | None) -> float | None:
    if value is None:
        return None
    s = value.strip().replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _find_shapefile(root: Path) -> tuple[Path, Path]:
    shp_files = sorted(root.rglob("*.shp"))
    if not shp_files:
        raise FileNotFoundError("No .shp file found in G32 archive/directory")
    candidates: list[tuple[Path, Path]] = []
    for shp in shp_files:
        dbf = shp.with_suffix(".dbf")
        if dbf.exists():
            candidates.append((shp, dbf))
    if not candidates:
        raise FileNotFoundError("Found .shp but no matching .dbf file")
    # Prefer names hinting TWD97/TWD9 if the archive contains multiple layers.
    candidates.sort(key=lambda pair: ("twd9" not in pair[0].stem.lower(), len(pair[0].name)))
    return candidates[0]


class G32ShapefileSource:
    """Nearest-cell reader for the official MOA G32 shapefile.

    The official resource is expected to use TWD97 / TM2 zone 121. If a future
    resource changes CRS, fail closed instead of silently applying the wrong transform.
    """

    def __init__(self, archive_or_shp: str | Path, field_map: dict[str, str] | None = None, crs: str = "EPSG:3826"):
        self.input_path = Path(archive_or_shp)
        self.field_map = field_map or {}
        self.crs = crs.upper()
        self._tmp: tempfile.TemporaryDirectory[str] | None = None

        if self.input_path.suffix.lower() == ".zip":
            self._tmp = tempfile.TemporaryDirectory(prefix="soiltrust-g32-")
            root = Path(self._tmp.name)
            with zipfile.ZipFile(self.input_path) as zf:
                # Basic zip-slip defence.
                for member in zf.infolist():
                    target = (root / member.filename).resolve()
                    if root.resolve() not in target.parents and target != root.resolve():
                        raise ValueError(f"Unsafe ZIP member: {member.filename}")
                zf.extractall(root)
            self.shp_path, self.dbf_path = _find_shapefile(root)
            self.source_sha256 = sha256_file(self.input_path)
        elif self.input_path.suffix.lower() == ".shp":
            self.shp_path = self.input_path
            self.dbf_path = self.input_path.with_suffix(".dbf")
            if not self.dbf_path.exists():
                raise FileNotFoundError(f"Missing matching DBF: {self.dbf_path}")
            h = hashlib.sha256()
            for p in (self.shp_path, self.dbf_path):
                h.update(bytes.fromhex(sha256_file(p)))
            self.source_sha256 = h.hexdigest()
        elif self.input_path.is_dir():
            self.shp_path, self.dbf_path = _find_shapefile(self.input_path)
            h = hashlib.sha256()
            for p in (self.shp_path, self.dbf_path):
                h.update(bytes.fromhex(sha256_file(p)))
            self.source_sha256 = h.hexdigest()
        else:
            raise ValueError("G32 input must be a .zip, .shp, or directory")

        if self.crs != "EPSG:3826":
            raise ValueError("V0.2 only supports verified TWD97 / TM2 zone 121 (EPSG:3826) input")
        self.fields = read_dbf_fields(self.dbf_path)
        self.schema = detect_g32_schema(self.fields, self.field_map)

    def inspect(self) -> dict:
        return {
            "shapefile": str(self.shp_path),
            "dbf": str(self.dbf_path),
            "crs": self.crs,
            "source_sha256": self.source_sha256,
            "fields": [f.__dict__ if hasattr(f, "__dict__") else {"name": f.name, "type_code": f.type_code, "length": f.length, "decimals": f.decimals} for f in self.fields],
            "detected_schema": self.schema.as_dict(),
        }

    def nearest(self, latitude: float, longitude: float) -> SoilRecord | None:
        best_row: dict[str, str] | None = None
        best_latlon: tuple[float, float] | None = None
        best_distance = float("inf")
        best_index = -1
        count = 0

        for idx, (center, row) in enumerate(zip(iter_shp_centers(self.shp_path), iter_dbf_rows(self.dbf_path)), start=1):
            count += 1
            if center is None or row is None:
                continue
            x, y = center
            row_lat, row_lon = twd97_tm2_121_to_wgs84(x, y)
            if not (18.0 <= row_lat <= 27.0 and 117.0 <= row_lon <= 123.5):
                raise ValueError(
                    "G32 geometry did not transform into a plausible Taiwan coordinate. "
                    "Do not continue until the source CRS is verified."
                )
            distance = haversine_m(latitude, longitude, row_lat, row_lon)
            if distance < best_distance:
                best_distance = distance
                best_row = row
                best_latlon = (row_lat, row_lon)
                best_index = idx

        if count == 0:
            return None
        if best_row is None or best_latlon is None:
            return None

        rec_id = best_row.get(self.schema.record_id, "") if self.schema.record_id else ""
        if not rec_id:
            rec_id = f"G32-{best_index}"
        observed = best_row.get(self.schema.observed_on, "") if self.schema.observed_on else ""
        observed = observed or None
        notes = (
            "Official MOA G32 250 m soil-fertility grid. Grid-cell centre derived from SHP geometry. "
            f"Raw source SHA-256={self.source_sha256}. Detected fields={json.dumps(self.schema.as_dict(), ensure_ascii=False)}. "
            "The government dataset page states a five-year update frequency; publication/update date is not treated as the soil observation date."
        )

        return SoilRecord(
            record_id=rec_id,
            latitude=best_latlon[0],
            longitude=best_latlon[1],
            ph=_float_or_none(best_row.get(self.schema.ph)) if self.schema.ph else None,
            organic_matter_pct=_float_or_none(best_row.get(self.schema.organic_matter)) if self.schema.organic_matter else None,
            cec_cmol_kg=_float_or_none(best_row.get(self.schema.cec)) if self.schema.cec else None,
            texture=None,
            observed_on=observed,
            distance_m=round(best_distance, 1),
            provenance=Provenance(
                source_name="農業部 G32 — 全台農田平地表土層土壤網格肥力資訊",
                source_url=G32_DATASET_PAGE,
                source_type="official_gis_shapefile",
                retrieved_at=utc_now_iso(),
                spatial_resolution_m=250.0,
                temporal_resolution="dataset update frequency: 5 years",
                observation_time=observed,
                license=G32_LICENSE,
                notes=notes,
            ),
            demo_fixture=False,
            source_attributes=dict(best_row),
        )


def fetch_g32(destination_dir: str | Path, timeout_s: int = 60) -> dict:
    """Download the official G32 binary resource and write provenance metadata.

    This function intentionally discovers the current FileUrl from the MOA metadata
    endpoint instead of hard-coding a mirror. If metadata discovery fails, it falls
    back to the official resource URL observed for RID=2009.
    """
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    metadata_req = Request(G32_METADATA_URL, headers={"User-Agent": "soiltrust/0.2 (+https://github.com/kodlbegiko)"})
    entry: dict[str, str] | None = None
    metadata_error: str | None = None
    try:
        with urlopen(metadata_req, timeout=timeout_s) as response:
            entries = json.load(response)
        if isinstance(entries, list) and entries:
            entry = next((e for e in entries if "TWD9" in str(e.get("FileName", "")).upper()), entries[0])
    except Exception as exc:  # fallback remains an official MOA URL, not a mirror
        metadata_error = str(exc)

    resource_url = (entry or {}).get("FileUrl") or G32_DEFAULT_RESOURCE_URL
    req = Request(resource_url, headers={"User-Agent": "soiltrust/0.2 (+https://github.com/kodlbegiko)"})
    with urlopen(req, timeout=timeout_s) as response:
        blob = response.read()
        disposition = response.headers.get("Content-Disposition", "")
        content_type = response.headers.get("Content-Type", "")

    if blob.startswith(b"PK\x03\x04"):
        suffix = ".zip"
    elif len(blob) >= 4 and struct.unpack(">i", blob[:4])[0] == 9994:
        suffix = ".shp"
    else:
        raise ValueError(f"Downloaded G32 resource has an unrecognised binary format ({content_type})")

    out = destination / f"moa_g32_official{suffix}"
    out.write_bytes(blob)
    digest = sha256_file(out)
    manifest = {
        "dataset": "G32 — 全台農田平地表土層土壤網格肥力資訊",
        "dataset_page": G32_DATASET_PAGE,
        "metadata_url": G32_METADATA_URL,
        "resource_url": resource_url,
        "metadata_entry": entry,
        "metadata_error": metadata_error,
        "content_type": content_type,
        "content_disposition": disposition,
        "downloaded_at": utc_now_iso(),
        "sha256": digest,
        "bytes": len(blob),
        "license": G32_LICENSE,
        "local_path": str(out),
    }
    (destination / "moa_g32_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
