"""Agent context — orientation snapshot for session start."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_agent_context() -> dict[str, Any]:
        """Get a full orientation snapshot of the ACES workspace.
        Returns: active brands, pending approvals awaiting human review,
        content pieces currently in review, and calendar slots due in the next 7 days.
        Call this first at the start of any session to understand the current state.
        """
        from sqlalchemy import select

        from architect.core.database import get_session_factory
        from architect.generated.aces.brand.models import Brand
        from architect.generated.aces.calendar_slot.models import CalendarSlot
        from architect.generated.aces.content_piece.models import ContentPiece
        from architect.modules.approvals.models import Approval

        factory = get_session_factory()
        async with factory() as session:
            brands_result = await session.execute(
                select(Brand).where(Brand.is_active.is_(True)).order_by(Brand.name)
            )
            brands = list(brands_result.scalars().all())

            approvals_result = await session.execute(
                select(Approval)
                .where(Approval.status == "pending")
                .where(Approval.workflow_slug == "aces")
                .order_by(Approval.created_at.desc())
                .limit(20)
            )
            pending_approvals = list(approvals_result.scalars().all())

            pieces_result = await session.execute(
                select(ContentPiece)
                .where(ContentPiece.status == "review")
                .order_by(ContentPiece.updated_at.desc())
                .limit(20)
            )
            pieces_in_review = list(pieces_result.scalars().all())

            today = date.today()
            due_by = today + timedelta(days=7)
            today_str = today.isoformat()
            due_by_str = due_by.isoformat()
            slots_result = await session.execute(
                select(CalendarSlot)
                .where(CalendarSlot.planned_date >= today_str)
                .where(CalendarSlot.planned_date <= due_by_str)
                .order_by(CalendarSlot.planned_date.asc())
                .limit(20)
            )
            due_soon = list(slots_result.scalars().all())

        return {
            "active_brands": [
                {
                    "id": str(b.id),
                    "name": b.name,
                    "platforms": b.platforms,
                    "pillars": [p["name"] for p in (b.content_pillars or [])],
                }
                for b in brands
            ],
            "pending_approvals": [
                {
                    "id": str(a.id),
                    "action_type": a.action_type,
                    "related_entity_id": str(a.related_entity_id)
                    if a.related_entity_id
                    else None,
                    "requested_by": a.requested_by,
                    "created_at": a.created_at.isoformat(),
                }
                for a in pending_approvals
            ],
            "pieces_in_review": [
                {
                    "id": str(p.id),
                    "brand_id": str(p.brand_id),
                    "title": p.title,
                    "format": p.format,
                    "platform": p.platform,
                }
                for p in pieces_in_review
            ],
            "calendar_slots_due_soon": [
                {
                    "id": str(s.id),
                    "calendar_id": str(s.calendar_id),
                    "piece_id": str(s.piece_id) if s.piece_id else None,
                    "planned_date": s.planned_date,
                    "platform": s.platform,
                    "format": s.format,
                    "pillar": s.pillar,
                    "status": s.status,
                }
                for s in due_soon
            ],
            "summary": {
                "active_brands": len(brands),
                "pending_approvals": len(pending_approvals),
                "pieces_in_review": len(pieces_in_review),
                "calendar_slots_due_7d": len(due_soon),
            },
        }
