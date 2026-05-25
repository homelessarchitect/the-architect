from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from factory.core.database import get_session_factory
from factory.modules.api_keys.service import ApiKeyService


class ApiKeyAuthMiddleware:
    """ASGI middleware that validates API keys via X-API-Key header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        api_key_header = request.headers.get("x-api-key")

        if not api_key_header:
            response = JSONResponse(
                {"error": "Missing X-API-Key header"}, status_code=401
            )
            await response(scope, receive, send)
            return

        factory = get_session_factory()
        async with factory() as session:
            service = ApiKeyService(session)
            api_key = await service.verify_key(api_key_header)
            await session.commit()

        if api_key is None:
            response = JSONResponse(
                {"error": "Invalid API key"}, status_code=401
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
