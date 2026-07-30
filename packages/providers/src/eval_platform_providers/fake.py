"""Deterministic no-network provider for tests and demonstrations."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping

from jsonschema import Draft202012Validator

from eval_platform_providers.base import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerationRequest,
    GenerationResponse,
    ProviderCapability,
    ProviderError,
    ProviderErrorKind,
    StructuredOutputRequest,
    Usage,
)


class DeterministicFakeProvider:
    """Return deterministic scripted or derived outputs without external calls."""

    def __init__(
        self,
        identifier: str = "fake/default",
        *,
        responses: Mapping[str, str] | None = None,
        failures: Mapping[str, ProviderErrorKind] | None = None,
        embedding_dimensions: int = 16,
    ) -> None:
        if embedding_dimensions < 1:
            raise ValueError("embedding_dimensions must be positive")
        self._identifier = identifier
        self._responses = dict(responses or {})
        self._failures = dict(failures or {})
        self._embedding_dimensions = embedding_dimensions

    @property
    def identifier(self) -> str:
        return self._identifier

    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset(ProviderCapability)

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        source = request.prompt or "\n".join(
            f"{message.role}: {message.content}" for message in request.messages
        )
        if source in self._failures:
            kind = self._failures[source]
            raise ProviderError(kind, f"scripted fake failure: {kind}", retry_after_seconds=0)
        text = self._responses.get(source, f"fake:{source.strip()}")
        for stop in request.stop:
            if stop and stop in text:
                text = text.split(stop, maxsplit=1)[0]
        input_tokens = self.count_tokens(request.model, source)
        output_tokens = self.count_tokens(request.model, text)
        request_id = hashlib.sha256(
            f"{self.identifier}\x00{source}\x00{request.seed}".encode()
        ).hexdigest()[:24]
        return GenerationResponse(
            text=text,
            model=request.model,
            finish_reason="stop",
            usage=Usage(input_tokens, output_tokens, input_tokens + output_tokens),
            provider_request_id=f"fake-{request_id}",
            raw_metadata={"deterministic": True},
        )

    async def generate_structured(self, request: StructuredOutputRequest) -> GenerationResponse:
        response = await self.generate(request.generation)
        try:
            structured = json.loads(response.text)
        except json.JSONDecodeError as error:
            raise ProviderError(
                ProviderErrorKind.MALFORMED_STRUCTURED_OUTPUT,
                "fake structured response is not valid JSON",
                provider_request_id=response.provider_request_id,
            ) from error
        errors = list(Draft202012Validator(request.schema).iter_errors(structured))
        if errors:
            raise ProviderError(
                ProviderErrorKind.MALFORMED_STRUCTURED_OUTPUT,
                "fake structured response does not satisfy its schema",
                provider_request_id=response.provider_request_id,
            )
        return GenerationResponse(
            text=response.text,
            model=response.model,
            finish_reason=response.finish_reason,
            usage=response.usage,
            provider_request_id=response.provider_request_id,
            structured=structured,
            raw_metadata=response.raw_metadata,
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        dimensions = request.dimensions or self._embedding_dimensions
        vectors = tuple(self._vector(text, dimensions) for text in request.inputs)
        tokens = sum(self.count_tokens(request.model, text) for text in request.inputs)
        return EmbeddingResponse(
            vectors=vectors,
            model=request.model,
            usage=Usage(tokens, 0, tokens),
            provider_request_id=f"fake-embed-{hashlib.sha256(repr(request).encode()).hexdigest()[:16]}",
        )

    def count_tokens(self, model: str, text: str) -> int:
        del model
        return max(1, len(text.encode("utf-8")) // 4) if text else 0

    @staticmethod
    def _vector(text: str, dimensions: int) -> tuple[float, ...]:
        values: list[float] = []
        for index in range(dimensions):
            digest = hashlib.sha256(f"{index}\x00{text}".encode()).digest()
            value = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
            values.append((value * 2) - 1)
        norm = math.sqrt(sum(value * value for value in values))
        return tuple(value / norm for value in values) if norm else tuple(values)
