"""Read-only attempt accounting, including cancellation and missing timestamps."""
from copy import deepcopy

import pytest

from scripts.ci_metrics import collect_run, summarize_attempt


def fixture():
    run = dict(id=42, run_attempt=2, repository={'full_name': 'owner/repo'}, head_sha='a' * 40,
               path='.github/workflows/ci-premerge.yml', status='completed', conclusion='success',
               created_at='2026-09-30T10:00:00Z', run_started_at='2026-09-30T12:00:00Z')
    jobs = [dict(id=1, name='python-tests', status='completed', conclusion='success',
                 started_at='2026-09-30T12:00:10Z', completed_at='2026-09-30T12:02:10Z'),
            dict(id=2, name='web-build', status='completed', conclusion='cancelled',
                 started_at='2026-09-30T12:00:20Z', completed_at='2026-09-30T12:01:20Z')]
    return run, jobs


def test_rerun_idle_time_is_not_queue_and_cancelled_execution_counts():
    run, jobs = fixture()
    result = summarize_attempt(run, jobs, 2)
    assert result['runner_seconds'] == 180 and result['runner_minutes'] == 3
    assert result['cancelled_jobs'] == 1
    assert result['elapsed_seconds'] == 130
    assert result['initial_dispatch_delay_seconds'] is None


@pytest.mark.parametrize('mutation', ['missing_start', 'missing_end', 'running', 'negative', 'invalid', 'naive'])
def test_unknown_job_timing_is_not_counted_as_zero(mutation):
    run, jobs = fixture()
    if mutation == 'missing_start': jobs[0]['started_at'] = None
    if mutation == 'missing_end': jobs[0]['completed_at'] = None
    if mutation == 'running': jobs[0]['status'] = 'in_progress'
    if mutation == 'negative': jobs[0]['completed_at'] = '2026-09-30T11:00:00Z'
    if mutation == 'invalid': jobs[0]['started_at'] = 'not a time'
    if mutation == 'naive': jobs[0]['started_at'] = '2026-09-30T12:00:10'
    result = summarize_attempt(run, jobs, 2)
    assert result['runner_seconds'] is result['runner_minutes'] is result['elapsed_seconds'] is None
    assert result['known_runner_seconds'] == 60 and not result['timing_complete']


def test_collects_each_attempt_and_all_job_pages_without_write_api():
    run, jobs = fixture()
    calls = []
    def reader(path):
        calls.append(path)
        if path.endswith('/42'): return run
        if '/jobs?' in path:
            return dict(total_count=2, jobs=[jobs[0]] if path.endswith('page=1') else [jobs[1]])
        value = deepcopy(run)
        value['run_attempt'] = int(path.rsplit('/', 1)[1])
        return value
    result = collect_run('owner/repo', 42, reader)
    assert [attempt['attempt'] for attempt in result['attempts']] == [1, 2]
    assert result['runner_minutes'] == result['known_runner_minutes'] == 6
    assert len(calls) == 7
    assert result['attempts'][0]['initial_dispatch_delay_seconds'] == 7210
    assert result['attempts'][1]['initial_dispatch_delay_seconds'] is None


def test_incomplete_or_duplicate_job_pagination_fails():
    run, jobs = fixture()
    run['run_attempt'] = 1
    def reader(path):
        if '/jobs?' in path: return dict(total_count=2, jobs=[jobs[0], jobs[0]])
        return run
    with pytest.raises(ValueError, match='pagination'):
        collect_run('owner/repo', 42, reader)


def test_wrong_repository_is_rejected():
    run, _ = fixture()
    with pytest.raises(ValueError, match='identity'):
        collect_run('other/repo', 42, lambda _: run)


def test_in_progress_attempt_total_stays_unknown_even_if_current_jobs_finished():
    run, jobs = fixture()
    run['status'] = 'in_progress'
    result = summarize_attempt(run, jobs, 2)
    assert not result['timing_complete']
    assert result['runner_seconds'] is result['elapsed_seconds'] is None
    assert result['known_runner_seconds'] == 180
