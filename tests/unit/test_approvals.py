import uuid
from typing import Any, ClassVar

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factory.core.database import Base
from factory.modules.approvals.models import Approval  # noqa: F401
from factory.modules.approvals.service import ApprovalService
from factory.primitives import DispatcherDefinition, Provider
from factory.runtime.dispatcher import Dispatcher
from factory.runtime.provider_registry import ProviderRegistry


class MockProvider(Provider):
    name: ClassVar[str] = "mock"
    config_fields: ClassVar[list] = []
    call_log: ClassVar[list] = []

    async def execute(
        self, action: str, payload: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        MockProvider.call_log.append({"action": action, "payload": payload})
        return {"status": "executed", "action": action}


class FailingProvider(Provider):
    name: ClassVar[str] = "failing"
    config_fields: ClassVar[list] = []

    async def execute(
        self, action: str, payload: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        raise RuntimeError("Provider execution failed")


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def mock_dispatcher():
    registry = ProviderRegistry()
    registry.register(MockProvider())
    return Dispatcher(
        definitions=[
            DispatcherDefinition(
                action_type="publish_piece", provider="mock", provider_action="publish"
            ),
        ],
        provider_registry=registry,
    )


@pytest.fixture
def failing_dispatcher():
    registry = ProviderRegistry()
    registry.register(FailingProvider())
    return Dispatcher(
        definitions=[
            DispatcherDefinition(
                action_type="dangerous_action", provider="failing", provider_action="do"
            ),
        ],
        provider_registry=registry,
    )


class TestApprovalService:
    async def test_create_approval(self, async_session):
        service = ApprovalService(async_session)
        approval = await service.create("crm", "send_email", {"to": "test@test.com"})
        await async_session.commit()
        assert approval.status == "pending"
        assert approval.workflow_slug == "crm"
        assert approval.action_type == "send_email"

    async def test_approve_without_dispatcher(self, async_session):
        service = ApprovalService(async_session)
        approval = await service.create("crm", "send_email", {"to": "test@test.com"})
        await async_session.commit()

        result = await service.approve(approval.id)
        await async_session.commit()
        assert result.status == "approved"
        assert result.resolved_by == "human"
        assert result.resolved_at is not None

    async def test_approve_with_dispatcher_executes(self, async_session, mock_dispatcher):
        MockProvider.call_log = []
        service = ApprovalService(async_session, dispatcher=mock_dispatcher)
        approval = await service.create("crm", "publish_piece", {"content": "hello"})
        await async_session.commit()

        result = await service.approve(approval.id)
        await async_session.commit()
        assert result.status == "executed"
        assert result.executed_at is not None
        assert len(MockProvider.call_log) == 1

    async def test_approve_dispatcher_failure(self, async_session, failing_dispatcher):
        service = ApprovalService(async_session, dispatcher=failing_dispatcher)
        approval = await service.create("crm", "dangerous_action", {"data": "x"})
        await async_session.commit()

        result = await service.approve(approval.id)
        await async_session.commit()
        assert result.status == "failed"
        assert "Provider execution failed" in result.error

    async def test_reject(self, async_session):
        service = ApprovalService(async_session)
        approval = await service.create("crm", "send_email", {"to": "test@test.com"})
        await async_session.commit()

        result = await service.reject(approval.id)
        await async_session.commit()
        assert result.status == "rejected"
        assert result.resolved_by == "human"

    async def test_approve_already_approved_raises(self, async_session):
        service = ApprovalService(async_session)
        approval = await service.create("crm", "send_email", {"to": "test@test.com"})
        await async_session.commit()
        await service.approve(approval.id)
        await async_session.commit()

        with pytest.raises(ValueError, match="not pending"):
            await service.approve(approval.id)

    async def test_reject_already_rejected_raises(self, async_session):
        service = ApprovalService(async_session)
        approval = await service.create("crm", "send_email", {"to": "test@test.com"})
        await async_session.commit()
        await service.reject(approval.id)
        await async_session.commit()

        with pytest.raises(ValueError, match="not pending"):
            await service.reject(approval.id)

    async def test_approve_nonexistent_raises(self, async_session):
        service = ApprovalService(async_session)
        with pytest.raises(ValueError, match="not found"):
            await service.approve(uuid.uuid4())

    async def test_list_pending(self, async_session):
        service = ApprovalService(async_session)
        await service.create("crm", "email", {"to": "a@a.com"})
        await service.create("crm", "email", {"to": "b@b.com"})
        await service.create("content", "publish", {"id": "123"})
        await async_session.commit()

        all_pending = await service.list_pending()
        assert len(all_pending) == 3

        crm_pending = await service.list_pending("crm")
        assert len(crm_pending) == 2

    async def test_list_pending_excludes_resolved(self, async_session):
        service = ApprovalService(async_session)
        a1 = await service.create("crm", "email", {"to": "a@a.com"})
        await service.create("crm", "email", {"to": "b@b.com"})
        await async_session.commit()

        await service.approve(a1.id)
        await async_session.commit()

        pending = await service.list_pending("crm")
        assert len(pending) == 1

    async def test_pending_count(self, async_session):
        service = ApprovalService(async_session)
        await service.create("crm", "email", {"to": "a@a.com"})
        await service.create("crm", "email", {"to": "b@b.com"})
        await async_session.commit()

        count = await service.pending_count("crm")
        assert count == 2

    async def test_get_approval(self, async_session):
        service = ApprovalService(async_session)
        approval = await service.create("crm", "email", {"to": "a@a.com"})
        await async_session.commit()

        result = await service.get(approval.id)
        assert result is not None
        assert result.action_type == "email"

    async def test_get_nonexistent(self, async_session):
        service = ApprovalService(async_session)
        result = await service.get(uuid.uuid4())
        assert result is None

    async def test_related_entity_id(self, async_session):
        entity_id = uuid.uuid4()
        service = ApprovalService(async_session)
        approval = await service.create(
            "crm",
            "publish",
            {"id": str(entity_id)},
            related_entity_id=entity_id,
        )
        await async_session.commit()
        assert approval.related_entity_id == entity_id


class TestPipelineApprovalIntegration:
    """T15: Integration test -- Pipeline transition triggers approval, approval triggers dispatcher."""

    async def test_full_hitl_flow(self, async_session, mock_dispatcher):
        """
        1. Pipeline says transition requires approval
        2. Create approval
        3. Human approves
        4. Dispatcher executes via provider
        """
        from factory.primitives import PipelineDefinition, Transition
        from factory.runtime.pipeline_engine import PipelineEngine

        MockProvider.call_log = []

        # Setup pipeline with approval gate
        pipeline = PipelineDefinition(
            entity_name="piece",
            statuses=["draft", "review", "published"],
            transitions=[
                Transition("draft", "review"),
                Transition(
                    "review",
                    "published",
                    approval_required=True,
                    approval_action_type="publish_piece",
                ),
            ],
        )
        engine = PipelineEngine([pipeline])

        # Step 1: Validate transition draft -> review (no approval needed)
        result = engine.validate_transition("piece", "draft", "review")
        assert result.allowed is True
        assert result.approval_required is False

        # Step 2: Validate transition review -> published (approval needed)
        result = engine.validate_transition("piece", "review", "published")
        assert result.allowed is True
        assert result.approval_required is True
        assert result.approval_action_type == "publish_piece"

        # Step 3: Create approval
        approval_service = ApprovalService(async_session, dispatcher=mock_dispatcher)
        approval = await approval_service.create(
            workflow_slug="content",
            action_type=result.approval_action_type,
            payload={"piece_id": "some-uuid", "platform": "instagram"},
            requested_by="agent",
        )
        await async_session.commit()
        assert approval.status == "pending"

        # Step 4: Human approves -> dispatcher executes
        approved = await approval_service.approve(approval.id, resolved_by="darien")
        await async_session.commit()
        assert approved.status == "executed"
        assert approved.resolved_by == "darien"
        assert len(MockProvider.call_log) == 1
        assert MockProvider.call_log[0]["action"] == "publish"
