"""Effect, correction, agreement, ranking, and planning tests."""

from __future__ import annotations

import pytest
from eval_platform_statistics.agreement import (
    krippendorff_alpha_nominal,
    rank_correlations,
    weighted_kappa,
)
from eval_platform_statistics.effects import (
    paired_binary_effects,
    paired_continuous_effects,
    tie_adjusted_win_rate,
)
from eval_platform_statistics.multiplicity import adjust_p_values
from eval_platform_statistics.planning import (
    minimum_detectable_standardized_effect,
    paired_continuous_sample_size,
    paired_preference_sample_size,
)
from eval_platform_statistics.ranking import (
    PairOutcome,
    bradley_terry,
    davidson,
    descriptive_elo,
)


def test_paired_effect_sizes_keep_candidate_orientation() -> None:
    continuous = paired_continuous_effects([1, 2, 3, 4], [2, 2, 4, 6])
    assert continuous.mean_difference == 1
    assert continuous.median_difference == 1
    assert continuous.relative_improvement == pytest.approx(0.4)
    assert continuous.probability_of_superiority == 0.875
    binary = paired_binary_effects(
        [True, True, False, False],
        [True, False, True, True],
    )
    assert binary.absolute_risk_difference == 0.25
    assert binary.discordant_baseline_only == 1
    assert binary.discordant_candidate_only == 2
    assert binary.matched_odds_ratio == 2
    assert tie_adjusted_win_rate(4, 2, 2) == 0.625


def test_multiple_comparison_adjustments_match_hand_example() -> None:
    p_values = {"a": 0.01, "b": 0.04, "c": 0.03}
    assert adjust_p_values(p_values, method="bonferroni") == {
        "a": 0.03,
        "b": 0.12,
        "c": 0.09,
    }
    holm = adjust_p_values(p_values, method="holm")
    assert holm == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})
    bh = adjust_p_values(p_values, method="benjamini-hochberg")
    assert bh == pytest.approx({"a": 0.03, "b": 0.04, "c": 0.04})


def test_rankings_identify_stronger_system_and_model_ties() -> None:
    outcomes = [
        PairOutcome("candidate", "baseline", 18, 2, 5),
        PairOutcome("candidate", "third", 15, 5, 4),
        PairOutcome("baseline", "third", 12, 8, 3),
    ]
    bradley = bradley_terry(outcomes)
    davidson_result = davidson(outcomes)
    assert bradley.converged
    assert davidson_result.converged
    assert bradley.strengths["candidate"] > bradley.strengths["baseline"]
    assert bradley.strengths["baseline"] > bradley.strengths["third"]
    assert sum(bradley.strengths.values()) == pytest.approx(1)
    assert davidson_result.tie_parameter is not None
    assert davidson_result.tie_parameter > 0
    elo = descriptive_elo(outcomes)
    assert elo["candidate"] == max(elo.values())
    assert sum(elo.values()) == pytest.approx(3 * 1500)


def test_agreement_measures_cover_perfect_disagreement_and_missing_raters() -> None:
    assert weighted_kappa([1, 2, 3], [1, 2, 3]) == 1
    assert weighted_kappa([1, 2, 3], [3, 2, 1]) < 0
    alpha = krippendorff_alpha_nominal(
        [["yes", "yes", None], ["no", "no", "no"], ["yes", "no", "yes"]]
    )
    assert alpha is not None
    assert -1 <= alpha <= 1
    correlations = rank_correlations([1, 2, 3, 4], [1, 2, 4, 3])
    assert correlations["spearman_rho"] == pytest.approx(0.8)
    assert correlations["kendall_tau"] == pytest.approx(2 / 3)


def test_planning_utilities_are_monotonic_and_expose_assumptions() -> None:
    small_effect = paired_continuous_sample_size(standardized_effect=0.2)
    large_effect = paired_continuous_sample_size(standardized_effect=0.5)
    assert small_effect.sample_size > large_effect.sample_size
    preference = paired_preference_sample_size(win_probability=0.6, tie_rate=0.2)
    no_ties = paired_preference_sample_size(win_probability=0.6)
    assert preference.sample_size > no_ties.sample_size
    assert preference.assumptions
    assert minimum_detectable_standardized_effect(sample_size=100) < (
        minimum_detectable_standardized_effect(sample_size=25)
    )
