"""Exact acquisition-test attempt accounting, never an availability certificate."""

def assert_attempt_ledger(attempts, binding, before_recoveries=0):
    from api.dfa_supervisor import TRANSIENT_FAILURES
    assert attempts, 'missing claim provenance'
    recoveries=before_recoveries
    previous_finish=None
    leases=set();actors=set()
    for attempt in attempts:
        assert isinstance(attempt.get('claim'),dict), 'missing claim provenance'
        claim=attempt['claim']
        assert claim['job']==binding and claim['state']['status']=='running'
        assert claim['state']['lease_token_hash'] and claim['state']['recoveries']==recoveries
        assert claim['state']['lease_token_hash'] not in leases, 'reused claim lease'
        leases.add(claim['state']['lease_token_hash'])
        assert claim['state']['generation']==binding['generation'] and claim['state']['execution_epoch']==binding['epoch']
        assert claim['state']['input_digest']==binding['input'] and claim['state']['origin']==binding['origin']
        assert claim['current'] is True and claim['mode']=='automatic', 'missing claim authority'
        if previous_finish is not None:assert previous_finish<=claim['at'], 'reuse before owner finish'
        occupied=attempt['occupied_ack'];finish=attempt['finish'];ack=attempt['finish_ack']
        assert occupied and finish and ack, 'missing occupied/finish provenance'
        actor=finish['actor']
        assert actor['actor'] and actor['actor'] not in actors and actor['incarnation'], 'missing/reused actor'
        actors.add(actor['actor'])
        assert isinstance(actor['identity'],dict) and all(actor['identity'].get(k) is not None for k in ('pid','pgid','start')), 'missing physical identity'
        assert finish['pending_actor']==actor and finish['pending_job']==binding, 'missing immutable pending binding'
        assert actor['actor']==occupied['actor']['actor'] and actor['binding']==occupied['actor']['binding']
        assert actor['binding']=={k:binding[k] for k in ('generation','epoch','input')}
        assert actor['identity']==occupied['actor']['identity'] and actor['incarnation']==occupied['actor']['incarnation']
        assert actor['state']=='idle' and finish['cancelled'] is True
        assert finish['exit_ack_at'] is not None, 'missing durable exit ACK'
        assert occupied['at']<=actor['exit_observed_at']<=finish['exit_ack_at']<=finish['at']<=ack['at']
        assert finish['job']==binding and finish['before']['recoveries']==recoveries
        assert finish['before']['status']=='running' and finish['before']['lease_token_hash']==claim['state']['lease_token_hash']
        assert finish['before']['generation']==binding['generation'] and ack['after']['generation']==binding['generation']
        assert finish['pending_status']==finish['status'] and finish['pending_reason']==finish['reason']
        assert finish['current'] is True and finish['mode']=='automatic', 'missing finish authority'
        if finish['status']=='output':
            assert finish['reason'] is None and ack['after']['status']=='complete' and ack['after']['result_present']
            assert ack['after']['recoveries']==recoveries
            assert attempt is attempts[-1], 'execution after terminal result'
        else:
            assert finish['status']=='failed' and finish['reason'] in TRANSIENT_FAILURES, 'unexplained recovery'
            trigger=finish['trigger']
            assert trigger and trigger['expired'] and not trigger['timed_out']
            assert trigger['actor']['actor']==actor['actor'], 'failure belongs to another actor'
            assert trigger['decision'] is not None, 'missing permission decision'
            if trigger['decision']['reason'] is not None:
                assert trigger['decision']['job']['job']==binding['job']
                assert trigger['decision']['job']['generation']==binding['generation']
                assert trigger['decision']['actor']['actor']==actor['actor']
            assert recoveries==0, 'extra automatic recovery'
            recoveries+=1
            assert ack['after']['status']=='queued' and ack['after']['recoveries']==recoveries
            assert ack['after']['error_code']==finish['reason'] and not ack['after']['result_present']
        assert not ack['after']['lease_token_hash']
        previous_finish=ack['at']
    assert attempts[-1]['finish_ack']['after']['status']=='complete'
    assert len(attempts)==recoveries-before_recoveries+1, 'unaccounted execution'
    return recoveries
