"""Materialize explicit human science approvals without manual YAML editing."""

from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Mapping, Sequence

import yaml

from analysis.science_yaml import load_science_yaml

from analysis.evidence_registry import (
    ApprovalMode,
    ArtifactRuntimeState,
    RecordStatus,
    ScienceRegistry,
    load_science_registry,
    render_registry_index,
)
from analysis.science_artifacts import (
    ReviewRole,
    ReviewSubjectKind,
    ScienceApproval,
    approval_statement_for_subject,
    evidence_review_digest,
    load_science_approvals,
    render_approval_comment_template,
    required_review_scopes,
    science_decision_digest,
    sync_science_artifacts,
)


_APPROVAL_MARKER_PREFIX = "praxys-science-approval:v1"
_APPROVAL_VISIBLE_MARKER = "Praxys science approval — **APPROVE**"
_APPROVAL_MARKER_RE = re.compile(
    r"<!--\s*praxys-science-approval:v1\s*(\{.*?\})\s*-->",
    re.DOTALL,
)
_LEGACY_EVIDENCE_RE = re.compile(
    r"\AMaintainer evidence review — \*\*Approve Evidence Review\*\* "
    r"for evidence digest `(?P<digest>sha256:[0-9a-f]{64})`\."
)
_LEGACY_DECISION_RE = re.compile(
    r"\AMaintainer decision — \*\*Approve decision sheet as a unit\*\* "
    r"for decision digest `(?P<digest>sha256:[0-9a-f]{64})`\."
)
_AUTHORIZED_PERMISSIONS = {"write", "maintain", "admin"}
_SAFE_SLUG_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def approvals_from_github_comments(
    science_dir: str | Path,
    comments: Sequence[Mapping[str, Any]],
    permissions: Mapping[str, str],
    *,
    activation_context=None,
    stop_context=None,
) -> list[ScienceApproval]:
    """Return digest-bound approvals from authorized human PR comments."""
    registry = load_science_registry(
        science_dir,
        validate_approvals=False,
    )
    from analysis.science_activation import (
        COMPOSITE_MARKER, V2_COMPOSITE_MARKER, composite_approval_payloads, implementation_envelope,
    )
    from analysis.science_artifacts import ImplementationBinding

    source_registry = registry
    implementation_payloads = {}
    historical_payloads = {}
    for comment in comments:
        user = comment.get("user", {})
        if (not isinstance(user, Mapping) or user.get("type") != "User"
                or str(user.get("login", "")).endswith("[bot]")
                or permissions.get(user.get("login"), "").lower() not in _AUTHORIZED_PERMISSIONS):
            continue
        payload = implementation_envelope(str(comment.get("body", "")))
        if payload is None:
            continue
        if activation_context is None:
            raise ValueError("Implementation approval requires authenticated repository context")
        binding = ImplementationBinding.model_validate(payload["implementation_binding"])
        source = str(comment.get("html_url", ""))
        expected_source = f"https://github.com/{binding.repository}/issues/{binding.pull_request}#issuecomment-"
        alternate = f"https://github.com/{binding.repository}/pull/{binding.pull_request}#issuecomment-"
        if not (source.startswith(expected_source) or source.startswith(alternate)):
            raise ValueError("Implementation approval source is not this repository/PR")
        if implementation_payloads:
            raise ValueError("One activation batch may contain exactly one implementation approval")
        registry = activation_context.verify(binding, registry, payload['subject_id'])
        from analysis.science_admission_amendment import DESIGNATED
        if payload['subject_id']==DESIGNATED:
            from analysis.science_activation_link import activation_input
            link=activation_input(source_registry,binding,activation_context)
            if link is not None:
                event=(activation_context.source_comments or {}).get(source)
                if not event or event['comment']!=comment:
                    raise ValueError('Fresh staged comment differs from authenticated transport event')
                historical_payloads={old.assertion['source_ref']:[{key:old.assertion[key] for key in ('subject_kind','subject_id','subject_digest','role')}] for old in link.historical_assertions}
        implementation_payloads[source] = (
            composite_approval_payloads(str(comment["body"]), registry,activation_context=activation_context)
            if any(m in str(comment["body"]) for m in (COMPOSITE_MARKER, V2_COMPOSITE_MARKER)) else [payload]
        )

    approvals: dict[
        tuple[ReviewSubjectKind, str, ReviewRole, str],
        ScienceApproval,
    ] = {}
    ordered_comments = sorted(
        comments,
        key=lambda item: (
            str(item.get("created_at", "")),
            int(item.get("id", 0)),
        ),
    )
    for comment in ordered_comments:
        user = comment.get("user")
        if not isinstance(user, Mapping):
            continue
        login = user.get("login")
        user_type = user.get("type")
        if (
            not isinstance(login, str)
            or user_type != "User"
            or login.endswith("[bot]")
            or permissions.get(login, "").lower()
            not in _AUTHORIZED_PERMISSIONS
        ):
            continue
        body = comment.get("body")
        source_ref = comment.get("html_url")
        created_at = comment.get("created_at")
        if not all(
            isinstance(value, str)
            for value in (body, source_ref, created_at)
        ):
            continue

        if source_ref in historical_payloads and (activation_context.source_comments or {}).get(source_ref,{}).get('comment')!=comment:
            raise ValueError('Retained staged comment differs from exact authenticated prior source')
        payloads = (implementation_payloads[source_ref] if source_ref in implementation_payloads
                    else historical_payloads[source_ref] if source_ref in historical_payloads
                    else _structured_approval_payloads(body, registry))
        if not payloads:
            payloads = _legacy_approval_payloads(body, registry)

        reviewed_on = _github_timestamp_date(created_at)
        for payload in payloads:
            role = ReviewRole(payload["role"])
            approval = ScienceApproval.model_validate({
                "schema_version": 2 if role == ReviewRole.IMPLEMENTATION_REVIEWER else 1,
                "implementation_binding": payload.get("implementation_binding"),
                "subject_kind": payload["subject_kind"],
                "subject_id": payload["subject_id"],
                "subject_digest": payload["subject_digest"],
                "reviewer": f"github:{login}",
                "role": role.value,
                "reviewed_on": reviewed_on.isoformat(),
                "scopes": [
                    scope.value
                    for scope in required_review_scopes(role)
                ],
                "source_ref": source_ref,
            })
            key = (
                approval.subject_kind,
                approval.subject_id,
                approval.role,
                approval.reviewer,
            )
            from analysis.science_admission_amendment import DESIGNATED
            if approval.subject_id==DESIGNATED:
                key=(*key,approval.subject_digest)
                if key in approvals and approvals[key]!=approval:
                    raise ValueError('Conflicting same-stage designated source assertions')
            approvals.setdefault(key, approval)

    from analysis.science_admission_amendment import DESIGNATED, require_authenticated_amendment_base
    if any(a.subject_id == DESIGNATED for a in approvals.values()):
        require_authenticated_amendment_base(source_registry, activation_context or stop_context)

    return sorted(
        approvals.values(),
        key=lambda item: (
            item.subject_id,
            item.role.value,
            item.reviewer,
        ),
    )


def materialize_science_approvals(
    science_dir: str | Path,
    approvals: Sequence[ScienceApproval],
    *,
    activation_context=None,
    stop_context=None,
) -> list[Path]:
    """Atomically record approvals and accepted lifecycle transitions."""
    unresolved_root = Path(science_dir)
    if unresolved_root.is_symlink() or unresolved_root.parent.is_symlink():
        raise ValueError("Science approval directory cannot be a symlink")
    root = unresolved_root.resolve()
    if not root.is_dir():
        raise ValueError(f"Science directory does not exist: {root}")
    if not approvals:
        return []
    from analysis.science_admission_amendment import DESIGNATED, require_authenticated_amendment_base
    designated = any(a.subject_id == DESIGNATED for a in approvals)
    if designated:
        require_authenticated_amendment_base(load_science_registry(root), activation_context or stop_context)
        if any(a.subject_id != DESIGNATED for a in approvals):
            raise ValueError('Designated batch issues only new V2 assertions; shared evidence cannot be renewed')
    implementation = [a for a in approvals if a.role == ReviewRole.IMPLEMENTATION_REVIEWER]
    link_input = None
    if implementation and designated:
        from analysis.science_activation_link import activation_input,read_link
        link_input=activation_input(load_science_registry(root),implementation[0].implementation_binding,activation_context)
        from analysis.science_activation import composite_approval_payloads
        event=(activation_context.source_comments or {}).get(str(implementation[0].source_ref))
        if link_input is not None:
            if not event or event.get('permission') not in _AUTHORIZED_PERMISSIONS:
                raise ValueError('Staged materialization requires authenticated complete fresh source')
            composite_approval_payloads(event['comment']['body'],load_science_registry(root),activation_context=activation_context)
            current=next((a for a in approvals if a.role==ReviewRole.DECISION_APPROVER and a.subject_digest==link_input.active_decision_digest),None)
            source_event=event['comment']
            if (current is None or current.reviewer!=implementation[0].reviewer
                    or str(current.source_ref)!=str(implementation[0].source_ref)
                    or source_event.get('html_url')!=str(current.source_ref)
                    or source_event.get('user',{}).get('type')!='User'
                    or source_event.get('user',{}).get('login')!=current.reviewer.removeprefix('github:')
                    or _github_timestamp_date(source_event['created_at'])!=current.reviewed_on
                    or current.reviewed_on!=implementation[0].reviewed_on):
                raise ValueError('Staged activation requires complete fresh exact decision and implementation assertions')
    if implementation:
        if activation_context is None or len(implementation) != 1:
            raise ValueError("Implementation approval requires one authenticated activation context")
        binding = implementation[0].implementation_binding
        activation_context.verify(binding, load_science_registry(root), implementation[0].subject_id)
        # Identical retries need no writes; all other input must be the frozen head.
        if all(a in load_science_approvals(root) for a in approvals):
            activation_context.verify_replay(binding, approvals, root.parent.parent)
            return []
        activation_context.require_reviewed_tree(binding, root.parent.parent)
    _reject_symlinks(root)
    _require_unique_approval_batch(approvals)
    _verify_generated_state(root)
    root_snapshot = _snapshot_tree(root)
    root_modes = {relative: (root / relative).stat().st_mode for relative in root_snapshot}

    with tempfile.TemporaryDirectory(prefix="praxys-science-approval-") as tmp:
        staged_root = Path(tmp) / "science"
        shutil.copytree(root, staged_root, symlinks=True)
        candidate_paths: set[Path] = set()

        ordered = sorted(approvals, key=lambda a: {
            ReviewRole.EVIDENCE_REVIEWER: 0, ReviewRole.DECISION_APPROVER: 1,
            ReviewRole.IMPLEMENTATION_REVIEWER: 2,
        }[a.role])
        for approval in ordered:
            if designated and approval in load_science_approvals(staged_root):
                continue
            record_path = _transition_subject(staged_root, approval)
            candidate_paths.add(record_path.relative_to(staged_root))
            approval_path = (_write_approval_artifact(staged_root,approval,active_link=link_input)
                             if link_input is not None else _write_approval_artifact(staged_root,approval))
            candidate_paths.add(approval_path.relative_to(staged_root))

        if link_input is not None:
            from analysis.science_activation_link import write_link
            link_path=write_link(staged_root,link_input,approvals,activation_context)
            candidate_paths.add(link_path.relative_to(staged_root))
        registry = load_science_registry(staged_root)
        generated_paths = sync_science_artifacts(registry, check=False)
        candidate_paths.update(generated_paths)

        registry_index = staged_root / "REGISTRY.md"
        registry_index.write_text(
            render_registry_index(registry),
            encoding="utf-8",
            newline="\n",
        )
        candidate_paths.add(Path("REGISTRY.md"))

        validated = load_science_registry(staged_root)
        if sync_science_artifacts(validated, check=True):
            raise ValueError("generated science artifacts remain stale")
        expected_index = render_registry_index(validated)
        if registry_index.read_text(encoding="utf-8") != expected_index:
            raise ValueError("generated science registry index remains stale")

        changed = [
            relative
            for relative in sorted(
                candidate_paths,
                key=lambda item: item.as_posix(),
            )
            if root_snapshot.get(relative)
            != _path_content(staged_root / relative)
        ]
        for relative in changed:
            original = root_snapshot.get(relative)
            if _path_content(root / relative) != original:
                raise ValueError(
                    f"Science file changed during approval materialization: "
                    f"{relative}"
                )
        if designated:
            require_authenticated_amendment_base(validated, activation_context or stop_context)
            admission_context = activation_context or stop_context
            if admission_context.recheck is not None:
                admission_context.recheck()
        if implementation:
            activation_context.require_reviewed_tree(binding, root.parent.parent)
            if activation_context.recheck is not None:
                activation_context.recheck()
        written = []
        try:
            for relative in changed:
                written.append(relative)
                _atomic_copy(staged_root / relative, root / relative)
        except Exception:
            # Roll back the completed part of this ledger batch; never leave a
            # partially active record after a recoverable publication failure.
            for relative in reversed(written):
                original = root_snapshot.get(relative)
                if original is None:
                    (root / relative).unlink(missing_ok=True)
                else:
                    recovery = Path(tmp) / 'recovery'
                    recovery.write_bytes(original)
                    recovery.chmod(root_modes[relative])
                    _atomic_copy(recovery, root / relative)
            raise

    load_science_registry(root)
    return changed


def verify_science_approval_changes(
    base_science_dir: str | Path,
    head_science_dir: str | Path,
    comments: Sequence[Mapping[str, Any]],
    permissions: Mapping[str, str],
    *,
    activation_context=None,
    stop_context=None,
) -> None:
    """Require every new approval to match an authenticated PR comment."""
    base_root = Path(base_science_dir)
    head_root = Path(head_science_dir)
    _reject_symlinks(base_root)
    _reject_symlinks(head_root)
    base_registry = load_science_registry(base_root)
    head_registry = load_science_registry(head_root)
    from analysis.science_activation import verify_governed_maintenance
    verify_governed_maintenance(base_registry, head_registry, stop_context=stop_context)

    from analysis.science_implementation_stop import load_implementation_stops, verify_stop_changes
    verified_stops=[]
    if load_implementation_stops(base_root) or load_implementation_stops(head_root):
        if stop_context is None:
            raise ValueError("STOP source/history verification requires authenticated context")
        verified_stops=verify_stop_changes(base_registry, head_registry,
                            repository_root=stop_context.repository_root,
                            base_sha=stop_context.base_sha,
                            authenticated=list(stop_context.authenticated_stops))

    from analysis.science_admission_amendment import DESIGNATED,validate_local_amendment
    from analysis.science_activation import directory_tree,git_tree,git
    stopped_v2=any(stop.subject_id==DESIGNATED for stop in load_implementation_stops(head_root))
    if stopped_v2:
        if stop_context is None:
            raise ValueError('Stopped V2 requires fully verified exact STOP/history context')
        expected_tree=git_tree(stop_context.repository_root,stop_context.base_sha)
        terminal_only=any(stop.subject_id==DESIGNATED for stop in verified_stops)
        unchanged_history=(not verified_stops and directory_tree(head_root.parent.parent,expected_tree,repository=stop_context.repository_root)==expected_tree)
        if not terminal_only and not unchanged_history:
            raise ValueError('No generic stopped-V2 maintenance, approval or revival is supported')
        if git(stop_context.repository_root,'rev-parse','HEAD').decode().strip()!=stop_context.head_sha:
            raise ValueError('Verified terminal history source head changed')
        from analysis.science_activation_link import verify_retained_source_comments
        verify_retained_source_comments(base_registry,comments,permissions,stop_context)
        from analysis.science_admission_amendment import BASELINE
        baseline_stop=next(s for s in load_implementation_stops(head_root) if s.subject_id==BASELINE)
        stop_context.require_denial(baseline_stop)
        validate_local_amendment(head_registry)
        _verify_generated_state(head_root,registry=head_registry)
        if stop_context.recheck is not None:
            stop_context.recheck()
        return
    base_approvals = load_science_approvals(base_root)
    head_approvals = load_science_approvals(head_root)
    verified = approvals_from_github_comments(
        head_root,
        comments,
        permissions,
        activation_context=activation_context,
        stop_context=stop_context,
    )

    for approval in base_approvals:
        if approval not in head_approvals:
            raise ValueError(
                f"Existing science approval was removed or modified: "
                f"{approval.subject_id} {approval.role.value}"
            )
    for approval in head_approvals:
        if approval in base_approvals:
            continue
        if approval not in verified:
            raise ValueError(
                f"Science approval for {approval.subject_id} is not backed by "
                "an authenticated exact PR approval comment"
            )

    _verify_lifecycle_transitions(
        base_registry,
        head_registry,
        head_approvals,
        admission_context=activation_context or stop_context,
    )
    _verify_generated_state(head_root, registry=head_registry)
    if stop_context is not None and stop_context.recheck is not None:
        stop_context.recheck()
    implementation = [a for a in head_approvals if a not in base_approvals
                      and a.role == ReviewRole.IMPLEMENTATION_REVIEWER]
    for approval in implementation:
        if activation_context is None:
            raise ValueError("Implementation replay requires authenticated repository context")
        activation_context.verify_replay(approval.implementation_binding, verified, head_root.parent.parent)


def _structured_approval_payloads(
    body: str,
    registry: ScienceRegistry,
) -> list[dict[str, str]]:
    matches = list(_APPROVAL_MARKER_RE.finditer(body))
    if _APPROVAL_MARKER_PREFIX in body and not matches:
        raise ValueError("science approval marker is malformed")
    if len(matches) > 1:
        raise ValueError("one science approval comment may approve one subject")
    if matches and _APPROVAL_VISIBLE_MARKER not in body:
        raise ValueError(
            "science approval marker requires an explicit visible approval"
        )
    payloads: list[dict[str, str]] = []
    required = {
        "subject_kind",
        "subject_id",
        "subject_digest",
        "role",
    }
    for match in matches:
        raw = json.loads(match.group(1))
        if not isinstance(raw, dict) or set(raw) != required:
            raise ValueError(
                "science approval marker must contain exactly "
                f"{sorted(required)}"
            )
        if not all(isinstance(raw[key], str) for key in required):
            raise ValueError("science approval marker values must be strings")
        subject_kind = ReviewSubjectKind(raw["subject_kind"])
        role = ReviewRole(raw["role"])
        if role == ReviewRole.IMPLEMENTATION_REVIEWER:
            raise ValueError(
                "Implementation approval is not automated until it binds "
                "the exact reviewed code"
            )
        expected_digest = _current_subject_digest(
            registry,
            subject_kind,
            raw["subject_id"],
        )
        if raw["subject_digest"] != expected_digest:
            continue
        statement = approval_statement_for_subject(
            registry,
            subject_kind=subject_kind,
            subject_id=raw["subject_id"],
            role=role,
        )
        expected_body = render_approval_comment_template(
            subject_kind=subject_kind,
            subject_id=raw["subject_id"],
            subject_digest=raw["subject_digest"],
            role=role,
            approval_statement=statement,
        )
        if body.strip() != expected_body.strip():
            raise ValueError(
                "science approval comment must match the canonical statement "
                "and visible role/subject/digest"
            )
        payloads.append(raw)
    return payloads


def _legacy_approval_payloads(
    body: str,
    registry: ScienceRegistry,
) -> list[dict[str, str]]:
    payloads: list[dict[str, str]] = []
    evidence_match = _LEGACY_EVIDENCE_RE.search(body)
    if evidence_match:
        digest = evidence_match.group("digest")
        expected_body = (
            "Maintainer evidence review — **Approve Evidence Review** for "
            f"evidence digest `{digest}`.\n\n"
            "The reviewed evidence claims, verification limits, "
            "uncertainties, and non-inferences are accepted for this "
            "proposal. This approval does not approve implementation or "
            "runtime activation."
        )
        if body.strip() != expected_body:
            return payloads
        subject_id = _unique_subject_for_digest(
            {
                review.id: evidence_review_digest(review)
                for review in registry.evidence_reviews.values()
                if review.approval_mode == ApprovalMode.ARTIFACT
            },
            digest,
        )
        if subject_id is not None:
            payloads.append({
                "subject_kind": ReviewSubjectKind.EVIDENCE_REVIEW.value,
                "subject_id": subject_id,
                "subject_digest": digest,
                "role": ReviewRole.EVIDENCE_REVIEWER.value,
            })

    decision_match = _LEGACY_DECISION_RE.search(body)
    if decision_match:
        digest = decision_match.group("digest")
        expected_body = (
            "Maintainer decision — **Approve decision sheet as a unit** for "
            f"decision digest `{digest}`.\n\n"
            "This approval covers the four proposed decisions "
            "(`supported-scope`, `evidence-use`, `hard-boundaries`, and "
            "`mostly-low-structure`) and agrees to the four explicit "
            "deferrals (`defer-baseline-history`, `defer-dose-taper`, "
            "`defer-fueling`, and `defer-pilot-activation`). The contract "
            "remains inactive. This comment does not approve implementation, "
            "runtime activation, or fill any deferred value."
        )
        if body.strip() != expected_body:
            return payloads
        subject_id = _unique_subject_for_digest(
            {
                decision.id: science_decision_digest(decision)
                for decision in registry.decisions.values()
                if decision.approval_mode == ApprovalMode.ARTIFACT
            },
            digest,
        )
        if subject_id is not None:
            payloads.append({
                "subject_kind": ReviewSubjectKind.SCIENCE_DECISION.value,
                "subject_id": subject_id,
                "subject_digest": digest,
                "role": ReviewRole.DECISION_APPROVER.value,
            })
    return payloads


def _unique_subject_for_digest(
    subject_digests: Mapping[str, str],
    digest: str,
) -> str | None:
    matches = [
        subject_id
        for subject_id, candidate in subject_digests.items()
        if candidate == digest
    ]
    if len(matches) > 1:
        raise ValueError(
            f"science approval digest {digest} matches multiple subjects"
        )
    return matches[0] if matches else None


def _current_subject_digest(
    registry: ScienceRegistry,
    subject_kind: ReviewSubjectKind,
    subject_id: str,
) -> str:
    if subject_kind == ReviewSubjectKind.EVIDENCE_REVIEW:
        if subject_id not in registry.evidence_reviews:
            raise ValueError(
                f"Unknown Evidence Review approval subject: {subject_id}"
            )
        return evidence_review_digest(registry.evidence_reviews[subject_id])
    if subject_kind == ReviewSubjectKind.SCIENCE_DECISION:
        if subject_id not in registry.decisions:
            raise ValueError(
                f"Unknown science decision approval subject: {subject_id}"
            )
        return science_decision_digest(registry.decisions[subject_id])
    raise ValueError(
        "Implementation approval is not automated until code binding exists"
    )


def _github_timestamp_date(value: str) -> date:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized).date()


def _require_unique_approval_batch(
    approvals: Sequence[ScienceApproval],
) -> None:
    keys = [
        (
            approval.subject_kind,
            approval.subject_id,
            approval.role,
            approval.reviewer,
        )
        for approval in approvals
    ]
    from analysis.science_admission_amendment import DESIGNATED
    keys=[(*key,a.subject_digest) if a.subject_id==DESIGNATED else key for key,a in zip(keys,approvals)]
    if len(keys) != len(set(keys)):
        raise ValueError("approval batch entries must be unique")


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink() or root.parent.is_symlink():
        raise ValueError("Science approval directory cannot be a symlink")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(
                f"Science approval materialization rejects symlink: {path}"
            )


def _transition_subject(
    science_dir: Path,
    approval: ScienceApproval,
) -> Path:
    from analysis.science_admission_amendment import DESIGNATED, prevalidate_amendment_record
    designated = approval.subject_id == DESIGNATED
    if approval.subject_kind == ReviewSubjectKind.EVIDENCE_REVIEW:
        record_path = _subject_path(
            science_dir / "evidence",
            approval.subject_id,
        )
    else:
        record_path = _subject_path(
            science_dir / "decisions",
            approval.subject_id,
        )

    raw = _load_mapping(record_path)
    if designated:
        # Public caller authenticates the complete input and staged output.
        prevalidate_amendment_record(raw)
    if raw.get("approval_mode") != ApprovalMode.ARTIFACT.value:
        raise ValueError(
            f"Approval subject {approval.subject_id} is not artifact-mode"
        )
    status = raw.get("status")
    text = record_path.read_text(encoding="utf-8")
    if (
        status == RecordStatus.DRAFT.value
        and not designated
        and (
            raw.get("version", 1) != 1
            or bool(raw.get("supersedes"))
        )
    ):
        raise ValueError(
            "Successor acceptance requires a coordinated reciprocal "
            "supersession lifecycle patch; the simple approval ledger will "
            "not infer predecessor transitions"
        )

    if approval.role == ReviewRole.EVIDENCE_REVIEWER:
        if status == RecordStatus.DRAFT.value:
            text = _replace_top_level_scalar(
                text,
                "status",
                RecordStatus.ACCEPTED.value,
            )
            text = _replace_top_level_scalar(
                text,
                "reviewed_on",
                approval.reviewed_on.isoformat(),
            )
        elif status not in {
            RecordStatus.ACCEPTED.value,
            RecordStatus.SUPERSEDED.value,
        }:
            raise ValueError(
                f"Evidence review {approval.subject_id} cannot be accepted "
                f"from status {status}"
            )
    elif approval.role == ReviewRole.DECISION_APPROVER:
        if status == RecordStatus.DRAFT.value:
            text = _replace_top_level_scalar(
                text,
                "status",
                RecordStatus.ACCEPTED.value,
            )
        elif status not in {
            RecordStatus.ACCEPTED.value,
            RecordStatus.SUPERSEDED.value,
        }:
            raise ValueError(
                f"Science decision {approval.subject_id} cannot be accepted "
                f"from status {status}"
            )
    elif approval.role == ReviewRole.IMPLEMENTATION_REVIEWER:
        if status != RecordStatus.ACCEPTED.value or approval.implementation_binding is None:
            raise ValueError("Implementation activation requires accepted code-bound decision")
        pattern = re.compile(r"(?m)^(  runtime_state:)[^\n]*$")
        if len(pattern.findall(text)) != 1:
            raise ValueError("Expected exactly one explicit artifact runtime state")
        text = pattern.sub(r"\1 active", text)
    else:
        raise ValueError("Unknown science approval role")

    record_path.write_text(text, encoding="utf-8", newline="\n")
    return record_path


def _subject_path(root: Path, subject_id: str) -> Path:
    matches = sorted(
        [
            *root.rglob(f"{subject_id}.yaml"),
            *root.rglob(f"{subject_id}.yml"),
        ],
        key=lambda item: item.as_posix(),
    )
    if len(matches) != 1:
        raise ValueError(
            f"Expected one record for {subject_id}, found {len(matches)}"
        )
    return matches[0]


def _load_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        raw = load_science_yaml(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Science record must be a mapping: {path}")
    return raw


def _replace_top_level_scalar(
    text: str,
    key: str,
    value: str,
) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}:[^\n]*$")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            f"Expected one top-level {key} field, found {len(matches)}"
        )
    return pattern.sub(f"{key}: {value}", text, count=1)


def _write_approval_artifact(
    science_dir: Path,
    approval: ScienceApproval,
    *, active_link=None,
) -> Path:
    reviewer_slug = _SAFE_SLUG_RE.sub("-", approval.reviewer).strip("-")
    filename = (
        f"{approval.subject_id}--{approval.role.value}--"
        f"{reviewer_slug}.yaml"
    )
    path = science_dir / 'approvals' / filename
    if active_link is not None and approval.role==ReviewRole.DECISION_APPROVER and approval.subject_digest==active_link.active_decision_digest:
        from analysis.science_activation_link import active_assertion_path
        path=science_dir/active_assertion_path(approval.model_dump(mode='json',exclude_none=True))
    payload = approval.model_dump(mode="json", exclude_none=True)
    content = yaml.safe_dump(payload, sort_keys=False)
    if path.exists():
        existing = ScienceApproval.model_validate(_load_mapping(path))
        if existing == approval:
            return path
        raise ValueError(f"Conflicting science approval artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def _path_content(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _snapshot_tree(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _verify_generated_state(
    science_dir: Path,
    *,
    registry: ScienceRegistry | None = None,
) -> None:
    current = registry or load_science_registry(science_dir)
    stale = sync_science_artifacts(current, check=True)
    if stale:
        raise ValueError(
            "Science approval requires trusted generated packets/contracts; "
            f"stale paths: {[path.as_posix() for path in stale]}"
        )
    registry_path = science_dir / "REGISTRY.md"
    expected = render_registry_index(current)
    actual = (
        registry_path.read_text(encoding="utf-8")
        if registry_path.exists()
        else ""
    )
    if actual != expected:
        raise ValueError("Science approval requires a current REGISTRY.md")


def _verify_lifecycle_transitions(
    base_registry: ScienceRegistry,
    head_registry: ScienceRegistry,
    head_approvals: Sequence[ScienceApproval],
    *, admission_context=None,
) -> None:
    from analysis.science_admission_amendment import DESIGNATED, require_authenticated_amendment_base
    from analysis.science_activation_link import current_approvals
    head_approvals=current_approvals(head_registry,head_approvals)
    if DESIGNATED in head_registry.decisions:
        require_authenticated_amendment_base(head_registry, admission_context)
        designated = head_registry.decisions[DESIGNATED]
        if designated.status == RecordStatus.ACCEPTED and not _has_exact_role_approval(
                head_approvals, ReviewSubjectKind.SCIENCE_DECISION, DESIGNATED, ReviewRole.DECISION_APPROVER):
            raise ValueError('Designated acceptance requires exact new decision approval')
    for review_id, head_review in head_registry.evidence_reviews.items():
        base_review = base_registry.evidence_reviews.get(review_id)
        if (
            base_review is not None
            and base_review.status == RecordStatus.DRAFT
            and head_review.status == RecordStatus.ACCEPTED
            and not _has_exact_role_approval(
                head_approvals,
                ReviewSubjectKind.EVIDENCE_REVIEW,
                review_id,
                ReviewRole.EVIDENCE_REVIEWER,
            )
        ):
            raise ValueError(
                f"Evidence Review {review_id} became accepted without an "
                "evidence_reviewer approval"
            )
    for decision_id, head_decision in head_registry.decisions.items():
        base_decision = base_registry.decisions.get(decision_id)
        if (
            base_decision is not None
            and base_decision.status == RecordStatus.DRAFT
            and head_decision.status == RecordStatus.ACCEPTED
            and not _has_exact_role_approval(
                head_approvals,
                ReviewSubjectKind.SCIENCE_DECISION,
                decision_id,
                ReviewRole.DECISION_APPROVER,
            )
        ):
            raise ValueError(
                f"Science decision {decision_id} became accepted without a "
                "decision_approver approval"
            )
        if (
            base_decision is not None
            and base_decision.artifact_policy is not None
            and head_decision.artifact_policy is not None
            and base_decision.artifact_policy.runtime_state
            != ArtifactRuntimeState.ACTIVE
            and head_decision.artifact_policy.runtime_state
            == ArtifactRuntimeState.ACTIVE
        ):
            if not _has_exact_role_approval(
                head_approvals, ReviewSubjectKind.IMPLEMENTATION_CONTRACT,
                decision_id, ReviewRole.IMPLEMENTATION_REVIEWER,
            ):
                raise ValueError("Runtime activation requires code-bound implementation approval")


def _has_exact_role_approval(
    approvals: Sequence[ScienceApproval],
    subject_kind: ReviewSubjectKind,
    subject_id: str,
    role: ReviewRole,
) -> bool:
    return any(
        approval.subject_kind == subject_kind
        and approval.subject_id == subject_id
        and approval.role == role
        for approval in approvals
    )


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        dir=target.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source.read_bytes())
        os.chmod(temp_name, source.stat().st_mode)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
