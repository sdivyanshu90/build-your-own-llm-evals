"""Celery tasks for outbox relay and resumable run execution."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from functools import partial
from typing import Any

from celery import Task
from eval_platform_application.experiments import MetricOutcome
from eval_platform_application.retry import RetryPolicy, call_with_retry
from eval_platform_domain.execution import FailureCategory, RunState
from eval_platform_infrastructure.database import create_engine, create_session_factory
from eval_platform_infrastructure.models import OutboxEventModel
from eval_platform_infrastructure.run_repository import SqlExperimentRepository
from eval_platform_infrastructure.settings import Settings
from eval_platform_metrics.base import MetricContext, MetricExecutionError, TaskType
from eval_platform_metrics.registry import builtin_registry
from eval_platform_providers.base import (
    GenerationRequest,
    Provider,
    ProviderError,
    ProviderErrorKind,
)
from eval_platform_providers.fake import DeterministicFakeProvider
from eval_platform_providers.http import (
    GenericHttpProvider,
    LocalOpenAICompatibleProvider,
    OpenAICompatibleProvider,
)
from sqlalchemy import select

from eval_platform_worker.celery_app import celery_app


def _provider(configuration: dict[str, Any], settings: Settings) -> Provider:
    provider_type = str(configuration.get("type", "fake"))
    identifier = str(configuration.get("identifier", provider_type))
    if provider_type == "fake":
        responses = configuration.get("responses", {})
        if not isinstance(responses, dict):
            raise ValueError("fake provider responses must be an object")
        return DeterministicFakeProvider(
            identifier,
            responses={str(key): str(value) for key, value in responses.items()},
        )
    base_url = str(configuration.get("base_url", "")).rstrip("/")
    secret_env = str(configuration.get("secret_env", ""))
    api_key = os.environ.get(secret_env, "") if secret_env else ""
    if provider_type == "local":
        return LocalOpenAICompatibleProvider(
            identifier=identifier,
            base_url=base_url,
            api_key=api_key or "local-no-secret",
            timeout_seconds=settings.provider_timeout_seconds,
        )
    adapter = GenericHttpProvider if provider_type == "generic_http" else OpenAICompatibleProvider
    return adapter(
        identifier=identifier,
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=settings.provider_timeout_seconds,
        max_response_bytes=settings.max_response_bytes,
    )


def _input_text(payload: dict[str, Any], suite: dict[str, Any]) -> str:
    configured = suite.get("input_field")
    candidates = [configured] if isinstance(configured, str) else []
    candidates.extend(["input", "question", "task", "document"])
    for field in candidates:
        if field in payload:
            value = payload[field]
            return value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _estimated_cost(
    input_tokens: int,
    max_output_tokens: int,
    parameters: dict[str, Any],
) -> Decimal:
    input_rate = Decimal(str(parameters.get("input_cost_per_million", "0")))
    output_rate = Decimal(str(parameters.get("output_cost_per_million", "0")))
    return (
        Decimal(input_tokens) * input_rate + Decimal(max_output_tokens) * output_rate
    ) / Decimal(1_000_000)


async def _execute_run(run_id: uuid.UUID, owner: str) -> None:
    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value())
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            repository = SqlExperimentRepository(session)
            run_context = await repository.get_run_context(run_id)
            if run_context is None:
                return
            run_model, experiment_model, snapshot_model = run_context
            if RunState(run_model.state) is RunState.QUEUED:
                await repository.transition_run(run_id, RunState.RUNNING)
            elif RunState(run_model.state) not in {RunState.RUNNING}:
                return
            await session.commit()
            provider = _provider(snapshot_model.provider, settings)
            suite = experiment_model.suite
            parameters = snapshot_model.parameters

        while True:
            async with factory() as session:
                repository = SqlExperimentRepository(session)
                run_context = await repository.get_run_context(run_id)
                if run_context is None:
                    return
                run_model, _, _ = run_context
                if RunState(run_model.state) is not RunState.RUNNING:
                    return
                task = await repository.claim_next_task(run_id, owner=owner)
                if task is None:
                    await session.commit()
                    return
                task_id = task.id
                input_payload = task.input_payload
                task_seed = int(task.seed)
                await session.commit()

            input_text = _input_text(input_payload, suite)
            prompt = snapshot_model.prompt_template.replace("{{ input }}", input_text)
            max_tokens = int(parameters.get("max_output_tokens", 512))
            request = GenerationRequest(
                model=snapshot_model.model,
                prompt=prompt,
                temperature=float(parameters.get("temperature", 0)),
                max_output_tokens=max_tokens,
                seed=task_seed,
                idempotency_key=f"eval-task-{task_id}",
            )
            estimate = _estimated_cost(
                provider.count_tokens(snapshot_model.model, prompt),
                max_tokens,
                parameters,
            )
            async with factory() as session:
                repository = SqlExperimentRepository(session)
                current_context = await repository.get_run_context(run_id)
                if current_context is None:
                    return
                current_run = current_context[0]
                if current_run.actual_cost + estimate > current_run.budget_limit:
                    await repository.mark_task_running(task_id, owner)
                    await repository.complete_task_failure(
                        task_id,
                        ProviderError(
                            ProviderErrorKind.INVALID_REQUEST,
                            "run budget is exhausted",
                        ),
                        category=FailureCategory.BUDGET,
                    )
                    await session.commit()
                    continue
                await repository.mark_task_running(task_id, owner)
                await session.commit()

            started = time.perf_counter()

            try:
                response = await call_with_retry(
                    partial(provider.generate, request),
                    RetryPolicy(
                        max_attempts=settings.provider_max_attempts,
                        timeout_seconds=settings.provider_timeout_seconds,
                    ),
                    seed=task_seed,
                )
            except ProviderError as error:
                async with factory() as session:
                    await SqlExperimentRepository(session).complete_task_failure(task_id, error)
                    await session.commit()
                continue

            latency_ms = round((time.perf_counter() - started) * 1000)
            actual_cost = (
                Decimal(response.usage.actual_cost)
                if response.usage.actual_cost is not None
                else estimate
            )
            metric_outcomes: list[MetricOutcome] = []
            reference_field = suite.get("reference_field")
            if isinstance(reference_field, str):
                reference = input_payload.get(reference_field)
            else:
                reference = next(
                    (
                        input_payload[field]
                        for field in ("reference", "reference_answer", "label", "answers")
                        if field in input_payload
                    ),
                    None,
                )
            if isinstance(reference, list) and reference:
                reference = reference[0]
            registry = builtin_registry()
            metric_context = MetricContext(
                task_type=TaskType(str(suite.get("task_type", "generation"))),
                input=input_text,
                prediction=response.text,
                reference=reference,
                metadata=input_payload.get("metadata", {}),
                retrieved_items=tuple(input_payload.get("retrieved_items", ())),
                relevant_item_ids=frozenset(
                    str(value) for value in input_payload.get("relevant_document_ids", ())
                ),
                trajectory=tuple(input_payload.get("trajectory", ())),
                operational={
                    "latency_ms": latency_ms,
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "cost_usd": float(actual_cost),
                    "cost_usd_estimated": response.usage.actual_cost is None,
                },
            )
            for metric_config in suite.get("metrics", []):
                identifier = str(metric_config["id"])
                configuration = metric_config.get("configuration", {})
                try:
                    result = registry.evaluate(identifier, metric_context, configuration)
                    metric_outcomes.append(
                        MetricOutcome(
                            identifier=result.metric_id,
                            version=result.metric_version,
                            status="missing" if result.missing else "succeeded",
                            scalar=result.scalar,
                            label=result.label,
                            structured=result.structured,
                            explanation=result.explanation,
                            metadata=result.metadata,
                        )
                    )
                except MetricExecutionError as error:
                    try:
                        metric_version = registry.definition(identifier).version
                    except MetricExecutionError:
                        metric_version = "unknown"
                    metric_outcomes.append(
                        MetricOutcome(
                            identifier=identifier,
                            version=metric_version,
                            status="failed",
                            error=str(error)[:1000],
                        )
                    )
            async with factory() as session:
                await SqlExperimentRepository(session).complete_task_success(
                    task_id,
                    response,
                    latency_ms=latency_ms,
                    cost=actual_cost,
                    estimated_cost=response.usage.actual_cost is None,
                    metric_outcomes=tuple(metric_outcomes),
                )
                await session.commit()
    finally:
        await engine.dispose()


@celery_app.task(
    bind=True,
    name="eval_platform_worker.tasks.execute_run",
    acks_late=True,
)
def execute_run(self: Task, run_id: str) -> None:
    """Execute or resume one run using durable leases and task uniqueness."""

    owner = f"{socket.gethostname()}:{os.getpid()}:{self.request.id}"
    asyncio.run(_execute_run(uuid.UUID(run_id), owner))


async def _relay_outbox(batch_size: int = 100) -> int:
    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value())
    factory = create_session_factory(engine)
    published = 0
    try:
        async with factory() as session:
            events = (
                await session.scalars(
                    select(OutboxEventModel)
                    .where(OutboxEventModel.published_at.is_(None))
                    .order_by(OutboxEventModel.created_at)
                    .with_for_update(skip_locked=True)
                    .limit(batch_size)
                )
            ).all()
            for event in events:
                if event.event_type == "evaluation.run.queued.v1":
                    execute_run.delay(event.payload["run_id"])
                event.published_at = datetime.now(UTC)
                event.attempts += 1
                published += 1
            await session.commit()
        return published
    finally:
        await engine.dispose()


@celery_app.task(name="eval_platform_worker.tasks.relay_outbox")
def relay_outbox() -> int:
    """Publish a bounded outbox batch; duplicate delivery is receiver-safe."""

    return asyncio.run(_relay_outbox())
