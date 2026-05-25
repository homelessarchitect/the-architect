from click.testing import CliRunner

from factory.cli.main import cli


class TestApiKeyCommand:
    def test_apikey_group_exists(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["apikey", "--help"])
        assert result.exit_code == 0
        assert "create" in result.output
        assert "list" in result.output
        assert "revoke" in result.output

    def test_apikey_create_requires_name(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["apikey", "create"])
        assert result.exit_code != 0
        assert "name" in result.output.lower() or "required" in result.output.lower()
