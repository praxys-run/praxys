"""Read GitHub Actions attempts and job timings; never modify GitHub state."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess


def read_api(path: str) -> dict:
    result = subprocess.run(['gh', 'api', '--method', 'GET', path],
                            check=True, capture_output=True, text=True)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError('GitHub API response must be an object')
    return value


def timestamp(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def seconds(start, end) -> float | None:
    before, after = timestamp(start), timestamp(end)
    if before is None or after is None or after < before:
        return None
    return (after - before).total_seconds()


def summarize_attempt(run: dict, jobs: list[dict], attempt: int) -> dict:
    observations = []
    for job in jobs:
        duration = seconds(job.get('started_at'), job.get('completed_at')) if job.get('status') == 'completed' else None
        observations.append(dict(id=job['id'], name=job.get('name'), status=job.get('status'),
                                 conclusion=job.get('conclusion'), started_at=job.get('started_at'),
                                 completed_at=job.get('completed_at'), runner_seconds=duration))
    complete = (run.get('status') == 'completed' and bool(observations)
                and all(job['runner_seconds'] is not None for job in observations))
    known_seconds = sum(job['runner_seconds'] for job in observations if job['runner_seconds'] is not None)
    starts = [job['started_at'] for job in observations if timestamp(job['started_at']) is not None]
    ends = [job['completed_at'] for job in observations if timestamp(job['completed_at']) is not None]
    earliest = min(starts, key=timestamp) if starts else None
    latest = max(ends, key=timestamp) if ends else None
    # created_at belongs to the original dispatch, including on rerun responses.
    start = run.get('created_at') if attempt == 1 else run.get('run_started_at')
    elapsed = seconds(start, latest) if complete and run.get('status') == 'completed' else None
    return dict(attempt=attempt, status=run.get('status'), conclusion=run.get('conclusion'),
                head_sha=run.get('head_sha'), jobs=observations,
                initial_dispatch_delay_seconds=seconds(run.get('created_at'), earliest) if attempt == 1 else None,
                dispatch_delay_note='first attempt only; rerun dispatch time unavailable' if attempt > 1
                                    else 'created_at to earliest job start; not per-job runner queue',
                elapsed_seconds=elapsed, elapsed_basis='created_at' if attempt == 1 else 'attempt run_started_at',
                timing_complete=complete, runner_seconds=known_seconds if complete else None,
                known_runner_seconds=known_seconds,
                runner_minutes=known_seconds / 60 if complete else None,
                cancelled_jobs=sum(job['conclusion'] == 'cancelled' for job in observations))


def collect_run(repository: str, run_id: int, reader=read_api) -> dict:
    root = f'repos/{repository}/actions/runs/{run_id}'
    current = reader(root)
    if current.get('id') != run_id or current.get('repository', {}).get('full_name') != repository:
        raise ValueError('GitHub run identity mismatch')
    attempts = []
    for number in range(1, int(current['run_attempt']) + 1):
        run = reader(f'{root}/attempts/{number}')
        if run.get('id') != run_id or run.get('run_attempt') != number or run.get('head_sha') != current.get('head_sha'):
            raise ValueError('GitHub attempt identity mismatch')
        jobs, page = [], 1
        while True:
            response = reader(f'{root}/attempts/{number}/jobs?per_page=100&page={page}')
            batch = response.get('jobs')
            if not isinstance(batch, list):
                raise ValueError('Missing jobs list')
            jobs.extend(batch)
            if len(jobs) >= response['total_count']:
                break
            if not batch:
                raise ValueError('Incomplete job pagination')
            page += 1
        if len(jobs) != response['total_count'] or len({job['id'] for job in jobs}) != len(jobs):
            raise ValueError('Ambiguous job pagination')
        attempts.append(summarize_attempt(run, jobs, number))
    all_known = bool(attempts) and all(item['runner_seconds'] is not None for item in attempts)
    known_seconds = sum(item['known_runner_seconds'] for item in attempts)
    return dict(repository=repository, run_id=run_id, head_sha=current.get('head_sha'),
                workflow_path=current.get('path'), attempts=attempts,
                runner_minutes=known_seconds / 60 if all_known else None,
                known_runner_minutes=known_seconds / 60,
                runner_minutes_note='sum of job execution time, not exact billed minutes; missing timing stays null')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--run-id', type=int, nargs='+', action='extend', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo) or any(run <= 0 for run in args.run_id):
        parser.error('expected OWNER/REPO and positive run IDs')
    result = dict(schema_version=1, repository=args.repo,
                  runs=[collect_run(args.repo, run_id) for run_id in dict.fromkeys(args.run_id)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    temporary.replace(args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
