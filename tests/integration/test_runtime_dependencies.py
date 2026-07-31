"""Real PostgreSQL, Redis, object-store, migration, and API isolation checks."""

from __future__ import annotations

import uuid

import pytest
from eval_platform_api.main import create_app
from eval_platform_infrastructure.audit import append_audit_event
from eval_platform_infrastructure.database import create_engine, create_session_factory
from eval_platform_infrastructure.models import AuditEventModel, OrganizationModel, ProjectModel
from eval_platform_infrastructure.object_store import S3ObjectStore
from eval_platform_infrastructure.settings import Environment, Settings
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select, text

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _settings() -> Settings:
    return Settings(environment=Environment.TEST, rate_limit_enabled=False)


async def test_migrations_and_transactional_audit_hash_chain() -> None:
    settings = _settings()
    engine = create_engine(settings.database_url.get_secret_value())
    factory = create_session_factory(engine)
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    try:
        async with factory() as session:
            assert (
                await session.execute(text("select version_num from alembic_version"))
            ).scalar_one()
            session.add(
                OrganizationModel(id=organization_id, slug=f"org-{organization_id}", name="I")
            )
            session.add(
                ProjectModel(
                    id=project_id,
                    organization_id=organization_id,
                    slug=f"project-{project_id}",
                    name="Integration",
                    concurrency_limit=2,
                    budget_amount=10,
                    budget_currency="USD",
                )
            )
            await session.flush()
            first = await append_audit_event(
                session,
                organization_id=organization_id,
                project_id=project_id,
                actor_subject="integration",
                action="test.first",
                target_type="project",
                target_id=project_id,
                outcome="succeeded",
                request_id="integration-1",
            )
            second = await append_audit_event(
                session,
                organization_id=organization_id,
                project_id=project_id,
                actor_subject="integration",
                action="test.second",
                target_type="project",
                target_id=project_id,
                outcome="succeeded",
                request_id="integration-2",
            )
            await session.flush()
            stored = list(
                (
                    await session.scalars(
                        select(AuditEventModel)
                        .where(AuditEventModel.organization_id == organization_id)
                        .order_by(AuditEventModel.sequence)
                    )
                ).all()
            )
            assert [event.event_hash for event in stored] == [first.event_hash, second.event_hash]
            assert second.previous_hash == first.event_hash
            await session.rollback()
    finally:
        await engine.dispose()


async def test_redis_and_s3_round_trip() -> None:
    settings = _settings()
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    key = f"integration:{uuid.uuid4()}"
    try:
        assert await redis.ping()
        await redis.set(key, "ready", ex=30)
        assert await redis.get(key) == "ready"
    finally:
        await redis.delete(key)
        await redis.aclose()

    store = S3ObjectStore(
        endpoint_url=settings.s3_endpoint_url,
        region=settings.s3_region,
        bucket=settings.s3_bucket,
        access_key_id=settings.s3_access_key_id.get_secret_value(),
        secret_access_key=settings.s3_secret_access_key.get_secret_value(),
    )
    await store.ensure_bucket()
    await store.check()
    object_key = f"integration/{uuid.uuid4()}/evidence.json"
    stored = await store.put(object_key, b'{"state":"ready"}', media_type="application/json")
    assert stored.byte_size == 17
    assert await store.get(object_key, max_bytes=100) == b'{"state":"ready"}'


async def test_api_health_openapi_and_cross_project_isolation() -> None:
    settings = _settings()
    app = create_app(settings)
    await app.state.object_store.ensure_bucket()
    organization_id = uuid.uuid4()
    bound_project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    headers = {
        "X-Organization-ID": str(organization_id),
        "X-Project-ID": str(bound_project_id),
        "X-Role": "admin",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://integration",
    ) as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready")
        schema = await client.get("/api/openapi.json")
        isolated = await client.get(
            f"/api/v1/projects/{other_project_id}/datasets",
            headers=headers,
        )
    assert live.status_code == 200
    assert ready.status_code == 200
    assert ready.json()["object_store"] == "ready"
    assert schema.status_code == 200
    assert "/api/v1/projects/{project_id}/comparisons" in schema.json()["paths"]
    assert isolated.status_code == 404
    assert isolated.json()["error"] == "not_found"
    await app.state.engine.dispose()
