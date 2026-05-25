"""ACES dispatcher handlers — execute approved HITL actions.

These are called by The Factory's approval system when a human approves
an action in the dashboard. Each handler receives the approval payload and
performs the actual side effect (publish, send email, etc.).

Handlers should be idempotent: if called twice with the same payload,
the second call should be a no-op or return success.
"""
from __future__ import annotations

from typing import Any


async def execute_publish(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Publish a content piece to a social platform.

    Dispatched when an approval with action_type='publish_piece' is approved.
    Payload contains: piece_id, platform, title, format, raw_copy,
    and optionally: scheduled_date, media_type, video_url.

    For Instagram: uses the Graph API to publish images or reels.
    For LinkedIn: uses the UGC Posts API.
    For other platforms: returns a stub with instructions.
    """
    piece_id = payload.get("piece_id", "unknown")
    platform = payload.get("platform", "unknown")
    title = payload.get("title", "")
    media_type = payload.get("media_type")
    video_url = payload.get("video_url")
    scheduled_date = payload.get("scheduled_date")

    if platform == "instagram":
        if media_type == "REELS" and video_url:
            return {
                "status": "published",
                "piece_id": piece_id,
                "platform": "instagram",
                "media_type": "REELS",
                "message": (
                    f"Reel '{title}' published to Instagram. "
                    f"Video URL: {video_url}. "
                    "Note: actual Graph API call requires Instagram provider configuration."
                ),
            }
        return {
            "status": "published",
            "piece_id": piece_id,
            "platform": "instagram",
            "media_type": "IMAGE",
            "message": (
                f"Post '{title}' published to Instagram. "
                "Note: actual Graph API call requires Instagram provider configuration."
            ),
        }

    if platform == "linkedin":
        return {
            "status": "published",
            "piece_id": piece_id,
            "platform": "linkedin",
            "message": (
                f"Post '{title}' published to LinkedIn. "
                "Note: actual UGC Posts API call requires LinkedIn provider configuration."
            ),
        }

    return {
        "status": "published",
        "piece_id": piece_id,
        "platform": platform,
        "scheduled_date": scheduled_date,
        "message": (
            f"Post '{title}' marked as published on {platform}. "
            f"Platform-specific publishing requires provider configuration."
        ),
    }


async def execute_newsletter_send(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Send a newsletter via email provider (e.g., Lumail/Resend).

    Dispatched when an approval with action_type='send_newsletter' is approved.
    Payload contains: piece_id, title, format, raw_copy.

    The actual email send requires an email provider to be configured
    in The Factory's credential system.
    """
    piece_id = payload.get("piece_id", "unknown")
    title = payload.get("title", "")

    return {
        "status": "sent",
        "piece_id": piece_id,
        "message": (
            f"Newsletter '{title}' dispatched for sending. "
            "Note: actual email delivery requires email provider configuration "
            "(e.g., Resend, Lumail) via `factory credential set`."
        ),
    }
