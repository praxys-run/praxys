"""Thin first-party owner routes for post-run DFA α1."""
from typing import Literal
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from api.auth import require_write_access, require_dfa_rights_access
from api import activity_dfa as service
from db.session import get_db


def private(response: Response):
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(prefix="/activities/{activity_id}/dfa-alpha1", tags=["dfa-alpha1"], dependencies=[Depends(private)])


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Input(StrictBody):
    provider: Literal["garmin"]
    snapshot_id: str = Field(min_length=1, max_length=36)
    parse_id: str = Field(min_length=1, max_length=36)


class Submit(StrictBody):
    input: Input
    catalog_revision: str = Field(min_length=64, max_length=64)
    source_confirmation_id: str | None = Field(None, max_length=36)


class Confirmation(StrictBody):
    run_id: str = Field(min_length=1, max_length=36)
    sensor_ref: str = Field(min_length=32, max_length=32)
    evidence_digest: str = Field(min_length=64, max_length=64)
    statement_version: Literal["dfa-source-attestation-v1"]
    confirmed: Literal[True]

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_boolean(cls, value):
        if value is not True:
            raise ValueError("An explicit true source confirmation is required")
        return value


class Retry(StrictBody):
    expected_generation: int = Field(ge=1)


@router.get("")
def catalog(activity_id: str, user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return service.catalog(db, user_id, activity_id)


@router.post("")
def submit(activity_id: str, body: Submit, response: Response,
           user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    result, response.status_code = service.submit(db, user_id, activity_id, body.input.model_dump(), body.catalog_revision, body.source_confirmation_id)
    return result


@router.get("/runs/{run_id}")
def run(activity_id: str, run_id: str, offset: int = Query(0, ge=0), limit: int = Query(120, ge=1, le=1000),
        user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return service.read_run(db, user_id, activity_id, run_id, offset, limit)


@router.post("/source-confirmations")
def confirm(activity_id: str, body: Confirmation, user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return service.confirm(db, user_id, activity_id, body.model_dump())


@router.get("/runs/{run_id}/context")
def context(activity_id: str, run_id: str, result_revision: str, expected_samples_revision: str | None = None,
            offset: int = Query(0, ge=0), limit: int = Query(120, ge=1, le=1000),
            user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return service.context(db, user_id, activity_id, run_id, offset, limit, result_revision, expected_samples_revision)


@router.post("/runs/{run_id}/retry")
def retry(activity_id: str, run_id: str, body: Retry, user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return service.change_run(db, user_id, activity_id, run_id, "retry", body.expected_generation)


@router.post("/runs/{run_id}/cancel")
def cancel(activity_id: str, run_id: str, user_id: str = Depends(require_dfa_rights_access), db: Session = Depends(get_db)):
    return service.change_run(db, user_id, activity_id, run_id, "cancel")


@router.delete("/source-confirmations/{confirmation_id}")
def revoke(activity_id: str, confirmation_id: str, user_id: str = Depends(require_dfa_rights_access), db: Session = Depends(get_db)):
    return service.erase(db, user_id, activity_id, confirmation_id)


@router.delete("")
def erase(activity_id: str, user_id: str = Depends(require_dfa_rights_access), db: Session = Depends(get_db)):
    return service.erase(db, user_id, activity_id)
