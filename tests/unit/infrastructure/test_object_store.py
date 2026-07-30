"""Object key and checksum boundary tests."""

from __future__ import annotations

import pytest
from eval_platform_infrastructure.object_store import validate_object_key


@pytest.mark.parametrize(
    "key",
    [
        "/absolute",
        "../escape",
        "run/../escape",
        "run//artifact",
        r"run\artifact",
        "run/has space",
        "run/\N{NULL}",
    ],
)
def test_object_keys_reject_path_ambiguity(key: str) -> None:
    with pytest.raises(ValueError, match="invalid object key"):
        validate_object_key(key)


@pytest.mark.parametrize(
    "key",
    [
        "datasets/0190/version-1.jsonl",
        "runs/id=result/trajectory.json",
        "reports/report_2026-07-29.html",
    ],
)
def test_object_keys_accept_scoped_portable_names(key: str) -> None:
    assert validate_object_key(key) == key
