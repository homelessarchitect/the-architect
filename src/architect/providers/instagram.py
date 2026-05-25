from __future__ import annotations

from typing import Any, ClassVar

from architect.primitives.entity import FieldDef
from architect.primitives.provider import Provider


class InstagramProvider(Provider):
    name: ClassVar[str] = "instagram"
    config_fields: ClassVar[list[FieldDef]] = [
        FieldDef(
            "access_token", str, required=True, description="Instagram Graph API access token"
        ),
        FieldDef(
            "business_account_id",
            str,
            required=True,
            description="Instagram Business Account ID",
        ),
    ]

    async def execute(
        self, action: str, payload: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        if action == "publish":
            return {
                "status": "stub",
                "action": action,
                "provider": self.name,
                "message": f"Would publish to Instagram: {payload.get('content', '')[:50]}...",
            }
        if action == "get_metrics":
            return {
                "status": "stub",
                "action": action,
                "provider": self.name,
                "message": (
                    f"Would fetch metrics for post {payload.get('post_id', 'unknown')}"
                ),
            }
        return {"error": f"Unknown action '{action}' for provider '{self.name}'"}
