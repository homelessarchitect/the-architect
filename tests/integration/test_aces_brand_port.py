import pytest
from pathlib import Path

from architect.generators.orchestrator import generate_workflow
from architect.cli.loader import load_workflow_from_file


@pytest.fixture
def aces_workflow():
    workflow_path = Path(__file__).parent.parent.parent / "examples" / "aces-brand" / "workflow.py"
    return load_workflow_from_file(workflow_path)


class TestAcesBrandPort:
    def test_loads_workflow(self, aces_workflow):
        assert aces_workflow.name == "ACES Content Ops"
        assert aces_workflow.slug == "aces"
        assert len(aces_workflow.entities) == 3

    def test_entities_have_correct_names(self, aces_workflow):
        names = [e.name for e in aces_workflow.entities]
        assert "brand" in names
        assert "persona" in names
        assert "content_idea" in names

    def test_brand_entity_fields(self, aces_workflow):
        brand = next(e for e in aces_workflow.entities if e.name == "brand")
        field_names = [f.name for f in brand.fields]
        assert "name" in field_names
        assert "voice_profile" in field_names
        assert "content_pillars" in field_names
        assert "visual_identity" in field_names
        assert "platforms" in field_names
        assert "is_active" in field_names

    def test_generates_all_code(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        for entity in aces_workflow.entities:
            entity_dir = output_dir / entity.name
            assert (entity_dir / "models.py").exists()
            assert (entity_dir / "schemas.py").exists()
            assert (entity_dir / "tools.py").exists()
            assert (entity_dir / "serialize.py").exists()
            assert (entity_dir / "repository.py").exists()

    def test_all_generated_valid_python(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        for py_file in output_dir.rglob("*.py"):
            content = py_file.read_text()
            compile(content, str(py_file), "exec")

    def test_brand_model_has_jsonb_fields(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        models_content = (output_dir / "brand" / "models.py").read_text()
        assert "JSONB" in models_content
        assert "voice_profile" in models_content
        assert "content_pillars" in models_content

    def test_brand_table_prefixed(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        models_content = (output_dir / "brand" / "models.py").read_text()
        assert "aces_brands" in models_content

    def test_persona_has_fk_to_brand(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        models_content = (output_dir / "persona" / "models.py").read_text()
        assert "ForeignKey" in models_content
        assert "aces_brands.id" in models_content

    def test_content_idea_has_fk_to_both(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        models_content = (output_dir / "content_idea" / "models.py").read_text()
        assert "aces_brands.id" in models_content
        assert "aces_personas.id" in models_content

    def test_tools_have_crud_operations(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        tools_content = (output_dir / "brand" / "tools.py").read_text()
        assert "list_brands" in tools_content
        assert "get_brand" in tools_content
        assert "create_brand" in tools_content
        assert "update_brand" in tools_content
        assert "delete_brand" in tools_content

    def test_registry_has_all_entities(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        registry = (output_dir / "_tools_registry.py").read_text()
        assert "register_brand" in registry
        assert "register_persona" in registry
        assert "register_content_idea" in registry

    def test_schemas_have_create_update_read(self, aces_workflow, tmp_path):
        output_dir = generate_workflow(aces_workflow, tmp_path)
        schemas = (output_dir / "brand" / "schemas.py").read_text()
        assert "BrandCreate" in schemas
        assert "BrandUpdate" in schemas
        assert "BrandRead" in schemas
