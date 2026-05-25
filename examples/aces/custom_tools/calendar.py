"""Calendar tools — context-fetcher for editorial planning and overview."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_calendar_build_context(
        brand_id: Annotated[str, "UUID of the brand to build a calendar for"],
        period_start: Annotated[str, "Start date ISO format YYYY-MM-DD"],
        period_end: Annotated[str, "End date ISO format YYYY-MM-DD"],
        editorial_theme: Annotated[str, "The macro narrative theme for this period"],
        platform_frequency: Annotated[
            str,
            'JSON: posts per week per platform e.g. {"instagram": 5, "tiktok": 7, "newsletter": 1}',
        ],
    ) -> dict[str, Any]:
        """Context-fetcher for calendar planning. Returns brand voice, pillars, platform config,
        and a reasoning_prompt instructing Claude to call create_content_calendar then
        create_calendar_slot for each planned post.
        """
        import json

        from factory.core.database import get_session_factory
        from factory.generated.aces.brand.repository import BrandRepository

        factory = get_session_factory()
        async with factory() as session:
            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(UUID(brand_id))
            if brand is None:
                return {"error": f"Brand {brand_id} not found"}

        freq = json.loads(platform_frequency) if isinstance(platform_frequency, str) else platform_frequency
        pillars = [p["name"] for p in (brand.content_pillars or [])]

        reasoning_prompt = (
            f"Build a content calendar for '{brand.name}' from {period_start} to {period_end}. "
            f"Theme: {editorial_theme}. "
            f"Platform frequency per week: {freq}. "
            f"Content pillars to rotate: {pillars}. "
            f"Platforms: {brand.platforms}. "
            f"Steps: "
            f"1) Call create_content_calendar(brand_id='{brand_id}', name=<name>, "
            f"editorial_theme='{editorial_theme}', period_start='{period_start}', "
            f"period_end='{period_end}', platform_frequency={freq}). "
            f"2) For each planned post, call create_calendar_slot(calendar_id=<id>, "
            f"planned_date=<date>, platform=<platform>, format=<format>, pillar=<pillar>). "
            f"Distribute pillars evenly. Vary formats (reel, carousel, static-post, newsletter)."
        )

        return {
            "brand": {
                "id": str(brand.id),
                "name": brand.name,
                "content_pillars": brand.content_pillars,
                "platforms": brand.platforms,
                "voice_profile": brand.voice_profile,
            },
            "period_start": period_start,
            "period_end": period_end,
            "editorial_theme": editorial_theme,
            "platform_frequency": freq,
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def get_calendar_overview(
        brand_id: Annotated[str, "UUID of the brand"],
        from_date: Annotated[str | None, "Start date filter ISO format YYYY-MM-DD"] = None,
        to_date: Annotated[str | None, "End date filter ISO format YYYY-MM-DD"] = None,
    ) -> dict[str, Any]:
        """Get all calendar slots for a brand across all calendars. Useful for scheduling overview."""
        from sqlalchemy import select

        from factory.core.database import get_session_factory
        from factory.generated.aces.calendar_slot.models import CalendarSlot
        from factory.generated.aces.content_calendar.models import ContentCalendar

        factory = get_session_factory()
        async with factory() as session:
            stmt = (
                select(CalendarSlot)
                .join(ContentCalendar, CalendarSlot.calendar_id == ContentCalendar.id)
                .where(ContentCalendar.brand_id == UUID(brand_id))
            )
            if from_date:
                stmt = stmt.where(CalendarSlot.planned_date >= from_date)
            if to_date:
                stmt = stmt.where(CalendarSlot.planned_date <= to_date)
            stmt = stmt.order_by(CalendarSlot.planned_date.asc())

            result = await session.execute(stmt)
            slots = list(result.scalars().all())

        return {
            "entries": [
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
                for s in slots
            ],
            "count": len(slots),
        }
