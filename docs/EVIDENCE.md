# Evidence and Claim Boundaries

## Claims SoilTrust V0.2 can support

- The Taiwan MOA G32 dataset is officially published as a 250 m × 250 m topsoil-fertility grid.
- A local G32 archive can be hashed, inspected and queried reproducibly.
- TWD97 / TM2 zone 121 coordinates can be converted to WGS84 without a hidden GIS service.
- SoilTrust can expose missing chemistry fields, unknown dates, spatial distance and model-grid limitations.
- Open-Meteo can provide current model soil moisture/temperature plus precipitation and ET0 context.
- The same inputs produce deterministic issue codes and decision state.

## Claims SoilTrust V0.2 does not support

- “This field needs X kg/ha fertilizer.”
- “This model soil-moisture value equals an in-field sensor reading.”
- “A 250 m map cell represents every point inside the field.”
- “PASS proves the agronomic recommendation is correct.”
- “G32 publication/update date equals the soil sampling date.”

## External evidence still required for a production SoilTech system

- field sampling / laboratory validation;
- sensor calibration and drift studies;
- crop and growth-stage context;
- field management history;
- evaluation against independent outcomes;
- operational monitoring for missing data, device faults and distribution shift.
