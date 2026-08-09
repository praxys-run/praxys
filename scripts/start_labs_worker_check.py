"""Start a one-off Labs worker database/grant check in Azure."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def build_startup_check_template(
    template: dict[str, Any],
    *,
    container_name: str,
) -> dict[str, Any]:
    """Return an execution template that preserves config but changes argv."""
    execution_template = copy.deepcopy(template)
    containers = execution_template.get("containers")
    if not isinstance(containers, list):
        raise ValueError("Container Apps job template has no containers")
    container = next(
        (
            item
            for item in containers
            if isinstance(item, dict)
            and item.get("name") == container_name
        ),
        None,
    )
    if container is None:
        raise ValueError(
            f"Container Apps job has no {container_name!r} container"
        )
    container["command"] = ["python"]
    container["args"] = [
        "-m",
        "api.labs_worker",
        "--startup-check",
    ]
    return execution_template


def _read_live_template(
    resource_group: str,
    job_name: str,
) -> dict[str, Any]:
    result = subprocess.run(
        [
            "az",
            "containerapp",
            "job",
            "show",
            "--resource-group",
            resource_group,
            "--name",
            job_name,
            "--query",
            "properties.template",
            "--output",
            "json",
            "--only-show-errors",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    template = json.loads(result.stdout)
    if not isinstance(template, dict):
        raise ValueError("Container Apps job returned an invalid template")
    return template


def start_startup_check(
    resource_group: str,
    job_name: str,
    *,
    container_name: str,
) -> None:
    """Start the worker with a one-execution command override."""
    template = build_startup_check_template(
        _read_live_template(resource_group, job_name),
        container_name=container_name,
    )
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            delete=False,
        ) as handle:
            json.dump(template, handle)
            temp_path = Path(handle.name)
        subprocess.run(
            [
                "az",
                "containerapp",
                "job",
                "start",
                "--resource-group",
                resource_group,
                "--name",
                job_name,
                "--yaml",
                str(temp_path),
                "--only-show-errors",
            ],
            check=True,
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> int:
    """Parse CLI arguments and start the isolated startup check."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--container-name", default="labs-worker")
    args = parser.parse_args()
    start_startup_check(
        args.resource_group,
        args.job_name,
        container_name=args.container_name,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
