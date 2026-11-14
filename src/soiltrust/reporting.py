from __future__ import annotations

import html
import json
from pathlib import Path

from soiltrust.models import DecisionReport


def write_json(report: DecisionReport, path: str | Path) -> None:
    Path(path).write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "n/a"
    return f"{value}{suffix}"


def write_html(report: DecisionReport, path: str | Path) -> None:
    d = report.to_dict()
    issue_rows = "".join(
        f"<tr><td>{html.escape(i['severity'].upper())}</td><td><code>{html.escape(i['code'])}</code></td><td>{html.escape(i['message'])}</td></tr>"
        for i in d["issues"]
    )
    next_items = "".join(f"<li>{html.escape(x)}</li>" for x in d["next_measurements"])
    soil = d["soil"] or {}
    weather = d["weather"] or {}
    status_class = d["status"].lower()
    raw = html.escape(json.dumps(d, indent=2, ensure_ascii=False))
    soil_source = ((soil.get("provenance") or {}).get("source_name") or "n/a")
    weather_source = ((weather.get("provenance") or {}).get("source_name") or "n/a")
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>SoilTrust V0.2 report</title>
<style>
body {{ font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; margin: 0; background: #f6f8fa; color: #17212b; }}
main {{ max-width: 1040px; margin: 36px auto; padding: 0 20px 48px; }}
header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-start; }}
h1 {{ margin:0; font-size:32px; }} .tag {{ color:#506273; margin-top:6px; }}
.badge {{ padding:10px 16px; border-radius:999px; font-weight:700; }}
.badge.abstain {{ background:#ffe7e7; color:#9b1c1c; }} .badge.caution {{ background:#fff2cc; color:#7a5700; }} .badge.pass {{ background:#daf5e4; color:#146c38; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:14px; margin:22px 0; }}
.card {{ background:white; border:1px solid #dfe5eb; border-radius:14px; padding:18px; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
.k {{ color:#687887; font-size:12px; text-transform:uppercase; letter-spacing:.05em; }} .v {{ font-size:22px; font-weight:700; margin-top:6px; }}
.source {{ font-size:13px; line-height:1.45; margin-top:8px; color:#506273; overflow-wrap:anywhere; }}
table {{ width:100%; border-collapse:collapse; background:white; }} th,td {{ border-bottom:1px solid #e7ebef; padding:10px; text-align:left; vertical-align:top; font-size:14px; }}
section {{ margin-top:22px; }} h2 {{ font-size:18px; }} code {{ font-size:12px; }}
pre {{ white-space:pre-wrap; background:#0f1720; color:#e5edf5; padding:16px; border-radius:12px; overflow:auto; font-size:12px; }}
.notice {{ border-left:4px solid #577590; padding:12px 14px; background:#eef4f8; }}
</style>
</head>
<body><main>
<header><div><h1>SoilTrust V0.2</h1><div class="tag">Reliability before recommendation</div></div><div class="badge {status_class}">{html.escape(d['status'])} · {d['reliability_score']}/100</div></header>
<section class="notice">{html.escape(d['explanation'])}</section>
<div class="grid">
<div class="card"><div class="k">Requested location</div><div class="v">{d['requested_location']['latitude']:.4f}, {d['requested_location']['longitude']:.4f}</div></div>
<div class="card"><div class="k">Soil pH</div><div class="v">{html.escape(_fmt(soil.get('ph')))}</div></div>
<div class="card"><div class="k">Organic matter</div><div class="v">{html.escape(_fmt(soil.get('organic_matter_pct'), '%'))}</div></div>
<div class="card"><div class="k">CEC</div><div class="v">{html.escape(_fmt(soil.get('cec_cmol_kg'), ' cmol+/kg'))}</div></div>
<div class="card"><div class="k">Model soil moisture</div><div class="v">{html.escape(_fmt(weather.get('soil_moisture_m3_m3'), ' m³/m³'))}</div></div>
<div class="card"><div class="k">7-day precipitation</div><div class="v">{html.escape(_fmt(weather.get('precipitation_7d_mm'), ' mm'))}</div></div>
<div class="card"><div class="k">7-day ET₀</div><div class="v">{html.escape(_fmt(weather.get('et0_7d_mm'), ' mm'))}</div></div>
<div class="card"><div class="k">Field decision</div><div class="v">{'Allowed' if d['can_make_field_decision'] else 'Blocked'}</div></div>
</div>
<section><h2>Evidence sources</h2><div class="grid"><div class="card"><div class="k">Soil</div><div class="source">{html.escape(soil_source)}</div></div><div class="card"><div class="k">Weather / soil-state model</div><div class="source">{html.escape(weather_source)}</div></div></div></section>
<section><h2>Quality & evidence checks</h2><table><thead><tr><th>Severity</th><th>Rule</th><th>Finding</th></tr></thead><tbody>{issue_rows}</tbody></table></section>
<section><h2>What evidence is needed next?</h2><ul>{next_items}</ul></section>
<section><h2>Raw structured report</h2><pre>{raw}</pre></section>
</main></body></html>"""
    Path(path).write_text(document, encoding="utf-8")
