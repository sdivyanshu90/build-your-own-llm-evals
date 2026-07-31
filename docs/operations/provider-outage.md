# Provider outage response

Provider errors are normalized as authentication, permission, rate limit,
context length, invalid request, timeout, connection, server, content policy,
malformed structured output, or unknown.

- Authentication/permission failures are not retried; verify secret rotation
  and provider account status.
- Rate limits honor `Retry-After`, reduce concurrency, and use exponential
  backoff with jitter.
- Timeouts, connection, and server errors use bounded retries.
- Invalid request, context length, policy, and malformed output need data or
  configuration review.

Pause dispatch when retries amplify an outage. Preserve partial results and
ambiguous-billing flags. Notify affected projects of the exact time window and
missing-data impact. Resume with a small canary run, then ramp concurrency while
watching error rate, latency, tokens, and cost.
