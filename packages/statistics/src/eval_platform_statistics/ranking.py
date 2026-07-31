"""Batch Bradley-Terry/Davidson rankings and explicitly descriptive Elo ratings."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from eval_platform_statistics.models import AnalysisWarning, WarningCode


@dataclass(frozen=True, slots=True)
class PairOutcome:
    """Aggregated outcomes for one unordered item pair."""

    item_a: str
    item_b: str
    wins_a: int
    wins_b: int
    ties: int = 0

    def __post_init__(self) -> None:
        if self.item_a == self.item_b:
            raise ValueError("pair items must differ")
        if min(self.wins_a, self.wins_b, self.ties) < 0:
            raise ValueError("outcome counts cannot be negative")
        if self.wins_a + self.wins_b + self.ties == 0:
            raise ValueError("an outcome must contain at least one judgment")


@dataclass(frozen=True, slots=True)
class RankingResult:
    """Identifiable centered log abilities and normalized strengths."""

    method: str
    log_abilities: dict[str, float]
    strengths: dict[str, float]
    tie_parameter: float | None
    converged: bool
    outcome_count: int
    warnings: tuple[AnalysisWarning, ...]


def bradley_terry(outcomes: Sequence[PairOutcome]) -> RankingResult:
    """Maximum-likelihood Bradley-Terry fit; explicit ties are excluded."""

    items, encoded = _encode(outcomes)
    warnings: list[AnalysisWarning] = []
    tie_count = sum(outcome.ties for outcome in outcomes)
    if tie_count:
        warnings.append(
            AnalysisWarning(
                WarningCode.ASSUMPTION_VIOLATION,
                f"{tie_count} ties were excluded by the Bradley-Terry likelihood",
            )
        )

    def objective(parameters: np.ndarray) -> float:
        abilities = np.append(parameters, -float(np.sum(parameters)))
        loss = 0.0
        for left, right, wins_left, wins_right, _ties in encoded:
            difference = abilities[left] - abilities[right]
            loss += wins_left * np.logaddexp(0, -difference)
            loss += wins_right * np.logaddexp(0, difference)
        return float(loss + 1e-8 * np.sum(abilities * abilities))

    result = minimize(
        objective,
        np.zeros(len(items) - 1, dtype=np.float64),
        method="BFGS",
        options={"gtol": 1e-10, "maxiter": 10_000},
    )
    abilities = np.append(result.x, -float(np.sum(result.x)))
    return _ranking(
        "bradley_terry",
        items,
        abilities,
        None,
        bool(result.success or np.linalg.norm(result.jac) < 1e-5),
        sum(outcome.wins_a + outcome.wins_b for outcome in outcomes),
        warnings,
    )


def davidson(outcomes: Sequence[PairOutcome]) -> RankingResult:
    """Davidson extension with a non-negative global tie propensity."""

    items, encoded = _encode(outcomes)

    def objective(parameters: np.ndarray) -> float:
        abilities = np.append(parameters[:-1], -float(np.sum(parameters[:-1])))
        tie_parameter = math.exp(float(parameters[-1]))
        loss = 0.0
        for left, right, wins_left, wins_right, ties in encoded:
            left_strength = math.exp(float(np.clip(abilities[left], -30, 30)))
            right_strength = math.exp(float(np.clip(abilities[right], -30, 30)))
            tie_strength = tie_parameter * math.sqrt(left_strength * right_strength)
            denominator = left_strength + right_strength + tie_strength
            loss -= wins_left * math.log(left_strength / denominator)
            loss -= wins_right * math.log(right_strength / denominator)
            if ties:
                loss -= ties * math.log(tie_strength / denominator)
        return loss + 1e-8 * float(np.sum(abilities * abilities))

    initial = np.zeros(len(items), dtype=np.float64)
    result = minimize(
        objective,
        initial,
        method="BFGS",
        options={"gtol": 1e-9, "maxiter": 10_000},
    )
    abilities = np.append(result.x[:-1], -float(np.sum(result.x[:-1])))
    tie_parameter = math.exp(float(result.x[-1]))
    return _ranking(
        "davidson",
        items,
        abilities,
        tie_parameter,
        bool(result.success or np.linalg.norm(result.jac) < 1e-5),
        sum(outcome.wins_a + outcome.wins_b + outcome.ties for outcome in outcomes),
        [],
    )


def descriptive_elo(
    outcomes: Sequence[PairOutcome],
    *,
    initial_rating: float = 1500,
    k_factor: float = 32,
) -> dict[str, float]:
    """Return order-dependent Elo as a descriptive view, not an inferential model."""

    if k_factor <= 0:
        raise ValueError("Elo k-factor must be positive")
    items, _encoded = _encode(outcomes)
    ratings = {item: float(initial_rating) for item in items}
    for outcome in outcomes:
        events = (
            [
                (1.0, 0.0),
            ]
            * outcome.wins_a
            + [(0.0, 1.0)] * outcome.wins_b
            + [(0.5, 0.5)] * outcome.ties
        )
        for score_a, score_b in events:
            expected_a = 1 / (1 + 10 ** ((ratings[outcome.item_b] - ratings[outcome.item_a]) / 400))
            change = k_factor * (score_a - expected_a)
            ratings[outcome.item_a] += change
            ratings[outcome.item_b] -= change
            if not math.isclose(score_a + score_b, 1):
                raise RuntimeError("invalid Elo event")
    return ratings


def _encode(
    outcomes: Sequence[PairOutcome],
) -> tuple[list[str], list[tuple[int, int, int, int, int]]]:
    if not outcomes:
        raise ValueError("at least one pair outcome is required")
    items = sorted({item for outcome in outcomes for item in (outcome.item_a, outcome.item_b)})
    if len(items) < 2:
        raise ValueError("at least two items are required")
    positions = {item: index for index, item in enumerate(items)}
    encoded = [
        (
            positions[outcome.item_a],
            positions[outcome.item_b],
            outcome.wins_a,
            outcome.wins_b,
            outcome.ties,
        )
        for outcome in outcomes
    ]
    return items, encoded


def _ranking(
    method: str,
    items: Sequence[str],
    abilities: np.ndarray,
    tie_parameter: float | None,
    converged: bool,
    count: int,
    warnings: Sequence[AnalysisWarning],
) -> RankingResult:
    strengths_array = np.exp(abilities - np.max(abilities))
    strengths_array /= np.sum(strengths_array)
    return RankingResult(
        method=method,
        log_abilities={
            item: float(ability) for item, ability in zip(items, abilities, strict=True)
        },
        strengths={
            item: float(strength) for item, strength in zip(items, strengths_array, strict=True)
        },
        tie_parameter=tie_parameter,
        converged=converged,
        outcome_count=count,
        warnings=tuple(warnings),
    )
