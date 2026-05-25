from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from architect.modules.state.models import StateLock, WorkflowState
from architect.modules.state.repository import StateRepository


class StateService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = StateRepository(session)

    async def get_latest(self, workflow_slug: str) -> WorkflowState | None:
        return await self._repo.get_latest(workflow_slug)

    async def create_version(
        self,
        workflow_slug: str,
        schema_hash: str,
        entities: dict,
        tools_count: int,
        tables_list: list[str],
        providers: list[str],
        created_by: str = "cli",
    ) -> WorkflowState:
        return await self._repo.create_version(
            workflow_slug=workflow_slug,
            schema_hash=schema_hash,
            entities=entities,
            tools_count=tools_count,
            tables_list=tables_list,
            providers=providers,
            created_by=created_by,
        )

    async def list_all_latest(self) -> list[WorkflowState]:
        return await self._repo.list_all_latest()

    async def acquire_lock(
        self,
        workflow_slug: str,
        operation: str,
        locked_by: str = "cli",
        ttl_seconds: int = 300,
    ) -> StateLock:
        return await self._repo.acquire_lock(workflow_slug, operation, locked_by, ttl_seconds)

    async def release_lock(self, workflow_slug: str, lock_id: uuid.UUID) -> bool:
        return await self._repo.release_lock(workflow_slug, lock_id)

    @staticmethod
    def compute_hash(workflow_path: str | Path) -> str:
        content = Path(workflow_path).read_bytes()
        return hashlib.sha256(content).hexdigest()[:12]

    async def diff_state(
        self,
        workflow_slug: str,
        current_hash: str,
        current_entities: list[str],
    ) -> dict:
        latest = await self.get_latest(workflow_slug)
        if latest is None:
            return {
                "status": "new",
                "message": f"Workflow '{workflow_slug}' is new — will create everything",
                "entities_to_create": current_entities,
                "entities_to_remove": [],
            }

        if latest.schema_hash == current_hash:
            return {
                "status": "no_changes",
                "message": "No changes detected",
                "version": latest.version,
            }

        previous_entities = list(latest.entities.get("names", []))
        new_entities = [e for e in current_entities if e not in previous_entities]
        removed_entities = [e for e in previous_entities if e not in current_entities]

        return {
            "status": "modified",
            "message": f"Changes detected (v{latest.version} → v{latest.version + 1})",
            "entities_to_create": new_entities,
            "entities_to_remove": removed_entities,
            "previous_version": latest.version,
        }
