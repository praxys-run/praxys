"""Exact captured launch predecessor, including both legitimate null encodings."""
from copy import deepcopy
import json
import queue
import sys
import threading
import time

import pytest
from sqlalchemy import null
from sqlalchemy.orm import Session, sessionmaker

from api.dfa_physical import PhysicalUnavailable, group_members
from db.models import ActivityDFAControl as Control
from tests.test_activity_dfa import store, confirmed


@pytest.mark.parametrize('store',['sqlite','postgresql'],indirect=True)
@pytest.mark.parametrize('encoding',['json_null','sql_null'])
@pytest.mark.parametrize('change_after_capture',[True,False])
def test_launch_ack_requires_exact_captured_null_semantics(store,monkeypatch,tmp_path,encoding,change_after_capture):
    factory,owner=store
    _,admitted=confirmed(factory,owner)
    supervisor=factory.dfa_supervisor
    records=[];writes=[];acks=[];threads=[]
    work_code=supervisor.work.__func__.__code__
    actual_launch=supervisor.lane.launch
    renewal=supervisor.renew
    def put_null():
        with factory() as db:
            row=db.get(Control,1)
            row.actor=None if encoding=='json_null' else null()
            db.commit()
    if not change_after_capture:put_null()
    class Observed(Session):
        def commit(self):
            caller=sys._getframe(1)
            value=super().commit()
            if caller.f_code is work_code:
                acks.append({'at':time.monotonic(),'actor_token':caller.f_locals['actor']['actor_token']})
            return value
    supervisor.controls=sessionmaker(class_=Observed,**factory.kw)
    def launch(*args,**kwargs):
        captured=deepcopy(sys._getframe(1).f_locals['sql_predecessor'])
        if change_after_capture:assert captured and captured['state']=='idle'
        else:assert captured is None
        actor,child=actual_launch(*args,**kwargs)
        records.append({'captured':captured,'new_actor':deepcopy(actor),'launched_at':time.monotonic()})
        original_stdin=child.stdin
        class CountWrites:
            def write(self,data):
                writes.append({'at':time.monotonic(),'bytes':len(data)})
                return original_stdin.write(data)
            def close(self):return original_stdin.close()
        child.stdin=CountWrites()
        if change_after_capture:
            put_null()
            records.append({'event':'idle_to_null_committed_before_ack','at':time.monotonic(),'encoding':encoding})
        return actor,child
    monkeypatch.setattr(supervisor.lane,'launch',launch)
    supervisor.allowed=False;supervisor.permission_until=0.
    controller=threading.Thread(target=renewal);threads.append(controller);controller.start()
    worker=None;status=None;failure=None;exit_refused=False
    outputs=queue.Queue(maxsize=1)
    cancellation=threading.Event()
    try:
        deadline=time.monotonic()+3
        while not supervisor.allowed:
            assert time.monotonic()<deadline,'genuine completed renewal absent'
            time.sleep(.005)
        job=supervisor.acquire_job();assert job
        with supervisor.lock:supervisor.active=job
        worker=threading.Thread(target=supervisor.work,args=(job,outputs,cancellation));worker.start();worker.join(5)
        assert not worker.is_alive(),'bounded real worker did not finish'
        status,value=outputs.get(timeout=1)
        failure=value if isinstance(value,str) else None
        cancellation.set();supervisor.retired.set()
        with supervisor.physical_mutex:supervisor.lane.retire()
        physical=supervisor.lane.actor()
        assert physical['state']=='idle' and physical['exit_observed_at']>=records[0]['launched_at']
        assert not group_members(physical['identity']['pgid'])
        if change_after_capture:
            # Check simple booleans/statuses so a red never prints numerical or
            # private worker payloads through pytest's assertion representation.
            assert status=='failed'
            assert failure=='binding_changed'
            assert len(acks)==0 and len(writes)==0
            with factory() as db:assert db.get(Control,1).actor is None
            with pytest.raises(PhysicalUnavailable,match='exit_journal_binding_changed'):
                supervisor.record_exit()
            exit_refused=True
            with factory() as db:assert db.get(Control,1).actor is None
        else:
            assert status=='output' and len(acks)==1 and len(writes)==1
            supervisor.record_exit()
            supervisor.finish(job,status,value)
            with factory() as db:
                assert db.get(Control,1).actor['state']=='idle'
                assert db.get(Control,1).actor['actor_token']==records[0]['new_actor']['actor_token']
    finally:
        cancellation.set();supervisor.stop.set()
        for thread in threads:thread.join(3)
        if worker is not None:worker.join(3)
        supervisor.lane.retire();supervisor.lane.close()
        with factory() as db:sql_actor=deepcopy(db.get(Control,1).actor)
        (tmp_path/'launch-predecessor-evidence.json').write_text(json.dumps({
            'encoding':encoding,'change_after_capture':change_after_capture,'records':records,
            'status':status,'safe_failure':failure,'work_commit_acks':acks,'payload_write_counts':writes,
            'physical_actor':supervisor.lane.actor(),'sql_actor':sql_actor,'exit_projection_refused':exit_refused,
            'owned_threads_joined':all(not t.is_alive() for t in threads) and (worker is None or not worker.is_alive())},indent=2))
        assert all(not t.is_alive() for t in threads)
