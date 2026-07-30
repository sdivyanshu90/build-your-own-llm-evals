"""Dataset registry API schemas."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import Field

from eval_platform_schemas.common import StrictModel


class DatasetCreate(StrictModel):
    """Create a dataset catalog."""

    slug: str = Field(min_length=1, max_length=63)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    tags: list[str] = Field(default_factory=list, max_length=100)


class DatasetRead(StrictModel):
    """Dataset catalog response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    slug: str
    name: str
    description: str
    tags: list[str]


class RecordInput(StrictModel):
    """One API-import record envelope."""

    key: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)
    splits: list[str] = Field(default_factory=list, max_length=100)


class DatasetVersionCreate(StrictModel):
    """Create and publish one immutable version."""

    schema_name: str = Field(min_length=1, max_length=100)
    schema_version: str = Field(min_length=1, max_length=32)
    schema_definition: dict[str, Any] = Field(alias="schema")
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_version_ids: list[uuid.UUID] = Field(default_factory=list)
    records: list[RecordInput] = Field(min_length=1)


class ValidationSummaryRead(StrictModel):
    """Version validation summary."""

    record_count: int
    duplicate_payload_count: int
    split_counts: dict[str, int]


class DatasetVersionRead(StrictModel):
    """Published dataset manifest response."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    state: str
    schema_name: str
    schema_version: str
    schema_definition: dict[str, Any] = Field(serialization_alias="schema")
    metadata: dict[str, Any]
    canonicalization_version: str
    content_hash: str
    parent_version_ids: list[uuid.UUID]
    validation: ValidationSummaryRead


class DatasetVersionSummaryRead(StrictModel):
    """Dataset version manifest summary for registry navigation."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    version_number: int
    state: str
    schema_name: str
    schema_version: str
    canonicalization_version: str
    content_hash: str
    record_count: int
    duplicate_payload_count: int
    split_counts: dict[str, int]
    parent_version_ids: list[uuid.UUID]


class DatasetRecordRead(StrictModel):
    """Canonical dataset record response."""

    key: str
    payload: dict[str, Any]
    metadata: dict[str, Any]
    splits: list[str]
    payload_hash: str
    envelope_hash: str


class FieldChangeRead(StrictModel):
    """One field-level diff."""

    pointer: str
    before: Any
    after: Any


class RecordDiffRead(StrictModel):
    """Diff classification for one logical key."""

    key: str
    kind: str
    changes: list[FieldChangeRead]


class DatasetDiffRead(StrictModel):
    """Complete dataset diff response."""

    source_version_id: uuid.UUID
    target_version_id: uuid.UUID
    counts: dict[str, int]
    records: list[RecordDiffRead]
