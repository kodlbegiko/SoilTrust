# SoilTrust v0.3 — Interactive Research Demo

**Scope:** a Streamlit presentation layer on top of the unchanged SoilTrust v0.2
quality engine. It is a research prototype, not a fertilizer, irrigation or
precision-agriculture recommendation tool.

## What the demo actually does

1. Enter WGS84 latitude and longitude, or choose a named test scenario.
2. Choose the bundled **synthetic** weather fixture or request **live
   model-derived** conditions from Open-Meteo.
3. The app calls soiltrust.demo.evaluate_demo, which invokes the repository's
   NormalizedTaiwanSoilCSVSource.nearest, weather-source adapter and
   **soiltrust.pipeline.build_report**. The report is NOT a static mock.
4. Inspect PASS, CAUTION or ABSTAIN, numerical rule-based score, each
   original rule code, evidence values and next required measurements.
5. Inspect full soil and weather provenance and download the original
   DecisionReport.to_dict() JSON schema.
6. Reproduce the deterministic rule codes with the CLI and unit tests.

The score deducts 35 points per critical issue and 12 per warning, clipped to
0–100. **This is not a statistical confidence/probability estimate.**

### Important provenance boundary

data/demo_taiwan_soil.csv contains only three synthetic soil records.
The nearest **synthetic fixture** is selected for an arbitrary coordinate.
Far-away requests are flagged by the existing distance rules. Selecting
another latitude/longitude does **not** retrieve actual G32 site measurements.

Open-Meteo supplies live *gridded model* conditions, not field sensor data.
The soil data stay synthetic when live weather is selected. If the live request
fails, the app passes weather=None into the existing evaluator, which emits
weather.missing and ABSTAIN. **There is no hidden fallback masquerading
as live data.**

The official MOA G32 binary is not bundled or downloaded automatically by
the public app. To evaluate original G32 data, follow the existing CLI
fetch-g32 / inspect-g32 / report workflow in the main README and verify
its schema, hash and sampling-date limitations.

## Local startup

Requires Python 3.11 or newer.

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    streamlit run streamlit_app.py

Windows activation: .venv\Scripts\activate

Check the unchanged core and new adapter:

    PYTHONPATH=src python -m unittest discover -s tests -v

The offline demo needs no API key and no network connection after installing
the dependencies.

## Streamlit Community Cloud deployment

1. Use the v0.3 code on the main branch and confirm GitHub Actions tests pass.
2. Sign in at https://share.streamlit.io with the GitHub account that can
   access https://github.com/kodlbegiko/SoilTrust .
3. Select **Create app** → existing repository and set:
   - Repository: kodlbegiko/SoilTrust
   - Branch: main
   - Main file path: streamlit_app.py
   - Python version: 3.11 or newer (as supported by the platform)
4. Deploy. Community Cloud assigns the public streamlit.app
   address; do not assume a public URL until successful deployment and testing.
5. Visit the public app in a private browser window. Verify default synthetic
   result is ABSTAIN, changing coordinates reruns the engine, downloads work,
   and simulated upstream errors do not become PASS.

Keep examples/report.html locally as an offline backup for a meeting.
Community Cloud can sleep or cold-start, and optional live calls can fail.
For scientific claims, show issue codes, provenance, source and tests rather
than treating the score as an empirically validated uncertainty metric.

## Deliberately deferred

- Loading arbitrary third-party CSVs from public uploads.
- Official G32 live ingestion and unverified field-level inference in the web UI.
- AI-generated agronomic recommendations.
- Authentication, persistence, field-data storage and model training.
- Interpreting a rule PASS as agronomic suitability.

These capabilities require data contracts, security controls, validation and
real-world testing beyond this research demo.
