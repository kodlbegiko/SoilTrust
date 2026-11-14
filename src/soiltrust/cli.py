from __future__ import annotations

import argparse
import json
from pathlib import Path

from soiltrust.pipeline import build_report
from soiltrust.reporting import write_html, write_json
from soiltrust.sources.fixture_weather import FixtureWeatherSource
from soiltrust.sources.g32 import G32ShapefileSource, fetch_g32, parse_field_map
from soiltrust.sources.local_soil import NormalizedTaiwanSoilCSVSource
from soiltrust.sources.open_meteo import OpenMeteoForecastSource


def _add_report_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lat", type=float, required=True, help="WGS84 latitude")
    parser.add_argument("--lon", type=float, required=True, help="WGS84 longitude")
    parser.add_argument("--soil-source", choices=["normalized", "g32"], default="normalized")
    parser.add_argument("--soil-csv", default="data/demo_taiwan_soil.csv", help="Normalized soil CSV")
    parser.add_argument("--g32", help="Official G32 .zip, .shp, or extracted directory")
    parser.add_argument("--g32-field-map", default="", help="Explicit DBF mapping, e.g. ph=PH,organic_matter=OM,cec=CEC")
    parser.add_argument("--weather", choices=["fixture", "open-meteo"], default="fixture")
    parser.add_argument("--json-out", default="examples/report.json")
    parser.add_argument("--html-out", default="examples/report.html")


def _report(args: argparse.Namespace) -> int:
    if args.soil_source == "g32":
        if not args.g32:
            raise SystemExit("--g32 is required when --soil-source=g32")
        soil_source = G32ShapefileSource(args.g32, field_map=parse_field_map(args.g32_field_map))
    else:
        soil_source = NormalizedTaiwanSoilCSVSource(args.soil_csv)
    soil = soil_source.nearest(args.lat, args.lon)

    if args.weather == "open-meteo":
        try:
            weather = OpenMeteoForecastSource().fetch(args.lat, args.lon)
        except Exception as exc:
            print(f"Open-Meteo fetch failed: {exc}")
            weather = None
    else:
        weather = FixtureWeatherSource().fetch(args.lat, args.lon)

    report = build_report(args.lat, args.lon, soil, weather)
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.html_out).parent.mkdir(parents=True, exist_ok=True)
    write_json(report, args.json_out)
    write_html(report, args.html_out)
    print(json.dumps({
        "status": report.status,
        "reliability_score": report.reliability_score,
        "can_make_field_decision": report.can_make_field_decision,
        "soil_source": soil.provenance.source_name if soil else None,
        "weather_source": weather.provenance.source_name if weather else None,
        "issues": [{"code": i.code, "severity": i.severity} for i in report.issues],
        "json_report": args.json_out,
        "html_report": args.html_out,
    }, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SoilTrust V0.2 — reliability before recommendation")
    sub = parser.add_subparsers(dest="command")

    report_parser = sub.add_parser("report", help="Build a SoilTrust decision report")
    _add_report_args(report_parser)

    fetch_parser = sub.add_parser("fetch-g32", help="Download the official MOA G32 resource with a provenance manifest")
    fetch_parser.add_argument("--out", default="data/raw/g32")

    inspect_parser = sub.add_parser("inspect-g32", help="Inspect the official G32 DBF schema and auto-detected mappings")
    inspect_parser.add_argument("--g32", required=True)
    inspect_parser.add_argument("--g32-field-map", default="")

    args = parser.parse_args()
    if args.command == "fetch-g32":
        print(json.dumps(fetch_g32(args.out), indent=2, ensure_ascii=False))
        return 0
    if args.command == "inspect-g32":
        source = G32ShapefileSource(args.g32, field_map=parse_field_map(args.g32_field_map))
        print(json.dumps(source.inspect(), indent=2, ensure_ascii=False))
        return 0
    if args.command == "report":
        return _report(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
