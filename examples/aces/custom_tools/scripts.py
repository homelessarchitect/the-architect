"""Script generation — context-fetcher and save with piece status transition."""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

ARCHETYPES = {
    "how-to": "Step-by-step tutorial. Clear value proposition. Numbered beats.",
    "myth-buster": "Challenge a common belief. Present evidence. Reveal truth.",
    "case-study": "Real example. Before/after. Quantified results.",
    "secret-tool": "Reveal an unknown tool/technique. Demo it. Show results.",
    "mistake-hook": "Common mistake opener. Why it happens. How to fix it.",
    "pov": "First-person narrative. Emotional journey. Relatable payoff.",
    "trend-alert": "Timely topic. Why it matters NOW. What to do about it.",
    "zero-click-value": "Complete answer in the content. No click needed. Pure value.",
}


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def generate_script(
        piece_id: Annotated[str, "UUID of the content piece to script"],
        archetype: Annotated[
            str,
            "Script archetype: how-to|myth-buster|case-study|secret-tool|mistake-hook|pov|trend-alert|zero-click-value",
        ],
    ) -> dict[str, Any]:
        """Fetch piece + brief + brand context so Claude can write a video script inline.
        Returns piece details, brand voice, archetype description, and platform guidelines.
        Claude should generate the script, then call save_script with the generated content.
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

        archetype_desc = ARCHETYPES.get(archetype, archetype)

        reasoning_prompt = (
            f"Write a video script for '{piece.title}' using the '{archetype}' archetype. "
            f"Archetype pattern: {archetype_desc}. "
            f"Brand: {brand.name if brand else 'unknown'}. "
            f"Voice: {brand.voice_profile if brand else {}}. "
            f"Platform: {piece.platform}. Format: {piece.format}. "
            + (
                f"Brief outline: {brief.outline}. CTA: {brief.cta}. "
                if brief
                else ""
            )
            + f"Structure: hook (first 3 seconds — make-or-break), "
            f"body_beats ([{{order, beat_type, content, duration_seconds}}]), "
            f"cta (low-friction closing). "
            f"Then call save_script(piece_id='{piece_id}', archetype='{archetype}', "
            f"hook=..., body_beats=..., cta=..., estimated_duration=..., platform_notes=...)."
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
                }
                if brief
                else None
            ),
            "archetype": archetype,
            "archetype_description": archetype_desc,
            "reasoning_prompt": reasoning_prompt,
        }

    @mcp.tool()
    async def save_script(
        piece_id: Annotated[str, "UUID of the content piece this script belongs to"],
        archetype: Annotated[
            str,
            "Script archetype: how-to|myth-buster|case-study|secret-tool|mistake-hook|pov|trend-alert|zero-click-value",
        ],
        hook: Annotated[str, "Opening hook — first 3 seconds, make-or-break"],
        body_beats: Annotated[
            list[dict], "Ordered beats: [{order, beat_type, content, duration_seconds}]"
        ],
        cta: Annotated[str, "Low-friction call to action for the closing"],
        estimated_duration: Annotated[int | None, "Total estimated duration in seconds"] = None,
        platform_notes: Annotated[str | None, "Platform-specific delivery tips"] = None,
    ) -> dict[str, Any]:
        """Save a generated script. Transitions piece status to 'scripted'
        and back-links piece.script_id. Call generate_script first.
        """
        from factory.core.database import get_session_factory
        from factory.generated.aces.content_piece.repository import ContentPieceRepository
        from factory.generated.aces.script.models import Script
        from factory.generated.aces.script.repository import ScriptRepository
        from factory.generated.aces.script.serialize import serialize_script

        factory = get_session_factory()
        async with factory() as session:
            script = Script(
                piece_id=UUID(piece_id),
                archetype=archetype,
                hook=hook,
                body_beats=body_beats,
                cta=cta,
                estimated_duration=estimated_duration,
                platform_notes=platform_notes,
            )
            script_repo = ScriptRepository(session)
            script = await script_repo.add(script)

            piece_repo = ContentPieceRepository(session)
            piece = await piece_repo.get(UUID(piece_id))
            if piece:
                piece.script_id = script.id
                if piece.status in ("idea", "briefed"):
                    piece.status = "scripted"
                await session.flush()

            await session.commit()
            await session.refresh(script)

        return {"script": serialize_script(script)}
