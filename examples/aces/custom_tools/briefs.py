"""Content brief generation — context-fetcher and save with side effects."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

FRAMEWORKS = {
    "PSP": "Pattern-interrupt (1-3s) → Story (10-20s) → Payoff + CTA (4-7s)",
    "PAS": "Problem → Agitate → Solution",
    "AIDA": "Attention → Interest → Desire → Action",
    "BAB": "Before → After → Bridge",
    "StoryBrand": "Customer is hero, Brand is guide, Stakes are real",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_brief_context(
        idea_id: Annotated[str, "UUID of the content idea to brief"],
        objective: Annotated[
            str, "Content objective: awareness|engagement|traffic|conversion|education"
        ],
        storytelling_framework: Annotated[str, "Framework: AIDA|PAS|BAB|StoryBrand|PSP"],
    ) -> dict[str, Any]:
        """Fetch idea + brand context so Claude can generate a content brief inline.
        Returns idea details, brand voice, framework structure, and hook type references.
        Claude should generate hook_options, outline, cta, and keywords,
        then call save_content_brief with the generated content.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.brand.repository import BrandRepository
        from factory.generated.aces.content_idea.repository import ContentIdeaRepository

        factory = get_session_factory()
        async with factory() as session:
            idea_repo = ContentIdeaRepository(session)
            idea = await idea_repo.get(UUID(idea_id))
            if idea is None:
                return {"error": f"ContentIdea {idea_id} not found"}

            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(idea.brand_id)

        framework_desc = FRAMEWORKS.get(storytelling_framework, storytelling_framework)

        reasoning_prompt = (
            f"Create a content brief for the idea: '{idea.concept}' "
            f"with angle: '{idea.angle}'. "
            f"Objective: {objective}. Framework: {storytelling_framework} ({framework_desc}). "
            f"Brand: {brand.name if brand else 'unknown'}. "
            f"Voice: {brand.voice_profile if brand else {}}. "
            f"Generate: 3-5 hook_options (each with 'type' and 'text'), "
            f"an outline (ordered beats with 'beat' and 'content'), "
            f"a low-friction CTA, and 5-10 keywords. "
            f"Hook types to consider: contrarian, statistic, direct question, "
            f"POV narrative, promise. "
            f"Then call save_content_brief with the generated content."
        )

        return {
            "idea": {
                "id": str(idea.id),
                "brand_id": str(idea.brand_id),
                "pillar": idea.pillar,
                "concept": idea.concept,
                "angle": idea.angle,
                "formats": idea.formats,
            },
            "brand": (
                {
                    "id": str(brand.id),
                    "name": brand.name,
                    "voice_profile": brand.voice_profile,
                    "content_pillars": brand.content_pillars,
                }
                if brand
                else None
            ),
            "objective": objective,
            "framework": storytelling_framework,
            "framework_description": framework_desc,
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def save_content_brief(
        idea_id: Annotated[str, "UUID of the content idea this brief belongs to"],
        brand_id: Annotated[str, "UUID of the brand"],
        objective: Annotated[
            str, "Content objective: awareness|engagement|traffic|conversion|education"
        ],
        storytelling_framework: Annotated[str, "Framework: AIDA|PAS|BAB|StoryBrand|PSP"],
        hook_options: Annotated[list[dict], "3-5 hook variations, each with 'type' and 'text'"],
        outline: Annotated[list[dict], "Ordered beats, each with 'beat' and 'content'"],
        cta: Annotated[str, "Low-friction call to action"],
        keywords: Annotated[list[str], "SEO/content keywords (5-10)"] = [],
        references: Annotated[dict | None, "Visual refs or competitor examples"] = None,
        notes: Annotated[str | None, "Additional notes"] = None,
    ) -> dict[str, Any]:
        """Save a content brief. Transitions the idea status to 'briefed'.
        Call get_brief_context first, then this tool with the generated content.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.content_brief.models import ContentBrief
        from factory.generated.aces.content_brief.repository import ContentBriefRepository
        from factory.generated.aces.content_idea.repository import ContentIdeaRepository

        factory = get_session_factory()
        async with factory() as session:
            brief = ContentBrief(
                idea_id=UUID(idea_id),
                brand_id=UUID(brand_id),
                objective=objective,
                storytelling_framework=storytelling_framework,
                hook_options=hook_options,
                outline=outline,
                cta=cta,
                keywords=keywords,
                references=references,
                notes=notes,
            )
            brief_repo = ContentBriefRepository(session)
            brief = await brief_repo.add(brief)

            idea_repo = ContentIdeaRepository(session)
            idea = await idea_repo.get(UUID(idea_id))
            if idea and idea.status == "backlog":
                idea.status = "briefed"
                await session.flush()

            await session.commit()
            await session.refresh(brief)

        from factory.generated.aces.content_brief.serialize import serialize_content_brief

        return {"brief": serialize_content_brief(brief)}
