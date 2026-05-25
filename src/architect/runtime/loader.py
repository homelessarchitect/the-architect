from __future__ import annotations

import importlib
from typing import Any

from architect.primitives.workflow import WorkflowDefinition


def load_workflow_module(workflow: WorkflowDefinition) -> dict[str, Any]:
    """Load generated code for a workflow and return a module dict for create_app."""
    module_path = f"architect.generated.{workflow.slug}._tools_registry"
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise RuntimeError(
            f"Generated code for workflow '{workflow.slug}' not found. "
            f"Run 'architect apply' first. (Module: {module_path})"
        ) from e

    return {
        "slug": workflow.slug,
        "register_fn": module.register_all_tools,
    }


def load_workflows(workflows: list[WorkflowDefinition]) -> list[dict[str, Any]]:
    """Load multiple workflows."""
    return [load_workflow_module(wf) for wf in workflows]
