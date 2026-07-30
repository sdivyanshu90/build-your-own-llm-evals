"""PostgreSQL implementation of the dataset repository."""

from __future__ import annotations

import uuid

from eval_platform_application.datasets import (
    DatasetRepository,
    VersionPublication,
)
from eval_platform_domain.datasets import (
    Dataset,
    DatasetRecord,
    DatasetVersion,
    DatasetVersionState,
    SourceProvenance,
)
from eval_platform_domain.errors import DomainError, ErrorCode
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eval_platform_infrastructure.dataset_models import (
    DatasetModel,
    DatasetRecordModel,
    DatasetVersionModel,
)


class SqlDatasetRepository(DatasetRepository):
    """Tenant-scoped dataset persistence with atomic publication."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_dataset(self, dataset: Dataset) -> None:
        existing = await self._session.scalar(
            select(DatasetModel.id).where(
                DatasetModel.organization_id == dataset.organization_id,
                DatasetModel.project_id == dataset.project_id,
                DatasetModel.slug == dataset.slug,
                DatasetModel.deleted_at.is_(None),
            )
        )
        if existing is not None:
            raise DomainError(ErrorCode.CONFLICT, "dataset slug already exists")
        self._session.add(
            DatasetModel(
                id=dataset.id,
                organization_id=dataset.organization_id,
                project_id=dataset.project_id,
                slug=dataset.slug,
                name=dataset.name,
                description=dataset.description,
                tags=list(dataset.tags),
            )
        )

    async def get_dataset(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> Dataset | None:
        model = await self._session.scalar(
            select(DatasetModel).where(
                DatasetModel.organization_id == organization_id,
                DatasetModel.project_id == project_id,
                DatasetModel.id == dataset_id,
                DatasetModel.deleted_at.is_(None),
            )
        )
        return None if model is None else _dataset(model)

    async def list_datasets(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        limit: int,
        after: uuid.UUID | None,
    ) -> list[Dataset]:
        statement = (
            select(DatasetModel)
            .where(
                DatasetModel.organization_id == organization_id,
                DatasetModel.project_id == project_id,
                DatasetModel.deleted_at.is_(None),
            )
            .order_by(DatasetModel.id)
            .limit(limit)
        )
        if after is not None:
            statement = statement.where(DatasetModel.id > after)
        return [_dataset(model) for model in (await self._session.scalars(statement)).all()]

    async def next_version_number(self, dataset_id: uuid.UUID) -> int:
        await self._session.execute(
            select(DatasetModel.id).where(DatasetModel.id == dataset_id).with_for_update()
        )
        current = await self._session.scalar(
            select(func.max(DatasetVersionModel.version_number)).where(
                DatasetVersionModel.dataset_id == dataset_id
            )
        )
        return int(current or 0) + 1

    async def add_version(self, publication: VersionPublication) -> None:
        version = publication.version
        model = DatasetVersionModel(
            id=version.id,
            organization_id=version.organization_id,
            project_id=version.project_id,
            dataset_id=version.dataset_id,
            version_number=version.version_number,
            state=version.state,
            schema_name=version.schema_name,
            schema_version=version.schema_version,
            schema_json=version.schema,
            metadata_json=version.metadata,
            canonicalization_version=version.canonicalization_version,
            content_hash=version.content_hash,
            record_count=publication.validation.record_count,
            duplicate_payload_count=publication.validation.duplicate_payload_count,
            split_counts=publication.validation.split_counts,
            parent_version_ids=list(version.parent_version_ids),
        )
        self._session.add(model)
        await self._session.flush((model,))
        self._session.add_all(
            [
                DatasetRecordModel(
                    organization_id=version.organization_id,
                    project_id=version.project_id,
                    dataset_version_id=version.id,
                    record_key=record.key,
                    payload=record.payload,
                    metadata_json=record.metadata,
                    splits=list(record.splits),
                    source={
                        "kind": record.source.kind,
                        "uri": record.source.uri,
                        "row": record.source.row,
                        "source_hash": record.source.source_hash,
                    },
                    payload_hash=record.payload_hash,
                    envelope_hash=record.envelope_hash,
                )
                for record in version.records
            ]
        )

    async def get_version(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> DatasetVersion | None:
        model = await self._session.scalar(
            select(DatasetVersionModel).where(
                DatasetVersionModel.organization_id == organization_id,
                DatasetVersionModel.project_id == project_id,
                DatasetVersionModel.id == version_id,
            )
        )
        if model is None:
            return None
        record_models = (
            await self._session.scalars(
                select(DatasetRecordModel)
                .where(
                    DatasetRecordModel.organization_id == organization_id,
                    DatasetRecordModel.project_id == project_id,
                    DatasetRecordModel.dataset_version_id == version_id,
                )
                .order_by(DatasetRecordModel.record_key)
            )
        ).all()
        records = tuple(
            DatasetRecord(
                key=record.record_key,
                payload=record.payload,
                metadata=record.metadata_json,
                splits=tuple(record.splits),
                source=SourceProvenance(**record.source),
                payload_hash=record.payload_hash,
                envelope_hash=record.envelope_hash,
            )
            for record in record_models
        )
        return DatasetVersion(
            id=model.id,
            dataset_id=model.dataset_id,
            organization_id=model.organization_id,
            project_id=model.project_id,
            version_number=model.version_number,
            schema_name=model.schema_name,
            schema_version=model.schema_version,
            schema=model.schema_json,
            metadata=model.metadata_json,
            canonicalization_version=model.canonicalization_version,
            content_hash=model.content_hash,
            records=records,
            state=DatasetVersionState(model.state),
            parent_version_ids=tuple(model.parent_version_ids),
        )


def _dataset(model: DatasetModel) -> Dataset:
    return Dataset(
        id=model.id,
        organization_id=model.organization_id,
        project_id=model.project_id,
        slug=model.slug,
        name=model.name,
        description=model.description,
        tags=tuple(model.tags),
    )
