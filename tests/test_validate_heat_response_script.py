"""CLI privacy and formatting tests for offline heat validation."""

from __future__ import annotations

import io
import json
from pathlib import Path

from scripts import validate_heat_response as script
from tests.test_heat_response_validation import (
    synthetic_research_bundle,
    synthetic_research_dataset,
)


def _mock_input(
    monkeypatch,
    payload: dict,
) -> None:
    encoded = json.dumps(payload)

    def fake_open(
        self: Path,
        mode: str = "r",
        encoding: str | None = None,
    ) -> io.StringIO:
        del self, mode, encoding
        return io.StringIO(encoded)

    monkeypatch.setattr(Path, "open", fake_open)


def _mock_inputs(
    monkeypatch,
    payloads: dict[str, dict],
) -> None:
    encoded = {
        path: json.dumps(payload)
        for path, payload in payloads.items()
    }

    def fake_open(
        self: Path,
        mode: str = "r",
        encoding: str | None = None,
    ) -> io.StringIO:
        del mode, encoding
        return io.StringIO(encoded[str(self)])

    monkeypatch.setattr(Path, "open", fake_open)


def test_cli_json_and_markdown_do_not_echo_activity_identity(
    monkeypatch,
    capsys,
) -> None:
    dataset = synthetic_research_dataset()
    private_id = dataset["records"][0]["activity"]["activity_id"]
    private_date = dataset["records"][0]["activity"]["date"]
    _mock_input(monkeypatch, dataset)

    assert script.main([
        "--input",
        "private-dataset.json",
        "--format",
        "json",
    ]) == 0
    json_output = capsys.readouterr().out
    assert private_id not in json_output
    assert private_date not in json_output
    assert '"value": "eligible_for_science_review"' in json_output

    assert script.main([
        "--input",
        "private-dataset.json",
        "--format",
        "markdown",
    ]) == 0
    markdown_output = capsys.readouterr().out
    assert private_id not in markdown_output
    assert private_date not in markdown_output
    assert "# #444 recommendation" in markdown_output
    assert "not WBGT" in markdown_output
    assert "Apply this result only through the accepted" in (
        markdown_output
    )
    assert "Run this pipeline" not in markdown_output
    assert (
        "private input contains activity IDs and dates"
        in markdown_output
    )


def test_cli_schema_error_is_clear_without_echoing_records(
    monkeypatch,
    capsys,
) -> None:
    dataset = synthetic_research_dataset()
    private_id = dataset["records"][0]["activity"]["activity_id"]
    dataset["schema_version"] = "private-invalid-schema"
    _mock_input(monkeypatch, dataset)

    assert script.main([
        "--input",
        "private-dataset.json",
    ]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert (
        "Input schema must be activity-research-dataset-v1"
        in captured.err
    )
    assert private_id not in captured.err


def test_cli_writes_only_when_output_is_explicit(
    monkeypatch,
    capsys,
) -> None:
    dataset = synthetic_research_dataset()
    _mock_input(monkeypatch, dataset)
    writes: dict[str, str] = {}

    def fake_write_text(
        self: Path,
        content: str,
        encoding: str | None = None,
    ) -> int:
        del encoding
        writes[str(self)] = content
        return len(content)

    monkeypatch.setattr(Path, "write_text", fake_write_text)

    assert script.main([
        "--input",
        "private-dataset.json",
        "--format",
        "markdown",
        "--output",
        "aggregate-report.md",
    ]) == 0
    assert capsys.readouterr().out == ""
    assert "aggregate-report.md" in writes
    assert "# Heat-response validation report" in (
        writes["aggregate-report.md"]
    )


def test_cli_repeated_inputs_create_complete_bundle_in_memory(
    monkeypatch,
    capsys,
) -> None:
    bundle = synthetic_research_bundle(activity_count=6, limit=2)
    inputs = {
        f"private-page-{index}.json": page
        for index, page in enumerate(bundle["pages"])
    }
    _mock_inputs(monkeypatch, inputs)
    arguments = ["--format", "json"]
    for path in inputs:
        arguments.extend(["--input", path])

    assert script.main(arguments) == 0

    report = json.loads(capsys.readouterr().out)
    complete = report["gates"]["complete_export"]
    assert complete["status"] == "pass"
    assert complete["observed"] == {
        "page_count": 3,
        "total": 6,
        "limit": 2,
        "record_count": 6,
        "offsets": [0, 2, 4],
        "complete": True,
    }
    assert report["dataset_integrity"]["verified_page_count"] == 3


def test_cli_accepts_one_prebuilt_bundle_file(
    monkeypatch,
    capsys,
) -> None:
    bundle = synthetic_research_bundle(activity_count=0, limit=50)
    _mock_input(monkeypatch, bundle)

    assert script.main([
        "--input",
        "private-bundle.json",
        "--format",
        "json",
    ]) == 0

    report = json.loads(capsys.readouterr().out)
    assert report["input_contract"]["received_schema_version"] == (
        "activity-research-dataset-bundle-v1"
    )
    assert report["gates"]["complete_export"]["status"] == "pass"
