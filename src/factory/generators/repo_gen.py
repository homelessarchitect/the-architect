"""Repository generator — produces async CRUD repository from EntityDefinition."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from factory.primitives.entity import EntityDefinition

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_repository(entity: EntityDefinition, output_dir: Path) -> Path:
    """Generate an async repository file for the given entity."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = env.get_template("repository.py.j2")
    content = template.render(entity=entity)

    output_path = output_dir / "repository.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return output_path
