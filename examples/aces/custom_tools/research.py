"""Content intelligence — viral research and gap analysis via Exa."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_viral_research_context(
        brand_id: Annotated[str, "UUID of the brand to research for"],
        topic: Annotated[str, "Topic or keyword to search for trending content"],
        platform: Annotated[str, "Target platform (instagram, linkedin, tiktok, etc.)"],
    ) -> dict[str, Any]:
        """Fetch brand context and Exa trending results for viral content research.
        Returns brand voice/pillars and real-time trending search results so Claude
        can decide which are worth saving as content ideas.
        Claude MUST call create_content_idea with source='trending' for each worthy result.
        Requires EXA_API_KEY in credentials.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.brand.repository import BrandRepository

        factory = get_session_factory()
        async with factory() as session:
            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(UUID(brand_id))
            if brand is None:
                return {"error": f"Brand {brand_id} not found"}

        brand_context = {
            "id": str(brand.id),
            "name": brand.name,
            "voice_profile": brand.voice_profile,
            "content_pillars": brand.content_pillars,
            "platforms": brand.platforms,
        }

        exa_results: list[dict] = []
        exa_error = None

        try:
            from factory.core.config import get_settings

            settings = get_settings()
            exa_key = getattr(settings, "exa_api_key", None)
            if not exa_key:
                exa_error = "EXA_API_KEY not configured"
            else:
                import httpx

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        "https://api.exa.ai/search",
                        headers={"x-api-key": exa_key},
                        json={
                            "query": f"{topic} {platform} trending",
                            "numResults": 10,
                            "useAutoprompt": True,
                        },
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        exa_results = [
                            {"title": r.get("title"), "url": r.get("url"), "score": r.get("score")}
                            for r in data.get("results", [])
                        ]
                    else:
                        exa_error = f"Exa API error: {resp.status_code}"
        except Exception as exc:
            exa_error = str(exc)

        if exa_error:
            return {"error": exa_error, "brand": brand_context}

        reasoning_prompt = (
            f"You are researching viral content trends for '{brand_context['name']}' "
            f"on '{platform}'. Topic: '{topic}'. "
            f"Review the {len(exa_results)} Exa results below. "
            f"For each genuinely trending idea, call create_content_idea with: "
            f"brand_id='{brand_id}', source='trending', "
            f"pillar (best fit from brand pillars), concept, angle, and formats."
        )

        return {
            "brand": brand_context,
            "topic": topic,
            "platform": platform,
            "exa_results": exa_results,
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def analyze_content_gaps(
        brand_id: Annotated[str, "UUID of the brand to analyze gaps for"],
        topic: Annotated[str, "Topic to search for content coverage"],
        competitor_domains: Annotated[
            list[str] | None,
            "Optional competitor domains to scope results (e.g. ['competitor.com'])",
        ] = None,
    ) -> dict[str, Any]:
        """Analyze content coverage gaps by searching for existing content via Exa.
        Returns structured results and a gap_summary for Claude to interpret.
        Read-only — does not persist any data. Requires EXA_API_KEY.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.brand.repository import BrandRepository

        factory = get_session_factory()
        async with factory() as session:
            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(UUID(brand_id))
            if brand is None:
                return {"error": f"Brand {brand_id} not found"}

        exa_results: list[dict] = []
        exa_error = None

        try:
            from factory.core.config import get_settings

            settings = get_settings()
            exa_key = getattr(settings, "exa_api_key", None)
            if not exa_key:
                exa_error = "EXA_API_KEY not configured"
            else:
                import httpx

                search_body: dict[str, Any] = {
                    "query": topic,
                    "numResults": 10,
                    "useAutoprompt": True,
                }
                if competitor_domains:
                    search_body["includeDomains"] = competitor_domains

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        "https://api.exa.ai/search",
                        headers={"x-api-key": exa_key},
                        json=search_body,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        exa_results = [
                            {"title": r.get("title"), "url": r.get("url"), "score": r.get("score")}
                            for r in data.get("results", [])
                        ]
                    else:
                        exa_error = f"Exa API error: {resp.status_code}"
        except Exception as exc:
            exa_error = str(exc)

        if exa_error:
            return {"error": exa_error}

        scope_desc = (
            f"competitor domains: {', '.join(competitor_domains)}"
            if competitor_domains
            else "the open web"
        )
        gap_summary = (
            f"Exa returned {len(exa_results)} results for '{topic}' scoped to {scope_desc}. "
            f"Review to identify: (1) subtopics heavily covered — avoid or differentiate, "
            f"(2) angles missing — opportunity for the brand, "
            f"(3) underrepresented content formats. "
            f"Suggest 2-3 content ideas to fill the gaps."
        )

        return {
            "brand_id": brand_id,
            "topic": topic,
            "competitor_domains": competitor_domains,
            "exa_results": exa_results,
            "gap_summary": gap_summary,
        }
