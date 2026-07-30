"""Tests for stable identifiers, money, authorization, and run transitions."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from eval_platform_domain.auth import Action, Principal, ProjectRole, authorize
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.execution import ALLOWED_RUN_TRANSITIONS, EvaluationRun, RunState
from eval_platform_domain.ids import UUID7Generator
from eval_platform_domain.money import Money


def test_uuid7_is_monotonic_during_clock_rollback() -> None:
    clock_values = iter([1_000, 1_000, 999])
    generator = UUID7Generator(
        clock_ms=lambda: next(clock_values),
        random_bits=lambda _: 10,
    )

    values = [generator() for _ in range(3)]

    assert values == sorted(values)
    assert all(value.version == 7 for value in values)
    assert all(value.variant == uuid.RFC_4122 for value in values)
    assert values[0].int >> 80 == 1_000
    assert values[2].int >> 80 == 1_000


def test_money_quantizes_and_rejects_currency_mismatch() -> None:
    value = Money(Decimal("1.1234567890124"), "usd")
    assert value.amount == Decimal("1.123456789012")
    assert value.currency == "USD"
    assert value + Money(Decimal("2")) == Money(Decimal("3.123456789012"))
    with pytest.raises(ValueError, match="currencies"):
        _ = value + Money(Decimal("1"), "EUR")
    with pytest.raises(ValueError, match="non-negative"):
        Money(Decimal("-0.01"))


def test_authorization_hides_cross_project_resources() -> None:
    organization = uuid.uuid4()
    principal = Principal(
        subject="runner",
        organization_id=organization,
        project_id=uuid.uuid4(),
        role=ProjectRole.RUNNER,
    )
    with pytest.raises(DomainError) as captured:
        authorize(
            principal,
            Action.RUN_READ,
            organization_id=organization,
            project_id=uuid.uuid4(),
        )
    assert captured.value.code is ErrorCode.NOT_FOUND


def test_api_key_scopes_restrict_a_role() -> None:
    organization = uuid.uuid4()
    project = uuid.uuid4()
    principal = Principal(
        subject="scoped-admin",
        organization_id=organization,
        project_id=project,
        role=ProjectRole.ADMIN,
        scopes=frozenset({Action.RUN_READ}),
    )
    authorize(
        principal,
        Action.RUN_READ,
        organization_id=organization,
        project_id=project,
    )
    with pytest.raises(DomainError):
        authorize(
            principal,
            Action.DATASET_WRITE,
            organization_id=organization,
            project_id=project,
        )


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (source, target)
        for source in RunState
        for target in RunState
        if target not in ALLOWED_RUN_TRANSITIONS[source]
    ],
)
def test_run_rejects_every_undefined_transition(
    source: RunState,
    target: RunState,
) -> None:
    run = EvaluationRun(uuid.uuid4(), uuid.uuid4(), source, total_tasks=1)
    with pytest.raises(DomainError) as captured:
        run.transition(target)
    assert captured.value.code is ErrorCode.INVALID_STATE_TRANSITION


@pytest.mark.parametrize(
    ("source", "target"),
    [(source, target) for source, targets in ALLOWED_RUN_TRANSITIONS.items() for target in targets],
)
def test_run_accepts_every_defined_transition(source: RunState, target: RunState) -> None:
    run = EvaluationRun(uuid.uuid4(), uuid.uuid4(), source, total_tasks=1)
    run.transition(target)
    assert run.state is target
    assert run.version_stamp == 2
