# G32 Ingestion Contract

## Official source

Dataset: `G32 — 全台農田平地表土層土壤網格肥力資訊`

Dataset page: <https://data.gov.tw/dataset/112848>

Metadata endpoint: <https://data.moa.gov.tw/api/FileToJson.ashx?DataId=G32&DataTable=OpenDataList>

The metadata endpoint currently identifies a resource named `全台平地農田表土層土壤網格肥力資訊_TWD9`.

## Fail-closed rules

1. Binary source is hashed before use.
2. A missing SHP/DBF pair is an error.
3. V0.2 accepts only `EPSG:3826` for the G32 path.
4. A transformed coordinate outside a conservative Taiwan envelope is an error.
5. Unknown DBF chemistry fields are not semantically guessed.
6. Publication/update date is not treated as sample date.

## Normalized fields

| Normalized field | Meaning | Required for richer report |
|---|---|---|
| `record_id` | source grid identifier | no |
| `latitude/longitude` | grid-cell centre in WGS84 | yes |
| `ph` | soil pH | recommended |
| `organic_matter_pct` | organic matter % | recommended |
| `cec_cmol_kg` | CEC cmol+/kg | recommended |
| `observed_on` | actual observation/sample date | optional but strongly preferred |

All original DBF attributes remain in `source_attributes` in the JSON report for inspection.
