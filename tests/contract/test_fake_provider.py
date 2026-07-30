"""Shared provider contract exercised by the deterministic fake."""

from __future__ import annotations

import pytest
from eval_platform_providers.base import (
    EmbeddingRequest,
    GenerationRequest,
    ProviderCapability,
    ProviderError,
    ProviderErrorKind,
)
from eval_platform_providers.fake import DeterministicFakeProvider


@pytest.mark.asyncio
async def test_fake_generation_usage_and_request_id_are_reproducible() -> None:
    provider = DeterministicFakeProvider(responses={"hello": "world"})
    request = GenerationRequest(model="fake-model", prompt="hello", seed=7)
    first = await provider.generate(request)
    second = await provider.generate(request)
    assert first == second
    assert first.text == "world"
    assert first.usage.total_tokens == first.usage.input_tokens + first.usage.output_tokens
    assert ProviderCapability.STRUCTURED in provider.capabilities()


@pytest.mark.asyncio
async def test_fake_embedding_dimensions_and_norm() -> None:
    provider = DeterministicFakeProvider(embedding_dimensions=8)
    response = await provider.embed(EmbeddingRequest("fake-embed", ("hello", "world")))
    assert len(response.vectors) == 2
    assert all(len(vector) == 8 for vector in response.vectors)
    assert response.vectors[0] != response.vectors[1]


@pytest.mark.asyncio
async def test_fake_normalizes_scripted_failure() -> None:
    provider = DeterministicFakeProvider(failures={"limited": ProviderErrorKind.RATE_LIMIT})
    with pytest.raises(ProviderError) as captured:
        await provider.generate(GenerationRequest(model="fake", prompt="limited"))
    assert captured.value.retryable is True
    assert "secret" not in captured.value.message
