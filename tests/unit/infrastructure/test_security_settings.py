"""Secret handling and production setting tests."""

from __future__ import annotations

import pytest
from eval_platform_infrastructure.security import (
    api_key_digest,
    generate_api_key,
    redact,
    verify_api_key,
)
from eval_platform_infrastructure.settings import AuthMode, Environment, Settings
from pydantic import ValidationError


def test_api_key_raw_value_is_not_the_stored_digest() -> None:
    raw, prefix = generate_api_key()
    digest = api_key_digest(raw, "pepper")
    assert raw.startswith("evp_")
    assert prefix == raw[:16]
    assert raw.encode() not in digest
    assert verify_api_key(raw, digest, "pepper")
    assert not verify_api_key(raw + "x", digest, "pepper")


def test_redaction_is_recursive_and_does_not_mutate_source() -> None:
    source = {
        "Authorization": "Bearer secret",
        "nested": [{"api_key": "abc", "safe": "yes"}],
    }
    assert redact(source) == {
        "Authorization": "[REDACTED]",
        "nested": [{"api_key": "[REDACTED]", "safe": "yes"}],
    }
    assert source["Authorization"] == "Bearer secret"


def test_production_rejects_development_authentication() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION,
        auth_mode=AuthMode.DEVELOPMENT,
    )
    try:
        settings.validate_secure_runtime()
    except ValueError as error:
        assert "forbidden" in str(error)
    else:
        raise AssertionError("unsafe production settings were accepted")


@pytest.mark.parametrize("interval", [0.5, 61])
def test_outbox_relay_interval_is_bounded(interval: float) -> None:
    with pytest.raises(ValidationError):
        Settings(outbox_relay_interval_seconds=interval)
