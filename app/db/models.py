import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class WorkflowRequest(Base):
    __tablename__ = "workflow_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus), default=WorkflowStatus.PENDING, nullable=False
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    structured_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent_tasks: Mapped[list["AgentTask"]] = relationship(
        back_populates="workflow_request", cascade="all, delete-orphan"
    )


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workflow_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_requests.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    succeeded: Mapped[bool | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    workflow_request: Mapped["WorkflowRequest"] = relationship(
        back_populates="agent_tasks"
    )
