"""Optional deterministic risk summary for a single executing session.

Classification is supplied by the session and is not an authorization receipt.
This module never dispatches agents, starts loops, or grants human authority.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from analysis.agentic_operating_model import (
    AgenticOperatingModel, PolicyRecord, ROOT, load_agentic_operating_model,
)


def _unique(values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError("classification and policy lists must be unique")


class RouteContribution(PolicyRecord):
    """A concern to cover, with no mandatory professional handoff."""

    description: str = Field(min_length=1)
    contexts: list[str]
    independent_review: bool


class TaskRoutingConfig(PolicyRecord):
    """Concern and risk vocabulary shared by both runtime adapters."""

    schema_version: Literal[2]
    routing_version: Literal["praxys-task-routing-v2"]
    primary_objects: dict[str, RouteContribution] = Field(min_length=1)
    impacts: dict[str, RouteContribution] = Field(min_length=1)
    risk_triggers: list[str] = Field(min_length=1)
    authority_triggers: list[str]

    @model_validator(mode="after")
    def validate_policy(self) -> "TaskRoutingConfig":
        """An authority concern must also receive independent review."""
        _unique(self.risk_triggers)
        _unique(self.authority_triggers)
        if not set(self.authority_triggers) <= set(self.risk_triggers):
            raise ValueError("authority triggers must also be risk triggers")
        for contributions, mandatory in (
            (self.primary_objects, (
                "scientific-evidence", "production-state", "production-incident", "agent-system",
            )),
            (self.impacts, (
                "scientific-evidence-or-claim", "production-operation", "incident-response",
                "agent-policy-or-autonomy", "architecture-boundary", "trust-boundary",
            )),
        ):
            for concern in mandatory:
                if concern not in contributions or not contributions[concern].independent_review:
                    raise ValueError(f"independent review is mandatory for {concern}")
        return self


class TaskClassification(PolicyRecord):
    """Facts inferred from user intent, changed paths and causal impact."""

    primary_object: str = Field(min_length=1)
    impacts: list[str] = Field(default_factory=list)
    risk_triggers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_classification(self) -> "TaskClassification":
        _unique(self.impacts)
        _unique(self.risk_triggers)
        return self


class TaskRoute(PolicyRecord):
    """A compact execution summary, never proof of authority or completion."""

    routing_version: str
    classification: TaskClassification
    execution_mode: Literal["single-session", "independent-review"]
    executor_agent: str
    reviewer_agent: str | None
    contexts: list[str]
    authority_checks: list[str]
    route_digest: str


def validate_task_routing_references(
    config: TaskRoutingConfig, model: AgenticOperatingModel, *, root: Path = ROOT,
) -> None:
    """Reject nonexistent context and agent references."""
    for trait in [*config.primary_objects.values(), *config.impacts.values()]:
        if not set(trait.contexts) <= set(model.contexts):
            raise ValueError("unknown domain context")
    for relative in [model.executor_agent, model.reviewer_agent, model.operations_agent, *model.contexts.values()]:
        path = root / relative
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"missing or escaping policy reference: {relative}")


def route_task(
    classification: TaskClassification, *, config: TaskRoutingConfig | None = None,
    model: AgenticOperatingModel | None = None,
) -> TaskRoute:
    """Consolidate concerns into at most one independent review, without approval."""
    config = config or load_task_routing_config()
    model = model or load_agentic_operating_model()
    if classification.primary_object not in config.primary_objects:
        raise ValueError(f"unknown primary object: {classification.primary_object}")
    if not set(classification.impacts) <= set(config.impacts):
        raise ValueError("unknown impacts")
    if not set(classification.risk_triggers) <= set(config.risk_triggers):
        raise ValueError("unknown risk triggers")
    normalized = TaskClassification(
        primary_object=classification.primary_object,
        impacts=[item for item in config.impacts if item in classification.impacts],
        risk_triggers=[item for item in config.risk_triggers if item in classification.risk_triggers],
    )
    traits = [config.primary_objects[normalized.primary_object], *(config.impacts[item] for item in normalized.impacts)]
    review = bool(normalized.risk_triggers) or any(trait.independent_review for trait in traits)
    concerns = {context for trait in traits for context in trait.contexts}
    payload = dict(
        routing_version=config.routing_version,
        classification=normalized.model_dump(),
        execution_mode="independent-review" if review else "single-session",
        executor_agent=model.executor_agent,
        reviewer_agent=model.reviewer_agent if review else None,
        contexts=list(dict.fromkeys(model.contexts[key] for key in model.contexts if key in concerns)),
        authority_checks=[item for item in normalized.risk_triggers if item in config.authority_triggers],
    )
    # Bind policy as well as output; changing the rules invalidates cached summaries.
    subject = {"route": payload, "policy": config.model_dump(), "model": model.model_dump()}
    digest = hashlib.sha256(json.dumps(subject, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return TaskRoute.model_validate({**payload, "route_digest": f"sha256:{digest}"})


def load_task_routing_config(path: str | Path | None = None) -> TaskRoutingConfig:
    """Load policy without dispatch, ledger I/O or persistent admission state."""
    source = Path(path) if path else ROOT / "config/agentic-task-routing.json"
    return TaskRoutingConfig.model_validate(json.loads(source.read_text()))
