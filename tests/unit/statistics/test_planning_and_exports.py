"""Planning approximation validation and lazy public export behavior."""

from __future__ import annotations

import pytest
from eval_platform_statistics import mean_t_interval
from eval_platform_statistics.planning import (
    minimum_detectable_standardized_effect,
    paired_continuous_sample_size,
    paired_preference_sample_size,
)


def test_lazy_public_statistics_export_loads_on_first_access() -> None:
    result = mean_t_interval([1, 2, 3, 4])
    assert result.method == "student_t"


def test_planning_utilities_return_assumptions_and_inflate_for_ties() -> None:
    continuous = paired_continuous_sample_size(standardized_effect=0.5)
    no_ties = paired_preference_sample_size(win_probability=0.6, tie_rate=0)
    ties = paired_preference_sample_size(win_probability=0.6, tie_rate=0.4)
    assert continuous.sample_size >= 2
    assert continuous.assumptions
    assert ties.sample_size > no_ties.sample_size
    assert minimum_detectable_standardized_effect(sample_size=100) > 0


@pytest.mark.parametrize(
    ("function", "kwargs"),
    [
        (paired_continuous_sample_size, {"standardized_effect": 0}),
        (paired_continuous_sample_size, {"standardized_effect": 0.2, "alpha": 0.7}),
        (paired_continuous_sample_size, {"standardized_effect": 0.2, "power": 0.4}),
        (paired_preference_sample_size, {"win_probability": 0.5}),
        (paired_preference_sample_size, {"win_probability": 0.6, "tie_rate": 1}),
        (minimum_detectable_standardized_effect, {"sample_size": 1}),
    ],
)
def test_planning_rejects_invalid_assumptions(function: object, kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        function(**kwargs)  # type: ignore[operator]
