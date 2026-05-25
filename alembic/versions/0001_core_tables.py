"""Create core tables.

Revision ID: 0001
Revises:
Create Date: 2026-05-24

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- api_keys ---
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(12), nullable=False, unique=True),
        sa.Column("hashed_key", sa.String(255), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- credentials ---
    op.create_table(
        "credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("encrypted_data", sa.LargeBinary, nullable=False),
        sa.Column("scope_workflow", sa.String(100), nullable=True),
        sa.Column("scope_agent", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- workflow_states ---
    op.create_table(
        "workflow_states",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_slug", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("lineage", UUID(as_uuid=True), nullable=False),
        sa.Column("schema_hash", sa.String(64), nullable=False),
        sa.Column("entities", JSONB, nullable=False),
        sa.Column("tools_count", sa.Integer, nullable=False),
        sa.Column("tables_list", JSONB, nullable=False),
        sa.Column("providers", JSONB, nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workflow_slug", "version", name="uq_workflow_state_slug_version"
        ),
    )

    # --- state_locks ---
    op.create_table(
        "state_locks",
        sa.Column("workflow_slug", sa.String(100), primary_key=True),
        sa.Column("lock_id", UUID(as_uuid=True), nullable=False),
        sa.Column("locked_by", sa.String(100), nullable=False),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
    )

    # --- token_budgets ---
    op.create_table(
        "token_budgets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_slug", sa.String(100), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("max_tokens", sa.Integer, nullable=False),
        sa.Column("current_usage", sa.Integer, nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "workflow_slug", "period", name="uq_token_budget_slug_period"
        ),
    )

    # --- workflow_executions (must come before execution_steps due to FK) ---
    op.create_table(
        "workflow_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_slug", sa.String(100), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("token_usage", JSONB, nullable=False),
        sa.Column("metadata", JSONB, nullable=False),
    )

    # --- execution_steps (FK -> workflow_executions) ---
    op.create_table(
        "execution_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "execution_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(200), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- Index on execution_steps.execution_id for FK lookups ---
    op.create_index(
        "ix_execution_steps_execution_id",
        "execution_steps",
        ["execution_id"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_execution_steps_execution_id", table_name="execution_steps")
    op.drop_table("execution_steps")
    op.drop_table("workflow_executions")
    op.drop_table("token_budgets")
    op.drop_table("state_locks")
    op.drop_table("workflow_states")
    op.drop_table("credentials")
    op.drop_table("api_keys")
