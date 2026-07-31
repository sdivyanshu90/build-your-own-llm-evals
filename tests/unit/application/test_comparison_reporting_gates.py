"""Paired comparison, report sanitization, and quality-gate behavior tests."""

from __future__ import annotations

import csv
import io
import uuid

import pytest
from eval_platform_application.comparisons import SampleMetric, compare_metric
from eval_platform_application.gates import evaluate_gate
from eval_platform_application.reporting import (
    comparison_csv,
    comparison_html,
    comparison_json,
    comparison_markdown,
)
from eval_platform_schemas.analysis import (
    ComparisonCreate,
    ComparisonRead,
    GateConfiguration,
    MissingDataPolicy,
)


def _metric(identifier: str = "accuracy"):
    baseline = {
        "one": SampleMetric("one", "succeeded", 0),
        "two": SampleMetric("two", "succeeded", 1),
        "three": SampleMetric("three", "failed", None),
        "four": SampleMetric("four", "succeeded", 0),
        "baseline-only": SampleMetric("baseline-only", "succeeded", 1),
    }
    candidate = {
        "one": SampleMetric("one", "succeeded", 1),
        "two": SampleMetric("two", "succeeded", 1),
        "three": SampleMetric("three", "succeeded", 1),
        "four": SampleMetric("four", "succeeded", 1),
        "candidate-only": SampleMetric("candidate-only", "succeeded", 0),
    }
    return compare_metric(
        metric_identifier=identifier,
        metric_version="1.0.0",
        baseline=baseline,
        candidate=candidate,
        confidence=0.95,
        bootstrap_method="percentile",
        bootstrap_resamples=500,
        test="permutation",
        seed=5,
        missing_data_policy=MissingDataPolicy.AVAILABLE_PAIRS,
        practical_difference=0.1,
        top_changed_examples=2,
    )


def _comparison(identifier: str = "accuracy") -> ComparisonRead:
    baseline_run = uuid.uuid4()
    candidate_run = uuid.uuid4()
    dataset = uuid.uuid4()
    return ComparisonRead(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        baseline_run_id=baseline_run,
        candidate_run_id=candidate_run,
        baseline_dataset_version_id=dataset,
        candidate_dataset_version_id=dataset,
        dataset_compatible=True,
        intersection_only=False,
        configuration=ComparisonCreate(
            baseline_run_id=baseline_run,
            candidate_run_id=candidate_run,
            bootstrap_resamples=500,
        ),
        metrics=[_metric(identifier)],
        limitations=["Synthetic example; external validity is not established."],
    )


def test_comparison_is_paired_and_exposes_every_denominator() -> None:
    metric = _metric()
    assert metric.paired_count == 3
    assert metric.total_union_count == 6
    assert metric.missing_baseline_count == 2
    assert metric.missing_candidate_count == 1
    assert metric.failed_baseline_count == 1
    assert metric.failed_candidate_count == 0
    assert metric.candidate_mean > metric.baseline_mean
    assert metric.confidence_interval.lower <= metric.mean_difference
    assert len(metric.largest_improvements) == 2
    assert metric.largest_improvements[0]["difference"] == 1


def test_failure_as_zero_policy_retains_failed_pair() -> None:
    metric = compare_metric(
        metric_identifier="accuracy",
        metric_version="1.0.0",
        baseline={
            "one": SampleMetric("one", "failed", None),
            "two": SampleMetric("two", "succeeded", 1),
        },
        candidate={
            "one": SampleMetric("one", "succeeded", 1),
            "two": SampleMetric("two", "succeeded", 1),
        },
        confidence=0.95,
        bootstrap_method="percentile",
        bootstrap_resamples=500,
        test="sign",
        seed=1,
        missing_data_policy=MissingDataPolicy.FAILURES_AS_ZERO,
        practical_difference=0,
        top_changed_examples=0,
    )
    assert metric.paired_count == 2
    assert metric.largest_improvements == []
    assert metric.largest_regressions == []


def test_reports_include_uncertainty_and_escape_untrusted_identifiers() -> None:
    comparison = _comparison('=HYPERLINK("https://invalid")')
    csv_text = comparison_csv(comparison)
    row = list(csv.reader(io.StringIO(csv_text)))[1]
    assert row[0].startswith("'=")
    markdown = comparison_markdown(comparison)
    assert "Delta (CI)" in markdown
    assert f"`{comparison.baseline_run_id}`" in markdown
    html = comparison_html(comparison)
    assert "<table>" in html
    assert "HYPERLINK" in html
    assert "<script" not in html
    assert '"paired_count": 3' in comparison_json(comparison)


def test_required_gate_passes_and_fails_with_evidence() -> None:
    comparison = _comparison()
    passing = evaluate_gate(
        GateConfiguration.model_validate(
            {
                "version": "1.0.0",
                "rules": [
                    {
                        "identifier": "accuracy-regression",
                        "metric_identifier": "accuracy",
                        "operator": "maximum_regression",
                        "threshold": 0.1,
                        "minimum_paired_count": 3,
                    }
                ],
            }
        ),
        comparison,
    )
    assert passing.passed
    failing = evaluate_gate(
        GateConfiguration.model_validate(
            {
                "version": "1.0.0",
                "rules": [
                    {
                        "identifier": "impossible-threshold",
                        "metric_identifier": "accuracy",
                        "operator": "lower_confidence_minimum",
                        "threshold": 0.99,
                    }
                ],
            }
        ),
        comparison,
    )
    assert not failing.passed
    assert failing.rules[0].observed is not None


def test_every_gate_operator_and_inconclusive_condition_is_explicit() -> None:
    comparison = _comparison()
    configuration = GateConfiguration.model_validate(
        {
            "version": "1.0.0",
            "rules": [
                {
                    "identifier": "minimum",
                    "metric_identifier": "accuracy",
                    "operator": "minimum",
                    "threshold": 0.5,
                },
                {
                    "identifier": "maximum",
                    "metric_identifier": "accuracy",
                    "operator": "maximum",
                    "threshold": 1,
                },
                {
                    "identifier": "meaningful",
                    "metric_identifier": "accuracy",
                    "operator": "no_meaningful_regression",
                    "threshold": 0,
                },
                {
                    "identifier": "too-few",
                    "metric_identifier": "accuracy",
                    "operator": "minimum",
                    "threshold": 0,
                    "minimum_paired_count": 100,
                    "required": False,
                },
                {
                    "identifier": "absent",
                    "metric_identifier": "not-recorded",
                    "operator": "minimum",
                    "threshold": 0,
                    "required": False,
                },
            ],
        }
    )
    result = evaluate_gate(configuration, comparison)
    assert result.passed
    assert result.rules[0].observed == comparison.metrics[0].candidate_mean
    assert result.rules[1].passed
    assert result.rules[2].passed
    assert result.rules[3].message == "minimum paired sample count is not satisfied"
    assert result.rules[4].observed is None


def test_comparison_requires_two_available_pairs() -> None:
    with pytest.raises(ValueError, match="at least two"):
        compare_metric(
            metric_identifier="accuracy",
            metric_version="1.0.0",
            baseline={"one": SampleMetric("one", "succeeded", 1)},
            candidate={"one": SampleMetric("one", "succeeded", 1)},
            confidence=0.95,
            bootstrap_method="bca",
            bootstrap_resamples=500,
            test="paired_t",
            seed=0,
            missing_data_policy=MissingDataPolicy.AVAILABLE_PAIRS,
            practical_difference=0,
            top_changed_examples=10,
        )
