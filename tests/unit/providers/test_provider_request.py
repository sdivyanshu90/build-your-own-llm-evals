"""Provider request validation tests."""

from __future__ import annotations

import pytest
from eval_platform_providers import GenerationRequest


def test_generation_request_allows_omitted_sampling_and_reasoning_level() -> None:
    request = GenerationRequest(
        model="reasoning-model",
        prompt="answer",
        temperature=None,
        reasoning_effort="minimal",
    )

    assert request.temperature is None
    assert request.reasoning_effort == "minimal"


def test_generation_request_rejects_unknown_reasoning_level() -> None:
    with pytest.raises(ValueError, match="reasoning_effort"):
        GenerationRequest(
            model="reasoning-model",
            prompt="answer",
            reasoning_effort="maximum",
        )
