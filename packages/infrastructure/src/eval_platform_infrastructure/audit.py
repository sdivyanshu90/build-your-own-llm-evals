"""Tamper-evident, transactionally serialized audit-event appends."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from eval_platform_domain.canonicalization import canonical_bytes
from eval_platform_domain.ids import new_uuid7
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from eval_platform_infrastructure.models import AuditEventModel


async def append_audit_event(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None,
    actor_subject: str,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    outcome: str,
    request_id: str,
    summary: dict[str, Any] | None = None,
) -> AuditEventModel:
    """Append a hash-chained event under an organization advisory lock."""

    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:organization_id, 0))"),
        {"organization_id": str(organization_id)},
    )
    previous = await session.scalar(
        select(AuditEventModel)
        .where(AuditEventModel.organization_id == organization_id)
        .order_by(AuditEventModel.sequence.desc())
        .limit(1)
    )
    sequence = 1 if previous is None else previous.sequence + 1
    previous_hash = None if previous is None else previous.event_hash
    event_id = new_uuid7()
    safe_summary = summary or {}
    material = {
        "id": str(event_id),
        "organization_id": str(organization_id),
        "project_id": str(project_id) if project_id else None,
        "sequence": sequence,
        "actor_subject": actor_subject,
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id) if target_id else None,
        "outcome": outcome,
        "request_id": request_id,
        "summary": safe_summary,
        "previous_hash": previous_hash,
    }
    event = AuditEventModel(
        id=event_id,
        organization_id=organization_id,
        project_id=project_id,
        sequence=sequence,
        actor_subject=actor_subject,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        request_id=request_id,
        summary=safe_summary,
        previous_hash=previous_hash,
        event_hash=hashlib.sha256(canonical_bytes(material)).hexdigest(),
    )
    session.add(event)
    # Subsequent appends in the same transaction must observe this event when
    # selecting the next sequence and chain head. The advisory lock keeps the
    # flush serialized across transactions.
    await session.flush()
    return event
