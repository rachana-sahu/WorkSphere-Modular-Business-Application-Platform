from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProjectTask(Base):
    __tablename__ = "project_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'done')", name="valid_status"
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name="valid_priority"
        ),
        Index("ix_project_tasks_project_status", "project_id", "status"),
        Index("ix_project_tasks_workspace_due_date", "workspace_id", "due_date"),
        Index("ix_project_tasks_assigned_to", "assigned_to"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    assigned_to: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="todo", server_default="todo"
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
