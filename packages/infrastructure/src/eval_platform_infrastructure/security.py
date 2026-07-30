"""Credential hashing and structure-aware secret redaction."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_KEYS = frozenset(
    {
        "authorization",
        "api_key",
        "apikey",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
    }
)


def generate_api_key() -> tuple[str, str]:
    """Return a one-time raw key and its public lookup prefix."""

    raw = f"evp_{secrets.token_urlsafe(32)}"
    return raw, raw[:16]


def api_key_digest(raw_key: str, pepper: str) -> bytes:
    """Return a keyed digest suitable for storage and constant-time comparison."""

    return hmac.new(pepper.encode(), raw_key.encode(), hashlib.sha256).digest()


def verify_api_key(raw_key: str, expected: bytes, pepper: str) -> bool:
    """Verify an API key without timing-sensitive equality."""

    return hmac.compare_digest(api_key_digest(raw_key, pepper), expected)


def redact(value: Any) -> Any:
    """Recursively redact values under known secret field names."""

    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if str(key).lower() in _SECRET_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact(item) for item in value]
    return value
