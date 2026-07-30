"""Stable provider contract independent of vendor SDKs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ProviderCapability(StrEnum):
    """Discoverable provider operations."""

    TEXT = "text_generation"
    CHAT = "chat_completion"
    STRUCTURED = "structured_output"
    EMBEDDING = "embedding"
    TOKEN_COUNT = "token_count"  # noqa: S105 - capability name, not a credential
    SEED = "seed"
    IDEMPOTENCY = "idempotency"


class ProviderErrorKind(StrEnum):
    """Normalized stable provider error taxonomy."""

    AUTHENTICATION = "authentication_failure"
    PERMISSION = "permission_failure"
    RATE_LIMIT = "rate_limit"
    CONTEXT_LENGTH = "context_length_overflow"
    INVALID_REQUEST = "invalid_request"
    TIMEOUT = "timeout"
    CONNECTION = "connection_error"
    SERVER = "provider_server_error"
    CONTENT_POLICY = "content_policy_rejection"
    MALFORMED_STRUCTURED_OUTPUT = "malformed_structured_output"
    UNKNOWN = "unknown_provider_failure"


_RETRYABLE = frozenset(
    {
        ProviderErrorKind.RATE_LIMIT,
        ProviderErrorKind.TIMEOUT,
        ProviderErrorKind.CONNECTION,
        ProviderErrorKind.SERVER,
    }
)


class ProviderError(Exception):
    """Sanitized provider failure with stable retry semantics."""

    def __init__(
        self,
        kind: ProviderErrorKind,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        provider_request_id: str | None = None,
        ambiguous_billing: bool = False,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retryable = kind in _RETRYABLE
        self.retry_after_seconds = retry_after_seconds
        self.provider_request_id = provider_request_id
        self.ambiguous_billing = ambiguous_billing


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """One chat message."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Normalized text or chat generation request."""

    model: str
    prompt: str | None = None
    messages: tuple[ChatMessage, ...] = ()
    temperature: float | None = 0.0
    max_output_tokens: int = 512
    seed: int | None = None
    reasoning_effort: str | None = None
    stop: tuple[str, ...] = ()
    idempotency_key: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (self.prompt is None) == (not self.messages):
            raise ValueError("exactly one of prompt or messages is required")
        if self.temperature is not None and not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be in [0, 2]")
        if self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be positive")
        if self.reasoning_effort not in {None, "none", "minimal", "low", "medium", "high"}:
            raise ValueError("reasoning_effort is not a supported level")


@dataclass(frozen=True, slots=True)
class StructuredOutputRequest:
    """Generation request requiring JSON output under a supplied schema."""

    generation: GenerationRequest
    schema: dict[str, Any]
    schema_name: str = "response"


@dataclass(frozen=True, slots=True)
class EmbeddingRequest:
    """Embedding batch request."""

    model: str
    inputs: tuple[str, ...]
    dimensions: int | None = None

    def __post_init__(self) -> None:
        if not self.inputs:
            raise ValueError("embedding inputs must not be empty")


@dataclass(frozen=True, slots=True)
class Usage:
    """Normalized token and provider-reported cost usage."""

    input_tokens: int
    output_tokens: int
    total_tokens: int
    actual_cost: str | None = None
    currency: str = "USD"
    estimated: bool = False

    def __post_init__(self) -> None:
        if min(self.input_tokens, self.output_tokens, self.total_tokens) < 0:
            raise ValueError("token counts must be non-negative")
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total token count must equal input plus output")


@dataclass(frozen=True, slots=True)
class GenerationResponse:
    """Normalized provider generation response."""

    text: str
    model: str
    finish_reason: str
    usage: Usage
    provider_request_id: str | None = None
    structured: dict[str, Any] | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EmbeddingResponse:
    """Normalized embedding response."""

    vectors: tuple[tuple[float, ...], ...]
    model: str
    usage: Usage
    provider_request_id: str | None = None


class Provider(Protocol):
    """Contract every remote and local model adapter must implement."""

    @property
    def identifier(self) -> str:
        """Return the stable configured provider identifier."""

        raise TypeError("protocol declaration has no runtime implementation")

    def capabilities(self) -> frozenset[ProviderCapability]:
        """Return supported operations without making a paid request."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        """Generate text or chat output."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def generate_structured(self, request: StructuredOutputRequest) -> GenerationResponse:
        """Generate and validate structured output."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """Embed one or more inputs."""

        raise TypeError("protocol declaration has no runtime implementation")

    def count_tokens(self, model: str, text: str) -> int:
        """Return a provider tokenizer count or documented estimate."""

        raise TypeError("protocol declaration has no runtime implementation")
