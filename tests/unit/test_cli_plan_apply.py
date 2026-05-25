import pytest
from pathlib import Path

from click.testing import CliRunner

from factory.cli.main import cli


@pytest.fixture
def workflow_file(tmp_path) -> Path:
    wf = tmp_path / "workflow.py"
    wf.write_text(
        '''
from factory.primitives import EntityDefinition, FieldDef, ToolDefinition, WorkflowDefinition

item = EntityDefinition(
    name="item",
    fields=[FieldDef("name", str, required=True, max_length=255)],
)

workflow = WorkflowDefinition(
    name="Test",
    slug="test",
    entities=[item],
    tools=[ToolDefinition.crud("item")],
)
'''
    )
    return wf


class TestCLILoader:
    def test_load_workflow_from_file(self, workflow_file):
        from factory.cli.loader import load_workflow_from_file

        wf = load_workflow_from_file(workflow_file)
        assert wf.name == "Test"
        assert wf.slug == "test"
        assert len(wf.entities) == 1

    def test_load_nonexistent_file(self, tmp_path):
        from factory.cli.loader import load_workflow_from_file

        with pytest.raises(FileNotFoundError):
            load_workflow_from_file(tmp_path / "nope.py")

    def test_load_file_without_workflow(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("x = 42")
        from factory.cli.loader import load_workflow_from_file

        with pytest.raises(RuntimeError, match="No WorkflowDefinition"):
            load_workflow_from_file(f)


class TestPlanCommand:
    def test_plan_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", "--help"])
        assert result.exit_code == 0
        assert "Show what will change" in result.output


class TestApplyCommand:
    def test_apply_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["apply", "--help"])
        assert result.exit_code == 0


class TestStateCommand:
    def test_state_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["state", "--help"])
        assert result.exit_code == 0


class TestDestroyCommand:
    def test_destroy_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["destroy", "--help"])
        assert result.exit_code == 0
        assert "force" in result.output.lower()
