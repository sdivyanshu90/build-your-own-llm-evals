"""CLI construction and local boundary-validation tests."""

from __future__ import annotations

import json
from pathlib import Path

from evalctl.main import app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_help_constructs_every_registered_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "compare" in result.stdout
    assert "gate" in result.stdout
    assert "report" in result.stdout


def test_cli_rejects_non_decimal_budget_before_network_access() -> None:
    result = runner.invoke(
        app,
        [
            "--organization-id",
            "01900000-0000-7000-8000-000000000001",
            "project",
            "create",
            "--slug",
            "invalid-budget",
            "--name",
            "Invalid budget",
            "--budget",
            "NaN",
        ],
    )
    assert result.exit_code == 2
    assert "finite and non-negative" in result.output


def test_dataset_validate_checks_example_without_network_access() -> None:
    result = runner.invoke(
        app,
        [
            "--json",
            "dataset",
            "validate",
            "--source",
            "examples/datasets/qa.jsonl",
            "--import-format",
            "jsonl",
            "--schema-identifier",
            "qa/v1",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["record_count"] == 2


def test_suite_create_writes_normalized_validated_configuration(tmp_path: Path) -> None:
    source = tmp_path / "suite-input.json"
    output = tmp_path / "suite.json"
    source.write_text(
        json.dumps(
            {
                "task_type": "qa",
                "input_field": "question",
                "reference_field": "answers",
                "metrics": [
                    {"id": "language/exact-match", "configuration": {}},
                ],
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "suite",
            "create",
            "--specification",
            str(source),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert json.loads(output.read_text())["task_type"] == "qa"
