import { z } from "zod";

const projectSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  slug: z.string(),
  name: z.string(),
  budget_amount: z.string(),
  budget_currency: z.string(),
  concurrency_limit: z.number().int(),
  version_stamp: z.number().int(),
});

const projectPageSchema = z.object({
  items: z.array(projectSchema),
  page: z.object({ next_cursor: z.string().nullable(), limit: z.number() }),
});

export type Project = z.infer<typeof projectSchema>;

const datasetSchema = z.object({
  id: z.string().uuid(),
  organization_id: z.string().uuid(),
  project_id: z.string().uuid(),
  slug: z.string(),
  name: z.string(),
  description: z.string(),
  tags: z.array(z.string()),
});

const datasetPageSchema = z.object({
  items: z.array(datasetSchema),
  page: z.object({ next_cursor: z.string().nullable(), limit: z.number() }),
});

const datasetVersionSchema = z.object({
  id: z.string().uuid(),
  dataset_id: z.string().uuid(),
  version_number: z.number().int(),
  state: z.string(),
  schema_name: z.string(),
  schema_version: z.string(),
  canonicalization_version: z.string(),
  content_hash: z.string(),
  record_count: z.number().int(),
  duplicate_payload_count: z.number().int(),
  split_counts: z.record(z.string(), z.number().int()),
  parent_version_ids: z.array(z.string().uuid()),
});

const datasetVersionPageSchema = z.object({
  items: z.array(datasetVersionSchema),
  page: z.object({ next_cursor: z.string().nullable(), limit: z.number() }),
});

const datasetDiffSchema = z.object({
  source_version_id: z.string().uuid(),
  target_version_id: z.string().uuid(),
  counts: z.record(z.string(), z.number().int()),
  records: z.array(
    z.object({
      key: z.string(),
      kind: z.string(),
      changes: z.array(
        z.object({
          pointer: z.string(),
          before: z.unknown(),
          after: z.unknown(),
        }),
      ),
    }),
  ),
});

const metricSchema = z.object({
  identifier: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string(),
  task_types: z.array(z.string()),
  direction: z.string(),
  determinism: z.string(),
  reference_required: z.boolean(),
});

export type Dataset = z.infer<typeof datasetSchema>;
export type DatasetVersion = z.infer<typeof datasetVersionSchema>;
export type DatasetDiff = z.infer<typeof datasetDiffSchema>;
export type MetricDefinition = z.infer<typeof metricSchema>;

const runSchema = z.object({
  id: z.string().uuid(),
  experiment_id: z.string().uuid(),
  state: z.string(),
  total_tasks: z.number().int(),
  succeeded_tasks: z.number().int(),
  failed_tasks: z.number().int(),
  cancelled_tasks: z.number().int(),
  pending_tasks: z.number().int(),
  version_stamp: z.number().int(),
});

const runPageSchema = z.object({
  items: z.array(runSchema),
  page: z.object({ next_cursor: z.string().nullable(), limit: z.number() }),
});

const aggregateSchema = z.object({
  metric_identifier: z.string(),
  metric_version: z.string(),
  slice_key: z.string(),
  value: z.number().nullable(),
  total_count: z.number().int(),
  available_count: z.number().int(),
  missing_count: z.number().int(),
  failed_count: z.number().int(),
  pending_count: z.number().int(),
});

const sampleSchema = z.object({
  id: z.string().uuid(),
  task_id: z.string().uuid(),
  record_key: z.string(),
  status: z.string(),
  latency_ms: z.number().int().nullable(),
  response_text: z.string().nullable(),
  model: z.string().nullable(),
  input_tokens: z.number().int().nullable(),
  output_tokens: z.number().int().nullable(),
  failure_category: z.string().nullable(),
  failure_message: z.string().nullable(),
});

const samplePageSchema = z.object({
  items: z.array(sampleSchema),
  page: z.object({ next_cursor: z.string().nullable(), limit: z.number() }),
});

const costSchema = z.object({
  currency: z.string(),
  actual: z.string(),
  estimated: z.string(),
  record_count: z.number().int(),
});

const errorSchema = z.object({
  category: z.string(),
  error_kind: z.string(),
  count: z.number().int(),
});

const intervalSchema = z.object({
  lower: z.number(),
  upper: z.number(),
  confidence: z.number(),
  method: z.string(),
});

const metricComparisonSchema = z.object({
  metric_identifier: z.string(),
  metric_version: z.string(),
  baseline_mean: z.number(),
  candidate_mean: z.number(),
  mean_difference: z.number(),
  median_difference: z.number(),
  relative_improvement: z.number().nullable(),
  probability_of_superiority: z.number(),
  standardized_mean_difference: z.number().nullable(),
  confidence_interval: intervalSchema,
  p_value: z.number(),
  adjusted_p_value: z.number().nullable(),
  test_method: z.string(),
  total_union_count: z.number().int(),
  paired_count: z.number().int(),
  missing_baseline_count: z.number().int(),
  missing_candidate_count: z.number().int(),
  failed_baseline_count: z.number().int(),
  failed_candidate_count: z.number().int(),
  practical_interpretation: z.string(),
  warnings: z.array(z.object({ code: z.string(), message: z.string() })),
  largest_improvements: z.array(z.record(z.string(), z.unknown())),
  largest_regressions: z.array(z.record(z.string(), z.unknown())),
});

const comparisonSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  baseline_run_id: z.string().uuid(),
  candidate_run_id: z.string().uuid(),
  baseline_dataset_version_id: z.string().uuid(),
  candidate_dataset_version_id: z.string().uuid(),
  dataset_compatible: z.boolean(),
  intersection_only: z.boolean(),
  configuration: z.record(z.string(), z.unknown()),
  metrics: z.array(metricComparisonSchema),
  limitations: z.array(z.string()),
});

const pairDesignSchema = z.object({
  id: z.string().uuid(),
  project_id: z.string().uuid(),
  name: z.string(),
  seed: z.number().int(),
  assignment_count: z.number().int(),
  reversed_duplicates: z.boolean(),
  assignments: z.array(z.unknown()).default([]),
});

const pairAggregateSchema = z.object({
  assignment_count: z.number().int(),
  judgment_count: z.number().int(),
  wins_a: z.number().int(),
  wins_b: z.number().int(),
  ties: z.number().int(),
  abstentions: z.number().int(),
  usable_count: z.number().int(),
  tie_adjusted_a_win_rate: z.number().nullable(),
  disagreement_rate: z.number().nullable(),
  position_a_win_rate: z.number().nullable(),
});

const auditEventSchema = z.object({
  id: z.string().uuid(),
  sequence: z.number().int(),
  project_id: z.string().uuid().nullable(),
  actor_subject: z.string(),
  action: z.string(),
  target_type: z.string(),
  target_id: z.string().uuid().nullable(),
  outcome: z.string(),
  request_id: z.string(),
  summary: z.record(z.string(), z.unknown()),
  previous_hash: z.string().nullable(),
  event_hash: z.string(),
});

const auditPageSchema = z.object({
  items: z.array(auditEventSchema),
  page: z.object({ next_cursor: z.string().nullable(), limit: z.number() }),
});

export type Run = z.infer<typeof runSchema>;
export type Aggregate = z.infer<typeof aggregateSchema>;
export type Sample = z.infer<typeof sampleSchema>;
export type Comparison = z.infer<typeof comparisonSchema>;
export type PairDesign = z.infer<typeof pairDesignSchema>;

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson(path: string, organizationId: string): Promise<unknown> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "X-Organization-ID": organizationId },
  });
  if (!response.ok) {
    const body: unknown = await response.json();
    const message =
      typeof body === "object" && body !== null && "message" in body
        ? String(body.message)
        : `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return response.json();
}

export async function listProjects(organizationId: string): Promise<Project[]> {
  return projectPageSchema.parse(
    await getJson("/api/v1/projects?limit=100", organizationId),
  ).items;
}

export async function listDatasets(
  organizationId: string,
  projectId: string,
): Promise<Dataset[]> {
  return datasetPageSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/datasets?limit=100`,
      organizationId,
    ),
  ).items;
}

export async function listMetrics(
  organizationId: string,
): Promise<MetricDefinition[]> {
  return z
    .array(metricSchema)
    .parse(await getJson("/api/v1/metrics", organizationId));
}

export async function listDatasetVersions(
  organizationId: string,
  projectId: string,
  datasetId: string,
): Promise<DatasetVersion[]> {
  return datasetVersionPageSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}/versions?limit=100`,
      organizationId,
    ),
  ).items;
}

export async function getDatasetDiff(
  organizationId: string,
  projectId: string,
  datasetId: string,
  source: string,
  target: string,
): Promise<DatasetDiff> {
  const query = new URLSearchParams({ source, target });
  return datasetDiffSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(datasetId)}/diff?${query.toString()}`,
      organizationId,
    ),
  );
}

export async function listRuns(
  organizationId: string,
  projectId: string,
): Promise<Run[]> {
  return runPageSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/runs?limit=100`,
      organizationId,
    ),
  ).items;
}

export async function getRun(
  organizationId: string,
  projectId: string,
  runId: string,
): Promise<Run> {
  return runSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}`,
      organizationId,
    ),
  );
}

export async function getRunAggregates(
  organizationId: string,
  projectId: string,
  runId: string,
): Promise<Aggregate[]> {
  return z
    .array(aggregateSchema)
    .parse(
      await getJson(
        `/api/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/aggregates`,
        organizationId,
      ),
    );
}

export async function getRunSamples(
  organizationId: string,
  projectId: string,
  runId: string,
): Promise<Sample[]> {
  return samplePageSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/results?limit=100`,
      organizationId,
    ),
  ).items;
}

export async function getRunCosts(
  organizationId: string,
  projectId: string,
  runId: string,
) {
  return z
    .array(costSchema)
    .parse(
      await getJson(
        `/api/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/costs`,
        organizationId,
      ),
    );
}

export async function getRunErrors(
  organizationId: string,
  projectId: string,
  runId: string,
) {
  return z
    .array(errorSchema)
    .parse(
      await getJson(
        `/api/v1/projects/${encodeURIComponent(projectId)}/runs/${encodeURIComponent(runId)}/errors`,
        organizationId,
      ),
    );
}

export async function listComparisons(
  organizationId: string,
  projectId: string,
): Promise<Comparison[]> {
  return z
    .array(comparisonSchema)
    .parse(
      await getJson(
        `/api/v1/projects/${encodeURIComponent(projectId)}/comparisons`,
        organizationId,
      ),
    );
}

export async function getComparison(
  organizationId: string,
  projectId: string,
  comparisonId: string,
): Promise<Comparison> {
  return comparisonSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/comparisons/${encodeURIComponent(comparisonId)}`,
      organizationId,
    ),
  );
}

export async function downloadComparisonReport(
  organizationId: string,
  projectId: string,
  comparisonId: string,
  format: "json" | "csv" | "markdown" | "html",
): Promise<Blob> {
  const query = new URLSearchParams({ format });
  const response = await fetch(
    `${API_BASE}/api/v1/projects/${encodeURIComponent(projectId)}/comparisons/${encodeURIComponent(comparisonId)}/report?${query.toString()}`,
    { headers: { "X-Organization-ID": organizationId } },
  );
  if (!response.ok) {
    throw new Error(`Report export failed with status ${response.status}`);
  }
  return response.blob();
}

export async function listPairDesigns(
  organizationId: string,
  projectId: string,
): Promise<PairDesign[]> {
  return z
    .array(pairDesignSchema)
    .parse(
      await getJson(
        `/api/v1/projects/${encodeURIComponent(projectId)}/pair-designs`,
        organizationId,
      ),
    );
}

export async function getPairAggregate(
  organizationId: string,
  projectId: string,
  designId: string,
) {
  return pairAggregateSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/pair-designs/${encodeURIComponent(designId)}/aggregate`,
      organizationId,
    ),
  );
}

export async function listAuditEvents(
  organizationId: string,
  projectId: string,
) {
  return auditPageSchema.parse(
    await getJson(
      `/api/v1/projects/${encodeURIComponent(projectId)}/audit-events?limit=100`,
      organizationId,
    ),
  ).items;
}
