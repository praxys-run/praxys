"""Morning Coach trust boundary regressions using synthetic observations only."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api import insights_generator, insights_runner, llm, morning_coach as coach
from api.insight_feedback import GENERATION_PROVENANCE_KEY, build_generation_provenance
from api.routes import insights
from db.cache_revision import SCOPES, bump_revisions, get_revisions
from db.models import AiInsight, AiInsightFeedback, Base, User

OWNER = 'morning-owner'


def context() -> dict:
    today = date.today()
    return {
        'as_of_date': today.isoformat(), 'include_stryd_plan': False,
        'coach_snapshot': coach.snapshot_identity(OWNER, dict.fromkeys(SCOPES, 0), today.isoformat(), False),
        'data_as_of': f'{today}T12:00:00Z',
        'recovery_state': {'sleep_score': 80, 'hrv_ms': 54.0, 'resting_hr': 48,
                           'hrv_trend': 'stable', 'rhr_trend': 'stable',
                           'metric_dates': dict.fromkeys(('sleep', 'hrv', 'rhr'), today.isoformat())},
        'current_fitness': {'ctl': 45, 'atl': 50, 'tsb': -5},
        'recent_training': {'sessions': [{'date': str(today-timedelta(days=1)), 'distance_km': 8, 'rss': 40},
                                        {'date': str(today-timedelta(days=7)), 'distance_km': 100, 'rss': 500}]},
        'planned_today': {'workout_type': 'easy', 'planned_duration_min': 45},
        'today_signal': {'recommendation': 'follow_plan', 'reason_code': 'recovery_normal'},
        'science': {'recovery': {'id': 'hrv_based', 'name': 'HRV-Based Recovery'},
                    'load': {'id': 'banister_pmc', 'name': 'Banister PMC'}},
    }


def selection(eligible: dict) -> dict:
    return {'evidence_ids': list(eligible['evidence']), 'interpretation_ids': list(eligible['interpretations']),
            'action_ids': list(eligible['actions'])}


def payload(ctx: dict) -> dict:
    eligible = coach.candidates(ctx)
    chosen = selection(eligible)
    return coach.bind_payload(coach.render_selection(chosen, eligible), ctx, chosen, eligible)


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/coach.sqlite')
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    db.add(User(id=OWNER, email='morning@example.test', hashed_password='x',
                terms_version=TERMS_VERSION, terms_digest=TERMS_CONTENT_DIGEST))
    db.commit()
    monkeypatch.setenv('PRAXYS_DISABLE_BACKGROUND_AI', 'false')
    monkeypatch.setattr(llm, 'runtime_ai_available', lambda: True)
    monkeypatch.setattr(llm, 'get_client', lambda: object())
    monkeypatch.setattr('api.stryd_access.stryd_connection_enabled', lambda *a, **k: False)
    monkeypatch.setattr(insights, '_INSIGHT_FEEDBACK_RATE_LIMIT', SimpleNamespace(check_and_record=lambda _: (True, 0)))
    yield db
    db.close()
    engine.dispose()


def store(db, ctx=None):
    ctx = ctx or context()
    ctx['coach_snapshot'] = coach.current_snapshot(db, OWNER, False)
    result = payload(ctx)
    meta = result.pop('meta_extra')
    meta[GENERATION_PROVENANCE_KEY] = build_generation_provenance('test', {}, run_started_at=datetime.now().isoformat(),
                                                                source_revisions=get_revisions(db, OWNER, SCOPES))
    row = AiInsight(user_id=OWNER, insight_type='daily_brief', **result, meta=meta)
    db.add(row)
    db.commit()
    return row, ctx


def test_current_summary_has_recovery_trends_load_and_plan():
    ctx = context()
    result = payload(ctx)
    assert 'resting heart rate stable' in result['summary']
    assert 'HRV trend stable' in result['summary']
    assert 'CTL 45.0, ATL 50.0, TSB -5.0' in str(result['findings'])
    assert 'CTL' not in result['summary']
    assert len(result['summary'].split()) < 65
    assert '1 recorded session' in result['summary']
    assert 'all recovery' not in result['summary'].lower()
    assert result['recommendations'] == ["Follow the planned 45-minute easy run."]
    assert '45 min' in str(result['findings'])
    assert len(result['translations']['zh']['findings']) == len(result['findings'])
    assert result['translations']['zh']['summary'].count('。') == 3
    assert len(result['meta_extra']['theory_refs']) == 2


@pytest.mark.parametrize('signal,reason,plan,expected', [
    ('rest', 'rest_scheduled', {'workout_type': 'rest'}, 'Keep today for recovery.'),
    ('rest', 'hrv_below_hard', {'workout_type': 'intervals'}, 'Keep today for recovery.'),
    ('easy', 'hrv_below_easy', {'workout_type': 'easy'}, "Keep today's session easy."),
    ('unscheduled', 'unscheduled_open', None, 'Review the training plan before adding a session.'),
    ('unscheduled', 'unscheduled_hrv_caution', None, 'Rest, walk, or do gentle mobility.'),
])
def test_canonical_action_cannot_be_overridden(signal, reason, plan, expected):
    ctx = context()
    ctx.update(planned_today=plan, today_signal={'recommendation': signal, 'reason_code': reason})
    eligible = coach.candidates(ctx)
    assert list(eligible['actions']) == [f'today.{signal}']
    assert payload(ctx)['recommendations'] == [expected]
    if plan is None:
        assert 'No Praxys-managed workout is scheduled today.' in payload(ctx)['summary']


@pytest.mark.parametrize('value,observed', [(float('inf'), 0), (float('nan'), 0), (-1, 0), (0, 0), (50, 2), (50, -1), (50, None)])
def test_rhr_individual_validity_never_borrows_sleep_date(value, observed):
    ctx = context()
    state = ctx['recovery_state']
    state['resting_hr'] = value
    state['metric_dates']['rhr'] = str(date.today()-timedelta(days=observed)) if observed is not None else None
    result = payload(ctx)
    assert 'Current resting heart rate unavailable' in result['summary']
    assert 'rhr.stable' not in coach.candidates(ctx)['interpretations']
    assert 'inf' not in str(result['findings'])


def test_yesterday_retains_observation_date_and_missing_not_zero():
    ctx = context()
    observed = str(date.today()-timedelta(days=1))
    ctx['recovery_state']['metric_dates']['rhr'] = observed
    assert f'48 bpm, recorded {observed}' in str(payload(ctx)['findings'])
    ctx['recovery_state'] = {}
    ctx['recent_training']['sessions'] = []
    result = payload(ctx)
    assert 'Current sleep score, HRV, resting heart rate unavailable.' in result['summary']
    assert 'modeled load awaits training data' in str(result['findings'])
    assert 'distance unavailable' in str(result['findings'])


def external_course(**changes) -> dict:
    return {'date': str(date.today()), 'source': 'stryd', 'owner': 'external',
            'workout_type': 'long', 'planned_distance_km': 18,
            'planned_duration_min': 110, 'target_power_min': 170,
            'target_power_max': 195, **changes}


def test_external_course_is_conditional_and_preserves_source_targets():
    ctx = context()
    ctx.update(include_stryd_plan=True, planned_today=None,
               external_planned_today=[external_course()],
               today_signal={'recommendation': 'unscheduled', 'reason_code': 'unscheduled_open'})
    result = payload(ctx)
    assert 'No Praxys-managed workout' in result['summary']
    assert 'Stryd lists an external long run' in result['summary']
    assert result['recommendations'] == [
        'If you choose the Stryd long run, use its 170–195 W target as a reference and adjust execution to how you feel.']
    assert '18 km, 110 min, 170–195 W' in str(result['findings'])
    assert '如果选择Stryd' in result['translations']['zh']['recommendations'][0]
    assert result['translations']['zh']['summary'].count('。') == 3


@pytest.mark.parametrize('recommendation,reason,plan,expected', [
    ('follow_plan', 'recovery_normal', {'workout_type': 'easy', 'planned_duration_min': 45}, 'Follow the planned 45-minute easy run.'),
    ('rest', 'rest_scheduled', {'workout_type': 'rest'}, 'Keep today for recovery.'),
    ('unscheduled', 'unscheduled_hrv_caution', None, 'Rest, walk, or do gentle mobility.'),
    ('unscheduled', 'unscheduled_high_load', None, 'Keep any optional movement easy and short.'),
])
def test_external_course_never_displaces_praxys_or_caution(recommendation, reason, plan, expected):
    ctx = context()
    ctx.update(include_stryd_plan=True, planned_today=plan,
               external_planned_today=[external_course()],
               today_signal={'recommendation': recommendation, 'reason_code': reason})
    result = payload(ctx)
    assert result['recommendations'] == [expected]
    if plan:
        assert 'Praxys' in result['summary']
        assert 'Stryd' not in result['summary']
    assert 'Stryd' in str(result['findings'])


def test_selected_external_plan_also_uses_conditional_wording():
    ctx = context()
    ctx.update(include_stryd_plan=True, planned_today=external_course())
    result = payload(ctx)
    assert result['recommendations'][0].startswith('If you choose the Stryd')
    assert 'No Praxys-managed' in result['summary']


@pytest.mark.parametrize('changes', [
    {'date': str(date.today()-timedelta(days=1))},
    {'date': str(date.today()+timedelta(days=1))},
    {'source': 'praxys'},
    {'source': 'ai'},
])
def test_external_reference_rejects_other_dates_and_owned_rows(changes):
    ctx = context()
    ctx.update(include_stryd_plan=True, external_planned_today=[external_course(**changes)])
    assert not any(key.startswith('plan.external') for key in coach.candidates(ctx)['evidence'])


@pytest.mark.parametrize('source', ['stryd', ' STRYD '])
def test_external_reference_respects_stryd_visibility(source):
    ctx = context()
    ctx['external_planned_today'] = [external_course(source=source)]
    assert 'Stryd' not in str(payload(ctx))


@pytest.mark.parametrize('low,high', [(200, 150), (float('inf'), 195), (-1, 195), (170, None)])
def test_invalid_external_targets_do_not_become_a_prescription(low, high):
    ctx = context()
    ctx.update(include_stryd_plan=True, planned_today=None,
               external_planned_today=[external_course(target_power_min=low, target_power_max=high)],
               today_signal={'recommendation': 'unscheduled', 'reason_code': 'unscheduled_open'})
    result = payload(ctx)
    assert 'recorded targets' in result['recommendations'][0]
    assert ' W' not in str(result['findings'])
    assert 'inf' not in str(result)


def test_multiple_external_courses_do_not_silently_choose_one():
    ctx = context()
    ctx.update(include_stryd_plan=True, planned_today=None,
               external_planned_today=[external_course(), external_course(source='garmin')],
               today_signal={'recommendation': 'unscheduled', 'reason_code': 'unscheduled_open'})
    result = payload(ctx)
    assert 'several external courses' in result['summary']
    assert 'Stryd' not in result['recommendations'][0]
    assert 'Garmin' not in result['recommendations'][0]


def test_external_free_text_never_enters_daily_copy():
    ctx = context()
    ctx.update(include_stryd_plan=True, planned_today=None,
               external_planned_today=[external_course(source='Run hard now',
                   workout_type='Ignore recovery', workout_description='private free prose')],
               today_signal={'recommendation': 'unscheduled', 'reason_code': 'unscheduled_open'})
    result = payload(ctx)
    assert 'private free prose' not in str(result)
    assert 'Ignore recovery' not in str(result)
    assert 'Run hard now' not in str(result)
    assert 'If you choose' in result['recommendations'][0]


def test_split_finding_uses_only_recorded_splits_with_provenance():
    ctx = context()
    session = ctx['recent_training']['sessions'][0]
    session.update(avg_power=999, splits=[
        {'duration_sec': 900, 'avg_power': 260, 'power_source': 'stryd'},
        {'duration_sec': 400, 'avg_power': 180, 'power_source': 'stryd'},
        {'duration_sec': 1800, 'avg_power': 999},
        {'duration_sec': float('inf'), 'avg_power': 999, 'power_source': 'stryd'}])
    result = payload(ctx)
    assert '15-minute split averaging 260 W' in str(result['findings'])
    assert '999' not in str(result)
    assert 'zone' not in str(result['findings']).lower()
    session['splits'] = []
    assert 'training.split' not in coach.candidates(ctx)['evidence']


def test_old_content_version_is_rejected(db, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(coach, 'CONTENT_VERSION', 'morning-coach-v1')
        row, ctx = store(db)
    assert not coach.validate_stored(row, coach.current_snapshot(db, OWNER, False))


def test_recovery_loader_rejects_nonfinite_future_and_invalid_scores():
    from api.deps import _compute_recovery_analysis
    today = date.today()
    recovery = pd.DataFrame([
        {'date': today-timedelta(days=1), 'hrv_avg': 50, 'resting_hr': 50, 'sleep_score': 80},
        {'date': today, 'hrv_avg': float('inf'), 'resting_hr': float('nan'), 'sleep_score': 101},
        {'date': today+timedelta(days=1), 'hrv_avg': 70, 'resting_hr': 70, 'sleep_score': 90},
    ])
    analysis, hrv, sleep, rhr = _compute_recovery_analysis(recovery, current_date=today)
    assert (hrv, sleep, rhr) == (50, 80, 50)
    assert analysis['rhr_latest_date'] == str(today-timedelta(days=1))
    assert analysis['rhr_trend'] is None
    assert analysis['classification_reason'] == 'insufficient_history'


@pytest.mark.parametrize('mutation', ['extra', 'prose', 'unknown', 'contradiction', 'missing_recovery', 'duplicate', 'foreign_interpretation', 'empty_action'])
def test_strict_selection_rejects_untrusted_or_incompatible_output(mutation):
    eligible = coach.candidates(context())
    raw = selection(eligible)
    if mutation == 'extra': raw['headline'] = 'Run hard'
    if mutation == 'prose': raw['evidence_ids'] = '睡眠正常，冲刺'
    if mutation == 'unknown': raw['evidence_ids'].append('foreign.evidence')
    if mutation == 'contradiction': raw['action_ids'] = ['today.rest']
    if mutation == 'missing_recovery': raw['evidence_ids'].remove('recovery.hrv')
    if mutation == 'duplicate': raw['action_ids'] *= 2
    if mutation == 'foreign_interpretation': raw['interpretation_ids'] = ['hrv.declining']
    if mutation == 'empty_action': raw['action_ids'] = []
    with pytest.raises(ValueError): coach.render_selection(raw, eligible)


def test_generator_does_not_log_rejected_model_text(monkeypatch, caplog):
    monkeypatch.setattr(llm, 'get_client', lambda: object())
    monkeypatch.setattr(llm, 'chat_json', lambda *a, **k: {'summary': 'private foreign text'})
    assert insights_generator.generate_daily_brief(context(), {}) is None
    assert 'private foreign text' not in caplog.text


def test_content_identity_differs_from_input_and_changes_with_selection():
    ctx = context()
    eligible = coach.candidates(ctx)
    chosen = selection(eligible)
    a = coach.bind_payload(coach.render_selection(chosen, eligible), ctx, chosen, eligible)
    chosen = deepcopy(chosen)
    chosen['evidence_ids'].reverse()
    b = coach.bind_payload(coach.render_selection(chosen, eligible), ctx, chosen, eligible)
    assert a['meta_extra']['input_hash'] == b['meta_extra']['input_hash']
    assert a['meta_extra']['dataset_hash'] != b['meta_extra']['dataset_hash']
    assert a['meta_extra']['dataset_hash'] != ctx['coach_snapshot']


def test_stored_provenance_content_and_owner_are_required(db):
    row, ctx = store(db)
    assert coach.validate_stored(row, ctx['coach_snapshot'])
    assert not coach.validate_stored(row, None)
    row.summary = 'forged prose'
    assert not coach.validate_stored(row, ctx['coach_snapshot'])
    db.rollback()
    row.meta = {k: v for k, v in row.meta.items() if k != GENERATION_PROVENANCE_KEY}
    assert not coach.validate_stored(row, ctx['coach_snapshot'])


def test_daily_read_rejects_missing_stale_and_foreign_snapshot(db):
    row, ctx = store(db)
    response = insights.get_insight('daily_brief', ctx['coach_snapshot'], OWNER, OWNER, db)
    assert response['content_status'] == 'ready'
    assert response['insight']['snapshot'] == ctx['coach_snapshot']
    assert '_morning_coach' not in response['insight']['meta']
    for snapshot in (None, 'foreign'):
        assert insights.get_insight('daily_brief', snapshot, OWNER, OWNER, db)['insight'] is None
    bump_revisions(db, OWNER, ['recovery']); db.commit()
    assert insights.get_insight('daily_brief', ctx['coach_snapshot'], OWNER, OWNER, db)['content_status'] == 'stale'
    current = coach.current_snapshot(db, OWNER, False)
    assert insights.get_insight('daily_brief', current, OWNER, OWNER, db)['insight'] is None


def test_read_fails_closed_when_source_changes_during_serialization(db, monkeypatch):
    row, ctx = store(db)
    original = insights._serialize_insight
    def serialize(*a, **k):
        response = original(*a, **k)
        bump_revisions(db, OWNER, ['plans']); db.commit()
        return response
    monkeypatch.setattr(insights, '_serialize_insight', serialize)
    response = insights.get_insight('daily_brief', ctx['coach_snapshot'], OWNER, OWNER, db)
    assert response['content_status'] == 'stale' and response['insight'] is None


def test_feedback_validates_before_duplicate_and_never_moves_votes(db):
    row, ctx = store(db)
    body = insights.InsightFeedbackRequest(vote='up', dataset_hash=row.meta['dataset_hash'],
                                           snapshot=ctx['coach_snapshot'], content_version=coach.CONTENT_VERSION)
    assert insights.submit_insight_feedback('daily_brief', body, OWNER, db)['duplicate'] is False
    assert insights.submit_insight_feedback('daily_brief', body, OWNER, db)['duplicate'] is True
    bump_revisions(db, OWNER, ['recovery']); db.commit()
    with pytest.raises(HTTPException) as exc:
        insights.submit_insight_feedback('daily_brief', body, OWNER, db)
    assert exc.value.status_code == 409
    assert db.query(AiInsightFeedback).count() == 1


@pytest.mark.parametrize('change', ['terms', 'inactive', 'demo', 'unavailable', 'version', 'no_snapshot', 'other_owner'])
def test_feedback_access_and_availability(db, monkeypatch, change):
    row, ctx = store(db)
    body = insights.InsightFeedbackRequest(vote='up', dataset_hash=row.meta['dataset_hash'],
                                           snapshot=ctx['coach_snapshot'], content_version=coach.CONTENT_VERSION)
    if change == 'terms': db.get(User, OWNER).terms_version = 'old'
    if change == 'inactive': db.get(User, OWNER).is_active = False
    if change == 'demo': db.get(User, OWNER).is_demo = True
    if change == 'unavailable': monkeypatch.setattr(llm, 'runtime_ai_available', lambda: False)
    if change == 'version': body.content_version = 'old'
    if change == 'no_snapshot': body.snapshot = None
    db.commit()
    with pytest.raises(HTTPException):
        insights.submit_insight_feedback('daily_brief', body, 'other' if change == 'other_owner' else OWNER, db)
    assert db.query(AiInsightFeedback).count() == 0


def setup_runner(monkeypatch):
    ctx = context()
    monkeypatch.setattr('api.ai.build_training_context', lambda **k: deepcopy(ctx))
    monkeypatch.setattr(llm, 'chat_json', lambda *a, **k: selection(coach.candidates(ctx)))
    return ctx


def test_no_new_rows_generates_daily_once_and_rollover_generates_again(db, monkeypatch):
    ctx = setup_runner(monkeypatch)
    first = insights_runner.run_insights_for_user(OWNER, db, {}, _session=db)
    assert first['daily_brief'] == 'generated'
    row = db.query(AiInsight).filter_by(insight_type='daily_brief').one()
    old_hash = row.meta['dataset_hash']
    assert insights_runner.run_insights_for_user(OWNER, db, {}, _session=db)['daily_brief'] == 'hash_match'
    tomorrow = date.today()+timedelta(days=1)
    class NextDate(date):
        @classmethod
        def today(cls): return tomorrow
    monkeypatch.setattr(coach, 'date', NextDate)
    monkeypatch.setattr(insights_runner, 'date', NextDate)
    ctx['as_of_date'] = str(tomorrow)
    result = insights_runner.run_insights_for_user(OWNER, db, {}, _session=db)
    assert result['daily_brief'] == 'generated'
    db.refresh(row)
    assert row.meta['dataset_hash'] != old_hash
    assert row.meta[coach.CONTRACT_KEY]['data_as_of'] == context()['data_as_of']


def test_cumulative_cap_counts_rejections_not_mutable_rows(db, monkeypatch):
    setup_runner(monkeypatch)
    monkeypatch.setattr(insights_runner, '_daily_cap', lambda _: 2)
    calls = []
    monkeypatch.setattr(llm, 'chat_json', lambda *a, **k: calls.append(1) or {'foreign': 'prose'})
    for _ in range(4): insights_runner.run_insights_for_user(OWNER, db, {}, _session=db)
    assert len(calls) == 2
    assert insights_runner._count_today(OWNER, db) == 2
    assert db.query(AiInsight).filter_by(insight_type='daily_brief').count() == 0


@pytest.mark.parametrize('change', ['source', 'terms', 'availability', 'date'])
def test_generation_races_fail_closed(db, monkeypatch, change):
    ctx = setup_runner(monkeypatch)
    def generate(*a, **k):
        if change == 'source': bump_revisions(db, OWNER, ['recovery']); db.commit()
        if change == 'terms': db.get(User, OWNER).terms_version = 'old'; db.commit()
        if change == 'availability': monkeypatch.setattr(llm, 'runtime_ai_available', lambda: False)
        if change == 'date':
            tomorrow = date.today()+timedelta(days=1)
            class NextDate(date):
                @classmethod
                def today(cls): return tomorrow
            monkeypatch.setattr(coach, 'date', NextDate)
            monkeypatch.setattr(insights_runner, 'date', NextDate)
        return selection(coach.candidates(ctx))
    monkeypatch.setattr(llm, 'chat_json', generate)
    result = insights_runner.run_insights_for_user(OWNER, db, {}, _session=db)
    assert result.get('daily_brief') != 'generated'
    assert db.query(AiInsight).filter_by(insight_type='daily_brief').count() == 0


@pytest.mark.parametrize('cache_mode', ['hit', 'bypass', 'miss'])
def test_today_verification_retries_and_fails_closed_during_read(db, monkeypatch, cache_mode):
    import json
    from starlette.requests import Request
    from api.routes import today
    count = 0
    monkeypatch.setattr(today, 'stryd_connection_enabled', lambda *a, **k: cache_mode == 'bypass')
    def compute(*a, **k):
        nonlocal count
        count += 1
        bump_revisions(db, OWNER, ['activities']); db.commit()
        return json.dumps({'as_of_date': str(date.today()), 'signal': {'recommendation': 'rest'}, 'coach_snapshot': 'unchecked'}).encode()
    monkeypatch.setattr(today, 'cached_or_compute', compute)
    response = today.get_today(Request({'type': 'http', 'headers': []}), OWNER, OWNER, db)
    assert count == 2
    assert json.loads(response.body)['coach_snapshot'] is None
    assert response.headers['cache-control'] == 'no-store'


def test_today_verified_retry_replaces_mixed_body(db, monkeypatch):
    import json
    from starlette.requests import Request
    from api.routes import today
    monkeypatch.setattr(today, 'stryd_connection_enabled', lambda *a, **k: False)
    count = 0
    def compute(*a, **k):
        nonlocal count
        count += 1
        if count == 1:
            bump_revisions(db, OWNER, ['recovery']); db.commit()
        return json.dumps({'as_of_date': str(date.today()), 'attempt': count}).encode()
    monkeypatch.setattr(today, 'cached_or_compute', compute)
    response = today.get_today(Request({'type': 'http', 'headers': []}), OWNER, OWNER, db)
    body = json.loads(response.body)
    assert body['attempt'] == 2
    assert body['coach_snapshot'] == coach.current_snapshot(db, OWNER, False)


def test_feedback_date_change_before_commit_rejects_vote(db, monkeypatch):
    row, ctx = store(db)
    body = insights.InsightFeedbackRequest(vote='up', dataset_hash=row.meta['dataset_hash'],
                                           snapshot=ctx['coach_snapshot'], content_version=coach.CONTENT_VERSION)
    original = coach.validate_stored
    calls = 0
    def validate(*a, **k):
        nonlocal calls
        calls += 1
        return calls == 1 and original(*a, **k)
    monkeypatch.setattr(coach, 'validate_stored', validate)
    with pytest.raises(HTTPException): insights.submit_insight_feedback('daily_brief', body, OWNER, db)
    assert db.query(AiInsightFeedback).count() == 0


def test_publication_uses_fresh_revision_lock_and_rechecks_source(db, monkeypatch):
    ctx = setup_runner(monkeypatch)
    from db import cache_revision
    original = cache_revision.lock_revision_writes
    changed = False
    def lock(session, owner):
        nonlocal changed
        original(session, owner)
        # First lock reserves the call; the publication lock is the second.
        if insights_runner._count_today(owner, session) and not changed:
            changed = True
            bump_revisions(session, owner, ['plans'])
            session.flush()
    monkeypatch.setattr(cache_revision, 'lock_revision_writes', lock)
    result = insights_runner.run_insights_for_user(OWNER, db, {}, _session=db)
    assert result['daily_brief'] == 'superseded'
    assert db.query(AiInsight).filter_by(insight_type='daily_brief').count() == 0
