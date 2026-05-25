from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from architect.core.encryption import decrypt, encrypt
from architect.modules.credentials.models import Credential


class CredentialStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        name: str,
        provider: str,
        value: str,
        scope_workflow: str | None = None,
        scope_agent: str | None = None,
    ) -> Credential:
        encrypted = encrypt(value)
        credential = Credential(
            name=name,
            provider=provider,
            encrypted_data=encrypted,
            scope_workflow=scope_workflow,
            scope_agent=scope_agent,
        )
        self._session.add(credential)
        await self._session.flush()
        await self._session.refresh(credential)
        return credential

    async def get(
        self,
        name: str,
        workflow_slug: str | None = None,
        agent_name: str | None = None,
    ) -> str | None:
        """Get decrypted credential value with scoping resolution.

        Priority: workflow+agent > workflow > global
        """
        stmt = select(Credential).where(Credential.name == name)
        result = await self._session.execute(stmt)
        candidates = list(result.scalars().all())

        if not candidates:
            return None

        best: Credential | None = None
        best_score = -1

        for cred in candidates:
            score = 0
            if cred.scope_workflow == workflow_slug and cred.scope_agent == agent_name:
                score = 3
            elif cred.scope_workflow == workflow_slug and cred.scope_agent is None:
                score = 2
            elif cred.scope_workflow is None and cred.scope_agent is None:
                score = 1
            else:
                continue

            if score > best_score:
                best = cred
                best_score = score

        if best is None:
            return None

        return decrypt(best.encrypted_data)

    async def list_all(self) -> list[dict]:
        stmt = select(Credential).order_by(Credential.created_at.desc())
        result = await self._session.execute(stmt)
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "provider": c.provider,
                "scope_workflow": c.scope_workflow,
                "scope_agent": c.scope_agent,
            }
            for c in result.scalars().all()
        ]

    async def remove(self, name: str) -> bool:
        stmt = select(Credential).where(Credential.name == name)
        result = await self._session.execute(stmt)
        credential = result.scalar_one_or_none()
        if credential is None:
            return False
        await self._session.delete(credential)
        await self._session.flush()
        return True
