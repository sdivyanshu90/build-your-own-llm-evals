"""Dataset registry application service."""

from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from eval_platform_domain.auth import Action, Principal, authorize
from eval_platform_domain.canonicalization import (
    CANONICALIZATION_VERSION,
    build_record,
    version_hash,
)
from eval_platform_domain.dataset_operations import diff_versions
from eval_platform_domain.datasets import (
    Dataset,
    DatasetDiff,
    DatasetRecord,
    DatasetVersion,
    SourceProvenance,
)
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.ids import new_uuid7

_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Publication validation counts."""

    record_count: int
    duplicate_payload_count: int
    split_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class VersionPublication:
    """Published version and its immutable validation summary."""

    version: DatasetVersion
    validation: ValidationSummary


class DatasetRepository(Protocol):
    """Persistence contract for dataset use cases."""

    async def add_dataset(self, dataset: Dataset) -> None:
        """Persist a new dataset identity."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def get_dataset(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> Dataset | None:
        """Return one tenant-scoped dataset."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def list_datasets(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        limit: int,
        after: uuid.UUID | None,
    ) -> list[Dataset]:
        """Return a keyset page of datasets."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def next_version_number(self, dataset_id: uuid.UUID) -> int:
        """Lock the dataset and return the next version number."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def add_version(
        self,
        publication: VersionPublication,
    ) -> None:
        """Persist a complete published version atomically."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def get_version(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> DatasetVersion | None:
        """Load one immutable version and its ordered records."""

        raise TypeError("protocol declaration has no runtime implementation")


class DatasetService:
    """Validate, canonicalize, hash, and publish datasets."""

    def __init__(self, repository: DatasetRepository) -> None:
        self._repository = repository

    async def create_dataset(
        self,
        principal: Principal,
        *,
        project_id: uuid.UUID,
        slug: str,
        name: str,
        description: str = "",
        tags: Sequence[str] = (),
    ) -> Dataset:
        """Create a dataset catalog identity."""

        authorize(
            principal,
            Action.DATASET_WRITE,
            organization_id=principal.organization_id,
            project_id=project_id,
        )
        normalized_slug = slug.strip().lower()
        if not _SLUG.fullmatch(normalized_slug):
            raise DomainError(ErrorCode.VALIDATION, "invalid dataset slug")
        clean_name = name.strip()
        if not clean_name:
            raise DomainError(ErrorCode.VALIDATION, "dataset name is required")
        normalized_tags = tuple(sorted({tag.strip().lower() for tag in tags if tag.strip()}))
        dataset = Dataset(
            id=new_uuid7(),
            organization_id=principal.organization_id,
            project_id=project_id,
            slug=normalized_slug,
            name=clean_name,
            description=description.strip(),
            tags=normalized_tags,
        )
        await self._repository.add_dataset(dataset)
        return dataset

    async def publish_version(
        self,
        principal: Principal,
        *,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
        schema_name: str,
        schema_version: str,
        schema: Mapping[str, Any],
        source_records: Sequence[Mapping[str, Any]],
        metadata: Mapping[str, Any] | None = None,
        parent_version_ids: Sequence[uuid.UUID] = (),
        source_kind: str = "api",
    ) -> VersionPublication:
        """Publish an immutable version or fail without partial persistence."""

        authorize(
            principal,
            Action.DATASET_WRITE,
            organization_id=principal.organization_id,
            project_id=project_id,
        )
        dataset = await self._repository.get_dataset(
            principal.organization_id,
            project_id,
            dataset_id,
        )
        if dataset is None:
            raise DomainError(ErrorCode.NOT_FOUND, "dataset was not found")
        if not source_records:
            raise DomainError(ErrorCode.VALIDATION, "dataset version must contain records")

        records: list[DatasetRecord] = []
        seen_keys: set[str] = set()
        for row, source_record in enumerate(source_records, start=1):
            key = str(source_record.get("key", "")).strip()
            if key in seen_keys:
                raise DomainError(
                    ErrorCode.VALIDATION,
                    "dataset version contains a duplicate record key",
                    details={"key": key, "row": row},
                )
            payload = source_record.get("payload")
            if not isinstance(payload, dict):
                raise DomainError(
                    ErrorCode.VALIDATION,
                    "record payload must be an object",
                    details={"row": row},
                )
            raw_metadata = source_record.get("metadata", {})
            raw_splits = source_record.get("splits", [])
            if not isinstance(raw_metadata, dict) or not isinstance(raw_splits, Sequence):
                raise DomainError(
                    ErrorCode.VALIDATION,
                    "record metadata or splits has the wrong type",
                    details={"row": row},
                )
            record = build_record(
                key=key,
                payload=payload,
                metadata=raw_metadata,
                splits=[str(split) for split in raw_splits],
                source=SourceProvenance(kind=source_kind, row=row),
                schema=schema,
            )
            seen_keys.add(record.key)
            records.append(record)

        normalized_metadata = dict(metadata or {})
        digest = version_hash(
            schema=schema,
            metadata=normalized_metadata,
            records=records,
        )
        number = await self._repository.next_version_number(dataset_id)
        version = DatasetVersion(
            id=new_uuid7(),
            dataset_id=dataset_id,
            organization_id=principal.organization_id,
            project_id=project_id,
            version_number=number,
            schema_name=schema_name,
            schema_version=schema_version,
            schema=dict(schema),
            metadata=normalized_metadata,
            canonicalization_version=CANONICALIZATION_VERSION,
            content_hash=digest,
            records=tuple(sorted(records, key=lambda item: item.key)),
            parent_version_ids=tuple(parent_version_ids),
        )
        payload_counts = Counter(record.payload_hash for record in records)
        split_counts = Counter(split for record in records for split in record.splits)
        validation = ValidationSummary(
            record_count=len(records),
            duplicate_payload_count=sum(count - 1 for count in payload_counts.values()),
            split_counts=dict(sorted(split_counts.items())),
        )
        publication = VersionPublication(version=version, validation=validation)
        await self._repository.add_version(publication)
        return publication

    async def diff(
        self,
        principal: Principal,
        *,
        project_id: uuid.UUID,
        source_version_id: uuid.UUID,
        target_version_id: uuid.UUID,
    ) -> DatasetDiff:
        """Compare two visible dataset versions."""

        authorize(
            principal,
            Action.DATASET_READ,
            organization_id=principal.organization_id,
            project_id=project_id,
        )
        source = await self._repository.get_version(
            principal.organization_id,
            project_id,
            source_version_id,
        )
        target = await self._repository.get_version(
            principal.organization_id,
            project_id,
            target_version_id,
        )
        if source is None or target is None:
            raise DomainError(ErrorCode.NOT_FOUND, "dataset version was not found")
        return diff_versions(source, target)
