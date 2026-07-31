"""Synchronous typed API client used by automation and the CLI."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from eval_platform_schemas.analysis import (
    ComparisonCreate,
    ComparisonRead,
    GateConfiguration,
    GateResult,
    JudgeConfigurationCreate,
    JudgeConfigurationRead,
    PairDesignCreate,
    PairDesignRead,
    RubricCreate,
    RubricRead,
)
from eval_platform_schemas.common import Page
from eval_platform_schemas.datasets import (
    DatasetCreate,
    DatasetDiffRead,
    DatasetRead,
    DatasetVersionCreate,
    DatasetVersionRead,
)
from eval_platform_schemas.experiments import (
    ExperimentCreate,
    ExperimentRead,
    RunRead,
    RunStart,
    SampleRead,
)
from eval_platform_schemas.projects import ProjectCreate, ProjectRead


class ApiClientError(RuntimeError):
    """API error with status and stable server error fields."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        super().__init__(str(body.get("message", "API request failed")))
        self.status_code = status_code
        self.body = body


class EvalPlatformClient:
    """Small typed client with bounded request timeouts."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        organization_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        timeout: float = 30.0,
    ) -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if organization_id:
            headers["X-Organization-ID"] = str(organization_id)
        if project_id:
            headers["X-Project-ID"] = str(project_id)
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )

    def __enter__(self) -> EvalPlatformClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Close pooled connections."""

        self._client.close()

    def create_project(
        self,
        slug: str,
        name: str,
        *,
        budget_amount: Decimal = Decimal("100"),
        concurrency_limit: int = 8,
    ) -> ProjectRead:
        """Create a project."""

        body = ProjectCreate(
            slug=slug,
            name=name,
            budget_amount=budget_amount,
            concurrency_limit=concurrency_limit,
        )
        response = self._request("POST", "/api/v1/projects", json=body.model_dump(mode="json"))
        return ProjectRead.model_validate(response)

    def iter_projects(self, *, page_size: int = 100) -> Iterator[ProjectRead]:
        """Iterate all visible projects using server keyset pagination."""

        after: str | None = None
        while True:
            params: dict[str, str | int] = {"limit": page_size}
            if after:
                params["after"] = after
            body = self._request("GET", "/api/v1/projects", params=params)
            for item in body["items"]:
                yield ProjectRead.model_validate(item)
            after = body["page"]["next_cursor"]
            if after is None:
                return

    def create_dataset(
        self,
        project_id: uuid.UUID,
        *,
        slug: str,
        name: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> DatasetRead:
        """Create a project-scoped dataset catalog."""

        body = DatasetCreate(
            slug=slug,
            name=name,
            description=description,
            tags=tags or [],
        )
        value = self._request(
            "POST",
            f"/api/v1/projects/{project_id}/datasets",
            json=body.model_dump(mode="json"),
        )
        return DatasetRead.model_validate(value)

    def iter_datasets(
        self,
        project_id: uuid.UUID,
        *,
        page_size: int = 100,
    ) -> Iterator[DatasetRead]:
        """Iterate visible dataset catalogs with keyset pagination."""

        after: str | None = None
        while True:
            params: dict[str, str | int] = {"limit": page_size}
            if after:
                params["after"] = after
            body = self._request(
                "GET",
                f"/api/v1/projects/{project_id}/datasets",
                params=params,
            )
            for item in body["items"]:
                yield DatasetRead.model_validate(item)
            after = body["page"]["next_cursor"]
            if after is None:
                return

    def publish_dataset_version(
        self,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
        body: DatasetVersionCreate,
    ) -> DatasetVersionRead:
        """Publish an immutable API-supplied dataset version."""

        value = self._request(
            "POST",
            f"/api/v1/projects/{project_id}/datasets/{dataset_id}/versions",
            json=body.model_dump(mode="json", by_alias=True),
        )
        return DatasetVersionRead.model_validate(value)

    def import_dataset_version(
        self,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
        *,
        source: Path,
        import_format: str,
        schema_name: str,
        schema_version: str,
        schema_definition: dict[str, Any],
    ) -> DatasetVersionRead:
        """Upload and atomically publish one bounded dataset file."""

        content_types = {
            "json": "application/json",
            "jsonl": "application/x-ndjson",
            "csv": "text/csv",
            "parquet": "application/vnd.apache.parquet",
        }
        with source.open("rb") as stream:
            response = self._client.post(
                f"/api/v1/projects/{project_id}/datasets/{dataset_id}/imports",
                data={
                    "import_format": import_format,
                    "schema_name": schema_name,
                    "schema_version": schema_version,
                    "schema_json": json.dumps(schema_definition, separators=(",", ":")),
                },
                files={
                    "file": (
                        source.name,
                        stream,
                        content_types.get(import_format, "application/octet-stream"),
                    )
                },
            )
        try:
            body = response.json()
        except ValueError as error:
            raise ApiClientError(
                response.status_code,
                {"message": "dataset import returned invalid JSON"},
            ) from error
        if response.is_error:
            raise ApiClientError(response.status_code, body)
        return DatasetVersionRead.model_validate(body)

    def diff_dataset_versions(
        self,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
        *,
        source: uuid.UUID,
        target: uuid.UUID,
    ) -> DatasetDiffRead:
        """Compare two immutable versions by record key."""

        value = self._request(
            "GET",
            f"/api/v1/projects/{project_id}/datasets/{dataset_id}/diff",
            params={"source": str(source), "target": str(target)},
        )
        return DatasetDiffRead.model_validate(value)

    def create_experiment(
        self,
        project_id: uuid.UUID,
        body: ExperimentCreate,
    ) -> ExperimentRead:
        """Create an immutable resolved experiment."""

        value = self._request(
            "POST",
            f"/api/v1/projects/{project_id}/experiments",
            json=body.model_dump(mode="json"),
        )
        return ExperimentRead.model_validate(value)

    def start_run(
        self,
        project_id: uuid.UUID,
        experiment_id: uuid.UUID,
        *,
        repetitions: int = 1,
        budget_limit: Decimal = Decimal("100"),
    ) -> RunRead:
        """Create durable evaluation tasks and queue a run."""

        body = RunStart(repetitions=repetitions, budget_limit=budget_limit)
        value = self._request(
            "POST",
            f"/api/v1/projects/{project_id}/experiments/{experiment_id}/runs",
            json=body.model_dump(mode="json"),
        )
        return RunRead.model_validate(value)

    def get_run(self, project_id: uuid.UUID, run_id: uuid.UUID) -> RunRead:
        """Get run state and denominator counters."""

        return RunRead.model_validate(
            self._request("GET", f"/api/v1/projects/{project_id}/runs/{run_id}")
        )

    def cancel_run(self, project_id: uuid.UUID, run_id: uuid.UUID) -> RunRead:
        """Request cooperative cancellation."""

        return RunRead.model_validate(
            self._request("POST", f"/api/v1/projects/{project_id}/runs/{run_id}/cancel")
        )

    def resume_run(self, project_id: uuid.UUID, run_id: uuid.UUID) -> RunRead:
        """Resume a paused run without recreating terminal work."""

        return RunRead.model_validate(
            self._request("POST", f"/api/v1/projects/{project_id}/runs/{run_id}/resume")
        )

    def list_results(
        self,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        limit: int = 100,
    ) -> Page[SampleRead]:
        """List the first keyset page of per-record results."""

        return Page[SampleRead].model_validate(
            self._request(
                "GET",
                f"/api/v1/projects/{project_id}/runs/{run_id}/results",
                params={"limit": limit},
            )
        )

    def create_rubric(
        self,
        project_id: uuid.UUID,
        body: RubricCreate,
    ) -> RubricRead:
        """Create an immutable rubric version."""

        return RubricRead.model_validate(
            self._request(
                "POST",
                f"/api/v1/projects/{project_id}/rubrics",
                json=body.model_dump(mode="json"),
            )
        )

    def create_judge_configuration(
        self,
        project_id: uuid.UUID,
        body: JudgeConfigurationCreate,
    ) -> JudgeConfigurationRead:
        """Create an immutable judge configuration."""

        return JudgeConfigurationRead.model_validate(
            self._request(
                "POST",
                f"/api/v1/projects/{project_id}/judge-configurations",
                json=body.model_dump(mode="json"),
            )
        )

    def create_pair_design(
        self,
        project_id: uuid.UUID,
        body: PairDesignCreate,
    ) -> PairDesignRead:
        """Create deterministic blinded pair assignments."""

        return PairDesignRead.model_validate(
            self._request(
                "POST",
                f"/api/v1/projects/{project_id}/pair-designs",
                json=body.model_dump(mode="json"),
            )
        )

    def create_comparison(
        self,
        project_id: uuid.UUID,
        body: ComparisonCreate,
    ) -> ComparisonRead:
        """Create a paired experiment comparison."""

        return ComparisonRead.model_validate(
            self._request(
                "POST",
                f"/api/v1/projects/{project_id}/comparisons",
                json=body.model_dump(mode="json"),
            )
        )

    def get_comparison(
        self,
        project_id: uuid.UUID,
        comparison_id: uuid.UUID,
    ) -> ComparisonRead:
        """Get one stored comparison."""

        return ComparisonRead.model_validate(
            self._request(
                "GET",
                f"/api/v1/projects/{project_id}/comparisons/{comparison_id}",
            )
        )

    def export_comparison_report(
        self,
        project_id: uuid.UUID,
        comparison_id: uuid.UUID,
        *,
        format: str,
    ) -> str:
        """Export one report as JSON, CSV, Markdown, or HTML text."""

        response = self._client.get(
            f"/api/v1/projects/{project_id}/comparisons/{comparison_id}/report",
            params={"format": format},
        )
        if response.is_error:
            try:
                body = response.json()
            except ValueError:
                body = {"message": "report export failed"}
            raise ApiClientError(response.status_code, body)
        return response.text

    def evaluate_gate(
        self,
        project_id: uuid.UUID,
        comparison_id: uuid.UUID,
        configuration: GateConfiguration,
    ) -> GateResult:
        """Evaluate a quality gate against a stored comparison."""

        return GateResult.model_validate(
            self._request(
                "POST",
                f"/api/v1/projects/{project_id}/comparisons/{comparison_id}/gate",
                json=configuration.model_dump(mode="json"),
            )
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._client.request(method, path, **kwargs)
        body = response.json()
        if response.is_error:
            raise ApiClientError(response.status_code, body)
        if not isinstance(body, dict):
            raise ApiClientError(response.status_code, {"message": "invalid API response"})
        return body
