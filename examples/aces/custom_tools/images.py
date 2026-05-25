"""Gemini image generation — external integration (requires GOOGLE_STUDIO_API_KEY)."""
from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def generate_image_with_gemini(
        prompt: Annotated[
            str,
            "Detailed image generation prompt. Be specific about composition, colors, typography, mood.",
        ],
        aspect_ratio: Annotated[
            str,
            "Aspect ratio. Valid: 1:1 (default), 3:4, 4:3, 9:16, 16:9.",
        ] = "1:1",
        model: Annotated[
            str | None,
            "Gemini model ID. Defaults to gemini-2.0-flash-preview-image-generation.",
        ] = None,
    ) -> dict[str, Any]:
        """Generate an image via Google Gemini and return a URL.
        Requires GOOGLE_STUDIO_API_KEY in credentials.
        Aspect ratio is a hint — Gemini may drift; 1:1 is safest for IG.
        On quota/rate-limit, returns error dict.
        """
        from architect.core.config import get_settings

        settings = get_settings()
        google_key = getattr(settings, "google_studio_api_key", None)
        if not google_key:
            return {
                "error": "integration_not_configured",
                "detail": (
                    "GOOGLE_STUDIO_API_KEY not configured. "
                    "Set it via `architect credential set google_studio_api_key <key>` "
                    "or as an environment variable."
                ),
            }

        try:
            import httpx

            async with httpx.AsyncClient(timeout=120) as client:
                model_id = model or "gemini-2.0-flash-preview-image-generation"
                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent",
                    params={"key": google_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseModalities": ["TEXT", "IMAGE"],
                            "imageSizeHint": {"aspectRatio": aspect_ratio},
                        },
                    },
                )
                if resp.status_code == 429:
                    return {"error": "rate_limited", "detail": "Gemini quota exceeded", "retry_after": 60}
                if resp.status_code != 200:
                    return {"error": "api_error", "detail": f"Gemini returned {resp.status_code}: {resp.text[:500]}"}

                data = resp.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return {"error": "no_image", "detail": "Gemini returned no candidates"}

                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        import base64
                        image_bytes = base64.b64decode(part["inlineData"]["data"])
                        return {
                            "image_generated": True,
                            "size_bytes": len(image_bytes),
                            "mime_type": part["inlineData"].get("mimeType", "image/png"),
                            "detail": (
                                "Image generated successfully. Save the base64 data to a file "
                                "or upload endpoint to get a URL for the Asset record."
                            ),
                        }

                return {"error": "no_image", "detail": "Gemini response contained no image data"}

        except Exception as exc:
            return {"error": "api_error", "detail": str(exc)}
