"""Golden and property tests for schema-aware canonicalization."""

from __future__ import annotations

import unicodedata

import pytest
from eval_platform_domain.canonicalization import (
    build_record,
    canonical_bytes,
    content_hash,
    normalize_json,
    version_hash,
)
from eval_platform_domain.datasets import SourceProvenance
from eval_platform_domain.errors import DomainError
from hypothesis import given
from hypothesis import strategies as st

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "text": {"type": "string"},
        "when": {"type": "string", "format": "date-time"},
        "optional": {"type": ["string", "null"]},
        "score": {"type": "number"},
    },
    "required": ["text", "when", "score"],
}


def test_semantically_equivalent_records_have_golden_hash() -> None:
    left = {
        "text": "Cafe\u0301\r\nline",
        "when": "2024-01-01T05:30:00+05:30",
        "score": -0.0,
    }
    right = {
        "score": 0,
        "optional": None,
        "when": "2024-01-01T00:00:00Z",
        "text": "Café\nline",
    }
    assert canonical_bytes(left, SCHEMA) == canonical_bytes(right, SCHEMA)
    assert content_hash(left, SCHEMA) == content_hash(right, SCHEMA)
    assert content_hash(left, SCHEMA) == (
        "41e8ffe1d572578fd3eab5c8d773760c09978bfffd1a74e6b1038b87e0c73775"
    )


def test_unicode_normalized_key_collision_is_rejected() -> None:
    with pytest.raises(DomainError, match="duplicate object key"):
        canonical_bytes({"é": 1, "e\u0301": 2})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_numbers_are_rejected(value: float) -> None:
    with pytest.raises(DomainError, match="finite"):
        canonical_bytes({"value": value})


def test_offset_free_timestamp_is_rejected() -> None:
    value = {"text": "x", "when": "2024-01-01T00:00:00", "score": 1}
    with pytest.raises(DomainError, match="explicit offset"):
        canonical_bytes(value, SCHEMA)


@given(
    st.recursive(
        st.none()
        | st.booleans()
        | st.integers(min_value=-(2**53) + 1, max_value=(2**53) - 1)
        | st.text(),
        lambda children: (
            st.lists(children, max_size=5)
            | st.dictionaries(st.text(min_size=1), children, max_size=5)
        ),
        max_leaves=20,
    )
)
def test_normalization_is_idempotent(value: object) -> None:
    first = normalize_json(value)
    assert normalize_json(first) == first


def test_version_hash_is_independent_of_import_order() -> None:
    schema = {
        "type": "object",
        "properties": {"input": {"type": "string"}},
        "required": ["input"],
        "additionalProperties": False,
    }
    records = [
        build_record(
            key=key,
            payload={"input": key},
            metadata={},
            splits=["test"],
            source=SourceProvenance("api", row=index),
            schema=schema,
        )
        for index, key in enumerate(("b", "a"), start=1)
    ]
    assert version_hash(schema=schema, metadata={}, records=records) == version_hash(
        schema=schema,
        metadata={},
        records=list(reversed(records)),
    )


def test_normalization_emits_nfc() -> None:
    value = normalize_json("e\u0301")
    assert value == "é"
    assert unicodedata.is_normalized("NFC", value)
