"""Focused tests for the experimental Garmin managed-plan adapter."""
from __future__ import annotations

import contextlib
from copy import deepcopy
from typing import Any, Mapping

import pytest
import requests
from garminconnect.exceptions import (
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from api.plan_delivery.base import (
    ProviderAuthenticationError,
    ProviderAuthenticationRequiredError,
    ProviderMutationHooks,
    ProviderOutcomeUnknownError,
    ProviderRateLimitError,
    ProviderRejectedError,
    ProviderRemovalError,
    ProviderRemovalOutcomeUnknownError,
    ProviderRequestError,
    ProviderTransientError,
)
from api.plan_delivery.garmin import GarminPlanDeliveryAdapter

PROFILE_ACCOUNT_ID = "international:stable-profile"
CREDENTIAL_GENERATION = "connection-id:generation"


def _garmin_error(status_code: int) -> GarminConnectConnectionError:
    return GarminConnectConnectionError(
        f"API call client error ({status_code}): API Error {status_code}"
    )


def _requests_error(status_code: int) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    return requests.HTTPError(
        f"HTTP {status_code}",
        response=response,
    )


class FakeGarmin:
    """In-memory Garmin template library and schedule calendar."""

    def __init__(self) -> None:
        self.templates: dict[str, dict[str, Any]] = {}
        self.schedules: dict[str, dict[str, str]] = {}
        self.upload_calls = 0
        self.schedule_calls = 0
        self.unschedule_calls: list[str] = []
        self.upload_response: object | None = None
        self.schedule_response: object | None = None
        self.schedule_date_override: str | None = None
        self.schedule_read_error: Exception | None = None
        self.mutate_uploaded_template = False
        self.upload_error_after_effect: Exception | None = None
        self.schedule_error_after_effect: Exception | None = None
        self._next_template_id = 101
        self._next_schedule_id = 201

    def get_workouts(self, *, start: int, limit: int) -> list[dict[str, Any]]:
        rows = [
            {
                "workoutId": int(template_id),
                "workoutName": payload.get("workoutName"),
                "description": payload.get("description"),
            }
            for template_id, payload in sorted(self.templates.items())
        ]
        return rows[start:start + limit]

    def get_workout_by_id(self, template_id: object) -> dict[str, Any]:
        normalized = str(template_id)
        if normalized not in self.templates:
            raise _garmin_error(404)
        return deepcopy(self.templates[normalized])

    def upload_workout(
        self,
        payload: Mapping[str, Any],
    ) -> object:
        self.upload_calls += 1
        template_id = str(self._next_template_id)
        self._next_template_id += 1
        self.templates[template_id] = deepcopy(dict(payload))
        if self.mutate_uploaded_template:
            self.templates[template_id]["estimatedDurationInSecs"] = 1
        if self.upload_error_after_effect is not None:
            raise self.upload_error_after_effect
        if self.upload_response is not None:
            return self.upload_response
        return {"workoutId": int(template_id)}

    def get_scheduled_workouts(
        self,
        year: int,
        month: int,
    ) -> dict[str, list[dict[str, Any]]]:
        items: list[dict[str, Any]] = []
        for schedule_id, schedule in sorted(self.schedules.items()):
            schedule_date = schedule["date"]
            if (
                int(schedule_date[:4]) != year
                or int(schedule_date[5:7]) != month
            ):
                continue
            template = self.templates[schedule["template_id"]]
            items.append({
                "id": int(schedule_id),
                "workoutId": int(schedule["template_id"]),
                "itemType": "workout",
                "date": schedule_date,
                "title": template["workoutName"],
                "description": template.get("description"),
                "sportTypeKey": "running",
                "duration": template["estimatedDurationInSecs"],
            })
        return {"calendarItems": items}

    def schedule_workout(
        self,
        template_id: object,
        schedule_date: str,
    ) -> object:
        self.schedule_calls += 1
        normalized_template_id = str(template_id)
        schedule_id = str(self._next_schedule_id)
        self._next_schedule_id += 1
        stored_date = self.schedule_date_override or schedule_date
        self.schedules[schedule_id] = {
            "template_id": normalized_template_id,
            "date": stored_date,
        }
        if self.schedule_error_after_effect is not None:
            raise self.schedule_error_after_effect
        if self.schedule_response is not None:
            return self.schedule_response
        return {
            "workoutScheduleId": int(schedule_id),
            "date": stored_date,
        }

    def get_scheduled_workout_by_id(
        self,
        external_id: object,
    ) -> dict[str, Any]:
        if self.schedule_read_error is not None:
            raise self.schedule_read_error
        normalized = str(external_id)
        schedule = self.schedules.get(normalized)
        if schedule is None:
            raise _garmin_error(404)
        return {
            "workoutScheduleId": int(normalized),
            "workoutId": int(schedule["template_id"]),
            "date": schedule["date"],
        }

    def unschedule_workout(self, external_id: object) -> None:
        normalized = str(external_id)
        self.unschedule_calls.append(normalized)
        if normalized not in self.schedules:
            raise _garmin_error(404)
        del self.schedules[normalized]


@pytest.fixture(autouse=True)
def no_garmin_test_pacing(monkeypatch):
    """Keep unit tests deterministic while production writes remain paced."""
    monkeypatch.setattr(
        GarminPlanDeliveryAdapter,
        "_pace_mutation",
        staticmethod(lambda: None),
    )
    monkeypatch.setattr(
        "api.routes.sync._garmin_tokenstore_lease",
        lambda user_id: contextlib.nullcontext(),
    )


def _adapter(client: FakeGarmin) -> GarminPlanDeliveryAdapter:
    adapter = GarminPlanDeliveryAdapter(
        {"email": "runner@example.test", "password": "secret"},
        user_id="garmin-adapter-user",
        source_options={"garmin_region": "international"},
        credential_generation=CREDENTIAL_GENERATION,
    )
    adapter._client = client
    adapter._provider_account_id = "international:stable-account"
    adapter._profile_account_id = PROFILE_ACCOUNT_ID
    return adapter


def _workout(**updates: object) -> dict[str, object]:
    workout: dict[str, object] = {
        "canonical_id": "5a334fb4-748e-4cb2-a73b-aa10f830b15a",
        "date": "2026-08-05",
        "workout_type": "easy",
        "planned_duration_min": 45,
        "planned_distance_km": 8,
        "workout_description": "Aerobic run",
    }
    workout.update(updates)
    return workout


def _recording_hooks(
    initial: Mapping[str, Any] | None = None,
) -> tuple[
    dict[str, Any],
    list[tuple[dict[str, Any], str | None]],
    list[str],
    ProviderMutationHooks,
]:
    references = dict(initial or {})
    checkpoints: list[tuple[dict[str, Any], str | None]] = []
    mutations: list[str] = []

    def checkpoint(
        update: Mapping[str, Any],
        external_id: str | None,
    ) -> None:
        references.clear()
        references.update(deepcopy(dict(update)))
        checkpoints.append((deepcopy(references), external_id))

    hooks = ProviderMutationHooks(
        provider_references=references,
        before_mutation=lambda: mutations.append("before"),
        checkpoint=checkpoint,
    )
    return references, checkpoints, mutations, hooks


@pytest.mark.parametrize(
    "credential_region,configured_region,expected_is_cn",
    [
        (False, "international", False),
        (True, "cn", True),
    ],
)
def test_adapter_uses_connection_configured_region(
    credential_region: bool,
    configured_region: str,
    expected_is_cn: bool,
) -> None:
    adapter = GarminPlanDeliveryAdapter(
        {
            "email": "runner@example.test",
            "password": "secret",
            "is_cn": credential_region,
        },
        user_id="garmin-adapter-user",
        source_options={"garmin_region": configured_region},
        credential_generation=CREDENTIAL_GENERATION,
    )

    assert adapter._is_cn is expected_is_cn


@pytest.mark.parametrize(
    "source_options",
    [
        {},
        {"garmin_region": "cn"},
    ],
)
def test_adapter_rejects_missing_or_mismatched_region(
    source_options: Mapping[str, object],
) -> None:
    with pytest.raises(
        ProviderAuthenticationError,
        match="region",
    ):
        GarminPlanDeliveryAdapter(
            {
                "email": "runner@example.test",
                "password": "secret",
                "is_cn": False,
            },
            user_id="garmin-adapter-user",
            source_options=source_options,
            credential_generation=CREDENTIAL_GENERATION,
        )


def test_adapter_requires_credential_generation() -> None:
    with pytest.raises(
        ProviderAuthenticationError,
        match="credential generation",
    ):
        GarminPlanDeliveryAdapter(
            {
                "email": "runner@example.test",
                "password": "secret",
                "is_cn": False,
            },
            user_id="garmin-adapter-user",
            source_options={"garmin_region": "international"},
            credential_generation=None,
        )


def test_authenticate_uses_generation_scoped_tokenstore(
    monkeypatch,
    tmp_path,
) -> None:
    captured: list[tuple[str, str]] = []
    published: list[str] = []

    class AuthenticatedGarmin:
        display_name = "stable-account"

        def __init__(self, email, password, is_cn=False):
            assert email == "runner@example.test"
            assert password == "secret"
            assert is_cn is False

        def connectapi(self, path):
            assert path == "/userprofile-service/socialProfile"
            return {"userProfileId": 12345}

    def token_dir(user_id: str, credential_generation: str) -> str:
        captured.append((user_id, credential_generation))
        return str(tmp_path / "generation-tokens")

    monkeypatch.setattr("garminconnect.Garmin", AuthenticatedGarmin)
    monkeypatch.setattr("api.routes.sync._garmin_token_dir", token_dir)
    monkeypatch.setattr(
        "api.routes.sync._login_garmin_with_cn_fallback",
        lambda client, creds, path: None,
    )
    monkeypatch.setattr(
        "api.routes.sync._seed_generation_tokens_from_legacy",
        lambda user_id, credential_generation: False,
    )
    adapter = GarminPlanDeliveryAdapter(
        {
            "email": "runner@example.test",
            "password": "secret",
            "is_cn": False,
        },
        user_id="garmin-adapter-user",
        source_options={"garmin_region": "international"},
        credential_generation=CREDENTIAL_GENERATION,
        token_publisher=lambda: (
            published.append(CREDENTIAL_GENERATION) or True
        ),
    )

    adapter.authenticate()

    assert captured == [
        ("garmin-adapter-user", CREDENTIAL_GENERATION),
    ]
    assert published == [CREDENTIAL_GENERATION]


def test_profile_identity_survives_display_name_change() -> None:
    adapter = _adapter(FakeGarmin())
    adapter._provider_account_id = "international:new-display-key"

    assert adapter.matches_provider_account(
        "international:old-display-key",
        {"profile_account_id": PROFILE_ACCOUNT_ID},
    )
    assert not adapter.matches_provider_account(
        "international:old-display-key",
        {"profile_account_id": "international:different-profile"},
    )


def test_prepare_is_deterministic_and_duration_only() -> None:
    adapter = _adapter(FakeGarmin())

    first = adapter.prepare_workout(_workout(), threshold_value=250)
    repeated = adapter.prepare_workout(_workout(), threshold_value=350)

    assert first == repeated
    assert first.request["workout"]["estimatedDurationInSecs"] == 2700
    assert (
        first.request["workout"]["workoutSegments"][0]["workoutSteps"][0][
            "targetType"
        ]["workoutTargetTypeKey"]
        == "no.target"
    )
    assert "praxys:5a334fb4-748e-4cb2-a73b-aa10f830b15a" in (
        first.request["workout"]["workoutName"]
    )


@pytest.mark.parametrize(
    "updates,message",
    [
        ({"planned_duration_min": None}, "requires a duration"),
        ({"target_power_min": 220}, "cannot safely encode"),
        ({"target_hr_max": 165}, "cannot safely encode"),
        ({"target_pace_min": 4.5}, "cannot safely encode"),
    ],
)
def test_prepare_rejects_unverified_encodings(
    updates: Mapping[str, object],
    message: str,
) -> None:
    adapter = _adapter(FakeGarmin())

    with pytest.raises(ProviderRequestError, match=message):
        adapter.prepare_workout(
            _workout(**updates),
            threshold_value=250,
        )


def test_create_checkpoints_both_garmin_identities() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    references, checkpoints, mutations, hooks = _recording_hooks()

    result = adapter.create_workout(prepared, hooks=hooks)

    assert result.external_id == "201"
    assert result.provider_references["template_id"] == "101"
    assert result.provider_references["schedule_id"] == "201"
    assert (
        result.provider_references["profile_account_id"]
        == PROFILE_ACCOUNT_ID
    )
    assert result.provider_references["upload_started"] is True
    assert result.provider_references["schedule_started"] is True
    assert references == result.provider_references
    assert checkpoints[0][0]["preexisting_template_ids"] == []
    assert checkpoints[-1][1] == "201"
    assert mutations == ["before", "before"]
    assert client.upload_calls == 1
    assert client.schedule_calls == 1


def test_mutation_checkpoint_precedes_final_guard_and_provider_io() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    events: list[str] = []
    original_upload = client.upload_workout
    original_schedule = client.schedule_workout

    def upload(payload: Mapping[str, Any]) -> object:
        events.append("upload")
        return original_upload(payload)

    def schedule(template_id: object, schedule_date: str) -> object:
        events.append("schedule")
        return original_schedule(template_id, schedule_date)

    client.upload_workout = upload
    client.schedule_workout = schedule
    references: dict[str, Any] = {}

    def checkpoint(
        update: Mapping[str, Any],
        external_id: str | None,
    ) -> None:
        del external_id
        references.clear()
        references.update(deepcopy(dict(update)))
        if update.get("upload_started") and "template_id" not in update:
            events.append("upload_checkpoint")
        if update.get("schedule_started") and "schedule_id" not in update:
            events.append("schedule_checkpoint")

    hooks = ProviderMutationHooks(
        provider_references=references,
        before_mutation=lambda: events.append("guard"),
        checkpoint=checkpoint,
    )

    adapter.create_workout(prepared, hooks=hooks)

    assert events.index("upload_checkpoint") < events.index("guard")
    assert events.index("guard") < events.index("upload")
    second_guard = events.index("guard", events.index("guard") + 1)
    assert events.index("schedule_checkpoint") < second_guard
    assert second_guard < events.index("schedule")


def test_guard_block_before_schedule_is_safe_to_retry() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    references: dict[str, Any] = {}
    guard_calls = 0

    def checkpoint(
        update: Mapping[str, Any],
        external_id: str | None,
    ) -> None:
        del external_id
        references.clear()
        references.update(deepcopy(dict(update)))

    def block_schedule() -> None:
        nonlocal guard_calls
        guard_calls += 1
        if guard_calls == 2:
            raise RuntimeError("consent revoked")

    with pytest.raises(RuntimeError, match="consent revoked"):
        adapter.create_workout(
            prepared,
            hooks=ProviderMutationHooks(
                provider_references=references,
                before_mutation=block_schedule,
                checkpoint=checkpoint,
            ),
        )

    assert client.upload_calls == 1
    assert client.schedule_calls == 0
    assert references["upload_started"] is True
    assert references["schedule_started"] is False
    assert references["template_id"] == "101"

    result = adapter.create_workout(
        prepared,
        hooks=ProviderMutationHooks(
            provider_references=references,
            before_mutation=lambda: None,
            checkpoint=checkpoint,
        ),
    )

    assert client.upload_calls == 1
    assert client.schedule_calls == 1
    assert result.external_id == "201"


def test_rate_limited_schedule_is_safe_to_retry_after_confirmed_absence() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    references: dict[str, Any] = {}
    original_schedule = client.schedule_workout

    def rate_limited_schedule(
        template_id: object,
        schedule_date: str,
    ) -> object:
        del template_id, schedule_date
        client.schedule_calls += 1
        raise GarminConnectTooManyRequestsError("rate limited")

    client.schedule_workout = rate_limited_schedule

    def checkpoint(
        update: Mapping[str, Any],
        external_id: str | None,
    ) -> None:
        del external_id
        references.clear()
        references.update(deepcopy(dict(update)))

    hooks = ProviderMutationHooks(
        provider_references=references,
        before_mutation=lambda: None,
        checkpoint=checkpoint,
    )
    with pytest.raises(ProviderTransientError, match="rate limit"):
        adapter.create_workout(prepared, hooks=hooks)

    assert client.upload_calls == 1
    assert client.schedule_calls == 1
    assert references["schedule_started"] is False
    assert references["template_id"] == "101"

    client.schedule_workout = original_schedule
    result = adapter.create_workout(prepared, hooks=hooks)

    assert client.upload_calls == 1
    assert client.schedule_calls == 2
    assert result.external_id == "201"


def test_upload_401_requires_reauthentication_without_retrying_workout() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    def reject_upload(payload: Mapping[str, Any]) -> object:
        del payload
        client.upload_calls += 1
        raise _garmin_error(401)

    client.upload_workout = reject_upload

    with pytest.raises(
        ProviderAuthenticationError,
        match="authentication expired",
    ):
        adapter.create_workout(prepared)

    assert client.upload_calls == 1
    assert client.templates == {}
    assert client.schedule_calls == 0


def test_schedule_401_requires_reauthentication_without_reupload() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    def reject_schedule(
        template_id: object,
        schedule_date: str,
    ) -> object:
        del template_id, schedule_date
        client.schedule_calls += 1
        raise _garmin_error(401)

    client.schedule_workout = reject_schedule

    with pytest.raises(
        ProviderAuthenticationError,
        match="authentication expired",
    ):
        adapter.create_workout(prepared)

    assert client.upload_calls == 1
    assert client.schedule_calls == 1
    assert client.schedules == {}


def test_empty_inventory_checkpoint_recovers_without_reupload() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    client.templates["101"] = deepcopy(
        dict(prepared.request["workout"])
    )
    initial = {
        "template_marker": prepared.request["marker"],
        "payload_fingerprint": prepared.content_version,
        "preexisting_template_ids": [],
    }
    references, _, _, hooks = _recording_hooks(initial)

    result = adapter.create_workout(prepared, hooks=hooks)

    assert result.provider_references["template_id"] == "101"
    assert references["schedule_id"] == "201"
    assert client.upload_calls == 0
    assert client.schedule_calls == 1


def test_malformed_upload_response_is_reconciled_by_exact_template() -> None:
    client = FakeGarmin()
    client.upload_response = {}
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    result = adapter.create_workout(prepared)

    assert result.provider_references["template_id"] == "101"
    assert result.external_id == "201"
    assert client.upload_calls == 1
    assert client.schedule_calls == 1


def test_upload_response_cannot_claim_preexisting_template() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    client.templates["99"] = deepcopy(
        dict(prepared.request["workout"])
    )
    client.upload_response = {"workoutId": 99}

    result = adapter.create_workout(prepared)

    assert result.provider_references["template_id"] == "101"
    assert result.external_id == "201"
    assert client.schedules["201"]["template_id"] == "101"
    assert client.upload_calls == 1
    assert client.schedule_calls == 1


def test_template_scan_limit_is_actionable_and_not_retryable() -> None:
    client = FakeGarmin()
    for template_id in range(1, 501):
        client.templates[str(template_id)] = {
            "workoutName": f"Existing workout {template_id}",
            "description": "",
        }
    client._next_template_id = 501
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    with pytest.raises(
        ProviderRejectedError,
        match="too large for safe delivery",
    ):
        adapter.create_workout(prepared)

    assert client.upload_calls == 0
    assert client.schedule_calls == 0


def test_template_scan_limit_after_upload_keeps_outcome_unknown() -> None:
    client = FakeGarmin()
    for template_id in range(1, 500):
        client.templates[str(template_id)] = {
            "workoutName": f"Existing workout {template_id}",
            "description": "",
        }
    client._next_template_id = 500
    client.upload_response = {}
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="safe recovery limit",
    ) as exc_info:
        adapter.create_workout(prepared)

    assert exc_info.value.provider_references["upload_started"] is True
    assert client.upload_calls == 1
    assert client.schedule_calls == 0


def test_transport_timeout_after_upload_is_reconciled() -> None:
    client = FakeGarmin()
    client.upload_error_after_effect = requests.Timeout(
        "response timed out"
    )
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    result = adapter.create_workout(prepared)

    assert result.provider_references["template_id"] == "101"
    assert result.external_id == "201"
    assert client.upload_calls == 1


def test_uploaded_template_is_verified_before_scheduling() -> None:
    client = FakeGarmin()
    client.mutate_uploaded_template = True
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="no longer matches",
    ):
        adapter.create_workout(prepared)

    assert client.upload_calls == 1
    assert client.schedule_calls == 0


@pytest.mark.parametrize(
    "schedule_failure",
    [
        _garmin_error(500),
        requests.Timeout("response timed out"),
        None,
    ],
)
def test_uncertain_schedule_is_not_claimed_or_replayed(
    schedule_failure: Exception | None,
) -> None:
    client = FakeGarmin()
    if schedule_failure is None:
        client.schedule_response = {}
    else:
        client.schedule_error_after_effect = schedule_failure
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="unowned instance",
    ) as captured:
        adapter.create_workout(prepared)

    assert captured.value.provider_references[
        "candidate_schedule_ids"
    ] == ["201"]
    assert list(client.schedules) == ["201"]
    assert client.schedule_calls == 1
    _, _, _, hooks = _recording_hooks(
        captured.value.provider_references
    )

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="unowned Garmin schedule",
    ):
        adapter.create_workout(prepared, hooks=hooks)

    assert client.schedule_calls == 1


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, ProviderAuthenticationRequiredError),
        (429, ProviderRateLimitError),
    ],
)
def test_schedule_verification_preserves_connection_failure(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    original_schedule = client.schedule_workout

    def schedule_then_reject_verification(
        template_id: object,
        schedule_date: str,
    ) -> object:
        response = original_schedule(template_id, schedule_date)
        client.schedule_read_error = _garmin_error(status_code)
        return response

    client.schedule_workout = schedule_then_reject_verification
    references, checkpoints, _, hooks = _recording_hooks()

    with pytest.raises(expected_error):
        adapter.create_workout(prepared, hooks=hooks)

    assert client.schedule_calls == 1
    assert references["returned_schedule_id"] == "201"
    assert any(
        checkpoint["returned_schedule_id"] == "201"
        for checkpoint, _ in checkpoints
        if "returned_schedule_id" in checkpoint
    )


def test_returned_preexisting_schedule_is_never_claimed() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    client.templates["101"] = deepcopy(dict(prepared.request["workout"]))
    client.schedules["250"] = {
        "template_id": "101",
        "date": "2026-08-05",
    }
    client.schedule_response = {
        "workoutScheduleId": 250,
        "date": "2026-08-05",
    }
    _, _, _, hooks = _recording_hooks({
        "template_marker": prepared.request["marker"],
        "payload_fingerprint": prepared.content_version,
        "preexisting_template_ids": [],
        "template_id": "101",
    })

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="pre-existing schedule",
    ) as captured:
        adapter.create_workout(prepared, hooks=hooks)

    assert captured.value.external_id is None
    assert captured.value.provider_references[
        "returned_preexisting_schedule_id"
    ] == "250"


def test_unexpected_date_schedule_is_checkpointed_for_exact_cleanup() -> None:
    client = FakeGarmin()
    client.schedule_date_override = "2026-08-06"
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    references, checkpoints, _, hooks = _recording_hooks()

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="unexpected date",
    ) as captured:
        adapter.create_workout(prepared, hooks=hooks)

    assert captured.value.external_id is None
    assert "schedule_id" not in references
    assert references["returned_schedule_id"] == "201"
    assert references["unexpected_schedule_date"] == "2026-08-06"
    assert checkpoints[-1][1] is None

    _, _, _, retry_hooks = _recording_hooks(references)
    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="requires reconciliation",
    ):
        adapter.create_workout(prepared, hooks=retry_hooks)
    assert client.schedule_calls == 1


def test_cross_date_preexisting_schedule_is_never_claimed() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    client.templates["101"] = deepcopy(dict(prepared.request["workout"]))
    client.schedules["250"] = {
        "template_id": "101",
        "date": "2026-08-06",
    }
    client.schedule_response = {
        "workoutScheduleId": 250,
        "date": "2026-08-05",
    }
    references, checkpoints, _, hooks = _recording_hooks({
        "template_marker": prepared.request["marker"],
        "payload_fingerprint": prepared.content_version,
        "preexisting_template_ids": [],
        "template_id": "101",
    })

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="unexpected date",
    ) as captured:
        adapter.create_workout(prepared, hooks=hooks)

    assert captured.value.external_id is None
    assert references["returned_schedule_id"] == "250"
    assert references["unexpected_schedule_date"] == "2026-08-06"
    assert "schedule_id" not in references
    assert checkpoints[-1][1] is None


def test_manual_reuse_of_retained_template_is_never_adopted() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    client.templates["101"] = deepcopy(dict(prepared.request["workout"]))
    client.schedules["201"] = {
        "template_id": "101",
        "date": "2026-08-05",
    }
    _, _, mutations, hooks = _recording_hooks({
        "template_marker": prepared.request["marker"],
        "payload_fingerprint": prepared.content_version,
        "preexisting_template_ids": [],
        "template_id": "101",
        "preexisting_schedule_ids": [],
    })

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="unowned Garmin schedule",
    ):
        adapter.create_workout(prepared, hooks=hooks)

    assert mutations == []
    assert client.schedule_calls == 0


def test_checkpointed_schedule_absence_fails_closed() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    client.templates["101"] = deepcopy(
        dict(prepared.request["workout"])
    )
    _, _, _, hooks = _recording_hooks({
        "template_marker": prepared.request["marker"],
        "payload_fingerprint": prepared.content_version,
        "preexisting_template_ids": [],
        "template_id": "101",
        "preexisting_schedule_ids": [],
        "schedule_id": "201",
    })

    with pytest.raises(
        ProviderOutcomeUnknownError,
        match="not visible",
    ) as captured:
        adapter.create_workout(prepared, hooks=hooks)

    assert captured.value.external_id == "201"
    assert client.schedule_calls == 0
    assert client.schedules == {}


def test_delete_unschedules_only_owned_instance_and_retains_template() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    prepared = adapter.prepare_workout(_workout(), threshold_value=250)
    client.templates["101"] = deepcopy(
        dict(prepared.request["workout"])
    )
    client.schedules = {
        "201": {"template_id": "101", "date": "2026-08-05"},
        "202": {"template_id": "101", "date": "2026-08-06"},
    }
    _, _, mutations, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    result = adapter.delete_workout("201", hooks=hooks)

    assert result.already_absent is False
    assert client.unschedule_calls == ["201"]
    assert set(client.schedules) == {"202"}
    assert set(client.templates) == {"101"}
    assert mutations == ["before"]
    assert result.response["template_retained"] is True


def test_delete_holds_shared_tokenstore_lease(monkeypatch) -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    client.schedules["201"] = {
        "template_id": "101",
        "date": "2026-08-05",
    }
    events: list[tuple[str, str]] = []

    @contextlib.contextmanager
    def recording_lease(user_id: str):
        events.append(("enter", user_id))
        try:
            yield
        finally:
            events.append(("exit", user_id))

    monkeypatch.setattr(
        "api.routes.sync._garmin_tokenstore_lease",
        recording_lease,
    )
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    adapter.delete_workout("201", hooks=hooks)

    assert events == [
        ("enter", "garmin-adapter-user"),
        ("exit", "garmin-adapter-user"),
    ]


def test_delete_refuses_schedule_with_different_template() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    client.schedules["201"] = {
        "template_id": "999",
        "date": "2026-08-05",
    }
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    with pytest.raises(
        ProviderRemovalOutcomeUnknownError,
        match="owned template",
    ):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == []


def test_delete_preflight_read_failure_is_retryable() -> None:
    client = FakeGarmin()
    client.schedule_read_error = _garmin_error(500)
    adapter = _adapter(client)
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    with pytest.raises(
        ProviderRemovalError,
        match="before removal",
    ):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == []


@pytest.mark.parametrize(
    "transport_error",
    [
        requests.exceptions.ChunkedEncodingError("truncated response"),
        requests.exceptions.ContentDecodingError(
            "invalid compressed response"
        ),
    ],
)
def test_delete_preflight_catches_requests_transport_errors(
    transport_error: requests.RequestException,
) -> None:
    client = FakeGarmin()
    client.schedule_read_error = transport_error
    adapter = _adapter(client)
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    with pytest.raises(ProviderRemovalError, match="before removal"):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == []


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, ProviderAuthenticationRequiredError),
        (429, ProviderRateLimitError),
    ],
)
def test_delete_classifies_requests_http_errors(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    client = FakeGarmin()
    client.schedule_read_error = _requests_error(status_code)
    adapter = _adapter(client)
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    with pytest.raises(expected_error):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == []


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, ProviderAuthenticationRequiredError),
        (429, ProviderRateLimitError),
    ],
)
def test_delete_classifies_nested_garth_error_status(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    client = FakeGarmin()
    nested = requests.RequestException("garth request failed")
    nested.error = _requests_error(status_code)
    client.schedule_read_error = nested
    adapter = _adapter(client)
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    with pytest.raises(expected_error):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == []


def test_delete_accepts_requests_http_404_verification() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    client.schedules["201"] = {
        "template_id": "101",
        "date": "2026-08-05",
    }
    original_read = client.get_scheduled_workout_by_id
    read_count = 0

    def read_then_report_absent(external_id: object) -> dict[str, Any]:
        nonlocal read_count
        read_count += 1
        if read_count == 1:
            return original_read(external_id)
        raise _requests_error(404)

    client.get_scheduled_workout_by_id = read_then_report_absent
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    result = adapter.delete_workout("201", hooks=hooks)

    assert result.already_absent is False
    assert client.unschedule_calls == ["201"]
    assert read_count == 2


def test_delete_transport_timeout_is_reconciled_as_unknown() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    client.schedules["201"] = {
        "template_id": "101",
        "date": "2026-08-05",
    }
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    def timeout(external_id: object) -> None:
        client.unschedule_calls.append(str(external_id))
        raise requests.Timeout("response timed out")

    client.unschedule_workout = timeout

    with pytest.raises(
        ProviderRemovalOutcomeUnknownError,
        match="outcome is uncertain",
    ):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == ["201"]
    assert "201" in client.schedules


def test_delete_dedicated_rate_limit_preserves_retryable_category() -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    client.schedules["201"] = {
        "template_id": "101",
        "date": "2026-08-05",
    }
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    def rate_limited(external_id: object) -> None:
        client.unschedule_calls.append(str(external_id))
        raise GarminConnectTooManyRequestsError("rate limited")

    client.unschedule_workout = rate_limited

    with pytest.raises(ProviderRateLimitError, match="rate limit"):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == ["201"]
    assert "201" in client.schedules


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, ProviderAuthenticationRequiredError),
        (429, ProviderRateLimitError),
    ],
)
def test_delete_preserves_connection_failure_when_verification_fails(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    client = FakeGarmin()
    adapter = _adapter(client)
    client.schedules["201"] = {
        "template_id": "101",
        "date": "2026-08-05",
    }
    _, _, _, hooks = _recording_hooks({
        "template_id": "101",
        "profile_account_id": PROFILE_ACCOUNT_ID,
    })

    def rejected(external_id: object) -> None:
        client.unschedule_calls.append(str(external_id))
        client.schedule_read_error = _garmin_error(500)
        raise _garmin_error(status_code)

    client.unschedule_workout = rejected

    with pytest.raises(expected_error):
        adapter.delete_workout("201", hooks=hooks)

    assert client.unschedule_calls == ["201"]
    assert "201" in client.schedules
