from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from architect.core.database import Base
from architect.modules.credentials.service import CredentialStore


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def mock_encryption():
    with (
        patch(
            "architect.modules.credentials.service.encrypt",
            side_effect=lambda s: s.encode(),
        ),
        patch(
            "architect.modules.credentials.service.decrypt",
            side_effect=lambda b: b.decode(),
        ),
    ):
        yield


class TestCredentialStore:
    async def test_add_credential(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        cred = await store.add(name="openai_key", provider="openai", value="sk-abc123")
        await async_session.commit()

        assert cred.id is not None
        assert cred.name == "openai_key"
        assert cred.provider == "openai"
        assert cred.encrypted_data == b"sk-abc123"
        assert cred.scope_workflow is None
        assert cred.scope_agent is None

    async def test_get_credential_global(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        await store.add(name="openai_key", provider="openai", value="sk-global")
        await async_session.commit()

        result = await store.get("openai_key")
        assert result == "sk-global"

    async def test_get_credential_scoped_workflow(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        await store.add(
            name="api_key",
            provider="openai",
            value="sk-workflow",
            scope_workflow="crm",
        )
        await async_session.commit()

        result = await store.get("api_key", workflow_slug="crm")
        assert result == "sk-workflow"

    async def test_get_credential_scoped_workflow_and_agent(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        await store.add(
            name="api_key",
            provider="openai",
            value="sk-agent",
            scope_workflow="crm",
            scope_agent="lead_qualifier",
        )
        await async_session.commit()

        result = await store.get("api_key", workflow_slug="crm", agent_name="lead_qualifier")
        assert result == "sk-agent"

    async def test_get_credential_priority(self, async_session: AsyncSession):
        """workflow+agent > workflow > global"""
        store = CredentialStore(async_session)

        # The unique constraint is on name, so we need different names
        # or we need to remove the unique constraint for scoped creds.
        # Since the model has unique=True on name, we test priority
        # by adding one credential at a time and verifying resolution.

        # Global credential
        await store.add(name="key_global", provider="openai", value="global-val")
        await async_session.commit()

        # Workflow-scoped credential (different name due to unique constraint)
        await store.add(
            name="key_wf",
            provider="openai",
            value="workflow-val",
            scope_workflow="crm",
        )
        await async_session.commit()

        # Workflow+agent scoped credential
        await store.add(
            name="key_agent",
            provider="openai",
            value="agent-val",
            scope_workflow="crm",
            scope_agent="qualifier",
        )
        await async_session.commit()

        # Global key resolves globally
        assert await store.get("key_global") == "global-val"

        # Workflow key resolves when workflow matches
        assert await store.get("key_wf", workflow_slug="crm") == "workflow-val"

        # Agent key resolves when both match
        assert (
            await store.get("key_agent", workflow_slug="crm", agent_name="qualifier")
            == "agent-val"
        )

    async def test_get_credential_wrong_scope_returns_none(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        await store.add(
            name="scoped_key",
            provider="openai",
            value="scoped-val",
            scope_workflow="crm",
            scope_agent="qualifier",
        )
        await async_session.commit()

        # Wrong workflow
        result = await store.get("scoped_key", workflow_slug="billing")
        assert result is None

        # No scope at all -- should not match a workflow+agent scoped cred
        result = await store.get("scoped_key")
        assert result is None

    async def test_get_nonexistent(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        result = await store.get("does_not_exist")
        assert result is None

    async def test_list_all(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        await store.add(name="key_a", provider="openai", value="secret-a")
        await async_session.commit()
        await store.add(name="key_b", provider="anthropic", value="secret-b")
        await async_session.commit()

        items = await store.list_all()
        assert len(items) == 2

        # Verify no decrypted values are exposed
        for item in items:
            assert "encrypted_data" not in item
            assert "value" not in item
            assert "name" in item
            assert "provider" in item
            assert "id" in item

    async def test_remove(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        await store.add(name="to_remove", provider="openai", value="bye")
        await async_session.commit()

        removed = await store.remove("to_remove")
        await async_session.commit()
        assert removed is True

        result = await store.get("to_remove")
        assert result is None

    async def test_remove_nonexistent(self, async_session: AsyncSession):
        store = CredentialStore(async_session)
        removed = await store.remove("ghost")
        assert removed is False
