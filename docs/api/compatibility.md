# API compatibility and deprecation

The stable REST prefix is `/api/v1`. Within v1:

- existing response fields are not removed or retyped;
- new optional response fields and endpoints may be added;
- request validation remains closed to unknown fields;
- enum additions are announced because exhaustive clients may need updates;
- keyset cursors are opaque and cannot be constructed by clients;
- stored schema versions such as `judge-response/1` evolve independently.

An incompatible change receives a new API prefix or a migration period with
parallel representations. Deprecated endpoints return `Deprecation`, `Sunset`,
and documentation `Link` headers for at least one minor release and 90 days,
whichever is longer. Security fixes may shorten the window with a published
advisory.

OpenAPI is served at `/api/openapi.json`. Python SDK schemas are maintained from
the same Pydantic contracts. The TypeScript client validates responses with
Zod, so unexpected server drift fails visibly rather than corrupting dashboard
state.

Errors use a stable object containing `error`, safe `message`, `request_id`, and
field `details`. Not-found intentionally covers cross-tenant denials. Clients
must not branch on prose.
