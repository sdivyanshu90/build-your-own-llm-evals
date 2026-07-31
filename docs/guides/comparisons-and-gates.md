# Compare experiments and enforce regression gates

## Preconditions

Both runs should use the same immutable dataset version. If versions differ,
the API rejects the comparison unless `allow_dataset_intersection` is true. In
intersection mode only matching `record_key + repetition` identities are paired
and the report carries a visible limitation.

Create a comparison:

```bash
evalctl --json compare \
  --project-id "$EVAL_PROJECT_ID" \
  --baseline-run-id 01911111-1111-7111-8111-111111111111 \
  --candidate-run-id 01922222-2222-7222-8222-222222222222 \
  --metric language/exact-match \
  --practical-difference 0.01 \
  --seed 20260730
```

The stored configuration fixes confidence, bootstrap method/resamples, paired
test, missing-data policy, seed, practical threshold, and example count. Reports
contain raw and Holm-adjusted p-values, effects, confidence limits, union and
paired counts, failures, missing values, changed examples, and limitations.

Export formats:

```bash
evalctl report export \
  --project-id "$EVAL_PROJECT_ID" \
  --comparison-id 01933333-3333-7333-8333-333333333333 \
  --format markdown \
  --output comparison.md
```

CSV fields that begin with spreadsheet formula characters are prefixed with an
apostrophe. HTML escapes identifiers and other untrusted text.

## Gate configuration

Commit a gate such as `evaluation-gate.json`:

```json
{
  "version": "1.0.0",
  "rules": [
    {
      "identifier": "accuracy-regression",
      "metric_identifier": "language/exact-match",
      "operator": "maximum_regression",
      "threshold": 0.01,
      "minimum_paired_count": 200,
      "required": true
    },
    {
      "identifier": "accuracy-lower-bound",
      "metric_identifier": "language/exact-match",
      "operator": "lower_confidence_minimum",
      "threshold": -0.005,
      "minimum_paired_count": 200,
      "required": true
    }
  ]
}
```

Run the gate:

```bash
evalctl gate check \
  --project-id "$EVAL_PROJECT_ID" \
  --comparison-id 01933333-3333-7333-8333-333333333333 \
  --configuration evaluation-gate.json
```

Exit code 0 means every required rule passed. Exit code 5 means at least one
required rule failed; 2 is local configuration input, 3 is file output, and 4
is an API failure.

Do not gate only on p-values. A trivial effect becomes significant at large
sample size, and a harmful effect may be inconclusive at small sample size.
Combine an MPID, uncertainty bound, minimum paired count, failure/safety limits,
and operational cost/latency criteria.
