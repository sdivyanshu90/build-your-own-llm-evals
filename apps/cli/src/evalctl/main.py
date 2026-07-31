"""Production-oriented ``evalctl`` command-line interface."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer
from eval_platform_domain.errors import DomainError
from eval_platform_schemas.analysis import ComparisonCreate, GateConfiguration
from eval_platform_schemas.datasets import DatasetVersionCreate
from eval_platform_schemas.experiments import ExperimentCreate, SuiteInput
from eval_platform_sdk.client import ApiClientError, EvalPlatformClient
from pydantic import BaseModel, ValidationError

app = typer.Typer(no_args_is_help=True, help="Operate the LLM Evaluation Platform.")
project_app = typer.Typer(no_args_is_help=True, help="Manage projects.")
dataset_app = typer.Typer(no_args_is_help=True, help="Manage immutable datasets.")
experiment_app = typer.Typer(no_args_is_help=True, help="Manage experiment snapshots.")
suite_app = typer.Typer(no_args_is_help=True, help="Validate evaluation suite configurations.")
run_app = typer.Typer(no_args_is_help=True, help="Operate evaluation runs.")
results_app = typer.Typer(no_args_is_help=True, help="Inspect per-record results.")
report_app = typer.Typer(no_args_is_help=True, help="Export reproducible reports.")
gate_app = typer.Typer(no_args_is_help=True, help="Evaluate CI regression gates.")
app.add_typer(project_app, name="project")
app.add_typer(dataset_app, name="dataset")
app.add_typer(experiment_app, name="experiment")
app.add_typer(suite_app, name="suite")
app.add_typer(run_app, name="run")
app.add_typer(results_app, name="results")
app.add_typer(report_app, name="report")
app.add_typer(gate_app, name="gate")


class Context:
    """CLI connection and rendering configuration."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        organization_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
        json_output: bool,
        timeout: float,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.organization_id = organization_id
        self.project_id = project_id
        self.json_output = json_output
        self.timeout = timeout

    def client(self) -> EvalPlatformClient:
        return EvalPlatformClient(
            self.base_url,
            api_key=self.api_key,
            organization_id=self.organization_id,
            project_id=self.project_id,
            timeout=self.timeout,
        )


@app.callback()
def root(
    ctx: typer.Context,
    base_url: Annotated[
        str,
        typer.Option(envvar="EVAL_API_BASE_URL", help="API base URL."),
    ] = "http://localhost:8000",
    api_key: Annotated[
        str | None,
        typer.Option(envvar="EVAL_API_KEY", help="Service API key."),
    ] = None,
    organization_id: Annotated[
        uuid.UUID | None,
        typer.Option(envvar="EVAL_ORGANIZATION_ID", help="Development organization ID."),
    ] = None,
    project_id: Annotated[
        uuid.UUID | None,
        typer.Option(envvar="EVAL_PROJECT_ID", help="Default project ID."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
    timeout: Annotated[
        float,
        typer.Option(envvar="EVAL_CLI_TIMEOUT", min=0.1, help="Request timeout seconds."),
    ] = 30.0,
) -> None:
    """Configure connection options shared by every command."""

    ctx.obj = Context(
        base_url,
        api_key,
        organization_id,
        project_id,
        json_output,
        timeout,
    )


def _emit(context: Context, value: object) -> None:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if context.json_output:
        typer.echo(json.dumps(value, ensure_ascii=False, sort_keys=True))
    elif isinstance(value, dict):
        for key, item in value.items():
            typer.echo(f"{key}: {item}")
    else:
        typer.echo(str(value))


def _project_id(context: Context, explicit: uuid.UUID | None) -> uuid.UUID:
    project_id = explicit or context.project_id
    if project_id is None:
        typer.echo("error: --project-id or EVAL_PROJECT_ID is required", err=True)
        raise typer.Exit(code=2)
    return project_id


def _api_failure(context: Context, error: ApiClientError) -> None:
    if context.json_output:
        typer.echo(json.dumps(error.body, sort_keys=True), err=True)
    else:
        typer.echo(f"error: {error}", err=True)
    raise typer.Exit(code=4) from error


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        typer.echo(f"error: cannot read valid JSON from {path}: {error}", err=True)
        raise typer.Exit(code=2) from error


def _money(value: str) -> Decimal:
    """Parse a finite non-negative decimal without a binary-float round trip."""

    try:
        result = Decimal(value)
    except (ValueError, ArithmeticError) as error:
        raise typer.BadParameter("budget must be a decimal number") from error
    if not result.is_finite() or result < 0:
        raise typer.BadParameter("budget must be finite and non-negative")
    return result


@project_app.command("create")
def project_create(
    ctx: typer.Context,
    slug: Annotated[str, typer.Option(prompt=True)],
    name: Annotated[str, typer.Option(prompt=True)],
    budget: Annotated[str, typer.Option(help="Non-negative decimal budget in USD.")] = "100",
    concurrency: Annotated[int, typer.Option(min=1, max=10_000)] = 8,
) -> None:
    """Create a project."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            project = client.create_project(
                slug,
                name,
                budget_amount=_money(budget),
                concurrency_limit=concurrency,
            )
        _emit(context, project)
    except ApiClientError as error:
        _api_failure(context, error)


@project_app.command("list")
def project_list(ctx: typer.Context) -> None:
    """List visible projects."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            items = [item.model_dump(mode="json") for item in client.iter_projects()]
        _emit(context, {"items": items})
    except ApiClientError as error:
        _api_failure(context, error)


@dataset_app.command("create")
def dataset_create(
    ctx: typer.Context,
    slug: Annotated[str, typer.Option(prompt=True)],
    name: Annotated[str, typer.Option(prompt=True)],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
    description: Annotated[str, typer.Option()] = "",
    tag: Annotated[list[str] | None, typer.Option("--tag")] = None,
) -> None:
    """Create a dataset catalog."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            value = client.create_dataset(
                _project_id(context, project_id),
                slug=slug,
                name=name,
                description=description,
                tags=tag,
            )
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@dataset_app.command("list")
def dataset_list(
    ctx: typer.Context,
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """List visible dataset catalogs."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            values = [
                item.model_dump(mode="json")
                for item in client.iter_datasets(_project_id(context, project_id))
            ]
        _emit(context, {"items": values})
    except ApiClientError as error:
        _api_failure(context, error)


@dataset_app.command("publish")
def dataset_publish(
    ctx: typer.Context,
    dataset_id: Annotated[uuid.UUID, typer.Option()],
    specification: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="JSON DatasetVersionCreate body.",
        ),
    ],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Validate and publish a JSON version specification."""

    context: Context = ctx.obj
    try:
        body = DatasetVersionCreate.model_validate(_load_json(specification))
        with context.client() as client:
            value = client.publish_dataset_version(
                _project_id(context, project_id),
                dataset_id,
                body,
            )
        _emit(context, value)
    except ValidationError as error:
        typer.echo(f"error: invalid version specification: {error}", err=True)
        raise typer.Exit(code=2) from error
    except ApiClientError as error:
        _api_failure(context, error)


@dataset_app.command("import")
def dataset_import(
    ctx: typer.Context,
    dataset_id: Annotated[uuid.UUID, typer.Option()],
    source: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    import_format: Annotated[str, typer.Option(help="json, jsonl, csv, or parquet.")],
    schema_identifier: Annotated[
        str,
        typer.Option(help="Built-in schema such as qa/v1 or classification/v1."),
    ],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Upload, validate, and atomically publish a dataset file."""

    from eval_platform_application.dataset_import import ImportFormat
    from eval_platform_domain.dataset_schemas import get_builtin_schema

    context: Context = ctx.obj
    try:
        parsed_format = ImportFormat(import_format)
        schema = get_builtin_schema(schema_identifier)
    except (ValueError, KeyError) as error:
        typer.echo(f"error: invalid format or built-in schema: {error}", err=True)
        raise typer.Exit(code=2) from error
    schema_name, schema_version = schema_identifier.split("/", maxsplit=1)
    try:
        with context.client() as client:
            value = client.import_dataset_version(
                _project_id(context, project_id),
                dataset_id,
                source=source,
                import_format=parsed_format.value,
                schema_name=schema_name,
                schema_version=schema_version.removeprefix("v"),
                schema_definition=schema,
            )
        _emit(context, value)
    except (OSError, ApiClientError) as error:
        if isinstance(error, ApiClientError):
            _api_failure(context, error)
        typer.echo(f"error: cannot read {source}: {error}", err=True)
        raise typer.Exit(code=3) from error


@dataset_app.command("validate")
def dataset_validate(
    ctx: typer.Context,
    source: Annotated[Path, typer.Option(exists=True, dir_okay=False, readable=True)],
    import_format: Annotated[str, typer.Option(help="json, jsonl, csv, or parquet.")],
    schema_identifier: Annotated[str, typer.Option()],
    max_records: Annotated[int, typer.Option(min=1)] = 1_000_000,
) -> None:
    """Validate a local dataset without publishing or making a network call."""

    from eval_platform_application.dataset_import import ImportFormat, parse_records
    from eval_platform_domain.dataset_schemas import get_builtin_schema
    from jsonschema import Draft202012Validator

    context: Context = ctx.obj
    try:
        parsed_format = ImportFormat(import_format)
        schema = get_builtin_schema(schema_identifier)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors: list[dict[str, object]] = []
        error_count = 0
        record_count = 0
        with source.open("rb") as stream:
            for index, record in enumerate(
                parse_records(stream, parsed_format, max_records=max_records),
                start=1,
            ):
                record_count = index
                for error in validator.iter_errors(record["payload"]):
                    error_count += 1
                    if len(errors) < 100:
                        errors.append(
                            {
                                "record": record["key"],
                                "path": list(error.absolute_path),
                                "message": error.message,
                            }
                        )
        result = {
            "valid": error_count == 0,
            "record_count": record_count,
            "error_count": error_count,
            "errors": errors,
            "errors_truncated": error_count > len(errors),
            "schema": schema_identifier,
        }
        _emit(context, result)
        if error_count:
            raise typer.Exit(code=2)
    except (OSError, ValueError, KeyError, DomainError) as error:
        typer.echo(f"error: validation could not complete: {error}", err=True)
        raise typer.Exit(code=2) from error


@dataset_app.command("diff")
def dataset_diff(
    ctx: typer.Context,
    dataset_id: Annotated[uuid.UUID, typer.Option()],
    source: Annotated[uuid.UUID, typer.Option()],
    target: Annotated[uuid.UUID, typer.Option()],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Compare two dataset versions."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            value = client.diff_dataset_versions(
                _project_id(context, project_id),
                dataset_id,
                source=source,
                target=target,
            )
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@suite_app.command("create")
def suite_create(
    ctx: typer.Context,
    specification: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, readable=True),
    ],
    output: Annotated[Path, typer.Option(dir_okay=False)],
) -> None:
    """Validate and write a canonical suite block for an experiment snapshot."""

    context: Context = ctx.obj
    try:
        suite = SuiteInput.model_validate(_load_json(specification))
        output.write_text(
            json.dumps(suite.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _emit(context, {"output": str(output), "metric_count": len(suite.metrics)})
    except (ValidationError, OSError) as error:
        typer.echo(f"error: cannot create suite configuration: {error}", err=True)
        raise typer.Exit(code=2) from error


@experiment_app.command("create")
def experiment_create(
    ctx: typer.Context,
    specification: Annotated[
        Path,
        typer.Option(
            exists=True,
            dir_okay=False,
            readable=True,
            help="JSON ExperimentCreate body.",
        ),
    ],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Create an immutable experiment from a JSON specification."""

    context: Context = ctx.obj
    try:
        body = ExperimentCreate.model_validate(_load_json(specification))
        with context.client() as client:
            value = client.create_experiment(_project_id(context, project_id), body)
        _emit(context, value)
    except ValidationError as error:
        typer.echo(f"error: invalid experiment specification: {error}", err=True)
        raise typer.Exit(code=2) from error
    except ApiClientError as error:
        _api_failure(context, error)


@run_app.command("start")
def run_start(
    ctx: typer.Context,
    experiment_id: Annotated[uuid.UUID, typer.Option()],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
    repetitions: Annotated[int, typer.Option(min=1, max=100)] = 1,
    budget: Annotated[str, typer.Option(help="Non-negative decimal run budget.")] = "100",
) -> None:
    """Create and queue a run."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            value = client.start_run(
                _project_id(context, project_id),
                experiment_id,
                repetitions=repetitions,
                budget_limit=_money(budget),
            )
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@run_app.command("status")
def run_status(
    ctx: typer.Context,
    run_id: Annotated[uuid.UUID, typer.Option()],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Show run state and counters."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            value = client.get_run(_project_id(context, project_id), run_id)
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@run_app.command("cancel")
def run_cancel(
    ctx: typer.Context,
    run_id: Annotated[uuid.UUID, typer.Option()],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Request cooperative cancellation."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            value = client.cancel_run(_project_id(context, project_id), run_id)
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@run_app.command("resume")
def run_resume(
    ctx: typer.Context,
    run_id: Annotated[uuid.UUID, typer.Option()],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Resume a paused run."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            value = client.resume_run(_project_id(context, project_id), run_id)
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@results_app.command("show")
def results_show(
    ctx: typer.Context,
    run_id: Annotated[uuid.UUID, typer.Option()],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
    limit: Annotated[int, typer.Option(min=1, max=200)] = 100,
) -> None:
    """Show a page of per-record results, including failures."""

    context: Context = ctx.obj
    try:
        with context.client() as client:
            value = client.list_results(
                _project_id(context, project_id),
                run_id,
                limit=limit,
            )
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@app.command("compare")
def compare_runs(
    ctx: typer.Context,
    baseline_run_id: Annotated[uuid.UUID, typer.Option()],
    candidate_run_id: Annotated[uuid.UUID, typer.Option()],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
    metric: Annotated[list[str] | None, typer.Option("--metric")] = None,
    seed: Annotated[int, typer.Option(min=0)] = 0,
    practical_difference: Annotated[float, typer.Option(min=0)] = 0,
    allow_dataset_intersection: Annotated[bool, typer.Option()] = False,
) -> None:
    """Create a paired statistical comparison."""

    context: Context = ctx.obj
    body = ComparisonCreate(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        metric_identifiers=metric or [],
        seed=seed,
        practical_difference=practical_difference,
        allow_dataset_intersection=allow_dataset_intersection,
    )
    try:
        with context.client() as client:
            value = client.create_comparison(_project_id(context, project_id), body)
        _emit(context, value)
    except ApiClientError as error:
        _api_failure(context, error)


@report_app.command("export")
def report_export(
    ctx: typer.Context,
    comparison_id: Annotated[uuid.UUID, typer.Option()],
    output: Annotated[Path, typer.Option(dir_okay=False)],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
    format: Annotated[
        str,
        typer.Option(help="json, csv, markdown, or html"),
    ] = "markdown",
) -> None:
    """Export a stored comparison report."""

    context: Context = ctx.obj
    if format not in {"json", "csv", "markdown", "html"}:
        typer.echo("error: --format must be json, csv, markdown, or html", err=True)
        raise typer.Exit(code=2)
    try:
        with context.client() as client:
            value = client.export_comparison_report(
                _project_id(context, project_id),
                comparison_id,
                format=format,
            )
        output.write_text(value, encoding="utf-8")
        _emit(context, {"output": str(output), "format": format})
    except OSError as error:
        typer.echo(f"error: cannot write {output}: {error}", err=True)
        raise typer.Exit(code=3) from error
    except ApiClientError as error:
        _api_failure(context, error)


@gate_app.command("check")
def gate_check(
    ctx: typer.Context,
    comparison_id: Annotated[uuid.UUID, typer.Option()],
    configuration: Annotated[
        Path,
        typer.Option(exists=True, dir_okay=False, readable=True),
    ],
    project_id: Annotated[uuid.UUID | None, typer.Option()] = None,
) -> None:
    """Evaluate a machine-readable gate and exit 5 when required rules fail."""

    context: Context = ctx.obj
    try:
        gate = GateConfiguration.model_validate(_load_json(configuration))
        with context.client() as client:
            result = client.evaluate_gate(
                _project_id(context, project_id),
                comparison_id,
                gate,
            )
        _emit(context, result)
        if not result.passed:
            raise typer.Exit(code=5)
    except ValidationError as error:
        typer.echo(f"error: invalid gate configuration: {error}", err=True)
        raise typer.Exit(code=2) from error
    except ApiClientError as error:
        _api_failure(context, error)


if __name__ == "__main__":
    app()
