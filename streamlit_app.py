"""SoilTrust v0.3 — interactive, evidence-aware research demonstration.

Only presentation and demonstration orchestration live here. All decisions,
scores and issue codes come from the existing V0.2 Python engine.
"""
from __future__ import annotations

import json
from dataclasses import asdict

import streamlit as st

from soiltrust.demo import SCENARIOS, evaluate_demo
from soiltrust.models import DecisionReport


st.set_page_config(
    page_title="SoilTrust | Research Demo",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("SoilTrust")
st.caption("Evidence-aware Soil Intelligence · Research Prototype · v0.3")
st.info(
    "RESEARCH DEMONSTRATION — Soil values are synthetic fixtures, not local "
    "measurements or official G32 observations. This prototype does not provide "
    "fertilizer, irrigation, or field-management recommendations."
)


def _provenance_table(record: object | None, name: str) -> None:
    st.subheader(name)
    if record is None:
        st.error("Unavailable: there is no usable record for this evaluation.")
        return

    provenance = record.provenance
    st.table(
        [
            {"Property": "Source", "Value": provenance.source_name},
            {"Property": "Type", "Value": provenance.source_type},
            {"Property": "Synthetic fixture", "Value": "YES" if record.demo_fixture else "NO"},
            {"Property": "Observation time", "Value": provenance.observation_time or "Unknown"},
            {"Property": "Retrieved at", "Value": provenance.retrieved_at},
            {
                "Property": "Spatial resolution",
                "Value": (
                    f"{provenance.spatial_resolution_m:g} m"
                    if provenance.spatial_resolution_m is not None
                    else "Unknown — not inferred"
                ),
            },
            {"Property": "Temporal resolution", "Value": provenance.temporal_resolution or "Unknown"},
            {"Property": "Licence", "Value": provenance.license or "Not supplied"},
            {"Property": "Source URL", "Value": provenance.source_url or "Not supplied"},
        ]
    )
    if provenance.notes:
        st.caption(provenance.notes)
    if provenance.source_url.startswith("https://"):
        st.markdown(f"[Open source reference]({provenance.source_url})")
    with st.expander(f"Full {name.lower()} record (including raw attributes)"):
        st.json(asdict(record))


with st.sidebar:
    st.header("Interactive Evaluation")
    st.caption("Select a synthetic scenario or enter WGS84 coordinates.")
    scenario = st.selectbox("Scenario", list(SCENARIOS.keys()))
    latitude_default, longitude_default = SCENARIOS[scenario]
    with st.form("evaluation_form"):
        latitude = st.number_input(
            "Latitude", min_value=-90.0, max_value=90.0,
            value=latitude_default, format="%.4f",
        )
        longitude = st.number_input(
            "Longitude", min_value=-180.0, max_value=180.0,
            value=longitude_default, format="%.4f",
        )
        weather_label = st.radio(
            "Weather input",
            ["Offline synthetic fixture", "Open-Meteo live model API"],
            help=(
                "Live weather is model-derived, not a field sensor. "
                "Soil input remains synthetic in either mode."
            ),
        )
        submitted = st.form_submit_button("Run evaluation", type="primary")

    st.caption(
        "Nearest synthetic CSV record is selected for every coordinate. "
        "When the location is far away, the existing soil.distance rule "
        "flags the mismatch. This is not a global soil-data lookup."
    )

weather_mode = "fixture" if weather_label.startswith("Offline") else "open-meteo"

if submitted or "soiltrust_latest" not in st.session_state:
    with st.spinner("Running SoilTrust deterministic evaluation..."):
        try:
            report, weather_error = evaluate_demo(
                latitude, longitude, weather_mode
            )
        except Exception as exc:
            st.error("Evaluation failed. No decision report was issued.")
            st.caption(f"Diagnostic: {type(exc).__name__}: {str(exc)[:240]}")
            st.stop()
        st.session_state["soiltrust_latest"] = {
            "report": report,
            "weather_error": weather_error,
            "weather_mode": weather_mode,
        }

result = st.session_state["soiltrust_latest"]
report: DecisionReport = result["report"]

if result["weather_error"]:
    st.warning(
        "Live weather request failed; no synthetic fallback was substituted. "
        "The original engine reports missing weather and abstains. "
        f"Diagnostic: {result['weather_error']}"
    )

st.subheader("Demonstration Result")
status_col, score_col, blocked_col = st.columns(3)
status_col.metric("Decision state", report.status)
score_col.metric("Rule-based reliability score", f"{report.reliability_score}/100")
blocked_col.metric(
    "Field-level decision", "NOT ALLOWED" if not report.can_make_field_decision else "RULES CLEAR"
)

if report.status == "ABSTAIN":
    st.error("ABSTAIN — field-level recommendation is blocked by the evaluation rules.")
elif report.status == "CAUTION":
    st.warning("CAUTION — limitations prevent unqualified field interpretation.")
else:
    st.success(
        "PASS — no implemented reliability rule was triggered. "
        "This is NOT proof of agronomic validity or permission to issue advice."
    )

st.write(report.explanation)
st.caption(
    f"Evaluated location: {report.requested_location['latitude']:.4f}, "
    f"{report.requested_location['longitude']:.4f} (WGS84) · "
    f"Generated: {report.generated_at} · "
    f"Weather mode: {result['weather_mode']}"
)
st.caption(
    "The reliability score is a deterministic penalty score, not a calibrated "
    "probability, confidence interval, or measurement of prediction accuracy."
)

reliability_tab, evidence_tab, research_tab = st.tabs(
    ["Reliability report", "Evidence & provenance", "Reproducible research"]
)

with reliability_tab:
    st.subheader("Deterministic rules and evidence")
    st.caption(
        "All rule codes and severity levels below come directly from "
        "soiltrust.quality.evaluate_quality; they are not manually authored UI states."
    )
    st.table(
        [
            {
                "Code": issue.code,
                "Severity": issue.severity.upper(),
                "Description": issue.message,
            }
            for issue in report.issues
        ]
    )
    with st.expander("Per-rule supporting values"):
        for issue in report.issues:
            if issue.evidence:
                st.write(f"{issue.code}:")
                st.json(issue.evidence)
    st.subheader("Next evidence needed")
    for step in report.next_measurements:
        st.write(f"- {step}")

with evidence_tab:
    soil_col, weather_col = st.columns(2)
    with soil_col:
        _provenance_table(report.soil, "Soil evidence")
    with weather_col:
        _provenance_table(report.weather, "Weather / model evidence")
    st.warning(
        "Dataset publication dates are not sampling dates. Unknown observation "
        "times or model-grid resolutions remain unknown. An API response is not "
        "equivalent to a locally calibrated observation."
    )

with research_tab:
    st.subheader("Download the evaluated DecisionReport")
    st.download_button(
        "Download JSON report",
        data=json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        file_name="soiltrust_v0.3_decision_report.json",
        mime="application/json",
    )
    st.caption(
        "The JSON contains the original V0.2 schema: inputs, status, score, "
        "issue codes, provenance, evidence, and next measurements."
    )
    st.subheader("Reproduce with the Python CLI")
    st.code(
        "PYTHONPATH=src python -m soiltrust.cli report "
        f"--lat {report.requested_location['latitude']:.4f} "
        f"--lon {report.requested_location['longitude']:.4f} "
        "--soil-source normalized --soil-csv data/demo_taiwan_soil.csv "
        f"--weather {result['weather_mode']}",
        language="bash",
    )
    st.code(
        "PYTHONPATH=src python -m unittest discover -s tests -v",
        language="bash",
    )
    st.markdown(
        "[GitHub source and tests](https://github.com/kodlbegiko/SoilTrust) · "
        "[Official Taiwan G32 dataset](https://data.gov.tw/dataset/112848) · "
        "[Open-Meteo documentation](https://open-meteo.com/en/docs)"
    )
    st.info(
        "For a fully offline meeting, keep examples/report.html as a fallback. "
        "Live Open-Meteo calls require network access; the offline fixture does not."
    )
