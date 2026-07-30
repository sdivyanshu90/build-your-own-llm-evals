"""Vendor-neutral model provider contracts and built-in adapters."""

from eval_platform_providers.base import (
    ChatMessage,
    EmbeddingRequest,
    EmbeddingResponse,
    GenerationRequest,
    GenerationResponse,
    Provider,
    ProviderError,
    ProviderErrorKind,
    StructuredOutputRequest,
    Usage,
)
from eval_platform_providers.fake import DeterministicFakeProvider

__all__ = [
    "ChatMessage",
    "DeterministicFakeProvider",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "GenerationRequest",
    "GenerationResponse",
    "Provider",
    "ProviderError",
    "ProviderErrorKind",
    "StructuredOutputRequest",
    "Usage",
]
