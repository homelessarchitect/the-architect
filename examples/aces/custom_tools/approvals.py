"""HITL approval tools — queue publish/newsletter requests for human review."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def request_publish(
        piece_id: Annotated[str, "UUID of the content piece to publish"],
        platform: Annotated[
            str,
            "Target platform: instagram|tiktok|linkedin|youtube|twitter|newsletter|web",
        ],
        scheduled_date: Annotated[
            str | None, "Planned publish date ISO YYYY-MM-DD (omit for immediate)"
        ] = None,
    ) -> dict[str, Any]:
        """Queue a publish request for human approval. Does NOT publish immediately.
        Creates an Approval(pending) and transitions piece status to 'review'.
        The human approves or rejects in the dashboard.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.generated.aces.render_job.repository import RenderJobRepository
        from factory.modules.approvals.service import ApprovalService

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}

            payload: dict[str, Any] = {
                "piece_id": piece_id,
                "platform": platform,
                "title": piece.title,
                "format": piece.format,
                "raw_copy": piece.raw_copy,
            }
            if scheduled_date:
                payload["scheduled_date"] = scheduled_date

            if platform == "instagram" and piece.format == "reel" and piece.script_id:
                render_repo = RenderJobRepository(session)
                renders = await render_repo.list(piece_id=UUID(piece_id))
                ready_renders = [r for r in renders if r.status == "ready"]
                if ready_renders:
                    latest = max(ready_renders, key=lambda r: r.created_at)
                    if latest.video_url:
                        payload["media_type"] = "REELS"
                        payload["video_url"] = latest.video_url

            svc = ApprovalService(session)
            approval = await svc.create(
                workflow_slug="aces",
                action_type="publish_piece",
                payload=payload,
                related_entity_id=UUID(piece_id),
                requested_by="claude_code",
            )

            if piece.status not in ("review", "approved", "published"):
                piece.status = "review"
                await session.flush()

            await session.commit()

        return {
            "approval": {
                "id": str(approval.id),
                "action_type": approval.action_type,
                "status": approval.status,
                "payload": approval.payload,
                "created_at": approval.created_at.isoformat(),
            },
            "message": "Publish request queued for human approval. Status: pending.",
        }

    @mcp.tool()
    async def request_newsletter_send(
        piece_id: Annotated[str, "UUID of the newsletter content piece to send"],
    ) -> dict[str, Any]:
        """Queue a newsletter send request for human approval. Does NOT send immediately.
        Creates an Approval(pending) and transitions piece status to 'review'.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.modules.approvals.service import ApprovalService

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}

            payload = {
                "piece_id": piece_id,
                "title": piece.title,
                "format": piece.format,
                "raw_copy": piece.raw_copy,
            }

            svc = ApprovalService(session)
            approval = await svc.create(
                workflow_slug="aces",
                action_type="send_newsletter",
                payload=payload,
                related_entity_id=UUID(piece_id),
                requested_by="claude_code",
            )

            if piece.status not in ("review", "approved", "published"):
                piece.status = "review"
                await session.flush()

            await session.commit()

        return {
            "approval": {
                "id": str(approval.id),
                "action_type": approval.action_type,
                "status": approval.status,
                "payload": approval.payload,
                "created_at": approval.created_at.isoformat(),
            },
            "message": "Newsletter send request queued for human approval. Status: pending.",
        }

    @mcp.tool()
    async def list_pending_approvals(
        limit: Annotated[int, "Max results (default 20)"] = 20,
    ) -> dict[str, Any]:
        """List all ACES approvals with status 'pending' — actions awaiting human review.
        Includes piece preview (title, copy, format, platform) when available.
        """
        from sqlalchemy import select

        from factory.core.database import get_session_factory
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.modules.approvals.models import Approval

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Approval)
                .where(Approval.status == "pending")
                .where(Approval.workflow_slug == "aces")
                .order_by(Approval.created_at.desc())
                .limit(limit)
            )
            approvals = list(result.scalars().all())

            enriched = []
            piece_repo = ContentPieceRepository(session)
            for a in approvals:
                entry: dict[str, Any] = {
                    "id": str(a.id),
                    "action_type": a.action_type,
                    "payload": a.payload,
                    "status": a.status,
                    "requested_by": a.requested_by,
                    "created_at": a.created_at.isoformat(),
                }
                if a.related_entity_id:
                    piece = await piece_repo.get(a.related_entity_id)
                    if piece:
                        entry["piece_preview"] = {
                            "title": piece.title,
                            "format": piece.format,
                            "platform": piece.platform,
                            "raw_copy": (piece.raw_copy or "")[:200],
                        }
                enriched.append(entry)

        return {"approvals": enriched, "count": len(enriched)}
