"""architect state — show current state of all deployed workflows."""

from __future__ import annotations

import asyncio

import click

from factory.core.database import Base, dispose_engine, get_engine, get_session_factory
from factory.modules.state.service import StateService


@click.command("state")
def state_cmd() -> None:
    """Show current state of all deployed workflows."""
    asyncio.run(_state())


async def _state() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        service = StateService(session)
        all_states = await service.list_all_latest()

    if not all_states:
        click.echo("No workflows applied yet.")
        await dispose_engine()
        return

    click.echo(
        f"\n{'Slug':<20} {'Version':<10} {'Entities':<10} {'Tools':<8} {'Applied':<20}"
    )
    click.echo("-" * 68)
    for s in all_states:
        entities_count = len(s.entities.get("names", []))
        applied = s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "--"
        click.echo(
            f"{s.workflow_slug:<20} {s.version:<10} {entities_count:<10} "
            f"{s.tools_count:<8} {applied:<20}"
        )

    click.echo("")
    await dispose_engine()
