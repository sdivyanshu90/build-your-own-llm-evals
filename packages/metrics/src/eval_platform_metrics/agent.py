"""End-state and trajectory-aware agent metrics."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from jsonschema import Draft202012Validator

from eval_platform_metrics.base import (
    RESULT_SCHEMA,
    Determinism,
    FailureBehavior,
    MetricContext,
    MetricDefinition,
    MetricResult,
    ScoreDirection,
    TaskType,
)


def _tool_calls(trajectory: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [step for step in trajectory if step.get("kind") == "tool_call"]


def tool_selection_accuracy(
    trajectory: Sequence[Mapping[str, Any]],
    expected_tools: Sequence[str],
) -> float | None:
    """Correct tool selections divided by expected selection slots."""

    calls = [str(step.get("tool", "")) for step in _tool_calls(trajectory)]
    if not expected_tools:
        return 1.0 if not calls else 0.0
    matches = sum(
        actual == expected for actual, expected in zip(calls, expected_tools, strict=False)
    )
    return matches / len(expected_tools)


def tool_argument_validity(
    trajectory: Sequence[Mapping[str, Any]],
    tool_schemas: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate every tool call against its named JSON Schema."""

    calls = _tool_calls(trajectory)
    outcomes: list[dict[str, Any]] = []
    for index, call in enumerate(calls):
        tool = str(call.get("tool", ""))
        schema = tool_schemas.get(tool)
        arguments = call.get("arguments")
        if schema is None:
            outcomes.append(
                {"index": index, "tool": tool, "valid": False, "reason": "unknown tool"}
            )
            continue
        errors = list(Draft202012Validator(schema).iter_errors(arguments))
        outcomes.append(
            {
                "index": index,
                "tool": tool,
                "valid": not errors,
                "reason": errors[0].message if errors else None,
            }
        )
    return {
        "rate": sum(item["valid"] for item in outcomes) / len(outcomes) if outcomes else None,
        "calls": outcomes,
    }


def tool_call_success_rate(trajectory: Sequence[Mapping[str, Any]]) -> float | None:
    """Successful tool results divided by tool results."""

    results = [step for step in trajectory if step.get("kind") == "tool_result"]
    if not results:
        return None
    return sum(step.get("success") is True for step in results) / len(results)


def invalid_tool_call_rate(
    trajectory: Sequence[Mapping[str, Any]],
    tool_schemas: Mapping[str, Mapping[str, Any]],
) -> float | None:
    """One minus tool argument validity."""

    validity = tool_argument_validity(trajectory, tool_schemas)["rate"]
    return None if validity is None else 1 - float(validity)


def redundant_tool_call_rate(trajectory: Sequence[Mapping[str, Any]]) -> float:
    """Exact repeated tool-and-argument calls divided by all calls."""

    calls = _tool_calls(trajectory)
    if not calls:
        return 0.0
    keys = [
        (
            str(call.get("tool", "")),
            json.dumps(call.get("arguments"), sort_keys=True, separators=(",", ":")),
        )
        for call in calls
    ]
    counts = Counter(keys)
    redundant = sum(count - 1 for count in counts.values())
    return redundant / len(calls)


def loop_detection(
    trajectory: Sequence[Mapping[str, Any]],
    *,
    minimum_repetitions: int = 3,
) -> dict[str, Any]:
    """Detect repeated normalized action cycles of length one through four."""

    if minimum_repetitions < 2:
        raise ValueError("minimum repetitions must be at least two")
    actions = [
        json.dumps(
            {
                "kind": step.get("kind"),
                "tool": step.get("tool"),
                "arguments": step.get("arguments"),
                "decision": step.get("decision"),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        for step in trajectory
        if step.get("kind") in {"tool_call", "model_decision"}
    ]
    for cycle_length in range(1, min(4, len(actions)) + 1):
        for start in range(len(actions) - cycle_length * minimum_repetitions + 1):
            cycle = actions[start : start + cycle_length]
            if all(
                actions[start + repeat * cycle_length : start + (repeat + 1) * cycle_length]
                == cycle
                for repeat in range(1, minimum_repetitions)
            ):
                return {
                    "detected": True,
                    "start": start,
                    "cycle_length": cycle_length,
                    "minimum_repetitions": minimum_repetitions,
                }
    return {
        "detected": False,
        "start": None,
        "cycle_length": None,
        "minimum_repetitions": minimum_repetitions,
    }


def recovery_after_tool_failure(trajectory: Sequence[Mapping[str, Any]]) -> float | None:
    """Fraction of failed tool results followed by a successful different action."""

    failures = [
        index
        for index, step in enumerate(trajectory)
        if step.get("kind") == "tool_result" and step.get("success") is False
    ]
    if not failures:
        return None
    recovered = 0
    for index in failures:
        later = trajectory[index + 1 :]
        if any(
            (step.get("kind") == "tool_result" and step.get("success") is True)
            or step.get("kind") == "final_output"
            for step in later
        ):
            recovered += 1
    return recovered / len(failures)


def state_consistency(
    trajectory: Sequence[Mapping[str, Any]],
    invariant: Callable[[Any], bool],
) -> dict[str, Any]:
    """Evaluate an explicit state invariant at every recorded state step."""

    violations: list[int] = []
    states = [step for step in trajectory if step.get("kind") == "state"]
    for index, step in enumerate(states):
        if not invariant(step.get("state")):
            violations.append(index)
    return {
        "score": 1 - len(violations) / len(states) if states else None,
        "violations": violations,
        "state_count": len(states),
    }


def grounded_in_tool_outputs(
    final_answer: str,
    trajectory: Sequence[Mapping[str, Any]],
) -> dict[str, float | int | None]:
    """Lexical support proxy for final-answer tokens from successful tool outputs."""

    answer_tokens = set(final_answer.casefold().split())
    tool_text = " ".join(
        str(step.get("output", ""))
        for step in trajectory
        if step.get("kind") == "tool_result" and step.get("success") is True
    )
    tool_tokens = set(tool_text.casefold().split())
    if not answer_tokens:
        return {"groundedness": None, "unsupported_token_count": 0}
    supported = answer_tokens & tool_tokens
    return {
        "groundedness": len(supported) / len(answer_tokens),
        "unsupported_token_count": len(answer_tokens - tool_tokens),
    }


def trajectory_summary(
    trajectory: Sequence[Mapping[str, Any]],
    *,
    tool_costs: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Return neutral step/call/latency/cost descriptors without equating fewer with better."""

    calls = _tool_calls(trajectory)
    costs = tool_costs or {}
    return {
        "step_count": len(trajectory),
        "tool_call_count": len(calls),
        "tool_cost": sum(float(costs.get(str(call.get("tool")), 0)) for call in calls),
        "loop": loop_detection(trajectory)["detected"],
    }


class ToolSuccessMetric:
    """Registered trajectory tool-call success metric."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="agent/tool-call-success-rate",
            name="Tool-call success rate",
            version="1.0.0",
            description="Successful tool results divided by observed tool results.",
            task_types=frozenset({TaskType.AGENT}),
            required_fields=frozenset({"trajectory"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean_available",
            failure_behavior=FailureBehavior.RETURN_MISSING,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "maxProperties": 0,
            },
            computational_cost="O(steps)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        value = tool_call_success_rate(context.trajectory)
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=value,
            missing=value is None,
            explanation="No tool results were observed." if value is None else None,
            metadata={"trajectory_steps": len(context.trajectory)},
        )


class LoopDetectionMetric:
    """Repeated-action loop rate represented as a per-trajectory indicator."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="agent/loop-detected",
            name="Loop detected",
            version="1.0.0",
            description="One when a normalized action cycle repeats at least the configured count.",
            task_types=frozenset({TaskType.AGENT}),
            required_fields=frozenset({"trajectory"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.LOWER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "minimum_repetitions": {
                        "type": "integer",
                        "minimum": 2,
                        "maximum": 100,
                    }
                },
                "required": ["minimum_repetitions"],
            },
            computational_cost="O(steps)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        config = configuration or {"minimum_repetitions": 3}
        evidence = loop_detection(
            context.trajectory,
            minimum_repetitions=int(config["minimum_repetitions"]),
        )
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=float(evidence["detected"]),
            structured=evidence,
        )


class RedundantToolCallMetric:
    """Repeated identical tool-call rate."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="agent/redundant-tool-call-rate",
            name="Redundant tool-call rate",
            version="1.0.0",
            description=(
                "Repeated identical calls divided by all calls; not a standalone quality score."
            ),
            task_types=frozenset({TaskType.AGENT}),
            required_fields=frozenset({"trajectory"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.LOWER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "maxProperties": 0,
            },
            computational_cost="O(calls)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        calls = _tool_calls(context.trajectory)
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=redundant_tool_call_rate(context.trajectory),
            metadata={"tool_call_count": len(calls)},
        )
