# ADR 0002: Immutable schema-aware dataset identity

- Status: Accepted
- Date: 2026-07-29

## Context

Bytewise source hashes vary with key order, whitespace, Unicode composition,
line endings, timezone offsets, negative zero, and explicit nulls even when
the evaluation meaning is equal. Aggressive generic normalization can also
collapse values that are semantically different.

## Decision

Dataset versions are immutable and content-addressed with SHA-256 over
schema-aware normalized records serialized using JSON Canonicalization Scheme.
The canonicalization algorithm has an explicit version. Record logical keys
drive diffs; payload and envelope hashes distinguish duplicate task content
from metadata/provenance changes.

## Consequences

Equivalent supported representations receive stable identity, experiments can
prove their exact data dependency, and golden fixtures detect accidental
algorithm drift. Schema authors carry responsibility for declaring timestamps
and optional nullable fields correctly. Any semantic rule change requires a
new canonicalization version rather than rewriting old hashes.
