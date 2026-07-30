"""Dataset diff, sampling, contamination, and redaction tests."""

from __future__ import annotations

import uuid

from eval_platform_domain.canonicalization import build_record, version_hash
from eval_platform_domain.dataset_operations import (
    contamination_matches,
    deterministic_sample,
    diff_versions,
    lsh_buckets,
    minhash_signature,
    redact_json,
    stratified_sample,
)
from eval_platform_domain.datasets import DatasetVersion, DiffKind, SourceProvenance
from hypothesis import given, settings
from hypothesis import strategies as st

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"input": {"type": "string"}, "label": {"type": "string"}},
    "required": ["input", "label"],
}


def _record(key: str, text: str, label: str = "a"):
    return build_record(
        key=key,
        payload={"input": text, "label": label},
        metadata={"stratum": label},
        splits=["test"],
        source=SourceProvenance("fixture"),
        schema=SCHEMA,
    )


def _version(records: tuple, number: int = 1) -> DatasetVersion:
    return DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        version_number=number,
        schema_name="fixture",
        schema_version="1",
        schema=SCHEMA,
        metadata={},
        canonicalization_version="dataset-c14n/1",
        content_hash=version_hash(schema=SCHEMA, metadata={}, records=records),
        records=records,
    )


def test_diff_partitions_keys_and_reports_field_pointer() -> None:
    before = _version((_record("keep", "same"), _record("edit", "old"), _record("remove", "x")))
    after = _version((_record("keep", "same"), _record("edit", "new"), _record("add", "y")), 2)
    result = diff_versions(before, after)
    assert result.counts() == {
        DiffKind.ADDED: 1,
        DiffKind.REMOVED: 1,
        DiffKind.MODIFIED: 1,
        DiffKind.UNCHANGED: 1,
    }
    modified = next(item for item in result.records if item.key == "edit")
    assert modified.changes[0].pointer == "/payload/input"


@given(st.integers(min_value=0, max_value=(1 << 64) - 1))
@settings(deadline=None)
def test_sampling_repeats_for_seed(seed: int) -> None:
    records = tuple(_record(str(index), str(index)) for index in range(20))
    assert deterministic_sample(records, 7, seed=seed) == deterministic_sample(
        tuple(reversed(records)),
        7,
        seed=seed,
    )


def test_stratified_sampling_uses_largest_remainder() -> None:
    records = tuple(
        [_record(f"a-{index}", str(index), "a") for index in range(7)]
        + [_record(f"b-{index}", str(index), "b") for index in range(3)]
    )
    sample = stratified_sample(records, 5, seed=9, metadata_field="stratum")
    counts = {
        label: sum(record.metadata["stratum"] == label for record in sample) for label in ("a", "b")
    }
    assert counts == {"a": 4, "b": 1}


def test_redaction_targets_exact_json_pointers() -> None:
    value = {"profile": {"email": "person@example.com", "city": "Pune"}}
    assert redact_json(value, ["/profile/email"]) == {
        "profile": {"email": "[REDACTED]", "city": "Pune"}
    }
    assert value["profile"]["email"] == "person@example.com"


def test_contamination_and_lsh_find_near_duplicate_fixture() -> None:
    sentence = "the quick brown fox jumps over the lazy dog every morning"
    matches = contamination_matches(
        [("train-1", sentence)],
        [("test-1", sentence), ("test-2", "completely unrelated short text")],
        threshold=0.8,
    )
    assert [(match.left_key, match.right_key) for match in matches] == [("train-1", "test-1")]
    signatures = {
        "train-1": minhash_signature(sentence),
        "test-1": minhash_signature(sentence),
    }
    assert any(set(keys) == {"train-1", "test-1"} for keys in lsh_buckets(signatures).values())
