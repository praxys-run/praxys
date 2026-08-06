"""Run the private heat-response validation pipeline without fetching data.

The input must be a local JSON export using
``activity-research-dataset-v1``. By default the aggregate report is written
to stdout; no athlete data or report file is written unless ``--output`` is
explicitly supplied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.heat_response_validation import (  # noqa: E402
    HeatValidationInputError,
    render_heat_response_markdown,
    validate_heat_response,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the offline validation command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Private activity-research-dataset-v1 JSON file.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Aggregate report format (default: json).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional report path. Without it, output goes to stdout.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate one local dataset and emit only the aggregate report."""
    args = build_parser().parse_args(argv)
    try:
        with args.input.open("r", encoding="utf-8") as handle:
            dataset = json.load(handle)
        report = validate_heat_response(dataset)
    except OSError:
        print("error: unable to read the input file", file=sys.stderr)
        return 2
    except json.JSONDecodeError:
        print("error: input is not valid JSON", file=sys.stderr)
        return 2
    except HeatValidationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError:
        print(
            "error: validation configuration or numeric input is invalid",
            file=sys.stderr,
        )
        return 2

    rendered = (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.format == "json"
        else render_heat_response_markdown(report)
    )
    if args.output is None:
        sys.stdout.write(rendered)
        return 0
    try:
        args.output.write_text(rendered, encoding="utf-8")
    except OSError:
        print("error: unable to write the output file", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
