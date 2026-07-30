"""Deterministic HTTP provider contract and error normalization tests."""

from __future__ import annotations

import json

import httpx
import pytest
from eval_platform_providers.base import (
    EmbeddingRequest,
    GenerationRequest,
    ProviderError,
    ProviderErrorKind,
    StructuredOutputRequest,
)
from eval_platform_providers.http import (
    LocalOpenAICompatibleProvider,
    _error_kind,
    _retry_after_seconds,
    _usage,
    _validate_destination,
)


def _provider(handler: httpx.AsyncBaseTransport) -> LocalOpenAICompatibleProvider:
    return LocalOpenAICompatibleProvider(
        identifier="local/contract",
        base_url="http://127.0.0.1/v1",
        client=httpx.AsyncClient(transport=handler),
    )


async def test_generation_structured_and_embedding_contract() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                headers={"x-request-id": "embed-request"},
                json={
                    "id": "embed-id",
                    "model": body["model"],
                    "data": [
                        {"index": 1, "embedding": [0, 1]},
                        {"index": 0, "embedding": [1, 0]},
                    ],
                    "usage": {"prompt_tokens": 4},
                },
            )
        content = '{"answer":"ok"}' if "response_format" in body else "plain answer"
        return httpx.Response(
            200,
            headers={"x-request-id": "generation-request"},
            json={
                "id": "response-id",
                "model": body["model"],
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2},
            },
        )

    provider = _provider(httpx.MockTransport(handler))
    response = await provider.generate(
        GenerationRequest(
            model="test",
            prompt="hello",
            temperature=0,
            max_output_tokens=20,
            seed=7,
            stop=("END",),
            idempotency_key="task-key",
        )
    )
    assert response.text == "plain answer"
    assert response.usage.total_tokens == 5
    assert response.provider_request_id == "generation-request"
    structured = await provider.generate_structured(
        StructuredOutputRequest(
            generation=GenerationRequest(model="test", prompt="json"),
            schema_name="answer",
            schema={
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
        )
    )
    assert structured.structured == {"answer": "ok"}
    embedding = await provider.embed(
        EmbeddingRequest(model="embedding", inputs=("one", "two"), dimensions=2)
    )
    assert embedding.vectors == ((1.0, 0.0), (0.0, 1.0))
    assert embedding.provider_request_id == "embed-request"
    assert provider.count_tokens("test", "12345678") == 2


async def test_generation_can_omit_sampling_and_set_reasoning_effort() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "temperature" not in body
        assert body["reasoning_effort"] == "minimal"
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "choices": [{"message": {"content": "391"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 2,
                    "total_tokens": 30,
                },
            },
        )

    provider = _provider(httpx.MockTransport(handler))
    response = await provider.generate(
        GenerationRequest(
            model="reasoning",
            prompt="multiply",
            temperature=None,
            reasoning_effort="minimal",
        )
    )

    assert response.text == "391"
    assert response.usage.output_tokens == 10


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [
        (401, "", ProviderErrorKind.AUTHENTICATION),
        (403, "policy rejected", ProviderErrorKind.CONTENT_POLICY),
        (403, "", ProviderErrorKind.PERMISSION),
        (429, "", ProviderErrorKind.RATE_LIMIT),
        (400, "context token length", ProviderErrorKind.CONTEXT_LENGTH),
        (400, "", ProviderErrorKind.INVALID_REQUEST),
        (503, "", ProviderErrorKind.SERVER),
        (418, "", ProviderErrorKind.UNKNOWN),
    ],
)
def test_status_error_taxonomy(status: int, body: str, kind: ProviderErrorKind) -> None:
    assert _error_kind(status, body) is kind


def test_retry_after_accepts_seconds_date_and_invalid_values() -> None:
    assert _retry_after_seconds("2.5") == 2.5
    assert _retry_after_seconds("invalid") is None
    assert _retry_after_seconds(None) is None
    assert _retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT") == 0


def test_usage_counts_hidden_reasoning_as_billable_output() -> None:
    usage = _usage({"prompt_tokens": 27, "completion_tokens": 2, "total_tokens": 55})

    assert usage.input_tokens == 27
    assert usage.output_tokens == 28
    assert usage.total_tokens == 55


async def test_http_errors_invalid_json_schema_and_size_are_normalized() -> None:
    responses = iter(
        [
            httpx.Response(429, headers={"retry-after": "2"}, text="slow down"),
            httpx.Response(200, content=b"not-json"),
            httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": '{"wrong":1}'}}],
                    "usage": {},
                },
            ),
        ]
    )

    provider = _provider(httpx.MockTransport(lambda _request: next(responses)))
    with pytest.raises(ProviderError) as limited:
        await provider.generate(GenerationRequest(model="test", prompt="one"))
    assert limited.value.kind is ProviderErrorKind.RATE_LIMIT
    assert limited.value.retry_after_seconds == 2
    with pytest.raises(ProviderError) as invalid_json:
        await provider.generate(GenerationRequest(model="test", prompt="two"))
    assert invalid_json.value.kind is ProviderErrorKind.UNKNOWN
    with pytest.raises(ProviderError) as malformed:
        await provider.generate_structured(
            StructuredOutputRequest(
                generation=GenerationRequest(model="test", prompt="three"),
                schema_name="answer",
                schema={
                    "type": "object",
                    "required": ["answer"],
                    "properties": {"answer": {"type": "string"}},
                },
            )
        )
    assert malformed.value.kind is ProviderErrorKind.MALFORMED_STRUCTURED_OUTPUT

    large = LocalOpenAICompatibleProvider(
        identifier="large",
        base_url="http://127.0.0.1",
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: httpx.Response(200, content=b"12345"))
        ),
    )
    large._max_response_bytes = 4
    with pytest.raises(ProviderError, match="size limit"):
        await large.generate(GenerationRequest(model="test", prompt="large"))


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:password@example.com",
        "https:///no-host",
    ],
)
async def test_destination_validation_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ProviderError) as captured:
        await _validate_destination(url, allow_http=False, allow_private=False)
    assert captured.value.kind is ProviderErrorKind.INVALID_REQUEST
