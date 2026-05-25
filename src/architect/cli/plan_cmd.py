"""architect plan — preview changes without modifying anything."""

from __future__ import annotations

import asyncio

import click

from architect.cli.loader import load_workflow_from_file
from architect.core.database import Base, dispose_engine, get_engine, get_session_factory
from architect.modules.state.service import StateService


@click.command("plan")
@click.argument("workflow_path", type=click.Path(exists=True))
def plan_cmd(workflow_path: str) -> None:
    """Show what will change without modifying anything."""
    asyncio.run(_plan(workflow_path))


async def _plan(workflow_path: str) -> None:
    workflow = load_workflow_from_file(workflow_path)
    current_hash = StateService.compute_hash(workflow_path)
    entity_names = [e.name for e in workflow.entities]

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        service = StateService(session)
        diff = await service.diff_state(workflow.slug, current_hash, entity_names)

    click.echo(f'\nThe Architect -- Plan for "{workflow.name}" (slug: {workflow.slug})\n')

    if diff["status"] == "new":
        click.echo(f"  + CREATE  {len(entity_names)} entities ({', '.join(entity_names)})")
        tools_count = len(entity_names) * 5  # 5 CRUD tools per entity
        click.echo(f"  + CREATE  {tools_count} CRUD tools")
        click.echo(f"\n  Plan: {len(entity_names)} entities, {tools_count} tools to create.")
    elif diff["status"] == "no_changes":
        click.echo("  No changes detected.\n")
    elif diff["status"] == "modified":
        click.echo(f"  {diff['message']}")
        for e in diff.get("entities_to_create", []):
            click.echo(f"  + ADD     entity '{e}'")
        for e in diff.get("entities_to_remove", []):
            click.echo(f"  - REMOVE  entity '{e}'")

    click.echo(f"\n  Run `architect apply {workflow_path}` to execute.\n")
    await dispose_engine()
