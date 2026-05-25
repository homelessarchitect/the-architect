"""Tests for the orchestrator generator (generate_workflow)."""

from __future__ import annotations

from enum import StrEnum

from uuid import UUID

import pytest

from factory.generators.orchestrator import generate_workflow
from factory.primitives import (
    EntityDefinition,
    FieldDef,
    ToolDefinition,
    WorkflowDefinition,
)


class LeadStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"


@pytest.fixture
def crm_workflow() -> WorkflowDefinition:
    lead = EntityDefinition(
        name="lead",
        fields=[
            FieldDef("name", str, required=True, max_length=255),
            FieldDef("email", str, email=True, nullable=True, required=False),
            FieldDef("lead_score", int, default=0),
            FieldDef("status", LeadStatus, default=LeadStatus.NEW),
        ],
        indexes=[["email"]],
    )
    interaction = EntityDefinition(
        name="interaction",
        fields=[
            FieldDef("lead_id", UUID, fk="lead.id"),
            FieldDef("channel", str, max_length=50),
            FieldDef("message", str),
        ],
    )
    return WorkflowDefinition(
        name="Test CRM",
        slug="crm",
        entities=[lead, interaction],
        tools=[ToolDefinition.crud("lead"), ToolDefinition.crud("interaction")],
    )


@pytest.fixture
def single_entity_workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="Simple",
        slug="simple",
        entities=[
            EntityDefinition(name="item", fields=[FieldDef("name", str)]),
        ],
    )


class TestGenerateOrchestrator:
    def test_creates_workflow_directory(self, crm_workflow, tmp_path):
        result = generate_workflow(crm_workflow, tmp_path)
        assert result.exists()
        assert result.name == "crm"

    def test_creates_workflow_init(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        init = tmp_path / "crm" / "__init__.py"
        assert init.exists()
        content = init.read_text()
        assert "crm" in content

    def test_creates_entity_directories(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        assert (tmp_path / "crm" / "lead").is_dir()
        assert (tmp_path / "crm" / "interaction").is_dir()

    def test_creates_all_files_per_entity(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        for entity_name in ["lead", "interaction"]:
            entity_dir = tmp_path / "crm" / entity_name
            assert (entity_dir / "__init__.py").exists()
            assert (entity_dir / "models.py").exists()
            assert (entity_dir / "schemas.py").exists()
            assert (entity_dir / "serialize.py").exists()
            assert (entity_dir / "repository.py").exists()
            assert (entity_dir / "tools.py").exists()

    def test_creates_tools_registry(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        registry = tmp_path / "crm" / "_tools_registry.py"
        assert registry.exists()
        content = registry.read_text()
        assert "register_all_tools" in content
        assert "register_lead" in content
        assert "register_interaction" in content

    def test_tools_registry_valid_python(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        registry = tmp_path / "crm" / "_tools_registry.py"
        content = registry.read_text()
        compile(content, str(registry), "exec")

    def test_all_generated_files_valid_python(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        for py_file in (tmp_path / "crm").rglob("*.py"):
            content = py_file.read_text()
            compile(content, str(py_file), "exec")

    def test_all_files_have_auto_generated_header(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        for py_file in (tmp_path / "crm").rglob("*.py"):
            content = py_file.read_text()
            assert "AUTO-GENERATED" in content, f"Missing header in {py_file}"

    def test_idempotent(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        generate_workflow(crm_workflow, tmp_path)  # Second call should not fail
        assert (tmp_path / "crm" / "lead" / "models.py").exists()

    def test_single_entity(self, single_entity_workflow, tmp_path):
        result = generate_workflow(single_entity_workflow, tmp_path)
        assert (result / "item" / "models.py").exists()
        registry = result / "_tools_registry.py"
        content = registry.read_text()
        assert "register_item" in content

    def test_empty_workflow(self, tmp_path):
        wf = WorkflowDefinition(name="Empty", slug="empty", entities=[])
        result = generate_workflow(wf, tmp_path)
        assert result.exists()
        registry = result / "_tools_registry.py"
        content = registry.read_text()
        assert "pass" in content

    def test_entities_get_slug(self, crm_workflow, tmp_path):
        generate_workflow(crm_workflow, tmp_path)
        models_content = (tmp_path / "crm" / "lead" / "models.py").read_text()
        assert "crm_leads" in models_content
