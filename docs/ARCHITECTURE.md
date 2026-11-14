# SoilTrust V0.2 Architecture

## Design invariant

**No explanation layer may upgrade the evidence state.**

If the deterministic layer says `ABSTAIN`, a later AI layer may explain why, but it cannot convert that state into a recommendation.

## Pipeline

```mermaid
flowchart TD
    G[MOA G32 SHP/DBF] --> H[SHA-256 + source manifest]
    H --> C[TWD97 TM2 / schema normalization]
    C --> S[Nearest 250 m soil grid]

    O[Open-Meteo] --> W[Current soil-state + 7-day rain/ET0]

    S --> P[Provenance bundle]
    W --> P
    P --> Q[Deterministic quality rules]
    Q --> D[Structured DecisionReport]
    D --> A{PASS / CAUTION / ABSTAIN}
    A --> E[Bounded explanation]
    E --> N[Next evidence / measurement needed]
```

## Trust boundaries

### G32

Trusted for: official public-source identity, declared 250 m grid, published chemistry attributes when correctly mapped.

Not automatically trusted for: current field state, exact within-field variability, unknown sample date, crop-specific recommendations.

### Open-Meteo

Trusted for: a reproducible public model-data API response and declared variable semantics.

Not automatically trusted for: local sensor truth, exact field-scale soil moisture, a fixed spatial resolution when the response does not identify the model/resolution.

### SoilTrust

Trusted for: deterministic checks implemented in source code, provenance capture, fail-closed behavior.

Not proof of: agronomic efficacy or decision correctness.
