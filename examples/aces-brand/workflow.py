"""ACES Brand entity port — validates The Architect generates code matching hand-written quality."""

from uuid import UUID

from architect.primitives import (
    EntityDefinition,
    FieldDef,
    ToolDefinition,
    WorkflowDefinition,
)

brand = EntityDefinition(
    name="brand",
    fields=[
        FieldDef("name", str, required=True, max_length=255, unique=True),
        FieldDef("description", str, required=False, nullable=True),
        FieldDef("voice_profile", dict, required=False, nullable=True),
        FieldDef("content_pillars", list, required=False, nullable=True),
        FieldDef("visual_identity", dict, required=False, nullable=True),
        FieldDef("platforms", list, required=False, nullable=True),
        FieldDef("is_active", bool, default=True),
    ],
    description="The creative identity — equivalent to Project in ASOS",
)

persona = EntityDefinition(
    name="persona",
    fields=[
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("name", str, required=True, max_length=255),
        FieldDef("type", str, max_length=50, required=True),
        FieldDef("demographics", dict, required=False, nullable=True),
        FieldDef("pain_points", list, required=False, nullable=True),
        FieldDef("goals", list, required=False, nullable=True),
        FieldDef("content_channels", list, required=False, nullable=True),
        FieldDef("content_preferences", list, required=False, nullable=True),
    ],
    description="Target audience — equivalent to Project.ICP in ASOS",
)

content_idea = EntityDefinition(
    name="content_idea",
    fields=[
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("persona_id", UUID, fk="persona.id", required=False, nullable=True),
        FieldDef("pillar", str, max_length=100),
        FieldDef("concept", str),
        FieldDef("angle", str, required=False, nullable=True),
        FieldDef("formats", list, required=False, nullable=True),
        FieldDef("source", str, max_length=50, default="manual"),
        FieldDef("status", str, max_length=50, default="backlog"),
    ],
    description="A raw content concept before it becomes a brief",
)

workflow = WorkflowDefinition(
    name="ACES Content Ops",
    slug="aces",
    entities=[brand, persona, content_idea],
    tools=[
        ToolDefinition.crud("brand"),
        ToolDefinition.crud("persona"),
        ToolDefinition.crud("content_idea"),
    ],
    description="Subset of ACES — validates The Architect generates code matching hand-written quality",
)
