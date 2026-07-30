"""Retrieval denominator and agent trajectory metric tests."""

from __future__ import annotations

import pytest
from eval_platform_metrics.agent import (
    grounded_in_tool_outputs,
    loop_detection,
    recovery_after_tool_failure,
    redundant_tool_call_rate,
    tool_argument_validity,
    tool_call_success_rate,
)
from eval_platform_metrics.rag import (
    average_precision,
    citation_metrics,
    duplicate_document_rate,
    hit_rate_at_k,
    ndcg,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


def test_retrieval_metrics_hand_example() -> None:
    retrieved = ["d2", "d1", "d4", "d1"]
    relevant = {"d1", "d3"}
    assert precision_at_k(retrieved, relevant, 3) == pytest.approx(1 / 3)
    assert recall_at_k(retrieved, relevant, 3) == 0.5
    assert hit_rate_at_k(retrieved, relevant, 1) == 0
    assert reciprocal_rank(retrieved, relevant) == 0.5
    assert average_precision(retrieved, relevant) == 0.25
    assert duplicate_document_rate(retrieved) == 0.25


def test_retrieval_no_relevance_labels_are_missing() -> None:
    assert recall_at_k(["d1"], set(), 1) is None
    assert hit_rate_at_k(["d1"], set(), 1) is None
    assert reciprocal_rank(["d1"], set()) is None
    assert ndcg(["d1"], {"d1": 0}, 1) is None


def test_ndcg_is_one_for_ideal_ranking() -> None:
    assert ndcg(["high", "medium"], {"high": 3, "medium": 1}, 2) == 1


def test_citations_distinguish_presence_validity_and_missing_claim_labels() -> None:
    result = citation_metrics(
        "Answer [source:a] and [source:missing].",
        {"a", "b"},
    )
    assert result == {
        "presence": 1.0,
        "validity": 0.5,
        "correctness": None,
        "completeness": None,
    }


def test_agent_tool_validity_success_redundancy_loop_and_recovery() -> None:
    trajectory = [
        {"kind": "tool_call", "tool": "search", "arguments": {"query": "x"}},
        {"kind": "tool_result", "success": False, "output": "offline"},
        {"kind": "tool_call", "tool": "search", "arguments": {"query": "x"}},
        {"kind": "tool_result", "success": True, "output": "answer is 42"},
        {"kind": "model_decision", "decision": "inspect"},
        {"kind": "model_decision", "decision": "inspect"},
        {"kind": "model_decision", "decision": "inspect"},
    ]
    schemas = {
        "search": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        }
    }
    assert tool_argument_validity(trajectory, schemas)["rate"] == 1
    assert tool_call_success_rate(trajectory) == 0.5
    assert redundant_tool_call_rate(trajectory) == 0.5
    assert loop_detection(trajectory)["detected"] is True
    assert recovery_after_tool_failure(trajectory) == 1
    grounded = grounded_in_tool_outputs("answer is 42", trajectory)
    assert grounded["groundedness"] == 1
