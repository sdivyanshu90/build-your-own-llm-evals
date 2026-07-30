"""Pure dataset diff, deterministic sampling, redaction, and contamination operations."""

from __future__ import annotations

import hashlib
import hmac
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from eval_platform_domain.datasets import (
    DatasetDiff,
    DatasetRecord,
    DatasetVersion,
    DiffKind,
    FieldChange,
    RecordDiff,
)
from eval_platform_domain.errors import DomainError, ErrorCode


def _field_changes(before: Any, after: Any, pointer: str = "") -> tuple[FieldChange, ...]:
    if before == after:
        return ()
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        changes: list[FieldChange] = []
        for key in sorted(set(before) | set(after)):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            child = f"{pointer}/{escaped}"
            if key not in before:
                changes.append(FieldChange(child, None, after[key]))
            elif key not in after:
                changes.append(FieldChange(child, before[key], None))
            else:
                changes.extend(_field_changes(before[key], after[key], child))
        return tuple(changes)
    return (FieldChange(pointer or "/", before, after),)


def diff_versions(source: DatasetVersion, target: DatasetVersion) -> DatasetDiff:
    """Compare versions by stable logical record key."""

    source_by_key = {record.key: record for record in source.records}
    target_by_key = {record.key: record for record in target.records}
    diffs: list[RecordDiff] = []
    for key in sorted(set(source_by_key) | set(target_by_key)):
        before = source_by_key.get(key)
        after = target_by_key.get(key)
        if before is None:
            diffs.append(RecordDiff(key, DiffKind.ADDED))
        elif after is None:
            diffs.append(RecordDiff(key, DiffKind.REMOVED))
        elif before.envelope_hash == after.envelope_hash:
            diffs.append(RecordDiff(key, DiffKind.UNCHANGED))
        else:
            before_envelope = {
                "payload": before.payload,
                "metadata": before.metadata,
                "splits": before.splits,
            }
            after_envelope = {
                "payload": after.payload,
                "metadata": after.metadata,
                "splits": after.splits,
            }
            diffs.append(
                RecordDiff(
                    key,
                    DiffKind.MODIFIED,
                    _field_changes(before_envelope, after_envelope),
                )
            )
    return DatasetDiff(source.id, target.id, tuple(diffs))


def _sample_score(seed: int, key: str) -> bytes:
    if not 0 <= seed < (1 << 64):
        raise DomainError(ErrorCode.VALIDATION, "seed must be an unsigned 64-bit integer")
    return hmac.new(seed.to_bytes(8, "big"), key.encode(), hashlib.sha256).digest()


def deterministic_sample(
    records: Sequence[DatasetRecord],
    size: int,
    *,
    seed: int,
) -> tuple[DatasetRecord, ...]:
    """Select a deterministic, import-order-independent sample."""

    if not 0 <= size <= len(records):
        raise DomainError(
            ErrorCode.VALIDATION,
            "sample size must be between zero and the population size",
        )
    ranked = sorted(records, key=lambda record: (_sample_score(seed, record.key), record.key))
    return tuple(ranked[:size])


def stratified_sample(
    records: Sequence[DatasetRecord],
    size: int,
    *,
    seed: int,
    metadata_field: str,
) -> tuple[DatasetRecord, ...]:
    """Allocate a deterministic proportional sample using largest remainders."""

    if not 0 <= size <= len(records):
        raise DomainError(ErrorCode.VALIDATION, "invalid stratified sample size")
    strata: dict[str, list[DatasetRecord]] = defaultdict(list)
    for record in records:
        value = record.metadata.get(metadata_field)
        strata[str(value)].append(record)
    if not strata and size:
        raise DomainError(ErrorCode.VALIDATION, "stratification field has no values")
    population = len(records)
    quotas: dict[str, int] = {}
    remainders: list[tuple[float, str]] = []
    allocated = 0
    for label in sorted(strata):
        exact = size * len(strata[label]) / population if population else 0.0
        base = math.floor(exact)
        quotas[label] = base
        allocated += base
        remainders.append((exact - base, label))
    for _, label in sorted(remainders, key=lambda item: (-item[0], item[1]))[: size - allocated]:
        quotas[label] += 1
    selected: list[DatasetRecord] = []
    for label in sorted(strata):
        stratum_seed = int.from_bytes(
            hashlib.sha256(seed.to_bytes(8, "big") + label.encode()).digest()[:8],
            "big",
        )
        selected.extend(deterministic_sample(strata[label], quotas[label], seed=stratum_seed))
    return tuple(sorted(selected, key=lambda record: record.key))


def redact_json(value: Any, sensitive_pointers: Iterable[str]) -> Any:
    """Return a copy with exact JSON-pointer locations replaced."""

    pointers = {pointer for pointer in sensitive_pointers}

    def visit(item: Any, pointer: str) -> Any:
        if pointer in pointers:
            return "[REDACTED]"
        if isinstance(item, Mapping):
            return {
                key: visit(
                    child,
                    f"{pointer}/{str(key).replace('~', '~0').replace('/', '~1')}",
                )
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [visit(child, f"{pointer}/{index}") for index, child in enumerate(item)]
        return item

    return visit(value, "")


_TOKEN = re.compile(r"\w+", re.UNICODE)


def ngrams(text: str, n: int = 5) -> frozenset[tuple[str, ...]]:
    """Return lowercase word n-grams for contamination diagnostics."""

    if n < 1:
        raise ValueError("n must be positive")
    tokens = _TOKEN.findall(text.casefold())
    return frozenset(tuple(tokens[index : index + n]) for index in range(len(tokens) - n + 1))


def ngram_jaccard(left: str, right: str, n: int = 5) -> float:
    """Compute n-gram Jaccard similarity with explicit empty behavior."""

    left_set = ngrams(left, n)
    right_set = ngrams(right, n)
    union = left_set | right_set
    return len(left_set & right_set) / len(union) if union else 1.0


@dataclass(frozen=True, slots=True)
class ContaminationMatch:
    """Heuristic near-duplicate evidence."""

    left_key: str
    right_key: str
    similarity: float


def contamination_matches(
    left: Sequence[tuple[str, str]],
    right: Sequence[tuple[str, str]],
    *,
    n: int = 5,
    threshold: float = 0.8,
) -> tuple[ContaminationMatch, ...]:
    """Find cross-set n-gram matches.

    This exact implementation is the correctness reference. Large imports use
    MinHash candidates and confirm candidates with this function.
    """

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    matches: list[ContaminationMatch] = []
    for left_key, left_text in left:
        for right_key, right_text in right:
            similarity = ngram_jaccard(left_text, right_text, n)
            if similarity >= threshold:
                matches.append(ContaminationMatch(left_key, right_key, similarity))
    return tuple(
        sorted(matches, key=lambda item: (-item.similarity, item.left_key, item.right_key))
    )


def minhash_signature(
    text: str,
    *,
    n: int = 5,
    permutations: int = 128,
    seed: int = 0,
) -> tuple[int, ...]:
    """Create a deterministic MinHash signature for LSH candidate generation."""

    if permutations < 1:
        raise ValueError("permutations must be positive")
    grams = ngrams(text, n)
    if not grams:
        return tuple((1 << 64) - 1 for _ in range(permutations))
    signature: list[int] = []
    for permutation in range(permutations):
        salt = hashlib.sha256(seed.to_bytes(8, "big") + permutation.to_bytes(4, "big")).digest()
        signature.append(
            min(
                int.from_bytes(
                    hashlib.blake2b(
                        "\x1f".join(gram).encode(),
                        key=salt,
                        digest_size=8,
                    ).digest(),
                    "big",
                )
                for gram in grams
            )
        )
    return tuple(signature)


def lsh_buckets(
    signatures: Mapping[str, tuple[int, ...]],
    *,
    bands: int = 16,
) -> dict[tuple[int, str], tuple[str, ...]]:
    """Bucket compatible MinHash signatures into deterministic LSH bands."""

    if bands < 1:
        raise ValueError("bands must be positive")
    lengths = {len(signature) for signature in signatures.values()}
    if len(lengths) > 1:
        raise ValueError("all signatures must have the same length")
    length = next(iter(lengths), 0)
    if length == 0 or length % bands:
        raise ValueError("signature length must be a positive multiple of bands")
    rows = length // bands
    mutable: dict[tuple[int, str], list[str]] = defaultdict(list)
    for key, signature in signatures.items():
        for band in range(bands):
            chunk = signature[band * rows : (band + 1) * rows]
            digest = hashlib.sha256(
                b"".join(value.to_bytes(8, "big") for value in chunk)
            ).hexdigest()
            mutable[(band, digest)].append(key)
    return {bucket: tuple(sorted(keys)) for bucket, keys in mutable.items() if len(keys) > 1}
