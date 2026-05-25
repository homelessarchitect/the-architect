from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from factory.modules.executions.models import ExecutionStep, WorkflowExecution


class ExecutionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_execution(
        self, workflow_slug: str, trigger_type: str = "manual"
    ) -> WorkflowExecution:
        execution = WorkflowExecution(
            workflow_slug=workflow_slug,
            trigger_type=trigger_type,
            status="running",
            token_usage={"total": 0, "by_tool": {}},
        )
        self._session.add(execution)
        await self._session.flush()
        await self._session.refresh(execution)
        return execution

    async def log_step(
        self,
        execution_id: uuid.UUID,
        tool_name: str,
        step_type: str,
        input_data: dict | None,
        output_data: dict | None,
        tokens_used: int = 0,
        duration_ms: int | None = None,
        status: str = "success",
        error: str | None = None,
    ) -> ExecutionStep:
        step = ExecutionStep(
            execution_id=execution_id,
            tool_name=tool_name,
            step_type=step_type,
            input_data=input_data,
            output_data=output_data,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            status=status,
            error=error,
        )
        self._session.add(step)
        await self._session.flush()

        # Update token usage on the execution
        execution = await self._session.get(WorkflowExecution, execution_id)
        if execution and tokens_used > 0:
            usage = dict(execution.token_usage)
            usage["total"] = usage.get("total", 0) + tokens_used
            by_tool = dict(usage.get("by_tool", {}))
            by_tool[tool_name] = by_tool.get(tool_name, 0) + tokens_used
            usage["by_tool"] = by_tool
            execution.token_usage = usage
            await self._session.flush()

        await self._session.refresh(step)
        return step

    async def complete_execution(
        self, execution_id: uuid.UUID, status: str = "completed", error: str | None = None
    ) -> WorkflowExecution | None:
        execution = await self._session.get(WorkflowExecution, execution_id)
        if execution is None:
            return None
        execution.status = status
        execution.completed_at = datetime.now(UTC)
        if error:
            execution.error = error
        await self._session.flush()
        await self._session.refresh(execution)
        return execution

    async def get_execution(self, execution_id: uuid.UUID) -> WorkflowExecution | None:
        return await self._session.get(WorkflowExecution, execution_id)

    async def get_steps(self, execution_id: uuid.UUID) -> list[ExecutionStep]:
        stmt = (
            select(ExecutionStep)
            .where(ExecutionStep.execution_id == execution_id)
            .order_by(ExecutionStep.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
