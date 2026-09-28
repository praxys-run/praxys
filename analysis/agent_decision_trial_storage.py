"""Atomic Azure Blob storage for a protected decision-card cohort broker."""

from __future__ import annotations

from azure.core import MatchConditions
from azure.core.exceptions import ResourceModifiedError, ResourceNotFoundError
from azure.storage.blob import BlobClient, ContentSettings
from pydantic import ValidationError

from analysis.agent_decision_trial import (
    CohortState,
    TrialPolicy,
    TrialUnavailable,
    _check_state,
)


_MAX_STATE_BYTES = 1024 * 1024


def _check_monotonic(previous: CohortState, updated: CohortState) -> None:
    if previous.stopped and not updated.stopped:
        raise TrialUnavailable("a stopped cohort cannot resume")
    if previous.checkpoint_review_digest is not None and (
        previous.checkpoint_review_digest != updated.checkpoint_review_digest
    ):
        raise TrialUnavailable("a checkpoint review cannot be changed")
    if not previous.assignments.keys() <= updated.assignments.keys():
        raise TrialUnavailable("an assignment cannot be removed")
    if len(updated.assignments) > len(previous.assignments) + 1:
        raise TrialUnavailable("only one task may be admitted at a time")
    added_tasks = updated.assignments.keys() - previous.assignments.keys()
    if added_tasks and (previous.stopped or updated.stopped):
        raise TrialUnavailable("stopping cannot admit tasks")
    if previous.checkpoint_review_digest != updated.checkpoint_review_digest and (
        previous.assignments != updated.assignments or previous.stopped != updated.stopped
    ):
        raise TrialUnavailable("checkpoint review must be separate from other updates")
    if previous.stopped != updated.stopped and previous.assignments != updated.assignments:
        raise TrialUnavailable("stopping cannot include other updates")
    for task_key, admission in previous.assignments.items():
        replacement = updated.assignments[task_key]
        if admission.model_copy(update={"events": replacement.events}) != replacement:
            raise TrialUnavailable("an assignment cannot be changed")
        if admission.events != replacement.events[:len(admission.events)]:
            raise TrialUnavailable("outcome history cannot be changed")


class AzureBlobCohortStore:
    """Read and replace a single pre-provisioned private Blob with ETag CAS."""

    def __init__(self, blob: BlobClient, policy: TrialPolicy) -> None:
        self._blob = blob
        self._policy = policy

    def read(self) -> tuple[str, CohortState]:
        try:
            download = self._blob.download_blob(
                offset=0, length=_MAX_STATE_BYTES + 1, max_concurrency=1
            )
            data = download.readall()
        except ResourceNotFoundError as error:
            raise TrialUnavailable("the cohort store has not been provisioned") from error
        if len(data) > _MAX_STATE_BYTES:
            raise TrialUnavailable("the cohort record exceeds its size limit")
        revision = download.properties.etag
        if not revision:
            raise TrialUnavailable("the cohort read has no revision")
        try:
            state = CohortState.model_validate_json(data)
            _check_state(self._policy, state)
        except (ValidationError, ValueError) as error:
            raise TrialUnavailable("the cohort record is invalid") from error
        return revision, state

    def compare_and_swap(self, revision: str, state: CohortState) -> bool:
        if not revision:
            raise TrialUnavailable("a cohort write requires a revision")
        current_revision, previous = self.read()
        if current_revision != revision:
            return False
        try:
            serialized = state.model_dump_json().encode("utf-8")
            updated = CohortState.model_validate_json(serialized)
            _check_state(self._policy, updated)
        except (ValidationError, ValueError) as error:
            raise TrialUnavailable("the cohort update is invalid") from error
        _check_monotonic(previous, updated)
        if (
            len(updated.assignments) > len(previous.assignments)
            and self._policy.status != "active"
        ):
            raise TrialUnavailable("a disabled policy cannot admit tasks")
        if len(serialized) > _MAX_STATE_BYTES:
            raise TrialUnavailable("the cohort update exceeds its size limit")
        try:
            self._blob.upload_blob(
                serialized,
                overwrite=True,
                etag=revision,
                match_condition=MatchConditions.IfNotModified,
                content_settings=ContentSettings(content_type="application/json"),
                max_concurrency=1,
            )
        except ResourceModifiedError as error:
            raise TrialUnavailable("cohort write outcome is ambiguous; candidate withheld") from error
        return True
