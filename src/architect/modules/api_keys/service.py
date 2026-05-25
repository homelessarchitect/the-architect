from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from architect.modules.api_keys.models import ApiKey

_ph = PasswordHasher()


class ApiKeyService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_key(self, name: str, created_by: str = "cli") -> tuple[ApiKey, str]:
        """Create a new API key. Returns (model, plaintext_key).
        The plaintext is shown ONCE — it cannot be recovered.
        """
        raw_key = secrets.token_urlsafe(32)
        prefix = raw_key[:8]
        hashed = _ph.hash(raw_key)

        api_key = ApiKey(
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            created_by=created_by,
        )
        self._session.add(api_key)
        await self._session.flush()
        await self._session.refresh(api_key)
        return api_key, raw_key

    async def verify_key(self, raw_key: str) -> ApiKey | None:
        """Verify an API key. Returns the ApiKey if valid, None otherwise."""
        prefix = raw_key[:8]
        stmt = (
            select(ApiKey)
            .where(ApiKey.prefix == prefix)
            .where(ApiKey.revoked_at.is_(None))
        )
        result = await self._session.execute(stmt)
        api_key = result.scalar_one_or_none()

        if api_key is None:
            return None

        try:
            _ph.verify(api_key.hashed_key, raw_key)
        except VerifyMismatchError:
            return None

        api_key.last_used_at = datetime.now(UTC)
        await self._session.flush()
        return api_key

    async def list_keys(self) -> list[ApiKey]:
        stmt = (
            select(ApiKey)
            .where(ApiKey.revoked_at.is_(None))
            .order_by(ApiKey.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke_key(self, key_id: uuid.UUID) -> bool:
        api_key = await self._session.get(ApiKey, key_id)
        if api_key is None or api_key.revoked_at is not None:
            return False
        api_key.revoked_at = datetime.now(UTC)
        await self._session.flush()
        return True
