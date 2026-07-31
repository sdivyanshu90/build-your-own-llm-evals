# Cost incident response

Immediately pause affected runs and disable provider dispatch for the project.
Compare project/run budgets, estimated reservations, actual provider usage,
ambiguous attempts, token counts, and the provider invoice. Rotate a compromised
key and reduce account-level provider limits when abuse is suspected.

Do not erase billed failed records: reports need their denominator and the
ledger needs reconciliation. Classify cause as price-table drift, unexpected
output length, retry amplification, duplicate non-idempotent request,
configuration error, or credential abuse. Backfill corrected prices as new
ledger adjustments rather than rewriting historical entries.

Resume only after a canary estimate and hard provider/project cap agree. Record
timeline, exposure, affected tenants, and preventive action.
