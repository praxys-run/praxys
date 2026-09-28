"""Synthetic local trial integration; never initialize the real Git-common ledger."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import pytest

from analysis.agent_decision_trial import DecisionCard, OutcomeEvent, TrialUnavailable, policy_digest
from analysis.agent_decision_trial_cooperative import (
    CooperativeTrial, ReviewedDecision, canonical_store_path, load_cooperative_policy, new_task_key,
)
from analysis.agentic_task_routing import TaskClassification, route_task

ROOT = Path(__file__).resolve().parents[1]
DIGEST = 'sha256:' + 'a' * 64
NOW = datetime(2026, 9, 28, tzinfo=timezone.utc)


def contract(*, excluded=False):
    return route_task(TaskClassification(
        primary_object='agent-system' if excluded else 'repository-behavior',
        impacts=['repository-change'], risk_triggers=[],
    ))


def trial(tmp_path):
    result = CooperativeTrial(tmp_path / 'private' / 'trial.sqlite3', load_cooperative_policy(), lambda: NOW)
    result.initialize()
    return result


def review():
    card = DecisionCard(
        review_route='human-review-required', subject_digest=DIGEST, evidence_digest=DIGEST,
        question='Choose the reviewed option?', recommendation='Retain baseline',
        main_tradeoff='Readability versus detail', human_authority='This bounded presentation',
        why_human='Existing policy requires judgment', if_declined='Baseline continues',
        deferred='Autonomy changes', evidence_refs=('synthetic-review',),
    )
    return ReviewedDecision(
        card=card, subject_digest=DIGEST, evidence_digest=DIGEST, review_digest=DIGEST,
        reviewer='independent-quality', proposer='product', executor='engineering',
    )


def cli(tmp_path, *args, ok=True):
    policy_path = tmp_path / 'policy.json'
    if not policy_path.exists():
        policy_path.write_text(load_cooperative_policy().model_dump_json())
    result = subprocess.run([
        sys.executable, str(ROOT / 'scripts/local_decision_trial.py'),
        '--test-policy', str(policy_path), '--test-store', str(tmp_path / 'private/trial.sqlite3'),
        *map(str, args),
    ], capture_output=True, text=True, cwd=ROOT)
    assert (result.returncode == 0) == ok, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_real_cli_lifecycle_and_no_implicit_setup(tmp_path):
    unavailable = cli(tmp_path, 'status', ok=False)
    assert unavailable['presentation'] == 'baseline'
    assert not (tmp_path / 'private').exists()
    first, second = [cli(tmp_path, 'new-task')['task_key'] for _ in range(2)]
    assert first != second
    cli(tmp_path, 'init')
    cli(tmp_path, 'init', ok=False)
    path = tmp_path / 'contract.json'
    path.write_text(contract().model_dump_json())
    assert cli(tmp_path, 'admit', '--task-key', first, '--contract', path)['original_arm'] == 'A'
    assert cli(tmp_path, 'admit', '--task-key', second, '--contract', path)['original_arm'] == 'B'
    again = cli(tmp_path, 'admit', '--task-key', second, '--contract', path, '--resume')
    assert again['reason'] == 'existing'
    unknown = cli(tmp_path, 'admit', '--task-key', new_task_key(), '--contract', path, '--resume')
    assert unknown['reason'] == 'unknown_resume'
    event_path = tmp_path / 'event.json'
    for index, kind in enumerate(['failed', 'baseline_fallback', 'no_pr', 'abandoned']):
        event_path.write_text(OutcomeEvent(event_key='evt_' + f'{index:064x}', kind=kind).model_dump_json())
        assert cli(tmp_path, 'outcome', '--task-key', second, '--event', event_path)['original_arm'] == 'B'
    status = cli(tmp_path, 'status')
    assert status['arms']['A']['completion_unknown'] == 1
    assert status['arms']['B']['events']['no_pr'] == 1
    assert status['human_active_minutes'] == 'unknown'
    cli(tmp_path, 'stop')
    assert cli(tmp_path, 'status')['reason'] == 'stopped'
    assert cli(tmp_path, 'admit', '--task-key', new_task_key(), '--contract', path)['enrolled'] is False


def test_corrupt_cli_store_is_not_reset_and_private_input_not_echoed(tmp_path):
    cli(tmp_path, 'init')
    path = tmp_path / 'private/trial.sqlite3'
    path.write_bytes(b'corrupt private input')
    assert cli(tmp_path, 'status', ok=False)['original_arm'] == 'unknown'
    assert path.read_bytes() == b'corrupt private input'
    secret = tmp_path / 'invalid.json'
    secret.write_text('{"private": "must not echo"}')
    result = cli(tmp_path, 'admit', '--task-key', new_task_key(), '--contract', secret, ok=False)
    assert 'must not echo' not in json.dumps(result)


def test_policy_pin_expiry_disabled_and_drift_preserve_original_b(tmp_path):
    service = trial(tmp_path)
    assert service.admit(new_task_key(), contract(excluded=True))['enrolled'] is False
    a, b = new_task_key(), new_task_key()
    service.admit(a, contract())
    service.admit(b, contract())
    changed = service.admit(b, contract(excluded=True), resume=True)
    assert changed['original_arm'] == 'B'
    assert changed['reason'] == 'contract_mismatch'
    assert service.card(b, contract(), review())['reason'] == 'baseline_fallback'
    assert len(service.store.read()[1].assignments) == 2
    altered = service.policy.model_copy(update={'expires_at': '2026-11-28T00:00:00Z'})
    assert policy_digest(altered) != policy_digest(service.policy)
    with pytest.raises(TrialUnavailable, match='invalid'):
        CooperativeTrial(service.path, altered, lambda: NOW).status()
    service.clock = lambda: datetime(2026, 10, 28, tzinfo=timezone.utc)
    expired = service.card(b, contract(), review())
    assert expired['card'] is None
    assert expired['original_arm'] == 'B'
    service.outcome(b, OutcomeEvent(event_key='evt_' + 'b' * 64, kind='no_pr'))
    assert service.status()['reason'] == 'expired'


@pytest.mark.parametrize('off', ['stop', 'expiry', 'disabled'])
def test_off_switches_suppress_b_without_changing_arm(tmp_path, off):
    service = trial(tmp_path)
    service.admit(new_task_key(), contract())
    key = new_task_key()
    service.admit(key, contract())
    if off == 'stop':
        service.stop()
    elif off == 'expiry':
        service.clock = lambda: datetime(2026, 10, 28, tzinfo=timezone.utc)
    else:
        disabled = service.policy.model_copy(update={'status': 'disabled'})
        assert policy_digest(disabled) == policy_digest(service.policy)
        service = CooperativeTrial(service.path, disabled, lambda: NOW)
    result = service.card(key, contract(), review())
    assert result['original_arm'] == 'B' and result['card'] is None
    assert service.admit(new_task_key(), contract())['enrolled'] is False
    service.outcome(key, OutcomeEvent(event_key='evt_' + 'c' * 64, kind='abandoned'))


def test_cards_require_b_review_and_one_issue_without_claiming_display(tmp_path):
    service = trial(tmp_path)
    a, b = new_task_key(), new_task_key()
    service.admit(a, contract())
    service.admit(b, contract())
    assert service.card(a, contract(), review())['card'] is None
    stale = review().model_copy(update={'subject_digest': 'sha256:' + 'f' * 64})
    result = service.card(b, contract(), stale)
    assert result['card'] is None and result['original_arm'] == 'B'
    assert result['reason'] == 'stale_evidence'
    with pytest.raises(ValueError, match='independent'):
        ReviewedDecision.model_validate({**review().model_dump(), 'reviewer': 'engineering'})
    with pytest.raises(ValueError):
        DecisionCard.model_validate({**review().card.model_dump(), 'review_route': 'blocked'})
    with pytest.raises(TrialUnavailable, match='display requires'):
        service.outcome(b, OutcomeEvent(event_key='evt_' + 'd' * 64, kind='card_displayed'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: service.card(b, contract(), review()), range(4)))
    assert sum(result['card'] is not None for result in results) == 1
    status = service.status()['arms']['B']
    assert status['events']['card_issued'] == 1
    assert status['exposure_unknown'] == 1
    service.outcome(b, OutcomeEvent(event_key='evt_' + 'd' * 64, kind='card_displayed'))
    assert service.status()['arms']['B']['exposure_unknown'] == 0
    assert 'Choose the reviewed option' not in service.store.read()[1].model_dump_json()


def test_concurrent_cap_checkpoint_and_existing_b_can_finish(tmp_path):
    service = trial(tmp_path)
    keys = [new_task_key() for _ in range(25)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda key: service.admit(key, contract()), keys))
    assert sum(result['enrolled'] for result in results) == 8
    assert service.status()['reason'] == 'checkpoint_due'
    state = service.store.read()[1]
    b = next(key for key, item in state.assignments.items() if item.arm == 'B')
    assert service.card(b, contract(), review())['card']
    service.checkpoint(DIGEST)
    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda _: service.admit(new_task_key(), contract()), range(20)))
    assert len(service.store.read()[1].assignments) == 16
    assert service.status()['reason'] == 'closed'
    b = next(key for key, item in service.store.read()[1].assignments.items()
             if item.arm == 'B' and not item.events)
    assert service.card(b, contract(), review())['card']
    service.outcome(b, OutcomeEvent(event_key='evt_' + 'e' * 64, kind='completed'))
    assert service.admit(new_task_key(), contract())['reason'] == 'closed'


def test_worktrees_resolve_same_canonical_path_without_creation(tmp_path):
    repository, worktree = tmp_path / 'repo', tmp_path / 'linked'
    subprocess.run(['git', 'init', str(repository)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repository), '-c', 'user.name=Synthetic',
                    '-c', 'user.email=synthetic@example.invalid', 'commit', '--allow-empty', '-m', 'fixture'],
                   check=True, capture_output=True)
    subprocess.run(['git', '-C', str(repository), 'worktree', 'add', '-b', 'linked', str(worktree)],
                   check=True, capture_output=True)
    first = canonical_store_path(repository, load_cooperative_policy())
    assert first == canonical_store_path(worktree, load_cooperative_policy())
    assert not first.parent.exists()


def test_cli_card_and_checkpoint_use_actual_recorded_assignment(tmp_path):
    cli(tmp_path, 'init')
    path = tmp_path / 'contract.json'
    path.write_text(contract().model_dump_json())
    review_path = tmp_path / 'review.json'
    review_path.write_text(review().model_dump_json())
    keys = [new_task_key() for _ in range(9)]
    for key in keys[:8]:
        cli(tmp_path, 'admit', '--task-key', key, '--contract', path)
    assert cli(tmp_path, 'admit', '--task-key', keys[8], '--contract', path)['reason'] == 'checkpoint_due'
    issued = cli(tmp_path, 'card', '--task-key', keys[1], '--contract', path, '--review', review_path)
    assert issued['reason'] == 'issued_display_unknown' and issued['card']
    again = cli(tmp_path, 'card', '--task-key', keys[1], '--contract', path, '--review', review_path)
    assert again['reason'] == 'already_issued' and again['card'] is None
    cli(tmp_path, 'checkpoint', '--review-digest', DIGEST)
    assert cli(tmp_path, 'admit', '--task-key', keys[8], '--contract', path)['reason'] == 'assigned'


def test_fallback_between_admission_check_and_card_cas_is_respected(tmp_path, monkeypatch):
    service = trial(tmp_path)
    service.admit(new_task_key(), contract())
    key = new_task_key()
    service.admit(key, contract())
    original = service.admit

    def drift_after_check(*args, **kwargs):
        result = original(*args, **kwargs)
        original(key, contract(excluded=True), resume=True)
        return result

    monkeypatch.setattr(service, 'admit', drift_after_check)
    result = service.card(key, contract(), review())
    assert result['reason'] == 'baseline_fallback'
    assert result['card'] is None and result['original_arm'] == 'B'
    assert not any(event.kind == 'card_issued' for event in service.store.read()[1].assignments[key].events)
