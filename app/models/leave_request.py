from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="valid_status"
        ),
        CheckConstraint("end_date >= start_date", name="valid_date_range"),
        Index("ix_leave_requests_workspace_status", "workspace_id", "status"),
        Index("ix_leave_requests_employee_dates", "employee_id", "start_date", "end_date"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
