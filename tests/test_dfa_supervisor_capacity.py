"""Measured healthy synthetic retirement cell; live/full-input cells remain unproved."""
from datetime import datetime,timedelta
from pathlib import Path
import json
import subprocess
import sys
import threading
import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tests.test_dfa_origins import both_origins, complete_unit
from tests.test_activity_dfa import store, confirmed
from api import activity_dfa as service
from db.models import ActivityDFARun as Run, ActivityDFAControl as Control


def test_100_healthy_synthetic_manual_admission_preemptions(both_origins,monkeypatch,tmp_path):
    factory,owner=both_origins
    proof,manual=confirmed(factory,owner)
    with factory() as db: claimed=service.claim(db)
    service.execute(factory,*claimed)
    with factory() as db:
        row=db.get(Run,manual['id']);row.status='failed';row.error_code='synthetic_retry';db.commit()
    complete_unit(factory,owner)
    supervisor=factory.dfa_supervisor
    supervisor.controls=sessionmaker(bind=create_engine(factory.kw['bind'].url,pool_size=1,max_overflow=0,pool_timeout=.1,
                                                        connect_args={'timeout':.1}))
    real_popen=subprocess.Popen
    code='''import io,json,signal,sys,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
raw=sys.stdin.buffer.readline(90*1024*1024+1)
payload=json.loads(raw)
if payload['origin']=='automatic':
    while True:time.sleep(.01)
else:
    signal.signal(signal.SIGTERM,signal.SIG_DFL)
    sys.stdin=io.TextIOWrapper(io.BytesIO(raw))
    from api.dfa_worker import main
    main()
'''
    def fixture_process(command,**kwargs):
        if command[-2:]==['-m','api.dfa_worker']:
            command=[sys.executable,'-E','-B','-c',code]
        return real_popen(command,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',fixture_process)
    outcomes=[]
    error=[]
    transitions=[]
    committed_exits={}
    real_record=supervisor.lane.record
    def record(value):
        real_record(value)
        transitions.append(json.loads(json.dumps(value)))
    monkeypatch.setattr(supervisor.lane,'record',record)
    real_record_exit=supervisor.record_exit
    def record_exit():
        real_record_exit()
        value=supervisor.lane.actor()
        committed_exits[value['actor_token']]=time.monotonic()
    monkeypatch.setattr(supervisor,'record_exit',record_exit)
    def run():
        try:supervisor.run()
        except Exception as exc:error.append(str(exc))
    worker=threading.Thread(target=run,daemon=True);worker.start()
    try:
        for trial in range(100):
            deadline=time.monotonic()+15
            while True:
                with factory() as db:
                    control=db.get(Control,1)
                    actor=control.actor
                    automatic=db.query(Run).filter_by(origin='automatic').first()
                    if actor and actor.get('state')=='occupied' and automatic and actor['binding']['input']==automatic.input_digest:
                        break
                if time.monotonic()>deadline: raise AssertionError({'trial':trial,'stage':'automatic_start','errors':error})
                time.sleep(.01)
            # Actual durable manual retry transaction, bracketed conservatively.
            with factory() as db:
                row=db.get(Run,manual['id'])
                if row.status=='complete': row.status='failed';db.commit()
                generation=row.generation
            # A healthy trial starts only with freshly completed real control
            # readiness. No fixture heartbeat or permission timestamp is forged.
            health_deadline=time.monotonic()+15
            while True:
                with factory() as db:
                    health=db.get(Control,1)
                    fresh=health.ready_until and health.ready_until > datetime.utcnow()+timedelta(seconds=.4)
                    readiness_sequence=health.readiness_sequence
                if fresh:break
                if time.monotonic()>health_deadline:raise AssertionError({'trial':trial,'stage':'fresh_control_readiness','errors':error,'control':supervisor.control_observation})
                time.sleep(.01)
            before=time.monotonic()
            with factory() as db:
                admitted=service.change_run(db,owner,'123',manual['id'],'retry',generation)
            after=time.monotonic()
            until=before+5
            while True:
                with factory() as db:
                    acknowledged=db.get(Control,1).actor
                if acknowledged and acknowledged.get('state')=='idle' and acknowledged.get('actor_token')==actor['actor_token']:
                    observed=time.monotonic();break
                # A new actor may start only after the old exit receipt was committed.
                if actor['actor_token'] in committed_exits:
                    observed=max(time.monotonic(),committed_exits[actor['actor_token']]);break
                if time.monotonic()>until: raise AssertionError({'trial':trial,'stage':'retirement','errors':error})
                time.sleep(.005)
            outcomes.append({'readiness_sequence':readiness_sequence,'trial':trial,'admission_id':admitted['admission_id'],'commit_bracket_seconds':after-before,
                             'availability_upper_seconds':observed-before})
            progress=Path(__file__).resolve().parents[1]/'.git/pr871-capacity-r3-steps.jsonl'
            with progress.open('a') as stream:stream.write(json.dumps(outcomes[-1])+'\n')
            deadline=time.monotonic()+15
            while True:
                with factory() as db:
                    if db.get(Run,manual['id']).status=='complete':break
                if time.monotonic()>deadline:raise AssertionError({'trial':trial,'stage':'manual_start_completion','errors':error})
                time.sleep(.01)
            starts=[value for value in transitions if value.get('state')=='occupied'
                    and value.get('binding',{}).get('generation')==admitted['generation']
                    and value.get('binding',{}).get('input')==row.input_digest]
            assert starts
            outcomes[-1]['manual_process_start_upper_seconds']=starts[-1]['launch_at']-before
        for previous,next_actor in zip(transitions,transitions[1:]):
            if next_actor['state']=='launching' and previous.get('actor_token') != next_actor.get('actor_token'):
                assert previous['state']=='idle'
                assert next_actor['launch_at']>=previous['exit_observed_at']
        assert len(outcomes)==100
        assert max(row['availability_upper_seconds'] for row in outcomes)<=5
        (tmp_path/'capacity.json').write_text(json.dumps(outcomes,indent=2))
        destination=Path(__file__).resolve().parents[1]/'test-screenshots/ui-quality/pr871'
        destination.mkdir(parents=True,exist_ok=True)
        (destination/'synthetic-capacity.json').write_text(json.dumps({'profile':'one SQLite writer + reserved control connection; 650 native RR; post-handshake ignored-TERM automatic fixture; real manual child computation',
            'trials':outcomes,'unproved':['raw-loading preemption','maximum-input/native-compute preemption','output-transfer preemption','Azure/API/sync contention','60-minute mixed-load soak','cross-host placement/handover']},indent=2))
    finally:
        supervisor.stop.set();worker.join(timeout=10)
        assert not worker.is_alive(),error
