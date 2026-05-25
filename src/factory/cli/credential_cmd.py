from __future__ import annotations

import asyncio

import click

from factory.core.database import Base, dispose_engine, get_engine, get_session_factory


async def _add_credential(
    name: str, provider: str, scope_workflow: str | None, scope_agent: str | None
) -> None:
    from factory.modules.credentials.service import CredentialStore

    value = click.prompt("Enter credential value", hide_input=True)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        store = CredentialStore(session)
        await store.add(name, provider, value, scope_workflow, scope_agent)
        await session.commit()

    scope_desc = "global"
    if scope_workflow:
        scope_desc = f"workflow:{scope_workflow}"
    if scope_agent:
        scope_desc += f", agent:{scope_agent}"

    click.echo(f"Credential '{name}' added (provider: {provider}, scope: {scope_desc}).")
    await dispose_engine()


async def _list_credentials() -> None:
    from factory.modules.credentials.service import CredentialStore

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        store = CredentialStore(session)
        creds = await store.list_all()

    if not creds:
        click.echo("No credentials stored.")
        await dispose_engine()
        return

    click.echo(f"\n{'Name':<25} {'Provider':<15} {'Scope':<30}")
    click.echo("-" * 70)
    for c in creds:
        scope = "global"
        if c["scope_workflow"]:
            scope = f"workflow:{c['scope_workflow']}"
        if c["scope_agent"]:
            scope += f", agent:{c['scope_agent']}"
        click.echo(f"{c['name']:<25} {c['provider']:<15} {scope:<30}")

    click.echo("")
    await dispose_engine()


async def _remove_credential(name: str) -> None:
    from factory.modules.credentials.service import CredentialStore

    get_engine()  # ensure engine is initialized
    factory = get_session_factory()
    async with factory() as session:
        store = CredentialStore(session)
        result = await store.remove(name)
        await session.commit()

    if result:
        click.echo(f"Credential '{name}' removed.")
    else:
        click.echo(f"Error: Credential '{name}' not found.", err=True)
        raise SystemExit(1)
    await dispose_engine()


@click.group("credential")
def credential_cmd() -> None:
    """Manage encrypted credentials for providers."""


@credential_cmd.command("add")
@click.option("--name", "-n", required=True, help="Credential name")
@click.option("--provider", "-p", required=True, help="Provider name (e.g., instagram, resend)")
@click.option("--scope-workflow", help="Scope to a specific workflow slug")
@click.option("--scope-agent", help="Scope to a specific agent name")
def credential_add(
    name: str, provider: str, scope_workflow: str | None, scope_agent: str | None
) -> None:
    """Add a new encrypted credential."""
    asyncio.run(_add_credential(name, provider, scope_workflow, scope_agent))


@credential_cmd.command("list")
def credential_list() -> None:
    """List all stored credentials (values are never shown)."""
    asyncio.run(_list_credentials())


@credential_cmd.command("remove")
@click.option("--name", "-n", required=True, help="Name of the credential to remove")
def credential_remove(name: str) -> None:
    """Remove a stored credential."""
    asyncio.run(_remove_credential(name))
