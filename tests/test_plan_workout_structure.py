"""Regression tests for authoritative workout-structure compatibility."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.plan_workout_structure import (
    StructuredWorkoutV1,
    inspect_workout_structure,
    synthesize_v1_structure_from_flat,
)


def _synthesize(**overrides: object) -> StructuredWorkoutV1:
    values: dict[str, object] = {
        "workout_type": "easy",
        "activity_type": "running",
        "planned_duration_min": 30,
        "planned_distance_km": None,
        "target_power_min": None,
        "target_power_max": None,
        "target_hr_min": None,
        "target_hr_max": None,
        "target_pace_min": None,
        "target_pace_max": None,
    }
    values.update(overrides)
    _, version, structure = synthesize_v1_structure_from_flat(**values)
    assert version == "v1"
    return structure


def test_structure_inspection_distinguishes_absent_supported_and_unsafe() -> None:
    absent = inspect_workout_structure(
        workout_structure_version=None,
        workout_structure=None,
    )
    supported = inspect_workout_structure(
        workout_structure_version="v1",
        workout_structure={
            "steps": [{
                "type": "step",
                "phase": "work",
                "termination": {"type": "time", "seconds": 60},
                "target": {
                    "metric": "none",
                    "unit": "none",
                    "reference": "none",
                },
            }],
        },
    )
    mismatched = inspect_workout_structure(
        workout_structure_version="v1",
        workout_structure=None,
    )
    unsupported = inspect_workout_structure(
        workout_structure_version="v2",
        workout_structure={"steps": []},
    )
    invalid = inspect_workout_structure(
        workout_structure_version="v1",
        workout_structure={"steps": [{"type": "step"}]},
    )

    assert absent.state == "absent"
    assert supported.state == "supported"
    assert isinstance(supported.structure, StructuredWorkoutV1)
    assert mismatched.state == "invalid"
    assert unsupported.state == "unsupported"
    assert invalid.state == "invalid"


def test_compatibility_synthesis_returns_a_validated_model() -> None:
    structure = _synthesize(
        planned_duration_min=2.05,
        target_power_min=200,
        target_power_max=240,
    )

    assert isinstance(structure, StructuredWorkoutV1)
    assert structure.steps[0].termination.seconds == 123
    assert structure.steps[0].target.min == 200
    assert structure.steps[0].target.max == 240


@pytest.mark.parametrize(
    "overrides",
    [
        {"planned_duration_min": 0.001},
        {
            "planned_duration_min": None,
            "planned_distance_km": 0.0001,
        },
        {
            "planned_duration_min": 30,
            "planned_distance_km": 5,
        },
        {
            "target_pace_min": "05:00",
            "target_pace_max": "04:00",
        },
        {"target_pace_min": "not-a-pace"},
        {
            "target_power_min": 200,
            "target_hr_min": 150,
        },
    ],
)
def test_compatibility_synthesis_rejects_unrepresentable_flat_values(
    overrides: dict[str, object],
) -> None:
    with pytest.raises((ValueError, ValidationError)):
        _synthesize(**overrides)
