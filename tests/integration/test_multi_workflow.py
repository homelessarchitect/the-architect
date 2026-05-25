from enum import StrEnum

import pytest

from architect.generators.orchestrator import generate_workflow
from architect.primitives import (
    EntityDefinition,
    FieldDef,
    ToolDefinition,
    WorkflowDefinition,
)


class Status(StrEnum):
    ACTIVE = "active"
    DONE = "done"


@pytest.fixture
def crm_workflow() -> WorkflowDefinition:
    lead = EntityDefinition(
        name="contact",
        fields=[
            FieldDef("name", str, required=True, max_length=255),
            FieldDef("email", str, email=True, required=False, nullable=True),
            FieldDef("status", Status, default=Status.ACTIVE),
        ],
    )
    return WorkflowDefinition(
        name="CRM",
        slug="crm",
        entities=[lead],
        tools=[ToolDefinition.crud("contact")],
    )


@pytest.fixture
def content_workflow() -> WorkflowDefinition:
    piece = EntityDefinition(
        name="contact",  # SAME entity name as CRM -- tests isolation
        fields=[
            FieldDef("title", str, required=True, max_length=255),
            FieldDef("body", str, nullable=True, required=False),
            FieldDef("status", Status, default=Status.ACTIVE),
        ],
    )
    return WorkflowDefinition(
        name="Content",
        slug="content",
        entities=[piece],
        tools=[ToolDefinition.crud("contact")],
    )


class TestMultiWorkflowIsolation:
    def test_separate_directories(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        assert (tmp_path / "crm" / "contact" / "models.py").exists()
        assert (tmp_path / "content" / "contact" / "models.py").exists()

    def test_different_table_names(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        crm_models = (tmp_path / "crm" / "contact" / "models.py").read_text()
        content_models = (tmp_path / "content" / "contact" / "models.py").read_text()

        assert "crm_contacts" in crm_models
        assert "content_contacts" in content_models

    def test_different_tool_imports(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        crm_tools = (tmp_path / "crm" / "contact" / "tools.py").read_text()
        content_tools = (tmp_path / "content" / "contact" / "tools.py").read_text()

        assert "architect.generated.crm" in crm_tools
        assert "architect.generated.content" in content_tools

    def test_separate_registries(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        crm_registry = (tmp_path / "crm" / "_tools_registry.py").read_text()
        content_registry = (tmp_path / "content" / "_tools_registry.py").read_text()

        assert "crm.contact.tools" in crm_registry
        assert "content.contact.tools" in content_registry

    def test_both_generate_valid_python(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        for py_file in tmp_path.rglob("*.py"):
            content = py_file.read_text()
            compile(content, str(py_file), "exec")

    def test_schema_isolation(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        crm_schema = (tmp_path / "crm" / "contact" / "schemas.py").read_text()
        content_schema = (tmp_path / "content" / "contact" / "schemas.py").read_text()

        # CRM has email field, content has body field
        assert "email" in crm_schema
        assert "body" in content_schema

    def test_serialize_isolation(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        crm_ser = (tmp_path / "crm" / "contact" / "serialize.py").read_text()
        content_ser = (tmp_path / "content" / "contact" / "serialize.py").read_text()

        assert "email" in crm_ser
        assert "body" in content_ser

    def test_repo_isolation(self, crm_workflow, content_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(content_workflow, tmp_path)

        crm_repo = (tmp_path / "crm" / "contact" / "repository.py").read_text()
        content_repo = (tmp_path / "content" / "contact" / "repository.py").read_text()

        assert "architect.generated.crm" in crm_repo
        assert "architect.generated.content" in content_repo
