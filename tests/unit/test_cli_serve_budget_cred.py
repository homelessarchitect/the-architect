from click.testing import CliRunner

from architect.cli.main import cli


class TestServeCommand:
    def test_serve_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["serve", "--help"])
        assert result.exit_code == 0
        assert "host" in result.output.lower()
        assert "port" in result.output.lower()


class TestBudgetCommand:
    def test_budget_group_exists(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "--help"])
        assert result.exit_code == 0
        assert "set" in result.output
        assert "show" in result.output
        assert "reset" in result.output

    def test_budget_set_requires_at_least_one(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "set", "crm"])
        assert result.exit_code != 0

    def test_budget_reset_requires_period(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["budget", "reset", "crm"])
        assert result.exit_code != 0


class TestCredentialCommand:
    def test_credential_group_exists(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["credential", "--help"])
        assert result.exit_code == 0
        assert "add" in result.output
        assert "list" in result.output
        assert "remove" in result.output

    def test_credential_add_requires_name(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["credential", "add", "--provider", "ig"])
        assert result.exit_code != 0

    def test_credential_add_requires_provider(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["credential", "add", "--name", "tok"])
        assert result.exit_code != 0
