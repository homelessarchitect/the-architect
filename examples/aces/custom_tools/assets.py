"""Asset tools — context-fetchers for AI image prompts and motion briefs."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

PLATFORM_SPECS = {
    "instagram": {
        "reel": {"dimensions": "1080x1920", "aspect_ratio": "9:16", "format": "mp4"},
        "carousel": {"dimensions": "1080x1080", "aspect_ratio": "1:1", "format": "jpg"},
        "static-post": {"dimensions": "1080x1080", "aspect_ratio": "1:1", "format": "jpg"},
        "story": {"dimensions": "1080x1920", "aspect_ratio": "9:16", "format": "jpg"},
    },
    "tiktok": {
        "reel": {"dimensions": "1080x1920", "aspect_ratio": "9:16", "format": "mp4"},
        "short-video": {"dimensions": "1080x1920", "aspect_ratio": "9:16", "format": "mp4"},
    },
    "linkedin": {
        "static-post": {"dimensions": "1200x627", "aspect_ratio": "1.91:1", "format": "jpg"},
        "carousel": {"dimensions": "1080x1080", "aspect_ratio": "1:1", "format": "pdf"},
    },
    "youtube": {
        "long-video": {"dimensions": "1920x1080", "aspect_ratio": "16:9", "format": "mp4"},
        "short-video": {"dimensions": "1080x1920", "aspect_ratio": "9:16", "format": "mp4"},
    },
}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_image_prompt_context(
        piece_id: Annotated[str, "UUID of the ContentPiece to generate an image prompt for"],
    ) -> dict[str, Any]:
        """Context-fetcher for AI image prompt generation. Returns brand visual identity,
        platform asset specs, and a reasoning_prompt instructing Claude to generate a detailed
        prompt and then call create_asset to save it.
        """
        from architect.core.database import get_session_factory
        from architect.generated.aces.brand.repository import BrandRepository
        from architect.generated.aces.content_piece.repository import ContentPieceRepository

        factory = get_session_factory()
        async with factory() as session:
            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece is None:
                return {"error": f"ContentPiece {piece_id} not found"}

            brand_repo = BrandRepository(session)
            brand = await brand_repo.get(piece.brand_id)

        platform_key = piece.platform if hasattr(piece, "platform") else "instagram"
        format_key = piece.format if hasattr(piece, "format") else "static-post"
        specs = PLATFORM_SPECS.get(platform_key, {}).get(format_key, {})

        reasoning_prompt = (
            f"Generate a detailed AI image prompt for '{piece.title}' "
            f"(format: {piece.format}, platform: {piece.platform}). "
            f"Brand: {brand.name if brand else 'unknown'}. "
            f"Visual identity: {brand.visual_identity if brand else {}}. "
            f"Target specs: {specs}. "
            f"Be specific about: composition, colors (use brand palette), typography style, "
            f"mood, lighting, and any text overlays. "
            f"After generating the prompt, call create_asset with: "
            f"piece_id='{piece_id}', asset_type='image', "
            f"format_specs='{specs}', ai_prompt=<your prompt>."
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
                    "visual_identity": brand.visual_identity,
                    "voice_profile": brand.voice_profile,
                }
                if brand
                else None
            ),
            "platform_specs": specs,
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def get_motion_brief_context(
        piece_id: Annotated[str, "UUID of the ContentPiece to generate a motion brief for"],
    ) -> dict[str, Any]:
        """Context-fetcher for motion design brief generation. Returns brand identity,
        platform specs, and a reasoning_prompt. Use for reels, short-videos, or any
        video format requiring motion design direction.
        """
        from architect.core.database import get_session_factory
        from architect.generated.aces.brand.repository import BrandRepository
        from architect.generated.aces.content_piece.repository import ContentPieceRepository
        from architect.generated.aces.script.repository import ScriptRepository

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
                        "estimated_duration": script.estimated_duration,
                    }

        platform_key = piece.platform if hasattr(piece, "platform") else "instagram"
        format_key = piece.format if hasattr(piece, "format") else "reel"
        specs = PLATFORM_SPECS.get(platform_key, {}).get(format_key, {})

        reasoning_prompt = (
            f"Write a motion design brief for '{piece.title}' "
            f"(format: {piece.format}, platform: {piece.platform}). "
            f"Brand: {brand.name if brand else 'unknown'}. "
            f"Visual identity: {brand.visual_identity if brand else {}}. "
            f"Target specs: {specs}. "
            + (
                f"Script: hook='{script_context['hook']}', "
                f"beats={len(script_context['body_beats'])} beats, "
                f"duration={script_context['estimated_duration']}s. "
                if script_context
                else ""
            )
            + f"Include: timing per section, transitions, text animations, "
            f"b-roll directions, music mood. "
            f"Call create_asset with asset_type='video', "
            f"format_specs='{specs}', production_brief=<your brief>."
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
                    "visual_identity": brand.visual_identity,
                }
                if brand
                else None
            ),
            "script": script_context,
            "platform_specs": specs,
            "reasoning_prompt": reasoning_prompt,
        }
