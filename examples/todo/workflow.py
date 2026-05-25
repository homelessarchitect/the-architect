"""Minimal example — a todo list workflow with one entity."""

from factory.primitives import (
    EntityDefinition,
    FieldDef,
    ToolDefinition,
    WorkflowDefinition,
)

item = EntityDefinition(
    name="item",
    fields=[
        FieldDef("title", str, required=True, max_length=255),
        FieldDef("done", bool, default=False),
        FieldDef("priority", int, default=0),
    ],
    description="A todo item",
)

workflow = WorkflowDefinition(
    name="Todo",
    slug="todo",
    entities=[item],
    tools=[ToolDefinition.crud("item")],
    description="Minimal todo list — one entity, CRUD tools auto-generated",
)
