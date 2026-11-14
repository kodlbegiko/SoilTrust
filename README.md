> **v0.3 interactive research demo:** Streamlit interface source is available on the
> [v0.3 feature branch](https://github.com/kodlbegiko/SoilTrust/tree/feat/soiltrust-v0.3-streamlit-demo).
> Install with pip install -r requirements.txt and start with streamlit run streamlit_app.py.
> See [interactive demo instructions](docs/INTERACTIVE_DEMO.md) for synthetic
> data, upstream failure behavior, tests and deployment instructions.
> The v0.2 deterministic core is unchanged. Source availability does not imply
> a successfully deployed public URL.

# SoilTrust V0.2

**Reliability before recommendation.**

SoilTrust is an inspectable reliability layer for soil intelligence. It does **not** begin by asking an AI model for an agronomic answer. It first asks whether the underlying evidence is trustworthy enough to support interpretation at all.

V0.2 adds a reproducible ingestion path for Taiwan Ministry of Agriculture **G32 — 全台農田平地表土層土壤網格肥力資訊**, plus richer Open-Meteo weather/soil-state context.

The pipeline is:

```text
official/public data
      ↓
provenance + raw hash
      ↓
coordinate/schema normalization
      ↓
deterministic quality checks
      ↓
PASS / CAUTION / ABSTAIN
      ↓
bounded explanation + next evidence needed
```

> `PASS` does not mean “agronomically correct.” It means no implemented reliability rule blocked the evidence. A field recommendation still requires crop context, local validation and an appropriate agronomic model.

## What changed in V0.2

- Pure-Python reader for the official G32 `SHP + DBF` resource.
- ZIP ingestion and SHA-256 provenance hash.
- TWD97 / TM2 zone 121 (`EPSG:3826`) → WGS84 conversion without a GIS dependency.
- Nearest 250 m grid-cell lookup from latitude/longitude.
- Explicit DBF schema inspection and field mapping; SoilTrust does **not** guess unknown chemistry fields.
- G32 publication/update time is **not** substituted for sampling time.
- Open-Meteo now uses current model conditions plus previous 7-day precipitation and ET₀ context.
- Model grid-cell offset is exposed and checked.
- Weather-model spatial resolution is left unknown when the API response does not identify it; SoilTrust does not invent a number.
- Raw G32 DBF attributes are preserved in the structured report.
- 10 automated tests cover quality logic, source selection, coordinate conversion, G32 parsing and Open-Meteo response handling.

## Public sources

### Taiwan soil — MOA G32

Official dataset page:

<https://data.gov.tw/dataset/112848>

The government describes G32 as a **250 m × 250 m** topsoil fertility grid for Taiwan's flat agricultural land, including pH, organic matter, CEC and multiple nutrient measurements. The portal states an update frequency of every five years.

The current MOA metadata endpoint used by SoilTrust is:

<https://data.moa.gov.tw/api/FileToJson.ashx?DataId=G32&DataTable=OpenDataList>

SoilTrust always discovers the official `FileUrl` first and writes a local provenance manifest when downloading.

### Weather / model soil state — Open-Meteo

Forecast API:

<https://open-meteo.com/en/docs>

V0.2 requests:

- current `soil_moisture_0_to_1cm`
- current `soil_temperature_0cm`
- current `precipitation`
- previous seven complete days of `precipitation_sum`
- previous seven complete days of `et0_fao_evapotranspiration`

These are gridded model outputs, **not field sensor ground truth**.

## Run without installation

The repository has no runtime third-party dependency.

```bash
PYTHONPATH=src python -m soiltrust.cli --help
```

## Step 1 — fetch the official G32 resource

```bash
PYTHONPATH=src python -m soiltrust.cli fetch-g32 \
  --out data/raw/g32
```

This writes the downloaded official binary plus `moa_g32_manifest.json` containing source URL, retrieval time, SHA-256 and licence information.

If a network or upstream server blocks the download, download the G32 SHP archive manually from the official dataset page and pass that local file to the next command. Do not substitute an unverified mirror silently.

## Step 2 — inspect the raw DBF schema

```bash
PYTHONPATH=src python -m soiltrust.cli inspect-g32 \
  --g32 data/raw/g32/moa_g32_official.zip
```

Typical auto-detected roles are:

```text
record_id → GRIDID / ID / FID ...
ph        → PH
organic_matter → OM
cec       → CEC
observed_on → DATE / sample date, if present
```

If the official file uses different field names, map them explicitly instead of guessing:

```bash
PYTHONPATH=src python -m soiltrust.cli inspect-g32 \
  --g32 path/to/G32.zip \
  --g32-field-map 'ph=PH_FIELD,organic_matter=OM_FIELD,cec=CEC_FIELD'
```

## Step 3 — build a real-source report

```bash
PYTHONPATH=src python -m soiltrust.cli report \
  --lat 24.1236 \
  --lon 120.6753 \
  --soil-source g32 \
  --g32 data/raw/g32/moa_g32_official.zip \
  --weather open-meteo \
  --json-out examples/g32_live_report.json \
  --html-out examples/g32_live_report.html
```

If the G32 DBF lacks a sampling date, SoilTrust deliberately emits `soil.date_unknown` and will normally return `CAUTION`, not pretend the publication date is the field observation date.

## Offline deterministic demo

The repository retains a clearly marked synthetic normalized soil fixture and weather fixture so the core logic can be tested without network access:

```bash
PYTHONPATH=src python -m soiltrust.cli report \
  --lat 24.1236 \
  --lon 120.6753 \
  --soil-source normalized \
  --soil-csv data/demo_taiwan_soil.csv \
  --weather fixture
```

Because both are fixtures, the correct output is `ABSTAIN`.

## Decision states

- `PASS` — no implemented reliability rule blocks the evidence.
- `CAUTION` — evidence may support contextual/regional interpretation, but explicit limitations remain.
- `ABSTAIN` — evidence is missing, invalid, synthetic, or spatially inappropriate; operational field decisions are blocked.

## Deterministic checks

Current checks include:

- missing soil / weather source;
- demo fixture detection;
- pH range 0–14;
- non-negative OM / CEC / precipitation / ET₀;
- volumetric soil moisture range 0–1;
- missing critical chemistry fields;
- nearest soil record distance >500 m / >2 km;
- unknown or >5-year-old soil observation date;
- weather grid-cell centre >5 km / >20 km from requested point;
- known soil/weather spatial-scale mismatch;
- unknown weather-model resolution when soil resolution is known.

## Why no LLM yet

An LLM would be allowed only *after* a structured `DecisionReport` exists. It must not be able to change:

- source provenance;
- deterministic issue codes;
- `PASS / CAUTION / ABSTAIN`;
- whether a field decision is blocked.

That is planned for a later bounded explanation layer with an evaluation set for unsupported inference and abstention failures.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected in V0.2: **10 tests passing**.

## Current limitations

1. G32 raw binary is not bundled in Git because it should remain traceable to the official government source.
2. V0.2 supports the verified/expected G32 TWD97 TM2 zone 121 path only; a changed CRS fails closed.
3. Auto-mapping is intentionally conservative. Unknown DBF fields remain unmapped until explicitly reviewed.
4. A 250 m soil grid is regional/contextual evidence, not a substitute for a fresh field sample.
5. Open-Meteo soil moisture is model-derived and is not treated as a local sensor measurement.
6. SoilTrust does not yet model crop, rooting depth, irrigation system, fertilizer history or field management.

## Project context

SoilTrust is being developed by **Sean Liu**, Department of Soil and Environmental Sciences, National Chung Hsing University, Taiwan, as an AI × SoilTech reliability project and as technical evidence for an overseas SoilTech learning/research proposal.
