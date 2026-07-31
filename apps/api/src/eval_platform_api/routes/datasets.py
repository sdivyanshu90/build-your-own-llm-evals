"""Versioned dataset REST API."""

from __future__ import annotations

import io
import json
import uuid
from typing import Annotated, Any

from eval_platform_application.dataset_import import ImportFormat, parse_records
from eval_platform_application.datasets import DatasetService, VersionPublication
from eval_platform_domain.auth import Action, authorize
from eval_platform_domain.dataset_operations import deterministic_sample
from eval_platform_domain.datasets import Dataset, DatasetVersion
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_infrastructure.dataset_models import DatasetVersionModel
from eval_platform_infrastructure.dataset_repository import SqlDatasetRepository
from eval_platform_schemas.common import Page, PageMetadata
from eval_platform_schemas.datasets import (
    DatasetCreate,
    DatasetDiffRead,
    DatasetRead,
    DatasetRecordRead,
    DatasetVersionCreate,
    DatasetVersionRead,
    DatasetVersionSummaryRead,
    FieldChangeRead,
    RecordDiffRead,
    ValidationSummaryRead,
)
from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from eval_platform_api.dependencies import (
    PrincipalDependency,
    SessionDependency,
    SettingsDependency,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}/datasets", tags=["datasets"])


def _dataset_read(dataset: Dataset) -> DatasetRead:
    return DatasetRead(
        id=dataset.id,
        organization_id=dataset.organization_id,
        project_id=dataset.project_id,
        slug=dataset.slug,
        name=dataset.name,
        description=dataset.description,
        tags=list(dataset.tags),
    )


def _version_read(publication: VersionPublication) -> DatasetVersionRead:
    version = publication.version
    return DatasetVersionRead(
        id=version.id,
        dataset_id=version.dataset_id,
        organization_id=version.organization_id,
        project_id=version.project_id,
        version_number=version.version_number,
        state=version.state,
        schema_name=version.schema_name,
        schema_version=version.schema_version,
        schema_definition=version.schema,
        metadata=version.metadata,
        canonicalization_version=version.canonicalization_version,
        content_hash=version.content_hash,
        parent_version_ids=list(version.parent_version_ids),
        validation=ValidationSummaryRead(
            record_count=publication.validation.record_count,
            duplicate_payload_count=publication.validation.duplicate_payload_count,
            split_counts=publication.validation.split_counts,
        ),
    )


def _record_read(version: DatasetVersion) -> list[DatasetRecordRead]:
    return [
        DatasetRecordRead(
            key=record.key,
            payload=record.payload,
            metadata=record.metadata,
            splits=list(record.splits),
            payload_hash=record.payload_hash,
            envelope_hash=record.envelope_hash,
        )
        for record in version.records
    ]


@router.post("", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    project_id: uuid.UUID,
    body: DatasetCreate,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> DatasetRead:
    """Create a dataset catalog."""

    service = DatasetService(SqlDatasetRepository(session))
    dataset = await service.create_dataset(
        principal,
        project_id=project_id,
        slug=body.slug,
        name=body.name,
        description=body.description,
        tags=body.tags,
    )
    return _dataset_read(dataset)


@router.get("", response_model=Page[DatasetRead])
async def list_datasets(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    after: uuid.UUID | None = None,
) -> Page[DatasetRead]:
    """List visible datasets."""

    authorize(
        principal,
        Action.DATASET_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    repository = SqlDatasetRepository(session)
    datasets = await repository.list_datasets(
        principal.organization_id,
        project_id,
        limit=limit + 1,
        after=after,
    )
    has_more = len(datasets) > limit
    page = datasets[:limit]
    return Page(
        items=[_dataset_read(dataset) for dataset in page],
        page=PageMetadata(
            next_cursor=str(page[-1].id) if has_more and page else None,
            limit=limit,
        ),
    )


@router.post(
    "/{dataset_id}/versions",
    response_model=DatasetVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def publish_version(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    body: DatasetVersionCreate,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> DatasetVersionRead:
    """Validate and atomically publish an API-supplied dataset version."""

    publication = await DatasetService(SqlDatasetRepository(session)).publish_version(
        principal,
        project_id=project_id,
        dataset_id=dataset_id,
        schema_name=body.schema_name,
        schema_version=body.schema_version,
        schema=body.schema_definition,
        source_records=[record.model_dump(mode="python") for record in body.records],
        metadata=body.metadata,
        parent_version_ids=body.parent_version_ids,
    )
    return _version_read(publication)


@router.post(
    "/{dataset_id}/imports",
    response_model=DatasetVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_version(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    settings: SettingsDependency,
    file: Annotated[UploadFile, File(description="JSON, JSONL, CSV, or Parquet dataset")],
    import_format: Annotated[ImportFormat, Form()],
    schema_name: Annotated[str, Form()],
    schema_version: Annotated[str, Form()],
    schema_definition_json: Annotated[str, Form(alias="schema_json")],
) -> DatasetVersionRead:
    """Import a bounded upload and publish it atomically."""

    body = await file.read(settings.max_upload_bytes + 1)
    if len(body) > settings.max_upload_bytes:
        raise DomainError(
            ErrorCode.VALIDATION,
            "upload exceeds the configured byte limit",
            details={"limit": settings.max_upload_bytes},
        )
    try:
        schema = json.loads(schema_definition_json)
    except json.JSONDecodeError as error:
        raise DomainError(
            ErrorCode.VALIDATION,
            "schema_json is invalid JSON",
            details={"line": error.lineno, "column": error.colno},
        ) from error
    if not isinstance(schema, dict):
        raise DomainError(ErrorCode.VALIDATION, "schema_json must be a JSON object")
    records = list(
        parse_records(
            io.BytesIO(body),
            import_format,
            max_records=settings.max_import_records,
        )
    )
    publication = await DatasetService(SqlDatasetRepository(session)).publish_version(
        principal,
        project_id=project_id,
        dataset_id=dataset_id,
        schema_name=schema_name,
        schema_version=schema_version,
        schema=schema,
        source_records=records,
        source_kind=f"upload:{import_format}",
    )
    return _version_read(publication)


@router.get("/{dataset_id}/versions/{version_id}", response_model=DatasetVersionRead)
async def get_version(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> DatasetVersionRead:
    """Return a published version manifest."""

    authorize(
        principal,
        Action.DATASET_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    version = await SqlDatasetRepository(session).get_version(
        principal.organization_id,
        project_id,
        version_id,
    )
    if version is None or version.dataset_id != dataset_id:
        raise DomainError(ErrorCode.NOT_FOUND, "dataset version was not found")
    validation = ValidationSummaryRead(
        record_count=len(version.records),
        duplicate_payload_count=len(version.records)
        - len({record.payload_hash for record in version.records}),
        split_counts={
            split: sum(split in record.splits for record in version.records)
            for split in sorted({value for record in version.records for value in record.splits})
        },
    )
    return DatasetVersionRead(
        id=version.id,
        dataset_id=version.dataset_id,
        organization_id=version.organization_id,
        project_id=version.project_id,
        version_number=version.version_number,
        state=version.state,
        schema_name=version.schema_name,
        schema_version=version.schema_version,
        schema_definition=version.schema,
        metadata=version.metadata,
        canonicalization_version=version.canonicalization_version,
        content_hash=version.content_hash,
        parent_version_ids=list(version.parent_version_ids),
        validation=validation,
    )


@router.get(
    "/{dataset_id}/versions",
    response_model=Page[DatasetVersionSummaryRead],
)
async def list_versions(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    after: int | None = Query(default=None, ge=0),
) -> Page[DatasetVersionSummaryRead]:
    """List immutable version manifests without loading record payloads."""

    authorize(
        principal,
        Action.DATASET_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    statement = (
        select(DatasetVersionModel)
        .where(
            DatasetVersionModel.organization_id == principal.organization_id,
            DatasetVersionModel.project_id == project_id,
            DatasetVersionModel.dataset_id == dataset_id,
        )
        .order_by(DatasetVersionModel.version_number)
        .limit(limit + 1)
    )
    if after is not None:
        statement = statement.where(DatasetVersionModel.version_number > after)
    values = list((await session.scalars(statement)).all())
    has_more = len(values) > limit
    values = values[:limit]
    return Page(
        items=[
            DatasetVersionSummaryRead(
                id=value.id,
                dataset_id=value.dataset_id,
                version_number=value.version_number,
                state=value.state,
                schema_name=value.schema_name,
                schema_version=value.schema_version,
                canonicalization_version=value.canonicalization_version,
                content_hash=value.content_hash,
                record_count=value.record_count,
                duplicate_payload_count=value.duplicate_payload_count,
                split_counts=value.split_counts,
                parent_version_ids=value.parent_version_ids,
            )
            for value in values
        ],
        page=PageMetadata(
            next_cursor=str(values[-1].version_number) if has_more and values else None,
            limit=limit,
        ),
    )


@router.get(
    "/{dataset_id}/versions/{version_id}/records",
    response_model=Page[DatasetRecordRead],
)
async def list_records(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=100, ge=1, le=200),
    after: str | None = None,
) -> Page[DatasetRecordRead]:
    """List canonical records using record-key pagination."""

    authorize(
        principal,
        Action.DATASET_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    version = await SqlDatasetRepository(session).get_version(
        principal.organization_id, project_id, version_id
    )
    if version is None or version.dataset_id != dataset_id:
        raise DomainError(ErrorCode.NOT_FOUND, "dataset version was not found")
    records = [record for record in version.records if after is None or record.key > after]
    has_more = len(records) > limit
    page_records = records[:limit]
    temporary = DatasetVersion(
        id=version.id,
        dataset_id=version.dataset_id,
        organization_id=version.organization_id,
        project_id=version.project_id,
        version_number=version.version_number,
        schema_name=version.schema_name,
        schema_version=version.schema_version,
        schema=version.schema,
        metadata=version.metadata,
        canonicalization_version=version.canonicalization_version,
        content_hash=version.content_hash,
        records=tuple(page_records),
        state=version.state,
        parent_version_ids=version.parent_version_ids,
    )
    return Page(
        items=_record_read(temporary),
        page=PageMetadata(
            next_cursor=page_records[-1].key if has_more and page_records else None,
            limit=limit,
        ),
    )


@router.get("/{dataset_id}/versions/{version_id}/export")
async def export_version(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> JSONResponse:
    """Export an exact canonical JSON representation and manifest."""

    authorize(
        principal,
        Action.DATASET_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    version = await SqlDatasetRepository(session).get_version(
        principal.organization_id, project_id, version_id
    )
    if version is None or version.dataset_id != dataset_id:
        raise DomainError(ErrorCode.NOT_FOUND, "dataset version was not found")
    payload: dict[str, Any] = {
        "manifest": {
            "version_id": str(version.id),
            "dataset_id": str(version.dataset_id),
            "version_number": version.version_number,
            "canonicalization_version": version.canonicalization_version,
            "content_hash": version.content_hash,
            "schema_name": version.schema_name,
            "schema_version": version.schema_version,
            "schema": version.schema,
            "metadata": version.metadata,
        },
        "records": [
            {
                "key": record.key,
                "payload": record.payload,
                "metadata": record.metadata,
                "splits": list(record.splits),
                "payload_hash": record.payload_hash,
                "envelope_hash": record.envelope_hash,
            }
            for record in version.records
        ],
    }
    return JSONResponse(
        payload,
        headers={"ETag": f'"sha256:{version.content_hash}"'},
    )


@router.get("/{dataset_id}/diff", response_model=DatasetDiffRead)
async def diff_versions(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    source: uuid.UUID,
    target: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> DatasetDiffRead:
    """Compare two versions by logical record key."""

    result = await DatasetService(SqlDatasetRepository(session)).diff(
        principal,
        project_id=project_id,
        source_version_id=source,
        target_version_id=target,
    )
    return DatasetDiffRead(
        source_version_id=result.source_version_id,
        target_version_id=result.target_version_id,
        counts={kind: count for kind, count in result.counts().items()},
        records=[
            RecordDiffRead(
                key=record.key,
                kind=record.kind,
                changes=[
                    FieldChangeRead(
                        pointer=change.pointer,
                        before=change.before,
                        after=change.after,
                    )
                    for change in record.changes
                ],
            )
            for record in result.records
        ],
    )


@router.get(
    "/{dataset_id}/versions/{version_id}/sample",
    response_model=list[DatasetRecordRead],
)
async def sample_version(
    project_id: uuid.UUID,
    dataset_id: uuid.UUID,
    version_id: uuid.UUID,
    size: int,
    seed: int,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> list[DatasetRecordRead]:
    """Return a reproducible deterministic sample."""

    authorize(
        principal,
        Action.DATASET_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    version = await SqlDatasetRepository(session).get_version(
        principal.organization_id, project_id, version_id
    )
    if version is None or version.dataset_id != dataset_id:
        raise DomainError(ErrorCode.NOT_FOUND, "dataset version was not found")
    sample = deterministic_sample(version.records, size, seed=seed)
    sampled_version = DatasetVersion(
        id=version.id,
        dataset_id=version.dataset_id,
        organization_id=version.organization_id,
        project_id=version.project_id,
        version_number=version.version_number,
        schema_name=version.schema_name,
        schema_version=version.schema_version,
        schema=version.schema,
        metadata=version.metadata,
        canonicalization_version=version.canonicalization_version,
        content_hash=version.content_hash,
        records=sample,
        state=version.state,
        parent_version_ids=version.parent_version_ids,
    )
    return _record_read(sampled_version)
