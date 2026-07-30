# Metric framework

## Contract

A metric plugin exposes a stable identifier and semantic version, name,
description, supported task types, required input fields, typed configuration
schema, output schema, score direction/range, reference requirement,
determinism, aggregation policy, failure behavior, and cost characteristics.
Registry lookup validates task compatibility and configuration before
execution. Results can contain a scalar, label, structured payload, concise
explanation, metadata, or explicit missing marker.

Metric identifiers name meaning, not implementation function names. Changing a
denominator, tokenization rule, normalization rule, or score interpretation is
a metric-version change. Historical results always retain both identifier and
version.

## Missingness and aggregation

Every aggregate carries:

- `total_count`: all selected evaluation samples;
- `available_count`: successful numeric results used in the point estimate;
- `missing_count`: metric is inapplicable or a required input is absent;
- `failed_count`: evaluation was attempted but failed;
- `pending_count`: no terminal metric result exists yet.

No category is silently dropped. The aggregation policy defines the numerator
and available denominator; reports show all counts. Inferential treatment of
missingness belongs to Phase 7 and must state complete-case, failure-as-zero,
imputation, or sensitivity policy explicitly.

## Language metrics

Implemented metrics include exact, normalized exact, case-insensitive match,
token precision/recall/F1, classification accuracy and confusion-derived
macro/micro/weighted summaries, multilabel summaries, ROUGE-1/2/L, BLEU,
character and word error rate, edit distance, JSON validity, JSON Schema
compliance, structured-field accuracy, bounded regex criteria, embedding cosine
similarity through an interface, and safety-classifier integration through an
interface. Operational plugins expose latency, time to first token, throughput,
tokens, cost, refusal, and error indicators.

Lexical overlap answers “how much token or subsequence overlap exists,” not
“is this answer useful or true.” It is informative for constrained extraction,
transcription, translation, and reference-like summarization, but can penalize
correct paraphrases and reward fluent copying. BLEU is corpus-oriented and
unstable for a single short answer. ROUGE recall can reward verbosity. Edit
distance depends strongly on normalization. Metric selection must follow the
construct being measured.

### Token F1 example

For prediction “blue car” and reference “blue fast car,” token counts yield
precision `2/2`, recall `2/3`, and F1 `0.8`. Duplicate tokens are a multiset,
not a set. When both sides are empty, the implementation returns perfect
agreement; when only one is empty, precision/recall/F1 are zero.

## Retrieval and RAG metrics

Let the first \(k\) returned item IDs be \(R_k\), and the judged relevant set be
\(G\):

- precision@k uses `relevant returned / number actually returned up to k`;
- recall@k uses `relevant returned / |G|` and is missing when no relevance
  judgments exist;
- hit-rate@k is one when any returned item is relevant;
- reciprocal rank is `1 / rank` of the first relevant result, else zero;
- average precision averages precision at each relevant hit, dividing by the
  number of relevant items that could be retrieved within the evaluation
  depth;
- nDCG uses graded gain over logarithmic rank discount and divides by ideal
  DCG; a zero ideal gain is missing;
- coverage divides unique relevant returned IDs by all judged relevant IDs;
- duplicate rate divides duplicate positions by returned positions.

The registry also includes citation presence/validity/correctness/completeness
and hooks for context utilization, answer relevance/correctness,
faithfulness, and unsupported-claim scoring. Model-based forms are deliberately
deferred to the judge framework in Phase 6; code metrics must not pretend to
establish semantic faithfulness from string overlap.

Labels may apply at document, chunk, or source level, but a single calculation
must choose one identity level. Mixing chunk predictions with document gold
inflates denominators and is invalid.

## Agent trajectory metrics

The trajectory model records observations, decisions, tool calls, tool
results, intermediate state, and final output. Implemented functions score tool
argument schema validity, call success/invalid/redundant rates, step count,
loop and repeated-action detection, recovery after a tool failure, state
consistency, and whether final claims are grounded in visible tool output.
Plugin wrappers expose core success, loop, redundant-call, step, and cost
signals; additional pure functions are ready for suite-specific wrappers.

Fewer steps are neutral by default. Efficiency is meaningful only conditional
on correctness and task complexity: a one-step hallucination is not better
than a four-step verified answer. Planning and trajectory “quality” require a
versioned explicit rubric and belong to the Phase 6 judge layer.

## Isolation, security, and extension

Built-ins are trusted in-process plugins. A plugin exception is converted to a
metric-specific failed result and never rolls back a completed provider
response. Arbitrary uploaded Python is intentionally unsupported in shared
workers; future third-party code should run in a separately sandboxed worker
pool with resource, filesystem, network, and tenant isolation.

Regex metrics reject unsafe length/configuration and use bounded patterns.
Safety and embedding integrations receive redacted, policy-approved inputs and
must declare external cost/data handling. Explanations are concise evidence,
not hidden chain-of-thought.

Tests compare formulas with hand-calculated cases, assert ranges and edge
denominators, validate registry metadata, and exercise RAG and agent failure
cases. Statistical coverage and paired comparisons are Phase 7 concerns.
