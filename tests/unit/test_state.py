import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factory.core.database import Base
from factory.modules.state.models import StateLock, WorkflowState
from factory.modules.state.service import StateService


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class TestStateService:
    async def test_get_latest_empty(self, async_session: AsyncSession):
        service = StateService(async_session)
        result = await service.get_latest("nonexistent")
        assert result is None

    async def test_create_first_version(self, async_session: AsyncSession):
        service = StateService(async_session)
        state = await service.create_version(
            workflow_slug="crm",
            schema_hash="abc123def456",
            entities={"names": ["lead", "interaction"]},
            tools_count=10,
            tables_list=["crm_leads", "crm_interactions"],
            providers=["resend"],
        )
        await async_session.commit()
        assert state.version == 1
        assert state.workflow_slug == "crm"
        assert state.lineage is not None
        assert state.schema_hash == "abc123def456"

    async def test_create_increments_version(self, async_session: AsyncSession):
        service = StateService(async_session)
        v1 = await service.create_version(
            workflow_slug="crm",
            schema_hash="hash1",
            entities={"names": ["lead"]},
            tools_count=5,
            tables_list=["crm_leads"],
            providers=[],
        )
        await async_session.commit()

        v2 = await service.create_version(
            workflow_slug="crm",
            schema_hash="hash2",
            entities={"names": ["lead", "campaign"]},
            tools_count=10,
            tables_list=["crm_leads", "crm_campaigns"],
            providers=[],
        )
        await async_session.commit()
        assert v2.version == 2
        assert v2.lineage == v1.lineage

    async def test_get_latest_returns_highest_version(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.create_version("crm", "h1", {"names": []}, 0, [], [])
        await async_session.commit()
        await service.create_version("crm", "h2", {"names": []}, 0, [], [])
        await async_session.commit()

        latest = await service.get_latest("crm")
        assert latest is not None
        assert latest.version == 2

    async def test_acquire_lock(self, async_session: AsyncSession):
        service = StateService(async_session)
        lock = await service.acquire_lock("crm", "apply")
        await async_session.commit()
        assert lock.workflow_slug == "crm"
        assert lock.operation == "apply"
        assert lock.lock_id is not None

    async def test_acquire_lock_blocked(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.acquire_lock("crm", "apply", ttl_seconds=300)
        await async_session.commit()

        with pytest.raises(RuntimeError, match="is locked"):
            await service.acquire_lock("crm", "plan")

    async def test_acquire_lock_expired(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.acquire_lock("crm", "apply", ttl_seconds=0)
        await async_session.commit()

        # Should succeed because TTL is 0 (already expired)
        lock = await service.acquire_lock("crm", "plan")
        await async_session.commit()
        assert lock.operation == "plan"

    async def test_release_lock(self, async_session: AsyncSession):
        service = StateService(async_session)
        lock = await service.acquire_lock("crm", "apply")
        await async_session.commit()

        released = await service.release_lock("crm", lock.lock_id)
        await async_session.commit()
        assert released is True

    async def test_release_lock_wrong_id(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.acquire_lock("crm", "apply")
        await async_session.commit()

        released = await service.release_lock("crm", uuid.uuid4())
        assert released is False

    async def test_release_lock_nonexistent(self, async_session: AsyncSession):
        service = StateService(async_session)
        released = await service.release_lock("crm", uuid.uuid4())
        assert released is False

    async def test_compute_hash(self, tmp_path: Path):
        workflow_file = tmp_path / "workflow.py"
        workflow_file.write_text("name = 'test'")

        h1 = StateService.compute_hash(workflow_file)
        assert len(h1) == 12

        h2 = StateService.compute_hash(workflow_file)
        assert h1 == h2

        workflow_file.write_text("name = 'changed'")
        h3 = StateService.compute_hash(workflow_file)
        assert h3 != h1

    async def test_diff_state_new(self, async_session: AsyncSession):
        service = StateService(async_session)
        diff = await service.diff_state("crm", "abc123", ["lead", "campaign"])
        assert diff["status"] == "new"
        assert diff["entities_to_create"] == ["lead", "campaign"]

    async def test_diff_state_no_changes(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.create_version("crm", "abc123", {"names": ["lead"]}, 5, [], [])
        await async_session.commit()

        diff = await service.diff_state("crm", "abc123", ["lead"])
        assert diff["status"] == "no_changes"

    async def test_diff_state_modified(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.create_version("crm", "abc123", {"names": ["lead"]}, 5, [], [])
        await async_session.commit()

        diff = await service.diff_state("crm", "xyz789", ["lead", "campaign"])
        assert diff["status"] == "modified"
        assert "campaign" in diff["entities_to_create"]
        assert diff["entities_to_remove"] == []

    async def test_diff_state_entity_removed(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.create_version(
            "crm", "abc123", {"names": ["lead", "old_entity"]}, 5, [], []
        )
        await async_session.commit()

        diff = await service.diff_state("crm", "xyz789", ["lead"])
        assert diff["status"] == "modified"
        assert "old_entity" in diff["entities_to_remove"]

    async def test_list_all_latest(self, async_session: AsyncSession):
        service = StateService(async_session)
        await service.create_version("crm", "h1", {"names": []}, 0, [], [])
        await async_session.commit()
        await service.create_version("crm", "h2", {"names": []}, 0, [], [])
        await async_session.commit()
        await service.create_version("content", "h1", {"names": []}, 0, [], [])
        await async_session.commit()

        all_latest = await service.list_all_latest()
        assert len(all_latest) == 2
        slugs = {s.workflow_slug for s in all_latest}
        assert slugs == {"crm", "content"}
        crm = next(s for s in all_latest if s.workflow_slug == "crm")
        assert crm.version == 2
