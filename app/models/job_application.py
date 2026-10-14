from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('applied', 'screening', 'interview', 'offer', 'hired', 'rejected')",
            name="valid_status",
        ),
        Index("uq_applications_candidate_job", "candidate_id", "job_id", unique=True),
        Index("ix_applications_workspace_status", "workspace_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("job_openings.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="applied", server_default="applied"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
