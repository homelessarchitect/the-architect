"""CRM example — leads with scoring, pipeline, and custom enrichment tool."""

from enum import StrEnum
from uuid import UUID

from architect.primitives import (
    DispatcherDefinition,
    EntityDefinition,
    FieldDef,
    PipelineDefinition,
    ToolDefinition,
    Transition,
    WorkflowDefinition,
)


class LeadStatus(StrEnum):
    NEW = "new"
    ENRICHED = "enriched"
    CONTACTED = "contacted"
    REPLIED = "replied"
    CONVERTED = "converted"
    REJECTED = "rejected"


project = EntityDefinition(
    name="project",
    fields=[
        FieldDef("name", str, required=True, max_length=255, unique=True),
        FieldDef("description", str, required=False, nullable=True),
        FieldDef("icp", dict, required=False, nullable=True),
        FieldDef("scoring_rubric", dict, required=False, nullable=True),
        FieldDef("is_active", bool, default=True),
    ],
    description="Sales playbook — ICP, scoring rules, templates",
)

lead = EntityDefinition(
    name="lead",
    fields=[
        FieldDef("project_id", UUID, fk="project.id"),
        FieldDef("name", str, required=True, max_length=255),
        FieldDef("business_name", str, max_length=255, required=False, nullable=True),
        FieldDef("email", str, email=True, required=False, nullable=True),
        FieldDef("instagram", str, max_length=100, required=False, nullable=True),
        FieldDef("phone", str, max_length=50, required=False, nullable=True),
        FieldDef("lead_score", int, default=0),
        FieldDef("status", LeadStatus, default=LeadStatus.NEW),
        FieldDef("metadata", dict, required=False, nullable=True),
    ],
    indexes=[["email"], ["instagram"]],
    unique_constraints=[["instagram", "business_name"]],
    description="A sales lead in the pipeline",
)

interaction = EntityDefinition(
    name="interaction",
    fields=[
        FieldDef("lead_id", UUID, fk="lead.id"),
        FieldDef("channel", str, max_length=50),
        FieldDef("message", str),
        FieldDef("response", str, required=False, nullable=True),
    ],
    description="Audit log of agent-lead interactions",
)

lead_pipeline = PipelineDefinition(
    entity_name="lead",
    statuses=["new", "enriched", "contacted", "replied", "converted", "rejected"],
    transitions=[
        Transition("new", "enriched"),
        Transition("enriched", "contacted"),
        Transition("contacted", "replied"),
        Transition(
            "replied",
            "converted",
            approval_required=True,
            approval_action_type="convert_lead",
        ),
        Transition("replied", "rejected"),
        Transition("new", "rejected"),
    ],
)

workflow = WorkflowDefinition(
    name="Sales CRM",
    slug="crm",
    entities=[project, lead, interaction],
    pipelines=[lead_pipeline],
    tools=[
        ToolDefinition.crud("project"),
        ToolDefinition.crud("lead"),
        ToolDefinition.crud("interaction"),
    ],
    dispatchers=[
        DispatcherDefinition(
            action_type="convert_lead",
            handler="examples.crm.dispatchers.handle_conversion",
        ),
    ],
    description="ASOS-style CRM with lead scoring, pipeline, and approval gates",
)
