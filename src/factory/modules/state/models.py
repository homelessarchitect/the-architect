from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from factory.core.database import Base

# JSON type that renders as JSONB on PostgreSQL, plain JSON elsewhere (e.g. SQLite in tests).
PortableJSON = JSON().with_variant(JSONB(), "postgresql")


class WorkflowState(Base):
    __tablename__ = "workflow_states"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lineage: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    schema_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    entities: Mapped[dict] = mapped_column(PortableJSON, nullable=False)
    tools_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tables_list: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=list)
    providers: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="cli")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("workflow_slug", "version", name="uq_workflow_state_slug_version"),
    )


class StateLock(Base):
    __tablename__ = "state_locks"

    workflow_slug: Mapped[str] = mapped_column(String(100), primary_key=True)
    lock_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    locked_by: Mapped[str] = mapped_column(String(100), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
