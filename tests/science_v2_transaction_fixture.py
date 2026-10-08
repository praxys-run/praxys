"""Disposable designated transactions; only external auth transport is offline."""
from dataclasses import replace
from pathlib import Path
import json,shutil,sys
from pytest import MonkeyPatch
from tests.test_science_activation import designated_case,commit,_designated_stop_context
from analysis.evidence_registry import load_science_registry
from analysis.science_artifacts import (ImplementationBinding,ReviewSubjectKind,ReviewRole,science_decision_digest,
 approval_statement_for_subject,render_approval_comment_template,digest_payload,build_policy_contract,load_science_approvals)
from analysis.science_activation import (ActivationContext,project_active_registry,diff_digest,render_activation_comment,
 WORKFLOW_PATH,VALIDATION_JOB,PROBE_JOB,git)
from analysis.science_approval_workflow import approvals_from_github_comments,materialize_science_approvals,verify_science_approval_changes
from analysis.science_admission_amendment import DESIGNATED,amendment_value
from analysis.science_implementation_stop import render_stop_comment,stop_from_comment,materialize_stop

def decision_comment(registry,number=42):
 role=ReviewRole.DECISION_APPROVER
 return dict(id=90,body=render_approval_comment_template(subject_kind=ReviewSubjectKind.SCIENCE_DECISION,subject_id=DESIGNATED,
  subject_digest=science_decision_digest(registry.decisions[DESIGNATED]),role=role,
  approval_statement=approval_statement_for_subject(registry,subject_kind=ReviewSubjectKind.SCIENCE_DECISION,subject_id=DESIGNATED,role=role)),
  user={'type':'User','login':'synthetic'},created_at='2026-10-08T01:00:00Z',html_url=f'https://github.com/praxys-run/praxys/pull/{number}#issuecomment-90')

def active_context(root,base,head,number,prior=None):
 registry=load_science_registry(root/'data/science');projected=project_active_registry(registry,DESIGNATED)
 contract=build_policy_contract(projected,DESIGNATED)
 proof=dict(schema_version=2,purpose='dfa-v2-activation',repository='praxys-run/praxys',pull_request=number,
  base_sha=base,reviewed_head_sha=head,diff_digest=diff_digest(root,base,head),active_contract_digest=contract.contract_digest,
  subject_id=DESIGNATED,admission_amendment=amendment_value(registry.decisions[DESIGNATED]).model_dump(mode='json'),
  baseline_guard_result='denied',workflow_path=WORKFLOW_PATH,workflow_sha=base,run_id=5,run_attempt=1,conclusion='success',required_jobs=[VALIDATION_JOB,PROBE_JOB])
 binding=ImplementationBinding(version=1,repository='praxys-run/praxys',pull_request=number,base_sha=base,reviewed_head_sha=head,
  diff_digest=proof['diff_digest'],active_contract_digest=contract.contract_digest,validation_run_id=5,validation_run_attempt=1,
  validation_workflow_sha=base,validation_artifact_id=6,validation_digest=digest_payload(proof))
 context=ActivationContext(root,'praxys-run/praxys',number,base,head,{binding.envelope_digest:proof})
 if prior is not None:
  context=replace(context,source_comments={prior['html_url']:{'comment':prior,'permission':'admin'}})
 body=render_activation_comment(registry,DESIGNATED,binding,activation_context=context)
 comment=dict(id=91,body=body,user={'type':'User','login':'synthetic'},created_at='2026-10-08T02:00:00Z',
  html_url=f'https://github.com/praxys-run/praxys/pull/{number}#issuecomment-91')
 events=dict(context.source_comments or {});events[comment['html_url']]={'comment':comment,'permission':'admin'}
 context=replace(context,source_comments=events)
 return context,binding,comment

def cli_verify(base,root,comments,context,stop_context,store,*,transport_mutation=None):
    """Actual native readers; only GitHubReader read/pages transport is offline."""
    import io,re,zipfile
    from hashlib import sha256
    from copy import deepcopy
    from analysis.science_activation import COLLECTOR_JOB,implementation_envelope
    from scripts import verify_science_approval_sources as cli
    import analysis.science_activation_github as activation_reader
    import analysis.science_stop_github as stop_reader
    cp=store/'comments.json';pp=store/'permissions.json'
    cp.write_text(json.dumps(comments));pp.write_text(json.dumps({'synthetic':'admin'}))
    repository=stop_context.repository;number=stop_context.pull_request
    pr=dict(number=number,state='open',base=dict(ref='main',repo={'full_name':repository},sha=stop_context.base_sha),
            head=dict(repo={'full_name':repository},sha=stop_context.head_sha))
    events={c['id']:c for c in comments}
    if context is not None:
        events.update({item['comment']['id']:item['comment'] for item in (getattr(context,'source_comments',None) or {}).values()})
    # Only recorded events are offered; missing/deleted historical sources fail.
    artifacts={};runs={};payloads={};requests=[]
    def add_artifact(manifest,artifact_id):
        run_id=manifest['run_id'];attempt=manifest['run_attempt'];workflow=manifest['workflow_sha']
        runs[run_id]=dict(id=run_id,run_attempt=attempt,head_sha=workflow,head_branch='main',event='workflow_dispatch',
            path=WORKFLOW_PATH,repository={'full_name':repository},head_repository={'full_name':repository},conclusion='success')
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:archive.writestr('validation.json',json.dumps(manifest,sort_keys=True))
        content=data.getvalue();payloads[artifact_id]=content
        artifacts[artifact_id]=dict(id=artifact_id,name=f'science-activation-validation-{run_id}-{attempt}',expired=False,
            workflow_run={'id':run_id,'head_sha':workflow},size_in_bytes=len(content),digest='sha256:'+sha256(content).hexdigest())
    for event in list(events.values()):
        envelope=implementation_envelope(str(event.get('body','')))
        if envelope is None:continue
        binding=ImplementationBinding.model_validate(envelope['implementation_binding'])
        if context is not None and binding.envelope_digest in context.validations:
            proof=dict(context.validations[binding.envelope_digest])
        else:
            proof=dict(schema_version=2,purpose='dfa-v2-activation',repository=binding.repository,pull_request=binding.pull_request,
                base_sha=binding.base_sha,reviewed_head_sha=binding.reviewed_head_sha,diff_digest=binding.diff_digest,
                active_contract_digest=binding.active_contract_digest,subject_id=envelope['subject_id'],
                admission_amendment=amendment_value(load_science_registry(root/'data/science').decisions[DESIGNATED]).model_dump(mode='json'),
                baseline_guard_result='denied',workflow_path=WORKFLOW_PATH,workflow_sha=binding.validation_workflow_sha,
                run_id=binding.validation_run_id,run_attempt=binding.validation_run_attempt,conclusion='success',required_jobs=[VALIDATION_JOB,PROBE_JOB])
        assert digest_payload(proof)==binding.validation_digest
        add_artifact(proof,binding.validation_artifact_id)
    for index,proof in enumerate(stop_context.maintenance_evidence.values()):add_artifact(dict(proof),70+index)
    if transport_mutation=='pr-head':pr['head']['sha']='0'*40
    if transport_mutation=='run-attempt':runs[5]['run_attempt']=2
    if transport_mutation=='artifact-digest':artifacts[6]['digest']='sha256:'+'0'*64
    if transport_mutation=='artifact-association':artifacts[6]['workflow_run']['id']=99
    if transport_mutation=='retained-event-body':events[90]['body']='forged historical source'
    if transport_mutation=='retained-event-timestamp':events[90]['created_at']='2026-10-08T04:00:00Z'
    class OfflineGitHubReader:
        def __init__(self,repo):
            assert repo==repository
            self.repository=repo
        def read(self,path,*,binary=False):
            requests.append({'method':'read','path':path,'binary':binary})
            if path==f'pulls/{number}':return deepcopy(pr)
            if path==f'collaborators/synthetic/permission':return {'permission':'read' if transport_mutation=='permission' else 'admin'}
            if path.startswith('issues/comments/'):
                identity=int(path.rsplit('/',1)[1])
                if identity not in events:raise ValueError('Offline transport source event unavailable')
                return deepcopy(events[identity])
            if path.startswith('actions/workflows/') and '/runs?' in path:return {'workflow_runs':deepcopy(list(runs.values()))}
            match=re.fullmatch(r'actions/runs/([0-9]+)',path)
            if match:return deepcopy(runs[int(match[1])])
            match=re.fullmatch(r'actions/artifacts/([0-9]+)(/zip)?',path)
            if match:return payloads[int(match[1])] if match[2] else deepcopy(artifacts[int(match[1])])
            raise AssertionError('Unexpected offline native-reader request: '+path)
        def pages(self,path,key=None):
            requests.append({'method':'pages','path':path,'key':key})
            if path==f'issues/{number}/comments':return deepcopy(comments)
            match=re.fullmatch(r'actions/runs/([0-9]+)/attempts/([0-9]+)/jobs',path)
            if match:
                run_id,attempt=map(int,match.groups());assert runs[run_id]['run_attempt']==attempt
                return [dict(id=run_id*10+i,run_id=run_id,status='completed',name=name,conclusion='skipped' if transport_mutation=='probe-job' and name==PROBE_JOB else 'success')
                        for i,name in enumerate([VALIDATION_JOB,PROBE_JOB,COLLECTOR_JOB],1)]
            match=re.fullmatch(r'actions/runs/([0-9]+)/artifacts',path)
            if match:return deepcopy([a for a in artifacts.values() if a['workflow_run']['id']==int(match[1])])
            raise AssertionError('Unexpected offline native-reader pages: '+path)
    try:
        with MonkeyPatch.context() as patch:
            patch.setattr(activation_reader,'GitHubReader',OfflineGitHubReader)
            patch.setattr(stop_reader,'GitHubReader',OfflineGitHubReader)
            patch.setattr(sys,'argv',['verify','--base-science-dir',str(base/'data/science'),'--head-science-dir',str(root/'data/science'),
                '--github-comments',str(cp),'--github-permissions',str(pp),'--repository',repository,'--pull-request',str(number)])
            return cli.main()
    finally:
        (store/'native-reader-offline-transport.json').write_text(json.dumps({'kind':'Only read/pages transport substituted; native authenticated contexts, source/permission/PR/run/job/archive/digest/history/recheck validators executed',
            'requests':requests,'pr':pr,'events':events,'runs':runs,'artifacts':artifacts},indent=2)+'\n')


def staged_case(directory,kind):
    root,science,context,_,_=designated_case(directory)
    base_root=directory/'initial-base';shutil.copytree(root,base_root,symlinks=True)
    git(base_root,'checkout','--detach',context.base_sha)
    prior=decision_comment(load_science_registry(science))
    stop_context=_designated_stop_context(science,context)
    approvals=approvals_from_github_comments(science,[prior],{'synthetic':'admin'},stop_context=stop_context)
    materialize_science_approvals(science,approvals,stop_context=stop_context)
    verify_science_approval_changes(base_root/'data/science',science,[prior],{'synthetic':'admin'},stop_context=stop_context)
    inactive=commit(root,'synthetic immutable accepted-inactive predecessor')
    if kind=='later-pr':
        base_root=directory/'later-base';shutil.copytree(root,base_root,symlinks=True)
    base=context.base_sha if kind=='same-pr' else inactive
    context,binding,fresh=active_context(root,base,inactive,42 if kind=='same-pr' else 43,prior=prior)
    stop_context=_designated_stop_context(science,context)
    comments=[prior,fresh] if kind=='same-pr' else [fresh]
    return root,base_root,context,binding,stop_context,comments,prior


def direct_active_case(directory):
    root,science,context,_,_=designated_case(directory)
    context,binding,fresh=active_context(root,context.base_sha,context.head_sha,42)
    approvals=approvals_from_github_comments(science,[fresh],{'synthetic':'admin'},activation_context=context)
    materialize_science_approvals(science,approvals,activation_context=context)
    context.verify_replay(binding,approvals,root)
    return root,context,binding,fresh


def lawful_stop_case(directory,*,staged=False):
    if staged:
        root,_,context,binding,_,comments,prior=staged_case(directory,'same-pr')
        approvals=approvals_from_github_comments(root/'data/science',comments,{'synthetic':'admin'},activation_context=context)
        materialize_science_approvals(root/'data/science',approvals,activation_context=context)
    else:
        root,context,binding,fresh=direct_active_case(directory);comments=[fresh]
    active=commit(root,'synthetic legitimate active V2 baseline')
    baseline=directory/'active-base';shutil.copytree(root,baseline,symlinks=True)
    target=dict(schema_version=1,action='stop',repository=context.repository,subject_id=DESIGNATED,
        active_contract_digest=binding.active_contract_digest,implementation_envelope_digest=binding.envelope_digest)
    event=dict(id=92,body=render_stop_comment(target),user={'type':'User','login':'synthetic'},
        created_at=next(a for a in load_science_approvals(baseline/'data/science')
                        if a.subject_id==DESIGNATED and a.role==ReviewRole.IMPLEMENTATION_REVIEWER).reviewed_on.isoformat()+'T03:00:00Z',
        html_url='https://github.com/praxys-run/praxys/pull/42#issuecomment-92')
    stop=stop_from_comment(event,'admin',context.repository);materialize_stop(root,stop)
    stopped_head=commit(root,'synthetic canonical exact two-file V2 STOP')
    transport=replace(context,base_sha=active,head_sha=stopped_head)
    stop_context=replace(_designated_stop_context(root/'data/science',transport),authenticated_stops=(stop,))
    return root,baseline,stop_context,comments,event,stop
