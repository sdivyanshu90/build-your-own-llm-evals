"""Deterministic multiple-comparison p-value adjustments."""

from __future__ import annotations

from collections.abc import Mapping


def adjust_p_values(
    p_values: Mapping[str, float],
    *,
    method: str,
) -> dict[str, float]:
    """Adjust a named family using Holm, Benjamini-Hochberg, or Bonferroni."""

    if not p_values:
        raise ValueError("at least one p-value is required")
    if any(not 0 <= value <= 1 for value in p_values.values()):
        raise ValueError("p-values must be between zero and one")
    count = len(p_values)
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    if method == "bonferroni":
        return {key: min(1.0, value * count) for key, value in p_values.items()}
    if method == "holm":
        adjusted: dict[str, float] = {}
        running = 0.0
        for index, (key, value) in enumerate(ordered):
            running = max(running, min(1.0, value * (count - index)))
            adjusted[key] = running
        return adjusted
    if method in {"benjamini-hochberg", "bh"}:
        adjusted = {}
        running = 1.0
        for rank, (key, value) in reversed(list(enumerate(ordered, start=1))):
            running = min(running, value * count / rank)
            adjusted[key] = min(1.0, running)
        return adjusted
    raise ValueError("method must be holm, benjamini-hochberg, or bonferroni")
