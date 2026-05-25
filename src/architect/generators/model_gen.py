"""Model generator — produces SQLAlchemy model files from EntityDefinition."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from architect.primitives.entity import EntityDefinition, _pluralize

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_model(entity: EntityDefinition, output_dir: Path) -> Path:
    """Generate a SQLAlchemy model file for the given entity."""
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["repr"] = repr
    env.globals["pluralize"] = _pluralize
    template = env.get_template("model.py.j2")
    content = template.render(entity=entity)

    output_path = output_dir / "models.py"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return output_path
