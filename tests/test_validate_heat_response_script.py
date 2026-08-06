"""CLI privacy and formatting tests for offline heat validation."""

from __future__ import annotations

import io
import json
from pathlib import Path

from scripts import validate_heat_response as script
from tests.test_heat_response_validation import synthetic_research_dataset


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
