import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from architect.core.database import Base
from architect.modules.executions.service import ExecutionService


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class TestExecutionHistory:
    async def test_start_execution(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        execution = await service.start_execution("crm", trigger_type="manual")
        await async_session.commit()

        assert execution.id is not None
        assert execution.workflow_slug == "crm"
        assert execution.trigger_type == "manual"
        assert execution.status == "running"
        assert execution.started_at is not None
        assert execution.completed_at is None
        assert execution.token_usage == {"total": 0, "by_tool": {}}

    async def test_log_step(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        execution = await service.start_execution("crm")
        await async_session.commit()

        step = await service.log_step(
            execution_id=execution.id,
            tool_name="search_leads",
            step_type="tool_call",
            input_data={"query": "test"},
            output_data={"results": []},
            tokens_used=100,
            duration_ms=50,
            status="success",
        )
        await async_session.commit()

        assert step.id is not None
        assert step.execution_id == execution.id
        assert step.tool_name == "search_leads"
        assert step.step_type == "tool_call"
        assert step.input_data == {"query": "test"}
        assert step.output_data == {"results": []}
        assert step.tokens_used == 100
        assert step.duration_ms == 50
        assert step.status == "success"
        assert step.error is None

    async def test_log_step_updates_token_usage(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        execution = await service.start_execution("crm")
        await async_session.commit()

        await service.log_step(
            execution_id=execution.id,
            tool_name="search_leads",
            step_type="tool_call",
            input_data=None,
            output_data=None,
            tokens_used=150,
        )
        await async_session.commit()

        updated = await service.get_execution(execution.id)
        assert updated is not None
        assert updated.token_usage["total"] == 150
        assert updated.token_usage["by_tool"]["search_leads"] == 150

    async def test_multiple_steps_accumulate_tokens(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        execution = await service.start_execution("crm")
        await async_session.commit()

        await service.log_step(
            execution_id=execution.id,
            tool_name="search_leads",
            step_type="tool_call",
            input_data=None,
            output_data=None,
            tokens_used=100,
        )
        await async_session.commit()

        await service.log_step(
            execution_id=execution.id,
            tool_name="create_lead",
            step_type="tool_call",
            input_data=None,
            output_data=None,
            tokens_used=200,
        )
        await async_session.commit()

        await service.log_step(
            execution_id=execution.id,
            tool_name="search_leads",
            step_type="tool_call",
            input_data=None,
            output_data=None,
            tokens_used=50,
        )
        await async_session.commit()

        updated = await service.get_execution(execution.id)
        assert updated is not None
        assert updated.token_usage["total"] == 350
        assert updated.token_usage["by_tool"]["search_leads"] == 150
        assert updated.token_usage["by_tool"]["create_lead"] == 200

    async def test_complete_execution_success(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        execution = await service.start_execution("crm")
        await async_session.commit()

        completed = await service.complete_execution(execution.id, status="completed")
        await async_session.commit()

        assert completed is not None
        assert completed.status == "completed"
        assert completed.completed_at is not None
        assert completed.error is None

    async def test_complete_execution_failed(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        execution = await service.start_execution("crm")
        await async_session.commit()

        completed = await service.complete_execution(
            execution.id, status="failed", error="Something broke"
        )
        await async_session.commit()

        assert completed is not None
        assert completed.status == "failed"
        assert completed.completed_at is not None
        assert completed.error == "Something broke"

    async def test_get_steps_ordered(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        execution = await service.start_execution("crm")
        await async_session.commit()

        await service.log_step(
            execution_id=execution.id,
            tool_name="step_a",
            step_type="tool_call",
            input_data=None,
            output_data=None,
            status="success",
        )
        await async_session.commit()

        await service.log_step(
            execution_id=execution.id,
            tool_name="step_b",
            step_type="tool_call",
            input_data=None,
            output_data=None,
            status="success",
        )
        await async_session.commit()

        await service.log_step(
            execution_id=execution.id,
            tool_name="step_c",
            step_type="tool_call",
            input_data=None,
            output_data=None,
            status="success",
        )
        await async_session.commit()

        steps = await service.get_steps(execution.id)
        assert len(steps) == 3
        assert steps[0].tool_name == "step_a"
        assert steps[1].tool_name == "step_b"
        assert steps[2].tool_name == "step_c"

    async def test_get_execution_not_found(self, async_session: AsyncSession):
        service = ExecutionService(async_session)
        result = await service.get_execution(uuid.uuid4())
        assert result is None
