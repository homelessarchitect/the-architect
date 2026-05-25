from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factory.modules.budgets.models import TokenBudget


class BudgetExceededError(Exception):
    def __init__(
        self,
        workflow_slug: str,
        period: str,
        max_tokens: int,
        current: int,
        requested: int,
    ):
        self.workflow_slug = workflow_slug
        self.period = period
        self.max_tokens = max_tokens
        self.current = current
        self.requested = requested
        super().__init__(
            f"Budget exceeded for '{workflow_slug}' ({period}): "
            f"{current + requested}/{max_tokens} tokens"
        )


class CircuitBreakerError(Exception):
    def __init__(self, workflow_slug: str, consecutive_failures: int):
        self.workflow_slug = workflow_slug
        self.consecutive_failures = consecutive_failures
        super().__init__(
            f"Circuit breaker triggered for '{workflow_slug}': "
            f"{consecutive_failures} consecutive failures"
        )


class BudgetTracker:
    CIRCUIT_BREAKER_THRESHOLD = 3

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._consecutive_failures: dict[str, int] = {}

    async def set_budget(
        self, workflow_slug: str, period: str, max_tokens: int
    ) -> TokenBudget:
        stmt = select(TokenBudget).where(
            TokenBudget.workflow_slug == workflow_slug,
            TokenBudget.period == period,
        )
        result = await self._session.execute(stmt)
        budget = result.scalar_one_or_none()

        if budget:
            budget.max_tokens = max_tokens
        else:
            budget = TokenBudget(
                workflow_slug=workflow_slug,
                period=period,
                max_tokens=max_tokens,
            )
            self._session.add(budget)

        await self._session.flush()
        await self._session.refresh(budget)
        return budget

    async def check(self, workflow_slug: str, estimated_tokens: int = 0) -> None:
        # Check circuit breaker
        failures = self._consecutive_failures.get(workflow_slug, 0)
        if failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            raise CircuitBreakerError(workflow_slug, failures)

        # Check all budgets for this workflow
        stmt = select(TokenBudget).where(TokenBudget.workflow_slug == workflow_slug)
        result = await self._session.execute(stmt)
        budgets = list(result.scalars().all())

        for budget in budgets:
            if budget.current_usage + estimated_tokens > budget.max_tokens:
                raise BudgetExceededError(
                    workflow_slug,
                    budget.period,
                    budget.max_tokens,
                    budget.current_usage,
                    estimated_tokens,
                )

    async def track(self, workflow_slug: str, tokens_used: int) -> None:
        stmt = select(TokenBudget).where(TokenBudget.workflow_slug == workflow_slug)
        result = await self._session.execute(stmt)
        budgets = list(result.scalars().all())

        for budget in budgets:
            budget.current_usage += tokens_used
        await self._session.flush()

    async def reset(self, workflow_slug: str, period: str) -> bool:
        stmt = select(TokenBudget).where(
            TokenBudget.workflow_slug == workflow_slug,
            TokenBudget.period == period,
        )
        result = await self._session.execute(stmt)
        budget = result.scalar_one_or_none()
        if budget is None:
            return False
        budget.current_usage = 0
        await self._session.flush()
        return True

    def record_failure(self, workflow_slug: str) -> None:
        self._consecutive_failures[workflow_slug] = (
            self._consecutive_failures.get(workflow_slug, 0) + 1
        )

    def record_success(self, workflow_slug: str) -> None:
        self._consecutive_failures[workflow_slug] = 0

    async def get_budgets(self, workflow_slug: str) -> list[TokenBudget]:
        stmt = select(TokenBudget).where(TokenBudget.workflow_slug == workflow_slug)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
