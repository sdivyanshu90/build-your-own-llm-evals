# Python SDK

`EvalPlatformClient` is a synchronous, typed client intended for scripts, CI,
and notebooks. It owns an `httpx` connection pool and should be used as a
context manager:

```python
import os
import uuid

from eval_platform_sdk import EvalPlatformClient

with EvalPlatformClient(
    "https://eval.example.com",
    api_key=os.environ["EVAL_API_KEY"],
) as client:
    run = client.get_run(
        uuid.UUID(os.environ["EVAL_PROJECT_ID"]),
        uuid.UUID(os.environ["EVAL_RUN_ID"]),
    )
    print(run.state, run.succeeded_tasks, run.failed_tasks)
```

The SDK validates responses with the same Pydantic v2 schemas used by the API.
Unexpected shapes therefore fail at the client boundary rather than leaking
untyped dictionaries into automation. `ApiClientError` retains the HTTP status
and stable server error body without including Authorization headers.

Dataset import streams a multipart file from disk. Comparison report export
returns text for JSON, safe CSV, Markdown, or printable HTML. Gate responses are
typed and leave process exit policy to the caller; `evalctl gate check` supplies
the standard exit-code behavior.

The v1 REST surface is additive within a minor release. Removals or meaning
changes require a new major path and the deprecation process documented in the
API compatibility policy.
