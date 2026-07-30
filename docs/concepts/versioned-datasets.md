# Versioned datasets

## Definition and motivation

A dataset is a mutable catalog identity. A dataset version is an immutable,
published manifest containing a schema, metadata, ordered records, source
provenance, split membership, canonicalization version, and content hash.
Experiments reference the version, never “latest.” This separates convenient
human naming from reproducible evidence.

Publication is atomic. Parsing, schema validation, key uniqueness checks,
canonicalization, duplicate counting, split counting, and version hashing
finish before any manifest is committed. A failed record prevents the complete
version from becoming visible.

## Canonicalization algorithm

The implementation uses JSON Canonicalization Scheme ordering after applying
schema-aware normalization:

1. Normalize strings to Unicode NFC and line endings to `LF`.
2. Normalize fields declared with `format: date-time` to UTC using a `Z`
   suffix; naive timestamps are invalid.
3. Reject non-finite floating-point values. Normalize negative zero to zero.
4. Recursively sort object keys through canonical JSON serialization.
5. For optional schema properties only, treat absent and explicit `null` as
   equivalent by removing `null` when the field is not required and its schema
   admits null.
6. Keep array order because it is normally semantic.
7. Hash canonical UTF-8 bytes with SHA-256.

Record `payload_hash` identifies the normalized task payload. Record
`envelope_hash` additionally covers key, metadata, splits, and provenance.
The dataset version hash covers the schema, version metadata, and all envelopes
sorted by record key.

This design intentionally does not collapse numeric strings with numbers,
unordered arrays with ordered arrays, missing required values with null, or
timestamps not declared by the schema. Those changes can alter evaluation
meaning. Changing any canonical rule requires a new canonicalization version;
old versions retain their original identity.

### Worked example

These payloads are equivalent under a schema that declares `when` as a
date-time and `optional` as nullable and optional:

```json
{"text":"Café\r\nline","when":"2024-01-01T05:30:00+05:30","score":-0.0}
```

```json
{"optional":null,"score":0,"text":"Café\nline","when":"2024-01-01T00:00:00Z"}
```

The golden test fixes their SHA-256 content identity at
`41e8ffe1d572578fd3eab5c8d773760c09978bfffd1a74e6b1038b87e0c73775`.
Any intentional algorithm change must change both the algorithm version and a
reviewed golden fixture.

## Schemas and imports

Built-in JSON Schemas cover generation, QA, classification, summarization,
extraction, RAG, preference, agent, and multi-turn conversation records.
Custom Draft 2020-12 JSON Schemas are accepted after structural validation.
API publication and bounded upload parsers support JSON, JSONL, CSV, and
Parquet. The parser iterates records and enforces a maximum record count;
Parquet reads batches. Production-scale uploads should be staged in object
storage before publication so a request does not retain all canonical records
in process memory—this reconciliation workflow is not yet implemented.

Record keys are stable logical identities. Reusing a payload under two keys is
allowed and reported as a duplicate payload; reusing a key inside one version
is rejected. Splits are normalized labels and may include standard names or
custom values.

## Diffs, sampling, and lineage

Diff aligns versions by record key:

- added: present only in the target;
- removed: present only in the source;
- modified: same key, different envelope hash, with field-level changes;
- unchanged: identical envelope hashes.

The direction is explicit, so swapping versions swaps added and removed while
preserving modified/unchanged membership. Deterministic sampling uses a seed
and a stable hash of seed plus record key rather than process hash order.
Stratified sampling applies the same method within each declared stratum and
reports undersized strata.

Each record stores source kind, optional URI, source row, and source hash.
Versions can list parent version IDs. A future transformation registry will
add typed transformation parameters; today callers place transformation
metadata in the immutable version metadata.

## Redaction and sensitive fields

Redaction walks JSON pointers and replaces configured values without mutating
the source. It is suitable for display and export policies, not for changing an
already published version. Redacting persisted evidence creates a new version
or a retention tombstone because changing bytes in place would invalidate
historical hashes.

## Contamination checks and limitations

The domain package supplies normalized n-grams, MinHash signatures, LSH
buckets, and candidate overlap reports. These are screening heuristics:

- exact or high n-gram overlap misses paraphrases and translations;
- MinHash approximates set Jaccard similarity and depends on tokenization,
  shingle size, permutations, bands, and threshold;
- embedding similarity depends on model/version and can confuse topical
  similarity with leakage;
- reference-answer overlap may identify conventional phrases rather than
  memorization.

A low score never proves absence of training contamination. Reports must state
the detector configuration, candidate corpus, threshold, and false
positive/negative limitations.

## Testing and operations

Golden, property, and unit tests assert idempotent canonicalization, stable
hashes for equivalent values, deterministic sampling, diff symmetry,
stratification, redaction, and contamination candidate behavior. Database
triggers reject updates and deletes of published version content. Backups must
retain manifests, records, artifacts, migration history, and the application
version that understands the canonicalization version.
