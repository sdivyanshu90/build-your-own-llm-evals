"""Statistically rigorous uncertainty, paired comparison, ranking, and planning.

Public symbols are loaded on first access so API processes that only validate
schemas do not pay SciPy's import cost. Static type checkers still see every
concrete export through the guarded imports.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from eval_platform_statistics.effects import (
        paired_binary_effects,
        paired_continuous_effects,
        tie_adjusted_win_rate,
    )
    from eval_platform_statistics.hypothesis import (
        mcnemar_test,
        paired_bootstrap_test,
        paired_t_test,
        paired_tost,
        pairwise_binomial_test,
        permutation_test,
        sign_test,
        wilcoxon_signed_rank_test,
    )
    from eval_platform_statistics.intervals import (
        bootstrap_interval,
        cluster_bootstrap_interval,
        mean_t_interval,
        paired_bootstrap_interval,
        proportion_interval,
        quantile_bootstrap_interval,
        stratified_bootstrap_interval,
    )
    from eval_platform_statistics.models import (
        AnalysisWarning,
        ConfidenceInterval,
        HypothesisTest,
        PairedSample,
        WarningCode,
        align_pairs,
    )
    from eval_platform_statistics.multiplicity import adjust_p_values
    from eval_platform_statistics.ranking import (
        PairOutcome,
        bradley_terry,
        davidson,
        descriptive_elo,
    )

_EXPORTS = {
    "AnalysisWarning": "models",
    "ConfidenceInterval": "models",
    "HypothesisTest": "models",
    "PairOutcome": "ranking",
    "PairedSample": "models",
    "WarningCode": "models",
    "adjust_p_values": "multiplicity",
    "align_pairs": "models",
    "bootstrap_interval": "intervals",
    "bradley_terry": "ranking",
    "cluster_bootstrap_interval": "intervals",
    "davidson": "ranking",
    "descriptive_elo": "ranking",
    "mcnemar_test": "hypothesis",
    "mean_t_interval": "intervals",
    "paired_binary_effects": "effects",
    "paired_bootstrap_interval": "intervals",
    "paired_bootstrap_test": "hypothesis",
    "paired_continuous_effects": "effects",
    "paired_t_test": "hypothesis",
    "paired_tost": "hypothesis",
    "pairwise_binomial_test": "hypothesis",
    "permutation_test": "hypothesis",
    "proportion_interval": "intervals",
    "quantile_bootstrap_interval": "intervals",
    "sign_test": "hypothesis",
    "stratified_bootstrap_interval": "intervals",
    "tie_adjusted_win_rate": "effects",
    "wilcoxon_signed_rank_test": "hypothesis",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    """Load one public implementation module on demand."""

    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(f"eval_platform_statistics.{module_name}"), name)
    globals()[name] = value
    return value
