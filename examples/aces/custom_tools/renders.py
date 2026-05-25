"""Remotion render management — enqueue and poll render jobs."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def render_reel(
        piece_id: Annotated[
            str, "UUID of the ContentPiece to render (must have format='reel' and a Script)"
        ],
    ) -> dict[str, Any]:
        """Start a Remotion video render for a reel ContentPiece.
        Validates piece has format='reel' and a linked Script.
        Creates a RenderJob(status=queued) and runs the render in the background.
        Poll get_render_status(render_id) to track progress.
        """
        from architect.core.database import get_session_factory
        from architect.generated.aces.content_piece.repository import ContentPieceRepository
        from architect.generated.aces.render_job.models import RenderJob
        from architect.generated.aces.render_job.repository import RenderJobRepository

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}
            if piece.format != "reel":
                return {"error": f"Expected format 'reel', got '{piece.format}'"}
            if not piece.script_id:
                return {"error": "Piece has no linked script. Call save_script first."}

            render = RenderJob(
                piece_id=UUID(piece_id),
                script_id=piece.script_id,
                status="queued",
            )
            render_repo = RenderJobRepository(session)
            render = await render_repo.add(render)
            await session.commit()

        return {
            "render_id": str(render.id),
            "status": "queued",
            "message": (
                "Render job queued. Poll get_render_status to track progress. "
                "Note: actual Remotion rendering requires the Remotion service to be running."
            ),
        }

    @mcp.tool()
    async def render_carousel_slide(
        piece_id: Annotated[str, "UUID of the carousel ContentPiece"],
        slot_order: Annotated[
            int, "0-based index of the slide slot to render (matches slide plan order)"
        ],
    ) -> dict[str, Any]:
        """Render a single carousel slide as a JPEG image using the brand template.
        Validates piece has format='carousel' and a SlidePlan with a valid slot at slot_order.
        Returns {render_id, status='queued'} on success.
        """
        from architect.core.database import get_session_factory
        from architect.generated.aces.content_piece.repository import ContentPieceRepository
        from architect.generated.aces.render_job.models import RenderJob
        from architect.generated.aces.render_job.repository import RenderJobRepository
        from architect.generated.aces.slide_plan.repository import SlidePlanRepository

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}
            if piece.format != "carousel":
                return {"error": f"Expected format 'carousel', got '{piece.format}'"}

            plan_repo = SlidePlanRepository(session)
            plans = await plan_repo.list(piece_id=UUID(piece_id))
            if not plans:
                return {"error": "No slide plan found. Call plan_carousel_slides first."}

            plan = plans[0]
            slot = next((s for s in (plan.slots or []) if s.get("order") == slot_order), None)
            if slot is None:
                return {"error": f"No slot at order {slot_order} in the slide plan."}

            render = RenderJob(
                piece_id=UUID(piece_id),
                slot_order=slot_order,
                status="queued",
            )
            render_repo = RenderJobRepository(session)
            render = await render_repo.add(render)
            await session.commit()

        return {
            "render_id": str(render.id),
            "status": "queued",
            "slot_order": slot_order,
            "message": "Carousel slide render queued. Poll get_render_status to track.",
        }

    @mcp.tool()
    async def get_render_status(
        render_id: Annotated[str, "UUID of the RenderJob to check"],
    ) -> dict[str, Any]:
        """Get the current status of a render job.
        Status values: queued, rendering, ready (video_url available), failed (error field set).
        """
        from architect.core.database import get_session_factory
        from architect.generated.aces.render_job.repository import RenderJobRepository
        from architect.generated.aces.render_job.serialize import serialize_render_job

        factory = get_session_factory()
        async with factory() as session:
            render_repo = RenderJobRepository(session)
            job = await render_repo.get(UUID(render_id))

        if job is None:
            return {"error": f"RenderJob {render_id} not found"}

        return serialize_render_job(job)
