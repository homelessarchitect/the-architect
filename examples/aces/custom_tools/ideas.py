"""Content idea generation — context-fetcher for Claude reasoning."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def generate_content_ideas(
        brand_id: Annotated[str, "UUID of the brand to generate ideas for"],
        pillar: Annotated[str, "Content pillar to focus ideas on"],
        count: Annotated[int, "Number of ideas to generate (default 5, max 20)"] = 5,
        persona_id: Annotated[str | None, "UUID of target persona for tailored ideas"] = None,
    ) -> dict[str, Any]:
        """Fetch brand and persona context so Claude can generate content ideas inline.
        Returns brand voice, content pillars, platforms, and persona details.
        Claude should use this context to reason and produce {count} ideas,
        then call create_content_idea for each one with source='ai-generated'.
        """
        from architect.core.database import get_session_factory
        from architect.generated.aces.brand.repository import BrandRepository
        from architect.generated.aces.persona.repository import PersonaRepository

        factory = get_session_factory()
        async with factory() as session:
            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(UUID(brand_id))
            if brand is None:
                return {"error": f"Brand {brand_id} not found"}

            persona_context = None
            if persona_id:
                persona_repo = PersonaRepository(session)
                persona = await persona_repo.get(UUID(persona_id))
                if persona:
                    persona_context = {
                        "id": str(persona.id),
                        "name": persona.name,
                        "type": persona.type,
                        "demographics": persona.demographics,
                        "pain_points": persona.pain_points,
                        "goals": persona.goals,
                        "content_channels": persona.content_channels,
                        "content_preferences": persona.content_preferences,
                    }

        reasoning_prompt = (
            f"Generate {count} content ideas for the brand '{brand.name}' "
            f"focused on the '{pillar}' pillar. "
            f"Brand voice: {brand.voice_profile}. "
            f"Available platforms: {brand.platforms}. "
            f"Content pillars: {[p['name'] for p in (brand.content_pillars or [])]}. "
            + (
                f"Target persona: {persona_context['name']} — "
                f"pain points: {persona_context['pain_points']}, "
                f"goals: {persona_context['goals']}. "
                if persona_context
                else ""
            )
            + f"For each idea provide: concept (one sentence), angle (specific hook), "
            f"and suggested formats. Then call create_content_idea for each with "
            f"source='ai-generated'."
        )

        return {
            "brand": {
                "id": str(brand.id),
                "name": brand.name,
                "voice_profile": brand.voice_profile,
                "content_pillars": brand.content_pillars,
                "platforms": brand.platforms,
            },
            "target_pillar": pillar,
            "persona": persona_context,
            "requested_count": count,
            "reasoning_prompt": reasoning_prompt,
        }
