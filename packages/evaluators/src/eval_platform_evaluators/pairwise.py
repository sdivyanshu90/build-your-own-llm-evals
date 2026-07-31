"""Deterministic, blinded, balanced pairwise assignment and aggregation."""

from __future__ import annotations

import hashlib
import itertools
import random
import uuid
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

_PAIR_NAMESPACE = uuid.UUID("239c5c52-1436-4bed-8c38-365f31ca19b8")


class Verdict(StrEnum):
    """Allowed pairwise judge outcomes."""

    A = "A"
    B = "B"
    TIE = "tie"
    ABSTAIN = "abstain"


@dataclass(frozen=True, slots=True)
class PairAssignment:
    """One immutable blinded comparison cell."""

    id: uuid.UUID
    design_id: uuid.UUID
    record_key: str
    variant_a_id: str
    variant_b_id: str
    judge_slot: int
    repetition: int
    orientation: int
    order_seed: int
    reverse_of: uuid.UUID | None = None

    def winner_variant(self, verdict: Verdict) -> str | None:
        """Resolve a blinded verdict to a real variant without exposing it to the judge."""

        if verdict is Verdict.A:
            return self.variant_a_id
        if verdict is Verdict.B:
            return self.variant_b_id
        return None


@dataclass(frozen=True, slots=True)
class PairJudgment:
    """Validated judgment linked to one assignment."""

    assignment_id: uuid.UUID
    verdict: Verdict
    confidence: float
    scores: dict[str, float]
    evidence: tuple[str, ...]
    justification: str
    abstention_reason: str | None = None
    judge_id: str = ""
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("judge confidence must be between zero and one")
        if self.verdict is Verdict.ABSTAIN and not self.abstention_reason:
            raise ValueError("abstentions require a reason")
        if self.verdict is not Verdict.ABSTAIN and self.abstention_reason is not None:
            raise ValueError("non-abstentions cannot carry an abstention reason")


@dataclass(frozen=True, slots=True)
class JudgmentAggregate:
    """Aggregate retaining every outcome denominator."""

    verdict: Verdict
    wins_a: int
    wins_b: int
    ties: int
    abstentions: int
    usable_count: int
    total_count: int
    disagreement_rate: float
    mean_confidence: float | None


def balanced_pair_assignments(
    *,
    design_id: uuid.UUID,
    record_keys: list[str],
    variant_ids: list[str],
    judge_slots: int = 1,
    repetitions: int = 1,
    seed: int,
    sample_size: int | None = None,
    reversed_duplicates: bool = False,
) -> tuple[PairAssignment, ...]:
    """Create a reproducible multi-variant design balanced across display positions."""

    if len(set(variant_ids)) != len(variant_ids) or len(variant_ids) < 2:
        raise ValueError("at least two unique variants are required")
    if len(set(record_keys)) != len(record_keys) or not record_keys:
        raise ValueError("record keys must be non-empty and unique")
    if judge_slots < 1 or repetitions < 1:
        raise ValueError("judge slots and repetitions must be positive")
    if not 0 <= seed < (1 << 64):
        raise ValueError("seed must be an unsigned 64-bit integer")

    cells = [
        (record_key, left, right, judge_slot, repetition)
        for record_key in sorted(record_keys)
        for left, right in itertools.combinations(sorted(variant_ids), 2)
        for judge_slot in range(judge_slots)
        for repetition in range(repetitions)
    ]
    generator = random.Random(seed)  # noqa: S311 - deterministic study design, not security
    generator.shuffle(cells)
    if sample_size is not None:
        if not 1 <= sample_size <= len(cells):
            raise ValueError("sample size must be within the available design cells")
        cells = cells[:sample_size]

    assignments: list[PairAssignment] = []
    pair_position_counts: Counter[tuple[str, str, str]] = Counter()
    for index, (record_key, left, right, judge_slot, repetition) in enumerate(cells):
        pair_key = (left, right)
        left_count = pair_position_counts[(left, right, left)]
        right_count = pair_position_counts[(left, right, right)]
        left_a = (
            _stable_bit(seed, record_key, left, right, judge_slot, repetition, index)
            if left_count == right_count
            else left_count < right_count
        )
        variant_a, variant_b = (left, right) if left_a else (right, left)
        pair_position_counts[(*pair_key, variant_a)] += 1
        assignment = _assignment(
            design_id=design_id,
            record_key=record_key,
            variant_a_id=variant_a,
            variant_b_id=variant_b,
            judge_slot=judge_slot,
            repetition=repetition,
            orientation=0,
            order_seed=seed,
            reverse_of=None,
        )
        assignments.append(assignment)
        if reversed_duplicates:
            assignments.append(
                _assignment(
                    design_id=design_id,
                    record_key=record_key,
                    variant_a_id=variant_b,
                    variant_b_id=variant_a,
                    judge_slot=judge_slot,
                    repetition=repetition,
                    orientation=1,
                    order_seed=seed,
                    reverse_of=assignment.id,
                )
            )
    if len({assignment.id for assignment in assignments}) != len(assignments):
        raise RuntimeError("pair assignment identity collision")
    return tuple(assignments)


def aggregate_judgments(judgments: list[PairJudgment]) -> JudgmentAggregate:
    """Aggregate majority outcome without converting abstentions into ties."""

    if not judgments:
        raise ValueError("at least one judgment is required")
    counts = Counter(judgment.verdict for judgment in judgments)
    usable = len(judgments) - counts[Verdict.ABSTAIN]
    candidates = {
        Verdict.A: counts[Verdict.A],
        Verdict.B: counts[Verdict.B],
        Verdict.TIE: counts[Verdict.TIE],
    }
    maximum = max(candidates.values())
    leaders = [verdict for verdict, count in candidates.items() if count == maximum]
    verdict = leaders[0] if len(leaders) == 1 and usable else Verdict.TIE
    agreement = maximum / usable if usable else 0.0
    confidences = [
        judgment.confidence for judgment in judgments if judgment.verdict is not Verdict.ABSTAIN
    ]
    return JudgmentAggregate(
        verdict=verdict,
        wins_a=counts[Verdict.A],
        wins_b=counts[Verdict.B],
        ties=counts[Verdict.TIE],
        abstentions=counts[Verdict.ABSTAIN],
        usable_count=usable,
        total_count=len(judgments),
        disagreement_rate=1 - agreement if usable else 1.0,
        mean_confidence=sum(confidences) / len(confidences) if confidences else None,
    )


def reversed_order_consistency(
    original: PairAssignment,
    original_verdict: Verdict,
    reversed_assignment: PairAssignment,
    reversed_verdict: Verdict,
) -> bool | None:
    """Compare winner identity across a linked reversed-order judgment."""

    if reversed_assignment.reverse_of != original.id:
        raise ValueError("assignments are not a linked reversal")
    if original_verdict in {Verdict.ABSTAIN, Verdict.TIE} or reversed_verdict in {
        Verdict.ABSTAIN,
        Verdict.TIE,
    }:
        return None
    return original.winner_variant(original_verdict) == reversed_assignment.winner_variant(
        reversed_verdict
    )


def position_bias(
    assignments: dict[uuid.UUID, PairAssignment],
    judgments: list[PairJudgment],
) -> dict[str, float | int | bool]:
    """Report how often the displayed A position wins among decisive judgments."""

    wins_a = 0
    wins_b = 0
    for judgment in judgments:
        if judgment.assignment_id not in assignments:
            raise ValueError("judgment references an unknown assignment")
        if judgment.verdict is Verdict.A:
            wins_a += 1
        elif judgment.verdict is Verdict.B:
            wins_b += 1
    decisive = wins_a + wins_b
    rate = wins_a / decisive if decisive else 0.5
    return {
        "a_wins": wins_a,
        "b_wins": wins_b,
        "decisive_count": decisive,
        "a_win_rate": rate,
        "absolute_position_effect": abs(rate - 0.5),
    }


def _assignment(
    *,
    design_id: uuid.UUID,
    record_key: str,
    variant_a_id: str,
    variant_b_id: str,
    judge_slot: int,
    repetition: int,
    orientation: int,
    order_seed: int,
    reverse_of: uuid.UUID | None,
) -> PairAssignment:
    identity = "|".join(
        [
            str(design_id),
            record_key,
            *sorted((variant_a_id, variant_b_id)),
            str(judge_slot),
            str(repetition),
            str(orientation),
        ]
    )
    return PairAssignment(
        id=uuid.uuid5(_PAIR_NAMESPACE, identity),
        design_id=design_id,
        record_key=record_key,
        variant_a_id=variant_a_id,
        variant_b_id=variant_b_id,
        judge_slot=judge_slot,
        repetition=repetition,
        orientation=orientation,
        order_seed=order_seed,
        reverse_of=reverse_of,
    )


def _stable_bit(seed: int, *parts: object) -> bool:
    digest = hashlib.sha256("|".join([str(seed), *(str(part) for part in parts)]).encode()).digest()
    return bool(digest[0] & 1)
