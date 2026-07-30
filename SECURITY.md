# Security policy

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Email
`security@example.invalid` with the affected version, reproduction steps,
impact, and any suggested mitigation. The address is an externally supplied
project value and must be replaced before the first public release.

Maintainers will acknowledge a report within three business days, provide a
triage update within seven business days, coordinate a fix and disclosure, and
credit reporters who request attribution. Please avoid accessing other tenants,
causing provider charges, or retaining sensitive data while investigating.

## Supported versions

Before the first stable release, only the latest tagged pre-release receives
security fixes. Stable support windows will be published in release notes.

## Security posture

Production deployments must disable development authentication, use TLS,
inject unique secrets through a secret manager, restrict outbound provider
destinations, configure project budgets, enable PostgreSQL backups, and review
provider data-sharing policies. See the threat model and operations guides.

Prompt delimiters, schema validation, and redaction reduce risk but do not make
LLM judges immune to prompt injection or guarantee detection of personal data.
