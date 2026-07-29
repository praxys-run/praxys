"""Stryd implementation of the provider-neutral delivery contract."""
from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

import requests

from api.plan_delivery.base import (
    ProviderAuthenticationError,
    ProviderCreateResult,
    ProviderOutcomeUnknownError,
    PreparedWorkoutDelivery,
    ProviderReadError,
    ProviderRejectedError,
    ProviderRemoveResult,
    ProviderRemovalError,
    ProviderRequestError,
)
from db.plan_ledger import normalize_stryd_workout_id
from sync import stryd_sync


class StrydPlanDeliveryAdapter:
    """Create, remove, and read Stryd workouts for one user's credentials."""

    target = "stryd"
    display_name = "Stryd"

    def __init__(self, credentials: Mapping[str, Any]):
        email = credentials.get("email")
        password = credentials.get("password")
        if not isinstance(email, str) or not email.strip():
            raise ProviderAuthenticationError(
                "Stryd credentials are missing an email"
            )
        if not isinstance(password, str) or not password:
            raise ProviderAuthenticationError(
                "Stryd credentials are missing a password"
            )
        self._email = email.strip()
        self._password = password
        self._provider_user_id: str | None = None
        self._token: str | None = None

    @property
    def account_id(self) -> str:
        """Return the authenticated Stryd account identity."""
        self.authenticate()
        assert self._provider_user_id is not None
        return self._provider_user_id

    def authenticate(self) -> None:
        """Authenticate once for all operations performed by this adapter."""
        if self._provider_user_id and self._token:
            return
        try:
            provider_user_id, token = stryd_sync._login_api(
                self._email,
                self._password,
            )
        except (
            requests.RequestException,
            KeyError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            raise ProviderAuthenticationError("Stryd login failed") from exc
        if not provider_user_id or not token:
            raise ProviderAuthenticationError(
                "Stryd login did not return a usable session"
            )
        self._provider_user_id = str(provider_user_id)
        self._token = str(token)

    def _session(self) -> tuple[str, str]:
        self.authenticate()
        assert self._provider_user_id is not None
        assert self._token is not None
        return self._provider_user_id, self._token

    @staticmethod
    def _http_detail(error: requests.HTTPError) -> str:
        detail = str(error)
        if error.response is not None:
            try:
                body = error.response.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and body.get("message"):
                detail = str(body["message"])
        return detail

    @staticmethod
    def _prepare_workout(
        workout: Mapping[str, Any],
        threshold_value: float,
    ) -> dict[str, Any]:
        try:
            raw_blocks = stryd_sync.build_workout_blocks(
                dict(workout),
                threshold_value,
            )
            blocks_without_ids = StrydPlanDeliveryAdapter._without_uuids(
                raw_blocks
            )
            block_seed = json.dumps(
                blocks_without_ids,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
            blocks = StrydPlanDeliveryAdapter._stable_uuids(
                raw_blocks,
                seed=block_seed,
            )
            workout_type = str(workout.get("workout_type") or "")
            provider_type = stryd_sync._STRYD_WORKOUT_TYPES.get(
                workout_type.casefold(),
                "",
            )
            return {
                "workout_date": str(workout["date"]),
                "title": workout_type.replace("_", " ").title(),
                "blocks": blocks,
                "workout_type": provider_type,
                "description": str(
                    workout.get("workout_description") or ""
                ),
            }
        except (ArithmeticError, KeyError, TypeError, ValueError) as exc:
            raise ProviderRequestError(str(exc)) from exc

    @staticmethod
    def _without_uuids(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): StrydPlanDeliveryAdapter._without_uuids(item)
                for key, item in value.items()
                if key != "uuid"
            }
        if isinstance(value, list):
            return [
                StrydPlanDeliveryAdapter._without_uuids(item)
                for item in value
            ]
        return value

    @staticmethod
    def _stable_uuids(
        value: Any,
        *,
        seed: str,
        path: str = "$",
    ) -> Any:
        if isinstance(value, Mapping):
            result = {
                str(key): StrydPlanDeliveryAdapter._stable_uuids(
                    item,
                    seed=seed,
                    path=f"{path}.{key}",
                )
                for key, item in value.items()
                if key != "uuid"
            }
            if "uuid" in value:
                result["uuid"] = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"praxys-stryd:{seed}:{path}",
                    )
                )
            return result
        if isinstance(value, list):
            return [
                StrydPlanDeliveryAdapter._stable_uuids(
                    item,
                    seed=seed,
                    path=f"{path}[{index}]",
                )
                for index, item in enumerate(value)
            ]
        return value

    def prepare_workout(
        self,
        workout: Mapping[str, Any],
        *,
        threshold_value: float,
    ) -> PreparedWorkoutDelivery:
        """Prepare and hash one deterministic Stryd create request."""
        payload = self._prepare_workout(workout, threshold_value)
        try:
            version = stryd_sync.stryd_delivery_payload_fingerprint(payload)
            content_version = (
                stryd_sync.stryd_delivery_content_fingerprint(payload)
            )
        except (TypeError, ValueError) as exc:
            raise ProviderRequestError(str(exc)) from exc
        return PreparedWorkoutDelivery(
            version=version,
            request=payload,
            content_version=content_version,
        )

    def create_workout(
        self,
        prepared: PreparedWorkoutDelivery,
    ) -> ProviderCreateResult:
        """Create a structured Stryd workout."""
        provider_user_id, token = self._session()

        try:
            response = stryd_sync.create_workout_api(
                user_id=provider_user_id,
                token=token,
                **prepared.request,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise ProviderOutcomeUnknownError(str(exc)) from exc
        except requests.HTTPError as exc:
            status_code = (
                exc.response.status_code if exc.response is not None else None
            )
            detail = self._http_detail(exc)
            if status_code is None or status_code == 408 or status_code >= 500:
                raise ProviderOutcomeUnknownError(detail) from exc
            raise ProviderRejectedError(f"Stryd API error: {detail}") from exc
        except requests.RequestException as exc:
            raise ProviderOutcomeUnknownError(str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise ProviderOutcomeUnknownError(str(exc)) from exc

        if not isinstance(response, Mapping):
            raise ProviderOutcomeUnknownError(
                "Stryd response was not an object"
            )
        external_id = normalize_stryd_workout_id(response.get("id"))
        if external_id is None:
            raise ProviderOutcomeUnknownError(
                "Stryd response did not include a workout id"
            )
        return ProviderCreateResult(
            external_id=external_id,
            provider_account_id=provider_user_id,
            response=dict(response),
        )

    def delete_workout(self, external_id: str) -> ProviderRemoveResult:
        """Delete a Stryd workout, treating an existing 404 as success."""
        provider_user_id, token = self._session()
        try:
            stryd_sync.delete_workout_api(
                provider_user_id,
                token,
                external_id,
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return ProviderRemoveResult(already_absent=True)
            raise ProviderRemovalError(str(exc)) from exc
        except requests.RequestException as exc:
            raise ProviderRemovalError(str(exc)) from exc
        return ProviderRemoveResult()

    def fetch_calendar(
        self,
        *,
        threshold_value: float | None = None,
        days_ahead: int = 14,
        days_back: int = 0,
        timezone_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch normalized Stryd calendar workouts."""
        provider_user_id, token = self._session()
        try:
            return stryd_sync.fetch_training_plan_api(
                provider_user_id,
                token,
                cp_watts=threshold_value,
                days_ahead=days_ahead,
                days_back=days_back,
                tz_name=timezone_name,
            )
        except (
            requests.RequestException,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            raise ProviderReadError(str(exc)) from exc
