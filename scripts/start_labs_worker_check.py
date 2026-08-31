"""Start a one-off Labs worker database/grant check in Azure."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import tempfile
import time
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
) -> str:
    """Start the check, wait for a terminal success, and return its ID."""
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
        started = subprocess.run(
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
                "--output",
                "json",
                "--only-show-errors",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(started.stdout)
        execution_name = (
            payload.get("name")
            if isinstance(payload, dict)
            else None
        )
        if not isinstance(execution_name, str) or not execution_name:
            raise RuntimeError(
                "Container Apps did not return a startup-check execution ID"
            )
        for _ in range(60):
            observed = subprocess.run(
                [
                    "az", "containerapp", "job", "execution", "show",
                    "--resource-group", resource_group,
                    "--name", job_name,
                    "--job-execution-name", execution_name,
                    "--query", "properties.status",
                    "--output", "tsv",
                    "--only-show-errors",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip().lower()
            if observed == "succeeded":
                return execution_name
            if observed in {"failed", "cancelled", "stopped"}:
                raise RuntimeError(
                    f"Labs worker startup check ended as {observed}"
                )
            time.sleep(5)
        raise TimeoutError(
            "Timed out waiting for the Labs worker startup check"
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
    execution_name = start_startup_check(
        args.resource_group,
        args.job_name,
        container_name=args.container_name,
    )
    print(f"Labs worker startup check succeeded: {execution_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
