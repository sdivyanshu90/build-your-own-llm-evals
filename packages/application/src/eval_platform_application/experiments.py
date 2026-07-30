"""Immutable experiment and run orchestration use cases."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from eval_platform_domain.auth import Action, Principal, authorize
from eval_platform_domain.canonicalization import canonical_bytes
from eval_platform_domain.datasets import DatasetVersion
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.execution import EvaluationRun, EvaluationTaskSpec, RunState
from eval_platform_domain.ids import new_uuid7
from eval_platform_domain.money import Money

_SECRET_FIELDS = frozenset(
    {"api_key", "secret", "password", "authorization", "access_token", "refresh_token"}
)


@dataclass(frozen=True, slots=True)
class SystemSnapshot:
    """Secret-free immutable system-under-test configuration."""

    id: uuid.UUID
    provider: dict[str, Any]
    model: str
    prompt_template: str
    parameters: dict[str, Any]
    content_hash: str


@dataclass(frozen=True, slots=True)
class Experiment:
    """Resolved immutable evaluation experiment."""

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    dataset_version_id: uuid.UUID
    system_snapshot: SystemSnapshot
    suite: dict[str, Any]
    seed: int
    config_hash: str
    application_version: str
    dependency_lock_hash: str


@dataclass(frozen=True, slots=True)
class RunCreation:
    """Run and its bounded natural-key task set."""

    run: EvaluationRun
    tasks: tuple[EvaluationTaskSpec, ...]
    budget_limit: Money


@dataclass(frozen=True, slots=True)
class MetricOutcome:
    """Persistence-neutral metric result or isolated failure."""

    identifier: str
    version: str
    status: str
    scalar: float | None = None
    label: str | None = None
    structured: dict[str, Any] | None = None
    explanation: str | None = None
    metadata: dict[str, Any] | None = None
    error: str | None = None


class ExperimentRepository(Protocol):
    """Persistence required for experiment and run creation."""

    async def get_dataset_version(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> DatasetVersion | None:
        """Resolve a published dataset version."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def add_experiment(self, experiment: Experiment) -> None:
        """Persist an immutable experiment and snapshot."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def add_run(self, creation: RunCreation) -> None:
        """Persist a queued run, tasks, state events, and outbox event."""

        raise TypeError("protocol declaration has no runtime implementation")


class ExperimentService:
    """Create fully resolved experiments and bounded runs."""

    def __init__(self, repository: ExperimentRepository) -> None:
        self._repository = repository

    async def create_experiment(
        self,
        principal: Principal,
        *,
        project_id: uuid.UUID,
        dataset_version_id: uuid.UUID,
        provider: dict[str, Any],
        model: str,
        prompt_template: str,
        parameters: dict[str, Any],
        suite: dict[str, Any],
        seed: int,
        application_version: str,
        dependency_lock_hash: str,
    ) -> Experiment:
        """Resolve and store an immutable, secret-free experiment."""

        authorize(
            principal,
            Action.RUN_START,
            organization_id=principal.organization_id,
            project_id=project_id,
        )
        dataset_version = await self._repository.get_dataset_version(
            principal.organization_id,
            project_id,
            dataset_version_id,
        )
        if dataset_version is None:
            raise DomainError(ErrorCode.NOT_FOUND, "dataset version was not found")
        _reject_secrets(provider)
        if not 0 <= seed < (1 << 64):
            raise DomainError(ErrorCode.VALIDATION, "seed must be an unsigned 64-bit integer")
        if not model.strip() or "{{ input }}" not in prompt_template:
            raise DomainError(
                ErrorCode.VALIDATION,
                "model is required and prompt template must contain {{ input }}",
            )
        snapshot_value = {
            "provider": provider,
            "model": model,
            "prompt_template": prompt_template,
            "parameters": parameters,
        }
        snapshot = SystemSnapshot(
            id=new_uuid7(),
            provider=provider,
            model=model,
            prompt_template=prompt_template,
            parameters=parameters,
            content_hash=hashlib.sha256(canonical_bytes(snapshot_value)).hexdigest(),
        )
        experiment_value = {
            "dataset_version_id": str(dataset_version_id),
            "system_snapshot_hash": snapshot.content_hash,
            "suite": suite,
            "seed": seed,
            "application_version": application_version,
            "dependency_lock_hash": dependency_lock_hash,
        }
        experiment = Experiment(
            id=new_uuid7(),
            organization_id=principal.organization_id,
            project_id=project_id,
            dataset_version_id=dataset_version_id,
            system_snapshot=snapshot,
            suite=suite,
            seed=seed,
            config_hash=hashlib.sha256(canonical_bytes(experiment_value)).hexdigest(),
            application_version=application_version,
            dependency_lock_hash=dependency_lock_hash,
        )
        await self._repository.add_experiment(experiment)
        return experiment

    async def create_run(
        self,
        principal: Principal,
        *,
        experiment: Experiment,
        dataset_version: DatasetVersion,
        repetitions: int,
        budget_limit: Money,
    ) -> RunCreation:
        """Create deterministic unique tasks and queue a run transactionally."""

        authorize(
            principal,
            Action.RUN_START,
            organization_id=experiment.organization_id,
            project_id=experiment.project_id,
        )
        if not 1 <= repetitions <= 100:
            raise DomainError(ErrorCode.VALIDATION, "repetitions must be between 1 and 100")
        run_id = new_uuid7()
        tasks: list[EvaluationTaskSpec] = []
        for record in dataset_version.records:
            for repetition in range(repetitions):
                derived_seed = int.from_bytes(
                    hashlib.sha256(
                        experiment.seed.to_bytes(8, "big")
                        + record.key.encode()
                        + repetition.to_bytes(4, "big")
                    ).digest()[:8],
                    "big",
                )
                tasks.append(
                    EvaluationTaskSpec(
                        id=new_uuid7(),
                        run_id=run_id,
                        record_key=record.key,
                        repetition=repetition,
                        system_snapshot_id=experiment.system_snapshot.id,
                        input_payload=record.payload,
                        seed=derived_seed,
                    )
                )
        run = EvaluationRun(
            id=run_id,
            experiment_id=experiment.id,
            state=RunState.DRAFT,
            total_tasks=len(tasks),
        )
        run.transition(RunState.VALIDATING)
        run.transition(RunState.QUEUED)
        creation = RunCreation(run=run, tasks=tuple(tasks), budget_limit=budget_limit)
        await self._repository.add_run(creation)
        return creation


def _reject_secrets(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in _SECRET_FIELDS:
                raise DomainError(
                    ErrorCode.VALIDATION,
                    "provider configuration must reference deployment secrets, not contain them",
                    details={"path": "/" + "/".join((*path, str(key)))},
                )
            _reject_secrets(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secrets(child, (*path, str(index)))
