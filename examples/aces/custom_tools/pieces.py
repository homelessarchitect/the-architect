"""Content piece tools — copy generation, hooks, adaptation, and copy save."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

PLATFORM_GUIDELINES = {
    "instagram": "Max 2200 chars caption. First line is the hook. Use line breaks. 20-30 hashtags.",
    "tiktok": "Short, punchy, conversational. Use trending sounds reference. 100-150 chars caption.",
    "linkedin": "Professional but human. 1300 chars for engagement. Use line breaks liberally.",
    "youtube": "SEO-optimized title (60 chars). Description with timestamps. Keywords in first 2 lines.",
    "twitter": "280 chars max. Thread format for long content. Hook in first tweet.",
    "newsletter": "Subject line < 50 chars. Preview text < 90 chars. Scannable format with headers.",
    "web": "SEO-first. H1 with keyword. Meta description < 160 chars. Structured with H2/H3.",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def generate_copy(
        piece_id: Annotated[str, "UUID of the content piece"],
        platform: Annotated[
            str,
            "Target platform: instagram|tiktok|linkedin|youtube|twitter|newsletter|web",
        ],
    ) -> dict[str, Any]:
        """Fetch piece + brand context so Claude can write platform-adapted copy inline.
        Returns brand voice, brief outline, and platform guidelines with a reasoning_prompt.
        Claude should generate the raw_copy, then call update_piece_copy to save it.
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

            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(piece.brand_id)

            brief = None
            if piece.brief_id:
                brief_repo = ContentBriefRepository(session)
                brief = await brief_repo.get(piece.brief_id)

        guidelines = PLATFORM_GUIDELINES.get(platform, "No specific guidelines.")

        reasoning_prompt = (
            f"Write copy for '{piece.title}' on {platform} (format: {piece.format}). "
            f"Brand: {brand.name if brand else 'unknown'}. "
            f"Voice: {brand.voice_profile if brand else {}}. "
            f"Platform guidelines: {guidelines}. "
            + (
                f"Brief outline: {brief.outline}. CTA: {brief.cta}. "
                if brief
                else ""
            )
            + f"After generating the copy, call update_piece_copy(piece_id='{piece_id}', "
            f"raw_copy=<your generated copy>)."
        )

        return {
            "piece": {
                "id": str(piece.id),
                "title": piece.title,
                "format": piece.format,
                "platform": piece.platform,
                "tags": piece.tags,
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
            "platform_guidelines": guidelines,
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def update_piece_copy(
        piece_id: Annotated[str, "UUID of the content piece"],
        raw_copy: Annotated[str, "Generated copy adapted to platform tone and length"],
    ) -> dict[str, Any]:
        """Save generated raw copy to a content piece. Call after generate_copy returns context."""
        from factory.core.database import get_session_factory
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.generated.aces.content_piece.serialize import serialize_content_piece

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}
            piece.raw_copy = raw_copy
            await session.flush()
            await session.refresh(piece)
            await session.commit()

        return {"piece": serialize_content_piece(piece)}

    @mcp.tool()
    async def generate_hooks(
        concept: Annotated[str, "The content concept or idea to generate hooks for"],
        brand_id: Annotated[str, "UUID of the brand"],
        count: Annotated[int, "Number of hook variations to generate (default 5)"] = 5,
    ) -> dict[str, Any]:
        """Fetch brand context so Claude can generate hook variations inline for A/B testing.
        Returns brand voice and a reasoning_prompt. Claude generates and returns the hooks
        directly — no save needed. Hooks are suggestions for create_content_brief.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.brand.repository import BrandRepository

        factory = get_session_factory()
        async with factory() as session:
            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(UUID(brand_id))
            if brand is None:
                return {"error": f"Brand {brand_id} not found"}

        reasoning_prompt = (
            f"Generate {count} hook variations for the concept: '{concept}'. "
            f"Brand: {brand.name}. Voice: {brand.voice_profile}. "
            f"Hook types to use: contrarian ('Todo lo que te dijeron sobre X está mal'), "
            f"statistic ('El 90% de los creadores comete este error'), "
            f"direct question ('¿Por qué tu contenido no convierte?'), "
            f"POV narrative ('POV: finalmente resolviste X'), "
            f"promise ('Te doy nuestro framework completo, gratis'). "
            f"Return the hooks directly — no save needed."
        )

        return {
            "brand": {
                "id": str(brand.id),
                "name": brand.name,
                "voice_profile": brand.voice_profile,
            },
            "concept": concept,
            "requested_count": count,
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def adapt_content(
        piece_id: Annotated[str, "UUID of the source content piece to repurpose"],
        target_format: Annotated[
            str,
            "Target format: reel|carousel|static-post|story|thread|newsletter|long-video|short-video|blog|podcast",
        ],
        target_platform: Annotated[
            str,
            "Target platform: instagram|tiktok|linkedin|youtube|twitter|newsletter|web",
        ],
    ) -> dict[str, Any]:
        """Fetch source piece + brand context so Claude can adapt content to a new format/platform.
        Returns source content, brand voice, format notes, and a reasoning_prompt.
        Claude adapts the content, then calls create_content_piece with parent_piece_id
        set to the source piece.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.brand.repository import BrandRepository
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.generated.aces.script.repository import ScriptRepository

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}

            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(piece.brand_id)

            script_context = None
            if piece.script_id:
                script_repo = ScriptRepository(session)
                script = await script_repo.get(piece.script_id)
                if script:
                    script_context = {
                        "archetype": script.archetype,
                        "hook": script.hook,
                        "body_beats": script.body_beats,
                        "cta": script.cta,
                    }

        guidelines = PLATFORM_GUIDELINES.get(target_platform, "No specific guidelines.")

        reasoning_prompt = (
            f"Adapt the content piece '{piece.title}' (format: {piece.format}, "
            f"platform: {piece.platform}) to target format '{target_format}' "
            f"on '{target_platform}'. "
            f"Brand: {brand.name if brand else 'unknown'}. "
            f"Voice: {brand.voice_profile if brand else {}}. "
            f"Platform guidelines: {guidelines}. "
            f"Source copy: {piece.raw_copy or 'not available'}. "
            + (f"Source script: hook='{script_context['hook']}'. " if script_context else "")
            + f"Create the adapted content, then call create_content_piece with "
            f"parent_piece_id='{piece_id}', brand_id='{piece.brand_id}', "
            f"format='{target_format}', platform='{target_platform}'."
        )

        return {
            "source_piece": {
                "id": str(piece.id),
                "title": piece.title,
                "format": piece.format,
                "platform": piece.platform,
                "raw_copy": piece.raw_copy,
                "tags": piece.tags,
            },
            "source_script": script_context,
            "brand": (
                {
                    "id": str(brand.id),
                    "name": brand.name,
                    "voice_profile": brand.voice_profile,
                }
                if brand
                else None
            ),
            "target_format": target_format,
            "target_platform": target_platform,
            "platform_guidelines": guidelines,
            "reasoning_prompt": reasoning_prompt,
        }
