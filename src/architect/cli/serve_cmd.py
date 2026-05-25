from __future__ import annotations

import asyncio
import importlib

import click


def _load_applied_workflows() -> list[dict]:
    """Load all applied workflows from the state table."""
    import sys
    from pathlib import Path

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    from architect.core.database import get_session_factory, reset_engine
    from architect.modules.state.service import StateService

    async def _fetch():
        factory = get_session_factory()
        async with factory() as session:
            svc = StateService(session)
            states = await svc.list_all_latest()
            return states

    states = asyncio.run(_fetch())
    reset_engine()

    modules = []
    for state in states:
        slug = state.workflow_slug
        module_path = f"architect.generated.{slug}._tools_registry"
        try:
            # Import models so they're registered with Base.metadata for DB access
            entity_names = state.entities.get("names", []) if state.entities else []
            for entity_name in entity_names:
                try:
                    importlib.import_module(f"architect.generated.{slug}.{entity_name}.models")
                except ModuleNotFoundError:
                    pass

            mod = importlib.import_module(module_path)
            modules.append({"slug": slug, "register_fn": mod.register_all_tools})
            click.echo(f"  Loaded workflow: {slug} (v{state.version}, {state.tools_count} CRUD tools)")
        except ModuleNotFoundError:
            click.echo(f"  WARNING: Generated code for '{slug}' not found. Run `architect apply` first.")
    return modules


@click.command("serve")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8000, type=int, help="Port to bind to")
def serve_cmd(host: str, port: int) -> None:
    """Start the FastAPI server with all applied workflows."""
    import uvicorn

    click.echo(f"Starting The Architect on {host}:{port}...")
    click.echo("Loading workflows from state...")

    from architect.runtime.app import create_app

    workflow_modules = _load_applied_workflows()
    if not workflow_modules:
        click.echo("  No workflows found. Run `architect apply <workflow.py>` first.\n")

    app = create_app(workflow_modules)
    click.echo("")
    uvicorn.run(app, host=host, port=port)
