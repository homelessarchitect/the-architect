"""Tool generator — produces MCP CRUD tool files from EntityDefinition."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from architect.primitives.entity import EntityDefinition

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _compute_filter_fields(entity: EntityDefinition) -> list:
    """Compute fields that should appear as filters in the list tool.

    Includes: fields with index=True, FK fields, and fields referenced
    in entity-level composite indexes.
    """
    from architect.primitives.entity import FieldDef

    seen: set[str] = set()
    result: list[FieldDef] = []

    # Fields with field-level index=True
    for f in entity.indexed_fields:
        if f.name not in seen:
            seen.add(f.name)
            result.append(f)

    # Fields from entity-level composite indexes
    field_map = {f.name: f for f in entity.fields}
    for idx_fields in entity.indexes:
        for field_name in idx_fields:
            if field_name not in seen and field_name in field_map:
                seen.add(field_name)
                result.append(field_map[field_name])

    # FK fields (always filterable)
    for f in entity.fk_fields:
        if f.name not in seen:
            seen.add(f.name)
            result.append(f)

    return result


def generate_tools(entity: EntityDefinition, output_dir: Path) -> Path:
    """Generate an MCP tools file for the given entity."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["repr"] = repr
    env.filters["escape_desc"] = lambda s: str(s).replace('"', "'") if s else s
    template = env.get_template("tool.py.j2")

    filter_fields = _compute_filter_fields(entity)
    content = template.render(entity=entity, filter_fields=filter_fields)

    output_path = output_dir / "tools.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return output_path
