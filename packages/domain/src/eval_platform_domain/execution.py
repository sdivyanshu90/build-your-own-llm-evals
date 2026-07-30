"""Evaluation execution state, trajectories, and budget invariants."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.money import Money


class RunState(StrEnum):
    """Stable evaluation run states."""

    DRAFT = "draft"
    VALIDATING = "validating"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


TERMINAL_RUN_STATES = frozenset(
    {
        RunState.CANCELLED,
        RunState.COMPLETED,
        RunState.COMPLETED_WITH_ERRORS,
        RunState.FAILED,
    }
)

ALLOWED_RUN_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.DRAFT: frozenset({RunState.VALIDATING}),
    RunState.VALIDATING: frozenset({RunState.DRAFT, RunState.QUEUED}),
    RunState.QUEUED: frozenset({RunState.RUNNING, RunState.CANCELLING, RunState.FAILED}),
    RunState.RUNNING: frozenset(
        {
            RunState.PAUSING,
            RunState.CANCELLING,
            RunState.COMPLETED,
            RunState.COMPLETED_WITH_ERRORS,
            RunState.FAILED,
        }
    ),
    RunState.PAUSING: frozenset({RunState.PAUSED, RunState.CANCELLING}),
    RunState.PAUSED: frozenset({RunState.QUEUED, RunState.CANCELLING}),
    RunState.CANCELLING: frozenset({RunState.CANCELLED}),
    RunState.CANCELLED: frozenset(),
    RunState.COMPLETED: frozenset(),
    RunState.COMPLETED_WITH_ERRORS: frozenset(),
    RunState.FAILED: frozenset(),
}


@dataclass(slots=True)
class EvaluationRun:
    """Run aggregate enforcing lifecycle and counter invariants."""

    id: uuid.UUID
    experiment_id: uuid.UUID
    state: RunState
    total_tasks: int
    succeeded_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    version_stamp: int = 1

    def __post_init__(self) -> None:
        counters = (
            self.total_tasks,
            self.succeeded_tasks,
            self.failed_tasks,
            self.cancelled_tasks,
        )
        if min(counters) < 0:
            raise ValueError("run counters must be non-negative")
        if sum(counters[1:]) > self.total_tasks:
            raise ValueError("settled task counts exceed total tasks")

    def transition(self, target: RunState) -> None:
        """Apply a legal state transition and advance optimistic version."""

        if target not in ALLOWED_RUN_TRANSITIONS[self.state]:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"cannot transition run from {self.state} to {target}",
            )
        self.state = target
        self.version_stamp += 1


class TaskState(StrEnum):
    """Evaluation task lifecycle."""

    PENDING = "pending"
    LEASED = "leased"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureCategory(StrEnum):
    """Stable execution failure taxonomy."""

    CANCELLATION = "cancellation"
    TIMEOUT = "timeout"
    PROVIDER = "provider_error"
    INVALID_OUTPUT = "invalid_output"
    METRIC = "metric_failure"
    JUDGE = "judge_failure"
    INFRASTRUCTURE = "infrastructure_failure"
    BUDGET = "budget_exceeded"


@dataclass(frozen=True, slots=True)
class EvaluationTaskSpec:
    """Natural identity and input of one evaluation attempt stream."""

    id: uuid.UUID
    run_id: uuid.UUID
    record_key: str
    repetition: int
    system_snapshot_id: uuid.UUID
    input_payload: dict[str, Any]
    seed: int


@dataclass(slots=True)
class BudgetLedger:
    """Conservative decimal budget reservation and actual-cost ledger."""

    limit: Money
    reserved: Decimal = Decimal("0")
    actual: Decimal = Decimal("0")

    def reserve(self, estimate: Money) -> None:
        """Reserve estimated cost before external work."""

        self._require_currency(estimate)
        if self.reserved + self.actual + estimate.amount > self.limit.amount:
            raise DomainError(ErrorCode.BUDGET_EXCEEDED, "project run budget would be exceeded")
        self.reserved += estimate.amount

    def reconcile(self, estimate: Money, actual: Money) -> None:
        """Replace one reservation with actual provider cost."""

        self._require_currency(estimate)
        self._require_currency(actual)
        if estimate.amount > self.reserved:
            raise ValueError("cannot reconcile more than the reserved amount")
        self.reserved -= estimate.amount
        self.actual += actual.amount

    def _require_currency(self, value: Money) -> None:
        if value.currency != self.limit.currency:
            raise ValueError("budget currency mismatch")


class TrajectoryStepKind(StrEnum):
    """Typed agent-trajectory events."""

    OBSERVATION = "observation"
    MODEL_DECISION = "model_decision"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE = "state"
    FINAL_OUTPUT = "final_output"


@dataclass(frozen=True, slots=True)
class TrajectoryStep:
    """One ordered trajectory event."""

    index: int
    kind: TrajectoryStepKind
    content: dict[str, Any]
    timestamp_offset_ms: int

    def __post_init__(self) -> None:
        if self.index < 0 or self.timestamp_offset_ms < 0:
            raise ValueError("trajectory indices and offsets must be non-negative")


@dataclass(frozen=True, slots=True)
class AgentTrajectory:
    """Ordered agent observations, decisions, tools, state, and output."""

    steps: tuple[TrajectoryStep, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        indices = [step.index for step in self.steps]
        if indices != list(range(len(indices))):
            raise ValueError("trajectory step indices must be contiguous from zero")
        offsets = [step.timestamp_offset_ms for step in self.steps]
        if offsets != sorted(offsets):
            raise ValueError("trajectory timestamps must be non-decreasing")
