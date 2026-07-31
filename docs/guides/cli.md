# Command-line interface

`evalctl` is the non-interactive automation surface. Global options precede the
resource command:

```bash
evalctl \
  --base-url http://localhost:8000 \
  --organization-id "$EVAL_ORGANIZATION_ID" \
  --project-id "$EVAL_PROJECT_ID" \
  --json \
  project list
```

Production uses `--api-key` or `EVAL_API_KEY`; development header identity is
rejected by a production-configured API. Flags override environment variables.
Every request has a bounded timeout (`--timeout`, default 30 seconds).

## Datasets and suites

Validate locally before upload:

```bash
evalctl --json dataset validate \
  --source examples/datasets/qa.jsonl \
  --import-format jsonl \
  --schema-identifier qa/v1
```

Validation makes no network call, caps records, checks the versioned JSON
Schema, returns exit 2 on validation errors, and truncates displayed errors
after 100 while preserving the total error count. Publish with:

```bash
evalctl dataset import \
  --project-id "$EVAL_PROJECT_ID" \
  --dataset-id "$DATASET_ID" \
  --source examples/datasets/qa.jsonl \
  --import-format jsonl \
  --schema-identifier qa/v1
```

`dataset publish` accepts a complete `DatasetVersionCreate` JSON body.
`dataset diff` compares immutable versions. `suite create` validates and
normalizes the suite block embedded in an immutable experiment snapshot:

```bash
evalctl suite create --specification suite-input.json --output suite.json
```

## Runs, results, comparisons, and gates

The core automation commands are `experiment create`, `run start`, `run
status`, `run cancel`, `run resume`, `results show`, `compare`, `report export`,
and `gate check`. Shell completion is provided by Typer's
`--install-completion` and `--show-completion`.

Exit codes are stable: 0 success, 2 local input/configuration, 3 local output
I/O, 4 API failure, and 5 required quality-gate failure. JSON mode writes only
machine-readable output on success. Secrets are sent only in the Authorization
header and are never included in rendered configuration.
