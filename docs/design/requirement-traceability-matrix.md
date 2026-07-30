# Requirement traceability matrix

**Baseline:** User specification received 2026-07-29  
**Status vocabulary:** `Designed`, `Planned`, `Implemented`, `Verified`  
**Rule:** A requirement is accepted only when its implementation, documentation,
and behavioral test evidence all exist. A file in backticks marked “planned” is
created in its assigned phase; it is not claimed to exist in Phase 1.

## Implementation status

The row-by-row baseline below preserves the original ten-phase design mapping.
Current implementation evidence lives beside each feature in source, tests,
documentation, CI workflows, and reproducible examples. A broad requirement is
not accepted merely because one vertical slice exists.

Verified during the delta are the clean dependency direction and static gates,
UUIDv7/money/error primitives, canonicalization and hashing golden properties,
dataset publication/diff/sampling, the complete run transition graph, fake and
HTTP provider contracts, metric metadata/result/failure isolation, core lexical
and retrieval formulas, non-paid deterministic execution, migrations,
documentation, and frontend/package builds. Requirements involving full
identity/audit workflows, staged imports, distributed concurrency, every
metric wrapper, pairwise judges, statistics, reporting, Kubernetes, and the
complete security/operations program remain `Designed` or partially
implemented.

Implemented and executed requirements include deterministic balanced/blinded
pairing, strict judge schemas and trust boundaries, repetitions/repair/
aggregation/calibration diagnostics, paired missingness alignment, the listed
core intervals/tests/effects/corrections/power/TOST/ranking point estimates,
stored comparisons, four safe report formats, CI gate exits, analysis/access
APIs, SDK/CLI/dashboard result views, Compose/Kubernetes/monitoring/security
assets, real dependency tests, empty-database migrations, non-root images,
browser evidence, and a no-paid-provider baseline/candidate/report demo.

Rows requiring independent registries for every system type, durable staged
million-record imports, automatic partition/retention/archive jobs, worker-
scheduled model judging for every mode, the complete dashboard authoring
surface, ranking-parameter bootstrap, or the full eleven-step live browser and
managed-cluster recovery program remain only partially accepted.

This matrix decomposes every numbered section of the specification into
independently verifiable capabilities. Repeated requirements share evidence only
when their acceptance behavior is identical.

## A. Mission, engineering standard, and structure

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| MIS-01 | Create/import/validate/version/tag/branch/compare datasets | P3 dataset registry | `docs/concepts/dataset-design.md`, `docs/guides/datasets.md` (planned) | Unit, property, integration, E2E | API and CLI can execute the lifecycle; published bytes/hash remain immutable; diff classifies every key | Designed |
| MIS-02 | Register all systems and evaluation configuration | P4 config registry | `docs/guides/system-configurations.md` (planned) | Unit, API, E2E | Immutable versions exist for models, prompts, providers, retrievers, embeddings, RAG, agents, tools, and judges | Designed |
| MIS-03 | Reproducible asynchronous evaluation | P4 orchestrator/worker | `docs/architecture/evaluation-engine.md` (planned) | State, integration, E2E | Fake-provider run survives worker interruption and reproduces from recorded snapshot | Designed |
| MIS-04 | Pointwise, pairwise, and rubric outputs | P5–P6 evaluator/judge engines | `docs/concepts/evaluation-modes.md` (planned) | Unit, contract, E2E | One suite runs each mode and stores typed per-sample and aggregate results | Designed |
| MIS-05 | Deterministic and nondeterministic systems | P4 sampling/repetition model | `docs/concepts/determinism.md` (planned) | Unit, property, integration | Repetitions and seeds are explicit; repeated fake runs match while stochastic runs retain each replicate | Designed |
| MIS-06 | Code and model metrics | P5 metric plugins; P6 judges | `docs/guides/custom-metrics.md`, `docs/guides/judges.md` (planned) | Contract, unit, E2E | Both plugin types satisfy versioned schemas and isolated failure behavior | Designed |
| MIS-07 | Uncertainty and paired comparisons | P7 statistics | `docs/statistics/index.md` (planned) | Hand, library, property, simulation | Paired deltas include effective n, interval, effect, test, missingness, and warnings | Designed |
| MIS-08 | Track operations and inspect records/aggregates | P4 runs; P8 dashboard | `docs/guides/results.md` (planned) | Integration, UI, E2E | Latency/tokens/cost/failures/retries appear per record and in aggregates without hiding missing values | Designed |
| MIS-09 | Machine- and human-readable reports | P8 reporting | `docs/guides/reports.md` (planned) | Golden, security, E2E | Same frozen comparison exports valid JSON, safe CSV, Markdown, and printable HTML | Designed |
| MIS-10 | Historical reproduction from immutable inputs | P4 snapshots/reproduction | `docs/concepts/reproducibility.md` (planned) | Integration, E2E | Reproduction resolves no mutable alias and records linkage plus environment drift | Designed |
| MIS-11 | Safe multi-user production operation | P2/P9 IAM and operations | `docs/architecture/multi-tenancy.md`, `docs/security/threat-model.md` (planned) | Authorization, security, deployment | Cross-project access is denied at application and RLS layers; production manifests use secure defaults | Designed |
| ENG-01 | Clean architecture, separation, inversion, explicit contracts | P2 package boundaries/ports | Phase 1 design §4; focused ADRs (planned) | Import architecture, type | Domain imports no delivery/infrastructure/vendor packages | Designed |
| ENG-02 | Types, validation, errors, focused code | P2 shared foundation; all phases | `docs/guides/development.md` (planned) | MyPy, schema, unit | Strict package type checks pass; all boundaries validate; stable structured errors cover expected failures | Designed |
| ENG-03 | Idempotency and transactional integrity | P2 idempotency/outbox; P3–P4 use cases | `docs/architecture/idempotency.md` (planned) | Integration, fault injection | Duplicate requests/tasks produce one logical effect and state/event commits cannot diverge | Designed |
| ENG-04 | Reproducibility and auditability | P2 audit; P3–P8 provenance | `docs/concepts/reproducibility.md`, `docs/security/audit.md` (planned) | Unit, integration, E2E | Every result resolves immutable versions, seeds, code/dependency provenance, actor, and audit events | Designed |
| ENG-05 | Logging, tracing, metrics, health | P2 observability | `docs/operations/observability.md` (planned) | Unit, integration, smoke | Correlated safe JSON logs, cross-process traces, Prometheus metrics, and distinct probes are observable | Designed |
| ENG-06 | Secure secret handling | P2 settings/secrets; P9 KMS guidance | `docs/security/secrets.md` (planned) | Security, log scan | No plaintext provider secret persists or appears in logs; references resolve at call time | Designed |
| ENG-07 | Safe concurrency and horizontal scale | P4 leases/limits/backpressure | `docs/architecture/scaling.md` (planned) | Fault, concurrency, performance | Competing workers do not commit duplicate successes or exceed configured dispatch/concurrency bounds | Designed |
| ENG-08 | Migrations and compatible API evolution | P2 Alembic/API versioning | `docs/operations/migrations.md`, `docs/api/compatibility.md` (planned) | Migration, schema diff | One migration head upgrades cleanly; breaking OpenAPI changes fail CI or follow deprecation policy | Designed |
| ENG-09 | Retry, timeout, rate, cost controls | P4 provider execution policies | `docs/operations/provider-outages.md`, `docs/operations/cost-incidents.md` (planned) | Unit, contract, fault | Only retryable classes retry within all budgets; limits and cancellation stop further calls | Designed |
| ENG-10 | Graceful shutdown, recovery, DR | P4 worker lifecycle; P9 operations | `docs/operations/disaster-recovery.md` (planned) | Integration, restore drill | Shutdown stops leases safely; expired work resumes; documented backup restores within stated objectives | Designed |
| ENG-11 | No unfinished placeholders or fake tests | All phases | `CONTRIBUTING.md` (planned) | Repository scan, review | Placeholder scan is clean and tests contain outcome assertions/mutation-sensitive cases | Designed |
| STR-01 | Required monorepo separation | P2 repository foundation | Phase 1 design §12 | Import architecture, repository smoke | All planned top-level concerns exist and dependencies follow declared direction | Designed |

## B. Domain and dataset registry

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| DOM-01 | Organization, project, user, role, service account/API key, audit | P2 IAM/audit aggregates | `docs/architecture/domain-model.md` (planned) | Unit, API, security | Each entity has stable ID, lifecycle, constraints, scoped CRUD, and audit behavior | Designed |
| DOM-02 | Organization/project RBAC | P2 authorization policy + RLS | `docs/architecture/multi-tenancy.md` (planned) | Policy matrix, integration, security | Every protected action has allow/deny tests including cross-project and reduced key scopes | Designed |
| DOM-03 | Dataset entity family | P3 dataset aggregates | `docs/architecture/domain-model.md` (planned) | Unit, persistence, API | Dataset/version/record/schema/split/tag/lineage/import/validation have relationships and invariants specified in Phase 1 §6–7 | Designed |
| DOM-04 | Suite/case/metric/rubric/judge/sampling/statistics configs | P4–P7 versioned config registry | `docs/architecture/domain-model.md` (planned) | Unit, API, immutability | Published suite resolves compatible immutable versions for every reference | Designed |
| DOM-05 | Model/provider/prompt/RAG/retriever/embedding/agent/tool/SUT | P4 system configuration | `docs/architecture/domain-model.md` (planned) | Unit, API, snapshot | Snapshot is secret-free, immutable, content-hashed, and sufficient to reproduce calls | Designed |
| DOM-06 | Complete execution entity family | P4–P8 run/results schemas | `docs/architecture/domain-model.md` (planned) | Migration, integration, E2E | All requested response/trace/trajectory/invocation/result/artifact/cost/failure entities persist and link to exact sample/task | Designed |
| DOM-07 | Aggregate boundaries, invariants, transitions, ownership, deletion | P1 design; implemented P2–P4 | Phase 1 design §6 | State/property/integration | Illegal states/FKs/deletes fail; legal lifecycle and retention workflows pass | Designed |
| DOM-08 | Sortable stable IDs | P2 UUIDv7 value object | Focused ID ADR (planned) | Unit, property, concurrency | IDs are valid UUIDv7, unique under concurrent generation, and monotonically sortable per generator | Designed |
| DSET-01 | Import API, JSON, JSONL, CSV, Parquet | P3 streaming parsers | `docs/guides/creating-datasets.md` (planned) | Golden, property, integration | Equivalent fixtures from all five inputs produce the same canonical version hash | Designed |
| DSET-02 | Versioned schema validation and reports | P3 schema registry/validator | `docs/guides/custom-dataset-schemas.md` (planned) | Unit, API, E2E | Invalid fields yield dataset/record errors with stable locations; valid version publishes | Designed |
| DSET-03 | Immutable versions and mutation prevention after use | P3 immutable repository/triggers | Immutability ADR (planned) | Unit, DB constraint, security | Published content update fails regardless of experiment use; new content requires new version | Designed |
| DSET-04 | Canonical hashes and duplicate detection | P3 canonicalization/dedupe | `docs/concepts/dataset-canonicalization.md` (planned) | Golden, property, cross-format | Phase 1 §7.4 rules hold and duplicate policy/report is deterministic | Designed |
| DSET-05 | Standard/custom splits | P3 split entities | `docs/guides/datasets.md` (planned) | Unit, API | Train/validation/test/challenge/custom names work; membership and overlap policy validate | Designed |
| DSET-06 | Tags and aliases | P3 catalog metadata | `docs/guides/versioning-datasets.md` (planned) | Unit, API | Alias uniqueness is project-scoped; tags do not mutate version content | Designed |
| DSET-07 | Record source, lineage, transformations, filters | P3 provenance graph | `docs/concepts/dataset-lineage.md` (planned) | Unit, integration | Each derived record/version resolves source, parents, transformation digest/params/actor/seed | Designed |
| DSET-08 | Dataset version diff | P3 streaming merge diff | `docs/guides/dataset-diffs.md` (planned) | Unit, property, performance | Added/removed/modified/unchanged partition the union; field diffs and symmetry properties hold | Designed |
| DSET-09 | Exact historical export | P3 export service | `docs/guides/exporting-datasets.md` (planned) | Golden, integration | Exported manifest, schema, records, and hashes reproduce the selected version | Designed |
| DSET-10 | Dataset/record metadata and sensitive fields | P3 schema annotations/redaction | `docs/security/data-classification.md` (planned) | Unit, security, UI | JSON-pointer sensitivity policy consistently redacts preview/log/judge/export destinations | Designed |
| DSET-11 | Soft delete and retention | P3/P9 deletion workflow | `docs/operations/data-deletion.md` (planned) | Unit, integration, recovery | Soft-deleted objects are hidden; hard delete honors references/legal holds and verifies S3/database erasure | Designed |
| DSET-12 | Branch/new version from existing | P3 transformation/version service | `docs/guides/versioning-datasets.md` (planned) | Integration, E2E | Parent remains unchanged and child records complete lineage and deterministic hash | Designed |
| DSET-13 | Deterministic and stratified sampling | P3 sampling policy | `docs/concepts/sampling.md` (planned) | Unit, property | Same seed/strata/input returns same ordered sample; quotas and underfill are reported | Designed |
| DSET-14 | Dataset- and record-level validation | P3 validation report | `docs/guides/validating-datasets.md` (planned) | Unit, integration, UI | Reports aggregate counts and retain bounded record errors with stable codes | Designed |
| CAN-01 | Key ordering, whitespace, and line-ending stability | P3 canonicalizer | `docs/concepts/dataset-canonicalization.md` (planned) | Golden, property | Semantically equal object orders/whitespace/CRLF/CR/LF hash equally | Designed |
| CAN-02 | Timestamp normalization | P3 schema-aware canonicalizer | Same as CAN-01 | Golden, property | Equivalent RFC3339 offsets hash equally; ambiguous/invalid timestamps reject | Designed |
| CAN-03 | Unicode normalization | P3 canonicalizer | Same as CAN-01 | Golden, property, security | NFC-equivalent keys/values hash equally and normalized key collisions reject | Designed |
| CAN-04 | Float representation | P3 RFC8785 serializer | Same as CAN-01 | Golden, property, library cross-check | Finite interoperable numbers serialize stably; negative zero normalizes; NaN/Inf reject | Designed |
| CAN-05 | Null/absent optional equivalence | P3 schema projection | Same as CAN-01 | Golden, property | Optional nullable absent/null hash equally; other semantic differences remain distinct | Designed |
| SCH-01 | General generation, QA, classification, summarization, extraction schemas | P3 built-in schemas | `docs/guides/custom-dataset-schemas.md` (planned) | Schema contract, examples | Each built-in accepts valid example and rejects task-specific missing/invalid fields | Designed |
| SCH-02 | RAG, preference, agent, multi-turn schemas | P3 built-in schemas | Same as SCH-01 | Schema contract, examples | Each complex task schema validates required structured traces/labels/conversations | Designed |
| SCH-03 | Validated custom JSON Schema | P3 safe schema compiler | Same as SCH-01 | Unit, security | Unsupported/pathological schema features and resource exhaustion are bounded; allowed schemas work | Designed |
| LEAK-01 | Near duplicate, n-gram, MinHash/LSH | P3 contamination scanners | `docs/concepts/leakage.md` (planned) | Unit, property, performance | Known overlaps are detected at configured thresholds with false-positive/negative limitations | Designed |
| LEAK-02 | Embedding similarity interface | P3/P5 scanner adapter | `docs/concepts/leakage.md` (planned) | Contract, fake integration | Scanner works with fake embeddings and records model/version/threshold | Designed |
| LEAK-03 | Split contamination and reference leakage | P3 reports | `docs/concepts/leakage.md` (planned) | Golden, E2E | Seeded contamination fixtures appear with evidence and never claim proof of absence | Designed |

## C. Evaluation engine and providers

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| RUN-01 | Immutable experiment config and version resolution | P4 experiment service | `docs/architecture/evaluation-engine.md` (planned) | Unit, integration | Creation fails on drafts/missing versions; persisted canonical snapshot cannot change | Designed |
| RUN-02 | One or more tasks per record with bounded fan-out | P4 dispatcher | `docs/architecture/scaling.md` (planned) | Integration, concurrency, performance | Unique task cardinality matches sampling/repetitions and queue window never exceeds limit | Designed |
| RUN-03 | Provider/project concurrency and rate limits | P4 limiter/dispatcher | `docs/operations/scaling-workers.md` (planned) | Unit, concurrent integration | Observed simultaneous calls stay within both limits and 429 delays honor policy | Designed |
| RUN-04 | Backoff, jitter, timeout, retry classification | P4 execution policy | `docs/architecture/provider-contract.md` (planned) | Unit, contract, seeded timing | Retryable matrix and capped full-jitter ranges match config; terminal failures call once | Designed |
| RUN-05 | Provider idempotency/ambiguous billing | P4 request identity | `docs/concepts/costs.md` (planned) | Contract, fault injection | Stable key is reused where safe; unsupported ambiguous outcomes are labeled and charged conservatively | Designed |
| RUN-06 | Partial progress and resume | P4 durable tasks/leases | `docs/operations/stuck-runs.md` (planned) | Worker crash integration | Committed samples persist; only unresolved retryable tasks resume; counters reconcile | Designed |
| RUN-07 | Pause and cancel queued/active work | P4 run control | `docs/guides/runs.md` (planned) | State, integration, E2E | No new work dispatches; cooperative active tasks settle; legal final state and costs remain | Designed |
| RUN-08 | Stable failure taxonomy | P4 domain errors/failure records | `docs/concepts/evaluation-failures.md` (planned) | Unit, contract, UI | Cancellation, timeout, provider, invalid output, metric, judge, infrastructure are distinguishable end-to-end | Designed |
| RUN-09 | Fail-fast and continue-on-error | P4 run policy | `docs/guides/runs.md` (planned) | Integration | Identical induced failure stops pending work in fail-fast and permits independent samples otherwise | Designed |
| RUN-10 | Seeds and complete provenance | P4 snapshot/environment recorder | `docs/concepts/reproducibility.md` (planned) | Unit, E2E | Report resolves seed, app/dependency/image, prompts, judges, params, and provider request IDs | Designed |
| RUN-11 | Durable streamed progress | P4 events/SSE | `docs/api/progress-stream.md` (planned) | API reconnect, E2E | Reconnect from last event receives no gap/duplicate semantic transition and final DB state wins | Designed |
| RUN-12 | Project budgets/token limits and estimates | P4 budget ledger | `docs/concepts/costs.md` (planned) | Unit, concurrent integration, security | Atomic reservations prevent overspend; estimate is shown; actual usage reconciles or flags uncertainty | Designed |
| RUN-13 | Dry-run validation | P4 preflight use case | `docs/guides/runs.md` (planned) | API, CLI | Dry run checks references/capabilities/schema/sample/cost without tasks or provider calls | Designed |
| RUN-14 | Required run state machine | P4 run aggregate/constraints | Phase 1 design §6.4 | Exhaustive unit, DB concurrency | All and only diagrammed transitions succeed; terminal records cannot reopen | Designed |
| RUN-15 | Reproduction inputs and provider limitation disclosure | P4 reproduce service | `docs/concepts/reproducibility.md` (planned) | E2E, report golden | New run uses exact stored inputs and visibly reports provider-side nondeterminism limits | Designed |
| PROV-01 | Generation, chat, structured output, embeddings | P4 provider port | `docs/guides/custom-providers.md` (planned) | Shared provider contract | Every adapter passes supported operations and returns normalized result schema | Designed |
| PROV-02 | Token count/estimate, capabilities, usage, tracing | P4 provider port/adapters | Same as PROV-01 | Contract | Adapter declares support, provides estimate/fallback, normalizes usage, and propagates trace/request ID | Designed |
| PROV-03 | Stable normalized provider errors | P4 provider error mapper | `docs/architecture/provider-contract.md` (planned) | Contract matrix | All ten specified error classes and retryability map consistently with sanitized messages | Designed |
| PROV-04 | Deterministic fake provider | P4 fake adapter | `docs/testing/fake-provider.md` (planned) | Contract, E2E | Scripted outputs/errors/usage/timing repeat exactly without network or paid key | Designed |
| PROV-05 | OpenAI-compatible adapter | P4 HTTP adapter | `docs/guides/providers.md` (planned) | Fake-server contract | Adapter interoperates with fixture server for all declared capabilities and error cases | Designed |
| PROV-06 | Local/self-hosted adapter | P4 local OpenAI-compatible profile | Same as PROV-05 | Fake-server contract, SSRF security | Allowlisted local endpoint works; unsafe destination fails policy | Designed |
| PROV-07 | Configurable generic HTTP adapter | P4 templated safe HTTP adapter | Same as PROV-05 | Schema, contract, SSRF security | Allowlisted request/response mappings work without arbitrary code/header secret exposure | Designed |
| PROV-08 | No core vendor SDK coupling | P2/P4 dependency boundaries | Provider ADR (planned) | Import architecture | Domain/application import graph contains no vendor SDK/provider implementation | Designed |

## D. Metric framework

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| MET-01 | Complete versioned metric metadata contract | P5 plugin API/registry | `docs/guides/custom-metrics.md` (planned) | Contract, schema | Plugin declares all specified identity/input/output/direction/range/reference/model/determinism/aggregate/failure/config/cost fields | Designed |
| MET-02 | Scalar, label, structured, explanation, metadata results | P5 result schemas | `docs/concepts/metrics.md` (planned) | Schema, API/UI | Each result kind round-trips and validates without conflating null and zero | Designed |
| MET-03 | Per-metric failure isolation | P5 executor/savepoints | `docs/architecture/metric-engine.md` (planned) | Fault integration | One plugin exception stores metric failure while sibling metrics and sample remain valid | Designed |
| LM-01 | Exact, normalized, and case-insensitive match | P5 lexical metrics | `docs/api/metrics/language.md` (planned) | Table, property | Unicode/normalization/case fixtures return specified scores and ranges | Designed |
| LM-02 | Token precision, recall, F1 | P5 token metrics | Same as LM-01 | Hand, property | Counts and zero-denominator policy match documented examples; scores stay in [0,1] | Designed |
| LM-03 | Classification accuracy, macro/micro/weighted PRF, confusion matrix | P5 classification metrics | Same as LM-01 | sklearn/reference, property | Known multiclass examples and absent-class policies match references | Designed |
| LM-04 | Multilabel metrics | P5 classification metrics | Same as LM-01 | Reference, property | Exact/subset and label/sample averaging modes match declared definitions | Designed |
| LM-05 | ROUGE variants and BLEU | P5 text metrics | `docs/concepts/lexical-metrics.md` (planned) | Published examples, library contract | Scores match pinned trusted implementation; tokenization/smoothing/version recorded | Designed |
| LM-06 | CER, WER, edit distance | P5 edit metrics | `docs/api/metrics/language.md` (planned) | Hand, property | Dynamic-programming counts and empty-reference denominators match specification | Designed |
| LM-07 | JSON validity/schema/field accuracy | P5 structured metrics | `docs/api/metrics/structured.md` (planned) | Schema, property, security | Malformed, duplicate-key, wrong-type, nested-field fixtures yield auditable structured errors/scores | Designed |
| LM-08 | Regex/rule criteria | P5 safe rule metrics | Same as LM-07 | Unit, ReDoS security | Anchoring/match policy works and regex time/complexity is bounded | Designed |
| LM-09 | Embedding similarity | P5 embedding metric/provider port | `docs/api/metrics/semantic.md` (planned) | Contract, numeric | Fake vectors give hand-computed similarity; model/version/dimensions recorded | Designed |
| LM-10 | Toxicity/safety classifier interface | P5 classifier port | `docs/api/metrics/safety.md` (planned) | Contract, fake integration | Classifier version/threshold/labels/probabilities and failure behavior persist | Designed |
| LM-11 | Latency, TTFT, throughput | P5 operational metrics | `docs/api/metrics/operations.md` (planned) | Unit, integration | Clock spans define each metric; unavailable TTFT is missing, not zero | Designed |
| LM-12 | Token and cost metrics | P5 operational metrics | Same as LM-11 | Decimal/unit, integration | Input/output/total and estimated/actual costs retain source and decimal precision | Designed |
| LM-13 | Refusal and error rates | P5 rate metrics | Same as LM-11 | Unit, judge/classifier contract | Numerator, denominator, unknown classification, and failures are explicit | Designed |
| LM-14 | Warn lexical overlap limitations | P5 docs/UI metadata | `docs/concepts/lexical-metrics.md` (planned) | Docs/UI | Selecting open-ended lexical metrics shows paraphrase/factuality limitation | Designed |
| RAG-01 | Recall@K, precision@K, hit@K | P5 retrieval metrics | `docs/api/metrics/rag.md` (planned) | Hand, property | Exact denominators and empty relevance/retrieval behavior match documented tables | Designed |
| RAG-02 | MRR, MAP, nDCG | P5 ranking metrics | Same as RAG-01 | Hand, library, property | Ranked examples including no relevant docs, ties, K clipping, graded labels match formulas | Designed |
| RAG-03 | Coverage and duplicate-document rate | P5 retrieval metrics | Same as RAG-01 | Unit, property | Identity level (doc/chunk/source) and numerator/denominator are configurable and recorded | Designed |
| RAG-04 | Context utilization/relevance/precision/recall | P5 code/judge metrics | `docs/concepts/rag-evaluation.md` (planned) | Unit, judge contract | Metric declares label/evidence source and handles empty context/reference explicitly | Designed |
| RAG-05 | Answer relevance/correctness/faithfulness | P5/P6 evaluator metrics | Same as RAG-04 | Judge, calibration | Strict judge results include evidence/justification and no hidden reasoning dependency | Designed |
| RAG-06 | Citation presence/validity/correctness/completeness | P5 citation parser/evaluator | Same as RAG-04 | Golden, property, judge | Citations resolve against supplied sources; unsupported/missing/unverifiable are distinct | Designed |
| RAG-07 | Unsupported-claim rate | P5/P6 claim/evidence metric | Same as RAG-04 | Judge, hand aggregation | Claims and support labels are auditable; denominator excludes no claim silently | Designed |
| RAG-08 | Retrieval/generation/end-to-end latency and cost | P5 operational metrics | `docs/api/metrics/rag.md` (planned) | Unit, integration | Trace spans/cost records reconcile component and total measurements | Designed |
| RAG-09 | Doc/chunk/source relevance labels | P3 schema + P5 metric config | `docs/concepts/rag-evaluation.md` (planned) | Schema, metric contract | Label granularity is validated and reflected in dedupe/denominators | Designed |
| AGT-01 | Complete trajectory representation | P4 agent trace schemas | `docs/concepts/agent-evaluation.md` (planned) | Schema, artifact integration | Observations, decisions, calls/results, state, and output round-trip with ordering and hashes | Designed |
| AGT-02 | Task success, partial completion, final correctness | P5 agent metrics | `docs/api/metrics/agent.md` (planned) | Hand, rubric/judge | End-state metrics distinguish partial, failure, abstention, and missing reference | Designed |
| AGT-03 | Tool selection, argument validity, success/invalid/redundant rates | P5 tool metrics | Same as AGT-02 | Unit, property | Tool schema and expected-call fixtures produce documented counts/denominators | Designed |
| AGT-04 | Tool efficiency and step count without simplistic ranking | P5 agent metrics | `docs/concepts/agent-evaluation.md` (planned) | Unit, docs/UI | Efficiency conditions on correctness/task budget and raw step count is never labeled quality alone | Designed |
| AGT-05 | Loop/repeated action detection | P5 trajectory algorithms | `docs/api/metrics/agent.md` (planned) | Unit, property | Exact/normalized repetition windows find seeded loops with configurable thresholds | Designed |
| AGT-06 | Recovery, constraint adherence, state consistency | P5 trajectory metrics | Same as AGT-05 | State/trajectory fixtures | Failure-recovery and invariant violations are localized to trace steps with evidence | Designed |
| AGT-07 | Planning/trajectory quality rubrics | P6 judge rubric | `docs/concepts/agent-evaluation.md` (planned) | Judge/calibration | Versioned explicit rubric emits dimensions, confidence, evidence, and concise justification | Designed |
| AGT-08 | Grounding, hallucinated tool results, safety, escalation | P5/P6 metrics/judges | Same as AGT-07 | Adversarial judge, hand fixtures | Claims link to actual tool outputs; invented results and escalation/safety decisions are separately scored | Designed |
| AGT-09 | Agent latency, tokens, tool/total cost | P5 operational metrics | `docs/api/metrics/agent.md` (planned) | Unit, integration | Per-step and total usage reconcile with explicit unknown/estimated fields | Designed |
| AGT-10 | End-state and trajectory-aware scoring | P5 plugin compatibility | Same as AGT-07 | Contract | Metric input requirements prevent accidental trajectory metric execution on end state only | Designed |

## E. Pairwise and LLM-as-a-Judge

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| PAIR-01 | Same-record A/B comparison, blind/order randomization | P6 pair designer | `docs/concepts/pairwise.md` (planned) | Unit, property, E2E | Inputs share record; blind mapping hides identity; same seed repeats and orders balance | Designed |
| PAIR-02 | Wins/losses/ties/abstentions; human/LLM; multiple judges/rubrics | P6 pair/judgment models | Same as PAIR-01 | Schema, API, judge | All verdict/judge types persist independently with rubric/version and no abstention-to-tie coercion | Designed |
| PAIR-03 | Confidence, evidence, malformed/inconsistent detection, safe retry | P6 judge executor | `docs/guides/judges.md` (planned) | Contract, fault, adversarial | Bounds/references/cross-fields validate; repair/retry is bounded and idempotent | Designed |
| PAIR-04 | Disagreement and inter-rater reliability | P6/P7 calibration/statistics | `docs/statistics/judge-agreement.md` (planned) | Hand, library | Reports distributions, effective raters, agreement method/assumptions, and missing ratings | Designed |
| PAIR-05 | Duplicate prevention and balanced deterministic multi-variant designs | P6 pair scheduler | `docs/architecture/pair-design.md` (planned) | Constraint, property | Natural-key duplicates fail; pair/position counts meet documented balance bound | Designed |
| PAIR-06 | Configurable deterministic sample sizes | P6 pair sampling | Same as PAIR-05 | Property, API | Exact feasible sample selected by seed; infeasible design returns validation explanation | Designed |
| PAIR-07 | Win rates/counts and tie adjustment | P7 pair summaries | `docs/statistics/ranking-models.md` (planned) | Hand, property | All four counts shown; denominators and tie convention match worked example | Designed |
| PAIR-08 | Bradley–Terry, Davidson ties, descriptive Elo | P7 ranking module | Same as PAIR-07 | Textbook, library/simulation | Parameters satisfy identifiability; disconnected/separated data warn; Elo config/order shown | Designed |
| PAIR-09 | Bootstrap ranking/outcome uncertainty | P7 cluster bootstrap | Same as PAIR-07 | Seeded simulation, property | Resampling unit preserves record/judge dependence and repeats for fixed seed | Designed |
| PAIR-10 | Position reversal, diagnostics, threshold alerts | P6/P7 pair design/analysis | `docs/concepts/judge-bias.md` (planned) | Property, statistical, E2E | Reversed links and position-stratified outcomes produce effect estimate/CI and configured alert | Designed |
| JDG-01 | Complete judge configuration | P6 versioned judge config | `docs/guides/configuring-judges.md` (planned) | Schema/API | Provider/model/params/prompt/rubric/schema/repetitions/aggregate/order/seed/timeout/retry/cost/calibration/data policy all validate | Designed |
| JDG-02 | All required judge modes | P6 judge strategy registry | `docs/concepts/llm-as-judge.md` (planned) | Contract, E2E | Point/binary/ordinal/multidimensional/pair/reference/RAG/agent fixtures execute | Designed |
| JDG-03 | Strict structured response without chain-of-thought | P6 judge schemas | Judge-schema ADR (planned) | Schema, security | Required fields and bounds enforce; stored response has concise evidence/justification and no hidden reasoning field | Designed |
| JDG-04 | Bounded repair/retry | P6 judge executor | `docs/architecture/judge-engine.md` (planned) | Fault/contract | Invalid fixtures exhaust configured finite repairs, retain attempts/costs, and isolate failure | Designed |
| JDG-05 | Randomization/blinding/instruction hierarchy/delimiters | P6 prompt builder | `docs/security/judge-injection.md` (planned) | Property, adversarial | Trusted/untrusted boundaries are present, identity absent, order seeded, and malicious strings remain data | Designed |
| JDG-06 | Temperature, repetitions, aggregation, ensembles | P6 judgment aggregator | `docs/guides/configuring-judges.md` (planned) | Unit, property | Majority/median/mean eligibility rules handle ties/missing and report all individual judgments | Designed |
| JDG-07 | Disagreement, calibration, sensitivity, abstention, confidence, drift | P6 calibration/monitoring | `docs/concepts/judge-reliability.md` (planned) | Statistical, integration | Human baseline and judge/model/time slices emit accuracy/agreement/calibration/drift alerts | Designed |
| JDG-08 | Versioned prompts and rubrics | P4/P6 config registry | Same as JDG-01 | Immutability/API | Published version cannot change and every judgment resolves exact prompt/rubric content hash | Designed |
| JDG-09 | Prompt-injection malicious cases and residual-risk disclosure | P6 adversarial suite | `docs/security/judge-injection.md` (planned) | Security/contract | Rubric/secret/score/system impersonation cases cannot break schema/prompt boundary; docs state no guarantee | Designed |
| CAL-01 | Accuracy, PRF, confusion for categorical calibration | P6/P7 calibration stats | `docs/statistics/judge-agreement.md` (planned) | Hand, library | Values and class support match trusted examples including imbalance | Designed |
| CAL-02 | Rank correlation, agreement, kappa/weighted kappa/alpha | P7 agreement module | Same as CAL-01 | Hand, library | Applicable assumptions validate; missing/multiple/ordinal fixtures match references | Designed |
| CAL-03 | Calibration curves/confidence and error slices | P6/P7 calibration analysis | Same as CAL-01 | Numeric, UI | Reliability bins include count/predicted/observed; slices show denominators and uncertainty | Designed |
| CAL-04 | Explain agreement limitations | P7 documentation/UI warnings | Same as CAL-01 | Docs/UI | Prevalence, independence, scale, missingness, sample-size caveats render with result | Designed |

## F. Statistics, experiment comparison, and slices

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| STAT-01 | Descriptive/inferential separation and paired default | P7 typed analysis API | `docs/statistics/index.md` (planned) | Unit/schema | Result schema distinguishes estimate/inference and matching records use paired procedures | Designed |
| STAT-02 | Store config/confidence/seed/effective n/missing/failures/warnings | P7 provenance schema | Same as STAT-01 | Unit, API/report | No analysis serializes without all fields and union/pair counts reconcile | Designed |
| STAT-03 | Avoid causal claims; separate statistical/practical meaning | P7 interpreter | `docs/concepts/significance.md` (planned) | Unit/golden report | Interpretation vocabulary is bounded and never emits causal/equivalent claims without procedure | Designed |
| CI-01 | Mean, median, proportion, accuracy/error/win intervals | P7 interval module | `docs/statistics/confidence-intervals.md` (planned) | Hand, library, simulation | Defaults match Phase 1 §10.3 and edge warnings appear | Designed |
| CI-02 | Paired delta, cost, latency, quantile, ranking intervals | P7 interval/ranking module | Same as CI-01 | Hand, seeded simulation | Resampling unit/config is stored and paired/cluster dependency is preserved | Designed |
| CI-03 | Normal, t, Wilson, exact binomial | P7 parametric/binomial module | Same as CI-01 | Textbook, library, extreme cases | Results match reference tolerances for small/large/extreme samples | Designed |
| CI-04 | Percentile, basic, BCa bootstrap | P7 bootstrap module | `docs/statistics/bootstrap.md` (planned) | Hand, property, simulation | Seed reproducibility and fallback warnings hold; definitions match reference | Designed |
| CI-05 | Paired, stratified, cluster bootstrap | P7 resampling strategies | `docs/statistics/paired-bootstrap.md` (planned) | Property, simulation | Sample indices preserve declared structure; too-few strata/clusters warn | Designed |
| CI-06 | Explain independent bootstrap error for paired data | P7 docs | Same as CI-05 | Docs example | Worked correlated example shows different paired vs independent uncertainty | Designed |
| TEST-01 | Paired t, Wilcoxon, sign tests | P7 hypothesis module | `docs/statistics/hypothesis-tests.md` (planned) | Textbook, SciPy cross-check | Known examples match configured alternatives/zero modes and report assumptions | Designed |
| TEST-02 | McNemar, paired bootstrap, permutation tests | P7 hypothesis module | Same as TEST-01 | Textbook, exact enumeration, simulation | Small discordant/exact and seeded sign-flip results match references | Designed |
| TEST-03 | Binomial wins with explicit tie handling | P7 pair test | Same as TEST-01 | Hand, edge | Exclude/half/model choices alter denominator exactly as documented; all ties warn | Designed |
| TEST-04 | Handle ties, zero, missing, small n | P7 validators/procedures | Same as TEST-01 | Edge/property | No crash/silent drop; typed non-computable result or valid exact result includes counts | Designed |
| EFF-01 | Mean/median/relative/paired standardized effects | P7 effects module | `docs/statistics/effect-sizes.md` (planned) | Hand, property | Sign follows metric direction; near-zero and zero-variance warnings appear | Designed |
| EFF-02 | Matched odds, risk, win difference, superiority | P7 effects module | Same as EFF-01 | Hand, library | Binary/pair fixtures match definitions including zero cells/ties | Designed |
| MULT-01 | Holm, BH, Bonferroni | P7 multiplicity module | `docs/statistics/multiple-comparisons.md` (planned) | Hand, statsmodels cross-check, property | Adjusted values monotone/in range and decisions match examples | Designed |
| MULT-02 | Explain FWER/FDR and freeze families | P7 analysis plan/docs | Same as MULT-01 | Schema/docs | Analysis rejects post-result family mutation and reports method/family membership | Designed |
| PWR-01 | MDE/sample sizes for paired proportions/continuous/preferences | P7 planning utilities | `docs/statistics/power.md` (planned) | Textbook/simulation | Inputs, approximation, assumptions, design effect, rounded sample size are returned | Designed |
| PRACT-01 | MPID interpretation categories | P7 interpreter/gates | `docs/concepts/significance.md` (planned) | Table-driven | All five requested outcome categories occur on constructed interval/effect cases | Designed |
| PRACT-02 | Paired continuous TOST | P7 equivalence module | `docs/statistics/equivalence.md` (planned) | Textbook, statsmodels cross-check | Both one-sided tests and compatible CI support equivalence; nonsignificance alone never does | Designed |
| WARN-01 | All requested small-sample/degenerate warnings | P7 warning rules | `docs/statistics/warnings.md` (planned) | Table/property/UI | Small n, degenerate, ties, zero variance, imbalance, missing, clusters, instability, disagreement each emit stable code | Designed |
| CMP-01 | Dataset/version/overlap compatibility | P7 comparison aligner | `docs/guides/comparing-experiments.md` (planned) | Unit, integration | Exact/mismatch/intersection cohorts classify; intersection warning and counts cannot be hidden | Designed |
| CMP-02 | Paired metric deltas, intervals, effects, adjusted/raw p | P7 comparison analyzer | Same as CMP-01 | Statistical, API/UI | Every comparable metric includes full inferential payload and procedure provenance | Designed |
| CMP-03 | Failure, cost, latency differences | P7 comparison analyzer | Same as CMP-01 | Unit, integration | Full union failure comparison and paired available cost/latency counts are explicit | Designed |
| CMP-04 | Slices and extreme positive/negative examples | P7/P8 analyzer/browser | Same as CMP-01 | Unit, API/UI | Metadata filters are safe; ranked deltas retain record links and sensitivity policy | Designed |
| CMP-05 | JSON/CSV/Markdown reproducible exports | P8 reports | `docs/guides/reports.md` (planned) | Golden, security | All exports share cohort/config digest; CSV formulas sanitize | Designed |
| CMP-06 | Baseline/regression thresholds for CI | P8 gates | `docs/guides/ci-gates.md` (planned) | Unit, CLI E2E | Versioned baseline config deterministically produces pass/fail/inconclusive and exit code | Designed |
| SLC-01 | Reusable slices over all required fields/categories | P7 slice DSL | `docs/concepts/slices.md` (planned) | Parser/property/security | Field/tag/language/topic/difficulty/length/depth/steps/error/confidence/custom safe predicates evaluate | Designed |
| SLC-02 | Versioned slices with n/uncertainty/small-n warning | P4 registry + P7 analyzer | Same as SLC-01 | Unit, UI | Result resolves immutable definition and always renders n, interval/missingness, warning | Designed |
| SLC-03 | Bound hierarchical/nested combinatorics | P7 planner | Same as SLC-01 | Unit, cost/security | Depth/cardinality/result caps reject explosive plans before query execution | Designed |

## G. API, CLI, web, persistence, and reporting

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| API-01 | Versioned REST/OpenAPI for all listed resources/actions | P2–P8 FastAPI routers | `docs/api/index.md` (planned) | API, OpenAPI, E2E | Auth, projects, all dataset/config/run/result/pair/stats/report/audit/probe operations appear and work under `/api/v1` | Designed |
| API-02 | Pagination, filter, sort | P2 API query contracts | `docs/api/conventions.md` (planned) | API/property | Keyset pages have stable no-duplicate traversal; allowlisted filters/sorts validate | Designed |
| API-03 | Stable errors and request IDs | P2 middleware/errors | Same as API-02 | API/contract | All errors use versioned problem schema and return/echo safe request ID | Designed |
| API-04 | Idempotency on creates/actions | P2 idempotency service | Same as API-02 | Concurrent integration | Same principal/route/key/body replays response; changed body conflicts; concurrent calls create once | Designed |
| API-05 | Optimistic locking/version checks | P2/P3 mutable resources | Same as API-02 | Concurrent API | Stale version stamp returns stable conflict without overwriting new state | Designed |
| API-06 | Typed SDK and compatibility/deprecation | P8 generated clients/policy | `docs/api/compatibility.md`, `docs/guides/sdk.md` (planned) | Generation drift, package, contract | SDK passes API workflow and incompatible schema diff requires version/deprecation evidence | Designed |
| CLI-01 | All specified `evalctl` commands | P3–P8 Typer CLI | `docs/guides/cli.md` (planned) | CLI integration/E2E | Project/dataset/suite/run/result/compare/report command examples execute | Designed |
| CLI-02 | Human and JSON output, CI, exit codes | P2/P8 CLI presenters | Same as CLI-01 | Golden, subprocess | JSON is schema-valid/no decoration; errors/gates return documented nonzero codes | Designed |
| CLI-03 | Config/env/auth/timeouts/help/completion | P2/P8 CLI config | Same as CLI-01 | Unit, CLI | Precedence is flags > env > file > default; token is redacted; timeouts and shell completions work | Designed |
| WEB-01 | Project and dataset registry/version/diff | P3/P8 React routes | `docs/guides/dashboard.md` (planned) | RTL, accessibility, E2E | Authorized keyboard user can select project, inspect versions and semantic diff | Designed |
| WEB-02 | Suite/metric/rubric/model/judge editors and experiment creation | P8 forms/routes | Same as WEB-01 | RTL, schema, E2E | Forms expose compatible versioned choices, validate, and never mutate published configs | Designed |
| WEB-03 | Progress, aggregate/CI, pairwise, slice results | P8 result routes | Same as WEB-01 | RTL, visual semantics, E2E | Live/reconnected progress and values with n/CI/warnings/pair counts render | Designed |
| WEB-04 | Record, RAG trace, agent trajectory inspection | P8 detail routes | Same as WEB-01 | RTL, XSS security, E2E | Untrusted content renders as text; ordered trace/calls/evidence and missing parts are distinct | Designed |
| WEB-05 | Cost, latency, errors, reports, role-aware audit | P8 operations routes | Same as WEB-01 | RTL, authorization, E2E | Each view filters/paginates and audit visibility follows role | Designed |
| WEB-06 | Loading/empty/error/partial/denied states | P8 shared state components | `docs/testing/frontend.md` (planned) | RTL, accessibility | Every data route has asserted semantic state and recovery action | Designed |
| WEB-07 | Keyboard/semantic labels/non-color and n/uncertainty/missing-vs-zero | P8 accessible design system | `docs/guides/accessibility.md` (planned) | axe, keyboard, Playwright | No critical axe violations; flows work keyboard-only; tables/text accompany charts | Designed |
| DB-01 | PostgreSQL normalized metadata/results | P2–P7 migrations/repositories | `docs/architecture/data-model.md` (planned) | Migration, constraint, performance | Requested entities have typed schema, FKs/checks/uniqueness, and query plans meet targets | Designed |
| DB-02 | S3 for all listed large artifacts | P2–P8 artifact service | `docs/architecture/object-storage.md` (planned) | Integration, reconciliation | Uploads/datasets/reports/traces/trajectories/raw outputs store by opaque key and verified hash | Designed |
| DB-03 | Index/partition/retention/archive/migration/backup design | P7/P9 database operations | `docs/operations/database.md` (planned) | EXPLAIN/performance, migration, restore | Hot queries use expected indexes; partitions route; retention/archive and backup restore succeed | Designed |
| DB-04 | Transactions and outbox | P2 application UoW/relay | `docs/architecture/outbox.md` (planned) | Fault integration | Rollback publishes nothing; commit eventually publishes; duplicate relay is harmless | Designed |
| DB-05 | At-least-once duplicate handling | P4 task repository | Same as DB-04 | Concurrency/fault | Replayed queue messages produce one committed task result and append attempts | Designed |
| REP-01 | Complete report contents | P8 report projection | `docs/guides/reports.md` (planned) | Golden, E2E | Report contains metadata/versions/config/metrics/n/missing/fail/CI/pairs/tests/effects/slices/cost/latency/errors/limits/reproduce | Designed |
| REP-02 | JSON, CSV subsets, Markdown, printable HTML | P8 renderers | Same as REP-01 | Schema/golden/security | Four formats generate from same snapshot; HTML prints; CSV formula payloads sanitize | Designed |
| REP-03 | No aggregate without n; no hidden failures | P5/P7/P8 schemas/renderers | Same as REP-01 | Schema, UI, golden | Serializer rejects aggregates lacking denominator/missing-policy/counts | Designed |

## H. Security, observability, deployment, and scalability

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| SEC-01 | Threat model covering every named threat | P1/P9 security review | `docs/security/threat-model.md` (planned; Phase 1 §9 baseline) | Threat-model review | Auth/authz/isolation/keys/encryption/SSRF/SQLi/XSS/CSRF/IDOR/uploads/CSV/path/archive/prompt/exfil/log/PII/supply-chain/DoS/cost/webhook are addressed | Designed |
| SEC-02 | Project-scoped authorization and tenant isolation | P2 IAM/repositories/RLS | `docs/architecture/multi-tenancy.md` (planned) | Unit, integration, security | Cross-project reads/writes and guessed IDs fail consistently at two layers | Designed |
| SEC-03 | Secret redaction/safe logging/no raw DB secrets | P2 secret/log processors | `docs/security/secrets.md` (planned) | Canary/security | Canary credentials never appear in DB exports, logs, traces, errors, or audit | Designed |
| SEC-04 | Upload limits/content validation/path/archive safety | P3 import boundary | `docs/security/uploads.md` (planned) | Security, fuzz, performance | Oversize/type mismatch/traversal/zip bomb/nesting/malicious name reject within bounded resources | Designed |
| SEC-05 | Rate limits, security headers, CORS, CSRF posture | P2 API edge | `docs/security/web.md` (planned) | API/security/browser | Limits return stable 429; headers/CSP/origins match env; auth mode has documented CSRF control | Designed |
| SEC-06 | Audit logging | P2/P3–P8 audit service | `docs/security/audit.md` (planned) | Integration, chain verification | Security/material changes append safe actor/action/outcome/target events and chain verifies | Designed |
| SEC-07 | Data retention/provider sharing warnings/CSV safety | P3/P8/P9 privacy/export | `docs/security/privacy.md` (planned) | Unit, UI, security | Policy blocks disallowed provider sharing, UI warns, deletions work, formulas sanitize | Designed |
| SEC-08 | Encryption in transit/at rest and secure defaults | P9 manifests/runbooks | `docs/security/deployment.md` (planned) | Manifest, deployment smoke | Production config requires TLS, secret injection, storage encryption guidance, non-dev auth | Designed |
| SEC-09 | Responsible disclosure `SECURITY.md` | P2 governance | `SECURITY.md` (planned) | Docs/repository | Contact, scope, response expectations, supported versions, and safe reporting exist | Designed |
| OBS-01 | JSON logs with request/trace IDs across API/worker/provider | P2/P4 instrumentation | `docs/operations/observability.md` (planned) | Unit/integration | One E2E run correlates safe log events and spans across all boundaries | Designed |
| OBS-02 | Prometheus health/readiness/liveness | P2 probes/metrics | Same as OBS-01 | HTTP/integration | Live indicates process; ready checks critical dependencies; metrics scrape succeeds | Designed |
| OBS-03 | All requested operational metrics | P2/P4–P7 instrumentation | Same as OBS-01 | Metrics contract | Queue/run/task/retry/provider/token/cost/disagreement/throughput/DB signals emit bounded labels | Designed |
| OBS-04 | Dashboards/alerts/runbooks for every named incident | P9 monitoring assets | `docs/operations/alert-response.md` (planned) | Promtool, provisioning, tabletop | Queue/provider/DB/Redis/S3/run/cost/stuck/worker/judge alerts validate and link actionable runbooks | Designed |
| DEP-01 | One-command Docker Compose local stack | P2/P9 Compose/Make | `docs/guides/local-install.md` (planned) | Docker smoke, E2E | `make dev-up` starts healthy Postgres/Redis/MinIO/API/worker/web and migrations | Designed |
| DEP-02 | Production multi-stage non-root images/probes | P2/P9 Dockerfiles | `docs/operations/containers.md` (planned) | Build, image inspect, smoke | Images build reproducibly, run with nonzero UID/read-only-compatible FS, and pass probes | Designed |
| DEP-03 | Kubernetes API/web/worker/migration/ingress/storage/secrets | P9 Kustomize manifests | `docs/guides/production-deployment.md` (planned) | Kubeconform/policy, kind smoke | Rendered base/overlay validates and starts with explicit migration job/order | Designed |
| DEP-04 | Replicas/resources/HPA/PDB guidance | P9 manifests/docs | Same as DEP-03 | Manifest/policy | Workloads set requests/limits and documented autoscaling/disruption constraints | Designed |
| DEP-05 | Complete safe `.env.example` | P2 configuration | `docs/operations/configuration.md` (planned) | Settings/schema scan | Fresh copy boots local stack; every variable is commented; no real secret exists | Designed |
| SCL-01 | Millions records/thousands tasks/large outputs | P3/P4 streaming/partitioning/artifacts | `docs/architecture/scaling.md` (planned) | Performance, memory profiling | Target scenarios avoid whole-run memory and meet documented controlled-runner thresholds | Designed |
| SCL-02 | Incremental aggregation/paginated browsing/batched writes | P4/P5/P8 data path | Same as SCL-01 | Unit, integration, performance | Aggregates converge to batch result; queries keyset-page; writes use bounded batches | Designed |
| SCL-03 | Horizontal workers/concurrency/backpressure/priority/cancel/retry | P4 dispatcher/queues | Same as SCL-01 | Concurrent integration, load | Scale-out increases throughput without limit violations; priority and cancellation remain bounded | Designed |
| SCL-04 | Bottleneck/index/partition/cache/aggregation/scale documentation | P9 architecture/operations | Same as SCL-01 | Design/performance review | Measured bottlenecks and EXPLAIN evidence map to scale-up/out paths and invalidation rules | Designed |

## I. Tests, CI/CD, documentation, examples, and gates

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TST-01 | All listed domain/algorithm unit tests | P2–P8 unit suites | `docs/testing/test-philosophy.md` (planned) | Unit | Every enumerated invariant/calculation/policy has outcome and edge assertions | Designed |
| TST-02 | Required property tests | P3–P7 Hypothesis suites | `docs/testing/property-tests.md` (planned) | Property | Canonical/hash/range/CI/sampling/order/diff/bootstrap/state properties run deterministically | Designed |
| TST-03 | Statistical trusted/hand/textbook/simulation validation | P7 validation suite | `docs/testing/statistical-validation.md` (planned) | Statistical | Reference tolerances are justified; coverage simulations fall within predeclared bands | Designed |
| TST-04 | Real PostgreSQL/Redis/S3 integration behaviors | P2–P9 testcontainers | `docs/testing/integration.md` (planned) | Integration | Migrations/transactions/queue/object/run/idempotency/failure/budget/immutability/audit/isolation pass | Designed |
| TST-05 | Shared provider contract without paid calls | P4 fake servers/contracts | `docs/testing/provider-contracts.md` (planned) | Contract | Every adapter passes success/structured/usage/timeout/rate/invalid/retry/redaction cases | Designed |
| TST-06 | Complete judge test matrix | P6 judge tests | `docs/testing/judges.md` (planned) | Unit, contract, adversarial | Valid/invalid/missing/bounds/injection/reversal/tie/abstain/disagreement/aggregate/retry/cost cases pass | Designed |
| TST-07 | Complete API test matrix | P2–P8 API suite | `docs/testing/api.md` (planned) | API | Success/validation/authn/authz/page/filter/sort/idempotency/conflict/error/OpenAPI cases pass | Designed |
| TST-08 | Complete frontend test matrix | P3/P6/P8 web tests | `docs/testing/frontend.md` (planned) | RTL, axe | Required components and states including uncertainty/pair/progress/trajectory pass | Designed |
| TST-09 | Eleven-step Playwright workflow | P8 E2E | `docs/testing/e2e.md` (planned) | Playwright | Project through audit/export workflow passes against fake-provider stack | Designed |
| TST-10 | Repeatable performance scenarios and thresholds | P3/P4/P7/P9 load suite | `docs/testing/performance.md` (planned) | Performance | Import/ingestion/schedule/aggregate/compare/dashboard scenarios report environment and targets | Designed |
| TST-11 | Complete security test matrix | P2–P9 security suite | `docs/testing/security.md` (planned) | Security | Isolation/auth/filename/size/path/CSV/XSS/prompt/log/rate cases fail safely | Designed |
| TST-12 | Quality gates and opt-in live-provider group | P2 CI/test config | `docs/testing/running-tests.md` (planned) | CI policy | Critical suites cannot skip; live calls excluded by default; type/lint/migration/build gates enforce | Designed |
| CICD-01 | Backend/frontend/docs/migration test workflows | P2/P8 GitHub Actions | `docs/operations/ci.md` (planned) | Workflow lint/dry run | All listed lint/format/type/test/build jobs exist, cache safely, and are required | Designed |
| CICD-02 | Vulnerability/secret/container/SBOM/license scans | P2/P9 supply-chain CI | `docs/security/supply-chain.md` (planned) | CI scan fixtures | Known seeded findings fail policy; release emits SBOM and license report | Designed |
| CICD-03 | Docker/release builds and deployment blocking | P9 release workflows | `docs/operations/releases.md` (planned) | Workflow, artifact smoke | Failed required gate prevents release; signed/versioned artifacts build only from protected tag | Designed |
| CICD-04 | Dependency caching and automated updates | P2 workflows/Dependabot | `docs/operations/dependencies.md` (planned) | Config validation | Lockfile-keyed caches and grouped scheduled update PR configuration validate | Designed |
| CICD-05 | Semantic version release process | P2/P9 governance | `docs/operations/releases.md` (planned) | Docs/release dry run | Version/changelog/API/migration/deprecation steps produce reproducible release candidate | Designed |
| DOC-01 | Root README/contributing/security/changelog/conduct/license | P2 governance docs | Those root files (planned except README) | Docs/link/license checks | All six exist, are substantive, consistent, and license scanner recognizes Apache-2.0 | Designed |
| DOC-02 | All required concept documents | P3–P7 concepts docs | `docs/concepts/` index (planned) | MkDocs/link/content review | Every named concept has definition/motivation/formalism/example/edges/tradeoffs/code/tests/ops/security as applicable | Designed |
| DOC-03 | All required architecture documents/diagrams | P2–P9 architecture docs | `docs/architecture/` index (planned) | Mermaid/link/design review | Context/container/component/data/domain/sequences/deploy/trust/scale/tenant/recovery/retention render | Designed |
| DOC-04 | Deep statistics documents/equations/examples | P7 statistics docs | `docs/statistics/` index (planned) | Math/content/link review | Every named statistics topic has equations, numerical example, assumptions, and code/test links | Designed |
| DOC-05 | All required user/developer guides | P2–P8 guides | `docs/guides/` index (planned) | Docs executable snippets/E2E | Every named install/dataset/suite/run/compare/judge/RAG/agent/provider/metric/report/CLI/SDK/gate guide runs | Designed |
| DOC-06 | All required operations runbooks | P9 operations docs | `docs/operations/` index (planned) | Tabletop/link/command checks | Every named config/backup/migration/queue/scale/monitor/incident/secret/DR/delete/upgrade procedure is actionable | Designed |
| DOC-07 | All required testing documents | P2–P9 testing docs | `docs/testing/` index (planned) | Docs/link review | Philosophy/pyramid/fixtures/fake/stats/integration/E2E/performance/security/run/debug documents exist | Designed |
| DOC-08 | Required focused ADRs | P2–P9 ADR series | `docs/adr/` index (planned) | ADR/link review | Monorepo/DB/queue/S3/clean/hash/immutable/provider/metric/stats/judge/tenant/obs/deploy decisions recorded | Designed |
| DOC-09 | Generated OpenAPI documentation | P2–P8 API build | `docs/api/openapi.json` (planned generated) | Drift/schema/docs build | OpenAPI generation is deterministic and docs expose all public operations/schemas | Designed |
| EX-01 | Synthetic/permissive QA/classification/RAG/pair/agent/judge/CI/regression examples | P3–P8 examples | `examples/README.md` (planned) | License/schema/E2E | Every requested example validates license/source and runs with fake provider | Designed |
| EX-02 | One-command dependencies+migrate+seed+demo+report | P9 Make/demo script | `docs/guides/demo.md` (planned) | Clean-machine smoke | One documented command ends with successful run/comparison and report artifact | Designed |
| GATE-01 | Accuracy/LCB/regression/failure/latency/cost/safety/n gates | P8 gate engine | `docs/guides/ci-gates.md` (planned) | Table, CLI E2E | Each gate has constructed pass/fail; compound config reports every decision | Designed |
| GATE-02 | Version-controlled machine config and nonzero CLI | P8 schemas/CLI | Same as GATE-01 | Schema, subprocess | Checked-in example validates and failing/inconclusive policies yield documented codes | Designed |
| GATE-03 | Explain why p-value-only gating fails | P7/P8 docs/UI | Same as GATE-01 | Docs/golden | Guide covers power, effect size, MPID, multiplicity, and operational constraints | Designed |
| CODE-01 | Types/docstrings/focus/no globals/cycles/DI/time/decimal/enums/validation/errors/safe logs | All production packages | `CONTRIBUTING.md` (planned) | Ruff/MyPy/import/security/review | Static gates and focused tests pass; architecture review finds no critical violation | Designed |
| CODE-02 | Reject invalid config; favor composition | All config/plugin systems | ADRs and developer guide (planned) | Schema/contract | Invalid configuration fails before work/billing and plugin strategies compose without deep inheritance | Designed |

## J. Delivery process, acceptance, and final review

| ID | Requirement | Phase / implementation component | Documentation evidence | Test category | Acceptance criterion | Status |
| --- | --- | --- | --- | --- | --- | --- |
| PROC-01 | Ten deliberate implementation phases | P1–P10 delivery | `docs/design/phase-1-design.md` | Phase review | Each phase integrates code, tests, documentation, and executable evidence | Verified |
| PROC-02 | Generate tests/docs with each feature and maintain consistency | P2–P9 change policy | `CONTRIBUTING.md` (planned) | CI/review | Feature PR cannot pass without relevant tests/docs; route/env/table/migration/link checks pass | Designed |
| PROC-03 | Honest final command verification | P10 verification report | `docs/verification/final-report.md` (planned) | Recorded commands | Each check lists exact command, timestamp/environment, outcome, cause/fix, and limitations | Designed |
| ACC-01 | Fresh clone config/local startup/migrations/seed | P2/P9 foundation/demo | Local install/demo guides (planned) | Clean clone smoke | `.env.example` to healthy seeded stack succeeds with documented commands | Designed |
| ACC-02 | Dataset import/version/immutability/diff | P3 vertical slice | Dataset guides (planned) | E2E | Required dataset lifecycle completes and forbidden update fails | Designed |
| ACC-03 | Suite and fake model evaluation | P4 vertical slice | Run guide (planned) | E2E | Suite runs all records deterministically with no paid key | Designed |
| ACC-04 | RAG and agent trajectory evaluation | P5 vertical slices | RAG/agent guides (planned) | E2E | Example traces produce required representative metrics and inspectable artifacts | Designed |
| ACC-05 | Pairwise randomized judge/injection safety | P6 vertical slice | Judge guide/security doc (planned) | E2E/security | Balanced blind comparison returns strict judgments; adversarial cases pass | Designed |
| ACC-06 | CI, paired comparisons, effects, missing/fail reporting | P7 vertical slice | Statistics/comparison docs (planned) | Statistical/E2E | Baseline/candidate report includes all required inferential and denominator fields | Designed |
| ACC-07 | Resume/reproduce, dashboard, reports, gates | P4/P8 vertical slices | Run/dashboard/report/gate guides (planned) | Worker fault/UI/CLI E2E | Interrupted run resumes; historical run reproduces; UI/report work; gate passes and fails correctly | Designed |
| ACC-08 | Cross-project denial and audit | P2/P9 security | Security docs (planned) | Security/E2E | Unauthorized access never leaks existence and both allowed/denied material actions audit | Designed |
| ACC-09 | Comprehensive no-paid tests/docs links/non-root/no secrets/CI | P2–P10 quality system | Testing/operations docs (planned) | Full verification | All required gates execute successfully in P10 with no paid credentials | Designed |
| REV-01 | Software architecture review | P10 six-perspective review | Final verification report (planned) | Architecture review | Modularity/direction/cohesion/coupling/extension/isolation findings recorded; critical/high resolved | Designed |
| REV-02 | Statistical review | P10 six-perspective review | Final verification report (planned) | Statistical review | Assumptions/pairing/intervals/edges/missing/effects/multiplicity/interpretation findings resolved | Designed |
| REV-03 | ML evaluation review | P10 six-perspective review | Final verification report (planned) | ML review | Dataset/validity/RAG/agent/judge/calibration/leakage/reproduction findings resolved | Designed |
| REV-04 | Security review | P10 six-perspective review | Final verification report (planned) | Threat/security review | Isolation/secrets/upload/injection/cost/log/export/provider findings resolved | Designed |
| REV-05 | Operations review | P10 six-perspective review | Final verification report (planned) | Ops/tabletop review | Deploy/observe/retry/cancel/recover/migrate/backup/alert/scale findings resolved | Designed |
| REV-06 | Test review | P10 six-perspective review | Final verification report (planned) | Mutation/evidence review | Tests demonstrate realistic defect detection; critical/high gaps resolved | Designed |

## Coverage audit

The matrix covers specification sections as follows:

| Specification section | Requirement IDs |
| --- | --- |
| 1 Core mission | MIS-01–MIS-11 |
| 2 Engineering standard | ENG-01–ENG-11, CODE-01–CODE-02 |
| 3 Default stack | ENG-01, Phase 1 technology decisions, DEP-01–DEP-04, TST-01–TST-12 |
| 4 Repository structure | STR-01 |
| 5 Domain model | DOM-01–DOM-08 |
| 6 Versioned datasets | DSET-01–DSET-14, CAN-01–CAN-05, SCH-01–SCH-03, LEAK-01–LEAK-03 |
| 7 Evaluation engine | RUN-01–RUN-15 |
| 8 Provider abstraction | PROV-01–PROV-08 |
| 9 Metric framework | MET-01–MET-03, LM-01–LM-14, RAG-01–RAG-09, AGT-01–AGT-10 |
| 10 Pairwise comparison | PAIR-01–PAIR-10 |
| 11 LLM-as-a-Judge | JDG-01–JDG-09, CAL-01–CAL-04 |
| 12 Statistical analysis | STAT-01–STAT-03, CI-01–CI-06, TEST-01–TEST-04, EFF-01–EFF-02, MULT-01–MULT-02, PWR-01, PRACT-01–PRACT-02, WARN-01 |
| 13 Experiment comparison | CMP-01–CMP-06 |
| 14 Slices | SLC-01–SLC-03 |
| 15 API | API-01–API-06 |
| 16 CLI | CLI-01–CLI-03 |
| 17 Web dashboard | WEB-01–WEB-07 |
| 18 Persistence | DB-01–DB-05 |
| 19 Security/privacy | SEC-01–SEC-09 |
| 20 Observability | OBS-01–OBS-04 |
| 21 Deployment | DEP-01–DEP-05 |
| 22 Testing strategy | TST-01–TST-12 |
| 23 CI/CD | CICD-01–CICD-05 |
| 24 Documentation | DOC-01–DOC-09 |
| 25 Examples | EX-01–EX-02 |
| 26 Reporting | REP-01–REP-03 |
| 27 Regression gates | GATE-01–GATE-03 |
| 28 Performance/scale | SCL-01–SCL-04 |
| 29 Code quality | CODE-01–CODE-02 |
| 30 Output protocol | PROC-01–PROC-03 |
| 31 File generation | PROC-01–PROC-02, ENG-11 |
| 32 Acceptance | ACC-01–ACC-09 |
| 33 Final quality review | REV-01–REV-06 |
| 34 Behavior/defaults | Phase 1 assumptions/design risks, PROC-01–PROC-03 |

## Change-control rule

When implementation reveals that an acceptance criterion is invalid or
incomplete, the change must:

1. add or amend a focused ADR;
2. update the Phase 1 design where its contract changes;
3. update this matrix without reusing or deleting the old requirement ID;
4. add the test that demonstrates the revised acceptance behavior.

Superseded rows remain in version history. Product releases publish a generated
snapshot of this matrix with links to the exact code, documentation, and CI
artifacts for that release.
