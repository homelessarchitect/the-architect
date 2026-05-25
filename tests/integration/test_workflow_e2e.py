from enum import StrEnum

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from factory.core.database import Base
from factory.generators.orchestrator import generate_workflow
from factory.modules.state.service import StateService
from factory.primitives import (
    EntityDefinition,
    FieldDef,
    ToolDefinition,
    WorkflowDefinition,
)


class ItemStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


@pytest.fixture
def todo_workflow() -> WorkflowDefinition:
    item = EntityDefinition(
        name="item",
        fields=[
            FieldDef("title", str, required=True, max_length=255),
            FieldDef("description", str, nullable=True, required=False),
            FieldDef("status", ItemStatus, default=ItemStatus.ACTIVE),
            FieldDef("priority", int, default=0),
        ],
        indexes=[["status"]],
    )
    return WorkflowDefinition(
        name="Todo App",
        slug="todo",
        entities=[item],
        tools=[ToolDefinition.crud("item")],
    )


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


class TestWorkflowE2E:
    def test_generate_creates_all_files(self, todo_workflow, tmp_path):
        output_dir = generate_workflow(todo_workflow, tmp_path)

        assert output_dir.exists()
        assert (output_dir / "__init__.py").exists()

        entity_dir = output_dir / "item"
        assert (entity_dir / "models.py").exists()
        assert (entity_dir / "schemas.py").exists()
        assert (entity_dir / "serialize.py").exists()
        assert (entity_dir / "repository.py").exists()
        assert (entity_dir / "tools.py").exists()

        assert (output_dir / "_tools_registry.py").exists()

    def test_all_generated_files_are_valid_python(self, todo_workflow, tmp_path):
        output_dir = generate_workflow(todo_workflow, tmp_path)
        for py_file in output_dir.rglob("*.py"):
            content = py_file.read_text()
            compile(content, str(py_file), "exec")

    def test_generated_models_contain_entity(self, todo_workflow, tmp_path):
        output_dir = generate_workflow(todo_workflow, tmp_path)
        models_content = (output_dir / "item" / "models.py").read_text()
        assert "class Item(Base):" in models_content
        assert "todo_items" in models_content
        assert "class ItemStatus(StrEnum):" in models_content

    def test_generated_tools_contain_crud(self, todo_workflow, tmp_path):
        output_dir = generate_workflow(todo_workflow, tmp_path)
        tools_content = (output_dir / "item" / "tools.py").read_text()
        assert "list_items" in tools_content
        assert "get_item" in tools_content
        assert "create_item" in tools_content
        assert "update_item" in tools_content
        assert "delete_item" in tools_content

    def test_tools_registry_imports_entity(self, todo_workflow, tmp_path):
        output_dir = generate_workflow(todo_workflow, tmp_path)
        registry_content = (output_dir / "_tools_registry.py").read_text()
        assert "register_all_tools" in registry_content
        assert "register_item" in registry_content

    def test_generation_is_idempotent(self, todo_workflow, tmp_path):
        generate_workflow(todo_workflow, tmp_path)
        generate_workflow(todo_workflow, tmp_path)
        assert (tmp_path / "todo" / "item" / "models.py").exists()

    async def test_state_plan_shows_new(self, todo_workflow, async_session):
        service = StateService(async_session)
        entity_names = [e.name for e in todo_workflow.entities]
        diff = await service.diff_state(todo_workflow.slug, "abc123", entity_names)
        assert diff["status"] == "new"
        assert "item" in diff["entities_to_create"]

    async def test_state_apply_creates_version(self, todo_workflow, async_session):
        service = StateService(async_session)
        entity_names = [e.name for e in todo_workflow.entities]

        state = await service.create_version(
            workflow_slug=todo_workflow.slug,
            schema_hash="abc123",
            entities={"names": entity_names},
            tools_count=5,
            tables_list=[e.table_name for e in todo_workflow.entities],
            providers=[],
        )
        await async_session.commit()

        assert state.version == 1
        assert state.workflow_slug == "todo"

    async def test_state_second_apply_no_changes(self, todo_workflow, async_session):
        service = StateService(async_session)
        entity_names = [e.name for e in todo_workflow.entities]

        await service.create_version(
            workflow_slug=todo_workflow.slug,
            schema_hash="abc123",
            entities={"names": entity_names},
            tools_count=5,
            tables_list=[],
            providers=[],
        )
        await async_session.commit()

        diff = await service.diff_state(todo_workflow.slug, "abc123", entity_names)
        assert diff["status"] == "no_changes"

    async def test_state_increments_version(self, todo_workflow, async_session):
        service = StateService(async_session)
        entity_names = [e.name for e in todo_workflow.entities]

        await service.create_version("todo", "hash1", {"names": entity_names}, 5, [], [])
        await async_session.commit()

        v2 = await service.create_version("todo", "hash2", {"names": entity_names}, 5, [], [])
        await async_session.commit()

        assert v2.version == 2
