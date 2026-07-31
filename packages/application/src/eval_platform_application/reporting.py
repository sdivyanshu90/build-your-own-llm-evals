"""Safe JSON, CSV, Markdown, and printable HTML comparison reports."""

from __future__ import annotations

import csv
import html
import io
import json

from eval_platform_schemas.analysis import ComparisonRead

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def comparison_json(comparison: ComparisonRead) -> str:
    """Return deterministic pretty JSON."""

    return json.dumps(
        comparison.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def comparison_csv(comparison: ComparisonRead) -> str:
    """Return a formula-injection-safe metric summary CSV."""

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "metric",
            "version",
            "baseline_mean",
            "candidate_mean",
            "mean_difference",
            "ci_lower",
            "ci_upper",
            "paired_count",
            "p_value",
            "adjusted_p_value",
            "interpretation",
        ]
    )
    for metric in comparison.metrics:
        writer.writerow(
            [
                _safe_cell(metric.metric_identifier),
                _safe_cell(metric.metric_version),
                metric.baseline_mean,
                metric.candidate_mean,
                metric.mean_difference,
                metric.confidence_interval.lower,
                metric.confidence_interval.upper,
                metric.paired_count,
                metric.p_value,
                metric.adjusted_p_value,
                _safe_cell(metric.practical_interpretation),
            ]
        )
    return output.getvalue()


def comparison_markdown(comparison: ComparisonRead) -> str:
    """Return a human-readable report retaining denominators and limitations."""

    lines = [
        "# Experiment comparison",
        "",
        f"- Comparison ID: `{comparison.id}`",
        f"- Baseline run: `{comparison.baseline_run_id}`",
        f"- Candidate run: `{comparison.candidate_run_id}`",
        f"- Dataset compatible: `{str(comparison.dataset_compatible).lower()}`",
        f"- Intersection only: `{str(comparison.intersection_only).lower()}`",
        "",
        "| Metric | Baseline | Candidate | Delta (CI) | n | p | Interpretation |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for metric in comparison.metrics:
        interval = metric.confidence_interval
        lines.append(
            f"| {_markdown(metric.metric_identifier)} | {metric.baseline_mean:.6g} | "
            f"{metric.candidate_mean:.6g} | {metric.mean_difference:.6g} "
            f"([{interval.lower:.6g}, {interval.upper:.6g}]) | "
            f"{metric.paired_count} | {metric.p_value:.6g} | "
            f"{_markdown(metric.practical_interpretation)} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {_markdown(limitation)}" for limitation in comparison.limitations)
    lines.extend(
        [
            "",
            "## Reproduction",
            "",
            "Use the stored comparison configuration, run IDs, dataset versions, and seed.",
            "",
        ]
    )
    return "\n".join(lines)


def comparison_html(comparison: ComparisonRead) -> str:
    """Return a standalone printable HTML report with escaped untrusted values."""

    rows = "".join(
        "<tr>"
        f"<th scope='row'>{html.escape(metric.metric_identifier)}</th>"
        f"<td>{metric.baseline_mean:.6g}</td>"
        f"<td>{metric.candidate_mean:.6g}</td>"
        f"<td>{metric.mean_difference:.6g}</td>"
        f"<td>[{metric.confidence_interval.lower:.6g}, "
        f"{metric.confidence_interval.upper:.6g}]</td>"
        f"<td>{metric.paired_count}</td>"
        f"<td>{html.escape(metric.practical_interpretation)}</td>"
        "</tr>"
        for metric in comparison.metrics
    )
    limitations = "".join(
        f"<li>{html.escape(limitation)}</li>" for limitation in comparison.limitations
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Experiment comparison</title>"
        "<style>body{font:16px system-ui;max-width:72rem;margin:auto;padding:2rem}"
        "table{border-collapse:collapse;width:100%}th,td{border:1px solid #777;"
        "padding:.5rem;text-align:right}th:first-child{text-align:left}"
        "@media print{body{padding:0}}</style></head><body>"
        "<h1>Experiment comparison</h1>"
        f"<p>Comparison <code>{comparison.id}</code></p>"
        "<table><caption>Metric estimates, uncertainty, and paired sample sizes</caption>"
        "<thead><tr><th scope='col'>Metric</th><th scope='col'>Baseline</th>"
        "<th scope='col'>Candidate</th><th scope='col'>Delta</th>"
        "<th scope='col'>Confidence interval</th><th scope='col'>n</th>"
        f"<th scope='col'>Interpretation</th></tr></thead><tbody>{rows}</tbody></table>"
        f"<h2>Limitations</h2><ul>{limitations}</ul></body></html>"
    )


def _safe_cell(value: object) -> object:
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _markdown(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")
