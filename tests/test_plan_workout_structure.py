"""Regression tests for authoritative workout-structure compatibility."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.plan_workout_structure import (
    WORKOUT_INSTRUCTIONS_MAX_LENGTH,
    WORKOUT_LABEL_MAX_LENGTH,
    StructuredWorkoutV1,
    inspect_workout_structure,
    project_workout_provider_compatibility,
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


def test_user_wording_is_trimmed_once_and_blank_wording_is_absent() -> None:
    structure = StructuredWorkoutV1.model_validate({
        "steps": [
            {
                "type": "step",
                "phase": "rest",
                "label": "  Float recovery  ",
                "instructions": "  Keep the cadence light; do not surge.  ",
                "termination": {"type": "time", "seconds": 60},
                "target": {
                    "metric": "none",
                    "unit": "none",
                    "reference": "none",
                },
            },
            {
                "type": "repeat",
                "label": "  Main set  ",
                "repetitions": 2,
                "steps": [
                    {
                        "type": "step",
                        "phase": "work",
                        "label": "\t",
                        "instructions": "\n ",
                        "termination": {"type": "time", "seconds": 30},
                        "target": {
                            "metric": "none",
                            "unit": "none",
                            "reference": "none",
                        },
                    }
                ],
            },
        ]
    })

    normalized = structure.model_dump(mode="json", exclude_none=True)
    assert normalized["steps"][0]["label"] == "Float recovery"
    assert normalized["steps"][0]["instructions"] == (
        "Keep the cadence light; do not surge."
    )
    assert normalized["steps"][1]["label"] == "Main set"
    assert "label" not in normalized["steps"][1]["steps"][0]
    assert "instructions" not in normalized["steps"][1]["steps"][0]


@pytest.mark.parametrize(
    ("field", "limit"),
    [
        ("label", WORKOUT_LABEL_MAX_LENGTH),
        ("instructions", WORKOUT_INSTRUCTIONS_MAX_LENGTH),
    ],
)
def test_step_wording_limits_reject_instead_of_truncating(
    field: str,
    limit: int,
) -> None:
    step = {
        "type": "step",
        "phase": "work",
        field: "界" * (limit + 1),
        "termination": {"type": "time", "seconds": 60},
        "target": {
            "metric": "none",
            "unit": "none",
            "reference": "none",
        },
    }

    with pytest.raises(ValidationError) as error:
        StructuredWorkoutV1.model_validate({"steps": [step]})

    assert any(
        item["type"] == "string_too_long"
        for item in error.value.errors(include_input=False)
    )


def test_repeat_label_limit_rejects_instead_of_truncating() -> None:
    with pytest.raises(ValidationError) as error:
        StructuredWorkoutV1.model_validate({
            "steps": [{
                "type": "repeat",
                "label": "M" * (WORKOUT_LABEL_MAX_LENGTH + 1),
                "repetitions": 2,
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
            }],
        })

    assert any(
        item["type"] == "string_too_long"
        for item in error.value.errors(include_input=False)
    )


def test_provider_compatibility_names_lossy_structured_details() -> None:
    """Provider previews must explain loss rather than flattening a tree."""
    structure = StructuredWorkoutV1.model_validate({
        "steps": [{
            "type": "repeat",
            "label": "Main hill set",
            "repetitions": 2,
            "steps": [{
                "type": "step",
                "phase": "rest",
                "label": "Reset",
                "instructions": "Walk until breathing settles.",
                "termination": {"type": "manual"},
                "target": {
                    "metric": "rpe",
                    "unit": "scale_10",
                    "reference": "perceived_exertion",
                    "min": 3,
                },
            }],
        }],
    })

    compatibility = project_workout_provider_compatibility(
        activity_type="trail_running",
        workout_structure_version="v1",
        workout_structure=structure,
        planned_duration_min=None,
        planned_distance_km=None,
        target_power_min=None,
        target_power_max=None,
        target_hr_min=None,
        target_hr_max=None,
        target_pace_min=None,
        target_pace_max=None,
    )
    by_target = {item["target"]: item for item in compatibility}

    assert by_target["garmin"]["compatible"] is False
    assert {
        reason["code"] for reason in by_target["garmin"]["reasons"]
    } >= {
        "structured_workout_not_supported",
        "activity_type_not_supported",
    }
    assert by_target["stryd"]["compatible"] is False
    assert {
        reason["code"] for reason in by_target["stryd"]["reasons"]
    } == {
        "wording_not_supported",
        "termination_not_supported",
        "target_not_supported",
    }


def test_provider_compatibility_rejects_lossy_flat_stryd_defaults() -> None:
    """Flat HR/no-duration rows must not preview as safe Stryd delivery."""
    compatibility = project_workout_provider_compatibility(
        activity_type="running",
        workout_structure_version=None,
        workout_structure=None,
        planned_duration_min=None,
        planned_distance_km=None,
        target_power_min=None,
        target_power_max=None,
        target_hr_min=140,
        target_hr_max=150,
        target_pace_min=None,
        target_pace_max=None,
    )
    stryd = next(item for item in compatibility if item["target"] == "stryd")

    assert stryd["compatible"] is False
    assert {
        reason["code"] for reason in stryd["reasons"]
    } >= {"duration_required", "target_not_supported"}


def test_provider_compatibility_rejects_subsecond_flat_durations() -> None:
    """A preview must reject durations that adapters round down to zero."""
    compatibility = project_workout_provider_compatibility(
        activity_type="running",
        workout_structure_version=None,
        workout_structure=None,
        planned_duration_min=0.001,
        planned_distance_km=None,
        target_power_min=200,
        target_power_max=220,
        target_hr_min=None,
        target_hr_max=None,
        target_pace_min=None,
        target_pace_max=None,
    )

    for provider in compatibility:
        assert provider["compatible"] is False
        assert "duration_required" in {
            reason["code"] for reason in provider["reasons"]
        }


def test_stryd_compatibility_rejects_one_sided_structured_targets() -> None:
    """Stryd cannot preserve whether a single bound is a floor or ceiling."""
    structure = StructuredWorkoutV1.model_validate({
        "steps": [{
            "type": "step",
            "phase": "work",
            "termination": {"type": "time", "seconds": 180},
            "target": {
                "metric": "power",
                "unit": "percent_cp",
                "reference": "critical_power",
                "min": 95,
            },
        }],
    })

    compatibility = project_workout_provider_compatibility(
        activity_type="running",
        workout_structure_version="v1",
        workout_structure=structure,
        planned_duration_min=3,
        planned_distance_km=None,
        target_power_min=None,
        target_power_max=None,
        target_hr_min=None,
        target_hr_max=None,
        target_pace_min=None,
        target_pace_max=None,
    )
    stryd = next(item for item in compatibility if item["target"] == "stryd")

    assert stryd["compatible"] is False
    assert stryd["reasons"] == [{
        "code": "target_not_supported",
        "path": "steps[0].target",
    }]


def _stryd_percent_cp_compatibility(
    minimum: float,
    maximum: float,
) -> dict[str, object]:
    structure = StructuredWorkoutV1.model_validate({
        "steps": [{
            "type": "step",
            "phase": "work",
            "termination": {"type": "time", "seconds": 180},
            "target": {
                "metric": "power",
                "unit": "percent_cp",
                "reference": "critical_power",
                "min": minimum,
                "max": maximum,
            },
        }],
    })
    compatibility = project_workout_provider_compatibility(
        activity_type="running",
        workout_structure_version="v1",
        workout_structure=structure,
        planned_duration_min=3,
        planned_distance_km=None,
        target_power_min=None,
        target_power_max=None,
        target_hr_min=None,
        target_hr_max=None,
        target_pace_min=None,
        target_pace_max=None,
    )
    return next(item for item in compatibility if item["target"] == "stryd")


def test_stryd_compatibility_accepts_percent_cp_bounds() -> None:
    """PowerCenter accepts complete percentage ranges."""
    stryd = _stryd_percent_cp_compatibility(95, 96)

    assert stryd == {
        "target": "stryd",
        "compatible": True,
        "mode": "structured",
        "reasons": [],
    }


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        (95.5, 96.5),
        (95.4, 95.49),
    ],
)
def test_stryd_compatibility_accepts_fractional_percent_cp_bounds(
    minimum: float,
    maximum: float,
) -> None:
    """PowerCenter numeric inputs preserve fractional percentage ranges."""
    stryd = _stryd_percent_cp_compatibility(minimum, maximum)

    assert stryd == {
        "target": "stryd",
        "compatible": True,
        "mode": "structured",
        "reasons": [],
    }


def test_stryd_reports_the_first_unsupported_target_path() -> None:
    """A later unsupported target does not replace the first actionable path."""
    structure = StructuredWorkoutV1.model_validate({
        "steps": [
            {
                "type": "step",
                "phase": "work",
                "termination": {"type": "time", "seconds": 60},
                "target": {
                    "metric": "heart_rate",
                    "unit": "bpm",
                    "reference": "absolute",
                    "min": 150,
                    "max": 160,
                },
            },
            {
                "type": "step",
                "phase": "work",
                "termination": {"type": "time", "seconds": 60},
                "target": {
                    "metric": "power",
                    "unit": "percent_cp",
                    "reference": "critical_power",
                    "min": 95,
                },
            },
        ],
    })
    compatibility = project_workout_provider_compatibility(
        activity_type="running",
        workout_structure_version="v1",
        workout_structure=structure,
        planned_duration_min=2,
        planned_distance_km=None,
        target_power_min=None,
        target_power_max=None,
        target_hr_min=None,
        target_hr_max=None,
        target_pace_min=None,
        target_pace_max=None,
    )
    stryd = next(item for item in compatibility if item["target"] == "stryd")

    assert stryd["reasons"] == [{
        "code": "target_not_supported",
        "path": "steps[0].target",
    }]


def test_stryd_compatibility_matches_current_powercenter_builder() -> None:
    """Distance, Rest, and no-target steps are valid PowerCenter structures."""
    structure = StructuredWorkoutV1.model_validate({
        "steps": [
            {
                "type": "step",
                "phase": "warmup",
                "termination": {"type": "time", "seconds": 600},
                "target": {
                    "metric": "power",
                    "unit": "percent_cp",
                    "reference": "critical_power",
                    "min": 60,
                    "max": 80,
                },
            },
            {
                "type": "repeat",
                "repetitions": 6,
                "steps": [
                    {
                        "type": "step",
                        "phase": "work",
                        "termination": {
                            "type": "distance",
                            "meters": 1000,
                        },
                        "target": {
                            "metric": "power",
                            "unit": "percent_cp",
                            "reference": "critical_power",
                            "min": 100,
                            "max": 120,
                        },
                    },
                    {
                        "type": "step",
                        "phase": "rest",
                        "termination": {"type": "time", "seconds": 120},
                        "target": {
                            "metric": "none",
                            "unit": "none",
                            "reference": "none",
                        },
                    },
                ],
            },
            {
                "type": "step",
                "phase": "cooldown",
                "termination": {"type": "open"},
                "target": {
                    "metric": "heart_rate",
                    "unit": "bpm",
                    "reference": "absolute",
                    "min": 130,
                    "max": 150,
                },
            },
        ],
    })

    compatibility = project_workout_provider_compatibility(
        activity_type="running",
        workout_structure_version="v1",
        workout_structure=structure,
        planned_duration_min=None,
        planned_distance_km=None,
        target_power_min=None,
        target_power_max=None,
        target_hr_min=None,
        target_hr_max=None,
        target_pace_min=None,
        target_pace_max=None,
    )
    stryd = next(item for item in compatibility if item["target"] == "stryd")

    assert stryd["reasons"] == [
        {
            "code": "termination_not_supported",
            "path": "steps[2].termination",
        },
        {
            "code": "target_not_supported",
            "path": "steps[2].target",
        },
    ]


def test_stryd_compatibility_accepts_one_exact_rpe() -> None:
    structure = StructuredWorkoutV1.model_validate({
        "steps": [{
            "type": "step",
            "phase": "work",
            "termination": {"type": "time", "seconds": 180},
            "target": {
                "metric": "rpe",
                "unit": "scale_10",
                "reference": "perceived_exertion",
                "min": 7,
                "max": 7,
            },
        }],
    })

    compatibility = project_workout_provider_compatibility(
        activity_type="running",
        workout_structure_version="v1",
        workout_structure=structure,
        planned_duration_min=3,
        planned_distance_km=None,
        target_power_min=None,
        target_power_max=None,
        target_hr_min=None,
        target_hr_max=None,
        target_pace_min=None,
        target_pace_max=None,
    )
    stryd = next(item for item in compatibility if item["target"] == "stryd")

    assert stryd["compatible"] is True
    assert stryd["reasons"] == []


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
