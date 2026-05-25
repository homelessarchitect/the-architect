"""ACES — Autonomous Content Engine System (full port).

Complete workflow definition porting ALL ACES entities, pipelines, custom tools,
and dispatchers to The Architect's declarative primitives.

Modules EXCLUDED (handled by The Architect core, not per-workflow):
  - api_keys        (shared auth — architect.modules.api_keys)
  - approvals       (shared HITL — architect.modules.approvals)
  - uploads         (stateless file I/O — no DB entity)
  - integrations    (OAuth proxy — no DB entity)
  - integration_settings (provider config — maps to architect.modules.credentials)

Known limitation: FieldDef.type does not support `date` (only `datetime`).
Fields like publish_date, period_start, period_end, planned_date use `str` with
max_length to store ISO date strings. The custom tools handle parsing.

Known limitation: The Jinja FK template appends 's' for pluralization instead of
using _pluralize(). Entity names ending in 'y' (e.g. calendar_entry) will produce
incorrect FK table names (calendar_entrys vs calendar_entries). Renamed to
'calendar_slot' to work around this until the template is fixed.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from architect.primitives import (
    AgentDefinition,
    DispatcherDefinition,
    EntityDefinition,
    FieldDef,
    PipelineDefinition,
    ToolDefinition,
    Transition,
    WorkflowDefinition,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class PersonaType(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    NEGATIVE = "negative"


class IdeaStatus(StrEnum):
    BACKLOG = "backlog"
    BRIEFED = "briefed"
    IN_PRODUCTION = "in-production"
    PUBLISHED = "published"
    DISCARDED = "discarded"


class IdeaSource(StrEnum):
    MANUAL = "manual"
    AI_GENERATED = "ai-generated"
    TRENDING = "trending"


class BriefObjective(StrEnum):
    AWARENESS = "awareness"
    ENGAGEMENT = "engagement"
    TRAFFIC = "traffic"
    CONVERSION = "conversion"
    EDUCATION = "education"


class StorytellingFramework(StrEnum):
    AIDA = "AIDA"
    PAS = "PAS"
    BAB = "BAB"
    STORYBRAND = "StoryBrand"
    PSP = "PSP"


class ContentFormat(StrEnum):
    REEL = "reel"
    CAROUSEL = "carousel"
    STATIC_POST = "static-post"
    STORY = "story"
    THREAD = "thread"
    NEWSLETTER = "newsletter"
    LONG_VIDEO = "long-video"
    SHORT_VIDEO = "short-video"
    BLOG = "blog"
    PODCAST = "podcast"


class ContentPlatform(StrEnum):
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    TWITTER = "twitter"
    NEWSLETTER = "newsletter"
    WEB = "web"


class PieceStatus(StrEnum):
    IDEA = "idea"
    BRIEFED = "briefed"
    SCRIPTED = "scripted"
    IN_PRODUCTION = "in-production"
    REVIEW = "review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ScriptArchetype(StrEnum):
    HOW_TO = "how-to"
    MYTH_BUSTER = "myth-buster"
    CASE_STUDY = "case-study"
    SECRET_TOOL = "secret-tool"
    MISTAKE_HOOK = "mistake-hook"
    POV = "pov"
    TREND_ALERT = "trend-alert"
    ZERO_CLICK_VALUE = "zero-click-value"


class AssetType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    GRAPHIC = "graphic"
    TEMPLATE = "template"


class AssetStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    READY = "ready"
    APPROVED = "approved"


class SlideRole(StrEnum):
    HOOK = "hook"
    STAT = "stat"
    EXPLANATION = "explanation"
    CASE = "case"
    CTA = "cta"
    TRANSITION = "transition"
    OTHER = "other"


class RenderStatus(StrEnum):
    QUEUED = "queued"
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


class CalendarStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class CalendarSlotStatus(StrEnum):
    PLANNED = "planned"
    IN_PRODUCTION = "in-production"
    READY = "ready"
    PUBLISHED = "published"


# ---------------------------------------------------------------------------
# Entity Definitions
# ---------------------------------------------------------------------------

# -- 1. Brand (root entity) ------------------------------------------------

brand = EntityDefinition(
    name="brand",
    fields=[
        FieldDef("name", str, required=True, max_length=255, unique=True),
        FieldDef("description", str, required=False, nullable=True),
        FieldDef(
            "voice_profile", dict, required=False, default=dict,
            description="tone, personality_traits[], yes_phrases[], no_phrases[]",
        ),
        FieldDef(
            "content_pillars", list, required=False, default=list,
            description="[{name, description, examples[]}]",
        ),
        FieldDef(
            "visual_identity", dict, required=False, default=dict,
            description="color_palette, typography, style_notes",
        ),
        FieldDef(
            "platforms", list, required=False, default=list,
            description='["instagram", "tiktok", "linkedin", "newsletter"]',
        ),
        FieldDef("is_active", bool, default=True),
    ],
    indexes=[["is_active"]],
    description="The creative identity -- equivalent to Project in ASOS",
)

# -- 2. Persona (target audience) ------------------------------------------

persona = EntityDefinition(
    name="persona",
    fields=[
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("name", str, required=True, max_length=255),
        FieldDef("type", PersonaType, default=PersonaType.PRIMARY),
        FieldDef(
            "demographics", dict, required=False, default=dict,
            description="age_range, roles[], geography[]",
        ),
        FieldDef("pain_points", list, required=False, default=list),
        FieldDef("goals", list, required=False, default=list),
        FieldDef("content_channels", list, required=False, default=list),
        FieldDef("content_preferences", list, required=False, default=list),
    ],
    indexes=[["brand_id"]],
    description="Target audience persona -- equivalent to Project.ICP in ASOS",
)

# -- 3. Content Idea -------------------------------------------------------

content_idea = EntityDefinition(
    name="content_idea",
    fields=[
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("persona_id", UUID, fk="persona.id", required=False, nullable=True),
        FieldDef("pillar", str, max_length=100, description="Must match Brand.content_pillars"),
        FieldDef("concept", str, description="One-sentence idea"),
        FieldDef("angle", str, description="Specific take/hook direction"),
        FieldDef("formats", list, required=False, default=list),
        FieldDef("source", IdeaSource, default=IdeaSource.MANUAL),
        FieldDef("status", IdeaStatus, default=IdeaStatus.BACKLOG),
    ],
    indexes=[["brand_id"], ["status"]],
    description="A raw content concept before it becomes a brief",
)

# -- 4. Content Brief ------------------------------------------------------

content_brief = EntityDefinition(
    name="content_brief",
    fields=[
        FieldDef("idea_id", UUID, fk="content_idea.id"),
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("objective", BriefObjective, default=BriefObjective.AWARENESS),
        FieldDef("storytelling_framework", StorytellingFramework, default=StorytellingFramework.PSP),
        FieldDef(
            "hook_options", list, required=False, default=list,
            description="3-5 hook variations [{type, text}]",
        ),
        FieldDef(
            "outline", list, required=False, default=list,
            description="Ordered beats [{beat, content}]",
        ),
        FieldDef("cta", str, description="Low-friction call to action"),
        FieldDef("keywords", list, required=False, default=list),
        FieldDef("references", dict, required=False, nullable=True),
        FieldDef("notes", str, required=False, nullable=True),
    ],
    indexes=[["brand_id"]],
    unique_constraints=[["idea_id"]],
    description="The creative brief for a single content piece",
)

# -- 5. Social Account -----------------------------------------------------

social_account = EntityDefinition(
    name="social_account",
    fields=[
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("platform", str, max_length=20),
        FieldDef("display_name", str, max_length=200),
        FieldDef("handle", str, max_length=200, required=False, nullable=True),
        FieldDef("is_active", bool, default=True),
    ],
    indexes=[["brand_id"]],
    description="A social media account linked to a brand",
)

# -- 6. Content Piece (the main pipeline entity) ---------------------------

content_piece = EntityDefinition(
    name="content_piece",
    fields=[
        FieldDef("brief_id", UUID, fk="content_brief.id", required=False, nullable=True),
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("title", str, max_length=500),
        FieldDef("format", ContentFormat, default=ContentFormat.REEL),
        FieldDef("platform", ContentPlatform, default=ContentPlatform.INSTAGRAM),
        FieldDef("raw_copy", str, required=False, nullable=True),
        FieldDef("script_id", UUID, fk="script.id", required=False, nullable=True),
        FieldDef("status", PieceStatus, default=PieceStatus.IDEA),
        FieldDef(
            "publish_date", str, max_length=10, required=False, nullable=True,
            description="ISO date YYYY-MM-DD (stored as str, date type unsupported in FieldDef)",
        ),
        FieldDef(
            "parent_piece_id", UUID, fk="content_piece.id",
            required=False, nullable=True,
            description="FK to self for repurposed pieces",
        ),
        FieldDef(
            "account_id", UUID, fk="social_account.id",
            required=False, nullable=True,
        ),
        FieldDef("tags", list, required=False, default=list),
    ],
    indexes=[["brand_id"], ["status"]],
    description="The main content object -- equivalent to Lead in ASOS",
)

# -- 7. Script (video content structure) -----------------------------------

script = EntityDefinition(
    name="script",
    fields=[
        FieldDef("piece_id", UUID, fk="content_piece.id"),
        FieldDef("archetype", ScriptArchetype, default=ScriptArchetype.HOW_TO),
        FieldDef("hook", str, description="Opening hook -- first 3 seconds"),
        FieldDef(
            "body_beats", list, required=False, default=list,
            description="[{order, beat_type, content, duration_seconds}]",
        ),
        FieldDef("cta", str, description="Low-friction closing CTA"),
        FieldDef("estimated_duration", int, required=False, nullable=True),
        FieldDef("platform_notes", str, required=False, nullable=True),
    ],
    indexes=[["piece_id"]],
    description="Structured video script: hook + body beats + CTA",
)

# -- 8. Slide Plan (carousel planning) ------------------------------------

slide_plan = EntityDefinition(
    name="slide_plan",
    fields=[
        FieldDef("piece_id", UUID, fk="content_piece.id"),
        FieldDef(
            "slots", list, required=False, default=list,
            description="[{order, role, text_overlay, visual_brief, suggested_archetype}]",
        ),
    ],
    indexes=[["piece_id"]],
    unique_constraints=[["piece_id"]],
    description="Carousel slide plan -- ordered slots with role and visual brief",
)

# -- 9. Asset (media files) ------------------------------------------------

asset = EntityDefinition(
    name="asset",
    fields=[
        FieldDef("piece_id", UUID, fk="content_piece.id"),
        FieldDef("type", AssetType, default=AssetType.IMAGE),
        FieldDef(
            "format_specs", dict, required=False, default=dict,
            description="dimensions, aspect_ratio, duration_seconds, file_format",
        ),
        FieldDef("production_brief", str, required=False, nullable=True),
        FieldDef("ai_prompt", str, required=False, nullable=True),
        FieldDef("file_url", str, max_length=1000, required=False, nullable=True),
        FieldDef("status", AssetStatus, default=AssetStatus.PENDING),
    ],
    indexes=[["piece_id"]],
    description="Image, video, audio, or graphic tied to a content piece",
)

# -- 10. Render Job (Remotion renders) -------------------------------------

render_job = EntityDefinition(
    name="render_job",
    fields=[
        FieldDef("piece_id", UUID, fk="content_piece.id"),
        FieldDef("script_id", UUID, fk="script.id", required=False, nullable=True),
        FieldDef("asset_id", UUID, fk="asset.id", required=False, nullable=True, index=True),
        FieldDef("slot_order", int, required=False, nullable=True),
        FieldDef("status", RenderStatus, default=RenderStatus.QUEUED),
        FieldDef("output_path", str, required=False, nullable=True),
        FieldDef("video_url", str, required=False, nullable=True),
        FieldDef("error", str, required=False, nullable=True),
        FieldDef("started_at", datetime, required=False, nullable=True),
        FieldDef("finished_at", datetime, required=False, nullable=True),
    ],
    indexes=[["piece_id"]],
    description="Tracks lifecycle of a Remotion render subprocess",
)

# -- 11. Content Calendar --------------------------------------------------

content_calendar = EntityDefinition(
    name="content_calendar",
    fields=[
        FieldDef("brand_id", UUID, fk="brand.id"),
        FieldDef("name", str, max_length=200),
        FieldDef("editorial_theme", str, description="Macro narrative for this period"),
        FieldDef(
            "period_start", str, max_length=10,
            description="ISO date YYYY-MM-DD",
        ),
        FieldDef(
            "period_end", str, max_length=10,
            description="ISO date YYYY-MM-DD",
        ),
        FieldDef(
            "platform_frequency", dict, required=False, default=dict,
            description='{instagram: 5, tiktok: 7, newsletter: 1} per week',
        ),
        FieldDef("status", CalendarStatus, default=CalendarStatus.DRAFT),
    ],
    indexes=[["brand_id"]],
    description="Editorial planning for a time period -- equivalent to Campaign in ASOS",
)

# -- 12. Calendar Slot (renamed from CalendarEntry to avoid pluralization bug)

calendar_slot = EntityDefinition(
    name="calendar_slot",
    fields=[
        FieldDef("calendar_id", UUID, fk="content_calendar.id"),
        FieldDef("piece_id", UUID, fk="content_piece.id", required=False, nullable=True),
        FieldDef(
            "planned_date", str, max_length=10,
            description="ISO date YYYY-MM-DD",
        ),
        FieldDef("platform", str, max_length=20),
        FieldDef("format", str, max_length=20),
        FieldDef("pillar", str, max_length=100),
        FieldDef("status", CalendarSlotStatus, default=CalendarSlotStatus.PLANNED),
    ],
    indexes=[["calendar_id"], ["planned_date"]],
    description="A single planned post within a content calendar",
)

# -- 13. Published Content -------------------------------------------------

published_content = EntityDefinition(
    name="published_content",
    fields=[
        FieldDef("piece_id", UUID, fk="content_piece.id", unique=True),
        FieldDef("platform", str, max_length=20),
        FieldDef("published_at", datetime),
        FieldDef("url", str, max_length=1000, required=False, nullable=True),
        FieldDef(
            "platform_post_id", str, max_length=200, required=False, nullable=True,
            description="Native platform ID for fetching metrics",
        ),
    ],
    indexes=[["piece_id"]],
    description="A content piece that was published live",
)

# -- 14. Content Metric (performance snapshots) ----------------------------

content_metric = EntityDefinition(
    name="content_metric",
    fields=[
        FieldDef("published_id", UUID, fk="published_content.id"),
        FieldDef("reach", int, default=0),
        FieldDef("impressions", int, default=0),
        FieldDef("engagement_rate", float, default=0.0),
        FieldDef("likes", int, default=0),
        FieldDef("comments", int, default=0),
        FieldDef("shares", int, default=0),
        FieldDef("saves", int, default=0),
        FieldDef("clicks", int, default=0),
        FieldDef("completion_rate", float, required=False, nullable=True),
        FieldDef("conversions", int, required=False, nullable=True),
        FieldDef("captured_at", datetime),
    ],
    indexes=[["published_id"]],
    description="Performance snapshot for a published piece (multiple per piece)",
)


# ---------------------------------------------------------------------------
# Pipeline Definitions (status machines with approval gates)
# ---------------------------------------------------------------------------

# ContentIdea pipeline: backlog -> briefed -> in-production -> published | discarded
idea_pipeline = PipelineDefinition(
    entity_name="content_idea",
    statuses=["backlog", "briefed", "in-production", "published", "discarded"],
    transitions=[
        Transition("backlog", "briefed"),
        Transition("briefed", "in-production"),
        Transition("in-production", "published"),
        Transition("backlog", "discarded"),
        Transition("briefed", "discarded"),
        Transition("in-production", "discarded"),
    ],
    initial_status="backlog",
)

# ContentPiece pipeline: idea -> ... -> published | archived
# The main production pipeline with HITL gates at review->approved and approved->published
piece_pipeline = PipelineDefinition(
    entity_name="content_piece",
    statuses=[
        "idea", "briefed", "scripted", "in-production",
        "review", "approved", "scheduled", "published", "archived",
    ],
    transitions=[
        Transition("idea", "briefed"),
        Transition("briefed", "scripted"),
        Transition("briefed", "in-production"),
        Transition("scripted", "in-production"),
        Transition("in-production", "review"),
        Transition(
            "review", "approved",
            approval_required=True,
            approval_action_type="publish_piece",
        ),
        Transition("approved", "scheduled"),
        Transition("approved", "published"),
        Transition("scheduled", "published"),
        Transition("published", "archived"),
        # Rejection loops
        Transition("review", "in-production"),
        Transition("idea", "archived"),
    ],
    initial_status="idea",
)

# Asset pipeline: pending -> in-progress -> ready -> approved
asset_pipeline = PipelineDefinition(
    entity_name="asset",
    statuses=["pending", "in-progress", "ready", "approved"],
    transitions=[
        Transition("pending", "in-progress"),
        Transition("in-progress", "ready"),
        Transition("ready", "approved"),
    ],
    initial_status="pending",
)

# RenderJob pipeline: queued -> rendering -> ready | failed
render_pipeline = PipelineDefinition(
    entity_name="render_job",
    statuses=["queued", "rendering", "ready", "failed"],
    transitions=[
        Transition("queued", "rendering"),
        Transition("rendering", "ready"),
        Transition("rendering", "failed"),
    ],
    initial_status="queued",
)

# ContentCalendar pipeline: draft -> active -> completed -> archived
calendar_pipeline = PipelineDefinition(
    entity_name="content_calendar",
    statuses=["draft", "active", "completed", "archived"],
    transitions=[
        Transition("draft", "active"),
        Transition("active", "completed"),
        Transition("completed", "archived"),
    ],
    initial_status="draft",
)

# CalendarSlot pipeline: planned -> in-production -> ready -> published
calendar_slot_pipeline = PipelineDefinition(
    entity_name="calendar_slot",
    statuses=["planned", "in-production", "ready", "published"],
    transitions=[
        Transition("planned", "in-production"),
        Transition("in-production", "ready"),
        Transition("ready", "published"),
    ],
    initial_status="planned",
)


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------
# CRUD tools are auto-generated. Custom tools need ToolDefinition.custom().
# Custom tools are domain-specific logic that goes beyond simple CRUD.
# Their dotpath points to the module where register(mcp) lives.

tools = [
    # -- CRUD for all entities --
    ToolDefinition.crud("brand"),
    ToolDefinition.crud("persona"),
    ToolDefinition.crud("content_idea"),
    ToolDefinition.crud("content_brief"),
    ToolDefinition.crud("social_account"),
    ToolDefinition.crud("content_piece"),
    ToolDefinition.crud("script"),
    ToolDefinition.crud("slide_plan"),
    ToolDefinition.crud("asset"),
    ToolDefinition.crud("render_job"),
    ToolDefinition.crud("content_calendar"),
    ToolDefinition.crud("calendar_slot"),
    ToolDefinition.crud("published_content"),
    ToolDefinition.crud("content_metric"),
    # -- Custom: Agent Context --
    ToolDefinition.custom(
        "examples.aces.custom_tools.context",
        description=(
            "get_agent_context: orientation snapshot -- active brands, "
            "pending approvals, pieces in review, calendar slots due in 7 days"
        ),
    ),
    # -- Custom: Idea Generation --
    ToolDefinition.custom(
        "examples.aces.custom_tools.ideas",
        description=(
            "generate_content_ideas: context-fetcher for Claude to reason "
            "and produce ideas, then call create_idea for each"
        ),
    ),
    # -- Custom: Brief Generation --
    ToolDefinition.custom(
        "examples.aces.custom_tools.briefs",
        description=(
            "get_brief_context: context-fetcher for brief generation with "
            "idea + brand voice + framework structure"
        ),
    ),
    # -- Custom: Copy & Hook Generation, Content Adaptation --
    ToolDefinition.custom(
        "examples.aces.custom_tools.pieces",
        description=(
            "generate_copy, generate_hooks, adapt_content, update_piece_copy: "
            "context-fetchers + save helpers for copy generation and repurposing"
        ),
    ),
    # -- Custom: Script Generation --
    ToolDefinition.custom(
        "examples.aces.custom_tools.scripts",
        description=(
            "generate_script: context-fetcher for video script writing; "
            "save_script: persist generated script and transition piece status"
        ),
    ),
    # -- Custom: Slide Plan Generation --
    ToolDefinition.custom(
        "examples.aces.custom_tools.slide_plans",
        description=(
            "generate_slide_plan_context: context-fetcher for carousel planning; "
            "plan_carousel_slides: persist slide plan + pre-create asset records"
        ),
    ),
    # -- Custom: Asset Prompt Generation --
    ToolDefinition.custom(
        "examples.aces.custom_tools.assets",
        description=(
            "get_image_prompt_context, get_motion_brief_context: "
            "context-fetchers for AI prompt and motion brief generation"
        ),
    ),
    # -- Custom: Gemini Image Generation --
    ToolDefinition.custom(
        "examples.aces.custom_tools.images",
        description=(
            "generate_image_with_gemini: generate image via Google Gemini "
            "and save to uploads, returns public URL"
        ),
    ),
    # -- Custom: Remotion Render Management --
    ToolDefinition.custom(
        "examples.aces.custom_tools.renders",
        description=(
            "render_reel, render_carousel_slide, get_render_status: "
            "enqueue Remotion renders and poll for completion"
        ),
    ),
    # -- Custom: Calendar Build --
    ToolDefinition.custom(
        "examples.aces.custom_tools.calendar",
        description=(
            "get_calendar_build_context, get_calendar_overview: "
            "context-fetchers for editorial calendar planning"
        ),
    ),
    # -- Custom: Content Intelligence / Research --
    ToolDefinition.custom(
        "examples.aces.custom_tools.research",
        description=(
            "get_viral_research_context: Exa trending search for idea discovery; "
            "analyze_content_gaps: gap analysis vs competitors"
        ),
    ),
    # -- Custom: Analytics & Optimization --
    ToolDefinition.custom(
        "examples.aces.custom_tools.analytics",
        description=(
            "record_published, log_metrics, analyze_performance, "
            "identify_best_performers, suggest_optimizations: "
            "performance tracking and data-driven content optimization"
        ),
    ),
    # -- Custom: Approvals (HITL publish/newsletter) --
    ToolDefinition.custom(
        "examples.aces.custom_tools.approvals",
        description=(
            "request_publish, request_newsletter_send: "
            "queue HITL approval requests (never auto-execute)"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Dispatcher Definitions (execute approved HITL actions)
# ---------------------------------------------------------------------------

dispatchers = [
    # Publish to Instagram (image or reel) or LinkedIn
    DispatcherDefinition(
        action_type="publish_piece",
        handler="examples.aces.dispatchers.execute_publish",
    ),
    # Send newsletter via Lumail
    DispatcherDefinition(
        action_type="send_newsletter",
        handler="examples.aces.dispatchers.execute_newsletter_send",
    ),
]


# ---------------------------------------------------------------------------
# Agent Configuration
# ---------------------------------------------------------------------------

agent = AgentDefinition(
    memory=True,
    experience_capture=["observation", "decision", "outcome", "pattern"],
    description=(
        "Content operations agent for ACES. Manages the full production loop: "
        "ideation -> briefing -> scripting -> asset production -> publish (HITL) -> analytics. "
        "Handles repurposing loop: one hero piece -> multiple format adaptations."
    ),
)


# ---------------------------------------------------------------------------
# Workflow Definition (the single export)
# ---------------------------------------------------------------------------

workflow = WorkflowDefinition(
    name="ACES Content Ops",
    slug="aces",
    entities=[
        brand,
        persona,
        content_idea,
        content_brief,
        social_account,
        content_piece,
        script,
        slide_plan,
        asset,
        render_job,
        content_calendar,
        calendar_slot,
        published_content,
        content_metric,
    ],
    pipelines=[
        idea_pipeline,
        piece_pipeline,
        asset_pipeline,
        render_pipeline,
        calendar_pipeline,
        calendar_slot_pipeline,
    ],
    tools=tools,
    dispatchers=dispatchers,
    agent=agent,
    description=(
        "Autonomous Content Engine System -- agent-first content production OS. "
        "Claude Code reasons, generates, and decides. The backend persists. "
        "HITL before any publish action. Repurposing is the killer feature."
    ),
)
