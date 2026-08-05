"""Experimental Garmin Connect implementation of managed-plan delivery."""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from datetime import date, timedelta
from typing import Any, Callable, Mapping

import requests
from garminconnect.exceptions import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from api.plan_delivery.base import (
    NOOP_PROVIDER_MUTATION_HOOKS,
    PreparedWorkoutDelivery,
    ProviderAuthenticationError,
    ProviderAuthenticationRequiredError,
    ProviderCreateResult,
    ProviderMutationHooks,
    ProviderOutcomeUnknownError,
    ProviderRateLimitError,
    ProviderReadError,
    ProviderRejectedError,
    ProviderRemoveResult,
    ProviderRemovalError,
    ProviderRemovalOutcomeUnknownError,
    ProviderRequestError,
    ProviderTransientError,
)
from api.plan_delivery.capabilities import garmin_region
from sync.garmin_sync import (
    enrich_training_plan_content,
    fetch_training_plan_api,
    garmin_workout_content_fingerprint,
    garmin_profile_account_id,
    garmin_provider_account_id,
    garmin_user_profile_id,
    parse_scheduled_workouts,
)
from sync.garmin_errors import garmin_http_status

try:
    from garth.exc import GarthHTTPError
except ImportError:
    _GARTH_HTTP_ERRORS: tuple[type[BaseException], ...] = ()
else:
    _GARTH_HTTP_ERRORS = (GarthHTTPError,)

_MAX_TEMPLATE_SCAN = 500
_TEMPLATE_PAGE_SIZE = 100
_MAX_DURATION_SECONDS = 24 * 60 * 60
_MIN_MUTATION_INTERVAL_SECONDS = 1.0
_MUTATION_PACE_LOCK = threading.Lock()
_last_mutation_started_at = 0.0
_TARGET_FIELDS = (
    "target_power_min",
    "target_power_max",
    "target_hr_min",
    "target_hr_max",
    "target_pace_min",
    "target_pace_max",
)
_GARMIN_ERRORS = (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
    *_GARTH_HTTP_ERRORS,
)
_GARMIN_READ_ERRORS = _GARMIN_ERRORS + (
    requests.RequestException,
    TypeError,
    ValueError,
)
_GARMIN_AUTH_ERRORS = _GARMIN_READ_ERRORS + (
    OSError,
    RuntimeError,
)


class _GarminTemplateLibraryLimitError(ProviderReadError):
    """The bounded recovery scan cannot prove template identity safely."""


def _positive_id(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.isdecimal() and int(normalized) > 0:
            return str(int(normalized))
    return None


_http_status = garmin_http_status


def _is_rate_limited(error: BaseException | None) -> bool:
    """Return whether Garmin explicitly rejected a request with HTTP 429."""
    return bool(
        error is not None
        and (
            isinstance(error, GarminConnectTooManyRequestsError)
            or _http_status(error) == 429
        )
    )


def _is_authentication_rejected(error: BaseException | None) -> bool:
    """Return whether Garmin explicitly rejected credentials with HTTP 401."""
    return bool(
        error is not None
        and (
            isinstance(error, GarminConnectAuthenticationError)
            or _http_status(error) == 401
        )
    )


def _raise_provider_read_failure(
    message: str,
    error: BaseException,
) -> None:
    if _is_rate_limited(error):
        raise ProviderRateLimitError(
            "Garmin API rate limit blocked calendar verification"
        ) from error
    if _is_authentication_rejected(error):
        raise ProviderAuthenticationRequiredError(
            "Garmin authentication expired; reconnect Garmin"
        ) from error
    raise ProviderReadError(message) from error


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not a workout number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("workout number must be finite")
    return result


class GarminPlanDeliveryAdapter:
    """Create and remove duration-based Garmin workouts for one account."""

    target = "garmin"
    display_name = "Garmin"

    def __init__(
        self,
        credentials: Mapping[str, Any],
        *,
        user_id: str,
        source_options: Mapping[str, Any],
        credential_generation: str | None,
        token_publisher: Callable[[], bool] | None = None,
    ) -> None:
        email = credentials.get("email")
        password = credentials.get("password")
        if not isinstance(email, str) or not email.strip():
            raise ProviderAuthenticationError(
                "Garmin credentials are missing an email"
            )
        if not isinstance(password, str) or not password:
            raise ProviderAuthenticationError(
                "Garmin credentials are missing a password"
            )
        self._email = email.strip()
        self._password = password
        self._user_id = str(user_id)
        if not isinstance(credential_generation, str) or not (
            credential_generation.strip()
        ):
            raise ProviderAuthenticationError(
                "Garmin credential generation is unavailable; reconnect Garmin"
            )
        self._credential_generation = credential_generation
        region = garmin_region(source_options)
        if region is None:
            raise ProviderAuthenticationError(
                "Garmin region is not configured; reconnect Garmin"
            )
        credential_region = (
            "cn" if credentials.get("is_cn") is True else "international"
        )
        if credential_region != region:
            raise ProviderAuthenticationError(
                "Garmin credentials do not match the configured region"
            )
        self._is_cn = region == "cn"
        self._client: Any | None = None
        self._provider_account_id: str | None = None
        self._profile_account_id: str | None = None
        self._token_publisher = token_publisher

    @property
    def account_id(self) -> str:
        """Return the rollout-compatible Garmin calendar account key."""
        self.authenticate()
        assert self._provider_account_id is not None
        return self._provider_account_id

    @property
    def account_references(self) -> Mapping[str, Any]:
        """Return the immutable identity fence for calendar snapshots."""
        self.authenticate()
        assert self._profile_account_id is not None
        return {"profile_account_id": self._profile_account_id}

    def matches_provider_account(
        self,
        stored_account_id: str,
        provider_references: Mapping[str, Any],
    ) -> bool:
        """Match a legacy calendar key through Garmin's immutable profile ID."""
        del stored_account_id
        self.authenticate()
        assert self._profile_account_id is not None
        return (
            str(
                provider_references.get("profile_account_id") or ""
            ).strip()
            == self._profile_account_id
        )

    def authenticate(self) -> None:
        """Reuse Praxys's isolated tokenstore and Garmin login workarounds."""
        if (
            self._client is not None
            and self._provider_account_id is not None
            and self._profile_account_id is not None
        ):
            return
        from api.routes.sync import _garmin_tokenstore_lease

        with _garmin_tokenstore_lease(self._user_id):
            self._authenticate_locked()

    def _authenticate_locked(self) -> None:
        """Authenticate while the caller holds the tokenstore lease."""
        if (
            self._client is not None
            and self._provider_account_id is not None
            and self._profile_account_id is not None
        ):
            return
        try:
            from garminconnect import Garmin
            from api.routes.sync import (
                _garmin_token_dir,
                _login_garmin_with_cn_fallback,
                _seed_generation_tokens_from_legacy,
            )

            client = Garmin(
                self._email,
                self._password,
                is_cn=self._is_cn,
            )
            token_dir = _garmin_token_dir(
                self._user_id,
                self._credential_generation,
            )
            _seed_generation_tokens_from_legacy(
                self._user_id,
                self._credential_generation,
            )
            os.makedirs(token_dir, exist_ok=True)
            _login_garmin_with_cn_fallback(
                client,
                {
                    "email": self._email,
                    "password": self._password,
                    "is_cn": self._is_cn,
                },
                token_dir,
            )
            profile_id = garmin_user_profile_id(client)
            profile_account_id = garmin_profile_account_id(
                user_id=self._user_id,
                is_cn=self._is_cn,
                garmin_user_profile_id=profile_id,
            )
            account_id = garmin_provider_account_id(
                user_id=self._user_id,
                display_name=getattr(client, "display_name", ""),
                is_cn=self._is_cn,
            )
        except _GARMIN_AUTH_ERRORS as exc:
            if _is_rate_limited(exc):
                raise ProviderRateLimitError(
                    "Garmin login was rate limited"
                ) from exc
            if _is_authentication_rejected(exc):
                raise ProviderAuthenticationRequiredError(
                    "Garmin login failed; reconnect Garmin"
                ) from exc
            raise ProviderAuthenticationError("Garmin login failed") from exc
        self._client = client
        self._provider_account_id = account_id
        self._profile_account_id = profile_account_id
        if (
            self._token_publisher is not None
            and not self._token_publisher()
        ):
            self._client = None
            self._provider_account_id = None
            self._profile_account_id = None
            raise ProviderAuthenticationError(
                "Garmin connection changed during login"
            )

    def _session(self) -> Any:
        self._authenticate_locked()
        assert self._client is not None
        return self._client

    @staticmethod
    def _pace_mutation() -> None:
        """Space undocumented Garmin writes to reduce bot-mitigation risk."""
        global _last_mutation_started_at
        with _MUTATION_PACE_LOCK:
            now = time.monotonic()
            delay = (
                _last_mutation_started_at
                + _MIN_MUTATION_INTERVAL_SECONDS
                - now
            )
            if delay > 0:
                time.sleep(delay)
            _last_mutation_started_at = time.monotonic()

    @staticmethod
    def _prepare_payload(
        workout: Mapping[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        canonical_id = str(workout.get("canonical_id") or "").strip()
        if not canonical_id:
            raise ProviderRequestError(
                "Garmin delivery requires canonical workout identity"
            )
        unsupported = [
            field
            for field in _TARGET_FIELDS
            if workout.get(field) not in (None, "", 0, 0.0)
        ]
        if unsupported:
            raise ProviderRequestError(
                "Garmin experimental delivery cannot safely encode "
                "power, heart-rate, or pace targets yet"
            )
        try:
            duration_minutes = _number(
                workout.get("planned_duration_min")
            )
        except (TypeError, ValueError) as exc:
            raise ProviderRequestError(
                "Garmin workout duration is invalid"
            ) from exc
        if duration_minutes is None or duration_minutes <= 0:
            raise ProviderRequestError(
                "Garmin experimental delivery requires a duration"
            )
        duration_seconds = round(duration_minutes * 60)
        if not 1 <= duration_seconds <= _MAX_DURATION_SECONDS:
            raise ProviderRequestError(
                "Garmin workout duration is outside the supported range"
            )

        workout_type = str(
            workout.get("workout_type") or "workout"
        ).replace("_", " ").strip().title()
        marker = f"praxys:{canonical_id}"
        workout_name = f"Praxys {workout_type} [{marker}]"
        description_parts = [
            f"[{marker}]",
            str(workout.get("workout_description") or "").strip(),
        ]
        distance = workout.get("planned_distance_km")
        if distance not in (None, ""):
            try:
                distance_value = _number(distance)
            except (TypeError, ValueError) as exc:
                raise ProviderRequestError(
                    "Garmin workout distance is invalid"
                ) from exc
            if distance_value is not None and distance_value > 0:
                description_parts.append(
                    f"Planned distance: {distance_value:g} km."
                )
        description = " ".join(
            part for part in description_parts if part
        )
        sport_type = {
            "sportTypeId": 1,
            "sportTypeKey": "running",
            "displayOrder": 1,
        }
        payload = {
            "workoutName": workout_name,
            "sportType": sport_type,
            "estimatedDurationInSecs": duration_seconds,
            "workoutSegments": [{
                "segmentOrder": 1,
                "sportType": sport_type,
                "workoutSteps": [{
                    "type": "ExecutableStepDTO",
                    "stepOrder": 1,
                    "stepType": {
                        "stepTypeId": 1,
                        "stepTypeKey": "warmup",
                        "displayOrder": 1,
                    },
                    "endCondition": {
                        "conditionTypeId": 2,
                        "conditionTypeKey": "time",
                        "displayOrder": 2,
                        "displayable": True,
                    },
                    "endConditionValue": float(duration_seconds),
                    "targetType": {
                        "workoutTargetTypeId": 1,
                        "workoutTargetTypeKey": "no.target",
                        "displayOrder": 1,
                    },
                }],
            }],
            "author": {},
            "description": description,
        }
        return payload, marker, str(workout["date"])

    def prepare_workout(
        self,
        workout: Mapping[str, Any],
        *,
        threshold_value: float,
    ) -> PreparedWorkoutDelivery:
        """Prepare one deterministic duration-only Garmin request."""
        del threshold_value
        payload, marker, schedule_date = self._prepare_payload(workout)
        content_version = garmin_workout_content_fingerprint(payload)
        request = {
            "workout": payload,
            "marker": marker,
            "schedule_date": schedule_date,
        }
        encoded = json.dumps(
            request,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
        return PreparedWorkoutDelivery(
            version=hashlib.sha256(encoded).hexdigest(),
            request=request,
            content_version=content_version,
        )

    def _list_templates(self) -> list[Mapping[str, Any]]:
        client = self._session()
        templates: list[Mapping[str, Any]] = []
        for start in range(0, _MAX_TEMPLATE_SCAN, _TEMPLATE_PAGE_SIZE):
            try:
                page = client.get_workouts(
                    start=start,
                    limit=_TEMPLATE_PAGE_SIZE,
                )
            except _GARMIN_READ_ERRORS as exc:
                _raise_provider_read_failure(
                    "Garmin workout library could not be read",
                    exc,
                )
            if not isinstance(page, list) or not all(
                isinstance(item, Mapping) for item in page
            ):
                raise ProviderReadError(
                    "Garmin workout library payload is invalid"
                )
            templates.extend(page)
            if len(page) < _TEMPLATE_PAGE_SIZE:
                return templates
        raise _GarminTemplateLibraryLimitError(
            "Garmin workout library has at least "
            f"{_MAX_TEMPLATE_SCAN} templates"
        )

    def _template_ids(self) -> list[str]:
        return sorted({
            template_id
            for row in self._list_templates()
            if (
                template_id := _positive_id(row.get("workoutId"))
            ) is not None
        })

    def _matching_templates(
        self,
        *,
        marker: str,
        content_version: str,
        excluded_ids: set[str],
    ) -> list[str]:
        client = self._session()
        matches: list[str] = []
        for summary in self._list_templates():
            template_id = _positive_id(summary.get("workoutId"))
            if (
                template_id is None
                or template_id in excluded_ids
                or (
                    marker not in str(summary.get("workoutName") or "")
                    and marker not in str(summary.get("description") or "")
                )
            ):
                continue
            try:
                template = client.get_workout_by_id(template_id)
                fingerprint = garmin_workout_content_fingerprint(template)
            except _GARMIN_READ_ERRORS as exc:
                _raise_provider_read_failure(
                    "Garmin workout template could not be verified",
                    exc,
                )
            if fingerprint == content_version:
                matches.append(template_id)
        return matches

    def _template_matches(
        self,
        template_id: str,
        *,
        marker: str,
        content_version: str,
    ) -> bool:
        try:
            template = self._session().get_workout_by_id(template_id)
            fingerprint = garmin_workout_content_fingerprint(template)
        except _GARMIN_READ_ERRORS as exc:
            if _http_status(exc) == 404:
                return False
            _raise_provider_read_failure(
                "Garmin workout template could not be verified",
                exc,
            )
        return (
            (
                marker in str(template.get("workoutName") or "")
                or marker in str(template.get("description") or "")
            )
            and fingerprint == content_version
        )

    def _scheduled_for_template(
        self,
        *,
        template_id: str,
        schedule_date: str,
    ) -> list[dict[str, Any]]:
        workout_date = date.fromisoformat(schedule_date)
        try:
            payload = self._session().get_scheduled_workouts(
                workout_date.year,
                workout_date.month,
            )
            return [
                row
                for row in parse_scheduled_workouts(
                    payload,
                    window_start=workout_date,
                    window_end=workout_date,
                )
                if (
                    row.get("provider_references", {}).get("template_id")
                    == template_id
                )
            ]
        except _GARMIN_READ_ERRORS as exc:
            _raise_provider_read_failure(
                "Garmin schedule calendar could not be verified",
                exc,
            )

    @staticmethod
    def _extract_template_id(response: object) -> str:
        if not isinstance(response, Mapping):
            raise ProviderOutcomeUnknownError(
                "Garmin upload response was not an object"
            )
        template_id = _positive_id(response.get("workoutId"))
        if template_id is None:
            raise ProviderOutcomeUnknownError(
                "Garmin upload response did not include workoutId"
            )
        return template_id

    @staticmethod
    def _extract_schedule_id(
        response: object,
        *,
        schedule_date: str,
    ) -> str:
        if not isinstance(response, Mapping):
            raise ProviderOutcomeUnknownError(
                "Garmin schedule response was not an object"
            )
        external_id = _positive_id(response.get("workoutScheduleId"))
        if external_id is None:
            raise ProviderOutcomeUnknownError(
                "Garmin schedule response did not include workoutScheduleId"
            )
        response_date = str(response.get("date") or schedule_date)
        if response_date[:10] != schedule_date:
            raise ProviderOutcomeUnknownError(
                "Garmin scheduled the workout on an unexpected date",
                external_id=external_id,
            )
        return external_id

    def create_workout(
        self,
        prepared: PreparedWorkoutDelivery,
        *,
        hooks: ProviderMutationHooks = NOOP_PROVIDER_MUTATION_HOOKS,
    ) -> ProviderCreateResult:
        """Upload, checkpoint, schedule, and verify one Garmin workout."""
        from api.routes.sync import _garmin_tokenstore_lease

        with _garmin_tokenstore_lease(self._user_id):
            return self._create_workout_locked(prepared, hooks=hooks)

    def _create_workout_locked(
        self,
        prepared: PreparedWorkoutDelivery,
        *,
        hooks: ProviderMutationHooks,
    ) -> ProviderCreateResult:
        """Create a workout while the caller holds the tokenstore lease."""
        request = prepared.request
        payload = request.get("workout")
        marker = str(request.get("marker") or "")
        schedule_date = str(request.get("schedule_date") or "")
        if (
            not isinstance(payload, Mapping)
            or not marker
            or not schedule_date
            or prepared.content_version is None
        ):
            raise ProviderRequestError(
                "Prepared Garmin workout is incomplete"
            )
        client = self._session()
        assert self._profile_account_id is not None
        references = dict(hooks.provider_references)
        existing_profile_account_id = str(
            references.get("profile_account_id") or ""
        ).strip()
        if (
            existing_profile_account_id
            and existing_profile_account_id != self._profile_account_id
        ):
            raise ProviderOutcomeUnknownError(
                "Garmin profile changed during delivery recovery",
                provider_references=references,
            )
        references["profile_account_id"] = self._profile_account_id
        if references.get("template_marker") not in (None, marker):
            raise ProviderOutcomeUnknownError(
                "Garmin template marker changed during recovery",
                provider_references=references,
            )
        if references.get("payload_fingerprint") not in (
            None,
            prepared.content_version,
        ):
            raise ProviderOutcomeUnknownError(
                "Garmin template content changed during recovery",
                provider_references=references,
            )

        template_id = _positive_id(references.get("template_id"))
        has_preexisting_checkpoint = (
            "preexisting_template_ids" in references
        )
        preexisting_ids = {
            value
            for raw in references.get("preexisting_template_ids", [])
            if (value := _positive_id(raw)) is not None
        }
        if template_id is None and not has_preexisting_checkpoint:
            try:
                preexisting_ids = set(self._template_ids())
            except _GarminTemplateLibraryLimitError as exc:
                raise ProviderRejectedError(
                    "Garmin workout library is too large for safe delivery; "
                    "remove unused templates in Garmin Connect before retrying"
                ) from exc
            except ProviderReadError as exc:
                raise ProviderTransientError(
                    "Garmin workout library could not be read before upload"
                ) from exc
            references.update({
                "template_marker": marker,
                "payload_fingerprint": prepared.content_version,
                "preexisting_template_ids": sorted(preexisting_ids),
            })
            hooks.checkpoint(references, None)
        elif template_id is None:
            try:
                recovered = self._matching_templates(
                    marker=marker,
                    content_version=prepared.content_version,
                    excluded_ids=preexisting_ids,
                )
            except _GarminTemplateLibraryLimitError as exc:
                raise ProviderOutcomeUnknownError(
                    "Garmin workout recovery exceeds the safe template "
                    "scan limit",
                    provider_references=references,
                ) from exc
            except ProviderReadError as exc:
                raise ProviderTransientError(
                    "Garmin workout recovery could not be read"
                ) from exc
            if len(recovered) > 1:
                raise ProviderOutcomeUnknownError(
                    "Multiple Garmin templates match the prior upload",
                    provider_references=references,
                )
            if len(recovered) == 1:
                template_id = recovered[0]
                references["template_id"] = template_id
                hooks.checkpoint(references, None)

        if template_id is None:
            upload_error: BaseException | None = None
            try:
                references["upload_started"] = True
                hooks.checkpoint(references, None)
                self._pace_mutation()
                try:
                    hooks.before_mutation()
                except Exception:
                    references["upload_started"] = False
                    hooks.checkpoint(references, None)
                    raise
                upload_response = client.upload_workout(dict(payload))
                template_id = self._extract_template_id(upload_response)
                if template_id in preexisting_ids:
                    template_id = None
                    raise ProviderOutcomeUnknownError(
                        "Garmin upload returned a pre-existing template",
                        provider_references=references,
                    )
            except ProviderOutcomeUnknownError as exc:
                upload_error = exc
            except _GARMIN_READ_ERRORS as exc:
                upload_error = exc
            if template_id is None:
                try:
                    recovered = self._matching_templates(
                        marker=marker,
                        content_version=prepared.content_version,
                        excluded_ids=preexisting_ids,
                    )
                except _GarminTemplateLibraryLimitError as exc:
                    raise ProviderOutcomeUnknownError(
                        "Garmin upload may have succeeded, but the workout "
                        "library exceeds the safe recovery limit",
                        provider_references=references,
                    ) from exc
                except ProviderReadError:
                    recovered = []
                if len(recovered) == 1:
                    template_id = recovered[0]
                elif len(recovered) > 1:
                    raise ProviderOutcomeUnknownError(
                        "Multiple Garmin templates match an uncertain upload",
                        provider_references=references,
                    ) from upload_error
                else:
                    status = (
                        _http_status(upload_error)
                        if upload_error is not None
                        else None
                    )
                    if _is_rate_limited(upload_error):
                        references["upload_started"] = False
                        hooks.checkpoint(references, None)
                        raise ProviderRateLimitError(
                            "Garmin API rate limit rejected the upload"
                        ) from upload_error
                    if _is_authentication_rejected(upload_error):
                        references["upload_started"] = False
                        hooks.checkpoint(references, None)
                        raise ProviderAuthenticationRequiredError(
                            "Garmin authentication expired during upload"
                        ) from upload_error
                    if (
                        status is not None
                        and status < 500
                        and status != 408
                    ):
                        references["upload_started"] = False
                        hooks.checkpoint(references, None)
                        raise ProviderRejectedError(
                            f"Garmin rejected the workout: {upload_error}"
                        ) from upload_error
                    raise ProviderOutcomeUnknownError(
                        "Garmin workout upload outcome is uncertain",
                        provider_references=references,
                    ) from upload_error
            references["template_id"] = template_id
            hooks.checkpoint(references, None)

        try:
            template_matches = self._template_matches(
                template_id,
                marker=marker,
                content_version=prepared.content_version,
            )
        except ProviderReadError as exc:
            raise ProviderTransientError(
                "Checkpointed Garmin template could not be read"
            ) from exc
        if not template_matches:
            raise ProviderOutcomeUnknownError(
                "Checkpointed Garmin template no longer matches",
                provider_references=references,
            )

        try:
            scheduled = self._scheduled_for_template(
                template_id=template_id,
                schedule_date=schedule_date,
            )
        except ProviderReadError as exc:
            raise ProviderTransientError(
                "Garmin calendar could not be read before scheduling"
            ) from exc
        preexisting_schedule_ids = {
            value
            for raw in references.get("preexisting_schedule_ids", [])
            if (value := _positive_id(raw)) is not None
        }
        if "preexisting_schedule_ids" not in references:
            preexisting_schedule_ids = {
                str(row["external_id"]) for row in scheduled
            }
            references["preexisting_schedule_ids"] = sorted(
                preexisting_schedule_ids
            )
            hooks.checkpoint(references, None)
        checkpointed_schedule_id = _positive_id(
            references.get("schedule_id")
        )
        if checkpointed_schedule_id is not None:
            exact_checkpoint = [
                row for row in scheduled
                if str(row["external_id"]) == checkpointed_schedule_id
            ]
            if len(exact_checkpoint) != 1:
                raise ProviderOutcomeUnknownError(
                    "Checkpointed Garmin schedule is not visible",
                    provider_references=references,
                    external_id=checkpointed_schedule_id,
                )
            external_id: str | None = checkpointed_schedule_id
        else:
            candidates = [
                row for row in scheduled
                if str(row["external_id"]) not in preexisting_schedule_ids
            ]
            if candidates:
                references["candidate_schedule_ids"] = sorted(
                    str(row["external_id"]) for row in candidates
                )
                raise ProviderOutcomeUnknownError(
                    "An unowned Garmin schedule uses this workout template",
                    provider_references=references,
                )
            external_id = None

        if (
            external_id is None
            and references.get("schedule_started") is True
        ):
            raise ProviderOutcomeUnknownError(
                "A prior Garmin schedule attempt requires reconciliation",
                provider_references=references,
            )

        if external_id is None:
            schedule_error: BaseException | None = None
            try:
                references["schedule_started"] = True
                hooks.checkpoint(references, None)
                self._pace_mutation()
                try:
                    hooks.before_mutation()
                except Exception:
                    references["schedule_started"] = False
                    hooks.checkpoint(references, None)
                    raise
                schedule_response = client.schedule_workout(
                    template_id,
                    schedule_date,
                )
            except _GARMIN_READ_ERRORS as exc:
                schedule_error = exc
            else:
                try:
                    external_id = self._extract_schedule_id(
                        schedule_response,
                        schedule_date=schedule_date,
                    )
                except ProviderOutcomeUnknownError as exc:
                    returned_id = _positive_id(exc.external_id)
                    if returned_id is None:
                        schedule_error = exc
                    else:
                        references["returned_schedule_id"] = returned_id
                        if returned_id in preexisting_schedule_ids:
                            references[
                                "returned_preexisting_schedule_id"
                            ] = returned_id
                            hooks.checkpoint(references, None)
                            raise ProviderOutcomeUnknownError(
                                "Garmin returned a pre-existing schedule "
                                "identity",
                                provider_references=references,
                            ) from exc
                        try:
                            returned_schedule = (
                                client.get_scheduled_workout_by_id(
                                    returned_id
                                )
                            )
                        except _GARMIN_READ_ERRORS as read_exc:
                            hooks.checkpoint(references, None)
                            if _is_rate_limited(read_exc):
                                raise ProviderRateLimitError(
                                    "Garmin API rate limit blocked schedule "
                                    "verification"
                                ) from read_exc
                            if _is_authentication_rejected(read_exc):
                                raise ProviderAuthenticationRequiredError(
                                    "Garmin authentication expired during "
                                    "schedule verification"
                                ) from read_exc
                            raise ProviderOutcomeUnknownError(
                                "Garmin returned schedule could not be "
                                "verified",
                                provider_references=references,
                            ) from read_exc
                        if (
                            not isinstance(returned_schedule, Mapping)
                            or _positive_id(
                                returned_schedule.get("workoutId")
                            )
                            != template_id
                        ):
                            hooks.checkpoint(references, None)
                            raise ProviderOutcomeUnknownError(
                                "Garmin returned schedule does not use the "
                                "created template",
                                provider_references=references,
                            ) from exc
                        references["unexpected_schedule_date"] = str(
                            returned_schedule.get("date") or ""
                        )
                        hooks.checkpoint(references, None)
                        raise ProviderOutcomeUnknownError(
                            "Garmin scheduled the workout on an unexpected "
                            "date",
                            provider_references=references,
                        ) from exc
                if external_id is not None:
                    references["returned_schedule_id"] = external_id
                    if external_id in preexisting_schedule_ids:
                        references[
                            "returned_preexisting_schedule_id"
                        ] = external_id
                        hooks.checkpoint(references, None)
                        raise ProviderOutcomeUnknownError(
                            "Garmin returned a pre-existing schedule identity",
                            provider_references=references,
                        )
                    try:
                        returned_schedule = (
                            client.get_scheduled_workout_by_id(external_id)
                        )
                    except _GARMIN_READ_ERRORS as read_exc:
                        hooks.checkpoint(references, None)
                        if _is_rate_limited(read_exc):
                            raise ProviderRateLimitError(
                                "Garmin API rate limit blocked schedule "
                                "verification"
                            ) from read_exc
                        if _is_authentication_rejected(read_exc):
                            raise ProviderAuthenticationRequiredError(
                                "Garmin authentication expired during "
                                "schedule verification"
                            ) from read_exc
                        raise ProviderOutcomeUnknownError(
                            "Garmin returned schedule could not be verified",
                            provider_references=references,
                        ) from read_exc
                    returned_template_id = (
                        _positive_id(returned_schedule.get("workoutId"))
                        if isinstance(returned_schedule, Mapping)
                        else None
                    )
                    returned_date = (
                        str(returned_schedule.get("date") or "")[:10]
                        if isinstance(returned_schedule, Mapping)
                        else ""
                    )
                    if returned_template_id != template_id:
                        hooks.checkpoint(references, None)
                        raise ProviderOutcomeUnknownError(
                            "Garmin returned schedule does not use the "
                            "created template",
                            provider_references=references,
                        )
                    if returned_date != schedule_date:
                        references["unexpected_schedule_date"] = (
                            returned_date
                        )
                        hooks.checkpoint(references, None)
                        raise ProviderOutcomeUnknownError(
                            "Garmin scheduled the workout on an unexpected "
                            "date",
                            provider_references=references,
                        )
            if external_id is None:
                try:
                    after = self._scheduled_for_template(
                        template_id=template_id,
                        schedule_date=schedule_date,
                    )
                except ProviderReadError:
                    after = []
                candidates = [
                    row for row in after
                    if (
                        str(row["external_id"])
                        not in preexisting_schedule_ids
                    )
                ]
                if candidates:
                    references["candidate_schedule_ids"] = sorted(
                        str(row["external_id"]) for row in candidates
                    )
                    raise ProviderOutcomeUnknownError(
                        "Garmin scheduling may have created an unowned instance",
                        provider_references=references,
                    ) from schedule_error
                status = (
                    _http_status(schedule_error)
                    if schedule_error is not None
                    else None
                )
                if _is_rate_limited(schedule_error):
                    references["schedule_started"] = False
                    hooks.checkpoint(references, None)
                    raise ProviderRateLimitError(
                        "Garmin API rate limit rejected the schedule"
                    ) from schedule_error
                if _is_authentication_rejected(schedule_error):
                    references["schedule_started"] = False
                    hooks.checkpoint(references, None)
                    raise ProviderAuthenticationRequiredError(
                        "Garmin authentication expired during scheduling"
                    ) from schedule_error
                if (
                    status is not None
                    and status < 500
                    and status != 408
                ):
                    references["schedule_started"] = False
                    hooks.checkpoint(references, None)
                    raise ProviderRejectedError(
                        f"Garmin rejected the schedule: {schedule_error}"
                    ) from schedule_error
                raise ProviderOutcomeUnknownError(
                    "Garmin schedule outcome is uncertain",
                    provider_references=references,
                ) from schedule_error
            references["schedule_id"] = external_id
            hooks.checkpoint(references, external_id)

        try:
            verified = self._scheduled_for_template(
                template_id=template_id,
                schedule_date=schedule_date,
            )
        except ProviderReadError as exc:
            raise ProviderOutcomeUnknownError(
                "Garmin schedule could not be read after creation",
                provider_references=references,
                external_id=external_id,
            ) from exc
        exact = [
            row for row in verified
            if str(row["external_id"]) == external_id
        ]
        if len(exact) != 1:
            raise ProviderOutcomeUnknownError(
                "Garmin schedule could not be verified after creation",
                provider_references=references,
                external_id=external_id,
            )
        return ProviderCreateResult(
            external_id=external_id,
            provider_account_id=self.account_id,
            provider_references=references,
            response={
                "workoutId": template_id,
                "workoutScheduleId": external_id,
                "experimental": True,
                "fidelity": "duration_only",
            },
        )

    def delete_workout(
        self,
        external_id: str,
        *,
        hooks: ProviderMutationHooks = NOOP_PROVIDER_MUTATION_HOOKS,
    ) -> ProviderRemoveResult:
        """Unschedule the exact owned instance without touching other entries."""
        from api.routes.sync import _garmin_tokenstore_lease

        with _garmin_tokenstore_lease(self._user_id):
            return self._delete_workout_locked(external_id, hooks=hooks)

    def _delete_workout_locked(
        self,
        external_id: str,
        *,
        hooks: ProviderMutationHooks,
    ) -> ProviderRemoveResult:
        """Remove a workout while the caller holds the tokenstore lease."""
        self._authenticate_locked()
        assert self._profile_account_id is not None
        owned_profile_account_id = str(
            hooks.provider_references.get("profile_account_id") or ""
        ).strip()
        if (
            not owned_profile_account_id
            or owned_profile_account_id != self._profile_account_id
        ):
            raise ProviderRemovalOutcomeUnknownError(
                "Garmin profile identity does not match this delivery",
                provider_references=hooks.provider_references,
            )
        template_id = _positive_id(
            hooks.provider_references.get("template_id")
        )
        if template_id is None:
            raise ProviderRemovalOutcomeUnknownError(
                "Garmin template identity is missing",
                provider_references=hooks.provider_references,
            )
        client = self._session()
        already_absent = False
        try:
            scheduled = client.get_scheduled_workout_by_id(external_id)
        except _GARMIN_READ_ERRORS as exc:
            if _http_status(exc) == 404:
                already_absent = True
                scheduled = None
            elif (
                isinstance(
                    exc,
                    (
                        GarminConnectAuthenticationError,
                        GarminConnectTooManyRequestsError,
                    ),
                )
                or _http_status(exc) in {401, 429}
            ):
                _raise_provider_read_failure(
                    "Garmin schedule could not be verified before removal",
                    exc,
                )
            else:
                raise ProviderRemovalError(
                    "Garmin schedule could not be verified before removal",
                ) from exc
        if scheduled is not None and not isinstance(scheduled, Mapping):
            raise ProviderRemovalOutcomeUnknownError(
                "Garmin schedule payload is invalid",
                provider_references=hooks.provider_references,
            )
        if scheduled is not None:
            observed_template_id = _positive_id(scheduled.get("workoutId"))
            if observed_template_id != template_id:
                raise ProviderRemovalOutcomeUnknownError(
                    "Garmin schedule no longer references the owned template",
                    provider_references=hooks.provider_references,
                )

        if not already_absent:
            try:
                self._pace_mutation()
                hooks.before_mutation()
                client.unschedule_workout(external_id)
            except _GARMIN_READ_ERRORS as exc:
                if _http_status(exc) == 404:
                    already_absent = True
                else:
                    try:
                        client.get_scheduled_workout_by_id(external_id)
                    except _GARMIN_READ_ERRORS as read_exc:
                        if _http_status(read_exc) == 404:
                            already_absent = True
                        else:
                            if (
                                _is_rate_limited(exc)
                                or _is_rate_limited(read_exc)
                            ):
                                raise ProviderRateLimitError(
                                    "Garmin API rate limit blocked removal "
                                    "verification"
                                ) from exc
                            if (
                                _is_authentication_rejected(exc)
                                or _is_authentication_rejected(read_exc)
                            ):
                                raise ProviderAuthenticationRequiredError(
                                    "Garmin authentication expired during "
                                    "removal"
                                ) from exc
                            raise ProviderRemovalOutcomeUnknownError(
                                "Garmin removal outcome is uncertain",
                                provider_references=(
                                    hooks.provider_references
                                ),
                            ) from exc
                    else:
                        status = _http_status(exc)
                        if _is_rate_limited(exc):
                            raise ProviderRateLimitError(
                                "Garmin API rate limit rejected the removal"
                            ) from exc
                        if _is_authentication_rejected(exc):
                            raise ProviderAuthenticationRequiredError(
                                "Garmin authentication expired during removal"
                            ) from exc
                        if (
                            status is not None
                            and status < 500
                            and status != 408
                        ):
                            raise ProviderRemovalError(
                                f"Garmin rejected the removal: {exc}"
                            ) from exc
                        raise ProviderRemovalOutcomeUnknownError(
                            "Garmin removal outcome is uncertain",
                            provider_references=hooks.provider_references,
                        ) from exc
        try:
            client.get_scheduled_workout_by_id(external_id)
        except _GARMIN_READ_ERRORS as exc:
            if _http_status(exc) != 404:
                if _is_rate_limited(exc):
                    raise ProviderRateLimitError(
                        "Garmin API rate limit blocked removal verification"
                    ) from exc
                if _is_authentication_rejected(exc):
                    raise ProviderAuthenticationRequiredError(
                        "Garmin authentication expired during removal "
                        "verification"
                    ) from exc
                raise ProviderRemovalOutcomeUnknownError(
                    "Garmin removal could not be verified",
                    provider_references=hooks.provider_references,
                ) from exc
        else:
            raise ProviderRemovalError(
                "Garmin schedule is still present after removal"
            )

        # Templates are intentionally retained. A user may have manually
        # scheduled the Praxys-created template elsewhere; deleting it could
        # mutate an unowned scheduled instance.
        return ProviderRemoveResult(
            already_absent=already_absent,
            response={
                "template_id": template_id,
                "template_retained": True,
                "experimental": True,
            },
        )

    def fetch_calendar(
        self,
        *,
        threshold_value: float | None = None,
        days_ahead: int = 14,
        days_back: int = 0,
        timezone_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch and fingerprint a bounded Garmin calendar snapshot."""
        from api.routes.sync import _garmin_tokenstore_lease

        with _garmin_tokenstore_lease(self._user_id):
            return self._fetch_calendar_locked(
                threshold_value=threshold_value,
                days_ahead=days_ahead,
                days_back=days_back,
                timezone_name=timezone_name,
            )

    def _fetch_calendar_locked(
        self,
        *,
        threshold_value: float | None,
        days_ahead: int,
        days_back: int,
        timezone_name: str | None,
    ) -> list[dict[str, Any]]:
        """Read the calendar while the caller holds the tokenstore lease."""
        del threshold_value, timezone_name
        today = date.today()
        window_start = today - timedelta(days=max(days_back, 0))
        window_end = today + timedelta(days=max(days_ahead, 0))
        client = self._session()
        try:
            rows = fetch_training_plan_api(
                client,
                window_start=window_start,
                window_end=window_end,
            )
            enrich_training_plan_content(client, rows)
            for row in rows:
                assert self._profile_account_id is not None
                row["provider_references"] = {
                    **dict(row.get("provider_references") or {}),
                    "profile_account_id": self._profile_account_id,
                }
            return rows
        except _GARMIN_READ_ERRORS as exc:
            _raise_provider_read_failure(
                "Garmin workout calendar could not be read",
                exc,
            )
