"""Built-in versioned JSON Schemas for common evaluation tasks."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_TEXT = {"type": "string", "minLength": 1}
_BASE = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
}

BUILTIN_SCHEMAS: dict[str, dict[str, Any]] = {
    "generation/v1": {
        **_BASE,
        "properties": {
            "input": _TEXT,
            "reference": {"type": ["string", "null"]},
        },
        "required": ["input"],
    },
    "qa/v1": {
        **_BASE,
        "properties": {
            "question": _TEXT,
            "context": {"type": ["string", "null"]},
            "answers": {"type": "array", "items": _TEXT, "minItems": 1},
        },
        "required": ["question", "answers"],
    },
    "classification/v1": {
        **_BASE,
        "properties": {
            "input": _TEXT,
            "label": _TEXT,
            "labels": {"type": ["array", "null"], "items": _TEXT, "uniqueItems": True},
        },
        "required": ["input", "label"],
    },
    "summarization/v1": {
        **_BASE,
        "properties": {"document": _TEXT, "reference_summary": _TEXT},
        "required": ["document", "reference_summary"],
    },
    "extraction/v1": {
        **_BASE,
        "properties": {
            "input": _TEXT,
            "expected": {"type": "object"},
        },
        "required": ["input", "expected"],
    },
    "rag/v1": {
        **_BASE,
        "properties": {
            "question": _TEXT,
            "reference_answer": {"type": ["string", "null"]},
            "relevant_document_ids": {
                "type": "array",
                "items": _TEXT,
                "uniqueItems": True,
            },
        },
        "required": ["question", "relevant_document_ids"],
    },
    "preference/v1": {
        **_BASE,
        "properties": {
            "input": _TEXT,
            "output_a": _TEXT,
            "output_b": _TEXT,
            "preference": {"enum": ["a", "b", "tie", "abstain"]},
        },
        "required": ["input", "output_a", "output_b", "preference"],
    },
    "agent/v1": {
        **_BASE,
        "properties": {
            "task": _TEXT,
            "expected_outcome": {"type": "object"},
            "allowed_tools": {"type": "array", "items": _TEXT, "uniqueItems": True},
        },
        "required": ["task", "expected_outcome", "allowed_tools"],
    },
    "conversation/v1": {
        **_BASE,
        "properties": {
            "messages": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "role": {"enum": ["system", "user", "assistant", "tool"]},
                        "content": {"type": "string"},
                    },
                    "required": ["role", "content"],
                },
            },
            "reference": {"type": ["string", "null"]},
        },
        "required": ["messages"],
    },
}


def get_builtin_schema(identifier: str) -> dict[str, Any]:
    """Return a defensive copy of a built-in schema."""

    try:
        return deepcopy(BUILTIN_SCHEMAS[identifier])
    except KeyError as error:
        raise KeyError(f"unknown built-in dataset schema: {identifier}") from error
