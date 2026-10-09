"""Designated immutable activation lineage: authenticated inputs, derived output.

Historical ScienceApproval models and payload digests are deliberately unchanged.
A local companion classifies preserved assertions; privileged replay/source checks
establish authority. A candidate companion never authenticates itself.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from analysis.science_admission_amendment import DESIGNATED

Digest = Annotated[StrictStr, Field(pattern=r'^sha256:[0-9a-f]{64}$')]
Revision = Annotated[StrictStr, Field(pattern=r'^[0-9a-f]{40}$')]
LINK_DIR = Path('activation-links')


class StrictLinkModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True, allow_inf_nan=False)


class AssertionSnapshot(StrictLinkModel):
    path: StrictStr
    mode: Literal['100644', '100755']
    bytes_digest: Digest
    assertion: dict[str, Any]
    source_timestamp: StrictStr
    source_comment_id: StrictInt

    @model_validator(mode='after')
    def validate_assertion(self):
        from analysis.science_artifacts import ScienceApproval
        from analysis.science_activation import same_typed_value
        relative = PurePosixPath(self.path)
        if (relative.as_posix() != self.path or relative.is_absolute() or '..' in relative.parts
                or len(relative.parts) != 2 or relative.parts[0] != 'approvals' or relative.suffix != '.yaml'):
            raise ValueError('Link assertion path must be one canonical approval file')
        approval = ScienceApproval.model_validate(self.assertion)
        if not same_typed_value(self.assertion, approval.model_dump(mode='json', exclude_none=True)):
            raise ValueError('Link assertion must preserve exact existing serialized types and fields')
        if approval.subject_id != DESIGNATED or approval.role.value not in {'decision_approver', 'implementation_reviewer'}:
            raise ValueError('Link only covers designated decision/implementation assertions')
        timestamp = source_time(self.source_timestamp)
        if timestamp.date().isoformat() != self.assertion['reviewed_on']:
            raise ValueError('Assertion date differs from authenticated source timestamp')
        match = re.fullmatch(r'https://github.com/praxys-run/praxys/(?:pull|issues)/[1-9][0-9]*#issuecomment-([1-9][0-9]*)',
                             self.assertion['source_ref'])
        if not match or self.source_comment_id <= 0 or int(match[1]) != self.source_comment_id:
            raise ValueError('Assertion immutable source identity mismatch')
        return self


class ActivationLinkInput(StrictLinkModel):
    schema_version: StrictInt
    kind: Literal['designated_v2_activation_input']
    subject_id: Literal['sdr-activity-dfa-alpha1-v2']
    version: StrictInt
    reviewed_head_sha: Revision
    predecessor_path: Literal['decisions/sdr-activity-dfa-alpha1-v2.yaml']
    predecessor_mode: Literal['100644']
    predecessor_blob: Revision
    predecessor_bytes_digest: Digest
    predecessor_payload: dict[str, Any]
    predecessor_digest: Digest
    historical_assertions: list[AssertionSnapshot]
    active_decision_digest: Digest
    implementation_envelope_digest: Digest

    @model_validator(mode='after')
    def validate_input(self):
        from analysis.science_activation import same_typed_value
        from analysis.science_artifacts import digest_payload, science_decision_payload
        from analysis.evidence_registry import ScienceDecisionRecord
        from analysis.science_admission_amendment import prevalidate_amendment_record
        if self.schema_version != 1 or self.version != 2 or not self.historical_assertions:
            raise ValueError('Link requires exact versioned designated predecessor assertions')
        raw = {**self.predecessor_payload, 'status':'accepted', 'approval_mode':'artifact',
               'human_reviewers':[], 'superseded_by':None}
        prevalidate_amendment_record(raw)
        decision = ScienceDecisionRecord.model_validate(raw)
        if (not same_typed_value(science_decision_payload(decision), self.predecessor_payload)
                or decision.artifact_policy.runtime_state.value != 'inactive'
                or digest_payload(self.predecessor_payload) != self.predecessor_digest):
            raise ValueError('Link predecessor payload/digest must be exact accepted-inactive content')
        active = deepcopy(self.predecessor_payload)
        active['artifact_policy']['runtime_state'] = 'active'
        if digest_payload(active) != self.active_decision_digest or self.active_decision_digest == self.predecessor_digest:
            raise ValueError('Link supports only distinct inactive-to-active runtime-state payloads')
        paths = [a.path for a in self.historical_assertions]
        keys = [(a.assertion['reviewer'], a.assertion['source_ref']) for a in self.historical_assertions]
        if paths != sorted(paths) or len(set(paths)) != len(paths) or len(set(keys)) != len(keys):
            raise ValueError('Link predecessor assertions must be complete unique canonical path order')
        for old in self.historical_assertions:
            if old.assertion['role'] != 'decision_approver' or old.assertion['subject_digest'] != self.predecessor_digest:
                raise ValueError('Link history contains an unrelated/stale assertion')
        return self


class ActivationLink(StrictLinkModel):
    schema_version: StrictInt
    kind: Literal['designated_v2_activation_receipt']
    input: ActivationLinkInput
    active_assertion: AssertionSnapshot
    implementation_assertion: AssertionSnapshot

    @model_validator(mode='after')
    def validate_receipt(self):
        from analysis.science_artifacts import ImplementationBinding
        if self.schema_version != 1:
            raise ValueError('Link schema must be actual integer')
        current, implementation = self.active_assertion, self.implementation_assertion
        if (current.assertion['role'] != 'decision_approver'
                or current.assertion['subject_digest'] != self.input.active_decision_digest
                or current.path != active_assertion_path(current.assertion).as_posix()
                or implementation.assertion['role'] != 'implementation_reviewer'
                or current.assertion['reviewer'] != implementation.assertion['reviewer']
                or current.assertion['source_ref'] != implementation.assertion['source_ref']
                or current.source_timestamp != implementation.source_timestamp
                or current.source_comment_id != implementation.source_comment_id):
            raise ValueError('Link fresh current assertions must be one exact active composite source')
        binding = ImplementationBinding.model_validate(implementation.assertion['implementation_binding'])
        if (binding.envelope_digest != self.input.implementation_envelope_digest
                or binding.reviewed_head_sha != self.input.reviewed_head_sha
                or implementation.assertion['subject_digest'] != binding.active_contract_digest):
            raise ValueError('Link implementation input/output envelope mismatch')
        if current.assertion['reviewer'] not in {old.assertion['reviewer'] for old in self.input.historical_assertions}:
            raise ValueError('Staged linkage cannot invent an alternate reviewer')
        for old in self.input.historical_assertions:
            if (old.path in {current.path, implementation.path}
                    or old.assertion['source_ref'] == current.assertion['source_ref']
                    or old.source_comment_id == current.source_comment_id
                    or source_time(old.source_timestamp) >= source_time(current.source_timestamp)):
                raise ValueError('Historical source must be a distinct authenticated earlier event')
        return self


def source_time(value: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)', value):
        raise ValueError('Link requires explicit authenticated UTC event timestamp')
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def byte_digest(value: bytes) -> str:
    return 'sha256:' + sha256(value).hexdigest()


def active_assertion_path(assertion: dict) -> Path:
    if assertion['subject_id'] != DESIGNATED or assertion['role'] != 'decision_approver':
        raise ValueError('Digest-qualified path is designated active decision only')
    slug = re.sub(r'[^A-Za-z0-9_.-]+', '-', assertion['reviewer']).strip('-')
    return Path('approvals') / f"{DESIGNATED}--decision_approver--{slug}--active-{assertion['subject_digest'].removeprefix('sha256:')}.yaml"


def companion_path(active_digest: str) -> Path:
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', active_digest):
        raise ValueError('Invalid link namespace digest')
    return LINK_DIR / f"{DESIGNATED}--{active_digest[7:]}.json"


def approval_entries(science: Path):
    from analysis.science_artifacts import ScienceApproval
    from analysis.science_yaml import load_science_yaml
    from analysis.evidence_registry import _yaml_paths
    return [(p, ScienceApproval.model_validate(load_science_yaml(p.read_text()))) for p in _yaml_paths(science/'approvals')]


def descriptor(path: Path, science: Path, approval, timestamp: str, comment_id: int) -> AssertionSnapshot:
    if path.is_symlink():
        raise ValueError('Link assertion cannot be a symlink')
    return AssertionSnapshot(path=path.relative_to(science).as_posix(), mode='100755' if path.stat().st_mode & 0o111 else '100644',
        bytes_digest=byte_digest(path.read_bytes()), assertion=approval.model_dump(mode='json', exclude_none=True),
        source_timestamp=timestamp, source_comment_id=comment_id)


def _source_for(approval, context, predecessor):
    """Use only source metadata supplied by the privileged authenticated reader."""
    from analysis.science_artifacts import approval_statement_for_subject, render_approval_comment_template
    source = str(approval.source_ref)
    event = (context.source_comments or {}).get(source)
    if not isinstance(event, dict) or set(event) != {'comment','permission'}:
        raise ValueError('Missing authenticated historical assertion source transport')
    comment, permission = event['comment'], event['permission']
    expected = render_approval_comment_template(subject_kind=approval.subject_kind, subject_id=approval.subject_id,
        subject_digest=approval.subject_digest, role=approval.role,
        approval_statement=approval_statement_for_subject(predecessor,subject_kind=approval.subject_kind,subject_id=approval.subject_id,role=approval.role))
    if (permission not in {'write','maintain','admin'} or type(comment.get('id')) is not int
            or comment.get('html_url') != source or comment.get('user',{}).get('type') != 'User'
            or comment.get('user',{}).get('login') != approval.reviewer.removeprefix('github:')
            or comment.get('body','').strip() != expected.strip()
            or source_time(comment.get('created_at')).date() != approval.reviewed_on):
        raise ValueError('Historical assertion source identity/permission/content/timestamp mismatch')
    # Same PR: its prior event must be in the complete authenticated comment set.
    # Later PR: the exact predecessor assertion must already be in trusted base.
    from analysis.science_activation import git_tree, git
    if f'/pull/{context.pull_request}#' not in source and f'/issues/{context.pull_request}#' not in source:
        path = next(p for p,a in approval_entries(predecessor.science_dir) if a == approval)
        relative = 'data/science/' + path.relative_to(predecessor.science_dir).as_posix()
        tree = git_tree(context.repository_root, context.base_sha)
        if (relative not in tree or git(context.repository_root,'cat-file','blob',tree[relative][1]) != path.read_bytes()
                or tree[relative][0]!=('100755' if path.stat().st_mode & 0o111 else '100644')):
            raise ValueError('Later-PR assertion lineage is absent from exact trusted base')
    return comment['created_at'], comment['id']


def activation_input(registry, binding, context) -> ActivationLinkInput | None:
    """Read exact reviewed preapproval Git snapshot, never the active output."""
    from analysis.science_activation import ActivationContext, git, git_tree
    from analysis.evidence_registry import ScienceDecisionRecord, load_science_registry
    from analysis.science_artifacts import science_decision_digest, science_decision_payload
    from analysis.science_yaml import load_science_yaml
    import io, tarfile, tempfile
    if not isinstance(context, ActivationContext):
        # Only a direct draft projection without history may lack this reader.
        old = [a for _,a in approval_entries(registry.science_dir) if a.subject_id == DESIGNATED and a.role.value == 'decision_approver']
        from analysis.science_artifacts import science_decision_digest
        if any(a.subject_digest!=science_decision_digest(registry.decisions[DESIGNATED]) for a in old) or registry.decisions[DESIGNATED].artifact_policy.runtime_state.value=='inactive' and old:
            raise ValueError('Staged activation requires authenticated exact predecessor snapshot')
        return None
    relative = 'data/science/decisions/' + DESIGNATED + '.yaml'
    tree = git_tree(context.repository_root, binding.reviewed_head_sha)
    if relative not in tree:
        raise ValueError('Designated predecessor snapshot is missing')
    mode, blob = tree[relative]
    raw_bytes = git(context.repository_root,'cat-file','blob',blob)
    raw = load_science_yaml(raw_bytes.decode())
    decision = ScienceDecisionRecord.model_validate(raw)
    if decision.status.value == 'draft':
        return None
    if decision.status.value != 'accepted' or decision.artifact_policy.runtime_state.value != 'inactive':
        raise ValueError('New staged activation requires accepted-inactive reviewed predecessor')
    with tempfile.TemporaryDirectory(prefix='designated-preapproval-') as temp:
        scratch = Path(temp)
        with tarfile.open(fileobj=io.BytesIO(git(context.repository_root,'archive',binding.reviewed_head_sha))) as archive:
            archive.extractall(scratch,filter='data')
        predecessor = load_science_registry(scratch/'data/science')
        history = []
        for path, approval in approval_entries(predecessor.science_dir):
            if approval.subject_id == DESIGNATED:
                if approval.role.value != 'decision_approver' or approval.subject_digest != science_decision_digest(decision):
                    raise ValueError('Predecessor contains unexpected designated approval authority')
                timestamp, identity = _source_for(approval,context,predecessor)
                history.append(descriptor(path,predecessor.science_dir,approval,timestamp,identity))
    from analysis.science_activation import project_active_registry, same_typed_value
    active_payload = science_decision_payload(project_active_registry(registry,DESIGNATED).decisions[DESIGNATED])
    expected = deepcopy(science_decision_payload(decision)); expected['artifact_policy']['runtime_state']='active'
    if not same_typed_value(active_payload,expected):
        raise ValueError('Staged predecessor/current scientific payload drift beyond activation')
    return ActivationLinkInput(schema_version=1,kind='designated_v2_activation_input',subject_id=DESIGNATED,version=2,
        reviewed_head_sha=binding.reviewed_head_sha,predecessor_path='decisions/'+DESIGNATED+'.yaml',predecessor_mode=mode,
        predecessor_blob=blob,predecessor_bytes_digest=byte_digest(raw_bytes),predecessor_payload=science_decision_payload(decision),
        predecessor_digest=science_decision_digest(decision),historical_assertions=sorted(history,key=lambda h:h.path),
        active_decision_digest=science_decision_digest(project_active_registry(registry,DESIGNATED).decisions[DESIGNATED]),
        implementation_envelope_digest=binding.envelope_digest)


def read_link(registry) -> ActivationLink | None:
    """Strict local provenance classification, without admission authority."""
    from analysis.science_activation import strict_json, same_typed_value
    from analysis.science_artifacts import science_decision_payload, science_decision_digest
    directory = registry.science_dir/LINK_DIR
    paths = sorted(directory.rglob('*')) if directory.exists() else []
    files = [p for p in paths if p.is_file() or p.is_symlink()]
    if not files:
        return None
    if len(files) != 1 or DESIGNATED not in registry.decisions:
        raise ValueError('Only one complete designated activation companion is supported')
    path = files[0]
    if path.is_symlink() or path.stat().st_mode & 0o111:
        raise ValueError('Activation companion must be a non-executable regular file')
    link = ActivationLink.model_validate(strict_json(path.read_text()))
    if path.relative_to(registry.science_dir) != companion_path(link.input.active_decision_digest):
        raise ValueError('Activation companion namespace differs from exact active digest')
    decision = registry.decisions[DESIGNATED]
    active = deepcopy(link.input.predecessor_payload);active['artifact_policy']['runtime_state']='active'
    if (decision.status.value != 'accepted' or decision.artifact_policy.runtime_state.value != 'active'
            or not same_typed_value(science_decision_payload(decision),active)
            or science_decision_digest(decision) != link.input.active_decision_digest):
        raise ValueError('Activation companion does not classify the exact current active decision')
    represented = [*link.input.historical_assertions,link.active_assertion,link.implementation_assertion]
    actual = {p.relative_to(registry.science_dir).as_posix():a for p,a in approval_entries(registry.science_dir) if a.subject_id==DESIGNATED}
    if set(actual) != {a.path for a in represented}:
        raise ValueError('Activation companion is missing, duplicate, orphaned or ambiguous assertion closure')
    for item in represented:
        file = registry.science_dir/item.path
        if (file.is_symlink() or byte_digest(file.read_bytes()) != item.bytes_digest
                or ('100755' if file.stat().st_mode & 0o111 else '100644') != item.mode
                or not same_typed_value(actual[item.path].model_dump(mode='json',exclude_none=True),item.assertion)):
            raise ValueError('Linked assertion original path/bytes/mode/content changed')
    return link


def current_approvals(registry, approvals):
    link = read_link(registry)
    if link is None:
        return list(approvals)
    old = [a.assertion for a in link.input.historical_assertions]
    return [a for a in approvals if a.model_dump(mode='json',exclude_none=True) not in old]


def write_link(science: Path, link_input: ActivationLinkInput, approvals, context) -> Path:
    from analysis.science_artifacts import ReviewRole
    current = next(a for a in approvals if a.subject_id==DESIGNATED and a.role==ReviewRole.DECISION_APPROVER and a.subject_digest==link_input.active_decision_digest)
    implementation = next(a for a in approvals if a.subject_id==DESIGNATED and a.role==ReviewRole.IMPLEMENTATION_REVIEWER)
    source = (context.source_comments or {}).get(str(current.source_ref))
    if not isinstance(source,dict) or source.get('permission') not in {'write','maintain','admin'}:
        raise ValueError('Fresh linkage requires authenticated current composite source transport')
    event=source['comment']; timestamp=event['created_at'];identity=event['id']
    if (event.get('html_url')!=str(current.source_ref) or event.get('user',{}).get('type')!='User'
            or event.get('user',{}).get('login')!=current.reviewer.removeprefix('github:')):
        raise ValueError('Fresh receipt event does not identify its actual authenticated reviewer/source')
    # Full canonical fresh source authentication is done by parser before writing;
    # replay also verifies it, so direct writer entry cannot invent the companion.
    current_path=active_assertion_path(current.model_dump(mode='json',exclude_none=True))
    implementation_path=next(p for p,a in approval_entries(science) if a==implementation)
    receipt=ActivationLink(schema_version=1,kind='designated_v2_activation_receipt',input=link_input,
        active_assertion=descriptor(science/current_path,science,current,timestamp,identity),
        implementation_assertion=descriptor(implementation_path,science,implementation,timestamp,identity))
    path=science/companion_path(link_input.active_decision_digest)
    content=json.dumps(receipt.model_dump(mode='json'),ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if path.exists() and path.read_text()!=content:
        raise ValueError('Activation lineage is immutable and cannot be overwritten')
    path.parent.mkdir(exist_ok=True);path.write_text(content,encoding='utf-8',newline='\n')
    return path


def verify_retained_source_comments(registry, comments, permissions, context) -> None:
    """STOP-only inspection authenticates retained sources without issuing roles.

    Caller must first verify the exact canonical STOP/full-tree transition or
    byte-identical terminal history. Nothing here permits a new assertion.
    """
    from analysis.science_artifacts import load_science_approvals, render_approval_comment_template
    from analysis.science_activation import (implementation_envelope,render_activation_comment,
                                            git,project_active_registry)
    from analysis.evidence_registry import load_science_registry
    import io,tarfile,tempfile
    approvals=load_science_approvals(registry.science_dir)
    link=read_link(registry)
    for event in comments:
        body=str(event.get('body',''))
        if not any(marker in body for marker in ('praxys-science-approval:','praxys-science-activation:','praxys-science-implementation:')):
            continue
        user=event.get('user',{})
        login=user.get('login')
        if user.get('type')!='User' or not isinstance(login,str) or permissions.get(login) not in {'write','maintain','admin'}:
            continue
        retained=[a for a in approvals if str(a.source_ref)==event.get('html_url')]
        if (not retained or any(a.reviewer!='github:'+login or a.reviewed_on!=source_time(event.get('created_at')).date() for a in retained)):
            raise ValueError('Terminal inspection rejects new/swapped approval source or chronology')
        payload=implementation_envelope(body)
        if payload is not None:
            implementation=[a for a in retained if a.role.value=='implementation_reviewer']
            if len(implementation)!=1 or implementation[0].implementation_binding.model_dump(mode='json')!=payload['implementation_binding']:
                raise ValueError('Retained implementation source envelope mismatch')
            binding=implementation[0].implementation_binding
            git(context.repository_root,'merge-base','--is-ancestor',binding.reviewed_head_sha,context.base_sha)
            with tempfile.TemporaryDirectory(prefix='terminal-source-history-') as temp:
                scratch=Path(temp)
                with tarfile.open(fileobj=io.BytesIO(git(context.repository_root,'archive',binding.reviewed_head_sha))) as archive:
                    archive.extractall(scratch,filter='data')
                predecessor=load_science_registry(scratch/'data/science')
                expected=render_activation_comment(predecessor,payload['subject_id'],binding,
                    activation_link_input=link.input if link and payload['subject_id']==DESIGNATED else None)
            if body.strip()!=expected.strip():
                raise ValueError('Retained activation comment changed canonical source coverage')
        else:
            if len(retained)!=1 or retained[0].role.value!='decision_approver':
                raise ValueError('Terminal inspection supports only exact retained standalone decision sources')
            approval=retained[0]
            if link and approval.subject_digest==link.input.predecessor_digest:
                statement=link.input.predecessor_payload['decision_review']['approval_statement']
                matching=next(old for old in link.input.historical_assertions if old.assertion['source_ref']==str(approval.source_ref))
                if event['created_at']!=matching.source_timestamp or event.get('id')!=matching.source_comment_id:
                    raise ValueError('Retained inactive event changed after authenticated linkage')
            else:
                statement=registry.decisions[approval.subject_id].decision_review.approval_statement
            expected=render_approval_comment_template(subject_kind=approval.subject_kind,subject_id=approval.subject_id,
                subject_digest=approval.subject_digest,role=approval.role,approval_statement=statement)
            if body.strip()!=expected.strip():
                raise ValueError('Retained inactive comment canonical source mismatch')
