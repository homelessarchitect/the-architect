import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from factory.core.database import Base
from factory.modules.budgets.service import (
    BudgetExceededError,
    BudgetTracker,
    CircuitBreakerError,
)


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


class TestBudgetTracker:
    async def test_set_budget(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        budget = await tracker.set_budget("crm", "daily", max_tokens=10000)
        await async_session.commit()

        assert budget.id is not None
        assert budget.workflow_slug == "crm"
        assert budget.period == "daily"
        assert budget.max_tokens == 10000
        assert budget.current_usage == 0

    async def test_set_budget_update_existing(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        await tracker.set_budget("crm", "daily", max_tokens=10000)
        await async_session.commit()

        updated = await tracker.set_budget("crm", "daily", max_tokens=20000)
        await async_session.commit()

        assert updated.max_tokens == 20000

        budgets = await tracker.get_budgets("crm")
        assert len(budgets) == 1

    async def test_check_within_budget(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        await tracker.set_budget("crm", "daily", max_tokens=10000)
        await async_session.commit()

        # Should not raise
        await tracker.check("crm", estimated_tokens=5000)

    async def test_check_exceeds_budget(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        await tracker.set_budget("crm", "daily", max_tokens=1000)
        await async_session.commit()

        with pytest.raises(BudgetExceededError) as exc_info:
            await tracker.check("crm", estimated_tokens=1500)

        assert exc_info.value.workflow_slug == "crm"
        assert exc_info.value.period == "daily"
        assert exc_info.value.max_tokens == 1000
        assert exc_info.value.requested == 1500

    async def test_track_updates_usage(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        await tracker.set_budget("crm", "daily", max_tokens=10000)
        await async_session.commit()

        await tracker.track("crm", tokens_used=500)
        await async_session.commit()

        budgets = await tracker.get_budgets("crm")
        assert len(budgets) == 1
        assert budgets[0].current_usage == 500

    async def test_track_accumulates(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        await tracker.set_budget("crm", "daily", max_tokens=10000)
        await async_session.commit()

        await tracker.track("crm", tokens_used=300)
        await async_session.commit()
        await tracker.track("crm", tokens_used=700)
        await async_session.commit()

        budgets = await tracker.get_budgets("crm")
        assert budgets[0].current_usage == 1000

    async def test_reset_budget(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        await tracker.set_budget("crm", "daily", max_tokens=10000)
        await async_session.commit()

        await tracker.track("crm", tokens_used=5000)
        await async_session.commit()

        result = await tracker.reset("crm", "daily")
        await async_session.commit()
        assert result is True

        budgets = await tracker.get_budgets("crm")
        assert budgets[0].current_usage == 0

    async def test_reset_nonexistent(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        result = await tracker.reset("ghost", "daily")
        assert result is False

    async def test_circuit_breaker_triggers(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)

        tracker.record_failure("crm")
        tracker.record_failure("crm")
        tracker.record_failure("crm")

        with pytest.raises(CircuitBreakerError) as exc_info:
            await tracker.check("crm")

        assert exc_info.value.workflow_slug == "crm"
        assert exc_info.value.consecutive_failures == 3

    async def test_circuit_breaker_resets_on_success(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)

        tracker.record_failure("crm")
        tracker.record_failure("crm")
        tracker.record_success("crm")
        tracker.record_failure("crm")

        # Should not raise -- only 1 consecutive failure after the success
        await tracker.check("crm")

    async def test_get_budgets(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)
        await tracker.set_budget("crm", "daily", max_tokens=10000)
        await async_session.commit()
        await tracker.set_budget("crm", "monthly", max_tokens=100000)
        await async_session.commit()

        budgets = await tracker.get_budgets("crm")
        assert len(budgets) == 2
        periods = {b.period for b in budgets}
        assert periods == {"daily", "monthly"}

    async def test_check_no_budgets_passes(self, async_session: AsyncSession):
        tracker = BudgetTracker(async_session)

        # No budgets set = no restrictions, should not raise
        await tracker.check("crm", estimated_tokens=999999)
