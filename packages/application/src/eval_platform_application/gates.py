"""Deterministic CI regression-gate evaluation."""

from __future__ import annotations

from eval_platform_schemas.analysis import (
    ComparisonRead,
    GateConfiguration,
    GateOperator,
    GateResult,
    GateRule,
    GateRuleResult,
)


def evaluate_gate(
    configuration: GateConfiguration,
    comparison: ComparisonRead,
) -> GateResult:
    """Evaluate every rule and fail only when a required rule fails."""

    metrics = {metric.metric_identifier: metric for metric in comparison.metrics}
    results = [
        _evaluate_rule(rule, metrics.get(rule.metric_identifier)) for rule in configuration.rules
    ]
    return GateResult(
        passed=all(result.passed or not result.required for result in results),
        rules=results,
    )


def _evaluate_rule(rule: GateRule, metric: object) -> GateRuleResult:
    from eval_platform_schemas.analysis import MetricComparisonRead

    if not isinstance(metric, MetricComparisonRead):
        return GateRuleResult(
            identifier=rule.identifier,
            passed=False,
            required=rule.required,
            observed=None,
            threshold=rule.threshold,
            message=f"metric {rule.metric_identifier} is absent",
        )
    if metric.paired_count < rule.minimum_paired_count:
        return GateRuleResult(
            identifier=rule.identifier,
            passed=False,
            required=rule.required,
            observed=float(metric.paired_count),
            threshold=float(rule.minimum_paired_count),
            message="minimum paired sample count is not satisfied",
        )
    if rule.operator == GateOperator.MINIMUM:
        observed = metric.candidate_mean
        passed = observed >= rule.threshold
    elif rule.operator == GateOperator.MAXIMUM:
        observed = metric.candidate_mean
        passed = observed <= rule.threshold
    elif rule.operator == GateOperator.MAXIMUM_REGRESSION:
        observed = metric.mean_difference
        passed = observed >= -abs(rule.threshold)
    elif rule.operator == GateOperator.LOWER_CONFIDENCE_MINIMUM:
        observed = metric.confidence_interval.lower
        passed = observed >= rule.threshold
    else:
        observed = metric.mean_difference
        passed = metric.practical_interpretation != "evidence_of_meaningful_regression"
    return GateRuleResult(
        identifier=rule.identifier,
        passed=passed,
        required=rule.required,
        observed=observed,
        threshold=rule.threshold,
        message=(
            f"{rule.metric_identifier} satisfied {rule.operator}"
            if passed
            else f"{rule.metric_identifier} violated {rule.operator}"
        ),
    )
