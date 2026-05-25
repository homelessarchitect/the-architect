"""Dynamic workflow file loader — imports a .py file and extracts the WorkflowDefinition."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from architect.primitives.workflow import WorkflowDefinition


def load_workflow_from_file(path: str | Path) -> WorkflowDefinition:
    """Load a Python file and return the first ``WorkflowDefinition`` found at module level.

    Raises:
        FileNotFoundError: If *path* does not exist.
        RuntimeError: If the module cannot be loaded or contains no ``WorkflowDefinition``.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    spec = importlib.util.spec_from_file_location("workflow_module", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, WorkflowDefinition):
            return attr

    raise RuntimeError(
        f"No WorkflowDefinition found in {path}. "
        f"Define a module-level variable of type WorkflowDefinition."
    )
