import click

from factory.cli.apikey_cmd import apikey_cmd
from factory.cli.apply_cmd import apply_cmd
from factory.cli.budget_cmd import budget_cmd
from factory.cli.credential_cmd import credential_cmd
from factory.cli.destroy_cmd import destroy_cmd
from factory.cli.init_cmd import init_cmd
from factory.cli.plan_cmd import plan_cmd
from factory.cli.serve_cmd import serve_cmd
from factory.cli.state_cmd import state_cmd


@click.group()
@click.version_option(package_name="the-architect")
def cli() -> None:
    """The Factory — Infrastructure for declarative MCP agent workflows."""


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
