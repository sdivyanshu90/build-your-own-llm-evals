"""Fake-provider structured-output, stop, failure, and embedding edges."""

from __future__ import annotations

import math

import pytest
from eval_platform_providers.base import (
    EmbeddingRequest,
    GenerationRequest,
    ProviderError,
    ProviderErrorKind,
    StructuredOutputRequest,
)
from eval_platform_providers.fake import DeterministicFakeProvider


def test_fake_provider_rejects_invalid_dimensions() -> None:
    with pytest.raises(ValueError, match="positive"):
        DeterministicFakeProvider(embedding_dimensions=0)


@pytest.mark.asyncio
async def test_fake_provider_stop_failure_and_embeddings_are_deterministic() -> None:
    provider = DeterministicFakeProvider(
        responses={"prompt": "answer<stop>ignored"},
        failures={"fail": ProviderErrorKind.RATE_LIMIT},
        embedding_dimensions=4,
    )
    generated = await provider.generate(
        GenerationRequest(model="fake", prompt="prompt", stop=("<stop>",))
    )
    assert generated.text == "answer"
    with pytest.raises(ProviderError) as captured:
        await provider.generate(GenerationRequest(model="fake", prompt="fail"))
    assert captured.value.kind is ProviderErrorKind.RATE_LIMIT
    first = await provider.embed(EmbeddingRequest(model="fake", inputs=("same",)))
    second = await provider.embed(EmbeddingRequest(model="fake", inputs=("same",)))
    assert first.vectors == second.vectors
    assert len(first.vectors[0]) == 4
    assert math.sqrt(sum(value * value for value in first.vectors[0])) == pytest.approx(1)


@pytest.mark.asyncio
async def test_fake_structured_output_normalizes_json_and_schema_failures() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"score": {"type": "number"}},
        "required": ["score"],
    }
    valid = DeterministicFakeProvider(responses={"valid": '{"score":0.8}'})
    response = await valid.generate_structured(
        StructuredOutputRequest(
            generation=GenerationRequest(model="fake", prompt="valid"),
            schema_name="score",
            schema=schema,
        )
    )
    assert response.structured == {"score": 0.8}
    for raw in ("not-json", '{"other":1}'):
        provider = DeterministicFakeProvider(responses={"invalid": raw})
        with pytest.raises(ProviderError) as captured:
            await provider.generate_structured(
                StructuredOutputRequest(
                    generation=GenerationRequest(model="fake", prompt="invalid"),
                    schema_name="score",
                    schema=schema,
                )
            )
        assert captured.value.kind is ProviderErrorKind.MALFORMED_STRUCTURED_OUTPUT
