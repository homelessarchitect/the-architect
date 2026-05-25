"""Carousel slide planning — context-fetcher and plan creation with asset pre-creation."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def generate_slide_plan_context(
        piece_id: Annotated[str, "UUID of the carousel piece to plan for"],
    ) -> dict[str, Any]:
        """Fetch brief + piece context for Claude to reason about a slide plan.
        Returns brief outline, hook_options, cta, keywords, and the piece's format/platform.
        Claude should design 2-10 slots and call plan_carousel_slides.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.brand.repository import BrandRepository
        from factory.generated.aces.content_brief.repository import ContentBriefRepository
        from factory.generated.aces.content_piece.repository import ContentPieceRepository

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}
            if piece.format != "carousel":
                return {
                    "error": "not_carousel",
                    "detail": f"Slide plans only for carousel format, got {piece.format}",
                }

            brief = None
            if piece.brief_id:
                brief_repo = ContentBriefRepository(session)
                brief = await brief_repo.get(piece.brief_id)

            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(piece.brand_id)

        reasoning_prompt = (
            f"Design a slide plan for the carousel '{piece.title}' on {piece.platform}. "
            f"Brand: {brand.name if brand else 'unknown'}. "
            f"Voice: {brand.voice_profile.get('tone', '') if brand and brand.voice_profile else ''}. "
            f"Use the brief's outline as the foundation — each beat typically maps to one slide. "
            f"Hooks become slide 0. CTAs become the last slide. "
            f"Aim for 5-8 slides (IG carousel sweet spot, max 10). "
            f"For each slide: order (0-indexed), "
            f"role (hook|stat|explanation|case|cta|transition|other), "
            f"text_overlay (visible text on image), "
            f"visual_brief (how to render — used as production_brief for the Asset). "
            f"Then call plan_carousel_slides(piece_id='{piece_id}', slots=[...])."
        )

        return {
            "piece": {
                "id": str(piece.id),
                "title": piece.title,
                "format": piece.format,
                "platform": piece.platform,
            },
            "brand": (
                {
                    "id": str(brand.id),
                    "name": brand.name,
                    "voice_profile": brand.voice_profile,
                }
                if brand
                else None
            ),
            "brief": (
                {
                    "id": str(brief.id),
                    "objective": brief.objective,
                    "framework": brief.storytelling_framework,
                    "hook_options": brief.hook_options,
                    "outline": brief.outline,
                    "cta": brief.cta,
                    "keywords": brief.keywords,
                }
                if brief
                else None
            ),
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def plan_carousel_slides(
        piece_id: Annotated[str, "UUID of the carousel ContentPiece"],
        slots: Annotated[
            list[dict],
            "List of 2-10 slot dicts: {order, role, text_overlay, visual_brief, suggested_archetype?}",
        ],
        replace: Annotated[
            bool, "If True, replace existing plan. Default False — returns error if plan exists."
        ] = False,
    ) -> dict[str, Any]:
        """Create a slide plan for a carousel piece. Pre-creates Asset records per slot.
        Use generate_slide_plan_context first to read the brief and reason about slides.
        Returns plan_id, piece_id, slots, and asset_ids (one per slot).
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.asset.models import Asset
        from factory.generated.aces.asset.repository import AssetRepository
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.generated.aces.slide_plan.models import SlidePlan
        from factory.generated.aces.slide_plan.repository import SlidePlanRepository

        if len(slots) < 2 or len(slots) > 10:
            return {"error": "ValidationError", "detail": "slots must have 2-10 items"}

        for s in slots:
            if "order" not in s or "role" not in s or "text_overlay" not in s:
                return {
                    "error": "ValidationError",
                    "detail": "Each slot needs: order, role, text_overlay, visual_brief",
                }

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}
            if piece.format != "carousel":
                return {"error": f"Expected carousel format, got {piece.format}"}

            plan_repo = SlidePlanRepository(session)
            existing = await plan_repo.list(piece_id=UUID(piece_id))
            if existing and not replace:
                return {
                    "error": "PlanExists",
                    "detail": f"Slide plan already exists for piece {piece_id}. Use replace=True.",
                }

            if existing and replace:
                for old_plan in existing:
                    await plan_repo.delete(old_plan.id)

            plan = SlidePlan(piece_id=UUID(piece_id), slots=slots)
            plan = await plan_repo.add(plan)

            asset_repo = AssetRepository(session)
            asset_ids = []
            for slot in sorted(slots, key=lambda s: s["order"]):
                asset = Asset(
                    piece_id=UUID(piece_id),
                    type="image",
                    format_specs={
                        "dimensions": "1080x1080",
                        "aspect_ratio": "1:1",
                        "file_format": "jpg",
                        "order": slot["order"],
                    },
                    production_brief=slot.get("visual_brief", ""),
                    status="pending",
                )
                asset = await asset_repo.add(asset)
                asset_ids.append(str(asset.id))

            await session.commit()

        return {
            "plan_id": str(plan.id),
            "piece_id": str(plan.piece_id),
            "slots": plan.slots,
            "asset_ids": asset_ids,
        }
