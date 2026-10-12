"""Actual service outcomes remain distinct from causal preemption certification."""
from copy import copy,deepcopy
from datetime import datetime,timedelta
from pathlib import Path
import json,os,select,subprocess,sys,threading,time
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine,event,text,update
from sqlalchemy.orm import sessionmaker
from api import activity_dfa as service
from db.models import ActivityDFAControl as Control,ActivityDFARun as Run
from tests.test_activity_dfa import store,confirmed
from tests.test_dfa_origins import both_origins,complete_unit
from tests.test_dfa_supervisor_capacity import admission_attempt,PriorityEvidence,predeclare_automatic_completions
from tests.dfa_capacity_measurement import observed_requests,workload_eligibility,observe_acceptance,classify_occupied


@pytest.fixture
def outcome_cell(both_origins,monkeypatch):
    factory,owner=both_origins
    _,manual=confirmed(factory,owner)
    with factory() as db:
        row=db.get(Run,manual['id']);row.status='failed';db.commit();manual_input=row.input_digest
    supervisor=factory.dfa_supervisor
    supervisor.allowed=False;supervisor.permission_until=0.
    with factory() as db:db.get(Control,1).ready_until=datetime.utcnow();db.commit()
    engine=create_engine(factory.kw['bind'].url,pool_size=2,max_overflow=0,pool_timeout=.1,connect_args={'timeout':.1})
    supervisor.controls=sessionmaker(bind=engine)
    evidence=PriorityEvidence(supervisor,monkeypatch)
    initial=supervisor.lane.actor();transitions=[initial] if initial else [];available={};errors=[];attempts=[]
    actual_record=supervisor.lane.record
    def record(actor):actual_record(actor);transitions.append(json.loads(json.dumps(actor)))
    monkeypatch.setattr(supervisor.lane,'record',record)
    actual_exit=supervisor.record_exit
    def record_exit():actual_exit();available[supervisor.lane.actor()['actor_token']]=time.monotonic()
    monkeypatch.setattr(supervisor,'record_exit',record_exit)
    cell=SimpleNamespace(factory=factory,owner=owner,manual=manual,manual_input=manual_input,supervisor=supervisor,
        evidence=evidence,transitions=transitions,available=available,errors=errors,attempts=attempts,
        deadline=time.monotonic()+25,force_bad_manual=False)
    read_fd,write_fd=os.pipe();real_popen=subprocess.Popen
    code=f'''import io,json,os,signal,sys,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
raw=sys.stdin.buffer.readline(90*1024*1024+1)
payload=json.loads(raw)
if payload['origin']=='automatic':
    os.write({write_fd},b'A')
    while True:time.sleep(.01)
else:
    signal.signal(signal.SIGTERM,signal.SIG_DFL)
    if __FORCE_BAD_MANUAL__:
        payload['raw_fit']='AA=='
        raw=json.dumps(payload).encode()+b'\\n'
    sys.stdin=io.TextIOWrapper(io.BytesIO(raw))
    from api.dfa_worker import main
    main()
'''
    def child(command,**kw):
        if command[-2:]==['-m','api.dfa_worker']:
            command=[sys.executable,'-E','-B','-c',code.replace('__FORCE_BAD_MANUAL__',repr(cell.force_bad_manual))]
            kw['pass_fds']=(*kw.get('pass_fds',()),write_fd)
        return real_popen(command,**kw)
    monkeypatch.setattr(subprocess,'Popen',child)
    def run():
        try:supervisor.run()
        except Exception as exc:errors.append(type(exc).__name__)
    def start(automatic):
        if automatic:complete_unit(factory,owner)
        cell.worker=threading.Thread(target=run);cell.worker.start()
        if automatic:
            assert select.select([read_fd],[],[],4)[0],errors
            assert os.read(read_fd,1)==b'A'
        wait(lambda:supervisor.control_observation['state']=='ready',cell.deadline,errors)
    cell.start=start
    try:yield cell
    finally:
        supervisor.stop.set()
        if hasattr(cell,'worker'):cell.worker.join(10);assert not cell.worker.is_alive()
        os.close(read_fd);os.close(write_fd);engine.dispose()
        root=Path(__file__).resolve().parents[1]
        (root/f'.git/pr871-capacity-outcome-{time.time_ns()}.json').write_text(json.dumps({
            'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'attempts':attempts,'renewal_decisions':evidence.renewal_decisions,'retirements':evidence.retirements,
            'transitions':transitions,'errors':errors,'scope':'bounded forced boundaries; no operational capacity certificate'},indent=2))


def wait(predicate,deadline,errors):
    while not predicate():
        assert time.monotonic()<deadline,errors
        time.sleep(.005)


def attempt(cell,requests,eligibility):
    return admission_attempt(requests,cell.owner,cell.manual['id'],cell.manual['generation'],cell.attempts,
                             {'eligibility':eligibility,'attempt':len(cell.attempts)})


def observe(cell,admitted,entry):
    return observe_acceptance(cell.factory,cell.owner,admitted,entry,cell.manual_input,cell.evidence,
                              cell.transitions,cell.available,cell.deadline,cell.errors)


def test_drain_denial_backoff_idle_manual_acceptance_completes(outcome_cell):
    c=outcome_cell;c.start(False)
    initial=workload_eligibility(c.factory,c.owner)
    assert not initial['eligible'] and initial['actor']['state']=='idle'
    # Explicit durable drain boundary, not an explanation of original32f loss.
    with c.factory() as db:
        control=db.get(Control,1);control.drained=True;control.ready_until=datetime.utcnow();db.commit()
    requests=observed_requests(c.factory)
    admitted,denial=attempt(c,requests,initial)
    assert admitted is None and denial['no_durable_acceptance']
    before=time.monotonic();c.supervisor.stop.wait(5);denial['backoff_elapsed_seconds']=time.monotonic()-before
    with c.factory() as db:db.get(Control,1).drained=False;db.commit()
    wait(lambda:c.supervisor.control_observation['state']=='ready',c.deadline,c.errors)
    eligibility=workload_eligibility(c.factory,c.owner)
    assert not eligibility['eligible'] and eligibility['actor']['state']=='idle'
    admitted,entry=attempt(c,requests,eligibility);assert admitted
    result=observe(c,admitted,entry)
    assert result['classification']=='idle_service' and result['service']=='complete'
    assert result['post_popen_start_upper_seconds'] is not None and not result['required_preemption']








def test_real_accepted_worker_failure_remains_observed(outcome_cell):
    c=outcome_cell;c.force_bad_manual=True;c.start(False)
    eligibility=workload_eligibility(c.factory,c.owner)
    requests=observed_requests(c.factory)
    admitted,entry=attempt(c,requests,eligibility);assert admitted
    result=observe(c,admitted,entry)
    assert entry['outcome']=='accepted' and result['service']=='failed'
    assert result['last_state']['error_code']=='fit_invalid'
    assert result['manual_actor'] and result['manual_physical_exit'] and result['manual_durable_available_at']
    assert not result['required_preemption']


def test_predeclared_workloads_have_distinct_true_provenance(both_origins):
    factory,owner=both_origins
    plan=predeclare_automatic_completions(factory,owner,3)
    assert len({p['activity_id'] for p in plan})==3
    assert len({p['snapshot_id'] for p in plan})==3 and len({p['receipt_id'] for p in plan})==3
    from db.models import GarminConnectIQJob,GarminConnectIQItem,ActivityDFASyncReceipt
    with factory() as db:
        assert db.query(Run).filter_by(origin='automatic').count()==0
        for item in plan:
            assert db.get(GarminConnectIQJob,item['job_id']).status=='complete'
            assert db.get(GarminConnectIQItem,item['item_id']).status=='complete'
            receipt=db.get(ActivityDFASyncReceipt,item['receipt_id'])
            assert receipt.disposition=='pending' and receipt.run_id is None
