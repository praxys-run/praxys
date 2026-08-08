"""Tests for the sitespeed.io baseline analyzer."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_baseline import extract_metrics


def _entry(
    pageref: str,
    url: str,
    *,
    body_size: int,
    wait: int,
    receive: int,
) -> dict[str, object]:
    return {
        "pageref": pageref,
        "request": {"url": url},
        "response": {
            "bodySize": body_size,
            "content": {"size": body_size},
            "httpVersion": "h2",
        },
        "timings": {"wait": wait, "receive": receive},
    }


def test_extract_metrics_reports_median_across_iterations(tmp_path: Path) -> None:
    """The analyzer should not report the first Sitespeed iteration."""
    pages = []
    entries = []
    for index, (fcp, lcp, ttfb) in enumerate(
        [(100, 1000, 10), (300, 3000, 30), (200, 2000, 20)],
        start=1,
    ):
        page_id = f"page_{index}"
        pages.append(
            {
                "id": page_id,
                "pageTimings": {"_domInteractiveTime": fcp + 50},
                "_googleWebVitals": {
                    "firstContentfulPaint": fcp,
                    "largestContentfulPaint": lcp,
                    "ttfb": ttfb,
                },
            }
        )
        entries.extend(
            [
                _entry(
                    page_id,
                    "https://www.praxys.run/assets/app.js",
                    body_size=index * 1024,
                    wait=5,
                    receive=5,
                ),
                _entry(
                    page_id,
                    "https://api.praxys.run/api/today",
                    body_size=index * 100,
                    wait=index * 10,
                    receive=index,
                ),
            ]
        )

    har_path = tmp_path / "browsertime.har"
    har_path.write_text(json.dumps({"log": {"pages": pages, "entries": entries}}))

    metrics = extract_metrics(tmp_path)

    assert metrics is not None
    assert metrics["fcp_ms"] == 200
    assert metrics["lcp_ms"] == 2000
    assert metrics["ttfb_ms"] == 20
    assert metrics["static_kb"] == 2.0
    assert metrics["num_requests"] == 2
    assert metrics["num_api"] == 1
    assert metrics["api_p50_ms"] == 22
