# Dataset workflow

## Create a catalog

In development, identify the tenant explicitly:

```bash
export EVAL_ORGANIZATION_ID=01900000-0000-7000-8000-000000000001
evalctl project list
```

Create a dataset through `POST
/api/v1/projects/{project_id}/datasets` with a lowercase slug, name,
description, and tags. The catalog is not evaluation evidence until it has a
published version.

## Publish records

API publication accepts a JSON Schema and records with `key`, `payload`,
optional `metadata`, and `splits`. Upload publication additionally accepts
JSON, JSONL, CSV, or Parquet and enforces `EVAL_MAX_UPLOAD_BYTES` and
`EVAL_MAX_IMPORT_RECORDS`.

JSONL example:

```json
{"key":"q1","payload":{"question":"What is 2+2?","answers":["4"]},"metadata":{"difficulty":"easy"},"splits":["test"]}
{"key":"q2","payload":{"question":"Capital of France?","answers":["Paris"]},"metadata":{"difficulty":"easy"},"splits":["test"]}
```

Publishers should choose record keys that remain stable across corrections. A
corrected payload under the same key appears as modified in a diff; assigning a
new key appears as remove plus add.

## Verify and compare

The version response includes canonicalization version, content hash, record
count, duplicate payload count, and split counts. Records are keyset-paginated.
The export endpoint returns the exact normalized historical manifest and
records. The diff endpoint aligns two visible versions and reports
added/removed/modified/unchanged records.

Sampling accepts an explicit seed and optional split. Store the seed and
sampling configuration with any downstream evaluation. Do not sample using
database row order or language runtime hash order.

## Sensitive data

Declare sensitive JSON pointers in policy metadata and apply redaction before
display or external provider use. Never edit a published record to remove PII;
create a redacted successor and execute the configured retention/deletion
workflow. Before sending evaluation inputs to a judge or remote provider,
confirm that the provider data-handling policy permits those fields.
