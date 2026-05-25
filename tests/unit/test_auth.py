import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factory.core.database import Base
from factory.modules.api_keys.service import ApiKeyService


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


class TestApiKeyService:
    async def test_create_key(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        api_key, plaintext = await service.create_key("test-key")
        await async_session.commit()
        assert api_key.name == "test-key"
        assert api_key.prefix == plaintext[:8]
        assert len(plaintext) > 20

    async def test_verify_valid_key(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        _, plaintext = await service.create_key("test-key")
        await async_session.commit()

        result = await service.verify_key(plaintext)
        assert result is not None
        assert result.name == "test-key"
        assert result.last_used_at is not None

    async def test_verify_invalid_key(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        await service.create_key("test-key")
        await async_session.commit()

        result = await service.verify_key("totally-invalid-key-value")
        assert result is None

    async def test_verify_wrong_key(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        _, plaintext = await service.create_key("test-key")
        await async_session.commit()

        mangled = plaintext[:8] + "WRONG" + plaintext[13:]
        result = await service.verify_key(mangled)
        assert result is None

    async def test_verify_revoked_key(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        api_key, plaintext = await service.create_key("test-key")
        await async_session.commit()

        await service.revoke_key(api_key.id)
        await async_session.commit()

        result = await service.verify_key(plaintext)
        assert result is None

    async def test_list_keys(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        await service.create_key("key-1")
        await service.create_key("key-2")
        await async_session.commit()

        keys = await service.list_keys()
        assert len(keys) == 2

    async def test_list_excludes_revoked(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        k1, _ = await service.create_key("key-1")
        await service.create_key("key-2")
        await async_session.commit()

        await service.revoke_key(k1.id)
        await async_session.commit()

        keys = await service.list_keys()
        assert len(keys) == 1
        assert keys[0].name == "key-2"

    async def test_revoke_key(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        api_key, _ = await service.create_key("test-key")
        await async_session.commit()

        result = await service.revoke_key(api_key.id)
        assert result is True

    async def test_revoke_nonexistent(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        result = await service.revoke_key(uuid.uuid4())
        assert result is False

    async def test_revoke_already_revoked(self, async_session: AsyncSession):
        service = ApiKeyService(async_session)
        api_key, _ = await service.create_key("test-key")
        await async_session.commit()
        await service.revoke_key(api_key.id)
        await async_session.commit()

        result = await service.revoke_key(api_key.id)
        assert result is False
