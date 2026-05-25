import click

from architect.cli.apikey_cmd import apikey_cmd
from architect.cli.apply_cmd import apply_cmd
from architect.cli.budget_cmd import budget_cmd
from architect.cli.credential_cmd import credential_cmd
from architect.cli.destroy_cmd import destroy_cmd
from architect.cli.init_cmd import init_cmd
from architect.cli.plan_cmd import plan_cmd
from architect.cli.serve_cmd import serve_cmd
from architect.cli.state_cmd import state_cmd


@click.group()
@click.version_option(package_name="the-architect")
def cli() -> None:
    """The Architect — Infrastructure for declarative MCP agent workflows."""


cli.add_command(init_cmd)
cli.add_command(apikey_cmd)
cli.add_command(plan_cmd)
cli.add_command(apply_cmd)
cli.add_command(state_cmd)
cli.add_command(destroy_cmd)
cli.add_command(serve_cmd)
cli.add_command(budget_cmd)
cli.add_command(credential_cmd)


if __name__ == "__main__":
    cli()
