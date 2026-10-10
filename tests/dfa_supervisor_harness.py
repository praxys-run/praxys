"""Explicitly synthetic direct-step harness using the real Linux supervisor.

It supplies fixture-only placement and readiness, never activation authority.
Legacy lifecycle tests can drive steps without reintroducing API computation.
"""
from datetime import datetime, timedelta
from pathlib import Path
import queue
import time

from api.dfa_supervisor import Supervisor
from db.models import ActivityDFAControl, ActivityDFARun

IDENTITY = {'resource':'synthetic','slot':'fixture','instance':'fixture','source':'fixture',
            'incarnation':'fixture','epoch':1,'boot':'fixture','namespace':'fixture'}


def install(factory, directory: Path, monkeypatch):
    from api import activity_dfa as service
    supervisor = Supervisor(factory, factory, IDENTITY, directory / 'physical')
    with factory() as db:
        control=db.get(ActivityDFAControl,1)
        if control is None:
            control=ActivityDFAControl(id=1);db.add(control)
        # This disposable fixture owns its synthetic global control row. Reset
        # the matching epoch after negative cases changed it; production never
        # self-elects or rewrites an incarnation this way.
        control.incarnation=IDENTITY;control.epoch=IDENTITY['epoch'];control.enabled=True;control.drained=False
        control.ready_until=datetime.utcnow()+timedelta(hours=1)
        db.commit()
    supervisor.allowed = True
    supervisor.permission_until = time.monotonic()+3600
    factory.dfa_supervisor = supervisor
    jobs = {}

    def claim(db):
        db.rollback()
        value = supervisor.acquire_job()
        if value:
            jobs[value['id']] = value
            with factory() as connection:
                token = connection.get(ActivityDFARun,value['id']).lease_token
            return value['id'], value['generation'], token
        return None

    def execute(session_factory, run_id, generation, token):
        value = jobs.get(run_id)
        if value is None or value['generation'] != generation:
            return
        outputs = queue.Queue()
        supervisor.work(value,outputs)
        supervisor.lane.retire()
        status,output = outputs.get(timeout=5)
        supervisor.finish(value,status,output)

    monkeypatch.setattr(service,'claim',claim)
    monkeypatch.setattr(service,'execute',execute)
    return supervisor
