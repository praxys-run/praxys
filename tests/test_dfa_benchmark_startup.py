"""Bounded real cold-start regressions; no capacity cohort is run here."""
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from hashlib import sha256

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api import activity_dfa as service
from db.models import ActivityDFAControl as Control, ActivityDFARun as Run
from tests.test_activity_dfa import store, confirmed
from tests.test_dfa_origins import both_origins, complete_unit
from tests.test_dfa_supervisor_capacity import PriorityEvidence


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('renewal',['timely','denied','delayed_ack'])
def test_first_automatic_child_requires_completed_valid_renewal(both_origins,monkeypatch,renewal):
    factory,owner=both_origins
    _,manual=confirmed(factory,owner)
    with factory() as db:claim=service.claim(db)
    service.execute(factory,*claim)
    complete_unit(factory,owner)
    supervisor=factory.dfa_supervisor
    inherited={'allowed':supervisor.allowed,'permission_until':supervisor.permission_until}
    assert inherited['allowed'] and inherited['permission_until']>time.monotonic()+10
    supervisor.allowed=False;supervisor.permission_until=0.
    url=factory.kw['bind'].url
    args={'timeout':.1} if url.get_backend_name()=='sqlite' else {
        'connect_timeout':1,'options':'-c statement_timeout=200 -c lock_timeout=200'}
    engine=create_engine(url,pool_size=2,max_overflow=0,pool_timeout=.1,connect_args=args)
    supervisor.controls=sessionmaker(bind=engine)
    evidence=PriorityEvidence(supervisor,monkeypatch)
    pending=threading.Event();release=threading.Event();started=threading.Event()
    commits=[];launches=[];errors=[]
    def before_commit(db):
        if threading.current_thread().name=='dfa-control' and db.get_bind() is engine and renewal=='timely' and not pending.is_set():
            pending.set();assert release.wait(2)
    def after_commit(db):
        if threading.current_thread().name=='dfa-control' and db.get_bind() is engine:
            # Commit is SQL-visible here; this is not yet Supervisor's ACK.
            commits.append({'sql_visible_after_commit_callback_at':time.monotonic()})
            if renewal=='delayed_ack':time.sleep(.30)
    event.listen(supervisor.controls.class_,'before_commit',before_commit)
    event.listen(supervisor.controls.class_,'after_commit',after_commit)
    actual_renew=supervisor.renew
    def renew():
        if renewal=='denied':
            with factory() as db:
                control=db.get(Control,1);control.drained=True;control.ready_until=None;db.commit()
        started.set();actual_renew()
    monkeypatch.setattr(supervisor,'renew',renew)
    actual_popen=subprocess.Popen
    code="import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)"
    def child(command,**kwargs):
        if command[-2:]==['-m','api.dfa_worker']:
            launches.append({'popen_invoked_at':time.monotonic(),'allowed':supervisor.allowed,
                             'permission_until':supervisor.permission_until})
            command=[sys.executable,'-E','-B','-c',code]
        return actual_popen(command,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',child)
    def worker():
        try:supervisor.run()
        except Exception as exc:errors.append(type(exc).__name__)
    thread=threading.Thread(target=worker);thread.start()
    startup=None;outcome='failed'
    try:
        assert started.wait(3),errors
        if renewal=='timely':
            assert pending.wait(3),errors
            time.sleep(.025)
            assert not launches and not evidence.renewals
            assert supervisor.allowed is False and supervisor.permission_until==0
            release.set()
            deadline=time.monotonic()+5
            while True:
                with factory() as db:
                    control=db.get(Control,1);actor=control.actor
                    automatic=db.query(Run).filter_by(origin='automatic').first()
                if actor and actor['state']=='occupied' and automatic and actor['binding']['input']==automatic.input_digest:break
                assert time.monotonic()<deadline,{'errors':errors,'launches':launches,'renewals':evidence.renewals}
                time.sleep(.005)
            startup=evidence.startup_launch(actor)
            assert len(launches)==1 and launches[0]['allowed'] is True
            assert startup['completed_valid_renewal']['epoch']==control.epoch
            assert actor['incarnation']==control.incarnation==supervisor.identity
        else:
            deadline=time.monotonic()+3
            expected='denied' if renewal=='denied' else 'deadline'
            while supervisor.control_observation['state']!=expected:
                assert time.monotonic()<deadline,{'control':supervisor.control_observation,'errors':errors}
                time.sleep(.005)
            assert not launches and not evidence.renewals
            assert supervisor.allowed is False and supervisor.permission_until==0
        assert not errors
        outcome='passed'
    finally:
        release.set();supervisor.stop.set();thread.join(3)
        root=Path(__file__).resolve().parents[1]
        (root/f'.git/pr871-benchmark-startup-{renewal}-{url.get_backend_name()}-{time.time_ns()}.json').write_text(json.dumps({
            'outcome':outcome,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
            'inherited_setup_permission':inherited,'renewal':renewal,'startup':startup,'launches':launches,
            'commit_return_observations':commits,'completed_valid_renewals':evidence.renewals,'errors':errors,
            'source_bindings':{str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in
                [Path(__file__),root/'tests/test_dfa_supervisor_capacity.py',root/'api/dfa_supervisor.py',root/'tests/dfa_supervisor_harness.py']},
            'perturbation':'bounded before-commit pause or300ms late-ACK for startup boundary only; never used in unparked cohort; real750ms timer unchanged'},indent=2))
        event.remove(supervisor.controls.class_,'before_commit',before_commit)
        event.remove(supervisor.controls.class_,'after_commit',after_commit)
        engine.dispose()
        assert not thread.is_alive(),errors
