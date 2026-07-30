"""Immutable dataset domain values and diff classifications."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DatasetVersionState(StrEnum):
    """Dataset version lifecycle."""

    DRAFT = "draft"
    VALIDATING = "validating"
    PUBLISHED = "published"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class Dataset:
    """Mutable catalog identity for immutable versions."""

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    slug: str
    name: str
    description: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceProvenance:
    """Origin of one normalized record."""

    kind: str
    uri: str | None = None
    row: int | None = None
    source_hash: str | None = None


@dataclass(frozen=True, slots=True)
class DatasetRecord:
    """Canonical record within a dataset version."""

    key: str
    payload: dict[str, Any]
    metadata: dict[str, Any]
    splits: tuple[str, ...]
    source: SourceProvenance
    payload_hash: str
    envelope_hash: str


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    """Published immutable dataset version."""

    id: uuid.UUID
    dataset_id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    version_number: int
    schema_name: str
    schema_version: str
    schema: dict[str, Any]
    metadata: dict[str, Any]
    canonicalization_version: str
    content_hash: str
    records: tuple[DatasetRecord, ...]
    state: DatasetVersionState = DatasetVersionState.PUBLISHED
    parent_version_ids: tuple[uuid.UUID, ...] = ()


class DiffKind(StrEnum):
    """Dataset record diff classification."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class FieldChange:
    """One changed JSON pointer."""

    pointer: str
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class RecordDiff:
    """Diff result for one logical record key."""

    key: str
    kind: DiffKind
    changes: tuple[FieldChange, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DatasetDiff:
    """Complete partition of record keys across two versions."""

    source_version_id: uuid.UUID
    target_version_id: uuid.UUID
    records: tuple[RecordDiff, ...]

    def counts(self) -> dict[DiffKind, int]:
        """Return counts for all classifications, including zeros."""

        return {kind: sum(record.kind is kind for record in self.records) for kind in DiffKind}
