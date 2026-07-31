# ADR 0005: Strict judges and paired statistical analysis

- Status: Accepted
- Date: 2026-07-30

## Context

Model-based evaluation introduces untrusted prompt content, structured-output
failures, judge bias, repeated judgments, and additional cost. Experiment
comparison usually observes the same records under both systems, so independent
sample procedures discard important covariance.

## Decision

Judge configurations, rubrics, pair designs, and judgments are immutable
project resources. Candidate identities are blinded. Untrusted evidence uses
length-labelled line envelopes. Responses follow `judge-response/1`; hidden
chain-of-thought is not requested or stored. Repairs and retries are bounded,
and abstention remains distinct from a tie.

Statistical analysis aligns stable record/repetition identities and uses paired
intervals and tests. Wilson is the default proportion interval, BCa is the
default comparison interval, and Holm adjusts a requested metric family.
Effects, practical thresholds, missing counts, warnings, confidence, and seeds
are stored with results. Bradley-Terry and Davidson are batch ranking models;
Elo is explicitly descriptive.

## Consequences

Reports are more interpretable and reproducible, and most comparison procedures
gain precision. The system must retain record identity and failure state.
Bootstrap and ranking work consume CPU, so scientific modules are lazy-loaded
and expensive analyses belong on workers at high volume. Judge delimiting
reduces but cannot eliminate prompt-injection risk.
