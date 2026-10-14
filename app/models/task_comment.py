from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TaskComment(Base):
    __tablename__ = "task_comments"
    __table_args__ = (
        Index("ix_task_comments_task_created", "task_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("project_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
