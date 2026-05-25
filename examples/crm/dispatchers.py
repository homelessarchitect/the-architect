"""Example dispatcher handler for lead conversion."""

from typing import Any


async def handle_conversion(payload: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    lead_id = payload.get("lead_id", "unknown")
    return {
        "status": "converted",
        "lead_id": lead_id,
        "message": f"Lead {lead_id} marked as converted",
    }
