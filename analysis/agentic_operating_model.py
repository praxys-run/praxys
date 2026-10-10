"""Small shared execution policy; domain knowledge is context, not an agent graph."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[1]


class PolicyRecord(BaseModel):
    """Reject unknown fields and ambiguous scalar coercion."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class IndependencePolicy(PolicyRecord):
    """The executor cannot supply its own independent review."""

    high_risk_review_required: Literal[True]
    reviewer_read_only: Literal[True]
    reviewer_fresh_context: Literal[True]


class AgenticOperatingModel(PolicyRecord):
    """One executor, one optional reviewer, and an isolated operations adapter."""

    schema_version: Literal[2]
    model_version: Literal["praxys-single-session-v2"]
    status: Literal["active"]
    workflow: list[str]
    executor_agent: str
    reviewer_agent: str
    operations_agent: str
    contexts: dict[str, str] = Field(min_length=1)
    record_fields: list[str] = Field(min_length=1)
    independence: IndependencePolicy
    native_capabilities: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_model(self) -> "AgenticOperatingModel":
        """Keep identities distinct and all context references inside the repo."""
        if self.workflow != ["understand", "implement", "verify"]:
            raise ValueError("workflow must be understand, implement, verify")
        agents = [self.executor_agent, self.reviewer_agent, self.operations_agent]
        if len(set(agents)) != 3:
            raise ValueError("executor, reviewer and operations must be distinct")
        for value in [*agents, *self.contexts.values()]:
            path = Path(value)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("policy paths must be repository-relative")
        return self


def load_agentic_operating_model(path: str | Path | None = None) -> AgenticOperatingModel:
    """Load the active policy without retaining stale policy across edits."""
    source = Path(path) if path else ROOT / "config/agentic-operating-model.json"
    return AgenticOperatingModel.model_validate(json.loads(source.read_text()))
