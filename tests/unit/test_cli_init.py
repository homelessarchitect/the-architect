from click.testing import CliRunner

from factory.cli.main import cli


class TestInitCommand:
    def test_creates_directory(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "my-crm", "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "my-crm").is_dir()

    def test_creates_workflow_file(self, tmp_path):
        runner = CliRunner()
        runner.invoke(cli, ["init", "my-crm", "-o", str(tmp_path)])
        wf = tmp_path / "my-crm" / "workflow.py"
        assert wf.exists()
        content = wf.read_text()
        assert "WorkflowDefinition" in content
        assert 'slug="my-crm"' in content

    def test_creates_subdirectories(self, tmp_path):
        runner = CliRunner()
        runner.invoke(cli, ["init", "my-crm", "-o", str(tmp_path)])
        assert (tmp_path / "my-crm" / "custom_tools").is_dir()
        assert (tmp_path / "my-crm" / "dispatchers").is_dir()

    def test_workflow_is_valid_python(self, tmp_path):
        runner = CliRunner()
        runner.invoke(cli, ["init", "my-crm", "-o", str(tmp_path)])
        content = (tmp_path / "my-crm" / "workflow.py").read_text()
        compile(content, "workflow.py", "exec")

    def test_fails_if_directory_exists(self, tmp_path):
        (tmp_path / "my-crm").mkdir()
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "my-crm", "-o", str(tmp_path)])
        assert result.exit_code != 0
        assert "already exists" in result.output

    def test_converts_underscores_to_hyphens(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "my_crm", "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "my-crm").is_dir()

    def test_output_shows_next_steps(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "test-wf", "-o", str(tmp_path)])
        assert "factory plan" in result.output
