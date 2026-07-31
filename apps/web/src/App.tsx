import { useQuery } from "@tanstack/react-query";
import {
  createRootRoute,
  createRoute,
  createRouter,
  Link,
  Outlet,
  RouterHistory,
  RouterProvider,
} from "@tanstack/react-router";
import { FormEvent, useState } from "react";
import type { ReactNode } from "react";

import {
  Comparison,
  downloadComparisonReport,
  getComparison,
  getDatasetDiff,
  getPairAggregate,
  getRun,
  getRunAggregates,
  getRunCosts,
  getRunErrors,
  getRunSamples,
  listAuditEvents,
  listComparisons,
  listDatasets,
  listDatasetVersions,
  listMetrics,
  listPairDesigns,
  listProjects,
  listRuns,
} from "./api";

const DEFAULT_ORGANIZATION = "01900000-0000-7000-8000-000000000001";

function ProjectsPage() {
  const [organizationId, setOrganizationId] = useState(
    localStorage.getItem("eval.organization") ?? DEFAULT_ORGANIZATION,
  );
  const [activeOrganization, setActiveOrganization] = useState(organizationId);
  const query = useQuery({
    queryKey: ["projects", activeOrganization],
    queryFn: () => listProjects(activeOrganization),
    retry: false,
  });

  function selectOrganization(event: FormEvent) {
    event.preventDefault();
    localStorage.setItem("eval.organization", organizationId);
    setActiveOrganization(organizationId);
  }

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Control plane</p>
          <h1>Evaluation projects</h1>
          <p>Version datasets, run evaluations, and inspect uncertainty.</p>
        </div>
        <form onSubmit={selectOrganization} aria-label="Select organization">
          <label htmlFor="organization">Organization UUID</label>
          <div className="inline">
            <input
              id="organization"
              value={organizationId}
              onChange={(event) => setOrganizationId(event.target.value)}
              required
              pattern="[0-9a-fA-F-]{36}"
            />
            <button type="submit">Load</button>
          </div>
        </form>
      </header>
      {query.isPending && <p role="status">Loading projects…</p>}
      {query.isError && (
        <section className="notice error" role="alert">
          <h2>Projects could not be loaded</h2>
          <p>{query.error.message}</p>
          <button type="button" onClick={() => void query.refetch()}>
            Retry
          </button>
        </section>
      )}
      {query.isSuccess && query.data.length === 0 && (
        <section className="notice">
          <h2>No projects yet</h2>
          <p>Create one with the API or evalctl to begin.</p>
        </section>
      )}
      {query.isSuccess && query.data.length > 0 && (
        <ul className="card-grid" aria-label="Projects">
          {query.data.map((project) => (
            <li className="card" key={project.id}>
              <h2>
                <Link
                  to="/projects/$projectId"
                  params={{ projectId: project.id }}
                >
                  {project.name}
                </Link>
              </h2>
              <p>{project.slug}</p>
              <dl>
                <div>
                  <dt>Budget</dt>
                  <dd>
                    {project.budget_amount} {project.budget_currency}
                  </dd>
                </div>
                <div>
                  <dt>Concurrency</dt>
                  <dd>{project.concurrency_limit}</dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function ProjectPage() {
  const { projectId } = projectRoute.useParams();
  const organizationId =
    localStorage.getItem("eval.organization") ?? DEFAULT_ORGANIZATION;
  const datasets = useQuery({
    queryKey: ["datasets", organizationId, projectId],
    queryFn: () => listDatasets(organizationId, projectId),
    retry: false,
    enabled: projectId.length > 0,
  });
  const metrics = useQuery({
    queryKey: ["metrics", organizationId],
    queryFn: () => listMetrics(organizationId),
    retry: false,
  });
  const runs = useQuery({
    queryKey: ["runs", organizationId, projectId],
    queryFn: () => listRuns(organizationId, projectId),
    retry: false,
  });
  const comparisons = useQuery({
    queryKey: ["comparisons", organizationId, projectId],
    queryFn: () => listComparisons(organizationId, projectId),
    retry: false,
  });
  const pairDesigns = useQuery({
    queryKey: ["pair-designs", organizationId, projectId],
    queryFn: () => listPairDesigns(organizationId, projectId),
    retry: false,
  });

  return (
    <>
      <Link to="/">Return to projects</Link>
      <header>
        <p className="eyebrow">Project</p>
        <h1>Evaluation workspace</h1>
        <p className="resource-id">Project {projectId}</p>
      </header>
      <div className="workspace-grid">
        <section aria-labelledby="datasets-heading">
          <h2 id="datasets-heading">Datasets</h2>
          {datasets.isPending && <p role="status">Loading datasets…</p>}
          {datasets.isError && (
            <div className="notice error" role="alert">
              <h3>Datasets could not be loaded</h3>
              <p>{datasets.error.message}</p>
            </div>
          )}
          {datasets.isSuccess && datasets.data.length === 0 && (
            <div className="notice">
              <h3>No datasets</h3>
              <p>Create and publish a version with the API or evalctl.</p>
            </div>
          )}
          {datasets.isSuccess && datasets.data.length > 0 && (
            <ul className="stack" aria-label="Dataset registry">
              {datasets.data.map((dataset) => (
                <li className="card" key={dataset.id}>
                  <h3>
                    <Link
                      to="/projects/$projectId/datasets/$datasetId"
                      params={{ projectId, datasetId: dataset.id }}
                    >
                      {dataset.name}
                    </Link>
                  </h3>
                  <p>{dataset.description || "No description supplied."}</p>
                  <p>
                    <span className="label">Slug</span> {dataset.slug}
                  </p>
                  <ul className="tags" aria-label={`${dataset.name} tags`}>
                    {dataset.tags.map((tag) => (
                      <li key={tag}>{tag}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section aria-labelledby="metrics-heading">
          <h2 id="metrics-heading">Available metrics</h2>
          {metrics.isPending && <p role="status">Loading metric contracts…</p>}
          {metrics.isError && (
            <div className="notice error" role="alert">
              <h3>Metrics could not be loaded</h3>
              <p>{metrics.error.message}</p>
            </div>
          )}
          {metrics.isSuccess && (
            <>
              <p>
                {metrics.data.length} versioned metric contracts registered.
              </p>
              <ul className="metric-list">
                {metrics.data.slice(0, 12).map((metric) => (
                  <li key={metric.identifier}>
                    <strong>{metric.name}</strong>
                    <span>
                      {metric.identifier} · v{metric.version}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
      <div className="workspace-grid">
        <ResourceSection
          heading="Evaluation runs"
          pending={runs.isPending}
          error={runs.error}
          empty={runs.isSuccess && runs.data.length === 0}
        >
          {runs.isSuccess && (
            <ul className="stack">
              {runs.data.map((run) => (
                <li className="card" key={run.id}>
                  <h3>
                    <Link
                      to="/projects/$projectId/runs/$runId"
                      params={{ projectId, runId: run.id }}
                    >
                      Run {run.id.slice(0, 8)}
                    </Link>
                  </h3>
                  <Status value={run.state} />
                  <p>
                    {run.succeeded_tasks +
                      run.failed_tasks +
                      run.cancelled_tasks}{" "}
                    of {run.total_tasks} tasks settled
                  </p>
                </li>
              ))}
            </ul>
          )}
        </ResourceSection>
        <section aria-labelledby="analysis-heading">
          <h2 id="analysis-heading">Comparisons and judging</h2>
          {comparisons.isPending || pairDesigns.isPending ? (
            <p role="status">Loading analyses…</p>
          ) : null}
          {comparisons.isError || pairDesigns.isError ? (
            <div className="notice error" role="alert">
              Analyses could not be loaded.
            </div>
          ) : null}
          {comparisons.isSuccess && comparisons.data.length > 0 && (
            <>
              <h3>Experiment comparisons</h3>
              <ul className="metric-list">
                {comparisons.data.map((comparison) => (
                  <li key={comparison.id}>
                    <Link
                      to="/projects/$projectId/comparisons/$comparisonId"
                      params={{ projectId, comparisonId: comparison.id }}
                    >
                      {comparison.metrics.length} metrics ·{" "}
                      {comparison.id.slice(0, 8)}
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
          {pairDesigns.isSuccess && pairDesigns.data.length > 0 && (
            <>
              <h3>Pairwise designs</h3>
              <ul className="metric-list">
                {pairDesigns.data.map((design) => (
                  <li key={design.id}>
                    <Link
                      to="/projects/$projectId/pairs/$designId"
                      params={{ projectId, designId: design.id }}
                    >
                      {design.name}
                    </Link>
                    <span>{design.assignment_count} blinded assignments</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <p>
            <Link to="/projects/$projectId/audit" params={{ projectId }}>
              View project audit log
            </Link>
          </p>
        </section>
      </div>
    </>
  );
}

interface ResourceSectionProps {
  heading: string;
  pending: boolean;
  error: Error | null;
  empty: boolean;
  children: ReactNode;
}

function ResourceSection({
  heading,
  pending,
  error,
  empty,
  children,
}: ResourceSectionProps) {
  const headingId = heading.toLowerCase().replaceAll(" ", "-");
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId}>{heading}</h2>
      {pending && <p role="status">Loading {heading.toLowerCase()}…</p>}
      {error && (
        <div className="notice error" role="alert">
          {error.message}
        </div>
      )}
      {empty && (
        <p className="notice">No {heading.toLowerCase()} are available.</p>
      )}
      {children}
    </section>
  );
}

function Status({ value }: { value: string }) {
  return (
    <span className="status" data-state={value}>
      <span aria-hidden="true">●</span> {value.replaceAll("_", " ")}
    </span>
  );
}

function DatasetPage() {
  const { projectId, datasetId } = datasetRoute.useParams();
  const organizationId =
    localStorage.getItem("eval.organization") ?? DEFAULT_ORGANIZATION;
  const versions = useQuery({
    queryKey: ["dataset-versions", organizationId, projectId, datasetId],
    queryFn: () => listDatasetVersions(organizationId, projectId, datasetId),
    retry: false,
  });
  const [selection, setSelection] = useState({ source: "", target: "" });
  const [activeDiff, setActiveDiff] = useState({ source: "", target: "" });
  const diff = useQuery({
    queryKey: ["dataset-diff", organizationId, datasetId, activeDiff],
    queryFn: () =>
      getDatasetDiff(
        organizationId,
        projectId,
        datasetId,
        activeDiff.source,
        activeDiff.target,
      ),
    enabled: activeDiff.source.length > 0 && activeDiff.target.length > 0,
    retry: false,
  });
  return (
    <>
      <Link to="/projects/$projectId" params={{ projectId }}>
        Return to workspace
      </Link>
      <header>
        <p className="eyebrow">Immutable dataset</p>
        <h1>Version browser</h1>
        <p className="resource-id">{datasetId}</p>
      </header>
      <ResourceSection
        heading="Published versions"
        pending={versions.isPending}
        error={versions.error}
        empty={versions.isSuccess && versions.data.length === 0}
      >
        {versions.isSuccess && versions.data.length > 0 && (
          <>
            <div className="table-scroll">
              <table>
                <caption>Immutable version manifests</caption>
                <thead>
                  <tr>
                    <th scope="col">Version</th>
                    <th scope="col">Records</th>
                    <th scope="col">Duplicates</th>
                    <th scope="col">Schema</th>
                    <th scope="col">Content hash</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.data.map((version) => (
                    <tr key={version.id}>
                      <th scope="row">v{version.version_number}</th>
                      <td>{version.record_count}</td>
                      <td>{version.duplicate_payload_count}</td>
                      <td>
                        {version.schema_name}@{version.schema_version}
                      </td>
                      <td className="resource-id">{version.content_hash}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <form
              className="diff-form"
              onSubmit={(event) => {
                event.preventDefault();
                setActiveDiff(selection);
              }}
            >
              <h2>Compare versions</h2>
              <label htmlFor="source-version">Source</label>
              <select
                id="source-version"
                required
                value={selection.source}
                onChange={(event) =>
                  setSelection({ ...selection, source: event.target.value })
                }
              >
                <option value="">Choose source</option>
                {versions.data.map((version) => (
                  <option value={version.id} key={version.id}>
                    v{version.version_number}
                  </option>
                ))}
              </select>
              <label htmlFor="target-version">Target</label>
              <select
                id="target-version"
                required
                value={selection.target}
                onChange={(event) =>
                  setSelection({ ...selection, target: event.target.value })
                }
              >
                <option value="">Choose target</option>
                {versions.data.map((version) => (
                  <option value={version.id} key={version.id}>
                    v{version.version_number}
                  </option>
                ))}
              </select>
              <button type="submit">Generate diff</button>
            </form>
          </>
        )}
      </ResourceSection>
      {diff.isPending && activeDiff.source && (
        <p role="status">Computing diff…</p>
      )}
      {diff.isError && (
        <div className="notice error" role="alert">
          {diff.error.message}
        </div>
      )}
      {diff.isSuccess && (
        <section aria-labelledby="diff-heading">
          <h2 id="diff-heading">Dataset diff</h2>
          <dl className="summary-grid">
            {Object.entries(diff.data.counts).map(([kind, count]) => (
              <div key={kind}>
                <dt>{kind}</dt>
                <dd>{count}</dd>
              </div>
            ))}
          </dl>
          <ul className="stack">
            {diff.data.records.map((record) => (
              <li className="card" key={record.key}>
                <strong>{record.key}</strong> <Status value={record.kind} />
                <p>{record.changes.length} field changes</p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function RunPage() {
  const { projectId, runId } = runRoute.useParams();
  const organizationId =
    localStorage.getItem("eval.organization") ?? DEFAULT_ORGANIZATION;
  const run = useQuery({
    queryKey: ["run", organizationId, projectId, runId],
    queryFn: () => getRun(organizationId, projectId, runId),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      return state &&
        ["completed", "completed_with_errors", "cancelled", "failed"].includes(
          state,
        )
        ? false
        : 2000;
    },
    retry: false,
  });
  const aggregates = useQuery({
    queryKey: ["aggregates", organizationId, projectId, runId],
    queryFn: () => getRunAggregates(organizationId, projectId, runId),
    retry: false,
  });
  const samples = useQuery({
    queryKey: ["samples", organizationId, projectId, runId],
    queryFn: () => getRunSamples(organizationId, projectId, runId),
    retry: false,
  });
  const costs = useQuery({
    queryKey: ["costs", organizationId, projectId, runId],
    queryFn: () => getRunCosts(organizationId, projectId, runId),
    retry: false,
  });
  const errors = useQuery({
    queryKey: ["errors", organizationId, projectId, runId],
    queryFn: () => getRunErrors(organizationId, projectId, runId),
    retry: false,
  });
  if (run.isPending) return <p role="status">Loading run progress…</p>;
  if (run.isError)
    return (
      <div className="notice error" role="alert">
        {run.error.message}
      </div>
    );
  const settled =
    run.data.succeeded_tasks + run.data.failed_tasks + run.data.cancelled_tasks;
  return (
    <>
      <Link to="/projects/$projectId" params={{ projectId }}>
        Return to workspace
      </Link>
      <header>
        <p className="eyebrow">Evaluation run</p>
        <h1>Run evidence</h1>
        <p className="resource-id">{runId}</p>
        <Status value={run.data.state} />
      </header>
      <section aria-labelledby="progress-heading">
        <h2 id="progress-heading">Progress</h2>
        <progress value={settled} max={run.data.total_tasks}>
          {settled} of {run.data.total_tasks}
        </progress>
        <p>
          {settled} of {run.data.total_tasks} tasks settled:{" "}
          {run.data.succeeded_tasks} succeeded, {run.data.failed_tasks} failed,{" "}
          {run.data.cancelled_tasks} cancelled, and {run.data.pending_tasks}{" "}
          pending.
        </p>
      </section>
      <ResourceSection
        heading="Aggregate metrics"
        pending={aggregates.isPending}
        error={aggregates.error}
        empty={aggregates.isSuccess && aggregates.data.length === 0}
      >
        {aggregates.isSuccess && (
          <div className="table-scroll">
            <table>
              <caption>
                Point estimates and explicit result denominators
              </caption>
              <thead>
                <tr>
                  <th scope="col">Metric</th>
                  <th scope="col">Value</th>
                  <th scope="col">Available / total</th>
                  <th scope="col">Missing</th>
                  <th scope="col">Failed</th>
                </tr>
              </thead>
              <tbody>
                {aggregates.data.map((metric) => (
                  <tr key={`${metric.metric_identifier}-${metric.slice_key}`}>
                    <th scope="row">{metric.metric_identifier}</th>
                    <td>
                      {metric.value === null
                        ? "Missing"
                        : metric.value.toFixed(4)}
                    </td>
                    <td>
                      {metric.available_count} / {metric.total_count}
                    </td>
                    <td>{metric.missing_count}</td>
                    <td>{metric.failed_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ResourceSection>
      <div className="workspace-grid">
        <ResourceSection
          heading="Cost"
          pending={costs.isPending}
          error={costs.error}
          empty={costs.isSuccess && costs.data.length === 0}
        >
          {costs.isSuccess &&
            costs.data.map((cost) => (
              <p key={cost.currency}>
                Actual {cost.actual} {cost.currency}; estimated {cost.estimated}{" "}
                {cost.currency} across {cost.record_count} ledger entries.
              </p>
            ))}
        </ResourceSection>
        <ResourceSection
          heading="Errors"
          pending={errors.isPending}
          error={errors.error}
          empty={errors.isSuccess && errors.data.length === 0}
        >
          {errors.isSuccess && (
            <ul>
              {errors.data.map((error) => (
                <li key={`${error.category}-${error.error_kind}`}>
                  {error.category}: {error.error_kind} ({error.count})
                </li>
              ))}
            </ul>
          )}
        </ResourceSection>
      </div>
      <ResourceSection
        heading="Per-record results"
        pending={samples.isPending}
        error={samples.error}
        empty={samples.isSuccess && samples.data.length === 0}
      >
        {samples.isSuccess && (
          <div className="table-scroll">
            <table>
              <caption>
                Individual outputs, failures, latency, and usage
              </caption>
              <thead>
                <tr>
                  <th scope="col">Record</th>
                  <th scope="col">Status</th>
                  <th scope="col">Output or failure</th>
                  <th scope="col">Latency</th>
                  <th scope="col">Tokens</th>
                </tr>
              </thead>
              <tbody>
                {samples.data.map((sample) => (
                  <tr key={sample.id}>
                    <th scope="row">{sample.record_key}</th>
                    <td>
                      <Status value={sample.status} />
                    </td>
                    <td className="output-cell">
                      {sample.response_text ??
                        sample.failure_message ??
                        "No result was recorded."}
                    </td>
                    <td>
                      {sample.latency_ms === null
                        ? "Missing"
                        : `${sample.latency_ms} ms`}
                    </td>
                    <td>
                      {sample.input_tokens === null
                        ? "Missing"
                        : `${sample.input_tokens} in / ${sample.output_tokens ?? 0} out`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ResourceSection>
    </>
  );
}

function ConfidenceIntervalFigure({
  metric,
}: {
  metric: Comparison["metrics"][number];
}) {
  const lower = metric.confidence_interval.lower;
  const upper = metric.confidence_interval.upper;
  const padding = Math.max(Math.abs(lower), Math.abs(upper), 0.01) * 0.2;
  const minimum = Math.min(lower, 0) - padding;
  const maximum = Math.max(upper, 0) + padding;
  const x = (value: number) =>
    15 + ((value - minimum) / (maximum - minimum)) * 270;
  return (
    <figure className="ci-figure">
      <svg
        viewBox="0 0 300 40"
        role="img"
        aria-label={`${metric.metric_identifier}: ${metric.mean_difference.toFixed(4)}, confidence interval ${lower.toFixed(4)} to ${upper.toFixed(4)}`}
      >
        <line className="zero-line" x1={x(0)} x2={x(0)} y1="4" y2="36" />
        <line
          className="interval-line"
          x1={x(lower)}
          x2={x(upper)}
          y1="20"
          y2="20"
        />
        <circle
          className="estimate-point"
          cx={x(metric.mean_difference)}
          cy="20"
          r="5"
        />
      </svg>
      <figcaption>
        Delta {metric.mean_difference.toFixed(4)};{" "}
        {(metric.confidence_interval.confidence * 100).toFixed(0)}% CI [
        {lower.toFixed(4)}, {upper.toFixed(4)}], n={metric.paired_count}.
      </figcaption>
    </figure>
  );
}

function ComparisonPage() {
  const { projectId, comparisonId } = comparisonRoute.useParams();
  const organizationId =
    localStorage.getItem("eval.organization") ?? DEFAULT_ORGANIZATION;
  const comparison = useQuery({
    queryKey: ["comparison", organizationId, projectId, comparisonId],
    queryFn: () => getComparison(organizationId, projectId, comparisonId),
    retry: false,
  });
  const [reporting, setReporting] = useState<string | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  async function downloadReport(format: "json" | "csv" | "markdown" | "html") {
    setReporting(format);
    setReportError(null);
    try {
      const blob = await downloadComparisonReport(
        organizationId,
        projectId,
        comparisonId,
        format,
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `comparison-${comparisonId}.${format === "markdown" ? "md" : format}`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setReportError(
        error instanceof Error ? error.message : "Report export failed",
      );
    } finally {
      setReporting(null);
    }
  }
  if (comparison.isPending) return <p role="status">Loading comparison…</p>;
  if (comparison.isError)
    return (
      <div className="notice error" role="alert">
        {comparison.error.message}
      </div>
    );
  return (
    <>
      <Link to="/projects/$projectId" params={{ projectId }}>
        Return to workspace
      </Link>
      <header>
        <p className="eyebrow">Paired evidence</p>
        <h1>Experiment comparison</h1>
        <p>
          Baseline <code>{comparison.data.baseline_run_id}</code>
          <br />
          Candidate <code>{comparison.data.candidate_run_id}</code>
        </p>
      </header>
      {comparison.data.intersection_only && (
        <div className="notice warning" role="status">
          Dataset versions differ. This analysis uses matching record identities
          only.
        </div>
      )}
      <section aria-labelledby="comparison-metrics">
        <h2 id="comparison-metrics">Metric deltas and uncertainty</h2>
        <div className="comparison-grid">
          {comparison.data.metrics.map((metric) => (
            <article className="card" key={metric.metric_identifier}>
              <h3>{metric.metric_identifier}</h3>
              <ConfidenceIntervalFigure metric={metric} />
              <dl>
                <div>
                  <dt>Baseline</dt>
                  <dd>{metric.baseline_mean.toFixed(4)}</dd>
                </div>
                <div>
                  <dt>Candidate</dt>
                  <dd>{metric.candidate_mean.toFixed(4)}</dd>
                </div>
                <div>
                  <dt>Adjusted p-value</dt>
                  <dd>
                    {metric.adjusted_p_value?.toPrecision(4) ?? "Not computed"}
                  </dd>
                </div>
                <div>
                  <dt>Interpretation</dt>
                  <dd>
                    {metric.practical_interpretation.replaceAll("_", " ")}
                  </dd>
                </div>
              </dl>
              <p>
                Missing: {metric.missing_baseline_count} baseline and{" "}
                {metric.missing_candidate_count} candidate. Failed:{" "}
                {metric.failed_baseline_count} baseline and{" "}
                {metric.failed_candidate_count} candidate.
              </p>
              {metric.warnings.length > 0 && (
                <details>
                  <summary>
                    {metric.warnings.length} statistical warnings
                  </summary>
                  <ul>
                    {metric.warnings.map((warning, index) => (
                      <li key={`${warning.code}-${index}`}>
                        {warning.message}
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </article>
          ))}
        </div>
      </section>
      <section aria-labelledby="limitations">
        <h2 id="limitations">Limitations</h2>
        <ul>
          {comparison.data.limitations.map((limitation) => (
            <li key={limitation}>{limitation}</li>
          ))}
        </ul>
        <div className="inline" aria-label="Export comparison report">
          <span>Reports:</span>
          {(["json", "csv", "markdown", "html"] as const).map((format) => (
            <button
              className="report-link"
              key={format}
              type="button"
              disabled={reporting !== null}
              onClick={() => void downloadReport(format)}
            >
              {reporting === format
                ? `Exporting ${format}…`
                : format.toUpperCase()}
            </button>
          ))}
        </div>
        {reportError && (
          <p className="notice error" role="alert">
            {reportError}
          </p>
        )}
      </section>
    </>
  );
}

function PairwisePage() {
  const { projectId, designId } = pairRoute.useParams();
  const organizationId =
    localStorage.getItem("eval.organization") ?? DEFAULT_ORGANIZATION;
  const aggregate = useQuery({
    queryKey: ["pair-aggregate", organizationId, projectId, designId],
    queryFn: () => getPairAggregate(organizationId, projectId, designId),
    retry: false,
  });
  return (
    <>
      <Link to="/projects/$projectId" params={{ projectId }}>
        Return to workspace
      </Link>
      <header>
        <p className="eyebrow">Blinded judging</p>
        <h1>Pairwise results</h1>
      </header>
      {aggregate.isPending && <p role="status">Loading pairwise outcomes…</p>}
      {aggregate.isError && (
        <div className="notice error" role="alert">
          {aggregate.error.message}
        </div>
      )}
      {aggregate.isSuccess && (
        <>
          <dl className="summary-grid">
            <div>
              <dt>A wins</dt>
              <dd>{aggregate.data.wins_a}</dd>
            </div>
            <div>
              <dt>B wins</dt>
              <dd>{aggregate.data.wins_b}</dd>
            </div>
            <div>
              <dt>Ties</dt>
              <dd>{aggregate.data.ties}</dd>
            </div>
            <div>
              <dt>Abstentions</dt>
              <dd>{aggregate.data.abstentions}</dd>
            </div>
          </dl>
          <p>
            Tie-adjusted A win rate:{" "}
            {aggregate.data.tie_adjusted_a_win_rate?.toFixed(3) ?? "Missing"} (
            n={aggregate.data.usable_count}). Judge disagreement:{" "}
            {aggregate.data.disagreement_rate?.toFixed(3) ?? "Missing"}.
            Display-position A win rate:{" "}
            {aggregate.data.position_a_win_rate?.toFixed(3) ?? "Missing"}.
          </p>
          <p className="notice">
            A and B are presentation positions, not model identities. Position
            effects must be reviewed before interpreting preference.
          </p>
        </>
      )}
    </>
  );
}

function AuditPage() {
  const { projectId } = auditRoute.useParams();
  const organizationId =
    localStorage.getItem("eval.organization") ?? DEFAULT_ORGANIZATION;
  const audit = useQuery({
    queryKey: ["audit", organizationId, projectId],
    queryFn: () => listAuditEvents(organizationId, projectId),
    retry: false,
  });
  return (
    <>
      <Link to="/projects/$projectId" params={{ projectId }}>
        Return to workspace
      </Link>
      <header>
        <p className="eyebrow">Administrator view</p>
        <h1>Audit log</h1>
      </header>
      {audit.isPending && <p role="status">Loading audit events…</p>}
      {audit.isError && (
        <div className="notice error" role="alert">
          <h2>Audit log unavailable</h2>
          <p>
            {audit.error.message}. This view requires the project audit-read
            permission.
          </p>
        </div>
      )}
      {audit.isSuccess && audit.data.length === 0 && (
        <p className="notice">No audit events are available.</p>
      )}
      {audit.isSuccess && audit.data.length > 0 && (
        <div className="table-scroll">
          <table>
            <caption>Append-only hash-chained project events</caption>
            <thead>
              <tr>
                <th scope="col">Sequence</th>
                <th scope="col">Action</th>
                <th scope="col">Actor</th>
                <th scope="col">Target</th>
                <th scope="col">Event hash</th>
              </tr>
            </thead>
            <tbody>
              {audit.data.map((event) => (
                <tr key={event.id}>
                  <th scope="row">{event.sequence}</th>
                  <td>{event.action}</td>
                  <td>{event.actor_subject}</td>
                  <td>
                    {event.target_type} {event.target_id}
                  </td>
                  <td className="resource-id">{event.event_hash}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function RootLayout() {
  return (
    <div className="shell">
      <nav aria-label="Primary">
        <Link className="brand" to="/">
          LLM Eval
        </Link>
        <span>Evidence over intuition</span>
      </nav>
      <main id="main">
        <Outlet />
      </main>
    </div>
  );
}

const rootRoute = createRootRoute({ component: RootLayout });
const projectsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ProjectsPage,
});
const projectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId",
  component: ProjectPage,
});
const datasetRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/datasets/$datasetId",
  component: DatasetPage,
});
const runRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/runs/$runId",
  component: RunPage,
});
const comparisonRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/comparisons/$comparisonId",
  component: ComparisonPage,
});
const pairRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/pairs/$designId",
  component: PairwisePage,
});
const auditRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/audit",
  component: AuditPage,
});
const routeTree = rootRoute.addChildren([
  projectsRoute,
  projectRoute,
  datasetRoute,
  runRoute,
  comparisonRoute,
  pairRoute,
  auditRoute,
]);

export function createAppRouter(history?: RouterHistory) {
  return createRouter({ routeTree, history });
}

export type AppRouter = ReturnType<typeof createAppRouter>;

declare module "@tanstack/react-router" {
  interface Register {
    router: AppRouter;
  }
}

interface AppProps {
  router: AppRouter;
}

export function App({ router }: AppProps) {
  return <RouterProvider router={router} />;
}
