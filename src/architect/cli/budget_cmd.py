from __future__ import annotations

import asyncio

import click

from architect.core.database import Base, dispose_engine, get_engine, get_session_factory


async def _set_budget(
    workflow_slug: str, daily: int | None, monthly: int | None, execution: int | None
) -> None:
    from architect.modules.budgets.service import BudgetTracker

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        tracker = BudgetTracker(session)
        if daily is not None:
            await tracker.set_budget(workflow_slug, "daily", daily)
            click.echo(f"  Daily budget:     {daily:,} tokens")
        if monthly is not None:
            await tracker.set_budget(workflow_slug, "monthly", monthly)
            click.echo(f"  Monthly budget:   {monthly:,} tokens")
        if execution is not None:
            await tracker.set_budget(workflow_slug, "execution", execution)
            click.echo(f"  Per-execution:    {execution:,} tokens")
        await session.commit()

    click.echo(f"\nBudgets updated for '{workflow_slug}'.")
    await dispose_engine()


async def _show_budget(workflow_slug: str) -> None:
    from architect.modules.budgets.service import BudgetTracker

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        tracker = BudgetTracker(session)
        budgets = await tracker.get_budgets(workflow_slug)

    if not budgets:
        click.echo(f"No budgets set for '{workflow_slug}'.")
        await dispose_engine()
        return

    click.echo(f"\nBudgets for '{workflow_slug}':\n")
    click.echo(f"{'Period':<15} {'Max Tokens':<15} {'Used':<15} {'Remaining':<15}")
    click.echo("-" * 60)
    for b in budgets:
        remaining = b.max_tokens - b.current_usage
        click.echo(f"{b.period:<15} {b.max_tokens:<15,} {b.current_usage:<15,} {remaining:<15,}")

    click.echo("")
    await dispose_engine()


async def _reset_budget(workflow_slug: str, period: str) -> None:
    from architect.modules.budgets.service import BudgetTracker

    get_engine()  # ensure engine is initialized
    factory = get_session_factory()
    async with factory() as session:
        tracker = BudgetTracker(session)
        result = await tracker.reset(workflow_slug, period)
        await session.commit()

    if result:
        click.echo(f"Budget '{period}' reset for '{workflow_slug}'.")
    else:
        click.echo(f"Error: No '{period}' budget found for '{workflow_slug}'.", err=True)
        raise SystemExit(1)
    await dispose_engine()


@click.group("budget")
def budget_cmd() -> None:
    """Manage token budgets for workflows."""


@budget_cmd.command("set")
@click.argument("workflow_slug")
@click.option("--daily", type=int, help="Daily token budget")
@click.option("--monthly", type=int, help="Monthly token budget")
@click.option("--execution", type=int, help="Per-execution token budget")
def budget_set(
    workflow_slug: str, daily: int | None, monthly: int | None, execution: int | None
) -> None:
    """Set token budgets for a workflow."""
    if daily is None and monthly is None and execution is None:
        click.echo("Error: Specify at least one of --daily, --monthly, or --execution.", err=True)
        raise SystemExit(1)
    asyncio.run(_set_budget(workflow_slug, daily, monthly, execution))


@budget_cmd.command("show")
@click.argument("workflow_slug")
def budget_show(workflow_slug: str) -> None:
    """Show token budgets for a workflow."""
    asyncio.run(_show_budget(workflow_slug))


@budget_cmd.command("reset")
@click.argument("workflow_slug")
@click.option(
    "--period", "-p", required=True, type=click.Choice(["daily", "monthly", "execution"])
)
def budget_reset(workflow_slug: str, period: str) -> None:
    """Reset token usage for a budget period."""
    asyncio.run(_reset_budget(workflow_slug, period))
