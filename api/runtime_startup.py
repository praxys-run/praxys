"""Repository-owned API startup with an optional, default-disabled DFA candidate."""
import os
import signal
import subprocess
import sys
import time
from api.dfa_physical import worker_environment

SUPERVISOR_ENV = {'PRAXYS_DATABASE_URL','DATABASE_URL','DATA_DIR','PRAXYS_DFA_SUPERVISOR_ENABLED',
    'PRAXYS_DFA_PLACEMENT_ID','PRAXYS_DFA_INCARNATION','PRAXYS_FEEDBACK_BLOB_CONTAINER',
    'PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING','PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL',
    'IDENTITY_ENDPOINT','IDENTITY_HEADER','AZURE_CLIENT_ID','STATSIG_SDK_KEY','STATSIG_ENV',
    'WEBSITE_SLOT_NAME','WEBSITE_INSTANCE_ID','WEBSITE_SITE_NAME','PRAXYS_DB_AUTH',
    'PRAXYS_DISABLE_CN_PROCESSING','PRAXYS_DISABLE_MINIAPP_PROCESSING'}


def supervisor_environment():
    return {**worker_environment(), **{key:os.environ[key] for key in SUPERVISOR_ENV if key in os.environ},
            'PRAXYS_DB_POOL_SIZE':'1','PRAXYS_DB_MAX_OVERFLOW':'0'}


def main():
    workers=int(os.environ.get('PRAXYS_API_WORKERS','1'))
    if not 1 <= workers <= 8:
        raise ValueError('Invalid API worker count')
    from db import session
    session.init_db()
    session.dispose_engines()
    children=[]
    if os.environ.get('PRAXYS_DFA_SUPERVISOR_ENABLED','').lower()=='true':
        children.append(subprocess.Popen([sys.executable,'-m','api.dfa_supervisor'],env=supervisor_environment()))
    api=subprocess.Popen([sys.executable,'-m','gunicorn','api.main:app','-k','uvicorn.workers.UvicornWorker',
        '--workers',str(workers),'--bind','0.0.0.0:'+os.environ.get('PORT','8000'),'--timeout','180'])
    children.append(api)
    stopping=False
    def request_stop(signum,frame):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,request_stop)
    signal.signal(signal.SIGINT,request_stop)
    while api.poll() is None and not stopping:
        time.sleep(.1)
    # First durable both-origin admission/publication fence, then termination.
    from db.models import ActivityDFAControl
    session.init_db()
    with session.SessionLocal() as db:
        row=db.query(ActivityDFAControl).filter_by(id=1).with_for_update().first()
        if row:
            row.drained=True; row.enabled=False; row.ready_until=None
            db.commit()
    session.dispose_engines()
    for child in children:
        if child.poll() is None: child.terminate()
    for child in children:
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # No exit assertion or automatic replacement follows a timeout.
            pass
    return api.returncode or 0


if __name__=='__main__':
    raise SystemExit(main())
