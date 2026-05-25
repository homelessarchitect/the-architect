from __future__ import annotations

import asyncio

import click

from architect.core.database import Base, dispose_engine, get_engine, get_session_factory


async def _create_key(name: str) -> None:
    from architect.modules.api_keys.service import ApiKeyService

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        service = ApiKeyService(session)
        api_key, plaintext = await service.create_key(name)
        await session.commit()

    click.echo(f"API key created: {api_key.name}")
    click.echo(f"  Prefix:  {api_key.prefix}")
    click.echo(f"  Key:     {plaintext}")
    click.echo("")
    click.echo("Save this key — it cannot be recovered.")
    await dispose_engine()


async def _list_keys() -> None:
    from architect.modules.api_keys.service import ApiKeyService

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        service = ApiKeyService(session)
        keys = await service.list_keys()

    if not keys:
        click.echo("No API keys found.")
    else:
        click.echo(f"{'Name':<20} {'Prefix':<12} {'Created':<20} {'Last Used':<20}")
        click.echo("-" * 72)
        for k in keys:
            created = k.created_at.strftime("%Y-%m-%d %H:%M") if k.created_at else "—"
            used = k.last_used_at.strftime("%Y-%m-%d %H:%M") if k.last_used_at else "never"
            click.echo(f"{k.name:<20} {k.prefix:<12} {created:<20} {used:<20}")

    await dispose_engine()


async def _revoke_key(name: str) -> None:
    from sqlalchemy import select

    from architect.modules.api_keys.models import ApiKey
    from architect.modules.api_keys.service import ApiKeyService

    get_engine()  # ensure engine is initialized
    factory = get_session_factory()
    async with factory() as session:
        service = ApiKeyService(session)
        stmt = select(ApiKey).where(ApiKey.name == name, ApiKey.revoked_at.is_(None))
        result = await session.execute(stmt)
        api_key = result.scalar_one_or_none()
        if api_key is None:
            click.echo(f"Error: API key '{name}' not found or already revoked.", err=True)
            raise SystemExit(1)
        await service.revoke_key(api_key.id)
        await session.commit()
    click.echo(f"API key '{name}' revoked.")
    await dispose_engine()


@click.group("apikey")
def apikey_cmd() -> None:
    """Manage API keys for MCP authentication."""


@apikey_cmd.command("create")
@click.option("--name", "-n", required=True, help="Name for the API key")
def apikey_create(name: str) -> None:
    """Create a new API key."""
    asyncio.run(_create_key(name))


@apikey_cmd.command("list")
def apikey_list() -> None:
    """List all active API keys."""
    asyncio.run(_list_keys())


@apikey_cmd.command("revoke")
@click.option("--name", "-n", required=True, help="Name of the API key to revoke")
def apikey_revoke(name: str) -> None:
    """Revoke an API key."""
    asyncio.run(_revoke_key(name))
