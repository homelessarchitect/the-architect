from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factory.modules.approvals.models import Approval
from factory.runtime.dispatcher import Dispatcher


class ApprovalService:
    def __init__(self, session: AsyncSession, dispatcher: Dispatcher | None = None) -> None:
        self._session = session
        self._dispatcher = dispatcher

    async def create(
        self,
        workflow_slug: str,
        action_type: str,
        payload: dict,
        related_entity_id: uuid.UUID | None = None,
        requested_by: str = "agent",
    ) -> Approval:
        approval = Approval(
            workflow_slug=workflow_slug,
            action_type=action_type,
            payload=payload,
            status="pending",
            related_entity_id=related_entity_id,
            requested_by=requested_by,
        )
        self._session.add(approval)
        await self._session.flush()
        await self._session.refresh(approval)
        return approval

    async def approve(
        self, approval_id: uuid.UUID, resolved_by: str = "human"
    ) -> Approval:
        approval = await self._session.get(Approval, approval_id)
        if approval is None:
            raise ValueError(f"Approval '{approval_id}' not found")
        if approval.status != "pending":
            raise ValueError(
                f"Approval '{approval_id}' is not pending (status: {approval.status})"
            )

        approval.status = "approved"
        approval.resolved_by = resolved_by
        approval.resolved_at = datetime.now(UTC)
        await self._session.flush()

        # Execute via dispatcher if available
        if self._dispatcher:
            try:
                await self._dispatcher.execute(approval.action_type, approval.payload)
                approval.status = "executed"
                approval.executed_at = datetime.now(UTC)
            except Exception as exc:
                approval.status = "failed"
                approval.error = str(exc)
            await self._session.flush()

        await self._session.refresh(approval)
        return approval

    async def reject(
        self, approval_id: uuid.UUID, resolved_by: str = "human"
    ) -> Approval:
        approval = await self._session.get(Approval, approval_id)
        if approval is None:
            raise ValueError(f"Approval '{approval_id}' not found")
        if approval.status != "pending":
            raise ValueError(
                f"Approval '{approval_id}' is not pending (status: {approval.status})"
            )

        approval.status = "rejected"
        approval.resolved_by = resolved_by
        approval.resolved_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(approval)
        return approval

    async def list_pending(self, workflow_slug: str | None = None) -> list[Approval]:
        stmt = select(Approval).where(Approval.status == "pending")
        if workflow_slug:
            stmt = stmt.where(Approval.workflow_slug == workflow_slug)
        stmt = stmt.order_by(Approval.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, approval_id: uuid.UUID) -> Approval | None:
        return await self._session.get(Approval, approval_id)

    async def pending_count(self, workflow_slug: str | None = None) -> int:
        pending = await self.list_pending(workflow_slug)
        return len(pending)
