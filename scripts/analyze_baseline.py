#!/usr/bin/env python3
"""Parse a sitespeed.io baseline directory into populated TEMPLATE.md rows.

Walks docs/perf-baselines/<date>-<sha>/ for cells named
`s<N>-<probe>-<device>/`, reads the sitespeed.io HAR inside each cell, and
prints a markdown table section per scenario that can be pasted into
TEMPLATE.md.

Everything we need is inside the HAR: sitespeed.io embeds one page record per
iteration with `pageTimings` (FCP/LCP/TTI) and `_googleWebVitals`
(CLS/TTFB/FID/TBT). The analyzer reports the median across those page records,
so we don't need a separate `browsertime.json` — it isn't written to disk by
default in v39+ anyway.

Usage:
    python scripts/analyze_baseline.py --baseline-dir docs/perf-baselines/2026-04-24-abc1234
    python scripts/analyze_baseline.py --baseline-dir ... --output-format json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import zipfile
from pathlib import Path
from typing import Any


CELL_RE = re.compile(r"^s(\d)-(.+)-(desktop|mobile)$")

SCENARIO_TITLES = {
    "s1": "S1 — Cold first load, Today page (via login)",
    "s2": "S2 — Cold first load, Training page (via login)",
    "s3": "S3 — Warm repeat visit, Today page",
    "s4": "S4 — Anonymous Landing page",
}

COLUMNS = [
    ("fcp_ms", "FCP (ms)"),
    ("lcp_ms", "LCP (ms)"),
    ("tti_ms", "TTI (ms)"),
    ("ttfb_ms", "HTML TTFB"),
    ("static_kb", "Static KB"),
    ("api_kb", "API KB"),
    ("num_requests", "# reqs"),
    ("num_api", "# API"),
    ("api_p50_ms", "API p50"),
    ("api_p95_ms", "API p95"),
    ("protocol", "Protocol"),
    ("font_css_ttfb", "Font CSS TTFB"),
]


def find_har(cell_dir: Path) -> Path | None:
    paths = list(cell_dir.rglob("browsertime.har")) + list(cell_dir.rglob("browsertime.har.zip"))
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def load_har(har_path: Path) -> dict[str, Any]:
    if har_path.suffix == ".zip":
        with zipfile.ZipFile(har_path) as z:
            inner = next((n for n in z.namelist() if n.endswith(".har")), None)
            if inner is None:
                raise ValueError(f"No .har file inside {har_path}")
            with z.open(inner) as f:
                return json.load(f)
    with har_path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_metrics(cell_dir: Path) -> dict[str, Any] | None:
    har_path = find_har(cell_dir)
    if har_path is None:
        return None
    har = load_har(har_path)
    log = har.get("log", {})
    pages = log.get("pages", [])
    entries = log.get("entries", [])

    entries_by_page: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        entries_by_page.setdefault(entry.get("pageref", ""), []).append(entry)

    runs: list[dict[str, Any]] = []
    for page in pages:
        page_timings = page.get("pageTimings", {}) or {}
        gwv = page.get("_googleWebVitals", {}) or {}
        page_entries = entries_by_page.get(page.get("id", ""), [])

        # Sitespeed.io underscores internal fields in the HAR; stable public
        # names live on _googleWebVitals. Fall back between them for safety.
        fcp = gwv.get("firstContentfulPaint") or page_timings.get("_firstContentfulPaint")
        lcp = gwv.get("largestContentfulPaint") or page_timings.get("_largestContentfulPaint")
        # TTI isn't a HAR field — use domInteractiveTime as the closest proxy.
        tti = page_timings.get("_domInteractiveTime")
        api_entries = [
            e for e in page_entries if "/api/" in (e.get("request") or {}).get("url", "")
        ]

        static_bytes = 0
        api_bytes = 0
        for entry in page_entries:
            url = (entry.get("request") or {}).get("url", "")
            size = ((entry.get("response") or {}).get("content") or {}).get("size") or 0
            transferred = (entry.get("response") or {}).get("bodySize")
            if transferred is None or transferred < 0:
                transferred = size
            if "/api/" in url:
                api_bytes += max(0, transferred)
            else:
                static_bytes += max(0, transferred)

        api_durations = []
        for entry in api_entries:
            timings = entry.get("timings") or {}
            wait = timings.get("wait") or 0
            receive = timings.get("receive") or 0
            if wait >= 0 and receive >= 0:
                api_durations.append(wait + receive)

        api_p50 = statistics.median(api_durations) if api_durations else None
        api_p95: float | None = None
        if len(api_durations) >= 2:
            api_p95 = statistics.quantiles(api_durations, n=20, method="inclusive")[-1]
        elif api_durations:
            api_p95 = api_durations[0]

        font_css_ttfb: Any = None
        for entry in page_entries:
            url = (entry.get("request") or {}).get("url", "")
            if "fonts.googleapis.com" in url:
                wait = (entry.get("timings") or {}).get("wait")
                font_css_ttfb = "timeout" if wait is None or wait < 0 else round(wait)
                break

        runs.append(
            {
                "fcp_ms": fcp,
                "lcp_ms": lcp,
                "tti_ms": tti,
                "ttfb_ms": gwv.get("ttfb"),
                "static_kb": static_bytes / 1024,
                "api_kb": api_bytes / 1024,
                "num_requests": len(page_entries),
                "num_api": len(api_entries),
                "api_p50_ms": api_p50,
                "api_p95_ms": api_p95,
                "font_css_ttfb": font_css_ttfb,
            }
        )

    if not runs:
        return None

    def median_for(key: str) -> float | None:
        values = [run[key] for run in runs if isinstance(run.get(key), (int, float))]
        return statistics.median(values) if values else None

    protocols = {((e.get("response") or {}).get("httpVersion") or "").lower() for e in entries}
    protocols.discard("")
    if any("3" in p for p in protocols):
        protocol: Any = "h3"
    elif any("2" in p for p in protocols):
        protocol = "h2"
    elif protocols:
        protocol = sorted(protocols)[0]
    else:
        protocol = "?"

    font_values = [run["font_css_ttfb"] for run in runs if run["font_css_ttfb"] is not None]
    if "timeout" in font_values:
        font_css_ttfb: Any = "timeout"
    else:
        numeric_font_values = [value for value in font_values if isinstance(value, (int, float))]
        font_css_ttfb = (
            round(statistics.median(numeric_font_values)) if numeric_font_values else None
        )

    # Zero is meaningful signal here, not missing data: S4 (anonymous
    # Landing) legitimately has 0 API requests / 0 API KB, and that's
    # what tells us the anonymous route isn't calling /api/*. So render
    # zeros as 0, not em-dash.
    return {
        "fcp_ms": round(value) if (value := median_for("fcp_ms")) is not None else None,
        "lcp_ms": round(value) if (value := median_for("lcp_ms")) is not None else None,
        "tti_ms": round(value) if (value := median_for("tti_ms")) is not None else None,
        "ttfb_ms": round(value) if (value := median_for("ttfb_ms")) is not None else None,
        "static_kb": round(median_for("static_kb") or 0, 1),
        "api_kb": round(median_for("api_kb") or 0, 1),
        "num_requests": round(median_for("num_requests") or 0),
        "num_api": round(median_for("num_api") or 0),
        "api_p50_ms": (
            round(value) if (value := median_for("api_p50_ms")) is not None else None
        ),
        "api_p95_ms": (
            round(value) if (value := median_for("api_p95_ms")) is not None else None
        ),
        "protocol": protocol,
        "font_css_ttfb": font_css_ttfb,
    }


def render_markdown(results: dict[str, dict[str, Any] | None]) -> str:
    by_scenario: dict[str, list[tuple[str, str, dict[str, Any] | None]]] = {}
    for cell_name, metrics in results.items():
        m = CELL_RE.match(cell_name)
        assert m is not None
        scenario = f"s{m.group(1)}"
        probe = m.group(2)
        device = m.group(3).capitalize()
        by_scenario.setdefault(scenario, []).append((probe, device, metrics))

    header = "| Probe | Device | " + " | ".join(label for _, label in COLUMNS) + " |"
    separator = "|" + "---|" * (len(COLUMNS) + 2)

    out: list[str] = []
    for scenario in sorted(by_scenario):
        title = SCENARIO_TITLES.get(scenario, scenario.upper())
        out.append(f"### {title}\n")
        out.append(header)
        out.append(separator)
        for probe, device, metrics in by_scenario[scenario]:
            cells: list[str] = []
            for key, _ in COLUMNS:
                v = metrics.get(key) if metrics else None
                cells.append("—" if v is None else str(v))
            out.append(f"| {probe} | {device} | " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-dir", required=True, type=Path)
    parser.add_argument("--output-format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    baseline_dir: Path = args.baseline_dir
    if not baseline_dir.is_dir():
        print(f"Error: baseline dir not found: {baseline_dir}", file=sys.stderr)
        return 1

    cells = sorted(p for p in baseline_dir.iterdir() if p.is_dir() and CELL_RE.match(p.name))
    if not cells:
        print(
            f"Error: no cell directories matching s<N>-<probe>-<desktop|mobile> in {baseline_dir}",
            file=sys.stderr,
        )
        return 1

    results: dict[str, dict[str, Any] | None] = {}
    for cell in cells:
        results[cell.name] = extract_metrics(cell)

    if args.output_format == "json":
        print(json.dumps(results, indent=2))
    else:
        print(render_markdown(results))

    missing = [name for name, v in results.items() if v is None]
    if missing:
        print(
            f"\nWarning: no sitespeed.io output found in {len(missing)} cell(s): {', '.join(missing)}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
