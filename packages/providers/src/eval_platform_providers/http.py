"""OpenAI-compatible and configurable HTTP provider adapters."""

from __future__ import annotations

import asyncio
import email.utils
import ipaddress
import json
import socket
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
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


def _error_kind(status: int, body: str) -> ProviderErrorKind:
    lowered = body.casefold()
    if status == 401:
        return ProviderErrorKind.AUTHENTICATION
    if status == 403:
        return (
            ProviderErrorKind.CONTENT_POLICY
            if "policy" in lowered or "safety" in lowered
            else ProviderErrorKind.PERMISSION
        )
    if status == 429:
        return ProviderErrorKind.RATE_LIMIT
    if status == 400:
        if "context" in lowered and ("length" in lowered or "token" in lowered):
            return ProviderErrorKind.CONTEXT_LENGTH
        return ProviderErrorKind.INVALID_REQUEST
    if status >= 500:
        return ProviderErrorKind.SERVER
    return ProviderErrorKind.UNKNOWN


def _retry_after_seconds(value: str | None) -> float | None:
    """Parse either Retry-After seconds or an HTTP date without raising."""

    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return max(0.0, (parsed - datetime.now(UTC)).total_seconds())


def _usage(value: Mapping[str, Any]) -> Usage:
    """Normalize usage while retaining billable reasoning/thinking tokens."""

    input_tokens = int(value.get("prompt_tokens", 0))
    visible_output_tokens = int(value.get("completion_tokens", 0))
    provider_total = int(value.get("total_tokens", input_tokens + visible_output_tokens))
    output_tokens = max(visible_output_tokens, provider_total - input_tokens)
    return Usage(input_tokens, output_tokens, input_tokens + output_tokens)


async def _validate_destination(
    url: str,
    *,
    allow_http: bool,
    allow_private: bool,
) -> None:
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        raise ProviderError(
            ProviderErrorKind.INVALID_REQUEST,
            "provider URL must not contain credentials",
        )
    if parsed.scheme not in ({"https", "http"} if allow_http else {"https"}):
        raise ProviderError(
            ProviderErrorKind.INVALID_REQUEST,
            "provider URL uses a forbidden scheme",
        )
    if not parsed.hostname:
        raise ProviderError(ProviderErrorKind.INVALID_REQUEST, "provider URL has no host")
    try:
        results = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise ProviderError(
            ProviderErrorKind.CONNECTION,
            "provider host could not be resolved",
        ) from error
    if not allow_private:
        for result in results:
            address = ipaddress.ip_address(result[4][0])
            if (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            ):
                raise ProviderError(
                    ProviderErrorKind.INVALID_REQUEST,
                    "provider host resolves to a forbidden network",
                )


class OpenAICompatibleProvider:
    """HTTP-only OpenAI-compatible adapter without vendor SDK coupling."""

    def __init__(
        self,
        *,
        identifier: str,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 60,
        max_response_bytes: int = 10 * 1024 * 1024,
        allow_http: bool = False,
        allow_private: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._identifier = identifier
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._allow_http = allow_http
        self._allow_private = allow_private
        self._client = client

    @property
    def identifier(self) -> str:
        return self._identifier

    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset(
            {
                ProviderCapability.TEXT,
                ProviderCapability.CHAT,
                ProviderCapability.STRUCTURED,
                ProviderCapability.EMBEDDING,
                ProviderCapability.TOKEN_COUNT,
                ProviderCapability.SEED,
                ProviderCapability.IDEMPOTENCY,
            }
        )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        endpoint = f"{self._base_url}/chat/completions"
        messages = (
            [{"role": "user", "content": request.prompt}]
            if request.prompt is not None
            else [
                {"role": message.role, "content": message.content} for message in request.messages
            ]
        )
        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_output_tokens,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.seed is not None:
            body["seed"] = request.seed
        if request.reasoning_effort is not None:
            body["reasoning_effort"] = request.reasoning_effort
        if request.stop:
            body["stop"] = list(request.stop)
        payload, headers = await self._post(endpoint, body, request.idempotency_key)
        try:
            choice = payload["choices"][0]
            text = choice["message"]["content"]
            usage_value = payload.get("usage", {})
            return GenerationResponse(
                text=str(text),
                model=str(payload.get("model", request.model)),
                finish_reason=str(choice.get("finish_reason", "unknown")),
                usage=_usage(usage_value),
                provider_request_id=headers.get("x-request-id") or payload.get("id"),
            )
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError(
                ProviderErrorKind.UNKNOWN,
                "provider response does not match the compatible response schema",
                provider_request_id=headers.get("x-request-id"),
            ) from error

    async def generate_structured(self, request: StructuredOutputRequest) -> GenerationResponse:
        generation = request.generation
        endpoint = f"{self._base_url}/chat/completions"
        messages = (
            [{"role": "user", "content": generation.prompt}]
            if generation.prompt is not None
            else [
                {"role": message.role, "content": message.content}
                for message in generation.messages
            ]
        )
        body: dict[str, Any] = {
            "model": generation.model,
            "messages": messages,
            "max_tokens": generation.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "strict": True,
                    "schema": request.schema,
                },
            },
        }
        if generation.temperature is not None:
            body["temperature"] = generation.temperature
        if generation.reasoning_effort is not None:
            body["reasoning_effort"] = generation.reasoning_effort
        payload, headers = await self._post(
            endpoint,
            body,
            generation.idempotency_key,
        )
        try:
            choice = payload["choices"][0]
            text = str(choice["message"]["content"])
            structured = json.loads(text)
            errors = list(Draft202012Validator(request.schema).iter_errors(structured))
            if errors:
                raise ValueError(errors[0].message)
            usage_value = payload.get("usage", {})
            return GenerationResponse(
                text=text,
                structured=structured,
                model=str(payload.get("model", generation.model)),
                finish_reason=str(choice.get("finish_reason", "unknown")),
                usage=_usage(usage_value),
                provider_request_id=headers.get("x-request-id") or payload.get("id"),
            )
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ProviderError(
                ProviderErrorKind.MALFORMED_STRUCTURED_OUTPUT,
                "provider returned invalid structured output",
                provider_request_id=headers.get("x-request-id"),
            ) from error

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        body: dict[str, Any] = {"model": request.model, "input": list(request.inputs)}
        if request.dimensions is not None:
            body["dimensions"] = request.dimensions
        payload, headers = await self._post(f"{self._base_url}/embeddings", body, None)
        try:
            ordered = sorted(payload["data"], key=lambda item: int(item["index"]))
            vectors = tuple(tuple(float(value) for value in item["embedding"]) for item in ordered)
            usage_value = payload.get("usage", {})
            input_tokens = int(usage_value.get("prompt_tokens", 0))
            return EmbeddingResponse(
                vectors=vectors,
                model=str(payload.get("model", request.model)),
                usage=Usage(input_tokens, 0, input_tokens),
                provider_request_id=headers.get("x-request-id") or payload.get("id"),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError(
                ProviderErrorKind.UNKNOWN,
                "provider returned an invalid embedding response",
            ) from error

    def count_tokens(self, model: str, text: str) -> int:
        del model
        return max(1, len(text.encode()) // 4) if text else 0

    async def _post(
        self,
        url: str,
        body: Mapping[str, Any],
        idempotency_key: str | None,
    ) -> tuple[dict[str, Any], Mapping[str, str]]:
        await _validate_destination(
            url,
            allow_http=self._allow_http,
            allow_private=self._allow_private,
        )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=False,
        )
        close = self._client is None
        try:
            response = await client.post(url, headers=headers, json=body)
            content = await response.aread()
            if len(content) > self._max_response_bytes:
                raise ProviderError(
                    ProviderErrorKind.INVALID_REQUEST,
                    "provider response exceeds the configured size limit",
                    provider_request_id=response.headers.get("x-request-id"),
                )
            if response.is_error:
                raise ProviderError(
                    _error_kind(response.status_code, content[:2000].decode(errors="replace")),
                    f"provider request failed with status {response.status_code}",
                    retry_after_seconds=_retry_after_seconds(response.headers.get("retry-after")),
                    provider_request_id=response.headers.get("x-request-id"),
                )
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("response root is not an object")
            return payload, response.headers
        except httpx.TimeoutException as error:
            raise ProviderError(
                ProviderErrorKind.TIMEOUT,
                "provider request timed out",
                ambiguous_billing=True,
            ) from error
        except httpx.NetworkError as error:
            raise ProviderError(
                ProviderErrorKind.CONNECTION,
                "provider connection failed",
                ambiguous_billing=True,
            ) from error
        except json.JSONDecodeError as error:
            raise ProviderError(
                ProviderErrorKind.UNKNOWN,
                "provider returned invalid JSON",
            ) from error
        finally:
            if close:
                await client.aclose()


class LocalOpenAICompatibleProvider(OpenAICompatibleProvider):
    """Explicit local/self-hosted profile that permits private HTTP destinations."""

    def __init__(
        self,
        *,
        identifier: str,
        base_url: str,
        api_key: str = "local-no-secret",
        timeout_seconds: float = 60,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            identifier=identifier,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            allow_http=True,
            allow_private=True,
            client=client,
        )


class GenericHttpProvider(OpenAICompatibleProvider):
    """Configuration-driven HTTP adapter using the documented compatible schema.

    The generic adapter deliberately accepts no templates that execute code. Its
    configured endpoint must expose the stable OpenAI-compatible JSON shapes;
    header names and secret values remain controlled by deployment configuration.
    """
