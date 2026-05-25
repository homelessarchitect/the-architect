from __future__ import annotations

import re
from dataclasses import dataclass, field

from factory.primitives.agent import AgentDefinition
from factory.primitives.dispatcher import DispatcherDefinition
from factory.primitives.entity import EntityDefinition
from factory.primitives.pipeline import PipelineDefinition
from factory.primitives.tool import ToolDefinition


@dataclass
class WorkflowDefinition:
    """Declarative workflow definition -- the 'Terraform file' for agent workflows."""

    name: str
    slug: str
    entities: list[EntityDefinition] = field(default_factory=list)
    pipelines: list[PipelineDefinition] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)
    dispatchers: list[DispatcherDefinition] = field(default_factory=list)
    providers: list[type] = field(default_factory=list)  # Provider classes
    agent: AgentDefinition | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not re.match(r"^[a-z][a-z0-9\-]*$", self.slug):
            raise ValueError(
                f"Workflow slug '{self.slug}' must be lowercase alphanumeric with hyphens"
            )
        if len(self.slug) < 2 or len(self.slug) > 50:
            raise ValueError(
                f"Workflow slug must be 2-50 characters, got {len(self.slug)}"
            )
        entity_names = [e.name for e in self.entities]
        duplicates = [n for n in entity_names if entity_names.count(n) > 1]
        if duplicates:
            raise ValueError(
                f"Duplicate entity names in workflow '{self.name}': {set(duplicates)}"
            )
        for entity in self.entities:
            entity.slug = self.slug
