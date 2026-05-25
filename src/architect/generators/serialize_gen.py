"""Serialize generator — produces _serialize() functions from EntityDefinition."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from architect.primitives.entity import EntityDefinition

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_serialize(entity: EntityDefinition, output_dir: Path) -> Path:
    """Generate a serialize function file for the given entity."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = env.get_template("serialize.py.j2")
    content = template.render(entity=entity)

    output_path = output_dir / "serialize.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return output_path
