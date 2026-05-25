from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from architect.modules.state.models import StateLock, WorkflowState


class StateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest(self, workflow_slug: str) -> WorkflowState | None:
        stmt = (
            select(WorkflowState)
            .where(WorkflowState.workflow_slug == workflow_slug)
            .order_by(WorkflowState.version.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_version(
        self,
        workflow_slug: str,
        schema_hash: str,
        entities: dict,
        tools_count: int,
        tables_list: list[str],
        providers: list[str],
        created_by: str = "cli",
        lineage: uuid.UUID | None = None,
    ) -> WorkflowState:
        latest = await self.get_latest(workflow_slug)
        version = (latest.version + 1) if latest else 1
        actual_lineage = lineage or (latest.lineage if latest else uuid.uuid4())

        state = WorkflowState(
            workflow_slug=workflow_slug,
            version=version,
            lineage=actual_lineage,
            schema_hash=schema_hash,
            entities=entities,
            tools_count=tools_count,
            tables_list=tables_list,
            providers=providers,
            created_by=created_by,
        )
        self._session.add(state)
        await self._session.flush()
        await self._session.refresh(state)
        return state

    async def list_all_latest(self) -> list[WorkflowState]:
        subq = (
            select(
                WorkflowState.workflow_slug,
                func.max(WorkflowState.version).label("max_version"),
            )
            .group_by(WorkflowState.workflow_slug)
            .subquery()
        )
        stmt = select(WorkflowState).join(
            subq,
            (WorkflowState.workflow_slug == subq.c.workflow_slug)
            & (WorkflowState.version == subq.c.max_version),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def acquire_lock(
        self,
        workflow_slug: str,
        operation: str,
        locked_by: str = "cli",
        ttl_seconds: int = 300,
    ) -> StateLock:
        now = datetime.now(UTC)
        existing = await self._session.get(StateLock, workflow_slug)

        expires = existing.expires_at if existing else None
        # SQLite returns naive datetimes; treat them as UTC for comparison.
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)

        if existing and expires is not None and expires > now:
            raise RuntimeError(
                f"Workflow '{workflow_slug}' is locked by '{existing.locked_by}' "
                f"for '{existing.operation}' until {existing.expires_at.isoformat()}"
            )

        if existing:
            await self._session.delete(existing)
            await self._session.flush()

        lock = StateLock(
            workflow_slug=workflow_slug,
            lock_id=uuid.uuid4(),
            locked_by=locked_by,
            locked_at=now,
            expires_at=datetime.fromtimestamp(
                now.timestamp() + ttl_seconds, tz=UTC
            ),
            operation=operation,
        )
        self._session.add(lock)
        await self._session.flush()
        await self._session.refresh(lock)
        return lock

    async def release_lock(self, workflow_slug: str, lock_id: uuid.UUID) -> bool:
        existing = await self._session.get(StateLock, workflow_slug)
        if not existing or existing.lock_id != lock_id:
            return False
        await self._session.delete(existing)
        await self._session.flush()
        return True
