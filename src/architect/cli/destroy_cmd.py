"""architect destroy — remove generated code for a workflow and update state."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import click

from architect.core.database import Base, dispose_engine, get_engine, get_session_factory
from architect.modules.state.service import StateService


@click.command("destroy")
@click.argument("slug")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
def destroy_cmd(slug: str, force: bool) -> None:
    """Remove generated code for a workflow and update state."""
    asyncio.run(_destroy(slug, force))


async def _destroy(slug: str, force: bool) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        service = StateService(session)
        latest = await service.get_latest(slug)

        if latest is None:
            click.echo(f"Error: No workflow '{slug}' found in state.", err=True)
            raise SystemExit(1)

        if not force:
            click.confirm(f"Destroy workflow '{slug}' (v{latest.version})?", abort=True)

        # Remove generated directory
        generated_dir = Path(__file__).parent.parent / "generated" / slug
        if generated_dir.exists():
            shutil.rmtree(generated_dir)
            click.echo(f"Removed generated code: {generated_dir}")
        else:
            click.echo(f"No generated code found at {generated_dir}")

        # Show SQL for table drops (safety -- we don't drop tables automatically)
        tables = latest.tables_list if isinstance(latest.tables_list, list) else []
        if tables:
            click.echo("\nTo drop the database tables, run manually:")
            for table in tables:
                click.echo(f"  DROP TABLE IF EXISTS {table} CASCADE;")

        click.echo(f"\nWorkflow '{slug}' destroyed.")

    await dispose_engine()
